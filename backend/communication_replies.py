"""Bounded incremental mailbox reads; exact conversation association, never domain/subject matching."""
import base64
import json
import re
import time
from email.utils import getaddresses
from html.parser import HTMLParser
from sqlalchemy import select
from .db import SessionLocal
from .models import Lead, LeadActivity, User
from .opportunity_models import RecipientPolicy
from .communication_models import ChannelAccount, OutboxMessage, ReceivedMessage
from .communication import lock, compact, adapter_for, cancel_pending, finish_task
from .gmail_adapter import AuthenticationRequired, ProviderRejected, ProviderUnavailable, provider_id


def headers(message):
    result={}
    for h in message.get('payload',{}).get('headers',[])[:200]:
        name=str(h.get('name','')).lower();value=str(h.get('value',''))[:8000]
        # Duplicate critical headers are ambiguous; never silently choose the convenient one.
        result[name]=value if name not in result else ''
    return result


def participants(value):
    from .security import normalize_email
    try: return {normalize_email(addr) for _,addr in getaddresses([value]) if addr}
    except ValueError: return set()


class PlainHTML(HTMLParser):
    def __init__(self): super().__init__(convert_charrefs=True);self.parts=[];self.hidden=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style','iframe','object','svg','template','noscript'): self.hidden+=1
        if tag in ('p','br','div','li') and not self.hidden: self.parts.append('\n')
    def handle_endtag(self,tag):
        if tag in ('script','style','iframe','object','svg','template','noscript') and self.hidden: self.hidden-=1
    def handle_data(self,data):
        if not self.hidden: self.parts.append(data)


def text_body(message):
    plain=[];html=[]
    def walk(part,depth=0):
        if depth>8 or part.get('filename'): return
        mime=part.get('mimeType','');body=part.get('body',{})
        encoded=body.get('data','')
        if isinstance(encoded,str) and len(encoded)<=200000 and mime in ('text/plain','text/html'):
            try:
                value=base64.urlsafe_b64decode(encoded+'='*(-len(encoded)%4)).decode('utf-8',errors='replace')[:32000]
                (plain if mime=='text/plain' else html).append(value)
            except (ValueError,TypeError): pass
        for child in part.get('parts',[])[:30]: walk(child,depth+1)
    walk(message.get('payload',{}))
    value='\n'.join(plain)
    if not value and html:
        parser=PlainHTML();parser.feed('\n'.join(html)[:32000]);value=''.join(parser.parts)
    # Do not retain quoted previous conversations, attachments, tracking or active HTML.
    lines=[]
    for line in value.splitlines():
        if re.match(r'^\s*(>|On .+wrote:|Em .+escreveu:|El .+escribi[oó]:|[-_]{3,})',line,re.I): break
        lines.append(line)
    return ''.join(c for c in '\n'.join(lines).strip() if c in '\n\t' or ord(c)>=32)[:4000]


def classify(text,h):
    auto=h.get('auto-submitted','').lower()
    if (auto and auto!='no') or h.get('x-autoreply') or h.get('x-autorespond'):
        return 'automatic_reply','Aguardar retorno humano; não preparar follow-up automático.'
    if 'delivery-status' in h.get('content-type','').lower():
        return 'delivery_failure','Verificar falha de entrega antes de qualquer nova abordagem.'
    normalized=' '.join(text.casefold().split())
    # Require a short, direct request. Questions/quoted material are not reliable positive labels.
    if re.search(r'\b(remova meu (e-?mail|contato)|remove me|unsubscribe|pare de (me )?enviar|não (me )?envie mais|no me (env[ií]e|contacte))\b',normalized):
        return 'opt_out','Contato suprimido a pedido do destinatário.'
    if re.search(r'\b(não (temos|tenho) interesse|not interested|no (tenemos|tengo) inter[eé]s)\b',normalized):
        return 'refusal','Interromper follow-ups; respeitar a recusa.'
    if len(normalized)>1200: return 'insufficient','Revisar a resposta antes de definir a próxima ação.'
    if re.search(r'\b(fora do (nosso )?orçamento|too expensive|sem orçamento|sin presupuesto)\b',normalized):
        return 'objection','Revisar a objeção e preparar uma proposta adequada, sem envio automático.'
    if re.search(r'\b(pode(m)? (me |nos )?(enviar|explicar)|could you (send|explain)|mais informações|more information|m[aá]s informaci[oó]n)\b',normalized):
        return 'information_request','Preparar as informações solicitadas para revisão.'
    if re.search(r'\b(temos interesse|tenho interesse|we are interested|i am interested|tenemos inter[eé]s|vamos agendar)\b',normalized):
        return 'interest','Revisar o interesse e preparar resposta contextualizada.'
    return 'insufficient','Revisar a resposta antes de definir a próxima ação.'


