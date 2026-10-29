import json
import time
from uuid import uuid4
import pytest
from sqlalchemy import select
from backend import main, research_worker as worker
from backend.db import SessionLocal
from backend.models import SmartSearch, ResearchExecutor, RadarSavedSearch, User
from backend.providers import DiscoveryBatch, DiscoveryResult
from backend.schemas import LeadInput
from backend.monitor_matching import matches
from test_smart_search import Researcher

class Source:
    name='legacy-controlled'
    def __init__(self): self.queries=[]
    def search(self,query):
        self.queries.append(query.model_dump())
        rows=[DiscoveryResult(source_id=f'old-{i}',lead=LeadInput(name=f'Oficina controlada {i}',
            category='Oficinas especiais',city='Recife',country='BR',address=f'Rua do Teste {i}',
            latitude=-8.05,longitude=-34.9-i*.001,phone='5581999999999',rating=4.5,
            reviews=300 if i==0 else 20)) for i in range(2)]
        return DiscoveryBatch(provider=self.name,location_label=query.location,results=rows,scanned=2,complete=True)

@pytest.fixture
def source(monkeypatch):
    value=Source()
    monkeypatch.setattr(main,'radar_provider',value)
    monkeypatch.setattr(worker,'MODE','worker')
    return value


def saved(auth,**patch):
    query=dict(location='Recife',country='BR',category='Oficinas especiais',scope='radius',radius_km=7,
        min_reviews=200,min_rating=4,contact_filter='phone',min_score=0,min_confidence=0,min_timing=0,
        service_key='',min_service_score=0,problem_keys=[])
    query.update(patch)
    response=auth.post('/api/radar/saved-searches',json={'name':'Consulta histórica','query':query})
    assert response.status_code==201,response.text
    return response.json()


def launch(auth,row,key=None):
    return auth.post(f"/api/smart-searches/saved/{row['id']}/launch",json={'version':row['version'],'request_key':key or str(uuid4())})


def drain(source):
    for _ in range(15):
        task=worker.claim()
        if not task:return
        worker.execute(task,Researcher(),source)
    pytest.fail('Shared executor did not finish')


def test_historical_query_preserves_predicates_geometry_and_response_ids(auth,source):
    row=saved(auth)
    query={k:v for k,v in row['query'].items() if k in main.DiscoveryQuery.model_fields}
    baseline=auth.post('/api/radar/search',json=query).json()
    expected=[r['id'] for r in baseline['results'] if matches(r,row['query'])]
    assert len(expected)==1
    response=launch(auth,row)
    assert response.status_code==200,response.text
    job=response.json()['job']
    for key,value in row['query'].items():
        if key!='commercial_intent': assert job['intent']['legacy'][key]==value
    drain(source)
    done=auth.get('/api/smart-searches/'+job['id']).json()
    assert [r['id'] for r in done['results']]==expected
    updated=auth.get('/api/radar/saved-searches').json()[0]
    assert updated['last_result_ids']==expected
    assert updated['query']==row['query']
    assert source.queries[0]==source.queries[1]
    copy=auth.post(f"/api/smart-searches/{job['id']}/save",json={'name':'Cópia estruturada'})
    assert copy.status_code==200,copy.text
    clone=next(r for r in auth.get('/api/radar/saved-searches').json() if r['id']==copy.json()['id'])
    assert clone['query']['commercial_intent']['legacy']==job['intent']['legacy']
    assert clone['query']['min_reviews']==200


def test_saved_launch_idempotence_and_version(auth,source):
    row=saved(auth);key=str(uuid4())
    first=launch(auth,row,key).json()['job']
    assert launch(auth,row,key).json()['job']['id']==first['id']
    assert launch(auth,{**row,'version':row['version']+1}).status_code==409
    with SessionLocal() as db:
        item=db.get(RadarSavedSearch,row['id']);data=json.loads(item.query_json)
        data['min_reviews']=500;item.query_json=json.dumps(data);db.commit()
    assert launch(auth,row,key).status_code==409


