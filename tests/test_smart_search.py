import json
import time
from uuid import uuid4
from types import SimpleNamespace
import pytest
from sqlalchemy import select
from backend import main, research_worker as worker
from backend.db import SessionLocal
from backend.models import Lead, SmartSearch, ResearchBatch, ResearchBatchItem, ResearchExecutor, LeadActivity
from backend.providers import DiscoveryBatch, DiscoveryResult, OpenStreetMapProvider, GeoapifyProvider
from backend.schemas import LeadInput
from backend.search_intent import interpret
from backend.search_sources import capabilities
from backend.commercial_fit import assess, same_business
from backend.scoring import score

@pytest.fixture(autouse=True)
def worker_mode(monkeypatch):
    monkeypatch.setattr(worker,'MODE','worker')

def candidate(index=0, **changes):
    data=dict(name=f'Clínica Aurora {index}',category='Clínica odontológica',city='Recife',country='BR',address=f'Rua Aurora, {index+1}',latitude=-8.05,longitude=-34.9-index*.001,
              phone='5581999999999',website='',website_status='unknown')
    data.update(changes)
    return DiscoveryResult(source_id=f'fixture-{index}',lead=LeadInput(**data))

class Source:
    name='controlled'
    def __init__(self,pages): self.pages=list(pages); self.offsets=[]
    def capabilities(self,sector): return {'supported':True,'pagination':True,'coverage':'Fixture local controlada','reason':''}
    def search_page(self,query,offset,limit):
        self.offsets.append(offset)
        items=self.pages.pop(0) if self.pages else []
        return DiscoveryBatch(provider=self.name,location_label='Recife',results=items,scanned=len(items),complete=not self.pages)

class Researcher:
    def research(self,lead,locale):
        return {'status':'confirmed','provider':'controlled','website_url':f'https://example.org/{lead.id}',
                'website_status':'poor','checked_at':int(time.time()),'page':{'pages_checked':1,'quality_score':40,'forms':1,'booking':False}}
    def deep_audit(self,lead,url):
        return {'website_status':'poor','pages_checked':2,'quality_score':40,'findings':[{'key':'no_cta','severity':'high','detail':'Fixture'}]}

def start(auth,monkeypatch,source,target=25,**intent_changes):
    monkeypatch.setattr(main,'radar_provider',source)
    intent=interpret('Clínicas odontológicas em Recife, Brasil',target).model_dump()
    intent.update(intent_changes)
    response=auth.post('/api/smart-searches',json={'intent':intent,'request_key':str(uuid4())})
    assert response.status_code==200,response.text
    return response.json()

def run_until_idle(source,limit=350):
    for _ in range(limit):
        with SessionLocal() as db:
            slot=db.get(ResearchExecutor,1); slot.next_at=0; slot.used=0
            db.commit()
        task=worker.claim()
        if not task: return
        worker.execute(task,researcher=Researcher(),provider=source)
    pytest.fail('Executor did not terminate within finite fixture budget')

@pytest.mark.parametrize('target',[25,50,75,100])
def test_target_means_qualified_not_raw(auth,monkeypatch,target):
    # Already verified inputs model reviewed imported facts; no real external calls.
    source=Source([[candidate(i,website_status='none',instagram='https://instagram.com/aurora',instagram_active=True) for i in range(target)]])
    job=start(auth,monkeypatch,source,target)
    run_until_idle(source)
    result=auth.get('/api/smart-searches/'+job['id']).json()
    assert result['status']=='completed',result
    assert result['counters']['qualified']==target
    assert result['counters']['created']==target
    assert result['counters']['investigated']==0