def ingest(db,account,message,now):
    mid=provider_id(message.get('id'));tid=provider_id(message.get('threadId'))
    if db.scalar(select(ReceivedMessage.id).where(ReceivedMessage.account_id==account.id,ReceivedMessage.provider_id==mid)): return
    if 'SENT' in message.get('labelIds',[]) or 'DRAFT' in message.get('labelIds',[]): return
    h=headers(message);sender=participants(h.get('from',''));to=participants(h.get('to',''))
    refs=set(re.findall(r'<[^<>\s]{1,198}>',h.get('in-reply-to','')+' '+h.get('references','')))
    candidates=db.scalars(select(OutboxMessage).where(OutboxMessage.user_id==account.user_id,
        OutboxMessage.account_id==account.id,OutboxMessage.thread_id==tid,OutboxMessage.status=='accepted')).all()
    matches=[x for x in candidates if x.message_id in refs and sender=={x.recipient} and account.identity in to and not h.get('cc')]
    leads={x.lead_id for x in matches if x.lead_id}
    association='matched' if len(leads)==1 else 'ambiguous' if len(leads)>1 else 'unmatched'
    # Unknown/ambiguous messages retain only provider IDs and status, not mailbox content.
    lead=db.get(Lead,next(iter(leads))) if association=='matched' else None
    if lead and lead.user_id!=account.user_id: lead=None;association='unmatched'
    text=text_body(message) if lead else ''
    classification,recommendation=classify(text,h) if lead else ('insufficient','')
    try: sent_at=int(message.get('internalDate',0))//1000
    except (ValueError,TypeError): sent_at=0
    if sent_at<=0 or sent_at>now+300: sent_at=now
    row=ReceivedMessage(user_id=account.user_id,account_id=account.id,lead_id=lead.id if lead else None,
        provider_id=mid,thread_id=tid,classification=classification,association=association,text=text,sent_at=sent_at,received_at=now)
    db.add(row)
    if not lead: return
    latest=db.scalar(select(ReceivedMessage.sent_at).where(ReceivedMessage.user_id==account.user_id,ReceivedMessage.lead_id==lead.id,
        ReceivedMessage.id!=row.id).order_by(ReceivedMessage.sent_at.desc()).limit(1)) or 0
    db.add(LeadActivity(user_id=account.user_id,lead_id=lead.id,kind='reply',body=text or 'Resposta sem texto legível; revisão necessária.',
        metadata_json=compact({'event':'outreach_reply','message_id':mid,'account_id':account.id,'classification':classification,
            'classification_method':'conservative-rules-v1','recommendation':recommendation,'sent_at':sent_at})))
    if sent_at>=latest and lead.stage not in ('won','lost') and not lead.next_action:
        lead.next_action=recommendation[:180];lead.next_action_on=None
    if classification in ('opt_out','refusal','delivery_failure'):
        recipient=next(iter(sender))
        policy=db.scalar(select(RecipientPolicy).where(RecipientPolicy.user_id==account.user_id,RecipientPolicy.channel=='email',RecipientPolicy.recipient==recipient))
        if policy:
            policy.blocked=1;policy.reason='Resposta recebida: '+classification;policy.recorded_at=now;policy.version+=1
        cancel_pending(db,account.user_id,recipient=recipient,reason='Resposta recebida: '+classification)
        from .opportunity_workflow import pause_drafts
        if classification in ('opt_out','refusal'):
            lead.contact_blocked=True;lead.contact_block_reason='Resposta recebida: '+classification
            pause_drafts(db,lead,'Resposta recebida interrompe contato e follow-ups.')


