"""Deterministic local suggestions. No scheduler, provider calls or send authorization."""
import json
import time
from datetime import datetime, timedelta
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from sqlalchemy import select, update, func, event, or_, tuple_
from .db import get_db
from .schemas import StrictModel
from .security import current_user, limiter
from .models import User, Lead, LeadActivity
from .opportunity_models import OutreachDraft, RecipientPolicy
from .communication_models import OutboxMessage, MessageEvent, ReceivedMessage, ChannelAccount
from .commercial_review_models import CommercialReview as Review
from .followup_models import FollowupPreference as Preference, FollowupSettings as Settings
from .outreach_intelligence import recipient_identity

router = APIRouter(prefix='/api/followup')
NAMESPACE = UUID('7da9d33c-34cc-4e4a-977e-6bbdf79cd431')
ACTIONS = {'followup_set', 'followup_snooze', 'followup_complete', 'followup_review', 'followup_prepare', 'followup_disable', 'followup_enable'}


def decoded(value):
    try:
        result = json.loads(value or '{}')
        return result if isinstance(result, dict) else {}
    except (TypeError, ValueError): return {}


def local_day(user, stamp=None):
    return datetime.fromtimestamp(stamp if stamp is not None else time.time(), ZoneInfo(user.timezone)).date()


def changed(mapper, connection, target):
    statement = update(Review.__table__).where(Review.user_id == (target.id if isinstance(target,User) else target.user_id))
    if hasattr(target, 'lead_id'):
        statement = statement.where(Review.lead_id == target.lead_id)
    elif isinstance(target, MessageEvent):
        statement = statement.where(Review.lead_id.in_(select(OutboxMessage.lead_id).where(OutboxMessage.id == target.outbox_id, OutboxMessage.user_id == target.user_id)))
    connection.execute(statement.values(followup_dirty=1,followup_generation=Review.followup_generation+1))


for model in (LeadActivity, OutreachDraft, OutboxMessage, MessageEvent, ReceivedMessage, RecipientPolicy, ChannelAccount, Preference, Settings):
    for signal in ('after_insert', 'after_update', 'after_delete'): event.listen(model, signal, changed)
event.listen(User, 'after_update', changed)


def settings_row(db, user):
    row = db.get(Settings, user.id)
    return {'interval_days': row.interval_days if row else 7, 'version': row.version if row else 0, 'timezone': user.timezone}


class SettingsInput(StrictModel):
    interval_days: int = Field(ge=1, le=90, strict=True)
    version: int = Field(ge=0, strict=True)


@router.get('/settings')
def settings(user=Depends(current_user), db=Depends(get_db)):
    return settings_row(db, user)


@router.put('/settings')
def save_settings(data: SettingsInput, user=Depends(current_user), db=Depends(get_db)):
    from .investigation import lock_user
    limiter.check('followup-settings:'+user.id, 15, 60); lock_user(db, user)
    current = settings_row(db, user)
    if current['version'] != data.version: raise HTTPException(409, 'Configuração alterada; atualize antes de salvar.')
    row = db.get(Settings, user.id)
    if not row: row = Settings(user_id=user.id); db.add(row)
    row.interval_days = data.interval_days
    db.commit()
    return settings_row(db, user)


def latest(db, model, user_id, ids, time_column, extra=(), partition=None, count=1):
    ranked = select(model.id.label('id'), func.row_number().over(partition_by=partition or model.lead_id,
        order_by=(time_column.desc(), model.id.desc())).label('n')).where(model.user_id == user_id, model.lead_id.in_(ids), *extra).subquery()
    return db.scalars(select(model).join(ranked, ranked.c.id == model.id).where(ranked.c.n <= count)).all()


