"""Daily operation contracts, only synthetic providers and isolated databases."""
import json
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from uuid import uuid4
import pytest
from sqlalchemy import select, func
from backend import main, research_worker as worker, consumption
from backend.db import SessionLocal, engine
from backend.models import Lead, User, SmartSearch, ResearchBatch, ResearchBatchItem, ResearchExecutor, LeadActivity
from backend.autonomy_models import WorkAttempt, ProviderOperation
from backend.prospecting_models import ProspectingPlan
from backend.opportunity_models import OutreachDraft
from backend.communication_models import OutboxMessage
from test_operational_autonomy import create as routine, Source, drain
from test_progressive_investigation import prefs, Researcher
from test_prospecting import save, activate, act
from test_commercial_review import create, queue, preview, commit


@pytest.fixture
def planned(auth, monkeypatch):
    now=int(datetime.now(ZoneInfo('America/Sao_Paulo')).replace(hour=12,minute=0,second=0,microsecond=0).timestamp())
    monkeypatch.setattr(time,'time',lambda:now)
    monkeypatch.setattr(worker,'MODE','worker')
    prefs(auth,search=True,allow_deep=False)
    source=Source(verified=True)
    monkeypatch.setattr(consumption,'PROVIDER_LIMITS',{**consumption.PROVIDER_LIMITS,source.name:100})
    source.search_page=consumption.metered(source.name)(source.search_page)
    row,source=routine(auth,monkeypatch,source,investigation_limit=2,research_mode='web')
    save(auth,row,daily_target=1,daily_investigations=2,daily_operations=10)
    activate(auth)
    return row,source,now


def discover(source):
    task=worker.claim();assert task and task['kind']=='smart'
    assert worker.execute(task,provider=source)
    with SessionLocal() as db:
        job=db.scalar(select(SmartSearch));return job.id,job.batch_id


def test_plan_goal_allows_admitted_progressive_work_and_tracks_ledger(planned,auth):
    row,source,now=planned
    search_id,batch_id=discover(source)
    assert batch_id
    with SessionLocal() as db:
        b=db.get(ResearchBatch,batch_id)
        assert b.mode=='progressive' and b.requested_count==1
        assert db.scalar(select(func.count()).select_from(ResearchBatch))==1
        original=db.scalar(select(ProspectingPlan)).config_json
    assert queue(auth,view='daily')['daily']['investigating']==1
    engine.dispose()
    researcher=Researcher();researcher.research=consumption.metered('website')(researcher.research)
    drain(source,researcher)
    d=queue(auth,view='daily')['daily']
    assert d['incorporated']==d['plan_incorporated']==d['investigated']==1
    assert d['investigating']==0 and source.calls==1
    with SessionLocal() as db:
        assert db.scalar(select(ProspectingPlan)).config_json==original
        attempts=db.scalars(select(WorkAttempt).where(WorkAttempt.kind=='batch')).all()
        assert attempts and all(a.run_id for a in attempts)
        assert db.scalar(select(func.count()).select_from(ProviderOperation))>=2
        assert db.scalar(select(func.count()).select_from(OutreachDraft))==0
        assert db.scalar(select(func.count()).select_from(OutboxMessage))==0
        assert db.get(SmartSearch,search_id).status in ('completed','partial')


def test_pause_revokes_linked_progressive_claim(planned,auth):
    _,source,_=planned;_,batch_id=discover(source)
    task=worker.claim();assert task and task['kind']=='batch'
    assert act(auth,'pause').status_code==200
    assert not worker.execute(task,researcher=Researcher())
    with SessionLocal() as db:
        assert db.get(ResearchBatch,batch_id).status=='cancelled'
        assert db.scalar(select(ProspectingPlan)).state=='paused'
    assert queue(auth,view='daily')['daily']['plan']['state']=='paused'


def test_zero_plan_investigations_cannot_enqueue_detached_batch(planned,auth):
    row,source,_=planned
    act(auth,'pause');save(auth,row,daily_target=1,daily_investigations=0);act(auth,'resume')
    drain(source,Researcher())
    with SessionLocal() as db: assert db.scalar(select(func.count()).select_from(ResearchBatch))==0


