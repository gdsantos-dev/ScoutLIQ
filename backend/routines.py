"""Explicit, bounded recurrence over RadarSavedSearch and the existing executor."""
import hashlib
import json
import time
from typing import Literal
from uuid import NAMESPACE_URL, uuid5
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from sqlalchemy import select, func, or_
from .db import get_db
from .models import RadarSavedSearch, SmartSearch, ResearchBatch, ResearchBatchItem, Lead, LeadResearch, User
from .autonomy_models import RoutineRun, RoutineEvent, WorkAttempt, ProviderOperation
from .security import current_user, limiter
from .search_intent import Strict, Intent, SECTORS
from .commercial_fit import norm, assess
from .smart_search import validate_intent, create_search, state, describe, classify, ACTIVE

router = APIRouter(prefix='/api/operations', tags=['operations'])
RUNNING = ('running','paused')


class RoutineConfig(Strict):
    objective: Literal['prospect','refresh'] = 'prospect'
    interval_hours: int = Field(default=24, ge=24, le=720)
    task_limit: int = Field(default=20, ge=1, le=100)
    daily_task_limit: int = Field(default=40, ge=1, le=200)
    operation_limit: int = Field(default=100, ge=1, le=500)
    daily_operation_limit: int = Field(default=150, ge=1, le=1000)
    page_limit: int = Field(default=3, ge=1, le=12)
    candidate_limit: int = Field(default=100, ge=25, le=600)
    investigation_limit: int = Field(default=15, ge=0, le=50)
    cooldown_days: int = Field(default=7, ge=1, le=90)
    duration_minutes: int = Field(default=60, ge=15, le=120)
    max_runs: int = Field(default=30, ge=1, le=365)
    research_mode: Literal['web','deep'] = 'web'


class Configure(Strict):
    version: int = Field(ge=1)
    enabled: bool = False
    config: RoutineConfig


class Control(Strict):
    version: int = Field(ge=1)
    action: Literal['pause','resume','cancel','run_now']


def owned(db, identifier, user):
    saved = db.scalar(select(RadarSavedSearch).where(RadarSavedSearch.id==identifier, RadarSavedSearch.user_id==user.id))
    if not saved: raise HTTPException(404,'Pesquisa salva não encontrada.')
    return saved


def event(db, saved, action, details):
    db.add(RoutineEvent(user_id=saved.user_id, saved_search_id=saved.id, action=action, detail_json=json.dumps(details)))


def config_of(saved):
    return json.loads(saved.routine_config_json or '{}')


def usage(db, run):
    tasks = db.scalar(select(func.count()).select_from(WorkAttempt).where(WorkAttempt.run_id==run.id))
    operations = db.execute(select(ProviderOperation.provider, ProviderOperation.status, func.count())
        .join(WorkAttempt).where(WorkAttempt.run_id==run.id).group_by(ProviderOperation.provider,ProviderOperation.status)).all()
    return {'tasks':tasks, 'operations':[{'provider':p,'state':s,'count':n} for p,s,n in operations],
            'estimated_cost':None,'confirmed_cost':None,'cost_state':'unknown'}


def run_row(db, run):
    return {'id':run.id,'status':run.status,'reason':run.reason,'scheduled_at':run.scheduled_at,
            'started_at':run.started_at,'finished_at':run.finished_at,'search_id':run.search_id,'batch_id':run.batch_id,
            'result':json.loads(run.result_json),'usage':usage(db,run)}


def saved_row(db, saved):
    runs = db.scalars(select(RoutineRun).where(RoutineRun.saved_search_id==saved.id).order_by(RoutineRun.started_at.desc()).limit(5)).all()
    cfg = config_of(saved)
    return {'id':saved.id,'name':saved.name,'version':saved.version,'state':saved.routine_state,'reason':saved.routine_reason,
            'next_at':saved.routine_next_at,'last_at':saved.routine_last_at,'config':cfg.get('limits'),
            'objective':cfg.get('limits',{}).get('objective'),'intent':cfg.get('intent'),
            'runs':[run_row(db,r) for r in runs]}