def test_saved_launch_checks_owner_and_rejects_mass_assignment(auth,source):
    row=saved(auth)
    with SessionLocal() as db:
        other=User(email='other@example.test',password_hash='unused')
        db.add(other);db.flush();db.get(RadarSavedSearch,row['id']).user_id=other.id;db.commit()
    assert launch(auth,row).status_code==404
    assert auth.post(f"/api/smart-searches/saved/{row['id']}/launch",json={'version':1,'request_key':str(uuid4()),'user_id':other.id}).status_code==422


def test_monitor_runs_as_shared_job_and_keeps_no_research_scope(auth,source):
    row=saved(auth)
    row=auth.patch(f"/api/radar/saved-searches/{row['id']}/monitor",json={'version':row['version'],'enabled':True,'interval':'daily'}).json()
    assert auth.post(f"/api/radar/saved-searches/{row['id']}/schedule").status_code==200
    task=worker.claim();assert task['kind']=='smart'
    assert worker.execute(task,provider=source)
    done=auth.get('/api/smart-searches/'+task['id']).json()
    assert done['limits']['investigations']==0
    assert done['batch_id'] is None
    updated=auth.get('/api/radar/saved-searches').json()[0]
    assert len(updated['last_result_ids'])==1 and updated['last_new_count']==1
    assert updated['next_monitor_at']>int(time.time())
    assert worker.claim() is None
    auth.post(f"/api/radar/saved-searches/{row['id']}/schedule")
    drain(source)
    assert auth.get('/api/radar/saved-searches').json()[0]['last_new_count']==0


@pytest.mark.parametrize('action',['disable','delete'])
def test_monitor_cancel_during_inflight_read_drops_stale_write(auth,source,action):
    row=saved(auth)
    row=auth.patch(f"/api/radar/saved-searches/{row['id']}/monitor",json={'version':row['version'],'enabled':True,'interval':'daily'}).json()
    auth.post(f"/api/radar/saved-searches/{row['id']}/schedule")
    task=worker.claim();before=source.search
    def stop(query):
        current=auth.get('/api/radar/saved-searches').json()[0]
        if action=='disable':
            assert auth.patch(f"/api/radar/saved-searches/{row['id']}/monitor",json={'version':current['version'],'enabled':False,'interval':'daily'}).status_code==200
        else: assert auth.delete(f"/api/radar/saved-searches/{row['id']}").status_code==200
        return before(query)
    source.search=stop
    worker.execute(task,provider=source)
    assert auth.get('/api/leads').json()==[]
    assert auth.get('/api/smart-searches/'+task['id']).json()['status']=='cancelled'


def test_monitor_recovery_uses_same_persisted_search(auth,source):
    row=saved(auth)
    row=auth.patch(f"/api/radar/saved-searches/{row['id']}/monitor",json={'version':row['version'],'enabled':True,'interval':'daily'}).json()
    auth.post(f"/api/radar/saved-searches/{row['id']}/schedule")
    old=worker.claim()
    with SessionLocal() as db:
        db.get(ResearchExecutor,1).lease_until=0
        db.get(SmartSearch,old['id']).lease_until=0;db.commit()
    new=worker.claim()
    assert old['id']==new['id'] and old['token']!=new['token']
    assert worker.execute(old,provider=source) is False
    assert worker.execute(new,provider=source)
    assert len(auth.get('/api/smart-searches').json())==1
    assert auth.get('/api/radar/saved-searches').json()[0]['last_result_ids']==[]
    assert auth.get('/api/smart-searches/'+new['id']).json()['status']=='partial'
    assert source.queries==[]  # Expired reservation consumes the one-page monitor budget.


@pytest.mark.parametrize('kind',['bounds','polygon'])
def test_legacy_geometry_does_not_rewrite_provider_parameters(auth,source,kind):
    box=[-34.92,-8.07,-34.88,-8.03]
    polygon=[[-34.92,-8.07],[-34.88,-8.07],[-34.88,-8.03],[-34.92,-8.03]] if kind=='polygon' else []
    row=saved(auth,scope=kind,radius_km=11,center_lat=-8.051,center_lng=-34.901,bounds=box,polygon=polygon)
    response=launch(auth,row)
    assert response.status_code==200,response.text
    legacy=response.json()['job']['intent']['legacy']
    for key in ('scope','radius_km','center_lat','center_lng','bounds','polygon'):
        assert legacy[key]==row['query'][key]