def test_reencounter_never_creates_second_automatic_investigation(planned,auth):
    _,source,_=planned;drain(source,Researcher());act(auth,'disable')
    intent=auth.post('/api/smart-searches/interpret',json={'text':'Clínicas odontológicas em Recife, Brasil','target':25}).json()['intent']
    result=auth.post('/api/smart-searches',json={'request_key':str(uuid4()),'intent':intent});assert result.status_code==200
    drain(source,Researcher())
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Lead))==1
        assert db.scalar(select(func.count()).select_from(ResearchBatch))==1
    assert queue(auth,view='daily')['daily']['plan_incorporated']==1


def done(lead):
    with SessionLocal() as db:
        l=db.get(Lead,lead['id']);b=ResearchBatch(user_id=l.user_id,mode='web',status='completed',requested_count=1,completed_at=int(time.time()))
        db.add(b);db.flush();db.add(ResearchBatchItem(batch_id=b.id,lead_id=l.id,status='done',finished_at=int(time.time())));db.commit()


def test_daily_order_preserves_human_states_and_has_stable_ties(auth,lead_data):
    response=create(auth,lead_data,name='Resposta')
    priority=create(auth,lead_data,name='Pronta');done(priority)
    stale=create(auth,lead_data,name='Revisão anterior');rows=queue(auth,state='all',lead_ids=[stale['id']])['items']
    op,_=preview(auth,rows);commit(auth,op)
    pending=create(auth,lead_data,name='Pendente',website_status='unknown',contact='',whatsapp='')
    blocked=create(auth,lead_data,name='Bloqueada')
    future=create(auth,lead_data,name='Ação futura')
    with SessionLocal() as db:
        l=db.get(Lead,response['id']);db.add(LeadActivity(user_id=l.user_id,lead_id=l.id,kind='reply',body='Pode enviar informações?',metadata_json=json.dumps({'event':'manual_activity','result':'information_request'})))
        db.get(Lead,stale['id']).reviews=99
        db.get(Lead,blocked['id']).contact_blocked=True
        f=db.get(Lead,future['id']);f.in_pipeline=True;f.next_action='Revisar no dia combinado';f.next_action_on=(datetime.now().date()+timedelta(days=3)).isoformat()
        db.commit()
    data=queue(auth,view='daily');ids=[r['id'] for r in data['items']]
    assert ids==[response['id'],priority['id'],stale['id'],pending['id'],blocked['id']]
    assert [r['id'] for r in queue(auth,view='daily')['items']]==ids
    assert data['items'][2]['review']['state']=='reviewed' and data['items'][2]['review']['needs_review']
    assert queue(auth,view='daily',attention='ready')['items'][0]['id']==priority['id']
    assert data['items'][1]['daily_attention']['kind']=='ready'
    assert data['items'][2]['daily_attention']['kind']=='stale'
    assert queue(auth,view='daily',attention='blocked')['items'][0]['id']==blocked['id']


def test_daily_counts_not_equivalent_and_no_implicit_draft_or_contact(auth,lead_data):
    first=create(auth,lead_data);done(first)
    create(auth,lead_data,website_status='unknown',whatsapp='',contact='')
    d=queue(auth,view='daily')['daily']
    assert d['incorporated']==2 and d['investigated']==1 and d['plan_incorporated']==0
    assert d['other_incorporated']==2 and d['plan'] is None
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(OutreachDraft))==0
        assert db.scalar(select(func.count()).select_from(OutboxMessage))==0


def test_daily_to_review_to_draft_reuses_versions_and_idempotent_operations(auth,lead_data):
    lead=create(auth,lead_data);done(lead)
    rows=queue(auth,view='daily')['items'];assert rows
    op,_=preview(auth,rows,'reviewed');commit(auth,op)
    refreshed=queue(auth,view='followup',state='all',lead_ids=[lead['id']])['items']
    draft,_=preview(auth,refreshed,'prepare');assert draft['eligible']==1
    result=commit(auth,draft);assert commit(auth,draft)==result
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(OutreachDraft))==1
        assert db.scalar(select(func.count()).select_from(OutboxMessage))==0
    assert queue(auth,view='daily')['daily']['operations']


