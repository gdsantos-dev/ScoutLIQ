"""Shared, deny-by-default outbox. Content approval never implies send authorization."""
import hashlib
import json
import os
import re
import time
from email.utils import formatdate
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from sqlalchemy import select, update, func, or_
from sqlalchemy.orm import Session
from .db import get_db, SessionLocal
from .models import User, Lead, LeadActivity, ResearchExecutor, uid
from .opportunity_models import OutreachDraft, RecipientPolicy
from .opportunity_workflow import owned, content_eligibility, activity
from .outreach_intelligence import policy_for
from .schemas import StrictModel
from .security import current_user, limiter
from .communication_models import ChannelAccount, ContactVerification, OutboxMessage, MessageEvent, ReceivedMessage
from .gmail_adapter import enabled, ProviderUnavailable, AuthenticationRequired, ProviderRejected, ProviderUncertain
from .consumption import ConsumptionLimit

router = APIRouter(prefix='/api/communication')
WAITING = ('queued','scheduled')
ACTIVE = WAITING + ('executing',)


def compact(value): return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def digest(value): return hashlib.sha256(compact(value).encode()).hexdigest()


def lock(db):
    # Reuses the executor row as a short write fence, never takes/replaces its lease.
    db.execute(update(ResearchExecutor).where(ResearchExecutor.id==1).values(next_at=ResearchExecutor.next_at))


def limits():
    try:
        daily = int(os.getenv('OUTREACH_DAILY_SEND_LIMIT','0'))
        interval = int(os.getenv('OUTREACH_MIN_INTERVAL_SECONDS','60'))
        markets = os.getenv('OUTREACH_ALLOWED_MARKETS','').split(',')
        if not 0 <= daily <= 100 or not 60 <= interval <= 86400: raise ValueError()
        return daily,interval,{m.strip() for m in markets if len(m.strip())==2 and m.strip().isalpha() and m.strip().isupper()}
    except ValueError: return 0,86400,set()


def event(db,item,name,detail=''):
    db.add(MessageEvent(user_id=item.user_id,outbox_id=item.id,event=name,detail=detail))
    item.updated_at=int(time.time())


def public(item):
    fields=('id','lead_id','draft_id','account_id','channel','recipient','status','due_at','expires_at',
            'created_at','updated_at','wire_started_at','provider_id','thread_id','error','cancel_requested','reconcile_count')
    return {k:getattr(item,k) for k in fields} | {'snapshot':json.loads(item.snapshot_json),
        'authorization':json.loads(item.authorization_json), 'delivery':'unverified','read':'unverified'}


def verification_for(db,policy,now):
    if not policy: return None
    return db.scalar(select(ContactVerification).where(ContactVerification.user_id==policy.user_id,
        ContactVerification.policy_id==policy.id,ContactVerification.policy_version==policy.version,
        ContactVerification.expires_at>now).order_by(ContactVerification.created_at.desc(),ContactVerification.id).limit(1))


def eligibility(db,lead,draft,account,now):
    if not lead or not draft or not account or lead.user_id!=draft.user_id or account.user_id!=lead.user_id:
        return 'Oportunidade, conta ou rascunho indisponível.'
    reason=content_eligibility(db,lead,draft)
    if reason: return reason
    if draft.channel!='email' or account.channel!=draft.channel or account.provider!='gmail':
        return 'Adapter oficial deste canal ainda indisponível.'
    if not enabled() or limits()[0]==0: return 'Envio desativado ou orçamento não configurado no servidor.'
    from .consumption import PROVIDER_LIMITS
    if PROVIDER_LIMITS.get('gmail',0)<=0: return 'Orçamento Gmail de operações de rede não configurado.'
    if account.status!='connected' or not account.credentials: return 'Reconecte a conta remetente.'
    policy=policy_for(db,lead.user_id,draft.channel,draft.recipient)
    if not policy or policy.blocked or policy.basis not in ('explicit_permission','inbound_request'):
        return 'Exige permissão explícita ou solicitação recebida, documentada e revisada.'
    if not policy.valid_until or policy.valid_until<=now: return 'Condição de contato expirada.'
    if policy.market not in limits()[2] or policy.market!=lead.country:
        return 'Jurisdição não habilitada ou incompatível com a oportunidade.'
    if not verification_for(db,policy,now): return 'Revise as evidências de contato e as regras do canal/jurisdição.'
    if any(c in draft.subject for c in '\r\n') or any(c in account.identity for c in '\r\n'):
        return 'Cabeçalho de mensagem inválido.'
    if not re.search(r'não receber|unsubscribe|no recibir',draft.body,re.I):
        return 'Inclua a orientação de remoção no texto e aprove novamente o conteúdo.'
    return ''