def collect(adapter,account,known_threads):
    state=json.loads(account.sync_json)
    messages=[];cursor=account.cursor
    if state.get('mode')=='rescan':
        pending=state['threads']
        for tid in pending[:3]:
            thread=adapter.thread(tid).get('messages',[])
            if len(thread)>100: state['truncated']=True
            messages.extend(thread[-100:])
        state['threads']=pending[3:]
        if not state['threads']:
            cursor=state['target_cursor'];state={'coverage':'known_threads_only','last_rescan_at':int(time.time()),'truncated':state.get('truncated',False)}
        return messages,cursor,state
    pending=state.get('pending_ids',[])
    if not pending:
        try: page=adapter.history(cursor,state.get('page_token',''))
        except ProviderRejected as exc:
            if str(exc)!='not_found': raise
            profile=adapter.profile()
            return [],cursor,{'mode':'rescan','threads':sorted(known_threads)[:500],
                'target_cursor':profile['cursor'],'coverage':'known_threads_only','truncated':len(known_threads)>500}
        additions=[x.get('message',{}) for entry in page.get('history',[]) for x in entry.get('messagesAdded',[])]
        pending=list(dict.fromkeys(provider_id(m.get('id')) for m in additions if m.get('threadId') in known_threads))
        if len(pending)>1000: raise ProviderUnavailable('Página de histórico excede o limite seguro.')
        state={'pending_ids':pending,'page_token':str(page.get('nextPageToken',''))[:2000],
            'target_cursor':str(int(page['historyId'])),'coverage':'known_threads_only','truncated':state.get('truncated',False)}
    for mid in pending[:8]: messages.append(adapter.message(mid))
    state['pending_ids']=pending[8:]
    if not state['pending_ids'] and not state['page_token']:
        cursor=state['target_cursor'];state={'coverage':'known_threads_only','truncated':state.get('truncated',False)}
    return messages,cursor,state


def execute_sync(task,adapter_factory=None):
    with SessionLocal() as db:
        account=db.get(ChannelAccount,task['id']);user=db.get(User,account.user_id) if account else None
        if (not account or not user or not user.is_active or account.lease_token!=task['token']
            or not account.sync_enabled or account.status!='connected'): return False
        known=set(db.scalars(select(OutboxMessage.thread_id).where(OutboxMessage.account_id==account.id,
            OutboxMessage.user_id==account.user_id,OutboxMessage.status=='accepted',OutboxMessage.thread_id!='')).all())
    result=None;auth_error=False
    try:
        adapter=(adapter_factory or adapter_for)(account)
        result=collect(adapter,account,known)
    except AuthenticationRequired: auth_error=True
    except Exception: pass
    now=int(time.time())
    with SessionLocal() as db:
        lock(db);current=db.get(ChannelAccount,account.id)
        if (not current or current.lease_token!=task['token'] or current.lease_until<=now or current.version!=account.version
            or not current.sync_enabled or current.status!='connected'): return False
        current.lease_token='';current.lease_until=0;current.next_sync_at=now+300
        if result:
            messages,cursor,state=result
            for message in messages: ingest(db,current,message,now)
            current.cursor=cursor;current.sync_json=compact(state);current.error='';current.attempts=0
            if state.get('pending_ids') or state.get('page_token') or state.get('mode')=='rescan': current.next_sync_at=now+60
        else:
            current.error='Sincronização interrompida; cursor preservado.'
            if auth_error:
                current.status='reconnect_required';current.version+=1
                cancel_pending(db,current.user_id,account_id=current.id,reason='Reconexão Gmail necessária.')
            elif current.attempts>=3:
                current.sync_enabled=0;current.error='Sincronização pausada após três falhas; revise e reative.'
        finish_task(db,task,now,'committed' if result else 'failed');db.commit()
    return bool(result)
