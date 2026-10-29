import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo
import pytest
from sqlalchemy import select, func, event, update
from backend import main, research_worker as worker, consumption
from backend.db import SessionLocal, engine
from backend.models import Lead, User, RadarSavedSearch, ResearchExecutor, SmartSearch, Session
from backend.autonomy_models import RoutineRun, WorkAttempt, ProviderOperation
from backend.prospecting_models import ProspectingPlan, PlanDecision, PlanIncorporation
from backend.prospecting import bounds, operational_window, progress
from test_operational_autonomy import create, Source, drain


@pytest.fixture
def setup(auth, monkeypatch):
    now=int(datetime.now(ZoneInfo('America/Sao_Paulo')).replace(hour=12,minute=0,second=0,microsecond=0).timestamp())
    monkeypatch.setattr(time,'time',lambda:now)
    monkeypatch.setattr(worker,'MODE','worker')
    monkeypatch.setattr(consumption,'PROVIDER_LIMITS',{**consumption.PROVIDER_LIMITS,'controlled-autonomy':500})
    row,source=create(auth,monkeypatch,Source(verified=True),investigation_limit=0)
    source.search_page=consumption.metered(source.name)(source.search_page)
    return row,source,now


def save(auth,row,**changes):
    place=next(o['location'] for o in auth.get('/api/operations/plan/options').json()['items'] if o['id']==row['id'])
    payload=dict(daily_target=50,members=[dict(saved_search_id=row['id'],priority=1)],locations=[place],
        weekdays=list(range(7)),window_start='00:00',window_end='23:59',daily_runs=4,companies_per_search=25,
        daily_investigations=0,daily_operations=50,cooldown_hours=24)
    payload.update(changes)
    old=auth.get('/api/operations/plan').json()
    response=auth.put('/api/operations/plan',json={'version':old['version'],'config':payload})
    assert response.status_code==200,response.text
    return response.json()


def act(auth,action,confirmed=True,**patch):
    row=auth.get('/api/operations/plan').json()
    preview=auth.get('/api/operations/plan/preview').json()
    return auth.post('/api/operations/plan/control',json=dict(version=row['version'],action=action,
        confirm=confirmed,preview_token=preview['token'],**patch))


def activate(auth):
    response=act(auth,'activate');assert response.status_code==200,response.text
    return response.json()


def test_disabled_creation_and_explicit_current_preview(setup,auth):
    row,source,_=setup
    assert auth.get('/api/operations/plan').json()['state']=='disabled'
    plan=save(auth,row)
    assert plan['state']=='disabled' and source.calls==0
    assert act(auth,'activate',False).status_code==409
    assert auth.post('/api/operations/plan/control',json={'version':plan['version'],'action':'activate','confirm':True,'preview_token':'stale'}).status_code==409
    assert activate(auth)['state']=='active'
    assert source.calls==0  # opening, configuring and authorizing never call a provider


@pytest.mark.parametrize('target',[25,50,75,100])
def test_configurable_goal_and_first_canonical_incorporation(setup,auth,target):
    row,source,_=setup; save(auth,row,daily_target=target);activate(auth)
    drain(source)
    result=auth.get('/api/operations/plan').json()
    assert result['progress']['incorporated']==1
    assert result['progress']['plan_incorporated']==1
    assert result['progress']['runs']==1
    assert result['config']['daily_target']==target
    assert source.calls==1
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(PlanIncorporation))==1
        assert db.scalar(select(func.count()).select_from(RoutineRun))==1