class VerifyContact(StrictModel):
    policy_id: UUID
    policy_version: int = Field(strict=True,ge=1)
    contact_source: str = Field(min_length=15,max_length=1000)
    permission_evidence: str = Field(min_length=15,max_length=1000)
    jurisdiction_reference: str = Field(min_length=15,max_length=1000)
    provider_policy_reference: str = Field(min_length=15,max_length=1000)
    reviewed_permission: Literal[True]
    reviewed_jurisdiction: Literal[True]
    reviewed_channel_rules: Literal[True]
    opt_out_supported: Literal[True]
    validity_days: int = Field(default=7,strict=True,ge=1,le=30)


@router.post('/contact-verifications')
def verify_contact(data:VerifyContact,user:User=Depends(current_user),db:Session=Depends(get_db)):
    limiter.check('contact-review:'+user.id,20,60); lock(db)
    policy=owned(db,RecipientPolicy,str(data.policy_id),user);now=int(time.time())
    if policy.version!=data.policy_version or policy.blocked or policy.basis not in ('explicit_permission','inbound_request'):
        raise HTTPException(409,'Condição alterada, bloqueada ou sem permissão/solicitação explícita.')
    if policy.market not in limits()[2] or not policy.reference.strip() or not policy.valid_until or policy.valid_until<=now:
        raise HTTPException(409,'Jurisdição, referência ou validade indisponível.')
    record=data.model_dump(mode='json')|{'reviewed_by':user.id,'method':'operator_evidence_review','legal_certification':False}
    row=ContactVerification(user_id=user.id,policy_id=policy.id,policy_version=policy.version,
        record_json=compact(record),created_at=now,expires_at=min(policy.valid_until,now+data.validity_days*86400))
    db.add(row);db.commit()
    return {'id':row.id,'expires_at':row.expires_at,'method':'operator_evidence_review'}


class AuthorizeSend(StrictModel):
    request_key: UUID
    draft_id: UUID
    draft_version: int = Field(strict=True,ge=1)
    account_id: UUID
    account_version: int = Field(strict=True,ge=1)
    verification_id: UUID
    due_at: int = Field(default=0,strict=True,ge=0)
    validity_hours: int = Field(default=24,strict=True,ge=1,le=72)
    authorize_external_send: Literal[True]
    legitimate_sender_confirmed: Literal[True]
    opt_out_in_message_confirmed: Literal[True]
    sender_configuration_reference: str = Field(min_length=15,max_length=1000)
    # Operator's SPF/DKIM/DMARC review; never advertised as an automatic DNS diagnosis.
    sender_dns_review: str = Field(min_length=15,max_length=1000)


@router.post('/outbox',status_code=201)
def authorize_send(data:AuthorizeSend,user:User=Depends(current_user),db:Session=Depends(get_db)):
    limiter.check('authorize-send:'+user.id,10,60);lock(db);now=int(time.time())
    fingerprint=digest(data.model_dump(mode='json'))
    previous=db.scalar(select(OutboxMessage).where(OutboxMessage.user_id==user.id,OutboxMessage.request_key==str(data.request_key)))
    if previous:
        if previous.input_hash!=fingerprint: raise HTTPException(409,'Identificador já usado para outra autorização.')
        return public(previous)
    draft=owned(db,OutreachDraft,str(data.draft_id),user)
    account=owned(db,ChannelAccount,str(data.account_id),user)
    lead=owned(db,Lead,draft.lead_id,user)
    if draft.version!=data.draft_version or account.version!=data.account_version: raise HTTPException(409,'Conta ou rascunho alterado; revise novamente.')
    reason=eligibility(db,lead,draft,account,now)
    if reason: raise HTTPException(409,reason)
    policy=policy_for(db,user.id,draft.channel,draft.recipient)
    verification=verification_for(db,policy,now)
    if verification.id!=str(data.verification_id): raise HTTPException(409,'Revisão de contato alterada.')
    prior=db.scalar(select(OutboxMessage).where(OutboxMessage.draft_id==draft.id,
        or_(OutboxMessage.draft_version==draft.version,OutboxMessage.status.in_(['uncertain','executing','accepted']))))
    if prior: raise HTTPException(409,'Este rascunho já possui execução. Consulte o resultado antes de preparar outra mensagem.')
    pending=db.scalar(select(func.count()).select_from(OutboxMessage).where(OutboxMessage.user_id==user.id,OutboxMessage.status.in_(ACTIVE)))
    if pending>=100: raise HTTPException(409,'Limite de 100 mensagens pendentes atingido.')
    expires=min(now+data.validity_hours*3600,draft.authorized_until,verification.expires_at)
    due=data.due_at or now
    if due<now-60 or due>=expires: raise HTTPException(422,'Agendamento fora da validade da autorização.')
    snapshot={'sender':account.identity,'recipient':draft.recipient,'channel':draft.channel,
        'subject':draft.subject,'body':draft.body,'date':formatdate(now,usegmt=True)}
    authorization=data.model_dump(mode='json')|{'operator_id':user.id,'authorized_at':now,'expires_at':expires,
        'approval_hash':draft.approval_hash,'lead_version':lead.version,'policy_id':policy.id,
        'policy_version':policy.version,'verification':json.loads(verification.record_json),'snapshot_hash':digest(snapshot)}
    identifier=uid()
    item=OutboxMessage(id=identifier,user_id=user.id,lead_id=lead.id,draft_id=draft.id,account_id=account.id,
        request_key=str(data.request_key),input_hash=fingerprint,draft_version=draft.version,channel=draft.channel,
        recipient=draft.recipient,snapshot_json=compact(snapshot),authorization_json=compact(authorization),
        status='scheduled' if due>now else 'queued',due_at=due,expires_at=expires,created_at=now,updated_at=now,
        message_id=f'<scoutliq.{identifier}@{account.identity.split("@",1)[1]}>')
    db.add(item);db.flush();event(db,item,'authorized','Envio externo explicitamente autorizado pelo operador.')
    activity(db,lead,'outreach_queued','Mensagem autorizada e registrada na fila. Ainda não aceita pelo provedor.',outbox_id=item.id)
    db.commit();return public(item)


