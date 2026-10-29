import json
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import pytest
from sqlalchemy import select, func, delete
from backend import main, research_worker as worker, consumption
from backend.db import SessionLocal
from backend.models import RadarSavedSearch, ResearchExecutor, SmartSearch, Lead, LeadResearch, ResearchBatchItem, User
from backend.autonomy_models import RoutineRun, RoutineEvent, WorkAttempt, ProviderOperation, WorkerHeartbeat
from backend.providers import DiscoveryBatch, DiscoveryResult
from backend.schemas import LeadInput
from backend.search_intent import interpret
from backend.worker_health import beat, snapshot
from backend.routines import RoutineConfig


class Source:
    name='controlled-autonomy'
    def __init__(self,verified=False): self.calls=0;self.verified=verified
    def capabilities(self,sector): return {'supported':True,'pagination':True,'coverage':'Synthetic test','reason':''}
    def search_page(self,query,offset,limit):
        self.calls+=1
        lead=LeadInput(name='Clínica Autonomia QA',category='Clínica odontológica',city='Recife',country='BR',
            address='Rua QA 10',latitude=-8.05,longitude=-34.9,phone='5581999999999',website_status='none' if self.verified else 'unknown',
            instagram='https://instagram.com/example' if self.verified else '',instagram_active=self.verified)
        return DiscoveryBatch(provider=self.name,location_label='Recife',results=[DiscoveryResult(source_id='autonomy-qa',lead=lead)],scanned=1,complete=True)


class Researcher:
    calls=0
    def research(self,lead,locale):
        self.calls+=1
        return {'status':'confirmed','provider':'controlled','website_url':'https://example.org','website_status':'poor',
                'checked_at':int(time.time()),'page':{'pages_checked':1,'quality_score':40,'forms':1}}


@pytest.fixture(autouse=True)
def configured_worker(monkeypatch):
    monkeypatch.setattr(worker,'MODE','worker')
    with SessionLocal() as db: db.execute(delete(WorkerHeartbeat));db.commit()


def create(auth,monkeypatch,source=None,**limits):
    source=source or Source()
    monkeypatch.setattr(main,'radar_provider',source)
    intent=interpret('Clínicas odontológicas em Recife, Brasil',25).model_dump()
    created=auth.post('/api/radar/saved-searches',json={'name':'Rotina '+str(uuid4()),'query':
        {'location':'Recife','country':'BR','category':'dentista','commercial_intent':intent}})
    assert created.status_code==201,created.text
    saved=created.json()
    configured=auth.put('/api/operations/routines/'+saved['id']+'/configuration',json={
        'version':saved['version'],'enabled':True,'config':{**RoutineConfig().model_dump(),**limits}})
    assert configured.status_code==200,configured.text
    return configured.json(),source


def action(auth,row,verb):
    result=auth.post('/api/operations/routines/'+row['id']+'/control',json={'version':row['version'],'action':verb})
    assert result.status_code==200,result.text
    return result.json()


def current(auth,identifier):
    return next(r for r in auth.get('/api/operations/routines').json() if r['id']==identifier)


def drain(source,researcher=None):
    for _ in range(30):
        with SessionLocal() as db:
            db.get(ResearchExecutor,1).next_at=0;db.commit()
        task=worker.claim()
        if not task: return
        worker.execute(task,provider=source,researcher=researcher or Researcher())
    pytest.fail('Routine exceeded bounded fixture loop')