def test_manual_and_absorption_origins_count_once_demo_and_existing_do_not(setup,auth,lead_data):
    row,source,now=setup
    lead=auth.post('/api/leads',json=lead_data);assert lead.status_code==201
    with SessionLocal() as db:
        user=db.scalar(select(User))
        db.add(Lead(user_id=user.id,name='Demo',category='Cafeteria',city='Recife',country='BR',latitude=-8,longitude=-34,demo=True,created_at=now))
        db.add(Lead(user_id=user.id,name='Absorvida',category='Cafeteria',city='Recife',country='BR',latitude=-8,longitude=-34,source='absorption',created_at=now))
        db.commit()
    save(auth,row);activate(auth);drain(source)
    result=auth.get('/api/operations/plan').json()['progress']
    assert result['incorporated']==3 and result['plan_incorporated']==1
    assert result['other_incorporated']==2
    # New plan never retroactively claims prior canonical companies.
    act(auth,'disable')
    with SessionLocal() as db:
        db.get(RadarSavedSearch,row['id']).routine_next_at=now+1;db.commit()
    drain(source)  # previous identity remains canonical
    assert auth.get('/api/operations/plan').json()['progress']['plan_incorporated']==1


def test_goal_reached_by_other_ingress_prevents_new_work(setup,auth,lead_data):
    row,source,_=setup; auth.post('/api/leads',json=lead_data)
    save(auth,row,daily_target=1);activate(auth)
    assert worker.claim() is None
    result=auth.get('/api/operations/plan').json()
    assert result['progress']['runs']==0 and 'Meta diária' in result['reason'] and source.calls==0


def test_no_new_results_exhausts_only_authorized_search(setup,auth):
    row,source,_=setup
    from backend.providers import DiscoveryBatch
    source.search_page=lambda *args:DiscoveryBatch(provider=source.name,location_label='Recife',results=[],scanned=0,complete=True)
    save(auth,row);activate(auth);drain(source)
    assert act(auth,'run_now').status_code==200
    assert worker.claim() is None
    report=auth.get('/api/operations/plan').json()
    assert report['progress']['runs']==1 and report['progress']['incorporated']==0
    assert 'Sem trabalho adicional' in report['reason']


def test_pause_fences_inflight_resume_disable_keep_history_and_saved_config(setup,auth):
    row,source,_=setup; save(auth,row);activate(auth)
    with SessionLocal() as db: before=db.get(RadarSavedSearch,row['id']).routine_config_json
    task=worker.claim();assert task
    assert act(auth,'pause').status_code==200
    assert not worker.execute(task,provider=source)
    assert act(auth,'resume',False).status_code==409
    assert act(auth,'resume').status_code==200
    assert worker.claim() is None  # cooldown; no replacement of a cancelled run
    assert act(auth,'disable').status_code==200
    with SessionLocal() as db:
        assert db.get(RadarSavedSearch,row['id']).routine_config_json==before
        assert db.scalar(select(func.count()).select_from(RoutineRun))==1
        assert db.scalar(select(func.count()).select_from(PlanDecision))>=4


def test_two_workers_one_plan_one_canonical_job_and_restart_recovery(setup,auth,monkeypatch):
    row,source,now=setup;save(auth,row);activate(auth)
    with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(lambda _:worker.claim(),range(2)))
    tasks=[x for x in results if x];assert len(tasks)==1
    original=tasks[0]
    monkeypatch.setattr(time,'time',lambda:now+worker.LEASE+1)
    reclaimed=worker.claim();assert reclaimed and reclaimed['id']==original['id']
    assert not worker.execute(original,provider=source)
    assert worker.execute(reclaimed,provider=source)
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(RoutineRun))==1
        assert db.scalar(select(func.count()).select_from(PlanDecision).where(PlanDecision.action=='scheduled'))==1
        assert db.scalar(select(func.count()).select_from(PlanIncorporation))==1


def test_operation_budget_reserved_atomically_for_plan(setup,auth):
    row,source,_=setup;save(auth,row,daily_operations=1);activate(auth)
    task=worker.claim();assert task
    def reserve():
        try:
            with consumption.work_scope(task['token']): return consumption.reserve(source.name)
        except consumption.ConsumptionLimit: return None
    with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(lambda _:reserve(),range(2)))
    assert sum(x is not None for x in results)==1
    assert worker.execute(task,provider=source)
    assert source.calls==0  # reservation exhausted before the adapter executes
    act(auth,'run_now');assert worker.claim() is None
    report=auth.get('/api/operations/plan').json()
    assert report['progress']['operations']==1
    assert 'Orçamento' in report['reason'] and report['progress']['incorporated']<50