def test_progressive_discovery_dedup_and_recovery(auth,monkeypatch):
    source=Source([[candidate(1),candidate(2,name='Starbucks Recife'),candidate(3,name='Prefeitura do Recife')],
                   [candidate(1),candidate(4)]])
    job=start(auth,monkeypatch,source)
    run_until_idle(source)
    result=auth.get('/api/smart-searches/'+job['id']).json()
    assert result['status']=='partial'
    assert result['counters']['duplicates']==1
    assert result['counters']['discarded']==3
    assert result['counters']['investigated']==2
    assert result['counters']['qualified']==2
    assert source.offsets==[0,3]
    with SessionLocal() as db:
        assert len(db.scalars(select(ResearchBatchItem)).all())==2
    assert auth.get('/api/smart-searches').json()[0]['id']==job['id']

def test_sparse_unknown_absence_failure_are_different():
    a=SimpleNamespace(**candidate().lead.model_dump(),source='geoapify',website_intelligence_json='{}')
    unknown=score(a)
    assert unknown['commercial_dimensions']['need']['value'] is None
    assert unknown['status'] in ('provisional','insufficient')
    a.website_status='none'
    assert score(a)['commercial_dimensions']['need']['value']==95
    a.website='https://example.com'
    assert score(a)['commercial_dimensions']['need']['state']=='contradictory'
    a.website_status='unknown'; a.reviews=10000; a.rating=5
    assert score(a)['value']<50

def test_independent_exceeds_chain_and_unknown():
    a=SimpleNamespace(**candidate(website_status='none',instagram='https://instagram.com/example',instagram_active=True).lead.model_dump(),source='manual')
    good=score(a)
    a.name='McDonald\'s Recife'
    assert score(a)['status']=='incompatible'
    assert good['value']>score(a)['value']
    a.qualification_json=json.dumps({'independence':'independent','review_reason':'Autonomia local comprovada em contato.'})
    assert assess(a)['status']=='compatible'

@pytest.mark.parametrize('source',['geoapify','openstreetmap','manual'])
def test_fit_is_identical_across_sources(source):
    lead=SimpleNamespace(**candidate(name='Starbucks Recife',website_status='none').lead.model_dump(),source=source)
    assert score(lead)['status']=='incompatible'
    lead.name='Prefeitura do Recife'
    assert assess(lead)['reasons'][0]['key']=='public_entity'

def test_frozen_before_after_evaluation():
    from pathlib import Path
    from backend.scoring import _technical_score
    rows=json.loads((Path(__file__).parent/'fixtures/commercial-evaluation-v132.json').read_text(encoding='utf-8'))
    for row in rows:
        lead=SimpleNamespace(**row['input'])
        assert _technical_score(lead)['value']==row['before']['value']
        assert score(lead)['value']==row['after']['value']
        assert score(lead)['status']==row['after']['status']
        assert row['human_label'] is None and row['outcome'] is None

def test_legacy_batch_controls_sync_smart_search(auth,monkeypatch):
    source=Source([[candidate()]]);job=start(auth,monkeypatch,source)
    worker.execute(worker.claim(),provider=source)
    job=auth.get('/api/smart-searches/'+job['id']).json()
    for action,status in [('pause','paused'),('resume','investigating'),('cancel','cancelled')]:
        assert auth.post(f"/api/research/batches/{job['batch_id']}/{action}").status_code==200
        assert auth.get('/api/smart-searches/'+job['id']).json()['status']==status

def test_intent_negation_preference_and_combinations():
    value=interpret('Restaurantes em Recife, Brasil, preferencialmente com WhatsApp, exceto cafeterias')
    assert value.sectors==['restaurante']
    assert 'cafeteria' in value.exclusions
    assert 'whatsapp' in value.preferences and 'whatsapp' not in value.requirements
    assert interpret('Clínicas em Recife, Brasil sem site ou com WhatsApp').unresolved
    assert interpret('Clínicas em Recife, Brasil não quero sem site').unresolved or 'no_site' not in interpret('Clínicas em Recife, Brasil não quero sem site').requirements

