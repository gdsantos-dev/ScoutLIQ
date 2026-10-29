"""Canonical evidence, drafting and content review. Send authorization lives in the shared outbox."""
import hashlib
import json
import re
import time
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, field_validator
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from .db import get_db
from .models import Lead, LeadResearch, LeadActivity, User, uid, ResearchBatch, ResearchBatchItem
from .opportunity_models import OpportunityEvidence, OutreachDraft, RecipientPolicy
from .schemas import StrictModel
from .security import current_user, normalize_email
from .scoring import score

router = APIRouter(prefix='/api/leads/{lead_id}')
from .evidence_intelligence import reconcile, interpretation, decide, TTL
from .outreach_intelligence import recipient_identity, recipient_blocker, policy_for, send_condition, compose
DAY = 86400


class VersionInput(StrictModel):
    version: int = Field(ge=1)


class EvidenceInput(StrictModel):
    statement: str = Field(min_length=5, max_length=600)
    source_url: str = Field(min_length=10, max_length=1000)
    validity_days: int = Field(default=14, ge=1, le=30)
    category: Literal['general', 'content', 'security', 'mobile', 'discovery', 'contact', 'performance'] = 'general'
    scope: str = Field(default='Observação manual na fonte indicada.', min_length=5, max_length=500)

    @field_validator('source_url')
    @classmethod
    def safe_url(cls, value):
        p = urlsplit(value)
        if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password or any(ord(c) < 32 for c in value):
            raise ValueError('Informe uma fonte HTTP(S) sem credenciais.')
        return value


class ReviewInput(VersionInput):
    classification: Literal['confirmed', 'probable', 'unverified', 'refuted']
    reason: str = Field(min_length=15, max_length=500)
    translations: dict[Literal['en-US', 'es'], str] = Field(default_factory=dict, max_length=2)

    @field_validator('translations')
    @classmethod
    def validate_translations(cls, value):
        if any(not 5 <= len(v.strip()) <= 600 for v in value.values()):
            raise ValueError('Traduções devem ter entre 5 e 600 caracteres.')
        return value


class DraftInput(StrictModel):
    request_id: UUID
    channel: Literal['email', 'whatsapp']
    locale: Literal['pt-BR', 'en-US', 'es'] = 'pt-BR'
    recipient: str = Field(min_length=8, max_length=254)
    evidence_ids: list[UUID] = Field(default_factory=list, max_length=8)
    strategy: Literal['initial', 'verified_opportunity', 'follow_up', 'reply'] = 'verified_opportunity'


class DraftEdit(VersionInput):
    subject: str = Field(default='', max_length=200)
    body: str = Field(min_length=10, max_length=6000)


class ApprovalInput(VersionInput):
    authorization_ref: str = Field(default='', max_length=500)  # Legacy review note, never consent proof.
    validity_days: int = Field(default=7, ge=1, le=30)


class ContactPolicyInput(VersionInput):
    blocked: bool
    reason: str = Field(min_length=5, max_length=500)


def owned(db, model, identifier, user):
    item = db.scalar(select(model).where(model.id == identifier, model.user_id == user.id))
    if item is None:
        raise HTTPException(404, 'Registro não encontrado.')
    return item


def lead_owned(db, lead_id, user, mutable=False):
    lead = owned(db, Lead, lead_id, user)
    if mutable and (lead.demo or lead.stage in ('won', 'lost')):
        raise HTTPException(409, 'Esta ação exige uma oportunidade real e ativa.')
    return lead


def child_owned(db, model, identifier, lead, user):
    item = owned(db, model, identifier, user)
    if item.lead_id != lead.id:
        raise HTTPException(404, 'Registro não encontrado.')
    return item


def check_version(item, version):
    if item.version != version:
        raise HTTPException(409, 'Registro alterado. Atualize a ficha antes de continuar.')


def activity(db, lead, event, body, **metadata):
    db.add(LeadActivity(user_id=lead.user_id, lead_id=lead.id, kind='note', body=body,
                        metadata_json=json.dumps({'event': event, **metadata}, ensure_ascii=False)))


def evidence_row(item, research=None):
    stale = item.valid_until <= int(time.time())
    fields = ('id', 'statement', 'source_url', 'method', 'classification', 'observed_at', 'valid_until', 'version',
        'category', 'scope', 'research_id', 'verified_at', 'review_reason', 'observation_key', 'observation_state',
        'analyzer_version', 'relation', 'related_id')
    return {k: getattr(item, k) for k in fields} | {'stale': stale, 'translations': json.loads(item.translations_json or '{}')}