def test_unavailable_provider_and_global_limit_do_not_create_job(setup,auth,monkeypatch):
    row,source,_=setup;save(auth,row);activate(auth)
    monkeypatch.setattr(main,'radar_provider',None)
    assert worker.claim() is None
    assert auth.get('/api/operations/plan').json()['progress']['runs']==0
    monkeypatch.setattr(main,'radar_provider',source)
    monkeypatch.setattr(consumption,'PROVIDER_LIMITS',{source.name:0})
    act(auth,'pause');assert act(auth,'resume').status_code==200
    assert worker.claim() is None
    assert auth.get('/api/operations/plan').json()['progress']['runs']==0


def test_disabled_routine_not_enabled_and_changed_config_requires_new_consent(setup,auth):
    row,source,_=setup;save(auth,row)
    with SessionLocal() as db:
        saved=db.get(RadarSavedSearch,row['id']);saved.routine_state='paused';db.commit()
    assert act(auth,'activate').status_code==409
    with SessionLocal() as db:
        assert db.get(RadarSavedSearch,row['id']).routine_state=='paused'
        db.get(RadarSavedSearch,row['id']).routine_state='active';db.commit()
    stale=auth.get('/api/operations/plan/preview').json()['token']
    with SessionLocal() as db:
        saved=db.get(RadarSavedSearch,row['id']);data=json.loads(saved.routine_config_json)
        data['limits']['operation_limit']=30;saved.routine_config_json=json.dumps(data);db.commit()
    plan=auth.get('/api/operations/plan').json()
    assert auth.post('/api/operations/plan/control',json=dict(version=plan['version'],action='activate',confirm=True,preview_token=stale)).status_code==409


def test_location_scope_dto_and_account_isolation(setup,auth):
    row,source,_=setup;plan=save(auth,row)
    bad={**plan['config'],'locations':['Outro local, BR']}
    assert auth.put('/api/operations/plan',json=dict(version=plan['version'],config=bad)).status_code==422
    assert auth.put('/api/operations/plan',json=dict(version=plan['version'],config=plan['config'],user_id='foreign')).status_code==422
    with SessionLocal() as db:
        user=User(email='other@example.test',password_hash='not-a-login');db.add(user);db.flush()
        foreign=RadarSavedSearch(user_id=user.id,name='Privada');db.add(foreign);db.commit();identifier=foreign.id
    bad={**plan['config'],'members':[dict(saved_search_id=identifier,priority=1)]}
    assert auth.put('/api/operations/plan',json=dict(version=plan['version'],config=bad)).status_code==404
    assert identifier not in str(auth.get('/api/operations/plan/options').json())


def test_daily_limit_and_cooldown(setup,auth,monkeypatch):
    row,source,now=setup;save(auth,row,daily_runs=1,cooldown_hours=72);activate(auth);drain(source)
    act(auth,'run_now');assert worker.claim() is None
    assert 'Limite diário' in auth.get('/api/operations/plan').json()['reason']
    with SessionLocal() as db:
        db.execute(update(Session).values(expires=now+4*86400));db.commit()
    monkeypatch.setattr(time,'time',lambda:now+86400)
    login=auth.post('/api/auth/login',json={'email':'test@example.com','password':'testing-password-123!'})
    assert login.status_code==200,login.text
    auth.headers['X-CSRF-Token']=login.json()['csrf']
    assert worker.claim() is None
    assert 'Sem trabalho' in auth.get('/api/operations/plan').json()['reason']
    history=auth.get('/api/operations/plan',params={'day':datetime.fromtimestamp(now,ZoneInfo('America/Sao_Paulo')).date().isoformat()}).json()
    assert history['progress']['runs']==1 and history['historical_targets']==[50]


