"""Bounded human operations. Reads canonical facts; never authorizes communication."""
import hashlib
import json
import time
from datetime import date
from typing import Literal
from uuid import UUID, uuid5
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import Field, field_validator, model_validator
from sqlalchemy import select, update, func, or_, case, event
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError
from .db import get_db
from .models import User, Lead, LeadResearch, ResearchBatch, ResearchBatchItem, LeadActivity
from .opportunity_models import OpportunityEvidence, OutreachDraft
from .commercial_review_models import CommercialReview as Review, CommercialOperation as Operation
from .schemas import StrictModel
from .security import current_user, limiter
from .investigation import projection, enqueue, lock_user
from .scoring import score
from .opportunity_workflow import DraftInput, create_draft, usable_evidence, activity, lead_owned
from .outreach_intelligence import recipient_identity, recipient_blocker, compose

router = APIRouter(prefix='/api/commercial-review')
Action = Literal['reviewed', 'selected', 'deferred', 'not_priority', 'reopen', 'investigate', 'prepare',
    'followup_set', 'followup_snooze', 'followup_complete', 'followup_review', 'followup_prepare', 'followup_disable', 'followup_enable']
Classification = Literal['priority', 'promising', 'pending', 'low', 'unavailable']
State = Literal['main', 'all', 'unreviewed', 'reviewed', 'selected', 'deferred', 'not_priority']


def compact(value): return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
def digest(value): return hashlib.sha256(compact(value).encode()).hexdigest()


def invalidate(mapper, connection, target):
    identifier = target.id if isinstance(target, Lead) else target.lead_id
    connection.execute(update(Review.__table__).where(Review.lead_id == identifier).values(dirty=1, followup_dirty=1, followup_generation=Review.followup_generation+1, generation=Review.generation+1))


for model in (Lead, LeadResearch, OpportunityEvidence, ResearchBatchItem):
    for signal in ('after_insert', 'after_update', 'after_delete'):
        event.listen(model, signal, invalidate)


def contexts(db, user_id, ids):
    """Fixed query count, no evidence text or draft bodies in the index scan."""
    now = int(time.time())
    leads = db.scalars(select(Lead).where(Lead.user_id == user_id, Lead.id.in_(ids))).all()
    research = {r.lead_id: r for r in db.scalars(select(LeadResearch).where(LeadResearch.user_id == user_id, LeadResearch.lead_id.in_(ids)))}
    latest = select(ResearchBatchItem.id.label('id'), func.row_number().over(partition_by=ResearchBatchItem.lead_id,
        order_by=(ResearchBatch.created_at.desc(), ResearchBatch.ordinal.desc(), ResearchBatchItem.id.desc())).label('n')).join(ResearchBatch).where(
            ResearchBatch.user_id == user_id, ResearchBatchItem.lead_id.in_(ids), ResearchBatchItem.outcome != 'already_pending').subquery()
    items = {i.lead_id: i for i in db.scalars(select(ResearchBatchItem).join(latest, latest.c.id == ResearchBatchItem.id).where(latest.c.n == 1))}
    valid = (OpportunityEvidence.classification == 'confirmed') & (OpportunityEvidence.relation == 'current') & (OpportunityEvidence.valid_until > now)
    totals = {r[0]: tuple(r[1:]) for r in db.execute(select(OpportunityEvidence.lead_id, func.count(), func.sum(OpportunityEvidence.version),
        func.sum(case((valid, 1), else_=0)), func.min(case((OpportunityEvidence.valid_until > now, OpportunityEvidence.valid_until), else_=None)))
        .where(OpportunityEvidence.user_id == user_id, OpportunityEvidence.lead_id.in_(ids)).group_by(OpportunityEvidence.lead_id))}
    generations = dict(db.execute(select(Review.lead_id, Review.generation).where(Review.user_id == user_id, Review.lead_id.in_(ids))).all())
    result = {}
    for lead in leads:
        r, item = research.get(lead.id), items.get(lead.id)
        q = projection(lead, r, item)
        total = totals.get(lead.id, (0, 0, 0, None))
        fingerprint = digest([lead.version, generations.get(lead.id, 0), total[:3], [r.checked_at, r.audited_at, r.status] if r else None,
            [item.id, item.status, item.phase] if item else None])
        result[lead.id] = {'lead': lead, 'research': r, 'qualification': q, 'hash': fingerprint,
            'generation': generations.get(lead.id, 0), 'confirmed': total[2] or 0, 'evidence_count': total[0], 'refresh_at': min(now + 300, total[3] or now + 300)}
    return result


