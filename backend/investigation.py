"""Progressive policy over ResearchBatch: no second executor and no outreach."""
import hashlib
import json
import time
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, field_validator
from sqlalchemy import select, update, func
from sqlalchemy.orm import Session
from .db import get_db
from .models import User, Lead, LeadResearch, LeadActivity, ResearchBatch, ResearchBatchItem, ResearchExecutor
from .schemas import StrictModel, ResearchBatchInput
from .security import current_user, limiter
from .scoring import score
from .commercial_fit import assess
from .consumption import ConsumptionLimit

router = APIRouter(prefix='/api/investigation')
ACTIVE = ('pending', 'running', 'paused')

class DailyInvestigationLimit(ConsumptionLimit):
    pass

class Preferences(StrictModel):
    search: bool = False
    absorption: bool = False
    execution_limit: int = Field(default=20, ge=1, le=25, strict=True)
    daily_limit: int = Field(default=40, ge=1, le=100, strict=True)
    operation_limit: int = Field(default=100, ge=1, le=400, strict=True)
    daily_operation_limit: int = Field(default=150, ge=1, le=500, strict=True)
    freshness_days: int = Field(default=30, ge=1, le=90, strict=True)
    allow_deep: bool = True

class Request(StrictModel):
    lead_ids: list[str] = Field(min_length=1, max_length=100)
    request_key: UUID

    @field_validator("lead_ids")
    @classmethod
    def valid_ids(cls, value):
        return ResearchBatchInput.valid_lead_ids(value)

def preferences(user):
    return Preferences.model_validate_json(user.investigation_json or '{}').model_dump()

def lock_user(db, user):
    db.execute(update(User).where(User.id == user.id).values(investigation_json=User.investigation_json))
    db.refresh(user)

@router.get('/preferences')
def get_preferences(user: User = Depends(current_user)):
    return preferences(user)

@router.put('/preferences')
def save_preferences(data: Preferences, user: User = Depends(current_user), db: Session = Depends(get_db)):
    limiter.check('investigation-preferences:'+user.id, 20, 60)
    lock_user(db, user)
    user.investigation_json = data.model_dump_json()
    db.commit()
    return preferences(user)

def enqueue(db, user, ids, source='manual', request_key=None):
    """Caller transaction includes ingress and queue. User lock serializes dedup/replay."""
    lock_user(db, user)
    cfg = preferences(user)
    if source != 'manual' and not cfg.get(source): return []
    ids = list(dict.fromkeys(ids))
    if not ids: return []
    leads = {lead.id: lead for lead in db.scalars(select(Lead).where(Lead.user_id == user.id, Lead.id.in_(ids)))}
    if len(leads) != len(ids): raise HTTPException(404, 'Uma empresa selecionada não está disponível.')
    key = str(request_key or uuid4())
    digest = hashlib.sha256(json.dumps([ids, source], separators=(',', ':')).encode()).hexdigest()
    replay = db.scalars(select(ResearchBatch).where(ResearchBatch.user_id == user.id,
        ResearchBatch.request_key.like(key+':%')).order_by(ResearchBatch.request_key)).all()
    if replay:
        if json.loads(replay[0].config_json).get('request_hash') != digest:
            raise HTTPException(409, 'Identificador de solicitação já usado para outras empresas.')
        return replay
    pending = set(db.scalars(select(ResearchBatchItem.lead_id).join(ResearchBatch).where(
        ResearchBatch.user_id == user.id, ResearchBatch.status.in_(ACTIVE),
        ResearchBatchItem.status.in_(['pending', 'running']))))
    now = int(time.time()); batches = []
    ordinal = db.scalar(select(func.max(ResearchBatch.ordinal)).where(ResearchBatch.user_id == user.id)) or 0
    # Keep a receipt even when all entries are duplicates: no silently discarded request.
    for offset in range(0, len(ids), cfg['execution_limit']):
        chunk = ids[offset:offset+cfg['execution_limit']]
        ordinal += 1
        batch = ResearchBatch(ordinal=ordinal, user_id=user.id, mode='progressive', status='pending',
            requested_count=len(chunk), created_at=now, updated_at=now,
            request_key=key+':'+str(offset).zfill(3),
            config_json=json.dumps({**cfg, 'source': source, 'request_hash': digest}))
        db.add(batch); db.flush(); batches.append(batch)
        for position, identifier in enumerate(chunk):
            duplicate = identifier in pending
            demo = leads[identifier].demo
            reason = 'Já existe investigação pendente para esta empresa.' if duplicate else 'Registro de demonstração.' if demo else ''
            db.add(ResearchBatchItem(batch_id=batch.id, lead_id=identifier, position=position,
                status='skipped' if reason else 'pending', outcome='already_pending' if duplicate else 'demo' if demo else '',
                plan_json=json.dumps({'reason': reason}), finished_at=now if reason else None))
        db.flush()
        from .research_worker import finish_batch
        finish_batch(db, batch.id, now)
    return batches

