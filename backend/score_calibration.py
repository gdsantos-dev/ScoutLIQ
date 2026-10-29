"""Offline hypotheses, explicit application and auditable rollback of the canonical Score."""
import json
import time
from copy import deepcopy
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .db import get_db
from .models import User, Lead, SmartSearch, ResearchBatch, RadarSavedSearch
from .learning_models import ScoreConfiguration, CalibrationProposal, CalibrationChange, LearningEvaluation, LearningCase
from .commercial_learning import lock, digest, encode
from .opportunity_workflow import owned, activity
from .score_criteria import Criteria, BASELINE, commercial_priority
from .scoring import score
from .schemas import StrictModel
from .security import current_user, limiter
from .selection_quality import reviewed_metrics

router = APIRouter(prefix='/api/learning/calibrations')


def current(db, user):
    config = db.get(ScoreConfiguration, user.id)
    raw = json.loads(config.config_json) if config else {}
    return config, {'version': config.version if config else 0, 'criteria': raw.get('criteria', BASELINE),
                    'engine_version': raw.get('version', '3.0')}


class ProposalInput(StrictModel):
    request_key: UUID
    development_id: UUID
    validation_id: UUID
    expected_version: int = Field(ge=0, strict=True)
    criteria: Criteria | None = None
    reason: str = Field(min_length=15, max_length=1000)


class ApplyInput(StrictModel):
    expected_version: int = Field(ge=0, strict=True)
    report_hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    approve_score_change: Literal[True]
    acknowledge_sample_limits: Literal[True]


class RollbackInput(StrictModel):
    expected_version: int = Field(ge=1, strict=True)
    reason: str = Field(min_length=15, max_length=1000)
    approve_score_change: Literal[True]


def paired(cases, criteria):
    eligible = [c for c in cases if c['system']['origin'] == 'scoutliq_live' and c['system'].get('dimensions') and c['system'].get('fit')]
    changed, after = [], []
    for case in eligible:
        item = deepcopy(case)
        result = commercial_priority(item['system']['dimensions'], item['system']['fit'], criteria)
        new_decision = 'selected' if result['status'] == 'qualified' else 'rejected' if result['status'] in ('evaluated', 'incompatible') else 'abstained'
        item['system'].update(score=result['value'], decision=new_decision, criteria_version='proposed', criteria=criteria)
        after.append(item)
        if case['system']['decision'] != new_decision or case['system']['score'] != result['value']:
            human = case['record']['classification'] if case['record']['review_status'] == 'reviewed' else 'uncertain'
            def correct(decision):
                return None if human == 'uncertain' else decision == ('selected' if human == 'suitable' else 'rejected')
            old_correct, new_correct = correct(case['system']['decision']), correct(new_decision)
            changed.append({'case_id': case['id'], 'case_version': case['version'], 'name': case['record']['company']['name'],
                'human': human, 'before': case['system']['decision'], 'after': new_decision,
                'score_before': case['system']['score'], 'score_after': result['value'],
                'regression': old_correct is True and new_correct is False,
                'improvement': old_correct is False and new_correct is True,
                'justification': case['record']['justification'], 'evidence': case['record']['evidence']})
    return {'sample': len(cases), 'replayable': len(eligible), 'excluded': len(cases)-len(eligible),
        'before': reviewed_metrics(eligible), 'after': reviewed_metrics(after), 'changes': changed,
        'regressions': sum(c['regression'] for c in changed), 'improvements': sum(c['improvement'] for c in changed)}


def proposal_row(item):
    report = json.loads(item.report_json)
    return {'id': item.id, 'created_at': item.created_at, 'base_version': item.base_version,
            'report_hash': digest(report), 'report': report}