def index_contexts(db, user_id, ids):
    data = contexts(db, user_id, ids)
    existing = {r.lead_id: r for r in db.scalars(select(Review).where(Review.user_id == user_id, Review.lead_id.in_(ids)))}
    for identifier, ctx in data.items():
        values = dict(context_hash=ctx['hash'], score_cache=ctx['qualification']['score'],
            classification=ctx['qualification']['class'], dirty=0, refresh_at=ctx['refresh_at'])
        review = existing.get(identifier)
        if review:
            db.execute(update(Review).where(Review.lead_id == identifier, Review.user_id == user_id, Review.generation == ctx['generation']).values(**values), execution_options={'synchronize_session': False})
            db.expire(review)
        else:
            review = Review(lead_id=identifier, user_id=user_id, **values); db.add(review)
        ctx['review'] = review
    db.flush()
    return data


def shortlist_evidence(db, user_id, ids):
    now = int(time.time())
    eligible = (OpportunityEvidence.classification == 'confirmed') & (OpportunityEvidence.relation == 'current') & (OpportunityEvidence.valid_until > now)
    gap = or_(OpportunityEvidence.category == 'content', OpportunityEvidence.observation_state.in_(['fail', 'warn']))
    ranked = select(OpportunityEvidence.id.label('id'), func.row_number().over(partition_by=OpportunityEvidence.lead_id,
        order_by=(case((gap, 0), else_=1), OpportunityEvidence.observed_at.desc(), OpportunityEvidence.id)).label('n')).where(
            OpportunityEvidence.user_id == user_id, OpportunityEvidence.lead_id.in_(ids), eligible).subquery()
    result = {identifier: [] for identifier in ids}
    for e in db.scalars(select(OpportunityEvidence).join(ranked, ranked.c.id == OpportunityEvidence.id).where(ranked.c.n <= 3)):
        result[e.lead_id].append(e)
    return result


def summary(ctx, evidence):
    lead, q = ctx['lead'], ctx['qualification']
    gaps = [e for e in evidence if e.category == 'content' or e.observation_state in ('fail', 'warn')]
    services = []
    if score(lead)['commercial_fit']['status'] == 'compatible':
        for e in gaps:
            service = 'Desenvolvimento Web' if e.category in ('content', 'discovery') else 'Manutenção e suporte'
            wording = e.statement.casefold()
            if e.method == 'operator_observation' and e.verified_at and e.category == 'content':
                if any(term in wording for term in ('processo manual', 'processos manuais', 'automação', 'integração de sistemas', 'sistema de agendamento')):
                    service = 'Sistemas personalizados e automações empresariais'
                elif any(term in wording for term in ('conteúdo social', 'calendário editorial', 'gestão de redes sociais')):
                    service = 'ORLIQ Social'
            if service not in [s['name'] for s in services]:
                services.append({'name': service, 'basis': e.statement, 'evidence_id': e.id, 'type': 'inference'})
    # Systems/Social require explicit, reviewed need; public Instagram alone is insufficient.
    unknown = q['pending'][:3]
    if not gaps: unknown = ['Necessidade específica ainda não sustentada por evidência revisada.'] + unknown
    return {'attention': gaps[0].statement if gaps and services else q['reasons'][0] if q['reasons'] else 'Revisar adequação comercial.',
        'services': services, 'facts': [{'id': e.id, 'statement': e.statement, 'source_url': e.source_url, 'scope': e.scope} for e in evidence],
        'unknown': unknown[:4], 'recommended_action': 'Revisar proposta com base nas evidências.' if services else 'Confirmar necessidade e destinatário antes de propor um serviço.'}