def facts_many(db, user, contexts):
    ids = list(contexts)
    if not ids: return {}
    preferences = {p.lead_id:p for p in db.scalars(select(Preference).where(Preference.user_id == user.id, Preference.lead_id.in_(ids)))}
    drafts = latest(db, OutreachDraft, user.id, ids, OutreachDraft.created_at)
    boxes = latest(db, OutboxMessage, user.id, ids, OutboxMessage.created_at, partition=(OutboxMessage.lead_id, OutboxMessage.status))
    accounts = {a.id:a for a in db.scalars(select(ChannelAccount).where(ChannelAccount.user_id == user.id, ChannelAccount.id.in_({b.account_id for b in boxes})))}
    events = db.scalars(select(MessageEvent).where(MessageEvent.user_id == user.id,
        MessageEvent.outbox_id.in_([b.id for b in boxes]), MessageEvent.event.in_(['accepted', 'delivered']))).all()
    # Association is established by the canonical synchronizer. Require its matching account/thread/outbox too.
    matched = select(OutboxMessage.id).join(ChannelAccount).where(OutboxMessage.user_id == user.id,
        ChannelAccount.user_id == user.id, OutboxMessage.account_id == ReceivedMessage.account_id,
        OutboxMessage.lead_id == ReceivedMessage.lead_id, OutboxMessage.thread_id == ReceivedMessage.thread_id,
        OutboxMessage.status == 'accepted').exists()
    replies = latest(db, ReceivedMessage, user.id, ids, ReceivedMessage.sent_at,
        extra=(ReceivedMessage.association == 'matched', matched))
    acts = latest(db, LeadActivity, user.id, ids, LeadActivity.created_at,
        extra=(LeadActivity.kind.in_(['email','whatsapp','call','meeting','proposal','reply']),),
        partition=(LeadActivity.lead_id, LeadActivity.kind), count=2)
    identities = set()
    for ctx in contexts.values():
        lead = ctx['lead']
        for channel, raw in [('email', lead.contact), ('whatsapp', lead.whatsapp)]:
            if raw:
                try: identities.add((channel, recipient_identity(channel, raw)))
                except HTTPException: pass
    identities.update((b.channel, b.recipient) for b in boxes)
    identities.update((d.channel, d.recipient) for d in drafts)
    policies = db.scalars(select(RecipientPolicy).where(RecipientPolicy.user_id == user.id,
        tuple_(RecipientPolicy.channel, RecipientPolicy.recipient).in_(identities))).all() if identities else []
    result = {i:{'draft':None,'boxes':[],'events':[],'reply':None,'activities':[], 'accounts':accounts,
                 'preference':preferences.get(i), 'policies':policies} for i in ids}
    for d in drafts: result[d.lead_id]['draft'] = d
    for b in boxes: result[b.lead_id]['boxes'].append(b)
    box_leads = {b.id:b.lead_id for b in boxes}
    for e in events: result[box_leads[e.outbox_id]]['events'].append(e)
    for r in replies: result[r.lead_id]['reply'] = r
    for a in acts: result[a.lead_id]['activities'].append(a)
    return result