@router.get('/routines')
def listing(user=Depends(current_user), db=Depends(get_db)):
    saved = db.scalars(select(RadarSavedSearch).where(RadarSavedSearch.user_id==user.id).order_by(RadarSavedSearch.created_at.desc())).all()
    return [saved_row(db,s) for s in saved if json.loads(s.query_json).get('commercial_intent')]


@router.get('/routines/{identifier}/history')
def history(identifier:str, user=Depends(current_user), db=Depends(get_db)):
    saved=owned(db,identifier,user)
    events=db.scalars(select(RoutineEvent).where(RoutineEvent.saved_search_id==saved.id).order_by(RoutineEvent.created_at.desc()).limit(100)).all()
    return [{'action':e.action,'at':e.created_at,'details':json.loads(e.detail_json)} for e in events]


def mode_required():
    from .research_worker import MODE
    if MODE!='worker': raise HTTPException(409,'Rotinas exigem o modo worker. Configure o executor antes de ativar.')


@router.put('/routines/{identifier}/configuration')
def configure(identifier:str, data:Configure, user=Depends(current_user), db=Depends(get_db)):
    mode_required()
    limiter.check('routine-config:'+user.id,20,60)
    saved=owned(db,identifier,user)
    if saved.version!=data.version: raise HTTPException(409,'Pesquisa alterada. Atualize antes de configurar.')
    if saved.monitor_enabled: raise HTTPException(409,'Desative o monitor territorial antes de configurar uma rotina comercial.')
    raw=json.loads(saved.query_json).get('commercial_intent')
    if not raw: raise HTTPException(422,'Salve uma intenção na Busca inteligente antes de configurar a rotina.')
    intent=validate_intent(Intent.model_validate(raw))
    from .main import radar_provider
    from .search_sources import capabilities, legacy_capabilities
    provider_key=getattr(radar_provider,'name','unconfigured')
    if data.enabled and data.config.objective=='prospect' and any(not (legacy_capabilities(radar_provider,intent.legacy.discovery()) if intent.legacy else capabilities(radar_provider,s,intent.location,intent.area))['supported'] for s in (intent.sectors or [''])):
        raise HTTPException(409,'A fonte configurada não cobre os setores desta intenção. A rotina não foi ativada.')
    canonical=intent.model_dump(exclude={'query'})
    for key,value in canonical.items():
        if isinstance(value,list): canonical[key]=sorted(value)
    signature=hashlib.sha256(json.dumps({'intent':canonical,'objective':data.config.objective},sort_keys=True).encode()).hexdigest()
    others=db.scalars(select(RadarSavedSearch).where(RadarSavedSearch.user_id==user.id,RadarSavedSearch.id!=saved.id,
        RadarSavedSearch.routine_state.in_(['active','paused']))).all()
    if any(config_of(s).get('signature')==signature for s in others):
        raise HTTPException(409,'Já existe uma rotina equivalente nesta conta. Edite a rotina existente.')
    if db.scalar(select(RoutineRun.id).where(RoutineRun.saved_search_id==saved.id,RoutineRun.status.in_(RUNNING))):
        raise HTTPException(409,'Cancele a execução atual antes de alterar critérios e limites.')
    before=config_of(saved)
    saved.routine_config_json=json.dumps({'limits':data.config.model_dump(),'intent':intent.model_dump(),'provider':provider_key,'signature':signature})
    saved.routine_state='active' if data.enabled else 'paused'
    saved.routine_next_at=int(time.time())+data.config.interval_hours*3600 if data.enabled else None
    saved.routine_reason=''
    event(db,saved,'configure',{'before':before,'after':config_of(saved),'enabled':data.enabled})
    db.commit()
    return saved_row(db,saved)