def test_recurring_saved_intent_runs_once_per_slot_and_suppresses_seen(auth,monkeypatch):
    row,source=create(auth,monkeypatch,Source(verified=True))
    assert worker.claim() is None  # no implicit run on configuration
    row=action(auth,row,'run_now')
    task=worker.claim();assert task['kind']=='smart'
    assert worker.claim() is None  # one global executor
    assert worker.execute(task,provider=source)
    drain(source)
    first=current(auth,row['id'])
    assert len(first['runs'])==1 and first['runs'][0]['result']['qualified']==1
    scheduled=action(auth,first,'run_now')
    assert scheduled['next_at']>first['runs'][0]['scheduled_at']
    later=scheduled['next_at']
    monkeypatch.setattr(time,'time',lambda:later)
    drain(source)
    second=current(auth,row['id'])
    assert len(second['runs'])==2
    assert sum(r['result'].get('qualified',0) for r in second['runs'])==1
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Lead))==1
        assert len(json.loads(db.get(RadarSavedSearch,row['id']).routine_seen_json))==1
    assert source.calls==2


def test_pause_and_cancel_fence_inflight_work_and_do_not_resume_via_child(auth,monkeypatch):
    row,source=create(auth,monkeypatch)
    row=action(auth,row,'run_now');task=worker.claim()
    row=action(auth,current(auth,row['id']),'pause')
    job=row['runs'][0]['search_id']
    assert auth.post('/api/smart-searches/'+job+'/action',json={'action':'resume'}).status_code==409
    assert not worker.execute(task,provider=source)
    assert auth.get('/api/leads').json()==[]
    row=action(auth,current(auth,row['id']),'resume')
    row=action(auth,row,'cancel')
    assert row['state']=='cancelled' and row['runs'][0]['status']=='cancelled'
    assert worker.claim() is None


def test_task_budget_and_max_runs_stop_without_repeating_investigation(auth,monkeypatch):
    row,source=create(auth,monkeypatch,task_limit=1,max_runs=1)
    action(auth,row,'run_now');drain(source)
    result=current(auth,row['id'])
    assert result['state']=='completed'
    assert result['runs'][0]['usage']['tasks']==1
    assert result['runs'][0]['status']=='partial'
    with SessionLocal() as db:
        assert not db.scalar(select(ResearchBatchItem.id).where(ResearchBatchItem.status.in_(['pending','running'])))
    assert auth.post('/api/operations/routines/'+row['id']+'/control',json={'version':result['version'],'action':'run_now'}).status_code==409


def test_concurrent_network_operations_reserve_before_call_and_keep_money_unknown(auth,monkeypatch):
    row,source=create(auth,monkeypatch,operation_limit=1)
    action(auth,row,'run_now');task=worker.claim()
    called=[]
    @consumption.metered('website')
    def controlled(): called.append(True);return True
    with consumption.work_scope(task['token']),ThreadPoolExecutor(max_workers=2) as pool:
        futures=[consumption.submit(pool,controlled) for _ in range(2)]
        outcomes=[]
        for future in futures:
            try: outcomes.append(future.result())
            except consumption.ConsumptionLimit: outcomes.append(False)
    assert outcomes.count(True)==1 and len(called)==1
    value=current(auth,row['id'])['runs'][0]['usage']
    assert value['estimated_cost'] is None and value['confirmed_cost'] is None
    assert sum(o['count'] for o in value['operations'])==1
    action(auth,current(auth,row['id']),'pause')
    with consumption.work_scope(task['token']),pytest.raises(consumption.ConsumptionLimit): controlled()
    assert len(called)==1


def test_provider_and_global_operation_budgets_are_persistent(auth,monkeypatch):
    row,source=create(auth,monkeypatch)
    action(auth,row,'run_now');task=worker.claim()
    monkeypatch.setattr(consumption,'PROVIDER_LIMITS',{'geoapify':1,'website':3})
    monkeypatch.setattr(consumption,'HTTP_BUDGET',2)
    with consumption.work_scope(task['token']):
        consumption.reserve('geoapify')
        with pytest.raises(consumption.ConsumptionLimit): consumption.reserve('geoapify')
        consumption.reserve('website')
        with pytest.raises(consumption.ConsumptionLimit): consumption.reserve('website')
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(ProviderOperation))==2