def test_technology_coverage_is_explicit(auth,monkeypatch):
    monkeypatch.setenv('RADAR_GEOAPIFY_API_KEY','controlled-fixture-not-real')
    source=GeoapifyProvider()
    monkeypatch.setattr(main,'radar_provider',source)
    intent=interpret('Software companies in Austin, United States').model_dump()
    response=auth.post('/api/smart-searches',json={'intent':intent,'request_key':str(uuid4())})
    assert response.status_code==200,response.text
    assert response.json()['status']=='partial'
    assert response.json()['counters']['discovered']==0
    assert capabilities(OpenStreetMapProvider(),'tecnologia')['supported']

def test_pause_cancel_and_stale_fence(auth,monkeypatch):
    source=Source([[candidate()]])
    job=start(auth,monkeypatch,source)
    task=worker.claim(); assert task['kind']=='smart'
    paused=auth.post(f"/api/smart-searches/{job['id']}/action",json={'action':'pause'})
    assert paused.status_code==200
    assert not worker.execute(task,provider=source)
    assert auth.get('/api/leads').json()==[]
    assert auth.post(f"/api/smart-searches/{job['id']}/action",json={'action':'resume'}).status_code==200
    assert auth.post(f"/api/smart-searches/{job['id']}/action",json={'action':'cancel'}).json()['status']=='cancelled'

def test_idempotency_saved_intent_and_owner(auth,monkeypatch):
    source=Source([[]]); monkeypatch.setattr(main,'radar_provider',source)
    payload={'intent':interpret('Clínicas em Recife, Brasil').model_dump(),'request_key':str(uuid4())}
    first=auth.post('/api/smart-searches',json=payload).json()
    assert auth.post('/api/smart-searches',json=payload).json()['id']==first['id']
    assert auth.post('/api/smart-searches',json={**payload,'user_id':'other'}).status_code==422
    saved=auth.post(f"/api/smart-searches/{first['id']}/save",json={'name':'Intenção clínica'})
    assert saved.status_code==200,saved.text
    searches=auth.get('/api/radar/saved-searches').json()
    assert searches[0]['query']['commercial_intent']==payload['intent']
    assert auth.get('/api/smart-searches/'+str(uuid4())).status_code==404

def test_homonyms_need_strong_identity():
    a=candidate().lead
    b=candidate(name=a.name,city='Olinda').lead
    assert not same_business(a,b)
    b=candidate(name=a.name,address='Outra rua',phone='',latitude=-9).lead
    assert not same_business(a,b)
    b=candidate(name=a.name,website='https://example.com').lead
    assert same_business(a,b)

def test_budget_deadline_and_expired_claim(auth,monkeypatch):
    source=Source([[candidate()],[candidate(1)]])
    job=start(auth,monkeypatch,source)
    stale=worker.claim()
    with SessionLocal() as db:
        obj=db.get(SmartSearch,job['id']);obj.lease_until=0
        slot=db.get(ResearchExecutor,1);slot.lease_until=0;slot.next_at=0
        db.commit()
    resumed=worker.claim()
    assert resumed['token']!=stale['token']
    assert not worker.execute(stale,provider=source)
    assert worker.execute(resumed,provider=source)
    with SessionLocal() as db:
        db.get(SmartSearch,job['id']).deadline=int(time.time())-1
        slot=db.get(ResearchExecutor,1);slot.used=worker.BUDGET;slot.day=int(time.time())//86400
        db.commit()
    assert worker.claim() is None
    result=auth.get('/api/smart-searches/'+job['id']).json()
    assert result['status']=='partial' and 'Prazo' in result['reason']
    with SessionLocal() as db:
        assert db.get(ResearchBatch,result['batch_id']).status=='cancelled'