def plan(ctx, facts, user, config):
    from .commercial_review import digest
    lead, q = ctx['lead'], ctx['qualification']
    today = local_day(user); pref = facts['preference']; draft = facts['draft']; reply = facts['reply']
    boxes = facts['boxes']; accounts = facts['accounts']
    identities = set(); valid_contact = False
    for channel, raw in [('email', lead.contact), ('whatsapp', lead.whatsapp)]:
        if raw:
            try: identities.add((channel, recipient_identity(channel, raw))); valid_contact = True
            except HTTPException: pass
    identities.update((b.channel,b.recipient) for b in boxes)
    if draft: identities.add((draft.channel,draft.recipient))
    blocked = lead.contact_blocked or any(p.blocked and (p.channel,p.recipient) in identities for p in facts['policies'])
    contacts = []; manual_replies = []
    for a in facts['activities']:
        meta = decoded(a.metadata_json)
        if not meta.get('event') or meta.get('event') == 'manual_activity':
            stamp = meta.get('occurred_at', a.created_at)
            if not isinstance(stamp, int) or stamp > time.time(): continue
            if a.kind in ('email','whatsapp','call') and meta.get('result') not in ('not_reached','delivery_failure'):
                contacts.append({'id':a.id,'at':stamp,'origin':'operator_declared','channel':a.kind})
            if a.kind == 'reply': manual_replies.append((stamp,a,meta))
    accepted = []
    for b in boxes:
        receipts = [e for e in facts['events'] if e.outbox_id == b.id and e.event == 'accepted']
        if b.status == 'accepted' and b.provider_id and b.account_id in accounts and receipts:
            stamp = min(e.created_at for e in receipts)
            accepted.append((stamp,b))
            contacts.append({'id':b.id,'at':stamp,'origin':'provider_accepted','channel':b.channel})
    contact = max(contacts,key=lambda c:(c['at'],c['id'])) if contacts else None
    manual_reply = max(manual_replies,key=lambda item:item[0]) if manual_replies else None
    response = None
    if reply: response = {'id':reply.id,'at':reply.sent_at,'classification':reply.classification,'origin':'provider_reply','text':reply.text[:500]}
    if manual_reply and (not response or manual_reply[0] > response['at']):
        at,a,meta = manual_reply
        response = {'id':a.id,'at':at,'classification':meta.get('result','insufficient'),'origin':'operator_declared','text':a.body[:500]}
    pending = next((b for b in sorted(boxes,key=lambda b:b.created_at,reverse=True) if b.status in ('queued','executing','uncertain')),None)
    latest_box = max(boxes,key=lambda b:b.created_at) if boxes else None
    last_contact_at = contact['at'] if contact else 0
    due = (local_day(user,last_contact_at)+timedelta(days=config['interval_days'])).isoformat() if contact else ''
    source = {'type':'lead','id':lead.id}; category='pending'; rank=8; code='prepare_initial'
    title='Preparar abordagem inicial'; reason='Não há abordagem preparada nem contato anterior confirmado no histórico.'
    confidence='limited'; unknown=[]; blocks=[]; strategy=None
    if accepted:
        stamp,accepted_box=max(accepted,key=lambda x:x[0])
        delivered = any(e.outbox_id==accepted_box.id and e.event=='delivered' for e in facts['events'])
        communication = {'state':'provider_accepted','accepted_at':stamp,'delivery':'confirmed' if delivered else 'unknown'}
        if not delivered: unknown.append('Aceitação pelo provedor não comprova entrega nem leitura.')
    elif latest_box:
        communication={'state':latest_box.status,'accepted_at':None,'delivery':'unknown'}
        unknown.append('Não há confirmação de aceitação desta tentativa pelo provedor.')
    else: communication={'state':'operator_declared' if contact else 'no_record','accepted_at':None,'delivery':'unknown'}
    if response and response['classification'] in ('refusal','opt_out','delivery_failure'): blocked=True
    if lead.stage in ('won','lost'):
        code='closed';category='closed';rank=100;title='Oportunidade encerrada';reason='O estágio atual não permite novas abordagens.';blocks.append(reason)
    elif blocked:
        code='stop_contact';category='blocked';rank=90;title='Interromper contato';reason='Há bloqueio, recusa ou falha de entrega que exige revisão.';blocks.append(reason)
    elif pref and pref.disabled:
        code='disabled';category='paused';rank=95;title='Acompanhamento desativado';reason='Decisão explícita do operador.'
    elif pending:
        code='check_execution';category='execution';rank=5;title='Acompanhar execução';source={'type':'outbox','id':pending.id};confidence='recorded'
        reason='Resultado incerto; reconciliar antes de outra abordagem.' if pending.status=='uncertain' else 'Autorização ou fila de execução não comprova envio, entrega ou leitura.'
        blocks.append('Não preparar outra mensagem enquanto esta execução estiver pendente.')
    elif latest_box and latest_box.status=='accepted' and not accepted:
        code='verify_acceptance';category='execution';rank=5;title='Revisar registro de aceitação'
        reason='Registro incompleto: data ou recibo de aceitação indisponível.';blocks.append(reason)
    elif draft and draft.status in ('draft','approved') and not any(b.draft_id==draft.id and b.status=='accepted' for b in boxes) and (not response or draft.created_at>=response['at']):
        code='review_draft' if draft.status=='draft' else 'review_contact_condition';category='review';rank=4
        title='Revisar conteúdo' if draft.status=='draft' else 'Revisar condição de contato'
        reason='Rascunho preparado ainda exige revisão humana.' if draft.status=='draft' else 'Conteúdo aprovado; nenhum envio foi autorizado por esta aprovação.'
        source={'type':'draft','id':draft.id};confidence='recorded'
    elif response:
        classification=response['classification'];source={'type':response['origin'],'id':response['id']};confidence='needs_human_review'
        category='response';rank=0
        code,title,reason={
            'interest':('review_response','Revisar possível interesse','Classificação conservadora de resposta; confirmar intenção antes de agir.'),
            'information_request':('prepare_reply','Preparar resposta','Há um pedido de informações associado ao histórico; revisar o contexto.'),
            'objection':('review_proposal','Revisar proposta','Há uma possível objeção; a classificação requer revisão humana.'),
            'automatic_reply':('wait_human','Aguardar retorno humano','Resposta automática não demonstra interesse comercial.'),
        }.get(classification,('review_response','Revisar resposta','Intenção insuficiente ou ambígua; não inferir interesse.'))
        if classification=='automatic_reply': category='awaiting';rank=7
        if classification in ('interest','information_request','objection'): strategy='reply'
        unknown.append('Classificação textual não é compreensão infalível da intenção.')
    elif contact:
        source={'type':contact['origin'],'id':contact['id']};confidence='recorded' if contact['origin']=='provider_accepted' else 'operator_declared'
        code='review_followup' if due<=today.isoformat() else 'await_response'
        title='Revisar follow-up' if code=='review_followup' else 'Aguardar retorno conhecido'
        category='today' if code=='review_followup' else 'awaiting';rank=3 if code=='review_followup' else 7
        reason='Intervalo de acompanhamento alcançado; avaliar uma retomada supervisionada.' if code=='review_followup' else 'Intervalo de acompanhamento ainda não alcançado.'
        unknown.append('Ausência de resposta registrada não significa que o destinatário ignorou a mensagem.')
        if code=='review_followup': strategy='follow_up'
    elif not valid_contact:
        code='verify_contact';category='pending';rank=6;title='Verificar contato';reason='Não há destinatário válido conhecido para e-mail ou WhatsApp.';blocks.append('Destinatário pendente.')
    elif q['class'] in ('pending','unavailable'):
        code='investigate';category='pending';rank=8;title='Revisar investigação';reason='A investigação possui pendências; não afirmar necessidades não verificadas.'
    if source['type']=='lead': due=''
    key = digest([code,source,lead.next_action,lead.next_action_on, draft.version if source['type']=='draft' and draft else None])
    if lead.next_action and category not in ('blocked','closed','paused','execution'):
        due = lead.next_action_on or due
        if lead.next_action_on and lead.next_action_on<=today.isoformat():
            category='overdue' if lead.next_action_on<today.isoformat() else 'today';rank=min(rank,1 if category=='overdue' else 2)
        elif lead.next_action_on and category!='response':
            category='awaiting';rank=7;strategy=None;title='Ação agendada'
            reason='Próxima ação com data futura definida pelo operador; nenhuma alteração automática.'
    if pref and category not in ('blocked','closed','paused'):
        if pref.snooze_until and pref.snooze_until>today.isoformat():
            category='paused';rank=94;due=pref.snooze_until;strategy=None
        elif pref.dismissed_key==key:
            category='completed';rank=96;strategy=None
    stamp = digest([ctx['hash'],config, pref.version if pref else 0,
        [(b.id,b.status,b.cancel_requested,b.provider_id) for b in boxes],[(e.id,e.event) for e in facts['events']],
        [draft.id,draft.version,draft.status] if draft else None,response,
        [(a.id,a.metadata_json) for a in facts['activities']],[(p.id,p.version,p.blocked) for p in facts['policies'] if (p.channel,p.recipient) in identities],
        today.isoformat(),key])
    return {'code':code,'title':title,'reason':reason,'category':category,'rank':rank,'due_on':due,
        'source':source,'confidence':confidence,'blocks':blocks,'unknown':unknown,'communication':communication,
        'response':response,'manual_action':lead.next_action,'manual_due_on':lead.next_action_on,
        'strategy':strategy,'contact':contact,'key':key,'key_after_clear':digest([code,source,'',None,draft.version if source['type']=='draft' and draft else None]),'stamp':stamp,'version':pref.version if pref else 0,
        'last_activity_at':max(last_contact_at,response['at'] if response else 0), 'timezone':user.timezone}