def test_daily_scope_and_selection_ids_do_not_leak_other_users(auth,lead_data):
    mine=create(auth,lead_data,website_status='unknown')
    with SessionLocal() as db:
        u=User(email='other@example.test',password_hash='not-a-real-credential');db.add(u);db.flush()
        l=Lead(**{**lead_data,'name':'Private other company'},user_id=u.id);db.add(l);db.commit();other=l.id
    result=queue(auth,view='daily');assert result['daily']['incorporated']==1
    assert 'Private other company' not in json.dumps(result)
    assert queue(auth,view='followup',state='all',lead_ids=[other])['total']==0
    assert auth.get('/api/commercial-review/queue',params=[('lead_ids',str(uuid4()))]*51).status_code==422
    assert auth.get('/api/commercial-review/queue?view=daily&cohort=unvalidated').status_code==422
    assert auth.get('/api/commercial-review/queue?lead_ids=bad').status_code==422


def test_empty_daily_view_exposes_zero_without_fake_goal(auth):
    result=queue(auth,view='daily');assert result['total']==0
    assert result['daily']['incorporated']==result['daily']['investigated']==result['daily']['ready']==0
    assert not result['daily']['searches'] and result['daily']['plan'] is None


def test_missing_fields_and_blocked_recipient_still_use_canonical_preview(auth,lead_data):
    lead=create(auth,lead_data,website_status='unknown',contact='',whatsapp='')
    row=queue(auth,view='daily')['items'][0]
    assert row['summary']['services']==[]
    op,_=preview(auth,[row],'prepare');assert op['eligible']==0
    assert 'Destinatário' in op['preview'][0]['reason']


def test_daily_endpoint_requires_authentication(client):
    assert client.get('/api/commercial-review/queue?view=daily').status_code==401


def test_progressive_plan_budget_exhaustion_is_visible_and_stops_work(planned,auth):
    row,source,_=planned
    act(auth,'pause');save(auth,row,daily_target=10,daily_investigations=2,daily_operations=1);act(auth,'resume')
    discover(source);drain(source,Researcher())
    d=queue(auth,view='daily')['daily']
    assert d['plan']['operations']==1 and d['investigating']==0
    assert any('Orçamento' in s['reason'] for s in d['searches'])
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(WorkAttempt).where(WorkAttempt.kind=='batch'))==0


def test_two_workers_and_expired_claim_preserve_single_progressive_item(planned,auth):
    from concurrent.futures import ThreadPoolExecutor
    _,source,now=planned;_,batch_id=discover(source)
    with ThreadPoolExecutor(max_workers=2) as pool:claims=list(pool.map(lambda _:worker.claim(),range(2)))
    task=next(t for t in claims if t);assert sum(t is not None for t in claims)==1
    with SessionLocal() as db:
        db.get(ResearchExecutor,1).lease_until=now-1
        db.get(ResearchBatchItem,task['id']).lease_until=now-1
        db.commit()
    recovered=worker.claim();assert recovered and recovered['id']==task['id'] and recovered['token']!=task['token']
    assert not worker.execute(task,researcher=Researcher())
    assert worker.execute(recovered,researcher=Researcher())
    drain(source,Researcher())
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(ResearchBatchItem).where(ResearchBatchItem.batch_id==batch_id))==1
        assert db.get(ResearchBatch,batch_id).status=='completed'
    assert queue(auth,view='daily')['daily']['investigated']==1


def test_daily_refresh_is_bounded_and_exposes_incomplete_index(auth,lead_data):
    from pathlib import Path
    from sqlalchemy import event
    with SessionLocal() as db:
        user=db.scalar(select(User));db.add_all([Lead(**{**lead_data,'name':f'Volume diário {i}'},user_id=user.id) for i in range(1000)]);db.commit()
    statements=[]
    def record(conn,cursor,statement,parameters,context,executemany):
        if statement.lstrip().upper().startswith('SELECT'):statements.append(statement)
    event.listen(engine,'before_cursor_execute',record);start=time.perf_counter()
    try:result=queue(auth,view='daily')
    finally:event.remove(engine,'before_cursor_execute',record)
    assert result['index_pending']==750 and result['daily']['index_pending']==750
    assert result['daily']['incorporated']==1000 and len(result['items'])<=25
    assert len(statements)<80
    Path('artifacts').mkdir(exist_ok=True)
    Path('artifacts/daily-volume.json').write_text(json.dumps({'companies':1000,'select_queries':len(statements),'seconds':round(time.perf_counter()-start,3),'index_pending':750,'providers':0}),encoding='utf8')
