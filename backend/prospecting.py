"""A bounded admission policy for routines.schedule_due, never another scheduler.

All mutations share the existing executor's short transaction fence. No network
inside transactions; provider calls still reserve through consumption.reserve.
"""
import hashlib
import json
import time
from datetime import date, datetime, timedelta
from typing import Literal
from uuid import uuid4
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, model_validator
from sqlalchemy import select, update, delete, func, case
from .db import get_db
from .models import User, Lead, RadarSavedSearch, ResearchExecutor, ResearchBatch, ResearchBatchItem, SmartSearch
from .autonomy_models import RoutineRun, WorkAttempt, ProviderOperation
from .prospecting_models import ProspectingPlan, PlanMember, PlanDecision, PlanIncorporation
from .search_intent import Strict, Intent
from .security import current_user, limiter

router = APIRouter(prefix='/api/operations/plan', tags=['operations'])
ACTIVE = ('running', 'paused')


class Member(Strict):
    saved_search_id: str = Field(min_length=1, max_length=36)
    priority: int = Field(default=1, ge=1, le=5, strict=True)


class PlanConfig(Strict):
    daily_target: int = Field(default=50, ge=1, le=500, strict=True)
    members: list[Member] = Field(min_length=1, max_length=20)
    locations: list[str] = Field(min_length=1, max_length=20)
    weekdays: list[Literal[0, 1, 2, 3, 4, 5, 6]] = Field(default=[0, 1, 2, 3, 4], min_length=1, max_length=7)
    window_start: str = Field(default='09:00', pattern=r'^([01][0-9]|2[0-3]):[0-5][0-9]$')
    window_end: str = Field(default='18:00', pattern=r'^([01][0-9]|2[0-3]):[0-5][0-9]$')
    daily_runs: int = Field(default=4, ge=1, le=20, strict=True)
    companies_per_search: int = Field(default=50, ge=1, le=100, strict=True)
    daily_investigations: int = Field(default=15, ge=0, le=100, strict=True)
    daily_operations: int = Field(default=100, ge=1, le=1000, strict=True)
    cooldown_hours: int = Field(default=24, ge=24, le=2160, strict=True)

    @model_validator(mode='after')
    def consistent(self):
        if self.window_end <= self.window_start:
            raise ValueError('A janela deve terminar no mesmo dia, depois do início.')
        if len({m.saved_search_id for m in self.members}) != len(self.members):
            raise ValueError('Pesquisa repetida no plano.')
        if len(set(self.weekdays)) != len(self.weekdays) or len(set(self.locations)) != len(self.locations):
            raise ValueError('Dias e localizações devem ser únicos.')
        if any(not s or len(s) > 200 for s in self.locations):
            raise ValueError('Localização inválida.')
        return self


class Configure(Strict):
    version: int = Field(ge=0)
    config: PlanConfig


class Control(Strict):
    version: int = Field(ge=1)
    action: Literal['activate', 'pause', 'resume', 'disable', 'run_now']
    confirm: bool = Field(default=False, strict=True)
    preview_token: str = Field(default='', max_length=64)


