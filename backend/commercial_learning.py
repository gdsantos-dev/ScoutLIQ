"""Bounded, transactional human reviews. External records are declarations, not verified facts."""
import hashlib
import json
import re
import time
from datetime import date
from types import SimpleNamespace
from typing import Any, Literal
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import Field, ValidationError, field_validator, model_validator
from sqlalchemy import select, update, delete, func
from sqlalchemy.orm import Session

from .db import get_db
from .schemas import StrictModel
from .models import Lead, User
from .learning_models import LearningCase, LearningImport, LearningRevision, LearningGate, LearningEvaluation
from .opportunity_models import OpportunityEvidence
from .opportunity_workflow import owned, activity
from .security import current_user, limiter
from .scoring import score, SERVICE_LABELS
from .commercial_fit import norm, same_business
from .selection_quality import reviewed_metrics
from .score_criteria import configuration

router = APIRouter(prefix='/api/learning')
MAX_CASES = 2000


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()


class Company(StrictModel):
    name: str = Field(min_length=2, max_length=160)
    country: str = Field(pattern=r'^[A-Z]{2}$')
    city: str = Field(min_length=2, max_length=100)
    region: str = Field(default='', max_length=100)
    sector: str = Field(min_length=2, max_length=80)
    address: str = Field(default='', max_length=250)
    phone: str = Field(default='', max_length=30)

    @model_validator(mode='after')
    def identified(self):
        if not self.address and not 8 <= len(re.sub(r'\D', '', self.phone)) <= 15:
            raise ValueError('Informe endereço ou telefone para distinguir homônimos.')
        return self


class ReviewEvidence(StrictModel):
    statement: str = Field(min_length=5, max_length=600)
    reference: str = Field(min_length=5, max_length=1000)
    evidence_id: UUID | None = None

    @field_validator('reference')
    @classmethod
    def safe_reference(cls, value):
        if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', value):
            p = urlsplit(value)
            if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password:
                raise ValueError('Use uma referência textual ou URL HTTP(S) sem credenciais.')
        if any(ord(c) < 32 for c in value):
            raise ValueError('Referência inválida.')
        return value


class SystemObservation(StrictModel):
    score: int = Field(ge=0, le=100, strict=True)
    decision: Literal['selected', 'rejected', 'abstained']
    criteria_version: str = Field(min_length=1, max_length=80)
    evaluated_on: date
    reason: str = Field(min_length=5, max_length=1000)

    @field_validator('evaluated_on')
    @classmethod
    def past_date(cls, value):
        if value > date.today(): raise ValueError('Data futura não permitida.')
        return value


class CaseInput(StrictModel):
    source: Literal['orliq_manual', 'external_review'] = 'orliq_manual'
    external_id: str = Field(min_length=1, max_length=100, pattern=r'^[\w.:-]+$')
    expected_version: int = Field(default=0, ge=0, strict=True)
    lead_id: UUID | None = None
    company: Company | None = None
    dataset: str = Field(min_length=2, max_length=80)
    split: Literal['development', 'validation']
    reviewed_on: date
    reviewer: str = Field(min_length=2, max_length=100)
    label_origin: Literal['human']
    classification: Literal['suitable', 'unsuitable', 'uncertain']
    justification: str = Field(min_length=15, max_length=1500)
    services: list[str] = Field(default_factory=list, max_length=11)
    operator_priority: Literal['low', 'medium', 'high', 'unknown'] = 'unknown'
    review_status: Literal['reviewed', 'needs_review'] = 'reviewed'
    evidence: list[ReviewEvidence] = Field(min_length=1, max_length=12)
    outcome: Literal['unknown', 'not_contacted', 'no_reply', 'reply', 'meeting', 'proposal', 'won', 'lost', 'refused', 'opt_out'] = 'unknown'
    outcome_reference: str = Field(default='', max_length=1000)
    outcome_on: date | None = None
    system_observation: SystemObservation | None = None

    @field_validator('services')
    @classmethod
    def known_services(cls, value):
        if len(set(value)) != len(value) or any(v not in SERVICE_LABELS for v in value):
            raise ValueError('Selecione serviços distintos do catálogo existente.')
        return value

    @model_validator(mode='after')
    def valid_record(self):
        if self.reviewed_on > date.today() or (self.outcome_on and self.outcome_on > date.today()):
            raise ValueError('Data futura não permitida.')
        if self.lead_id and (self.company or self.system_observation):
            raise ValueError('A identidade e o Score do Lead são obtidos pelo servidor.')
        if not self.lead_id and not self.company:
            raise ValueError('Caso externo exige identidade desambiguada.')
        if self.outcome not in ('unknown', 'not_contacted') and (not self.outcome_on or len(self.outcome_reference) < 5):
            raise ValueError('Resultado comercial exige data e referência.')
        return self