def stop_run(db, run, status, reason, now):
    run.status,run.reason,run.finished_at=status,reason,now
    if run.search_id:
        job=db.get(SmartSearch,run.search_id)
        if job and job.status in (*ACTIVE,'paused'):
            info=state(job);info['reason']=reason
            intent=Intent.model_validate_json(job.intent_json)
            for entry in info.get('candidates',[]):
                lead=db.get(Lead,entry['id'])
                if lead and lead.user_id==run.user_id and entry['group']!='discarded':
                    group,why=classify(lead,intent);entry.update(group=group,reason=why)
            job.state_json=json.dumps(info)
            job.status='cancelled' if status=='cancelled' else 'partial'
            job.lease_token='';job.lease_until=0;job.updated_at=now
            run.batch_id=job.batch_id
    if run.batch_id:
        batch=db.get(ResearchBatch,run.batch_id)
        if batch and batch.status!='completed':
            batch.status='cancelled';batch.completed_at=now
            for item in db.scalars(select(ResearchBatchItem).where(ResearchBatchItem.batch_id==batch.id,
                    ResearchBatchItem.status.in_(['pending','running']))).all():
                item.status='cancelled';item.lease_token='';item.lease_until=0
    finalize_run(db,run)


def finalize_run(db, run):
    """Record final counts even when a budget stops a job between worker ticks."""
    saved=db.get(RadarSavedSearch,run.saved_search_id)
    job=db.get(SmartSearch,run.search_id) if run.search_id else None
    if job:
        counters=describe(job,db,include_results=False)['counters']
        if job.batch_id:
            counters['investigated']=db.scalar(select(func.count()).select_from(ResearchBatchItem).where(
                ResearchBatchItem.batch_id==job.batch_id,ResearchBatchItem.status.in_(['done','error','skipped'])))
            info=state(job);info['investigated']=counters['investigated'];job.state_json=json.dumps(info)
        run.result_json=json.dumps(counters)
        seen=set(json.loads(saved.routine_seen_json))
        seen.update(e['id'] for e in state(job).get('candidates',[]) if e['group']=='qualified')
        saved.routine_seen_json=json.dumps(sorted(seen))
    elif run.batch_id:
        run.result_json=json.dumps(dict(db.execute(select(ResearchBatchItem.status,func.count()).where(
            ResearchBatchItem.batch_id==run.batch_id).group_by(ResearchBatchItem.status)).all()))
    saved.routine_reason=run.reason
    count=db.scalar(select(func.count()).select_from(RoutineRun).where(RoutineRun.saved_search_id==saved.id))
    if count>=json.loads(run.config_json)['limits']['max_runs'] and saved.routine_state=='active':
        saved.routine_state='completed';saved.routine_next_at=None


def cancel_saved(db, saved, reason='Rotina cancelada pelo operador.'):
    for run in db.scalars(select(RoutineRun).where(RoutineRun.saved_search_id==saved.id,RoutineRun.status.in_(RUNNING))).all():
        stop_run(db,run,'cancelled',reason,int(time.time()))