def test_window_end_stops_inflight_and_next_time_is_not_guaranteed(setup,auth,monkeypatch):
    row,source,now=setup;save(auth,row,window_start='11:00',window_end='13:00');activate(auth)
    task=worker.claim();assert task
    monkeypatch.setattr(time,'time',lambda:now+7200)
    with consumption.work_scope(task['token']),pytest.raises(consumption.ConsumptionLimit): consumption.reserve(source.name)
    worker.claim()
    report=auth.get('/api/operations/plan').json()
    assert report['next_is_estimate'] and report['progress']['running']==0


def test_targeted_aggregates_do_not_load_companies_or_call_intelligence(setup,auth,monkeypatch):
    row,source,_=setup;save(auth,row);activate(auth)
    from backend import operational_intelligence
    monkeypatch.setattr(operational_intelligence,'report',lambda *a,**kw:pytest.fail('Scheduler used full report'))
    queries=[]
    def capture(conn,cursor,statement,*args): queries.append(statement)
    event.listen(engine,'before_cursor_execute',capture)
    try: task=worker.claim()
    finally: event.remove(engine,'before_cursor_execute',capture)
    assert task
    assert not any('SELECT leads.id,' in q for q in queries)
    assert len(queries)<160


def test_suggestions_have_evidence_no_auto_adjustment(setup,auth):
    row,source,_=setup;plan=save(auth,row)
    report=auth.get('/api/operations/plan/suggestions')
    assert report.status_code==200,report.text
    data=report.json()
    assert data['small_sample'] and not data['applied'] and data['suggestions']==[]
    assert auth.get('/api/operations/plan').json()['version']==plan['version']


def test_local_day_dst_is_calendar_day():
    now=int(datetime(2026,3,8,12,tzinfo=ZoneInfo('America/New_York')).timestamp())
    _,start,end=bounds('America/New_York',now)
    assert end-start==23*3600


def test_two_authorized_locations_general_search_priority_and_neutral_fallback(setup,auth):
    row,source,_=setup
    source.general_capabilities=lambda:source.capabilities('')
    intent={**row['intent'],'market':{**row['intent']['market'],'city':'Olinda'},'sectors':[],'search_mode':'general','unresolved':[]}
    response=auth.post('/api/radar/saved-searches',json={'name':'Geral Olinda','query':{'location':'Olinda','country':'BR','category':'','commercial_intent':intent}})
    assert response.status_code==201,response.text
    other=response.json()
    response=auth.put('/api/operations/routines/'+other['id']+'/configuration',json={'version':other['version'],'enabled':True,'config':row['config']})
    assert response.status_code==200,response.text
    opts=auth.get('/api/operations/plan/options').json()['items']
    save(auth,row,members=[{'saved_search_id':row['id'],'priority':1},{'saved_search_id':other['id'],'priority':5}],locations=list({o['location'] for o in opts}))
    activate(auth)
    first=worker.claim();assert first
    with SessionLocal() as db:
        job=db.get(SmartSearch,first['id']);data=json.loads(job.intent_json)
        assert data['sectors']==[] and data['market']['city']=='Olinda'
        assert len(json.loads(job.state_json)['coverage'])==1
    assert worker.execute(first,provider=source)
    drain(source);act(auth,'run_now');second=worker.claim();assert second
    with SessionLocal() as db:
        data=json.loads(db.get(SmartSearch,second['id']).intent_json)
        assert data['sectors']==['odontologia'] and data['market']['city'].lower()=='recife'
    assert worker.execute(second,provider=source)
    drain(source)
    result=auth.get('/api/operations/plan').json()['progress']
    assert result['runs']==2 and result['plan_incorporated']==1  # repeated provider identity