def research_for(db, lead):
    return db.scalar(select(LeadResearch).where(LeadResearch.lead_id == lead.id, LeadResearch.user_id == lead.user_id))


def usable_evidence(db, lead, ids):
    if len(set(ids)) != len(ids):
        raise HTTPException(422, 'Selecione evidências distintas.')
    items = db.scalars(select(OpportunityEvidence).where(OpportunityEvidence.lead_id == lead.id,
        OpportunityEvidence.user_id == lead.user_id, OpportunityEvidence.id.in_(ids))).all()
    research = research_for(db, lead)
    if len(items) != len(ids) or any(e.classification != 'confirmed' or e.relation != 'current' or evidence_row(e, research)['stale'] for e in items):
        raise HTTPException(409, 'Revise evidências confirmadas e válidas antes de continuar.')
    return sorted(items, key=lambda e: e.id)


def approval_context(db, lead, draft):
    items = usable_evidence(db, lead, json.loads(draft.evidence_json))
    payload = [draft.channel, draft.locale, draft.recipient, draft.subject, draft.body,
               [(e.id, e.version) for e in items], lead.version, draft.authorization_ref, draft.authorized_until,
               policy_for(db, lead.user_id, draft.channel, draft.recipient).version if policy_for(db, lead.user_id, draft.channel, draft.recipient) else 0]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False).encode()).hexdigest()


def content_eligibility(db, lead, draft):
    if lead.contact_blocked:
        return 'Contato suspenso em todos os canais desta oportunidade.'
    if recipient_blocker(db, lead, draft.channel, draft.recipient):
        return recipient_blocker(db, lead, draft.channel, draft.recipient)
    if lead.demo or lead.stage in ('won', 'lost'):
        return 'Oportunidade indisponível para contato.'
    if draft.status != 'approved':
        return 'A mensagem precisa de aprovação.'
    if not draft.authorized_until or draft.authorized_until <= int(time.time()):
        return 'A aprovação do conteúdo expirou.'
    try:
        if draft.approval_hash != approval_context(db, lead, draft):
            return 'O conteúdo, a oportunidade ou as evidências mudaram. Revise e aprove novamente.'
    except HTTPException as exc:
        return exc.detail
    return ''


def draft_row(db, lead, item):
    result = {k: getattr(item, k) for k in ('id', 'channel', 'locale', 'recipient', 'subject', 'body', 'status',
        'authorization_ref', 'authorized_until', 'approved_at', 'created_at', 'updated_at', 'version', 'strategy', 'generation_method')}
    result['evidence_ids'] = json.loads(item.evidence_json)
    result['review_blocker'] = result['content_blocker'] = content_eligibility(db, lead, item)
    result['eligibility_state'], result['send_blocker'] = send_condition(db, lead, item)
    result['provider_status'] = 'requires_account_and_send_authorization' if item.channel=='email' else 'not_implemented'
    result['dispatch_available'] = False
    return result


def pause_drafts(db, lead, reason):
    from .communication import cancel_pending
    cancel_pending(db,lead.user_id,lead_id=lead.id,reason=reason)
    items = db.scalars(select(OutreachDraft).where(OutreachDraft.user_id == lead.user_id,
        OutreachDraft.lead_id == lead.id, OutreachDraft.status.in_(['draft', 'approved']))).all()
    for item in items:
        item.status = 'paused'
        item.approval_hash = ''
        item.updated_at = int(time.time())
    if items:
        activity(db, lead, 'outreach_paused', reason, draft_ids=[i.id for i in items])


def export_workflow(db, user):
    evidence = db.scalars(select(OpportunityEvidence).where(OpportunityEvidence.user_id == user.id)).all()
    drafts = db.scalars(select(OutreachDraft).where(OutreachDraft.user_id == user.id)).all()
    def public_record(item):
        return {column.name: getattr(item, column.name) for column in item.__table__.columns
                if column.name not in ('user_id', 'approval_hash')}
    return {'opportunity_workflow_version': 2, 'recipient_policies': [public_record(p) for p in db.scalars(select(RecipientPolicy).where(RecipientPolicy.user_id == user.id)).all()], 'opportunity_evidence': [public_record(e) for e in evidence],
            'outreach_drafts': [public_record(d) for d in drafts]}