def plans(db, user, contexts):
    facts=facts_many(db,user,contexts);config=settings_row(db,user)
    return {identifier:plan(ctx,facts[identifier],user,config) for identifier,ctx in contexts.items()}


def index(db,user,ids):
    from .commercial_review import index_contexts, compact
    contexts=index_contexts(db,user.id,ids)
    generations=dict(db.execute(select(Review.lead_id,Review.followup_generation).where(Review.user_id==user.id,Review.lead_id.in_(ids))).all())
    result=plans(db,user,contexts)
    now=int(time.time()); midnight=datetime.combine(local_day(user)+timedelta(days=1),datetime.min.time(),ZoneInfo(user.timezone)).timestamp()
    for identifier,p in result.items():
        db.execute(update(Review).where(Review.lead_id==identifier,Review.user_id==user.id,Review.followup_generation==generations[identifier]).values(
            followup_json=compact(p),followup_category=p['category'],followup_rank=p['rank'],followup_due=p['due_on'],
            followup_confidence=contexts[identifier]['qualification'].get('confidence',{}).get('value',0),followup_last=p['last_activity_at'],
            followup_dirty=0,followup_refresh_at=min(now+300,int(midnight))),execution_options={'synchronize_session':False})
        db.expire(contexts[identifier]['review'])
    return result