def test_all_smart_objects_require_owner_and_csrf(auth,monkeypatch):
    from backend.models import User
    source=Source([[]]);job=start(auth,monkeypatch,source)
    with SessionLocal() as db:
        other=User(email='other-smart@example.test',password_hash='unusable-fixture',name='Outro');db.add(other);db.flush()
        db.get(SmartSearch,job['id']).user_id=other.id
        lead=Lead(**candidate().lead.model_dump(),user_id=other.id);db.add(lead);db.commit();identifier=lead.id
    assert auth.get('/api/smart-searches/'+job['id']).status_code==404
    assert auth.post('/api/smart-searches/'+job['id']+'/action',json={'action':'cancel'}).status_code==404
    assert auth.post('/api/smart-searches/'+job['id']+'/save',json={'name':'Inválido'}).status_code==404
    assert auth.post('/api/smart-searches/leads/'+identifier+'/review',json={'version':1,'independence':'independent','operating_status':'active','reason':'Não deve alterar registro de outra conta.'}).status_code==404
    auth.headers['X-CSRF-Token']='invalid'
    assert auth.post('/api/smart-searches/interpret',json={'text':'Clínicas em Recife, Brasil'}).status_code==403

def test_page_budget_honors_repeated_irrelevant_results(auth,monkeypatch):
    source=Source([[candidate(i,name=f'Starbucks Recife {i}')] for i in range(20)])
    job=start(auth,monkeypatch,source)
    run_until_idle(source)
    result=auth.get('/api/smart-searches/'+job['id']).json()
    assert result['status']=='partial'
    assert result['counters']['calls']==12
    assert result['counters']['qualified']==0 and result['counters']['investigated']==0

def test_failed_collection_is_not_absence(auth,monkeypatch):
    source=Source([[candidate()]])
    job=start(auth,monkeypatch,source)
    assert worker.execute(worker.claim(),provider=source)
    class Failure:
        def research(self,*args): raise RuntimeError('secret-network-error')
    for _ in range(3):
        with SessionLocal() as db:
            db.get(ResearchExecutor,1).next_at=0
            for item in db.scalars(select(ResearchBatchItem)).all(): item.retry_at=0
            db.commit()
        task=worker.claim();assert task['kind']=='batch'
        worker.execute(task,researcher=Failure())
    run_until_idle(source)
    result=auth.get('/api/smart-searches/'+job['id']).json()
    assert result['counters']['qualified']==0 and result['counters']['investigating']==1
    assert 'secret-network-error' not in json.dumps(result)
    assert result['results'][0]['priority']['commercial_dimensions']['need']['value'] is None

def test_closed_and_opt_out_are_preserved(auth,monkeypatch,lead_data):
    created=auth.post('/api/leads',json={**lead_data,'name':'Clínica Aurora 0','category':'Clínica odontológica'}).json()
    with SessionLocal() as db:
        lead=db.get(Lead,created['id']);lead.contact_blocked=True;lead.stage='won';db.commit()
    source=Source([[candidate()]])
    job=start(auth,monkeypatch,source)
    run_until_idle(source)
    result=auth.get('/api/smart-searches/'+job['id']).json()
    assert result['counters']['existing']==1
    assert result['counters']['discarded']==1
    with SessionLocal() as db:
        lead=db.get(Lead,created['id']);assert lead.contact_blocked and lead.stage=='won'
    current_version=auth.get('/api/leads').json()[0]['version']
    review=auth.post('/api/smart-searches/leads/'+created['id']+'/review',json={'version':current_version,'independence':'unknown','operating_status':'closed','reason':'Encerramento confirmado em revisão local.'})
    assert review.status_code==200
    assert review.json()['score']['commercial_fit']['status']=='incompatible'
    stale=auth.post('/api/smart-searches/leads/'+created['id']+'/review',json={'version':current_version,'independence':'independent','operating_status':'active','reason':'Revisão antiga não deve sobrescrever o encerramento.'})
    assert stale.status_code==409
    with SessionLocal() as db:
        lead=db.get(Lead,created['id'])
        assert json.loads(lead.qualification_json)['operating_status']=='closed'
        assert lead.contact_blocked and lead.stage=='won'