def test_refresh_skips_recent_blocked_other_market_and_preserves_crm(auth,monkeypatch,lead_data):
    old=auth.post('/api/leads',json={**lead_data,'name':'Clínica Atualizar','category':'Clínica odontológica'}).json()
    recent=auth.post('/api/leads',json={**lead_data,'name':'Clínica Recente','category':'Clínica odontológica'}).json()
    blocked=auth.post('/api/leads',json={**lead_data,'name':'Clínica Bloqueada','category':'Clínica odontológica'}).json()
    with SessionLocal() as db:
        db.get(Lead,old['id']).in_pipeline=True
        db.get(Lead,blocked['id']).contact_blocked=True
        db.add(LeadResearch(user_id=db.get(Lead,recent['id']).user_id,lead_id=recent['id'],checked_at=int(time.time())))
        db.commit()
    row,source=create(auth,monkeypatch,objective='refresh')
    action(auth,row,'run_now');researcher=Researcher();drain(source,researcher)
    result=current(auth,row['id'])
    assert researcher.calls==1 and result['runs'][0]['status']=='completed'
    with SessionLocal() as db:
        assert db.get(Lead,old['id']).in_pipeline and db.get(Lead,blocked['id']).contact_blocked
        assert db.scalar(select(LeadResearch).where(LeadResearch.lead_id==old['id'])).status=='confirmed'


def test_source_change_duplicate_and_object_authorization(auth,monkeypatch):
    row,source=create(auth,monkeypatch)
    assert auth.put('/api/operations/routines/'+row['id']+'/configuration',json={'version':row['version'],'enabled':True,'config':{},'user_id':'x'}).status_code==422
    assert auth.post('/api/operations/routines/'+row['id']+'/control',json={'version':row['version']-1,'action':'pause'}).status_code in (409,422)
    with SessionLocal() as db:
        other=User(email='other-routine@example.test',name='Other',password_hash='unusable');db.add(other);db.flush()
        foreign=RadarSavedSearch(user_id=other.id,name='Private');db.add(foreign);db.commit();identifier=foreign.id
    assert auth.get('/api/operations/routines/'+identifier+'/history').status_code==404
    assert auth.post('/api/operations/routines/'+identifier+'/control',json={'version':1,'action':'cancel'}).status_code==404
    action(auth,row,'run_now')
    source.name='changed-source'
    assert worker.claim() is None
    assert current(auth,row['id'])['state']=='blocked'
    assert auth.get('/api/operations/routines/'+row['id']+'/history').json()
    auth.headers['X-CSRF-Token']='invalid'
    assert auth.post('/api/operations/routines/'+row['id']+'/control',json={'version':row['version'],'action':'cancel'}).status_code==403


def test_worker_probe_uses_progress_deadline_without_leaking_work(auth,monkeypatch):
    assert auth.get('/api/health/worker').status_code==503
    identifier=str(uuid4());beat(identifier)
    assert auth.get('/api/health/worker').json()=={'status':'ok'}
    now=int(time.time())
    with SessionLocal() as db:
        assert snapshot(db,now+31)['status']=='unavailable'
    beat(identifier,'busy',now+60)
    with SessionLocal() as db:
        assert snapshot(db,now+40)['status']=='ok'
        assert snapshot(db,now+61)['status']=='unavailable'
    beat(identifier,'stopped')
    assert auth.get('/api/health/worker').status_code==503


def test_delete_saved_search_cancels_inflight_children(auth,monkeypatch):
    row,source=create(auth,monkeypatch);action(auth,row,'run_now');task=worker.claim()
    assert auth.delete('/api/radar/saved-searches/'+row['id']).status_code==200
    assert not worker.execute(task,provider=source)
    assert auth.get('/api/leads').json()==[]