def assess(db,user,lead,ctx,data,selection):
    p=plans(db,user,{lead.id:ctx})[lead.id]
    if selection.followup_version is None or selection.followup_version!=p['version']:
        raise HTTPException(409,'Acompanhamento alterado; atualize a seleção.')
    if data.action in ('followup_set','followup_snooze','followup_complete') and lead.next_action and not data.overwrite_manual:
        raise HTTPException(409,'Ação manual existente: consentimento explícito necessário para substituí-la ou concluí-la.')
    if data.action=='followup_set' and (not lead.in_pipeline or not data.next_action):
        raise HTTPException(409,'Definir próxima ação exige oportunidade ativa no Pipeline e texto da ação.')
    if data.action in ('followup_set','followup_snooze') and (not data.due_on or data.due_on<local_day(user)):
        raise HTTPException(409,'Informe uma data a partir de hoje no fuso do usuário.')
    if data.action=='followup_prepare' and (p['blocks'] or not p['strategy'] or p['category'] in ('closed','paused','completed')):
        raise HTTPException(409,'O contexto ainda não permite preparar follow-up ou resposta; revise a pendência apresentada.')
    return p


def draft_plan(db,user,lead,ctx,data,p):
    from .commercial_review import draft_plan as canonical_plan, known_recipient
    recipient=known_recipient(lead,data.channel)
    anchor=p['response']['id'] if p['strategy']=='reply' else p['contact']['id']
    request=uuid5(NAMESPACE,'|'.join([user.id,lead.id,anchor,p['strategy'],data.channel,recipient,data.locale]))
    if db.scalar(select(OutreachDraft.id).where(OutreachDraft.user_id==user.id,OutreachDraft.request_id==str(request))):
        raise HTTPException(409,'Já existe rascunho para este evento, canal e idioma; revise o conteúdo existente.')
    effective=data.model_copy(update={'strategy':p['strategy']})
    draft, preview=canonical_plan(db,lead,effective,str(request))
    draft.request_id=request
    return draft,preview


def apply(db,user,lead,data,p):
    pref=db.get(Preference,lead.id)
    if not pref: pref=Preference(lead_id=lead.id,user_id=user.id);db.add(pref)
    if data.action=='followup_set':
        lead.next_action=data.next_action;lead.next_action_on=data.due_on.isoformat();pref.dismissed_key=''
    elif data.action=='followup_snooze':
        pref.snooze_until=data.due_on.isoformat()
        if lead.next_action: lead.next_action_on=pref.snooze_until
    elif data.action=='followup_complete':
        pref.dismissed_key=p['key'];pref.snooze_until=''
        if lead.next_action:
            # Keep completion anchored to the suggestion after the explicit manual-action clearing.
            lead.next_action='';lead.next_action_on=None
            pref.dismissed_key=p['key_after_clear']
    elif data.action=='followup_disable': pref.disabled=1
    elif data.action=='followup_enable': pref.disabled=0;pref.snooze_until='';pref.dismissed_key=''
    elif data.action=='followup_review': pref.snooze_until='';pref.dismissed_key=''
    if pref.version: pref.version+=1


def export_followup(db,user):
    return {'followup_settings':settings_row(db,user),'followup_preferences':[
        {key:getattr(row,key) for key in ('lead_id','disabled','snooze_until','dismissed_key','version')}
        for row in db.scalars(select(Preference).where(Preference.user_id==user.id))]}