def dump(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def config(plan):
    return PlanConfig.model_validate_json(plan.config_json)


def owned(db, user):
    return db.scalar(select(ProspectingPlan).where(ProspectingPlan.user_id == user.id))


def fence(db):
    db.execute(update(ResearchExecutor).where(ResearchExecutor.id == 1).values(next_at=ResearchExecutor.next_at))


def guard_saved_deletion(db, saved, now):
    """Do not erase today's canonical budget joins through a cascading delete."""
    fence(db)
    plan=db.scalar(select(ProspectingPlan).where(ProspectingPlan.user_id==saved.user_id))
    if not plan: return
    _,start,end=bounds(plan.timezone,now)
    linked=select(RoutineRun.id).join(PlanDecision,PlanDecision.run_id==RoutineRun.id).where(
        PlanDecision.plan_id==plan.id,RoutineRun.user_id==saved.user_id,RoutineRun.saved_search_id==saved.id)
    today=db.scalar(linked.where(RoutineRun.started_at>=start,RoutineRun.started_at<end).limit(1))
    attempts=db.scalar(select(WorkAttempt.token).where(WorkAttempt.run_id.in_(linked),WorkAttempt.started_at>=start,WorkAttempt.started_at<end).limit(1))
    if today or attempts:
        raise HTTPException(409,'Esta pesquisa possui execução do plano no dia operacional. Pause ou desative a rotina; exclua em outro dia para preservar os limites e o histórico diário.')


def bounds(timezone, now, day=None):
    local = datetime.fromtimestamp(now, ZoneInfo(timezone))
    chosen = day or local.date()
    start = datetime.combine(chosen, datetime.min.time(), tzinfo=local.tzinfo)
    return chosen.isoformat(), int(start.timestamp()), int((start + timedelta(days=1)).timestamp())


def operational_window(plan, now):
    cfg = config(plan)
    local = datetime.fromtimestamp(now, ZoneInfo(plan.timezone))
    begin = local.replace(hour=int(cfg.window_start[:2]), minute=int(cfg.window_start[3:]), second=0, microsecond=0)
    end = local.replace(hour=int(cfg.window_end[:2]), minute=int(cfg.window_end[3:]), second=0, microsecond=0)
    if local.weekday() in cfg.weekdays and begin <= local < end:
        return True, int(end.timestamp())
    for offset in range(8):
        upcoming = begin + timedelta(days=offset)
        if upcoming.weekday() in cfg.weekdays and upcoming > local:
            return False, int(upcoming.timestamp())
    raise ValueError('Invalid operational window')


def location_label(raw):
    if raw.get('location'): return raw['location'].get('formatted') or raw['location'].get('name', '')
    if raw.get('area'): return raw['area'].get('label') or 'Área selecionada no mapa'
    if raw.get('legacy'): return raw['legacy'].get('location', '')
    market = raw.get('market', {})
    return ', '.join(str(market[k]) for k in ('city', 'region', 'country') if market.get(k))


def member_info(saved, provider):
    from .routines import config_of
    from .smart_search import validate_intent, discovery_sectors
    from .search_sources import capabilities, legacy_capabilities
    cfg = config_of(saved)
    reason, coverage = '', []
    intent = cfg.get('intent') or json.loads(saved.query_json).get('commercial_intent') or {}
    if saved.routine_state != 'active': reason = 'Rotina não está ativa; o plano não a habilita.'
    elif saved.monitor_enabled: reason = 'Monitor territorial ativo; revise a rotina.'
    elif not cfg or cfg.get('limits', {}).get('objective') != 'prospect': reason = 'Configure uma rotina de prospecção.'
    elif cfg.get('provider') != getattr(provider, 'name', 'unconfigured'): reason = 'Fonte alterada ou não configurada.'
    else:
        try:
            parsed = validate_intent(Intent.model_validate(intent))
            coverage = [dict(sector=s, **(legacy_capabilities(provider, parsed.legacy.discovery()) if parsed.legacy else capabilities(provider, s, parsed.location, parsed.area))) for s in discovery_sectors(parsed)]
            if any(not item['supported'] for item in coverage): reason = 'Fonte sem cobertura para os critérios autorizados.'
        except (ValueError, HTTPException): reason = 'Intenção indisponível; revise a pesquisa salva.'
    fingerprint = hashlib.sha256(dump({'config':cfg, 'query':json.loads(saved.query_json)}).encode()).hexdigest()
    return dict(id=saved.id, name=saved.name, location=location_label(intent), state=saved.routine_state,
        reason=reason, provider=cfg.get('provider'), coverage=coverage, limits=cfg.get('limits'), fingerprint=fingerprint)


def preview(db, plan, user, provider):
    from .research_worker import MODE, BUDGET, INTERVAL
    from .consumption import HTTP_BUDGET, PROVIDER_LIMITS
    cfg = config(plan)
    saved = {s.id:s for s in db.scalars(select(RadarSavedSearch).where(RadarSavedSearch.user_id == user.id, RadarSavedSearch.id.in_([m.saved_search_id for m in cfg.members])))}
    members = [dict(member_info(saved[m.saved_search_id], provider), priority=m.priority) if m.saved_search_id in saved else dict(id=m.saved_search_id, reason='Pesquisa removida ou indisponível.') for m in cfg.members]
    blockers = [m['reason'] for m in members if m['reason']]
    if MODE != 'worker': blockers.append('Ative o executor existente em modo worker.')
    if user.timezone != plan.timezone: blockers.append('Fuso da conta alterado; salve e revise o plano.')
    if any(m.get('location') not in cfg.locations for m in members): blockers.append('Localização fora da seleção autorizada.')
    envelope = dict(config=cfg.model_dump(), timezone=plan.timezone, members=members,
        global_limits=dict(tasks=BUDGET, operations=HTTP_BUDGET, providers=PROVIDER_LIMITS, interval_seconds=INTERVAL), mode=MODE)
    token = hashlib.sha256(dump(envelope).encode()).hexdigest()
    return dict(**envelope, token=token, blockers=list(dict.fromkeys(blockers)), monetary_cost=None,
        restrictions=['Uma pesquisa coordenada por vez por conta. Limites mais restritivos das rotinas e do worker prevalecem.',
            'A frequência respeita intervalo original, cooldown, dias e janela; atingir a meta não é garantido.',
            'Pausar encerra os jobs do plano. Desativar devolve as pesquisas às recorrências originais já autorizadas.',
            'Meta, orçamento, falha, ausência de trabalho, pausa e fim da janela interrompem novas execuções.',
            'Nenhum envio comercial é autorizado pelo plano.'])


def progress(db, plan, now, day=None):
    label, start, end = bounds(plan.timezone, now, day)
    end = min(end, now + 1)
    lead_scope = (Lead.user_id == plan.user_id, Lead.demo.is_(False), Lead.created_at >= start, Lead.created_at < end)
    discarded=select(PlanIncorporation.lead_id).where(PlanIncorporation.discarded.is_(True))
    total = db.scalar(select(func.count()).select_from(Lead).where(*lead_scope,~Lead.id.in_(discarded)))
    excluded = db.scalar(select(func.count()).select_from(Lead).where(*lead_scope,Lead.id.in_(discarded)))
    attributed = db.scalar(select(func.count()).select_from(PlanIncorporation).join(Lead).join(PlanDecision).where(
        PlanDecision.plan_id == plan.id, PlanIncorporation.discarded.is_(False), *lead_scope))
    run_scope = (PlanDecision.plan_id == plan.id, RoutineRun.user_id == plan.user_id,
                 RoutineRun.started_at >= start, RoutineRun.started_at < end)
    statuses = dict(db.execute(select(RoutineRun.status, func.count()).join(PlanDecision, PlanDecision.run_id == RoutineRun.id).where(*run_scope).group_by(RoutineRun.status)).all())
    attempt_scope = (PlanDecision.plan_id == plan.id, WorkAttempt.user_id == plan.user_id)
    operations = db.scalar(select(func.count()).select_from(ProviderOperation).join(WorkAttempt).join(PlanDecision, PlanDecision.run_id == WorkAttempt.run_id).where(
        *attempt_scope, ProviderOperation.started_at >= start, ProviderOperation.started_at < end))
    investigated = db.scalar(select(func.count(func.distinct(WorkAttempt.item_id))).select_from(WorkAttempt).join(PlanDecision, PlanDecision.run_id == WorkAttempt.run_id).where(
        *attempt_scope, WorkAttempt.kind == 'batch', WorkAttempt.started_at >= start, WorkAttempt.started_at < end))
    pending = db.scalar(select(func.count()).select_from(ResearchBatchItem).join(ResearchBatch).join(Lead).where(
        ResearchBatch.user_id == plan.user_id, Lead.user_id == plan.user_id, Lead.demo.is_(False),
        ResearchBatch.status.in_(['pending','running','paused']), ResearchBatchItem.status.in_(['pending','running'])))
    deferred = db.scalar(select(func.count()).select_from(PlanDecision).where(PlanDecision.plan_id == plan.id,
        PlanDecision.action == 'deferred', PlanDecision.at >= start, PlanDecision.at < end))
    return dict(day=label, from_at=start, to_at=end, timezone=plan.timezone, incorporated=total, plan_incorporated=attributed,
        other_incorporated=total-attributed, discarded_excluded=excluded, runs=sum(statuses.values()), completed=statuses.get('completed',0), finished=sum(n for s,n in statuses.items() if s not in ACTIVE),
        running=sum(n for s,n in statuses.items() if s in ACTIVE), statuses=statuses, deferred=deferred,
        investigations_started=investigated, investigations_pending=pending, operations=operations)


def decision(db, plan, action, reason, now, details=None, key=None, run=None):
    cfg = config(plan)
    key = key or str(uuid4())
    existing = db.scalar(select(PlanDecision).where(PlanDecision.plan_id == plan.id, PlanDecision.key == key))
    if existing: return existing
    row = PlanDecision(plan_id=plan.id, key=key, at=now, version=plan.version, action=action, reason=reason,
        details_json=dump({'target':cfg.daily_target, 'timezone':plan.timezone, **(details or {})}), run_id=run.id if run else None)
    db.add(row); db.flush()
    return row


def describe(db, plan, now, day=None):
    if not plan: return dict(state='disabled', version=0, config=None, progress=None, history=[], reason='Configure o plano antes de ativar.')
    stats = progress(db, plan, now, day)
    events = db.scalars(select(PlanDecision).where(PlanDecision.plan_id == plan.id, PlanDecision.at >= stats['from_at'], PlanDecision.at < stats['to_at']).order_by(PlanDecision.at.desc(), PlanDecision.id).limit(201)).all()
    targets = sorted({json.loads(e.details_json).get('target') for e in events if json.loads(e.details_json).get('target') is not None})
    return dict(id=plan.id, state=plan.state, version=plan.version, config=config(plan).model_dump(), timezone=plan.timezone,
        reason=plan.reason, progress=stats, next_at=plan.next_check_at if plan.state=='active' else None, next_is_estimate=True,
        historical_targets=targets, history_truncated=len(events)>200,
        history=[dict(at=e.at, action=e.action, reason=e.reason, version=e.version, run_id=e.run_id, details=json.loads(e.details_json)) for e in events[:200]])


@router.get('')
def get_plan(day: date | None=None, user=Depends(current_user), db=Depends(get_db)):
    limiter.check('plan-read:'+user.id, 60, 60)
    now = int(time.time()); today = datetime.fromtimestamp(now, ZoneInfo(user.timezone)).date()
    if day and not today-timedelta(days=366) <= day <= today: raise HTTPException(422, 'Escolha um dia nos últimos 366 dias.')
    return describe(db, owned(db,user), now, day)


@router.get('/options')
def options(user=Depends(current_user), db=Depends(get_db)):
    from .main import radar_provider
    limiter.check('plan-options:'+user.id, 30, 60)
    rows = db.scalars(select(RadarSavedSearch).where(RadarSavedSearch.user_id==user.id).order_by(RadarSavedSearch.name).limit(201)).all()
    return dict(items=[member_info(s,radar_provider) for s in rows[:200]], truncated=len(rows)>200)


@router.put('')
def configure(data: Configure, user=Depends(current_user), db=Depends(get_db)):
    limiter.check('plan-config:'+user.id, 20, 60); fence(db)
    plan = owned(db,user)
    if (plan.version if plan else 0) != data.version: raise HTTPException(409,'Plano alterado. Atualize a tela.')
    if plan and plan.state=='active': raise HTTPException(409,'Pause o plano antes de alterar limites ou pesquisas.')
    ids = [m.saved_search_id for m in data.config.members]
    rows = db.scalars(select(RadarSavedSearch).where(RadarSavedSearch.user_id==user.id, RadarSavedSearch.id.in_(ids))).all()
    if len(rows)!=len(ids): raise HTTPException(404,'Pesquisa indisponível nesta conta.')
    from .routines import config_of
    locations = {location_label(config_of(s).get('intent') or json.loads(s.query_json).get('commercial_intent') or {}) for s in rows}
    if set(data.config.locations)!=locations: raise HTTPException(422,'Selecione exatamente os locais das pesquisas participantes.')
    if not plan:
        plan = ProspectingPlan(user_id=user.id,config_json=dump(data.config.model_dump()),timezone=user.timezone)
        db.add(plan); db.flush()
    else:
        plan.config_json=dump(data.config.model_dump()); plan.timezone=user.timezone
        plan.authorization=''; plan.reason='Configuração salva; autorização pendente.'
        db.execute(delete(PlanMember).where(PlanMember.plan_id==plan.id))
    for member in data.config.members: db.add(PlanMember(plan_id=plan.id,**member.model_dump()))
    db.flush(); decision(db,plan,'configure','Configuração salva sem ativar.',int(time.time()),{'config':data.config.model_dump()})
    db.commit(); return describe(db,plan,int(time.time()))


@router.get('/preview')
def get_preview(user=Depends(current_user), db=Depends(get_db)):
    from .main import radar_provider
    limiter.check('plan-preview:'+user.id,30,60)
    plan=owned(db,user)
    if not plan: raise HTTPException(409,'Configure o plano primeiro.')
    return preview(db,plan,user,radar_provider)


@router.post('/control')
def control(data: Control, user=Depends(current_user), db=Depends(get_db)):
    from .main import radar_provider
    from .routines import stop_run
    limiter.check('plan-control:'+user.id,20,60); fence(db)
    plan=owned(db,user); now=int(time.time())
    if not plan or plan.version!=data.version: raise HTTPException(409,'Plano alterado. Atualize a tela.')
    if data.action in ('activate','resume'):
        expected='paused' if data.action=='resume' else 'disabled'
        if plan.state!=expected: raise HTTPException(409,'Estado do plano incompatível com a ação.')
        check=preview(db,plan,user,radar_provider)
        if not data.confirm or data.preview_token!=check['token']: raise HTTPException(409,'Revise a prévia atual e confirme a autorização.')
        if check['blockers']: raise HTTPException(409,'Resolva os bloqueios apresentados na prévia.')
        plan.authorization=check['token']; plan.state='active'; plan.next_check_at=now
        plan.reason='Autorizado; aguardando janela e capacidade do executor.'
    elif data.action=='run_now':
        if plan.state!='active': raise HTTPException(409,'Ative o plano antes de solicitar um ciclo.')
        plan.next_check_at=now; plan.reason='Ciclo solicitado; os mesmos limites e janela serão respeitados.'
    else:
        if data.action=='pause' and plan.state!='active': raise HTTPException(409,'O plano não está ativo.')
        plan.state='paused' if data.action=='pause' else 'disabled'
        plan.reason='Plano pausado.' if data.action=='pause' else 'Plano desativado; recorrências originais preservadas.'
        for run in db.scalars(select(RoutineRun).join(PlanDecision,PlanDecision.run_id==RoutineRun.id).where(
                PlanDecision.plan_id==plan.id, RoutineRun.user_id==user.id, RoutineRun.status.in_(ACTIVE))):
            stop_run(db,run,'cancelled',plan.reason,now)
            slot=db.get(ResearchExecutor,1)
            attempt=db.get(WorkAttempt,slot.token) if slot and slot.token else None
            if attempt and attempt.run_id==run.id:
                slot.token=''; slot.lease_until=0
                attempt.status='obsolete';attempt.finished_at=now
    db.flush(); decision(db,plan,data.action,plan.reason,now)
    db.commit(); return describe(db,plan,now)


def managed_searches():
    return select(PlanMember.saved_search_id).join(ProspectingPlan).where(ProspectingPlan.state.in_(['active','paused']))


def next_plan(db, now):
    return db.scalar(select(ProspectingPlan).join(User).where(User.is_active.is_(True), ProspectingPlan.state=='active',
        ProspectingPlan.next_check_at<=now).order_by(ProspectingPlan.next_check_at,ProspectingPlan.id).limit(1))


def defer(db, plan, now, reason, next_at, details=None):
    plan.next_check_at=max(now+60,next_at); plan.reason=reason
    # One explanation per reason/participant state/day, not one event per worker tick.
    day=bounds(plan.timezone,now)[0]
    digest=hashlib.sha256(dump([reason,details]).encode()).hexdigest()[:24]
    decision(db,plan,'deferred',reason,now,details,key=f'defer:{day}:{digest}')
    return None


def choose(db, plan, now, provider):
    """At most 20 members. Aggregate queries, no Intelligence report or Lead list."""
    cfg=config(plan); user=db.get(User,plan.user_id)
    check=preview(db,plan,user,provider)
    if check['token']!=plan.authorization or check['blockers']:
        return defer(db,plan,now,'Autorização ou fonte alterada; pause, revise e autorize novamente.',now+300)
    inside, boundary=operational_window(plan,now)
    if not inside: return defer(db,plan,now,'Fora dos dias ou da janela autorizados.',boundary)
    stats=progress(db,plan,now); end=bounds(plan.timezone,now)[2]
    if stats['incorporated']>=cfg.daily_target: return defer(db,plan,now,'Meta diária de novas empresas atingida.',end)
    if stats['runs']>=cfg.daily_runs: return defer(db,plan,now,'Limite diário de execuções atingido.',end)
    if stats['operations']>=cfg.daily_operations: return defer(db,plan,now,'Orçamento diário do plano esgotado.',end)
    from .consumption import HTTP_BUDGET, PROVIDER_LIMITS
    utc_day=now//86400*86400
    provider_key=getattr(provider,'name','unconfigured')
    global_used=db.scalar(select(func.count()).select_from(ProviderOperation).where(ProviderOperation.started_at>=utc_day))
    source_used=db.scalar(select(func.count()).select_from(ProviderOperation).where(ProviderOperation.started_at>=utc_day,ProviderOperation.provider==provider_key))
    available=min(HTTP_BUDGET-global_used,PROVIDER_LIMITS.get(provider_key,0)-source_used)
    if available<=0: return defer(db,plan,now,'Limite global ou da fonte indisponível; nenhum novo job criado.',utc_day+86400)
    if db.scalar(select(RoutineRun.id).where(RoutineRun.user_id==plan.user_id,RoutineRun.status.in_(ACTIVE))):
        return defer(db,plan,now,'Já existe uma rotina em execução nesta conta.',now+60)
    if db.scalar(select(SmartSearch.id).where(SmartSearch.user_id==plan.user_id,SmartSearch.status.in_(['pending','running','investigating','paused']))):
        return defer(db,plan,now,'Existe busca aberta nesta conta; aguarde ou conclua.',now+60)
    ids=[m.saved_search_id for m in cfg.members]
    history={r[0]:r[1:] for r in db.execute(select(RoutineRun.saved_search_id,func.max(RoutineRun.started_at),func.count(),
        func.sum(case((RoutineRun.started_at>=stats['from_at'],1),else_=0))).where(RoutineRun.user_id==plan.user_id,
        RoutineRun.saved_search_id.in_(ids)).group_by(RoutineRun.saved_search_id))}
    rows={s.id:s for s in db.scalars(select(RadarSavedSearch).where(RadarSavedSearch.user_id==plan.user_id,RadarSavedSearch.id.in_(ids)))}
    candidates=[]; skipped=[]; next_at=end
    for member in cfg.members:
        saved=rows[member.saved_search_id]; limits=json.loads(saved.routine_config_json)['limits']
        last,count,today=history.get(saved.id,(0,0,0))
        allowed=(last or 0)+max(cfg.cooldown_hours,limits['interval_hours'])*3600
        # At most once per search per local day, including failed/empty runs. A
        # missed target never licenses repeated exhausted queries that same day.
        why='Já executada hoje; não repetir fonte esgotada ou com falha.' if today else 'Cooldown da pesquisa.' if allowed>now else 'Limite de execuções da rotina.' if count>=limits['max_runs'] else ''
        if why:
            skipped.append(dict(id=saved.id,reason=why)); next_at=min(next_at,max(now+60,allowed)); continue
        candidates.append((member.priority,last or 0,saved,limits))
    if not candidates: return defer(db,plan,now,'Sem trabalho adicional autorizado neste momento.',next_at,{'searches':skipped})
    _,_,saved,limits=sorted(candidates,key=lambda r:(-r[0],r[1],r[2].id))[0]
    operations=min(limits['operation_limit'],limits['daily_operation_limit'],cfg.daily_operations-stats['operations'],available)
    effective={**limits,'operation_limit':operations,
        'candidate_limit':min(limits['candidate_limit'],cfg.companies_per_search,cfg.daily_target-stats['incorporated']),
        'investigation_limit':min(limits['investigation_limit'],max(0,cfg.daily_investigations-stats['investigations_started']))}
    plan.next_check_at=now+60; plan.reason='Pesquisa selecionada por prioridade, cooldown e cobertura autorizada.'
    return dict(plan=plan,saved=saved,config={**json.loads(saved.routine_config_json),'limits':effective},
        details={'saved_search_id':saved.id,'skipped':skipped,'limits':effective,'progress_before':stats},deadline=boundary)


def link_run(db, selected, run, now):
    decision(db,selected['plan'],'scheduled',selected['plan'].reason,now,selected['details'],key='run:'+run.id,run=run)
    job=db.get(SmartSearch,run.search_id) if run.search_id else None
    if job:
        job.deadline=min(job.deadline,selected['deadline'])
        info=json.loads(job.state_json);info['prospecting_plan_id']=selected['plan'].id;job.state_json=dump(info)


def record_incorporations(db, job, new_ids, entries, now):
    if not new_ids: return
    row=db.scalar(select(PlanDecision).join(RoutineRun,PlanDecision.run_id==RoutineRun.id).join(ProspectingPlan).where(
        RoutineRun.search_id==job.id,RoutineRun.user_id==job.user_id,ProspectingPlan.user_id==job.user_id))
    # An unlinked observation never attributes a search to a plan. It only
    # records explicit discard at incorporation, avoiding JSON scans of all jobs.
    valid=set(db.scalars(select(Lead.id).where(Lead.id.in_(new_ids),Lead.user_id==job.user_id,Lead.demo.is_(False))))
    existing=set(db.scalars(select(PlanIncorporation.lead_id).where(PlanIncorporation.lead_id.in_(valid))))
    groups={e['id']:e['group'] for e in entries}
    for identifier in valid-existing:
        db.add(PlanIncorporation(lead_id=identifier,decision_id=row.id if row else None,search_id=job.id,
            discarded=groups.get(identifier,'discarded')=='discarded',at=now))


def run_block(db, run, now, provider=None):
    row=db.scalar(select(PlanDecision).where(PlanDecision.run_id==run.id))
    if not row: return ''
    plan=db.get(ProspectingPlan,row.plan_id)
    if not plan or plan.user_id!=run.user_id or plan.state!='active': return 'Plano interrompido.'
    cfg=config(plan)
    if not operational_window(plan,now)[0]: return 'Janela do plano encerrada.'
    if bounds(plan.timezone,now)[0]!=bounds(plan.timezone,run.started_at)[0]: return 'Dia operacional encerrado.'
    if provider is not None:
        check=preview(db,plan,db.get(User,plan.user_id),provider)
        if check['blockers'] or check['token']!=plan.authorization: return 'Autorização do plano alterada.'
    stats=progress(db,plan,now)
    if stats['operations']>=cfg.daily_operations: return 'Orçamento diário do plano esgotado.'
    if stats['incorporated']>=cfg.daily_target: return 'Meta diária atingida; resultados preservados.'
    return ''


def guard_operation(db, attempt, now):
    if not attempt.run_id: return
    from .main import radar_provider
    from .consumption import ConsumptionLimit
    run=db.get(RoutineRun,attempt.run_id)
    if run:
        reason=run_block(db,run,now,radar_provider)
        if reason: raise ConsumptionLimit(reason)


@router.get('/suggestions')
def suggestions(user=Depends(current_user), db=Depends(get_db)):
    # Explicit user request only. The scheduler never calls the complete report.
    from .operational_intelligence import report
    limiter.check('plan-suggestions:'+user.id,6,60)
    data=report(db,user,'7','all')
    keys={'coordinates','duplicates','investigation_queue','review_pending','source_limits','limit_or_configuration'}
    return dict(window=data['window'],sample=data['coverage'],suggestions=[r for r in data['diagnostics'] if r['key'] in keys],
        small_sample=data['coverage']['companies']<30, applied=False,
        limitation='Observações de cobertura parcial; não estimam lucro, conversão nem qualidade comercial. Nenhum ajuste aplicado.')