def test_supervisor_stops_siblings_on_exit_and_stalled_heartbeat():
    from scripts.start import supervise
    class Child:
        def __init__(self,exited=False): self.exited=exited;self.signalled=False
        def poll(self): return 0 if self.exited else None
        def send_signal(self,signal): self.signalled=True;self.exited=True
        def wait(self,timeout): return 0
    class Stop:
        def wait(self,timeout): return False
    for crash in (True,False):
        children=[Child(crash),Child()];queue=iter(children)
        code=supervise([['web'],['worker']],env={},health=lambda:False,stop=Stop(),popen=lambda *a,**k:next(queue),startup_grace=-1,interval=0,grace=0)
        assert code==1 and children[1].signalled


def test_combined_rejects_nonshared_sqlite_and_legacy(monkeypatch):
    from scripts.start import validate_environment
    monkeypatch.setenv('SCOUTLIQ_PROCESS_MODE','combined');monkeypatch.setenv('RESEARCH_EXECUTION_MODE','legacy')
    with pytest.raises(RuntimeError): validate_environment()
    monkeypatch.setenv('RESEARCH_EXECUTION_MODE','worker');monkeypatch.setenv('DATABASE_URL','sqlite:///:memory:')
    with pytest.raises(RuntimeError): validate_environment()


def test_equivalent_configuration_rejected_and_two_stalled_pages_stop(auth,monkeypatch):
    class Repeating(Source):
        def search_page(self,*args):
            batch=super().search_page(*args)
            batch.complete=False
            return batch
    source=Repeating(verified=True)
    row,_=create(auth,monkeypatch,source,page_limit=12)
    with SessionLocal() as db:
        original=db.get(RadarSavedSearch,row['id'])
        duplicate=RadarSavedSearch(user_id=original.user_id,name='Duplicata',query_json=original.query_json)
        db.add(duplicate);db.commit();identifier=duplicate.id;version=duplicate.version
    response=auth.put('/api/operations/routines/'+identifier+'/configuration',json={'version':version,'enabled':True,'config':{}})
    assert response.status_code==409
    action(auth,row,'run_now');drain(source)
    result=current(auth,row['id'])['runs'][0]
    assert source.calls==3 and result['status']=='partial'
    assert 'duas páginas' in result['reason']


def test_reclaimed_routine_attempt_fences_old_result_and_preserves_ledger(auth,monkeypatch):
    row,source=create(auth,monkeypatch,Source(verified=True))
    action(auth,row,'run_now');first=worker.claim()
    now=int(time.time())
    with SessionLocal() as db:
        db.get(ResearchExecutor,1).lease_until=now-1
        db.get(ResearchExecutor,1).next_at=0
        db.get(SmartSearch,first['id']).lease_until=now-1
        db.commit()
    recovered=worker.claim()
    assert recovered['id']==first['id'] and recovered['token']!=first['token']
    assert not worker.execute(first,provider=source)
    assert worker.execute(recovered,provider=source)
    drain(source)
    with SessionLocal() as db:
        assert db.get(WorkAttempt,first['token']).status=='expired'
        assert db.get(WorkAttempt,recovered['token']).status=='committed'
        assert db.scalar(select(func.count()).select_from(Lead))==1
    assert current(auth,row['id'])['runs'][0]['usage']['tasks']==2


def test_partial_budget_keeps_job_and_routine_investigation_counts_consistent(auth,monkeypatch):
    row,source=create(auth,monkeypatch,task_limit=2)
    action(auth,row,'run_now');drain(source)
    result=current(auth,row['id'])['runs'][0]
    job=auth.get('/api/smart-searches/'+result['search_id']).json()
    assert result['status']=='partial'
    assert result['result']['investigated']==job['counters']['investigated']==1
    assert result['usage']['tasks']==2


def test_source_change_during_claim_does_not_call_new_provider(auth,monkeypatch):
    row,source=create(auth,monkeypatch)
    action(auth,row,'run_now');task=worker.claim()
    source.name='new-provider'
    worker.execute(task,provider=source)
    assert source.calls==0
    assert current(auth,row['id'])['runs'][0]['status']=='partial'