@router.get('/workflow')
def workflow(lead_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    lead = lead_owned(db, lead_id, user)
    research = research_for(db, lead)
    evidence = [evidence_row(e, research) for e in db.scalars(select(OpportunityEvidence).where(
        OpportunityEvidence.user_id == user.id, OpportunityEvidence.lead_id == lead.id).order_by(OpportunityEvidence.observed_at.desc())).all()]
    drafts = [draft_row(db, lead, d) for d in db.scalars(select(OutreachDraft).where(
        OutreachDraft.user_id == user.id, OutreachDraft.lead_id == lead.id).order_by(OutreachDraft.created_at.desc())).all()]
    confirmed = sum(e['classification'] == 'confirmed' and not e['stale'] for e in evidence)
    current_score = score(lead)
    insight = interpretation(lead, evidence, current_score)
    activities = db.scalars(select(LeadActivity).where(LeadActivity.lead_id == lead.id, LeadActivity.user_id == user.id).order_by(LeadActivity.created_at.desc()).limit(30)).all()
    active = db.scalar(select(ResearchBatchItem.id).join(ResearchBatch).where(ResearchBatch.user_id == user.id,
        ResearchBatchItem.lead_id == lead.id, ResearchBatch.status.in_(['pending', 'running']), ResearchBatchItem.status.in_(['pending', 'running'])))
    recommendation = decide(lead, evidence, drafts, insight, research, activities, bool(active))
    next_action = recommendation['id']
    return {'lead_id': lead.id, 'lead_version': lead.version, 'score': score(lead), 'evidence': evidence, 'drafts': drafts,
        'next_action': next_action, 'recommendation': recommendation, 'insight': insight, 'contact_blocked': lead.contact_blocked, 'contact_block_reason': lead.contact_block_reason,
        'coverage': {'confirmed': confirmed, 'total': len(evidence)},
        'limitations': ['A análise HTML não comprova experiência mobile ou acessibilidade completa.',
                         'Envio por e-mail exige conexão Gmail, elegibilidade revisada e autorização específica na fila. WhatsApp permanece sem adapter de envio.']}


@router.post('/evidence', status_code=201)
def add_evidence(lead_id: str, data: EvidenceInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    lead = lead_owned(db, lead_id, user, True)
    if db.scalar(select(func.count()).select_from(OpportunityEvidence).where(OpportunityEvidence.lead_id == lead.id)) >= 200:
        raise HTTPException(409, 'Limite de 200 evidências por oportunidade atingido.')
    now = int(time.time())
    item = OpportunityEvidence(user_id=user.id, lead_id=lead.id, source_key=uid(), statement=data.statement,
        source_url=data.source_url, method='operator_observation', classification='unverified', observed_at=now,
        valid_until=now + DAY * min(data.validity_days, TTL[data.category]), category=data.category, scope=data.scope)
    db.add(item)
    db.flush()
    activity(db, lead, 'evidence_added', 'Evidência registrada para revisão.', evidence_id=item.id,
             statement=item.statement, source_url=item.source_url, method=item.method)
    db.commit()
    return evidence_row(item)


@router.post('/evidence/capture')
def capture_research(lead_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    lead = lead_owned(db, lead_id, user, True)
    research = research_for(db, lead)
    if not research or research.status != 'confirmed' or not research.website_url:
        raise HTTPException(409, 'Execute a pesquisa e confirme a identidade do site primeiro.')
    EvidenceInput.safe_url(research.website_url)
    added = reconcile(db, lead, research)
    db.commit()
    return {'added': added}


@router.patch('/evidence/{evidence_id}')
def review_evidence(lead_id: str, evidence_id: str, data: ReviewInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    lead = lead_owned(db, lead_id, user, True)
    item = child_owned(db, OpportunityEvidence, evidence_id, lead, user)
    check_version(item, data.version)
    before = item.classification
    item.classification = data.classification
    item.review_reason = data.reason
    item.verified_at = int(time.time())
    item.translations_json = json.dumps(data.translations, ensure_ascii=False)
    # Even a review retaining the classification changes the approval snapshot.
    item.version += 1
    activity(db, lead, 'evidence_reviewed', data.reason, evidence_id=item.id, previous=before,
             classification=item.classification, revision=item.version)
    db.commit()
    return evidence_row(item, research_for(db, lead))


def create_draft(db, lead, data):
    """Canonical preparation, caller owns the transaction; never approves or sends."""
    if lead.demo or lead.stage in ('won', 'lost'):
        raise HTTPException(409, 'Esta ação exige uma oportunidade real e ativa.')
    if lead.contact_blocked:
        raise HTTPException(409, 'Contato suspenso nesta oportunidade.')
    recipient = recipient_identity(data.channel, data.recipient)
    blocked = recipient_blocker(db, lead, data.channel, recipient)
    if blocked: raise HTTPException(409, blocked)
    if data.strategy == 'verified_opportunity' and not data.evidence_ids:
        raise HTTPException(409, 'Selecione evidências revisadas para esta estratégia.')
    ids = sorted(str(i) for i in data.evidence_ids)
    previous = db.scalar(select(OutreachDraft).where(OutreachDraft.user_id == lead.user_id, OutreachDraft.request_id == str(data.request_id)))
    if previous:
        if (previous.lead_id, previous.channel, previous.locale, previous.recipient, json.loads(previous.evidence_json), previous.strategy) != (lead.id, data.channel, data.locale, recipient, ids, data.strategy):
            raise HTTPException(409, 'Identificador de preparação já utilizado para outro conteúdo.')
        return previous
    items = usable_evidence(db, lead, ids)
    if db.scalar(select(func.count()).select_from(OutreachDraft).where(OutreachDraft.lead_id == lead.id)) >= 50:
        raise HTTPException(409, 'Limite de 50 rascunhos por oportunidade atingido.')
    activities = db.scalars(select(LeadActivity).where(LeadActivity.lead_id == lead.id, LeadActivity.user_id == lead.user_id)).all()
    subject, body = compose(lead, data, items, activities)
    item = OutreachDraft(user_id=lead.user_id, lead_id=lead.id, request_id=str(data.request_id), channel=data.channel,
        locale=data.locale, recipient=recipient, subject=subject[:200] if data.channel == 'email' else '',
        body=body, evidence_json=json.dumps(ids), status='draft', strategy=data.strategy)
    db.add(item)
    db.flush()
    activity(db, lead, 'outreach_prepared', 'Abordagem preparada para revisão.', draft_id=item.id, evidence_ids=ids)
    return item


@router.post('/outreach/drafts', status_code=201)
def prepare_draft(lead_id: str, data: DraftInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    lead = lead_owned(db, lead_id, user, True)
    item = create_draft(db, lead, data)
    db.commit()
    return draft_row(db, lead, item)

@router.put('/outreach/drafts/{draft_id}')
def edit_draft(lead_id: str, draft_id: str, data: DraftEdit, user: User = Depends(current_user), db: Session = Depends(get_db)):
    lead = lead_owned(db, lead_id, user, True)
    item = child_owned(db, OutreachDraft, draft_id, lead, user)
    check_version(item, data.version)
    item.subject, item.body = data.subject, data.body
    item.status, item.approval_hash, item.approved_at = 'draft', '', None
    item.authorization_ref, item.authorized_until = '', None
    item.updated_at = int(time.time())
    activity(db, lead, 'outreach_edited', 'Rascunho alterado; exige nova aprovação.', draft_id=item.id)
    db.commit()
    return draft_row(db, lead, item)


@router.post('/outreach/drafts/{draft_id}/approve')
def approve_draft(lead_id: str, draft_id: str, data: ApprovalInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    lead = lead_owned(db, lead_id, user, True)
    item = child_owned(db, OutreachDraft, draft_id, lead, user)
    check_version(item, data.version)
    if lead.contact_blocked:
        raise HTTPException(409, 'Contato suspenso nesta oportunidade.')
    blocked = recipient_blocker(db, lead, item.channel, item.recipient)
    if blocked: raise HTTPException(409, blocked)
    item.authorization_ref = data.authorization_ref
    item.authorized_until = int(time.time()) + data.validity_days * DAY
    item.approval_hash = approval_context(db, lead, item)
    item.status, item.approved_at = 'approved', int(time.time())
    item.updated_at = item.approved_at
    activity(db, lead, 'outreach_approved', 'Conteúdo aprovado. Nenhum envio realizado.', draft_id=item.id,
             content_hash=item.approval_hash, authorization_ref=item.authorization_ref, authorized_until=item.authorized_until,
             snapshot={'channel': item.channel, 'locale': item.locale, 'recipient': item.recipient,
                       'subject': item.subject, 'body': item.body, 'evidence_ids': json.loads(item.evidence_json)})
    db.commit()
    return draft_row(db, lead, item)


@router.post('/outreach/drafts/{draft_id}/dispatch')
def dispatch_draft(lead_id: str, draft_id: str, data: VersionInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    lead = lead_owned(db, lead_id, user, True)
    item = child_owned(db, OutreachDraft, draft_id, lead, user)
    check_version(item, data.version)
    blocker = content_eligibility(db, lead, item)
    if blocker:
        raise HTTPException(409, blocker)
    # Preserve this legacy endpoint's fail-closed contract: content approval alone cannot enqueue.
    raise HTTPException(503, 'Autorize o envio na fila de comunicação, selecionando conta e revisão de contato. Nenhuma mensagem foi enviada por esta ação.')


@router.patch('/contact-policy')
def contact_policy(lead_id: str, data: ContactPolicyInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    lead = lead_owned(db, lead_id, user)
    check_version(lead, data.version)
    lead.contact_blocked, lead.contact_block_reason = data.blocked, data.reason
    if data.blocked:
        pause_drafts(db, lead, 'Rascunhos pausados por recusa de contato.')
    activity(db, lead, 'contact_policy_changed', data.reason, blocked=data.blocked)
    db.commit()
    return {'contact_blocked': lead.contact_blocked, 'lead_version': lead.version}


class RecipientPolicyInput(StrictModel):
    channel: Literal['email', 'whatsapp']
    recipient: str = Field(min_length=8, max_length=254)
    version: int = Field(default=0, ge=0)
    blocked: bool = False
    basis: Literal['unknown', 'inbound_request', 'explicit_permission', 'existing_relationship'] = 'unknown'
    reference: str = Field(default='', max_length=1000)
    reason: str = Field(min_length=15, max_length=500)
    market: str = Field(pattern=r'^[A-Z]{2}$')
    validity_days: int = Field(default=30, ge=1, le=90)

@router.get('/recipient-policy')
def get_recipient_policy(lead_id: str, channel: Literal['email', 'whatsapp'], recipient: str,
                         user: User = Depends(current_user), db: Session = Depends(get_db)):
    lead_owned(db, lead_id, user)
    p = policy_for(db, user.id, channel, recipient)
    return {'policy': {c.name: getattr(p, c.name) for c in p.__table__.columns if c.name != 'user_id'} if p else None}

@router.put('/recipient-policy')
def update_recipient_policy(lead_id: str, data: RecipientPolicyInput,
                            user: User = Depends(current_user), db: Session = Depends(get_db)):
    lead = lead_owned(db, lead_id, user)
    recipient = recipient_identity(data.channel, data.recipient)
    item = policy_for(db, user.id, data.channel, recipient)
    if item: check_version(item, data.version)
    elif data.version: raise HTTPException(409, 'Condição alterada; consulte novamente.')
    else:
        item = RecipientPolicy(user_id=user.id, channel=data.channel, recipient=recipient)
        db.add(item)
    item.blocked, item.basis, item.reference, item.reason = int(data.blocked), data.basis, data.reference, data.reason
    item.market, item.recorded_at = data.market, int(time.time())
    item.valid_until = item.recorded_at + data.validity_days * DAY
    db.flush()
    drafts = db.scalars(select(OutreachDraft).where(OutreachDraft.user_id == user.id,
        OutreachDraft.channel == data.channel, OutreachDraft.recipient == recipient)).all()
    from .communication import cancel_pending
    cancel_pending(db,user.id,recipient=recipient,reason='Política de destinatário alterada; autorização anterior cancelada.')
    for draft in drafts:
        draft.approval_hash = ''
        draft.status = 'paused' if data.blocked else 'draft'
        draft.updated_at = item.recorded_at
    activity(db, lead, 'recipient_policy_changed', data.reason, policy_id=item.id, channel=item.channel,
             recipient=item.recipient, blocked=data.blocked, basis=data.basis, reference=data.reference,
             market=data.market, valid_until=item.valid_until, revision=item.version,
             affected_drafts=[d.id for d in drafts])
    db.commit()
    return {'version': item.version, 'blocked': bool(item.blocked), 'eligibility_state': 'blocked' if item.blocked else 'pending_verification'}