def review_row(review):
    return {k: getattr(review, k) for k in ('state', 'version', 'author_id', 'decided_at', 'reason')} | {
        'needs_review': bool(review.decided_at and review.context_hash != review.review_hash)}


def known_recipient(lead, channel):
    raw = lead.contact if channel == 'email' else lead.whatsapp
    # Never infer an email from a name, or a WhatsApp account from a phone number.
    if not raw: raise HTTPException(409, 'Destinatário ausente para este canal; verificar contato.')
    return recipient_identity(channel, raw)


@router.get('/queue')
def queue(classification: Classification | None = None, state: State = 'main', source: str = Query(default='', max_length=50),
          view: Literal['triage','followup'] = 'triage', attention: Literal['all','today','overdue','awaiting','response','review','execution','pending','blocked','closed','paused','completed'] = 'all',
          search: str = Query(default='', max_length=100), offset: int = Query(default=0, ge=0, le=100000),
          limit: int = Query(default=25, ge=1, le=50), user: User = Depends(current_user), db: Session = Depends(get_db)):
    limiter.check('commercial-queue:'+user.id, 120, 60)
    lock_user(db, user)
    now = int(time.time())
    from . import followup
    stale = select(Lead.id).outerjoin(Review, Review.lead_id == Lead.id).where(Lead.user_id == user.id, Lead.demo == False,
        or_(Review.lead_id.is_(None), Review.dirty == 1, Review.refresh_at <= now,
            *([Review.followup_dirty == 1, Review.followup_refresh_at <= now] if view=='followup' else [])))
    ids = db.scalars(stale.order_by(Lead.id).limit(250)).all()
    if ids:
        if view=='followup': followup.index(db,user,ids)
        else: index_contexts(db, user.id, ids)
    remaining = db.scalar(select(func.count()).select_from(stale.subquery()))
    filters = [Lead.user_id == user.id, Lead.demo == False, Review.user_id == user.id, Review.dirty == 0, Review.refresh_at > now]
    if classification: filters.append(Review.classification == classification)
    if source: filters.append(Lead.source == source)
    if search: filters.append(or_(Lead.name.icontains(search, autoescape=True), Lead.city.icontains(search, autoescape=True), Lead.category.icontains(search, autoescape=True)))
    if view=='followup':
        filters.extend([Review.followup_dirty==0,Review.followup_refresh_at>now])
        if attention=='today': filters.append(Review.followup_rank<=4)
        elif attention!='all': filters.append(Review.followup_category==attention)
    elif state == 'main': filters.append(or_(Review.state == 'unreviewed', Review.context_hash != Review.review_hash))
    elif state != 'all': filters.append(Review.state == state)
    query = select(Lead, Review).join(Review, Review.lead_id == Lead.id).where(*filters)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    ordering = [Review.followup_rank, case((Review.followup_due=='','9999-12-31'),else_=Review.followup_due),
        case((Lead.stage=='negotiating',0),(Lead.stage=='replied',1),else_=2),Review.score_cache.desc(),Review.followup_confidence.desc(),Review.followup_last,Lead.id] if view=='followup' else [Review.score_cache.desc(),Lead.id]
    pairs = db.execute(query.order_by(*ordering).offset(offset).limit(limit)).all()
    selected = [lead.id for lead, _ in pairs]
    data = contexts(db, user.id, selected) if selected else {}
    evidence = shortlist_evidence(db, user.id, selected) if selected else {}
    draft_counts = dict(db.execute(select(OutreachDraft.lead_id, func.count()).where(OutreachDraft.user_id == user.id,
        OutreachDraft.lead_id.in_(selected)).group_by(OutreachDraft.lead_id)).all()) if selected else {}
    rows = []
    for lead, review in pairs:
        ctx = data[lead.id]
        rows.append({'id': lead.id, 'version': lead.version, 'name': lead.name, 'city': lead.city, 'category': lead.category,
            'source': lead.source, 'stage': lead.stage, 'qualification': ctx['qualification'], 'review': review_row(review),
            'summary': summary(ctx, evidence[lead.id]), 'evidence_count': ctx['evidence_count'], 'confirmed_count': ctx['confirmed'],
            'draft_count': draft_counts.get(lead.id, 0), 'followup': json.loads(review.followup_json) if view=='followup' else None,
            'contact': {'email': lead.contact, 'whatsapp': lead.whatsapp, 'phone': lead.phone}})
    db.commit()
    return {'items': rows, 'total': total, 'offset': offset, 'limit': limit, 'index_pending': remaining}