@router.post('/requests', status_code=201)
def request(data: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    limiter.check('investigation-create:'+user.id, 10, 60)
    batches = enqueue(db, user, data.lead_ids, request_key=data.request_key)
    db.commit()
    from .main import _research_batch_row
    return {'batch': _research_batch_row(db, batches[0]), 'batches': [_research_batch_row(db, b) for b in batches]}

@router.get('/queue')
def queue(user: User = Depends(current_user), db: Session = Depends(get_db)):
    from .main import _research_batch_row
    owned = select(ResearchBatch).where(ResearchBatch.user_id == user.id, ResearchBatch.mode == 'progressive')
    active = db.scalars(owned.where(ResearchBatch.status.in_(ACTIVE))).all()
    recent = db.scalars(owned.where(~ResearchBatch.status.in_(ACTIVE)).order_by(ResearchBatch.ordinal.desc()).limit(50)).all()
    rows = sorted([*active, *recent], key=lambda b: b.ordinal, reverse=True)
    return {'batches': [_research_batch_row(db, b, include_details=False) for b in rows]}

def projection(lead, research=None, item=None, now=None):
    now = int(time.time()) if now is None else now
    canonical = score(lead); fit = canonical['commercial_fit']
    pending = [d['reason'] for d in canonical['commercial_dimensions'].values() if d['value'] is None]
    state = 'pending'; reasons = [r['label'] for r in fit['reasons']]
    if item and item.status == 'error':
        state = 'unavailable'; reasons = [item.error]
    elif fit['status'] == 'incompatible' or canonical['status'] == 'incompatible':
        state = 'low'
    elif not lead.name.strip() or not lead.city.strip() or fit['status'] == 'indeterminate':
        reasons = ['Identidade, cidade ou categoria precisam de revisão.']
    elif canonical['status'] == 'qualified':
        state = 'priority'; reasons = ['Score 3.0 sustenta revisão comercial; abordagem exige decisão humana.']
    elif canonical['status'] == 'evaluated' and canonical['commercial_dimensions']['need']['value'] < 65:
        state = 'low'; reasons = ['Avaliação canônica não demonstra uma necessidade comercial relevante agora.']
    elif fit['status'] == 'compatible' and (lead.phone or lead.whatsapp or lead.instagram or lead.reviews):
        state = 'promising'; reasons = ['Adequação e sinais públicos disponíveis; completar as evidências indicadas.']
    elif fit['status'] == 'compatible':
        reasons = ['Dados insuficientes para priorização comercial.']
    if research and research.status in ('not_found', 'unverified'):
        pending.append('Site oficial não confirmado; isso não comprova ausência de site.')
    plan = json.loads(item.plan_json or '{}') if item else {}
    return {'class': state, 'score': canonical['value'], 'score_status': canonical['status'],
        'coverage': canonical['coverage'], 'confidence': canonical.get('confidence'),
        'reasons': reasons, 'pending': pending, 'decision': plan.get('reason', ''),
        'phase': item.phase if item else None, 'state': item.status if item else 'unrequested'}

def local_plan(lead, research, cfg, now):
    if lead.demo: return 'stop', 'Registro de demonstração; sem consulta externa.'
    fit = assess(lead)
    if fit['status'] == 'incompatible': return 'stop', fit['reasons'][0]['label']
    if not lead.name.strip() or not lead.city.strip() or fit['status'] == 'indeterminate':
        return 'stop', 'Resolva identidade, cidade e categoria antes de consultar provedores.'
    canonical = score(lead)
    if (canonical['status'] == 'evaluated' and canonical['commercial_dimensions']['need']['value'] < 65
            and lead.website_analyzed_at and lead.website_analyzed_at >= now-cfg['freshness_days']*86400):
        return 'stop', 'Avaliação recente não demonstra necessidade relevante; reavalie quando houver novos sinais.'
    if research and (research.status == 'confirmed' or not research.fetch_errors) and research.checked_at and research.checked_at >= now-cfg['freshness_days']*86400:
        return 'cached', 'Pesquisa recente reutilizada; ausência de confirmação não é evidência negativa.'
    return 'web', 'Empresa compatível; verificar presença web e lacunas comerciais.'

def deepen(lead, research, cfg, now):
    if not cfg['allow_deep'] or not research or research.status != 'confirmed' or not research.website_url:
        return False
    if research.audited_at and research.audited_at >= now-cfg['freshness_days']*86400: return False
    canonical = score(lead)
    need = canonical['commercial_dimensions']['need']['value']
    return assess(lead)['status'] == 'compatible' and (need is None or need >= 65) and bool(
        lead.phone or lead.whatsapp or lead.instagram or (lead.reviews or 0) >= 20)

def admit(db, item, batch, now):
    """Called under executor lock. Daily slots are persisted once per investigation and UTC day."""
    if batch.mode != 'progressive': return True
    cfg = json.loads(batch.config_json)
    user = db.get(User, batch.user_id)
    if item.phase != 'local':
        from .autonomy_models import ProviderOperation, WorkAttempt
        operations = db.scalar(select(func.count()).select_from(ProviderOperation).join(WorkAttempt).where(
            WorkAttempt.user_id == batch.user_id, ProviderOperation.started_at >= now//86400*86400))
        if operations >= min(cfg['daily_operation_limit'], preferences(user)['daily_operation_limit']):
            item.retry_at = (now//86400+1)*86400
            item.plan_json = json.dumps({'reason': 'Teto diário de consultas atingido; retomada no próximo dia UTC.'})
            return False
    if item.charged_at and item.charged_at//86400 == now//86400: return True
    limit = min(cfg['daily_limit'], preferences(user)['daily_limit'])
    used = db.scalar(select(func.count()).select_from(ResearchBatchItem).join(ResearchBatch).where(
        ResearchBatch.user_id == batch.user_id, ResearchBatchItem.charged_at >= now//86400*86400,
        ResearchBatchItem.charged_at > 0))
    if used >= limit:
        item.retry_at = (now//86400+1)*86400
        item.plan_json = json.dumps({'reason': 'Teto diário atingido; fila preservada para o próximo dia UTC.'})
        return False
    item.charged_at = now
    return True

def fence_control(db, batch, now):
    """Revoke in-flight results even when pause is immediately followed by resume."""
    for item in db.scalars(select(ResearchBatchItem).where(ResearchBatchItem.batch_id == batch.id,
            ResearchBatchItem.status.in_(['running', 'pending']))):
        if item.lease_token:
            db.execute(update(ResearchExecutor).where(ResearchExecutor.id == 1,
                ResearchExecutor.token == item.lease_token).values(token='', lease_until=0))
            item.attempts = max(0, item.attempts-1)
        item.lease_token, item.lease_until = '', 0
        item.status = 'pending'

def guard_operation(db, attempt, now):
    from .autonomy_models import ProviderOperation, WorkAttempt
    from .consumption import ConsumptionLimit
    if attempt.kind != 'batch': return
    item = db.get(ResearchBatchItem, attempt.item_id)
    batch = db.get(ResearchBatch, item.batch_id) if item else None
    if not batch or batch.mode != 'progressive': return
    user = db.get(User, batch.user_id)
    if batch.status != 'running' or item.lease_token != attempt.token or not user or not user.is_active:
        raise ConsumptionLimit('Investigação interrompida.')
    cfg = json.loads(batch.config_json)
    query = select(func.count()).select_from(ProviderOperation).join(WorkAttempt)
    total = db.scalar(query.where(WorkAttempt.kind == 'batch', WorkAttempt.item_id.in_(
        select(ResearchBatchItem.id).where(ResearchBatchItem.batch_id == batch.id))))
    daily = db.scalar(query.where(WorkAttempt.user_id == batch.user_id, ProviderOperation.started_at >= now//86400*86400))
    if total >= cfg['operation_limit']:
        raise ConsumptionLimit('Orçamento de investigação atingido; resultados parciais preservados.')
    if daily >= min(cfg['daily_operation_limit'], preferences(user)['daily_operation_limit']):
        raise DailyInvestigationLimit('Teto diário de consultas atingido.')

def record(db, user, lead, item, reason, now):
    item.plan_json = json.dumps({'reason': reason, 'criteria': 'progressive-1'})
    db.add(LeadActivity(user_id=user.id, lead_id=lead.id, kind='note', body=reason,
        metadata_json=json.dumps({'event': 'progressive_investigation', 'batch_id': item.batch_id,
            'phase': item.phase, 'classification': projection(lead, item=item)['class'],
            'score_version': score(lead)['version']}), created_at=now))

def execute(task, researcher):
    from .db import SessionLocal
    from . import main
    from .autonomy_models import WorkAttempt
    from .consumption import ConsumptionLimit
    from .research import SearchConfigurationError
    from .research_worker import finish_batch, MAX_ATTEMPTS
    with SessionLocal() as db:
        item = db.get(ResearchBatchItem, task['id'])
        if not item or item.lease_token != task['token']: return False
        batch = db.get(ResearchBatch, item.batch_id)
        user, lead = db.get(User, batch.user_id), db.get(Lead, item.lead_id)
        if not user or not user.is_active or not lead or lead.user_id != user.id: return False
        research = db.scalar(select(LeadResearch).where(LeadResearch.lead_id == lead.id, LeadResearch.user_id == user.id))
        version, checked = lead.version, research.checked_at if research else None
        phase, cfg = item.phase, json.loads(batch.config_json)
    result = audit = None; reason = error = ''; terminal = False; next_phase = None; daily_limit = False
    try:
        now = int(time.time())
        if phase == 'local':
            action, reason = local_plan(lead, research, cfg, now)
            next_phase = 'web' if action == 'web' else 'deep' if action == 'cached' and deepen(lead, research, cfg, now) else None
        elif phase == 'web':
            result = researcher.research(lead, user.locale)
            reason = 'Pesquisa salva no LeadResearch; qualificação depende das evidências comerciais.'
        elif phase == 'deep':
            if deepen(lead, research, cfg, now):
                audit = researcher.deep_audit(lead, research.website_url)
                reason = 'Auditoria salva; revise os motivos e as pendências comerciais.'
            else:
                reason = 'Aprofundamento não se justifica com os dados atuais.'
        else: raise ValueError('Invalid phase')
    except Exception as exc:
        daily_limit = isinstance(exc, DailyInvestigationLimit)
        terminal = isinstance(exc, (ConsumptionLimit, SearchConfigurationError, ValueError)) and not daily_limit
        error = 'Limite ou configuração indisponível; resultados anteriores preservados.' if terminal else 'Consulta indisponível; nova tentativa com espera limitada.'
        if daily_limit: error = 'Teto diário de consultas atingido; retomada no próximo dia UTC, com tentativas limitadas.'
    now = int(time.time())
    with SessionLocal() as db:
        fence = db.execute(update(ResearchExecutor).where(ResearchExecutor.id == 1,
            ResearchExecutor.token == task['token'], ResearchExecutor.lease_until > now).values(token='', lease_until=0))
        if fence.rowcount != 1: db.rollback(); return False
        item = db.get(ResearchBatchItem, task['id'])
        if not item:
            db.commit(); return False
        batch = db.get(ResearchBatch, item.batch_id)
        if item.lease_token != task['token'] or batch.status not in ('running', 'pending'): db.rollback(); return False
        lead, user = db.get(Lead, item.lead_id), db.get(User, batch.user_id)
        if not user or not user.is_active or not lead or lead.user_id != user.id:
            item.status, item.finished_at, item.lease_token, item.lease_until = 'cancelled', now, '', 0
            finish_batch(db, batch.id, now)
            db.commit(); return False
        research = db.scalar(select(LeadResearch).where(LeadResearch.lead_id == lead.id, LeadResearch.user_id == user.id))
        item.lease_token, item.lease_until = '', 0
        if lead.version != version or (research.checked_at if research else None) != checked:
            error = 'Dados alterados durante a consulta; resultado obsoleto descartado. Reavalie a empresa.'
            terminal = True
        if error:
            item.status = 'error' if terminal or item.attempts >= MAX_ATTEMPTS else 'pending'
            item.error, item.outcome = error, 'partial' if research else 'unavailable'
            item.retry_at = (now//86400+1)*86400 if daily_limit else now+30*2**(item.attempts-1)
            if item.status == 'error': item.finished_at = now
            record(db, user, lead, item, error, now)
        else:
            if result:
                research = main._persist_research_result(db, user, lead, result)
                next_phase = 'deep' if deepen(lead, research, cfg, now) else None
                if result.get('status') != 'confirmed' and result.get('fetch_errors', 0):
                    error = 'Falhas de acesso impediram confirmar o site; dados parciais preservados.'
                if next_phase:
                    reason += ' Aprofundar: site confirmado, necessidade aberta e canal público ou atividade disponível.'
                if not next_phase and result.get('status') != 'confirmed':
                    reason = 'Site não confirmado. Lead preservado para revisão; auditoria técnica não aplicável.'
            if audit:
                before = main._commercial_snapshot(lead)
                research.audit_level, research.audit_json, research.audited_at = 'deep', json.dumps(audit), now
                research.website_status = str(audit.get('website_status', 'unknown'))[:20]
                lead.website_status = research.website_status
                main._set_website_intelligence(lead, main._intelligence_from_audit(audit), now)
                from .website_context import persist
                persist(db, lead, research, audit.get('context'), now)
                main._sync_commercial_signals(lead, previous_snapshot=before, track_changes=True)
            item.status, item.outcome, item.error = ('pending' if next_phase else 'done'), ('continue' if next_phase else 'review'), ''
            record(db, user, lead, item, reason, now)
            if next_phase:
                item.phase, item.attempts, item.retry_at = next_phase, 0, 0
            else: item.finished_at = now
            if error:
                item.status, item.error, item.outcome, item.finished_at = 'error', error, 'partial', now
        finish_batch(db, batch.id, now)
        attempt = db.get(WorkAttempt, task['token'])
        attempt.status, attempt.finished_at = ('failed' if error else 'committed'), now
        db.commit()
    return True