class ImportInput(StrictModel):
    request_key: UUID
    records: list[dict[str, Any]] = Field(min_length=1, max_length=50)


class CommitInput(StrictModel):
    preview_hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    confirm_human_reviews: Literal[True]


def lock(db):
    # One short transaction serializes preview/commit decisions on SQLite and PostgreSQL.
    db.execute(update(LearningGate).where(LearningGate.id == 1).values(version=LearningGate.version + 1))


def snapshot(lead):
    result = score(lead)
    status = result['status']
    return {'origin': 'scoutliq_live', 'score': result['value'], 'status': status,
        'decision': 'selected' if status == 'qualified' else 'rejected' if status in ('evaluated', 'incompatible') else 'abstained',
        'criteria_version': result['version'], 'coverage': result['coverage'],
        'dimensions': result['commercial_dimensions'], 'fit': result['commercial_fit'],
        'criteria': configuration(lead)[0],
        'lead_version': lead.version}


def case_row(case):
    return {'id': case.id, 'version': case.version, 'lead_id': case.lead_id,
        'record': json.loads(case.record_json), 'system': json.loads(case.system_json), 'updated_at': case.updated_at}


def normalized_record(db, user, item):
    record = item.model_dump(mode='json', exclude={'expected_version'})
    lead = owned(db, Lead, str(item.lead_id), user) if item.lead_id else None
    if lead:
        if lead.demo: raise HTTPException(409, 'Casos de demonstração não são revisões humanas reais.')
        company = {k: getattr(lead, k) for k in ('name', 'country', 'city', 'address', 'phone')}
        company.update(sector=lead.category, region=lead.city)
        system = snapshot(lead)
        identity_key = digest(['lead', lead.id])
    else:
        company = item.company.model_dump()
        company_identity = [norm(company[k]) for k in ('name', 'country', 'city', 'address')]
        # Address is stable identity when supplied; otherwise exact normalized phone.
        identity_key = digest(company_identity + ([re.sub(r'\D', '', company['phone'])] if not company['address'] else []))
        system = ({'origin': 'external_declared', **item.system_observation.model_dump(mode='json')}
                  if item.system_observation else {'origin': 'unavailable', 'score': None, 'decision': 'abstained', 'criteria_version': None})
        candidate = SimpleNamespace(**company)
        leads = db.scalars(select(Lead).where(Lead.user_id == user.id, Lead.country == company['country']))
        if any(same_business(candidate, known) for known in leads):
            raise HTTPException(409, 'Identidade já cadastrada. Vincule o Lead existente.')
    record['company'] = company
    for evidence in item.evidence:
        if evidence.evidence_id:
            e = owned(db, OpportunityEvidence, str(evidence.evidence_id), user)
            if not lead or e.lead_id != lead.id: raise HTTPException(404, 'Evidência não encontrada nesta oportunidade.')
    return record, system, identity_key