@router.get('/configuration')
def get_configuration(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return current(db, user)[1]


@router.post('/proposals')
def propose(payload: ProposalInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    limiter.check('calibration-proposal:' + user.id, 10, 60)
    lock(db)
    input_hash = digest(payload.model_dump(mode='json', exclude={'request_key'}))
    previous = db.scalar(select(CalibrationProposal).where(CalibrationProposal.user_id == user.id, CalibrationProposal.request_key == str(payload.request_key)))
    if previous:
        if previous.input_hash != input_hash: raise HTTPException(409, 'Chave de proposta reutilizada com outros parâmetros.')
        return proposal_row(previous)
    if db.scalar(select(func.count()).select_from(CalibrationProposal).where(CalibrationProposal.user_id == user.id, CalibrationProposal.created_at >= int(time.time()) // 86400 * 86400)) >= 30:
        raise HTTPException(429, 'Limite de 30 comparações de critérios por dia UTC.')
    _, active = current(db, user)
    if payload.expected_version != active['version']: raise HTTPException(409, 'Configuração alterada. Atualize antes de propor.')
    dev = owned(db, LearningEvaluation, str(payload.development_id), user)
    validation = owned(db, LearningEvaluation, str(payload.validation_id), user)
    if json.loads(dev.report_json)['parameters']['split'] != 'development' or json.loads(validation.report_json)['parameters']['split'] != 'validation':
        raise HTTPException(422, 'Selecione conjuntos separados de desenvolvimento e validação.')
    dev_cases, val_cases = json.loads(dev.snapshot_json), json.loads(validation.snapshot_json)
    if {c['id'] for c in dev_cases} & {c['id'] for c in val_cases}:
        raise HTTPException(409, 'Há empresas repetidas entre desenvolvimento e validação.')
    if any(c['system'].get('criteria') != active['criteria'] for c in dev_cases + val_cases if c['system']['origin'] == 'scoutliq_live'):
        raise HTTPException(409, 'As amostras precisam registrar os critérios atualmente ativos.')
    if payload.criteria:
        criteria, method = payload.criteria.model_dump(), 'operator_proposal'
    else:
        # Only development labels select a hypothesis. Validation labels never optimize it.
        options = []
        for threshold in (70, 80, 90):
            candidate = deepcopy(active['criteria']); candidate['selection_threshold'] = threshold
            if candidate == active['criteria']: continue
            comparison = paired(dev_cases, candidate)
            options.append((comparison['improvements']-comparison['regressions'], -threshold, candidate))
        best = max(options, key=lambda item: item[:2])
        if best[0] <= 0: raise HTTPException(409, 'Nenhuma hipótese controlada melhorou os casos de desenvolvimento. Amplie ou revise a amostra.')
        criteria, method = best[2], 'development_threshold_search'
    development, holdout = paired(dev_cases, criteria), paired(val_cases, criteria)
    if not development['before']['metrics']['labeled'] or not holdout['before']['metrics']['labeled']:
        raise HTTPException(409, 'São necessários casos humanos conclusivos com dimensões nativas em ambas as amostras.')
    if criteria == active['criteria']: raise HTTPException(409, 'Os critérios propostos são iguais aos atuais.')
    report = {'reason': payload.reason, 'method': method, 'previous': active, 'criteria': criteria,
        'development_id': dev.id, 'validation_id': validation.id,
        'development': development, 'validation': holdout,
        'case_versions': [{'id': c['id'], 'version': c['version']} for c in dev_cases+val_cases],
        'limitations': ['Hipótese estimada nos mesmos snapshots, sem nova pesquisa ou comprovação de ganho comercial.',
            'A validação deve permanecer independente. Reutilizar o mesmo conjunto para escolher ajustes causa vazamento de avaliação.',
            'Aprovação explícita altera critérios apenas nesta conta, preservando snapshots e histórico.',
            'Pesos não alteram portões de identidade, atividade, contato, necessidade e compatibilidade.',
            'Scores externos sem dimensões nativas não podem sustentar recalibração.']}
    item = CalibrationProposal(user_id=user.id, request_key=str(payload.request_key), input_hash=input_hash,
        report_json=encode(report), base_version=active['version'], created_at=int(time.time()))
    db.add(item); db.commit()
    return proposal_row(item)


@router.get('/proposals')
def proposals(user: User = Depends(current_user), db: Session = Depends(get_db), offset: int = Query(0, ge=0)):
    return {'proposals': [proposal_row(p) for p in db.scalars(select(CalibrationProposal).where(
        CalibrationProposal.user_id == user.id).order_by(CalibrationProposal.created_at.desc(), CalibrationProposal.id).offset(offset).limit(20))]}


@router.get('/proposals/{proposal_id}')
def get_proposal(proposal_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return proposal_row(owned(db, CalibrationProposal, proposal_id, user))


def change_row(change):
    return {'id': change.id, 'proposal_id': change.proposal_id, 'reverted_change_id': change.reverted_change_id,
        'previous': json.loads(change.previous_json), 'applied': json.loads(change.applied_json),
        'config_version': change.config_version, 'reason': change.reason, 'created_at': change.created_at}


def change_configuration(db, user, criteria, reason, proposal_id=None, reverted_change_id=None):
    now = int(time.time())
    # Avoid changing selection criteria while work on this user's opportunities is in flight.
    busy = (db.scalar(select(SmartSearch.id).where(SmartSearch.user_id == user.id, SmartSearch.status.in_(('pending','running','investigating'))).limit(1))
        or db.scalar(select(ResearchBatch.id).where(ResearchBatch.user_id == user.id, ResearchBatch.status.in_(('pending','running'))).limit(1))
        or db.scalar(select(RadarSavedSearch.id).where(RadarSavedSearch.user_id == user.id, RadarSavedSearch.lease_until > now).limit(1)))
    if busy: raise HTTPException(409, 'Conclua ou cancele as pesquisas ativas antes de alterar critérios.')
    leads = list(db.scalars(select(Lead).where(Lead.user_id == user.id).order_by(Lead.id).limit(5001)))
    if len(leads) > 5000: raise HTTPException(409, 'Aplicação acima de 5.000 oportunidades requer execução em lote ainda indisponível.')
    config, before = current(db, user)
    change = CalibrationChange(user_id=user.id, proposal_id=proposal_id, reverted_change_id=reverted_change_id,
        previous_json=encode(before), applied_json='{}', config_version=0, reason=reason, created_at=now)
    db.add(change); db.flush()
    raw = {} if criteria == BASELINE else {'criteria': criteria, 'version': '3.0-' + change.id}
    if not config:
        config = ScoreConfiguration(user_id=user.id, config_json=encode(raw), version=1); db.add(config)
    else:
        # Even rollback to the same values must advance the optimistic configuration version.
        config.config_json = encode(raw)
        config.version += 1
    for lead in leads:
        old_score = score(lead); old_score.pop('previous', None)
        lead.previous_score_json = encode(old_score)
        lead.score_criteria_json = encode(raw)
        new_score = score(lead); new_score.pop('previous', None)
        activity(db, lead, 'score_calibration', 'Critérios do Score alterados por aprovação explícita.',
            change_id=change.id, before=old_score, after=new_score)
    db.flush()
    change.applied_json = encode(current(db, user)[1])
    change.config_version = config.version
    return change


@router.post('/proposals/{proposal_id}/apply')
def apply(proposal_id: str, payload: ApplyInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    limiter.check('calibration-apply:' + user.id, 5, 60)
    lock(db)
    proposal = owned(db, CalibrationProposal, proposal_id, user)
    report = json.loads(proposal.report_json)
    if payload.report_hash != digest(report): raise HTTPException(409, 'A comparação aprovada não corresponde à proposta.')
    existing = db.scalar(select(CalibrationChange).where(CalibrationChange.user_id == user.id, CalibrationChange.proposal_id == proposal.id))
    if existing: return change_row(existing)
    _, active = current(db, user)
    if payload.expected_version != active['version'] or proposal.base_version != active['version']:
        raise HTTPException(409, 'Configuração alterada depois da proposta. Gere outra comparação.')
    for frozen in report['case_versions']:
        case = owned(db, LearningCase, frozen['id'], user)
        if case.version != frozen['version']: raise HTTPException(409, 'Revisões humanas mudaram. Reavalie antes de aplicar.')
    change = change_configuration(db, user, report['criteria'], report['reason'], proposal_id=proposal.id)
    db.commit()
    return change_row(change)


@router.get('/changes')
def changes(user: User = Depends(current_user), db: Session = Depends(get_db), offset: int = Query(0, ge=0)):
    return {'changes': [change_row(c) for c in db.scalars(select(CalibrationChange).where(CalibrationChange.user_id == user.id)
        .order_by(CalibrationChange.config_version.desc()).offset(offset).limit(50))]}


@router.post('/changes/{change_id}/rollback')
def rollback(change_id: str, payload: RollbackInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    limiter.check('calibration-rollback:' + user.id, 5, 60)
    lock(db)
    original = owned(db, CalibrationChange, change_id, user)
    previous_rollback = db.scalar(select(CalibrationChange).where(CalibrationChange.user_id == user.id, CalibrationChange.reverted_change_id == original.id))
    if previous_rollback: return change_row(previous_rollback)
    _, active = current(db, user)
    if payload.expected_version != active['version'] or original.config_version != active['version']:
        raise HTTPException(409, 'Somente a alteração vigente pode ser revertida. Atualize o histórico.')
    change = change_configuration(db, user, json.loads(original.previous_json)['criteria'], payload.reason, reverted_change_id=original.id)
    db.commit()
    return change_row(change)