@router.post('/routines/{identifier}/control')
def control(identifier:str, data:Control, user=Depends(current_user), db=Depends(get_db)):
    mode_required()
    limiter.check('routine-control:'+user.id,30,60)
    saved=owned(db,identifier,user)
    if saved.version!=data.version: raise HTTPException(409,'Rotina alterada. Atualize antes de continuar.')
    if not config_of(saved): raise HTTPException(409,'Configure os critérios da rotina primeiro.')
    now=int(time.time())
    runs=db.scalars(select(RoutineRun).where(RoutineRun.saved_search_id==saved.id,RoutineRun.status.in_(RUNNING))).all()
    if data.action=='run_now':
        if saved.routine_state!='active': raise HTTPException(409,'Ative a rotina antes de agendar.')
        if runs: raise HTTPException(409,'Já existe uma execução aberta desta rotina.')
        last=db.scalar(select(func.max(RoutineRun.scheduled_at)).where(RoutineRun.saved_search_id==saved.id))
        saved.routine_next_at=max(now,(last or 0)+1)
    elif data.action=='cancel':
        cancel_saved(db,saved)
        saved.routine_state='cancelled';saved.routine_next_at=None
    elif data.action=='pause':
        if saved.routine_state!='active': raise HTTPException(409,'A rotina não está ativa.')
        saved.routine_state='paused'
        for run in runs:
            run.status='paused'
            job=db.get(SmartSearch,run.search_id) if run.search_id else None
            if job:
                job.status='paused';job.lease_token='';job.lease_until=0;run.batch_id=job.batch_id
            batch=db.get(ResearchBatch,run.batch_id) if run.batch_id else None
            if batch: batch.status='paused'
    else:
        if saved.routine_state!='paused': raise HTTPException(409,'A rotina não está pausada.')
        saved.routine_state='active';saved.routine_next_at=now+config_of(saved)['limits']['interval_hours']*3600
        for run in runs:
            deadline=run.started_at+json.loads(run.config_json)['limits']['duration_minutes']*60
            if deadline<=now:
                stop_run(db,run,'partial','Prazo encerrado durante a pausa.',now);continue
            run.status='running'
            job=db.get(SmartSearch,run.search_id) if run.search_id else None
            if job: job.status='investigating' if job.batch_id else 'pending'
            batch=db.get(ResearchBatch,run.batch_id) if run.batch_id else None
            if batch: batch.status='pending'
    event(db,saved,data.action,{'state':saved.routine_state,'next_at':saved.routine_next_at})
    db.commit()
    return saved_row(db,saved)


def run_for_task(db, kind, item):
    if kind=='smart': return db.scalar(select(RoutineRun).where(RoutineRun.search_id==item.id))
    if kind=='batch':
        return db.scalar(select(RoutineRun).where(or_(RoutineRun.batch_id==item.batch_id,
            RoutineRun.search_id.in_(select(SmartSearch.id).where(SmartSearch.batch_id==item.batch_id)))))
    return None


def guard_child_control(db, action, *, batch_id=None, search_id=None):
    query=select(RoutineRun)
    query=query.where(RoutineRun.search_id==search_id) if search_id else query.where(or_(RoutineRun.batch_id==batch_id,
        RoutineRun.search_id.in_(select(SmartSearch.id).where(SmartSearch.batch_id==batch_id))))
    run=db.scalar(query)
    if not run: return
    saved=db.get(RadarSavedSearch,run.saved_search_id)
    if action=='resume' and (saved.routine_state!='active' or run.status not in RUNNING):
        raise HTTPException(409,'Retome a rotina em Automações antes de continuar este trabalho.')
    if run.status in RUNNING:
        run.status={'pause':'paused','resume':'running','cancel':'cancelled'}[action]
        if action=='cancel': run.finished_at=int(time.time())