def test_planned_cap_applies_even_when_adapter_returns_too_many(setup,auth):
    row,source,_=setup
    from backend.providers import DiscoveryBatch, DiscoveryResult
    from backend.schemas import LeadInput
    source.search_page=lambda *args:DiscoveryBatch(provider=source.name,location_label='Recife',results=[DiscoveryResult(source_id=f'cap-{i}',lead=LeadInput(
        name=f'Clínica {i}',category='Clínica odontológica',city='Recife',country='BR',latitude=-8,longitude=-34,address=f'Rua {i}')) for i in range(6)],scanned=6,complete=True)
    save(auth,row,companies_per_search=2);activate(auth);drain(source)
    result=auth.get('/api/operations/plan').json()['progress']
    assert result['incorporated']==2 and result['plan_incorporated']==2


def test_existing_search_blocks_plan_without_cancelling_it(setup,auth):
    row,source,now=setup
    from backend.smart_search import create_search
    from backend.search_intent import Intent
    with SessionLocal() as db:
        user=db.scalar(select(User));job=create_search(db,user,Intent.model_validate(row['intent']),str(uuid4()),source,now)
        db.commit();identifier=job.id
    save(auth,row);activate(auth)
    task=worker.claim();assert task and task['id']==identifier
    assert auth.get('/api/operations/plan').json()['progress']['runs']==0


def test_claim_at_budget_exhaustion_does_not_add_decisions_in_loop(setup,auth,monkeypatch):
    row,source,now=setup;save(auth,row);activate(auth)
    with SessionLocal() as db:
        slot=db.get(ResearchExecutor,1);slot.day=now//86400;slot.used=worker.BUDGET;db.commit()
        before=db.scalar(select(func.count()).select_from(PlanDecision))
    for _ in range(3): assert worker.claim() is None
    with SessionLocal() as db: assert db.scalar(select(func.count()).select_from(PlanDecision))==before


def test_suggestions_with_observed_backlog_keep_period_sample_and_score(setup,auth,lead_data):
    row,source,_=setup
    company=auth.post('/api/leads',json=lead_data).json()
    from backend.models import ResearchBatch,ResearchBatchItem
    with SessionLocal() as db:
        lead=db.get(Lead,company['id']);before=lead.score_criteria_json
        batch=ResearchBatch(user_id=lead.user_id,mode='web',status='pending',requested_count=1);db.add(batch);db.flush()
        db.add(ResearchBatchItem(batch_id=batch.id,lead_id=lead.id,position=0));db.commit()
    save(auth,row)
    response=auth.get('/api/operations/plan/suggestions');assert response.status_code==200,response.text
    report=response.json();suggestion=next(s for s in report['suggestions'] if s['key']=='investigation_queue')
    assert suggestion['count']==1 and suggestion['from_at']<suggestion['to_at'] and suggestion['population']
    assert report['small_sample'] and not report['applied']
    with SessionLocal() as db: assert db.get(Lead,company['id']).score_criteria_json==before


def test_plan_requires_authentication_and_csrf(client,auth,setup):
    row,_,_=setup;plan=save(auth,row)
    auth.headers.pop('X-CSRF-Token')
    assert auth.post('/api/operations/plan/control',json={'version':plan['version'],'action':'activate','confirm':True}).status_code==403
    client.cookies.clear()
    assert client.get('/api/operations/plan').status_code==401


@pytest.mark.parametrize('patch',[
    {'daily_operations':0},{'daily_operations':1001},{'weekdays':[]},{'weekdays':[0,0]},
    {'window_start':'21:00','window_end':'08:00'},{'cooldown_hours':0},{'daily_runs':1000},
    {'companies_per_search':False},{'daily_investigations':-1}])
def test_backend_rejects_invalid_limits(setup,auth,patch):
    row,_,_=setup;plan=save(auth,row)
    response=auth.put('/api/operations/plan',json={'version':plan['version'],'config':{**plan['config'],**patch}})
    assert response.status_code==422,response.text