@router.get('/leads/{lead_id}')
def detail(lead_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    from .main import lead_row
    lead = lead_owned(db, lead_id, user)
    review = db.get(Review, lead.id)
    return {'lead': lead_row(lead), 'review': review_row(review) if review else None}


class Selection(StrictModel):
    id: UUID
    version: int = Field(ge=1, strict=True)
    review_version: int = Field(ge=0, strict=True)
    followup_version: int | None = Field(default=None, ge=0, strict=True)


class PreviewInput(StrictModel):
    request_key: UUID
    action: Action
    selection: list[Selection] = Field(min_length=1, max_length=50)
    reason: str = Field(default='', max_length=500)
    channel: Literal['email', 'whatsapp'] = 'email'
    locale: Literal['pt-BR', 'en-US', 'es'] = 'pt-BR'
    strategy: Literal['auto', 'initial', 'verified_opportunity', 'follow_up', 'reply'] = 'auto'
    next_action: str = Field(default='', max_length=180)
    due_on: date | None = None
    overwrite_manual: bool = False

    @model_validator(mode='after')
    def valid(self):
        if len({i.id for i in self.selection}) != len(self.selection): raise ValueError('Selecione empresas distintas.')
        if self.action in ('deferred', 'not_priority') and len(self.reason.strip()) < 5: raise ValueError('Informe o motivo da decisão.')
        return self


class ConfirmInput(StrictModel):
    confirm: Literal[True]


def draft_plan(db, lead, data, operation_id):
    recipient = known_recipient(lead, data.channel)
    if lead.contact_blocked: raise HTTPException(409, 'Contato suspenso nesta oportunidade.')
    blocker = recipient_blocker(db, lead, data.channel, recipient)
    if blocker: raise HTTPException(409, blocker)
    if score(lead)['commercial_fit']['status'] == 'incompatible': raise HTTPException(409, 'Adequação comercial incompatível; revisar antes de preparar abordagem.')
    available = shortlist_evidence(db, lead.user_id, [lead.id])[lead.id]
    gaps = [e for e in available if e.category == 'content' or e.observation_state in ('fail', 'warn')]
    strategy = ('verified_opportunity' if gaps else 'initial') if data.strategy == 'auto' else data.strategy
    ids = [e.id for e in gaps] if strategy != 'initial' else []
    if strategy == 'verified_opportunity' and not ids: raise HTTPException(409, 'Sem evidência revisada para proposta específica; use apresentação inicial.')
    draft = DraftInput(request_id=uuid5(UUID(operation_id), lead.id), channel=data.channel, locale=data.locale,
        recipient=recipient, evidence_ids=ids, strategy=strategy)
    items = usable_evidence(db, lead, ids)
    activities = db.scalars(select(LeadActivity).where(LeadActivity.user_id == lead.user_id, LeadActivity.lead_id == lead.id,
        LeadActivity.kind.in_(['email', 'whatsapp', 'call', 'reply']))).all()
    subject, body = compose(lead, draft, items, activities)
    if db.scalar(select(func.count()).select_from(OutreachDraft).where(OutreachDraft.user_id == lead.user_id, OutreachDraft.lead_id == lead.id)) >= 50:
        raise HTTPException(409, 'Limite de 50 rascunhos por oportunidade atingido.')
    return draft, {'recipient': recipient, 'channel': data.channel, 'locale': data.locale, 'strategy': strategy,
        'subject': subject, 'body': body, 'evidence_ids': ids}


def assess_item(db, user, selection, data, operation_id):
    lead = db.scalar(select(Lead).where(Lead.id == str(selection.id), Lead.user_id == user.id))
    if not lead: raise HTTPException(404, 'Empresa indisponível.')
    if lead.demo or (lead.stage in ('won', 'lost') and data.action!='followup_disable'): raise HTTPException(409, 'Empresa de demonstração ou oportunidade encerrada.')
    if lead.version != selection.version: raise HTTPException(409, 'Empresa alterada; atualize a seleção.')
    ctx = index_contexts(db, user.id, [lead.id])[lead.id]
    review = ctx['review']
    if review.version != selection.review_version: raise HTTPException(409, 'Revisão alterada; atualize a seleção.')
    if data.action == 'reopen' and review.state == 'unreviewed': raise HTTPException(409, 'Empresa já está aberta para revisão.')
    prepared = None
    if data.action.startswith('followup_'):
        from . import followup
        p=followup.assess(db,user,lead,ctx,data,selection);ctx['followup']=p
        ctx['hash']=digest([ctx['hash'],p['stamp']])
        if data.action=='followup_prepare': _,prepared=followup.draft_plan(db,user,lead,ctx,data,p)
    if data.action == 'prepare': _, prepared = draft_plan(db, lead, data, operation_id)
    return lead, ctx, prepared


def operation_row(op):
    preview = json.loads(op.preview_json)
    return {'id': op.id, 'action': op.action, 'status': op.status, 'created_at': op.created_at, 'expires_at': op.created_at+900,
        'preview': preview, 'eligible': sum(r['eligible'] for r in preview), 'total': len(preview),
        'results': json.loads(op.result_json), 'stage_changes': False, 'external_send': False}


@router.post('/operations/preview', status_code=201)
def preview(data: PreviewInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    limiter.check('commercial-preview:'+user.id, 15, 60); lock_user(db, user)
    payload = data.model_dump(mode='json'); signature = digest(payload)
    previous = db.scalar(select(Operation).where(Operation.user_id == user.id, Operation.request_key == str(data.request_key)))
    if previous:
        if previous.request_hash != signature and PreviewInput.model_validate_json(previous.payload_json).model_dump(mode='json') != payload:
            raise HTTPException(409, 'Identificador já usado para outra operação.')
        return operation_row(previous)
    from .models import uid
    op = Operation(id=uid(), user_id=user.id, request_key=str(data.request_key), request_hash=signature,
        action=data.action, payload_json=compact(payload), preview_json='[]')
    db.add(op); db.flush(); rows = []
    for item in data.selection:
        row = {'id': str(item.id), 'eligible': False}
        try:
            with db.begin_nested():
                lead, ctx, prepared = assess_item(db, user, item, data, op.id)
                row.update(name=lead.name, state=ctx['review'].state, eligible=True, context_hash=ctx['hash'], draft=prepared,
                    followup=ctx.get('followup'), next_action_before=lead.next_action, due_before=lead.next_action_on,
                    next_action_after=data.next_action if data.action=='followup_set' else '' if data.action=='followup_complete' else lead.next_action,
                    due_after=data.due_on.isoformat() if data.action in ('followup_set','followup_snooze') and data.due_on else None if data.action=='followup_complete' else lead.next_action_on,
                    effect='Preparar rascunho sem aprovar ou enviar.' if data.action in ('prepare','followup_prepare') else 'Adicionar à fila de investigação.' if data.action == 'investigate' else 'Atualizar acompanhamento conforme ação e data apresentadas; estágio preservado.' if data.action.startswith('followup_') else 'Registrar decisão sem alterar estágio do CRM.')
        except HTTPException as exc: row['reason'] = exc.detail
        rows.append(row)
    op.preview_json = compact(rows); db.commit()
    return operation_row(op)


@router.get('/operations')
def history(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Operation).where(Operation.user_id == user.id).order_by(Operation.created_at.desc(), Operation.id).limit(20)).all()
    return {'operations': [{'id': o.id, 'action': o.action, 'status': o.status, 'created_at': o.created_at} for o in rows]}


@router.get('/operations/{operation_id}')
def operation(operation_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    op = db.scalar(select(Operation).where(Operation.id == operation_id, Operation.user_id == user.id))
    if not op: raise HTTPException(404, 'Operação indisponível.')
    return operation_row(op)


@router.post('/operations/{operation_id}/confirm')
def confirm(operation_id: str, confirmation: ConfirmInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    limiter.check('commercial-confirm:'+user.id, 15, 60)
    # Share the canonical short write fence with message acceptance/reply ingestion.
    # This does not acquire a worker lease or execute any external operation.
    from .communication import lock as communication_lock
    communication_lock(db); lock_user(db, user)
    op = db.scalar(select(Operation).where(Operation.id == operation_id, Operation.user_id == user.id))
    if not op: raise HTTPException(404, 'Operação indisponível.')
    if op.status == 'committed': return operation_row(op)
    if op.created_at+900 < int(time.time()): raise HTTPException(409, 'Prévia expirada; prepare uma nova operação.')
    data = PreviewInput.model_validate_json(op.payload_json); rows = []
    for selected, before in zip(data.selection, json.loads(op.preview_json)):
        result = {'id': str(selected.id), 'name': before.get('name', ''), 'status': 'skipped'}
        if not before['eligible']:
            result['reason'] = before['reason']; rows.append(result); continue
        try:
            with db.begin_nested():
                # Lock the exact owned Lead before checking its current version. Other domains retain optimistic locking.
                db.execute(update(Lead).where(Lead.id == str(selected.id), Lead.user_id == user.id).values(version=Lead.version))
                db.expire_all()
                db.scalars(select(OpportunityEvidence).where(OpportunityEvidence.user_id == user.id,
                    OpportunityEvidence.lead_id == str(selected.id)).with_for_update()).all()
                lead, ctx, prepared = assess_item(db, user, selected, data, op.id)
                if ctx['hash'] != before['context_hash'] or prepared != before.get('draft'):
                    raise HTTPException(409, 'Contexto alterado desde a prévia; revisar novamente.')
                review = ctx['review']
                if data.action in ('prepare','followup_prepare'):
                    if data.action=='followup_prepare':
                        from . import followup
                        draft_input,_=followup.draft_plan(db,user,lead,ctx,data,ctx['followup'])
                    else: draft_input, _ = draft_plan(db, lead, data, op.id)
                    draft = create_draft(db, lead, draft_input)
                    result['draft_id'] = draft.id
                elif data.action.startswith('followup_'):
                    from . import followup
                    followup.apply(db,user,lead,data,ctx['followup'])
                elif data.action == 'investigate':
                    batches = enqueue(db, user, [lead.id], request_key=uuid5(UUID(op.id), lead.id))
                    result['batch_ids'] = [b.id for b in batches]
                else:
                    review.state = 'unreviewed' if data.action == 'reopen' else data.action
                    review.author_id, review.decided_at = user.id, int(time.time())
                    review.reason, review.review_hash = data.reason.strip(), ctx['hash']
                    review.version += 1
                activity(db, lead, 'commercial_triage', data.reason.strip() or 'Operação comercial confirmada pelo operador.',
                    operation_id=op.id, action=data.action, previous_state=before.get('state'),
                    review_state=review.state, context_hash=ctx['hash'], draft_id=result.get('draft_id'),
                    next_action_before=before.get('next_action_before'),due_before=before.get('due_before'),
                    next_action_after=lead.next_action,due_after=lead.next_action_on,overwrite_manual=data.overwrite_manual)
                db.flush(); result['status'] = 'success'
        except (HTTPException, StaleDataError) as exc:
            result['status'] = 'failed'; result['reason'] = exc.detail if isinstance(exc, HTTPException) else 'Registro alterado durante a operação; revisar novamente.'
        rows.append(result)
    op.status, op.committed_at, op.result_json = 'committed', int(time.time()), compact(rows)
    db.commit()
    return operation_row(op)


def export_reviews(db, user):
    reviews = db.scalars(select(Review).where(Review.user_id == user.id)).all()
    operations = db.scalars(select(Operation).where(Operation.user_id == user.id)).all()
    return {'commercial_review_version': 1, 'commercial_reviews': [review_row(r) | {'lead_id': r.lead_id} for r in reviews],
        'commercial_operations': [operation_row(o) for o in operations]}