def reconcile(db, now):
    """Only called with the executor write lock; no network or implicit messages."""
    for run in db.scalars(select(RoutineRun).where(RoutineRun.status.in_(RUNNING))).all():
        saved=db.get(RadarSavedSearch,run.saved_search_id)
        user=db.get(User,run.user_id)
        cfg=json.loads(run.config_json)['limits']
        if not user or not user.is_active:
            stop_run(db,run,'cancelled','Conta indisponível.',now);continue
        from .prospecting import run_block
        from .main import radar_provider
        blocked=run_block(db,run,now,radar_provider)
        if blocked:
            stop_run(db,run,'partial',blocked,now);continue
        if now>=run.started_at+cfg['duration_minutes']*60:
            stop_run(db,run,'partial','Prazo da rotina encerrado.',now)
        job=db.get(SmartSearch,run.search_id) if run.search_id else None
        if job:
            run.batch_id=job.batch_id
            result=describe(job,db,include_results=False)
            run.result_json=json.dumps(result['counters'])
            if job.status not in (*ACTIVE,'paused'):
                run.status=job.status;run.reason=job.error or result['reason'];run.finished_at=now
                seen=set(json.loads(saved.routine_seen_json))
                seen.update(e['id'] for e in state(job).get('candidates',[]) if e['group']=='qualified')
                saved.routine_seen_json=json.dumps(sorted(seen))
        elif run.batch_id:
            batch=db.get(ResearchBatch,run.batch_id)
            if batch and batch.status in ('completed','cancelled'):
                statuses=db.execute(select(ResearchBatchItem.status,func.count()).where(ResearchBatchItem.batch_id==batch.id).group_by(ResearchBatchItem.status)).all()
                result=dict(statuses);run.result_json=json.dumps(result)
                run.status='partial' if result.get('error') else batch.status;run.finished_at=now
        if run.status=='running':
            daily=db.scalar(select(func.count()).select_from(WorkAttempt).join(RoutineRun).where(
                RoutineRun.saved_search_id==saved.id,WorkAttempt.started_at>=now//86400*86400))
            if usage(db,run)['tasks']>=cfg['task_limit'] or daily>=cfg['daily_task_limit']:
                stop_run(db,run,'partial','Orçamento de tarefas atingido; resultados preservados.',now)
        if run.status not in RUNNING:
            finalize_run(db,run)


def schedule_due(db, now, provider):
    from .prospecting import managed_searches, next_plan, choose
    saved=db.scalar(select(RadarSavedSearch).join(User).where(User.is_active.is_(True),
        RadarSavedSearch.routine_state=='active',RadarSavedSearch.routine_next_at<=now,
        ~RadarSavedSearch.id.in_(managed_searches()),
        ~RadarSavedSearch.id.in_(select(RoutineRun.saved_search_id).where(RoutineRun.status.in_(RUNNING))))
        .order_by(RadarSavedSearch.routine_next_at).limit(1))
    plan=next_plan(db,now)
    if plan and (not saved or plan.next_check_at<=saved.routine_next_at):
        selected=choose(db,plan,now,provider)
        if selected:
            return schedule_saved(db,selected['saved'],now,provider,selected)
    if not saved: return
    return schedule_saved(db,saved,now,provider)


def schedule_saved(db, saved, now, provider, planned=None):
    """The one creation path for both original recurrences and authorized plans."""
    cfg=planned['config'] if planned else config_of(saved);limits=cfg['limits']
    count=db.scalar(select(func.count()).select_from(RoutineRun).where(RoutineRun.saved_search_id==saved.id))
    if count>=limits['max_runs']:
        saved.routine_state='completed';saved.routine_next_at=None;saved.routine_reason='Limite de execuções atingido.';return
    if limits['objective']=='prospect' and cfg['provider']!=getattr(provider,'name','unconfigured'):
        saved.routine_state='blocked';saved.routine_next_at=None;saved.routine_reason='Fonte alterada. Revise e autorize a configuração.';return
    last=db.scalar(select(func.max(RoutineRun.scheduled_at)).where(RoutineRun.saved_search_id==saved.id)) if planned else None
    scheduled=max(now,(last or 0)+1) if planned else saved.routine_next_at
    run=RoutineRun(user_id=saved.user_id,saved_search_id=saved.id,scheduled_at=scheduled,started_at=now,config_json=json.dumps(cfg))
    db.add(run);db.flush()
    saved.routine_last_at=now;saved.routine_reason=''
    if not planned: saved.routine_next_at=now+limits['interval_hours']*3600
    intent=Intent.model_validate(cfg['intent'])
    if limits['objective']=='prospect':
        try:
            job=create_search(db,db.get(User,saved.user_id),intent,str(uuid5(NAMESPACE_URL,f'routine:{saved.id}:{scheduled}')),provider,now,
                {**limits,'suppress_ids':json.loads(saved.routine_seen_json),'exclude_pipeline':True,'authorized_provider':cfg['provider']})
            run.search_id=job.id
        except HTTPException:
            run.status='skipped';run.reason='Capacidade de buscas abertas atingida ou intenção indisponível.';run.finished_at=now
    else:
        leads=db.scalars(select(Lead).where(Lead.user_id==saved.user_id,Lead.demo.is_(False),Lead.contact_blocked.is_(False),
            ~Lead.stage.in_(['won','lost'])).order_by(Lead.id).limit(1000)).all()
        from .scoring import score
        candidates=[]
        for lead in leads:
            if norm(lead.city)!=norm(intent.market.city) or norm(lead.country)!=norm(intent.market.country): continue
            if intent.sectors and not any(any(t in norm(lead.category) for t in SECTORS.get(s,(s,))) for s in intent.sectors): continue
            if assess(lead)['status']=='incompatible': continue
            if classify(lead,intent)[0]=='discarded': continue
            previous=db.scalar(select(LeadResearch).where(LeadResearch.lead_id==lead.id))
            if previous and previous.checked_at>now-limits['cooldown_days']*86400: continue
            candidates.append(lead)
        candidates.sort(key=lambda lead:score(lead)['value'],reverse=True)
        selected=candidates[:min(limits['investigation_limit'],limits['task_limit'])]
        if not selected:
            run.status='completed';run.finished_at=now;run.reason='Nenhuma empresa elegível com investigação vencida.'
        else:
            batch=ResearchBatch(user_id=saved.user_id,mode=limits['research_mode'],status='pending',requested_count=len(selected))
            db.add(batch);db.flush();run.batch_id=batch.id
            for index,lead in enumerate(selected): db.add(ResearchBatchItem(batch_id=batch.id,lead_id=lead.id,position=index))
    if run.status not in RUNNING: finalize_run(db,run)
    if planned:
        from .prospecting import link_run
        link_run(db,planned,run,now)
    event(db,saved,'scheduled',{'run_id':run.id,'scheduled_at':scheduled,'next_at':saved.routine_next_at})
    return run


@router.get('/status')
def status(user=Depends(current_user), db=Depends(get_db)):
    from .worker_health import snapshot
    from .research_worker import BUDGET, MODE
    from .consumption import HTTP_BUDGET, PROVIDER_LIMITS
    from .models import ResearchExecutor
    now=int(time.time());day=now//86400*86400
    slot=db.get(ResearchExecutor,1)
    own_tasks=db.scalar(select(func.count()).select_from(WorkAttempt).where(WorkAttempt.user_id==user.id,WorkAttempt.started_at>=day))
    own_ops=db.scalar(select(func.count()).select_from(ProviderOperation).join(WorkAttempt).where(WorkAttempt.user_id==user.id,ProviderOperation.started_at>=day))
    global_ops=db.scalar(select(func.count()).select_from(ProviderOperation).where(ProviderOperation.started_at>=day))
    providers=db.execute(select(ProviderOperation.provider,func.count()).where(ProviderOperation.started_at>=day).group_by(ProviderOperation.provider)).all()
    failures=db.scalars(select(RoutineRun).where(RoutineRun.user_id==user.id,RoutineRun.status.in_(['partial','skipped']))
        .order_by(RoutineRun.started_at.desc()).limit(10)).all()
    return {'worker':snapshot(db),'mode':MODE,'tasks':{'own':own_tasks,'global_used':slot.used if slot and slot.day==now//86400 else 0,'limit':BUDGET},
            'operations':{'own':own_ops,'global_used':global_ops,'limit':HTTP_BUDGET,'providers':
                [{'provider':p,'used':dict(providers).get(p,0),'limit':limit} for p,limit in PROVIDER_LIMITS.items()]},
            'estimated_cost':None,'confirmed_cost':None,'cost_state':'unknown','resets_at':day+86400,
            'attention':[{'run_id':r.id,'reason':r.reason,'saved_search_id':r.saved_search_id} for r in failures]}