def test_plans_are_fair_between_accounts_and_keep_separate_progress(setup,auth):
    row,source,now=setup;save(auth,row);activate(auth)
    from backend.prospecting_models import PlanMember
    from backend.prospecting import preview
    with SessionLocal() as db:
        first=db.scalar(select(ProspectingPlan));cfg=json.loads(first.config_json)
        user=User(email='second-plan@example.test',password_hash='not-for-login');db.add(user);db.flush()
        saved=db.get(RadarSavedSearch,row['id'])
        other=RadarSavedSearch(user_id=user.id,name='Second account',query_json=saved.query_json,routine_config_json=saved.routine_config_json,routine_state='active',routine_next_at=now+86400)
        db.add(other);db.flush();cfg['members']=[{'saved_search_id':other.id,'priority':1}]
        plan=ProspectingPlan(user_id=user.id,timezone=user.timezone,config_json=json.dumps(cfg),state='active',next_check_at=now)
        db.add(plan);db.flush();db.add(PlanMember(plan_id=plan.id,saved_search_id=other.id,priority=1));db.flush()
        plan.authorization=preview(db,plan,user,source)['token'];db.commit()
    drain(source)
    with SessionLocal() as db:
        rows=db.execute(select(RoutineRun.user_id,func.count()).group_by(RoutineRun.user_id)).all()
        assert len(rows)==2 and all(n==1 for _,n in rows)
    assert auth.get('/api/operations/plan').json()['progress']['plan_incorporated']==1


def test_discarded_candidates_are_not_goal_credit_and_keep_radar_record(setup,auth):
    row,source,_=setup
    original=source.search_page
    def response(*args):
        result=original(*args)
        result.results[0].lead.name='Starbucks Recife'
        return result
    source.search_page=response
    save(auth,row);activate(auth);drain(source)
    stats=auth.get('/api/operations/plan').json()['progress']
    assert stats['incorporated']==stats['plan_incorporated']==0
    assert stats['discarded_excluded']==1
    with SessionLocal() as db: assert db.scalar(select(func.count()).select_from(Lead))==1


def test_deleting_routine_cannot_reset_today_plan_budget(setup,auth,monkeypatch):
    row,source,now=setup;save(auth,row,daily_runs=1);activate(auth);drain(source)
    assert act(auth,'disable').status_code==200
    response=auth.delete('/api/radar/saved-searches/'+row['id'])
    assert response.status_code==409,response.text
    stats=auth.get('/api/operations/plan').json()['progress']
    assert stats['runs']==1 and stats['operations']==1
    monkeypatch.setattr(time,'time',lambda:now+86400)
    login=auth.post('/api/auth/login',json={'email':'test@example.com','password':'testing-password-123!'})
    assert login.status_code==200
    auth.headers['X-CSRF-Token']=login.json()['csrf']
    assert auth.delete('/api/radar/saved-searches/'+row['id']).status_code==200


@pytest.mark.parametrize('size',[1000,10000])
def test_plan_progress_volume_uses_bounded_sql(setup,auth,size):
    from sqlalchemy import insert
    from pathlib import Path
    row,_,now=setup;save(auth,row)
    with SessionLocal() as db:
        user=db.scalar(select(User))
        db.execute(insert(Lead),[dict(user_id=user.id,name=f'Volume {i}',category='Cafeteria',city='Recife',country='BR',latitude=-8,longitude=-34,created_at=now) for i in range(size)])
        db.commit();plan=db.scalar(select(ProspectingPlan))
        queries=[]
        def capture(conn,cursor,statement,*args):queries.append(statement)
        event.listen(engine,'before_cursor_execute',capture)
        started=time.perf_counter()
        try: data=progress(db,plan,now)
        finally: event.remove(engine,'before_cursor_execute',capture)
        elapsed=time.perf_counter()-started
        assert data['incorporated']==size and len(queries)<=12
        assert not any('SELECT leads.id,' in q for q in queries)
        folder=Path('artifacts');folder.mkdir(exist_ok=True)
        (folder/f'planning-volume-{size}.json').write_text(json.dumps(dict(companies=size,queries=len(queries),seconds=round(elapsed,4),providers=0)),encoding='utf-8')