@router.get('/outbox')
def list_outbox(lead_id:str='',offset:int=0,user:User=Depends(current_user),db:Session=Depends(get_db)):
    query=select(OutboxMessage).where(OutboxMessage.user_id==user.id)
    if lead_id:
        owned(db,Lead,lead_id,user);query=query.where(OutboxMessage.lead_id==lead_id)
    return {'messages':[public(x) for x in db.scalars(query.order_by(OutboxMessage.created_at.desc(),OutboxMessage.id).offset(max(0,offset)).limit(30))]}


@router.get('/outbox/{identifier}')
def get_outbox(identifier:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    row=owned(db,OutboxMessage,identifier,user)
    return public(row)|{'events':[{'event':x.event,'detail':x.detail,'created_at':x.created_at} for x in db.scalars(
        select(MessageEvent).where(MessageEvent.user_id==user.id,MessageEvent.outbox_id==row.id).order_by(MessageEvent.created_at,MessageEvent.id))]}


@router.post('/outbox/{identifier}/cancel')
def cancel(identifier:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    lock(db);row=owned(db,OutboxMessage,identifier,user)
    if row.status in WAITING or (row.status=='executing' and not row.wire_started_at):
        row.status='cancelled';row.cancel_requested=1;event(db,row,'cancelled','Cancelada antes da tentativa de envio.')
    elif row.status in ('executing','uncertain'):
        row.cancel_requested=1;event(db,row,'cancellation_requested','Tentativa iniciada; cancelamento não comprova que o provedor deixou de aceitar.')
    db.commit();return public(row)


@router.post('/outbox/{identifier}/reconcile')
def request_reconciliation(identifier:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    limiter.check('reconcile:'+user.id,5,60);lock(db);row=owned(db,OutboxMessage,identifier,user)
    if row.status!='uncertain': raise HTTPException(409,'A reconciliação exige resultado incerto.')
    if row.reconcile_count>=10: raise HTTPException(409,'Limite de reconciliações atingido; verifique a conta no provedor. Nenhum reenvio autorizado.')
    row.reconcile_at=max(row.reconcile_at,int(time.time()))
    db.commit();return public(row)


def cancel_pending(db,user_id,*,recipient=None,lead_id=None,account_id=None,reason):
    q=select(OutboxMessage).where(OutboxMessage.user_id==user_id,OutboxMessage.status.in_(ACTIVE))
    if recipient: q=q.where(OutboxMessage.recipient==recipient)
    if lead_id: q=q.where(OutboxMessage.lead_id==lead_id)
    if account_id: q=q.where(OutboxMessage.account_id==account_id)
    for item in db.scalars(q):
        item.cancel_requested=1
        if not item.wire_started_at: item.status='cancelled'
        event(db,item,'contact_interrupted',reason)


def recover(db,now):
    for row in db.scalars(select(OutboxMessage).where(OutboxMessage.status=='executing',OutboxMessage.lease_until<=now)):
        row.status='uncertain' if row.wire_started_at else ('cancelled' if row.cancel_requested else 'queued')
        row.lease_token='';row.lease_until=0;row.reconcile_at=now+60 if row.wire_started_at else 0
        event(db,row,'recovered','Lease expirado; tentativa iniciada nunca é reenviada automaticamente.')


def next_task(db,now):
    recover(db,now)
    row=db.scalar(select(OutboxMessage).join(User).where(User.is_active.is_(True),OutboxMessage.lease_until<=now,
        or_((OutboxMessage.status.in_(WAITING)) & (OutboxMessage.due_at<=now),
            (OutboxMessage.status=='uncertain') & (OutboxMessage.reconcile_at>0) & (OutboxMessage.reconcile_at<=now) & (OutboxMessage.reconcile_count<10)))
        .order_by(OutboxMessage.created_at).limit(1))
    if row:
        if row.status!='uncertain': row.status='executing'
        return 'outreach',row
    account=db.scalar(select(ChannelAccount).join(User).where(User.is_active.is_(True),ChannelAccount.status=='connected',
        ChannelAccount.sync_enabled==1,ChannelAccount.next_sync_at<=now,ChannelAccount.lease_until<=now)
        .order_by(ChannelAccount.next_sync_at).limit(1))
    return ('mail_sync',account) if account else (None,None)


def dispatch_blocker(db,item,account,now):
    user=db.get(User,item.user_id);lead=db.get(Lead,item.lead_id) if item.lead_id else None
    draft=db.get(OutreachDraft,item.draft_id) if item.draft_id else None
    if not user or not user.is_active: return 'Conta de usuário indisponível.'
    reason=eligibility(db,lead,draft,account,now)
    if reason: return reason
    auth=json.loads(item.authorization_json)
    if item.cancel_requested or item.expires_at<=now: return 'Autorização cancelada ou expirada.'
    if (draft.version!=item.draft_version or draft.approval_hash!=auth['approval_hash']
        or account.version!=auth['account_version'] or account.identity!=json.loads(item.snapshot_json)['sender']):
        return 'Conteúdo, aprovação ou conexão alterada; exige nova autorização.'
    policy=policy_for(db,item.user_id,item.channel,item.recipient)
    verification=db.get(ContactVerification,auth['verification_id'])
    if (not verification or verification.user_id!=item.user_id or verification.expires_at<=now
        or policy.id!=auth['policy_id'] or policy.version!=auth['policy_version']): return 'Revisão de contato alterada ou expirada.'
    return ''


def adapter_for(account):
    from .gmail_adapter import unseal, refresh, seal, GmailAdapter
    if account.provider!='gmail' or account.status!='connected': raise AuthenticationRequired('Conexão indisponível.')
    credentials=unseal(account.credentials,account.user_id+':'+account.id)
    if credentials['expires_at']<=int(time.time())+60:
        credentials=refresh(credentials)
        with SessionLocal() as db:
            lock(db);current=db.get(ChannelAccount,account.id)
            if not current or current.status!='connected' or current.version!=account.version: raise AuthenticationRequired('Conexão alterada.')
            current.credentials=seal(credentials,current.user_id+':'+current.id);db.commit()
    return GmailAdapter(credentials)


def finish_task(db,task,now,status):
    from .autonomy_models import WorkAttempt
    attempt=db.get(WorkAttempt,task['token'])
    if attempt: attempt.status=status;attempt.finished_at=now
    slot=db.get(ResearchExecutor,1)
    if slot.token==task['token']: slot.token='';slot.lease_until=0


def execute_outreach(task,adapter_factory=None):
    factory=adapter_factory or adapter_for
    with SessionLocal() as db:
        lock(db);item=db.get(OutboxMessage,task['id']);now=int(time.time())
        if not item or item.lease_token!=task['token'] or item.lease_until<=now: return False
        account=db.get(ChannelAccount,item.account_id)
        reconcile=item.status=='uncertain'
        if item.status=='cancelled':
            item.lease_until=0;item.lease_token='';finish_task(db,task,now,'committed');db.commit();return False
        if not reconcile:
            reason=dispatch_blocker(db,item,account,now)
            if reason:
                item.status='blocked';item.error=reason;item.lease_until=0;item.lease_token=''
                event(db,item,'blocked',reason);finish_task(db,task,now,'failed');db.commit();return False
        elif not account or account.user_id!=item.user_id or account.status!='connected':
            item.reconcile_at=0;item.lease_until=0;item.lease_token='';item.error='Reconecte a conta para reconciliar.'
            finish_task(db,task,now,'failed');db.commit();return False
        snapshot=json.loads(item.snapshot_json);message_id=item.message_id;account_version=account.version
        db.commit()
    acceptance=None;error='';outcome='failed';wire=False
    try:
        adapter=factory(account)
        # Refresh occurs before the irreversible boundary. Recheck all mutable guards afterwards.
        with SessionLocal() as db:
            lock(db);item=db.get(OutboxMessage,task['id']);slot=db.get(ResearchExecutor,1);now=int(time.time())
            if (not item or item.lease_token!=task['token'] or slot.token!=task['token']
                or slot.lease_until<=now or item.lease_until<=now): return False
            current=db.get(ChannelAccount,item.account_id)
            if not current or current.version!=account_version or current.status!='connected': raise AuthenticationRequired('Conexão alterada.')
            if not reconcile:
                reason=dispatch_blocker(db,item,current,now)
                if reason: raise ProviderRejected(reason)
                daily,interval,_=limits()
                count=db.scalar(select(func.count()).select_from(OutboxMessage).where(OutboxMessage.user_id==item.user_id,
                    OutboxMessage.wire_started_at>=now//86400*86400))
                latest=db.scalar(select(func.max(OutboxMessage.wire_started_at)).where(OutboxMessage.user_id==item.user_id)) or 0
                if count>=daily or latest+interval>now:
                    item.status='scheduled';item.due_at=max((now//86400+1)*86400 if count>=daily else now,latest+interval)
                    item.lease_token='';item.lease_until=0;event(db,item,'deferred','Limite diário/intervalo de envio.')
                    finish_task(db,task,now,'committed');db.commit();return True
                item.wire_started_at=now;wire=True;event(db,item,'attempt_started','Fronteira de envio persistida; interrupção passa a resultado incerto.')
            else:
                item.reconcile_count+=1;event(db,item,'reconciliation_started')
            db.commit()
        acceptance=adapter.reconcile(snapshot,message_id) if reconcile else adapter.send(snapshot,message_id)
        outcome='accepted' if acceptance else 'uncertain'
    except AuthenticationRequired:
        error='Credencial expirada, revogada ou alterada; reconecte a conta.';outcome='failed' if not reconcile else 'uncertain'
        with SessionLocal() as db:
            lock(db);a=db.get(ChannelAccount,account.id)
            if a and a.version==account_version and a.status=='connected':
                a.status='reconnect_required';a.version+=1;a.error=error;cancel_pending(db,a.user_id,account_id=a.id,reason=error);db.commit()
    except ProviderRejected:
        error='Provedor ou validação recusou a operação; nenhuma repetição automática.';outcome='uncertain' if reconcile else 'failed'
    except ConsumptionLimit:
        error='Operação não iniciada: orçamento ou lease de rede indisponível.';outcome='uncertain' if reconcile else 'failed'
    except Exception:
        # Includes process/network/ledger failures. Once wire marker exists, absence of receipt is uncertainty.
        error='Resultado não confirmado. Consulte o histórico e reconcilie antes de preparar outro envio.'
        outcome='uncertain' if wire or reconcile else 'failed'
    now=int(time.time())
    with SessionLocal() as db:
        lock(db);item=db.get(OutboxMessage,task['id'])
        if not item or item.lease_token!=task['token'] or item.lease_until<=now: return False
        item.status=outcome;item.error=error;item.lease_token='';item.lease_until=0
        item.reconcile_at=now+300 if outcome=='uncertain' and item.reconcile_count<3 else 0
        if acceptance:
            item.provider_id=acceptance.message_id;item.thread_id=acceptance.thread_id
            lead=db.get(Lead,item.lead_id) if item.lead_id else None
            if lead and lead.user_id==item.user_id:
                db.add(LeadActivity(user_id=item.user_id,lead_id=lead.id,kind='email',body='Mensagem aceita pela Gmail API. Entrega e leitura não confirmadas.',
                    metadata_json=compact({'event':'outreach_accepted','outbox_id':item.id,'provider_id':item.provider_id,'thread_id':item.thread_id})))
        event(db,item,outcome,error or ('Aceitação técnica; não comprova entrega/leitura.' if acceptance else 'Nenhuma correspondência inequívoca. Não reenviar.'))
        finish_task(db,task,now,'committed' if acceptance else 'failed');db.commit()
    return True


def export_communication(db,user):
    return {'communication':{'outbox':[public(x) for x in db.scalars(select(OutboxMessage).where(OutboxMessage.user_id==user.id))],
        'received':[{'id':r.id,'lead_id':r.lead_id,'classification':r.classification,'association':r.association,'text':r.text,'sent_at':r.sent_at}
                    for r in db.scalars(select(ReceivedMessage).where(ReceivedMessage.user_id==user.id))]}}