@router.post('/imports/preview')
def preview(payload: ImportInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    limiter.check('learning-preview:' + user.id, 20, 60)
    raw = payload.model_dump(mode='json')
    input_hash = digest(raw['records'])
    lock(db)
    previous = db.scalar(select(LearningImport).where(LearningImport.user_id == user.id, LearningImport.request_key == str(payload.request_key)))
    if previous:
        if previous.input_hash != input_hash: raise HTTPException(409, 'Chave de importação reutilizada com conteúdo diferente.')
        return import_row(previous)
    now = int(time.time())
    # Unconfirmed previews are temporary. Committed receipts remain for idempotence/audit.
    db.execute(delete(LearningImport).where(LearningImport.user_id == user.id, LearningImport.committed_at.is_(None), LearningImport.expires_at < now))
    count = db.scalar(select(func.count()).select_from(LearningImport).where(LearningImport.user_id == user.id, LearningImport.committed_at.is_(None)))
    if count >= 50: raise HTTPException(429, 'Há muitas prévias pendentes. Aguarde a expiração de 24 horas.')
    rows, keys, identities = [], set(), set()
    for index, raw_record in enumerate(payload.records):
        try:
            item = CaseInput.model_validate(raw_record)
            key = (item.source, item.external_id)
            if key in keys: raise HTTPException(409, 'Identificador repetido neste arquivo.')
            keys.add(key)
            record, system, identity_key = normalized_record(db, user, item)
            if identity_key in identities: raise HTTPException(409, 'Empresa repetida neste arquivo.')
            identities.add(identity_key)
            existing = db.scalar(select(LearningCase).where(LearningCase.user_id == user.id,
                LearningCase.source == item.source, LearningCase.external_id == item.external_id))
            duplicate = db.scalar(select(LearningCase).where(LearningCase.user_id == user.id, LearningCase.identity_key == identity_key))
            if duplicate and (not existing or duplicate.id != existing.id):
                raise HTTPException(409, 'Empresa já revisada com outro identificador. Corrija o caso existente.')
            if existing and existing.identity_key != identity_key:
                raise HTTPException(409, 'Não é permitido trocar a identidade de um caso existente.')
            if not existing:
                candidate = SimpleNamespace(**record['company'])
                for known in db.scalars(select(LearningCase).where(LearningCase.user_id == user.id)):
                    if same_business(candidate, SimpleNamespace(**json.loads(known.record_json)['company'])):
                        raise HTTPException(409, 'Empresa já revisada. Use o identificador do caso existente.')
            record_hash = digest(record)
            action = 'unchanged' if existing and existing.record_hash == record_hash else 'update' if existing else 'create'
            if action != 'unchanged' and item.expected_version != (existing.version if existing else 0):
                raise HTTPException(409, 'Versão desatualizada. Consulte o caso e gere outra prévia.')
            rows.append({'index': index, 'action': action, 'case_id': existing.id if existing else None,
                'expected_version': existing.version if existing else 0, 'identity_key': identity_key,
                'record': record, 'system': system, 'record_hash': record_hash,
                'before': case_row(existing) if existing else None, 'errors': []})
        except ValidationError as exc:
            rows.append({'index': index, 'action': 'error', 'errors': [
                {'field': '.'.join(map(str, e['loc'])), 'message': str(e.get('ctx', {}).get('error') or ('Campo inválido: ' + e['type']))[:300]} for e in exc.errors()]})
        except HTTPException as exc:
            rows.append({'index': index, 'action': 'error', 'errors': [{'field': '', 'message': exc.detail}]})
    preview_value = {'rows': rows, 'valid': all(not row['errors'] for row in rows)}
    entry = LearningImport(user_id=user.id, request_key=str(payload.request_key), input_hash=input_hash,
        preview_json=encode(preview_value), receipt_json='{}', expires_at=now + 86400)
    db.add(entry); db.commit()
    return import_row(entry)


def import_row(entry):
    value = json.loads(entry.preview_json)
    return {'id': entry.id, 'preview_hash': digest(value), **value, 'expires_at': entry.expires_at,
            'committed_at': entry.committed_at, 'receipt': json.loads(entry.receipt_json)}


@router.get('/imports/{import_id}')
def get_import(import_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return import_row(owned(db, LearningImport, import_id, user))


@router.post('/imports/{import_id}/commit')
def commit(import_id: str, payload: CommitInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    limiter.check('learning-commit:' + user.id, 30, 60)
    lock(db)
    entry = owned(db, LearningImport, import_id, user)
    value = json.loads(entry.preview_json)
    if payload.preview_hash != digest(value): raise HTTPException(409, 'Prévia diferente da confirmação.')
    if entry.committed_at: return json.loads(entry.receipt_json)
    if entry.expires_at <= int(time.time()): raise HTTPException(409, 'Prévia expirada. Gere outra prévia.')
    if not value['valid']: raise HTTPException(409, 'Corrija todos os registros antes de importar.')
    today = int(time.time()) // 86400 * 86400
    if db.scalar(select(func.count()).select_from(LearningImport).where(LearningImport.user_id == user.id, LearningImport.committed_at >= today)) >= 100:
        raise HTTPException(429, 'Limite de 100 importações confirmadas por dia UTC.')
    count = db.scalar(select(func.count()).select_from(LearningCase).where(LearningCase.user_id == user.id))
    if count + sum(row['action'] == 'create' for row in value['rows']) > MAX_CASES:
        raise HTTPException(409, 'Limite de 2.000 empresas revisadas por conta.')
    receipt = {'import_id': entry.id, 'created': 0, 'updated': 0, 'unchanged': 0, 'cases': []}
    now = int(time.time())
    for row in value['rows']:
        case = owned(db, LearningCase, row['case_id'], user) if row['case_id'] else None
        if case and case.version != row['expected_version']:
            raise HTTPException(409, 'Caso alterado depois da prévia. Nada foi importado.')
        record = row['record']
        lead = owned(db, Lead, record['lead_id'], user) if record['lead_id'] else None
        if not lead:
            normalized_record(db, user, CaseInput.model_validate(record))
        if not case:
            candidate = SimpleNamespace(**record['company'])
            for known in db.scalars(select(LearningCase).where(LearningCase.user_id == user.id)):
                if same_business(candidate, SimpleNamespace(**json.loads(known.record_json)['company'])):
                    raise HTTPException(409, 'Empresa já revisada depois da prévia. Nada foi importado.')
        if lead and (lead.demo or snapshot(lead) != row['system']):
            raise HTTPException(409, 'Oportunidade alterada depois da prévia. Nada foi importado.')
        for evidence in record['evidence']:
            if evidence['evidence_id']:
                e = owned(db, OpportunityEvidence, evidence['evidence_id'], user)
                if not lead or e.lead_id != lead.id: raise HTTPException(409, 'Evidência indisponível. Gere outra prévia.')
        if row['action'] == 'unchanged':
            receipt['unchanged'] += 1
        else:
            if not case:
                case = LearningCase(user_id=user.id, lead_id=record['lead_id'], source=record['source'],
                    external_id=record['external_id'], identity_key=row['identity_key'], version=1)
                db.add(case)
            case.dataset, case.split = record['dataset'], record['split']
            case.record_json, case.system_json = encode(record), encode(row['system'])
            case.record_hash, case.updated_at = row['record_hash'], now
            db.flush()  # Optimistic version and unique source/identity constraints are part of this transaction.
            frozen = case_row(case) | {'recorded_by': user.id, 'import_id': entry.id, 'human_attested': True}
            db.add(LearningRevision(user_id=user.id, case_id=case.id, version=case.version,
                snapshot_json=encode(frozen), recorded_at=now))
            if lead:
                activity(db, lead, 'commercial_review', 'Revisão humana de oportunidade registrada.',
                    case_id=case.id, case_version=case.version, classification=record['classification'], import_id=entry.id)
            receipt['created' if row['action'] == 'create' else 'updated'] += 1
        receipt['cases'].append({'id': case.id, 'version': case.version})
    entry.committed_at, entry.receipt_json = now, encode(receipt)
    db.commit()
    return receipt


@router.get('/cases')
def list_cases(lead_id: UUID | None = None, dataset: str | None = Query(None, max_length=80),
               offset: int = Query(0, ge=0), user: User = Depends(current_user), db: Session = Depends(get_db)):
    query = select(LearningCase).where(LearningCase.user_id == user.id)
    if lead_id:
        owned(db, Lead, str(lead_id), user)
        query = query.where(LearningCase.lead_id == str(lead_id))
    if dataset: query = query.where(LearningCase.dataset == dataset)
    return {'cases': [case_row(c) for c in db.scalars(query.order_by(LearningCase.updated_at.desc(), LearningCase.id).offset(offset).limit(50))]}


@router.get('/cases/{case_id}')
def get_case(case_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return case_row(owned(db, LearningCase, case_id, user))


@router.get('/cases/{case_id}/history')
def history(case_id: str, offset: int = Query(0, ge=0), user: User = Depends(current_user), db: Session = Depends(get_db)):
    owned(db, LearningCase, case_id, user)
    return {'revisions': [json.loads(r.snapshot_json) for r in db.scalars(select(LearningRevision).where(
        LearningRevision.user_id == user.id, LearningRevision.case_id == case_id).order_by(LearningRevision.version.desc()).offset(offset).limit(50))]}


class EvaluationInput(StrictModel):
    request_key: UUID
    dataset: str = Field(min_length=2, max_length=80)
    split: Literal['development', 'validation']
    k: int = Field(default=10, ge=1, le=100, strict=True)


@router.post('/evaluations')
def evaluate(payload: EvaluationInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    limiter.check('learning-evaluation:' + user.id, 10, 60)
    lock(db)
    parameters = payload.model_dump(mode='json', exclude={'request_key'})
    previous = db.scalar(select(LearningEvaluation).where(LearningEvaluation.user_id == user.id, LearningEvaluation.request_key == str(payload.request_key)))
    if previous:
        if previous.input_hash != digest(parameters): raise HTTPException(409, 'Chave reutilizada com parâmetros diferentes.')
        return evaluation_row(previous)
    if db.scalar(select(func.count()).select_from(LearningEvaluation).where(LearningEvaluation.user_id == user.id, LearningEvaluation.created_at >= int(time.time()) // 86400 * 86400)) >= 30:
        raise HTTPException(429, 'Limite de 30 avaliações congeladas por dia UTC.')
    cases = db.scalars(select(LearningCase).where(LearningCase.user_id == user.id, LearningCase.dataset == payload.dataset,
        LearningCase.split == payload.split).order_by(LearningCase.id)).all()
    if not cases: raise HTTPException(409, 'Nenhum caso neste conjunto e divisão.')
    frozen = [case_row(c) for c in cases]
    report = reviewed_metrics(frozen, payload.k) | {'parameters': parameters, 'dataset_hash': digest(frozen)}
    entry = LearningEvaluation(user_id=user.id, request_key=str(payload.request_key), input_hash=digest(parameters),
        dataset=payload.dataset, snapshot_json=encode(frozen), report_json=encode(report), created_at=int(time.time()))
    db.add(entry); db.commit()
    return evaluation_row(entry)


def evaluation_row(entry):
    return {'id': entry.id, 'created_at': entry.created_at, 'report': json.loads(entry.report_json)}


@router.get('/evaluations')
def list_evaluations(offset: int = Query(0, ge=0), user: User = Depends(current_user), db: Session = Depends(get_db)):
    return {'evaluations': [evaluation_row(r) for r in db.scalars(select(LearningEvaluation).where(
        LearningEvaluation.user_id == user.id).order_by(LearningEvaluation.created_at.desc(), LearningEvaluation.id).offset(offset).limit(20))]}


@router.get('/evaluations/{evaluation_id}')
def get_evaluation(evaluation_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    entry = owned(db, LearningEvaluation, evaluation_id, user)
    return evaluation_row(entry) | {'cases': json.loads(entry.snapshot_json)}


def export_learning(db, user):
    from .learning_models import CalibrationProposal, CalibrationChange
    from .score_calibration import proposal_row, change_row, current
    def rows(model): return db.scalars(select(model).where(model.user_id == user.id)).all()
    return {'commercial_learning': {
        'cases': [case_row(c) for c in rows(LearningCase)],
        'revisions': [json.loads(r.snapshot_json) for r in rows(LearningRevision)],
        'evaluations': [evaluation_row(e) | {'cases': json.loads(e.snapshot_json)} for e in rows(LearningEvaluation)],
        'import_receipts': [json.loads(i.receipt_json) for i in rows(LearningImport) if i.committed_at],
        'criteria': current(db, user)[1], 'calibrations': [proposal_row(p) for p in rows(CalibrationProposal)],
        'criteria_history': [change_row(c) for c in rows(CalibrationChange)]}}
