"""Broad discovery uses controlled sources only, with no paid API or messages."""
import json
import time
from uuid import uuid4
from urllib.parse import parse_qs
import pytest
from sqlalchemy import select, func
from backend import main, locations, research_worker as worker, smart_search, discovery_plan
from backend.db import SessionLocal
from backend.models import SmartSearch, User, Lead, ResearchBatchItem, RadarSavedSearch
from backend.providers import GeoapifyProvider, OpenStreetMapProvider, DiscoveryBatch, DiscoveryResult, ProviderConfigurationError, GEOAPIFY_DEFAULT_CATEGORIES
from backend.search_intent import Intent, interpret, discovery_sectors
from backend.search_location import SearchArea
from backend.search_sources import capabilities, search_page
from backend.communication_models import OutboxMessage
from backend.opportunity_models import OutreachDraft
from test_unified_search import place, request, ControlledSource
from test_smart_search import candidate, run_until_idle
from test_search_area import area


class BroadSource(ControlledSource):
    def __init__(self, pages=()):
        super().__init__(); self.pages=list(pages); self.offsets=[]
    def general_capabilities(self):
        return dict(supported=True,pagination=True,coverage='Controlled broad coverage',reason='')
    def area_capabilities(self, area):
        return dict(supported=True,coverage='Controlled map coverage')
    def search_page(self, query, offset, limit):
        self.queries.append(query);self.offsets.append(offset)
        rows=self.pages.pop(0) if self.pages else []
        return DiscoveryBatch(provider=self.name,location_label=query.location,results=rows,scanned=len(rows),complete=not self.pages)


@pytest.fixture
def general(monkeypatch):
    monkeypatch.setattr(worker,'MODE','worker')
    monkeypatch.setattr(locations,'search_locations',lambda *a,**k:[{'resolved':place().model_dump()}])
    monkeypatch.delenv('SCOUT_SEMANTIC_AUTO_POLICY',raising=False)
    source=BroadSource();monkeypatch.setattr(main,'radar_provider',source)
    return source


def launch(auth, **changes):
    response=auth.post('/api/smart-searches/launch',json=request(text='',**changes))
    assert response.status_code==200,response.text
    return response.json()


@pytest.mark.parametrize('text,mode,sectors',[('', 'general', []),('   ','general',[]),('Hamburguerias','directed',['hamburgueria']),('x','ambiguous',[])])
def test_explicit_interpretation_modes(text,mode,sectors):
    intent=interpret(text)
    assert intent.search_mode==mode and intent.sectors==sectors
    assert bool(smart_search.non_geographic_warnings(intent))==(mode=='ambiguous')
    assert Intent.model_validate_json(intent.model_dump_json())==intent


def test_empty_launch_and_idempotency_use_one_broad_step(auth,general,monkeypatch):
    from backend import semantic_intent
    monkeypatch.setenv('SCOUT_SEMANTIC_AUTO_POLICY','complex_only')
    monkeypatch.setattr(semantic_intent,'interpret_optional',lambda *a:pytest.fail('Empty query must not spend on a model'))
    data=request(text='')
    result=auth.post('/api/smart-searches/launch',json=data).json()
    job=result['job']; assert job['intent']['search_mode']=='general' and job['intent']['sectors']==[]
    assert len(job['plan']['steps'])==1 and job['plan']['steps'][0]['sector']==''
    assert job['limits']=={'provider_pages':12,'candidates':600,'investigations':200}
    worker.execute(worker.claim(),provider=general)
    assert general.queries[0].category=='' and general.queries[0].resolved_location.id==place().id
    assert auth.post('/api/smart-searches/launch',json=data).json()['job']['id']==job['id']
    assert auth.post('/api/smart-searches/launch',json={**data,'target':25}).status_code==409
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(OutboxMessage))==0
        assert db.scalar(select(func.count()).select_from(OutreachDraft))==0


def test_unknown_text_requires_explicit_review(auth,general):
    response=auth.post('/api/smart-searches/launch',json=request(text='qwerty específico')).json()
    assert response['status']=='clarification'
    assert auth.get('/api/smart-searches').json()==[]
    criteria=dict(sectors=[],profile=interpret('').profile.model_dump(),accept_unresolved=False)
    assert auth.post('/api/smart-searches/launch',json=request(text='qwerty',criteria=criteria)).json()['status']=='clarification'
    criteria['accept_unresolved']=True
    job=auth.post('/api/smart-searches/launch',json=request(text='qwerty',criteria=criteria)).json()['job']
    assert job['intent']['search_mode']=='filtered' and job['intent']['sectors']==[]


@pytest.mark.parametrize('sectors',[[],['odontologia','academia']])
def test_optional_advanced_niches_and_commercial_exclusions(auth,general,sectors):
    criteria=dict(sectors=sectors,profile=interpret('').profile.model_dump(),exclusions=['centralized_chains','public_entities','closed','farmacia'],requirements=['whatsapp'])
    job=launch(auth,criteria=criteria)['job']
    intent=Intent.model_validate(job['intent'])
    assert intent.search_mode=='filtered' and intent.sectors==sectors
    assert intent.requirements==['whatsapp'] and 'farmacia' in intent.exclusions
    assert len(job['coverage'])==(len(sectors) or 1)
    assert smart_search.query_for(intent,{'sector':0}).category==('dentista' if sectors else '')
    if sectors: assert smart_search.query_for(intent,{'sector':1}).category=='academia'


def test_general_requires_real_selected_location(auth,general):
    assert auth.post('/api/smart-searches/launch',json=request(text='',location=None)).status_code==422
    assert auth.post('/api/smart-searches/launch',json=request(text='',location={'id':'fake','query':'Recife'})).status_code==422


def test_general_source_support_is_explicit_even_with_location_hook(auth,general,monkeypatch):
    source=ControlledSource();monkeypatch.setattr(main,'radar_provider',source)
    job=launch(auth)['job']
    assert job['status']=='partial' and not job['coverage'][0]['supported']
    assert worker.claim() is None and source.queries==[]


def test_geoapify_general_reuses_bounded_multicategory_page(monkeypatch):
    monkeypatch.setenv('RADAR_GEOAPIFY_API_KEY','fixture-only')
    source=GeoapifyProvider();calls=[]
    monkeypatch.setattr(source,'_geocode',lambda *a:pytest.fail('Must use selected boundary'))
    monkeypatch.setattr(source,'_request_json',lambda path,params,**kw: calls.append(params) or {'features':[]})
    intent=interpret('');intent.location=place()
    result=search_page(source,smart_search.query_for(intent,{'sector':0}),100,25)
    assert len(calls)==1 and calls[0]['categories']==','.join(GEOAPIFY_DEFAULT_CATEGORIES)
    assert calls[0]['offset']==100 and calls[0]['limit']==25
    assert calls[0]['filter']=='place:'+place().id
    assert result.complete and capabilities(source,'',place())['supported']
    assert not capabilities(source,'',place(source='ibge',id='2611606'))['supported']


def test_osm_general_map_is_one_union_with_observed_geography(monkeypatch):
    source=OpenStreetMapProvider();calls=[]
    monkeypatch.setattr(source,'_geocode',lambda *a:pytest.fail('Map must not geocode'))
    elements=[dict(type='node',id=i,lat=-8.05,lon=-34.9,tags={
        'name':'OSM controlado '+str(i),'shop':'bakery',**({'addr:city':'Recife','addr:country':'BR'} if i==1 else {})}) for i in [1,2]]
    elements.append(dict(type='node',id=3,lat=-8.05,lon=-34.9,tags=['invalid upstream shape']))
    monkeypatch.setattr(source,'_request_overpass',lambda payload: calls.append(parse_qs(payload.decode())['data'][0]) or {'elements':elements})
    intent=interpret('');intent.area=SearchArea.model_validate(area())
    q=smart_search.query_for(intent,{'sector':0})
    result=search_page(source,q,0,100)
    assert len(calls)==1 and calls[0].count('out tags center')==1
    assert '"shop"' in calls[0] and '"amenity"' in calls[0]
    assert len(result.results)==1 and result.results[0].lead.city=='Recife'
    assert result.results[0].lead.country=='BR'
    assert capabilities(source,'',area=intent.area)['supported']
    assert not capabilities(source,'',place())['supported']
    search_page(source,q,100,100);assert len(calls)==1  # No invented pagination.


def test_general_pause_resume_cancel_and_ownership(auth,general):
    job=launch(auth)['job'];path='/api/smart-searches/'+job['id']
    assert auth.post(path+'/action',json={'action':'pause'}).json()['status']=='paused'
    assert worker.claim() is None
    assert auth.post(path+'/action',json={'action':'resume'}).status_code==200
    assert auth.post(path+'/action',json={'action':'cancel'}).json()['status']=='cancelled'
    assert worker.claim() is None
    with SessionLocal() as db:
        other=User(email='isolation-general@example.test',password_hash='unused',email_verified_at=1)
        db.add(other);db.flush();db.get(SmartSearch,job['id']).user_id=other.id;db.commit()
    assert auth.get(path).status_code==404
    assert auth.post(path+'/action',json={'action':'resume'}).status_code==404
    assert auth.post(path+'/save',json={'name':'Wrong owner'}).status_code==404


def test_general_saved_reopens_with_filters_and_runs_monitor(auth,general):
    from backend.search_compat import intent_from_saved
    job=launch(auth,criteria=dict(sectors=[],profile=interpret('').profile.model_dump(),exclusions=['farmacia']))['job']
    saved=auth.post('/api/smart-searches/'+job['id']+'/save',json={'name':'Exploração geral Recife'}).json()
    with SessionLocal() as db:
        row=db.get(RadarSavedSearch,saved['id']);intent=intent_from_saved(row)
        assert intent.sectors==[] and intent.exclusions==['farmacia'] and intent.query==''
        assert intent.location.id==place().id
        row.monitor_enabled=True;row.next_monitor_at=int(time.time())-1;db.commit()
    auth.post('/api/smart-searches/'+job['id']+'/action',json={'action':'cancel'})
    run_until_idle(general)
    assert general.queries and all(q.category=='' for q in general.queries)


def test_general_routine_uses_same_worker(auth,general):
    from backend.routines import RoutineConfig
    job=launch(auth)['job']
    saved=auth.post('/api/smart-searches/'+job['id']+'/save',json={'name':'General routine'}).json()
    auth.post('/api/smart-searches/'+job['id']+'/action',json={'action':'cancel'})
    row=next(r for r in auth.get('/api/radar/saved-searches').json() if r['id']==saved['id'])
    response=auth.put('/api/operations/routines/'+saved['id']+'/configuration',json={
        'version':row['version'],'enabled':True,'config':RoutineConfig().model_dump()})
    assert response.status_code==200,response.text
    row=response.json()
    response=auth.post('/api/operations/routines/'+saved['id']+'/control',json={'version':row['version'],'action':'run_now'})
    assert response.status_code==200,response.text
    run_until_idle(general)
    assert general.queries and general.queries[0].category==''


def test_diversity_is_secondary_to_quality_and_uses_observed_categories():
    rows=[dict(id=i,quality=80,category='cafe') for i in range(4)]+[dict(id=4,quality=80,category='dentista'),dict(id=5,quality=20,category='oficina')]
    result=discovery_plan.diverse(rows,lambda r:r['quality'],lambda r:r['category'])
    assert [r['category'] for r in result[:2]]==['cafe','dentista']
    assert result[-1]['quality']==20
    assert all(row['quality']==rows[row['id']]['quality'] for row in result)


def test_general_prefetch_and_final_diversity_preserve_canonical_score(auth,general):
    general.pages=[[candidate(i,category='Cafeteria',website_status='none',instagram='https://instagram.com/test',instagram_active=True) for i in range(30)],
                   [candidate(100+i,category='Barbearia',website_status='none',instagram='https://instagram.com/test',instagram_active=True) for i in range(10)]]
    job=launch(auth,target=25)['job'];run_until_idle(general)
    result=auth.get('/api/smart-searches/'+job['id']).json()
    assert len(general.queries)==2 and result['status']=='completed'
    qualified=[r for r in result['results'] if r['group']=='qualified']
    assert len(qualified)==25 and len({r['category'] for r in qualified})==2
    assert result['diversity']['categories']==2
    from backend.scoring import score
    with SessionLocal() as db:
        assert all(r['priority']==score(db.get(Lead,r['id'])) for r in result['results'])


@pytest.mark.parametrize('pages,candidate_cap,expected',[(2,600,2),(12,200,2)])
def test_general_budget_exhaustion_keeps_partial_results(auth,general,monkeypatch,pages,candidate_cap,expected):
    general.pages=[[candidate(100*p+i,category='Cafeteria') for i in range(100)] for p in range(4)]
    monkeypatch.setattr(smart_search,'classify',lambda lead,intent:('discarded','Controlled ineligible'))
    job=launch(auth)['job']
    with SessionLocal() as db:
        row=db.get(SmartSearch,job['id']);info=json.loads(row.state_json)
        info.update(page_limit=pages,candidate_limit=candidate_cap);row.state_json=json.dumps(info);db.commit()
    run_until_idle(general)
    result=auth.get('/api/smart-searches/'+job['id']).json()
    assert len(general.queries)==expected and result['status']=='partial'
    assert result['counters']['discovered']==200 and len(result['results'])==200
    assert result['counters']['investigated']==0


def test_historical_intent_without_mode_is_not_reinterpreted():
    old=interpret('Hamburguerias em Recife, Brasil').model_dump();old.pop('search_mode')
    parsed=Intent.model_validate(old)
    assert parsed.search_mode=='directed' and parsed.sectors==['hamburgueria']
    assert discovery_sectors(parsed)==['hamburgueria']


def test_general_research_allocation_is_diverse_and_excludes_incompatible(auth,general):
    general.pages=[[candidate(i,category='Cafeteria') for i in range(6)] +
                   [candidate(10,category='Barbearia'),candidate(11,name='Starbucks QA',category='Cafeteria'),
                    candidate(12,category='Farmácia')]]
    job=launch(auth,criteria=dict(sectors=[],profile=interpret('').profile.model_dump(),exclusions=['farmacia']))['job']
    with SessionLocal() as db:
        row=db.get(SmartSearch,job['id']);info=json.loads(row.state_json)
        info['investigation_limit']=2;row.state_json=json.dumps(info);db.commit()
    worker.execute(worker.claim(),provider=general)
    with SessionLocal() as db:
        items=db.scalars(select(ResearchBatchItem).order_by(ResearchBatchItem.position)).all()
        assert len(items)==2
        assert {db.get(Lead,i.lead_id).category for i in items}=={'Cafeteria','Barbearia'}
    result=auth.get('/api/smart-searches/'+job['id']).json()
    assert all(r['group']=='discarded' for r in result['results'] if r['name']=='Starbucks QA' or r['category']=='Farmácia')
    assert result['counters']['investigated']==0


def test_historical_persisted_job_without_mode_resumes_same_query(auth,general):
    response=auth.post('/api/smart-searches/launch',json=request(text='Hamburguerias'))
    assert response.status_code==200
    job=response.json()['job']
    with SessionLocal() as db:
        row=db.get(SmartSearch,job['id']);intent=json.loads(row.intent_json)
        intent.pop('search_mode');row.intent_json=json.dumps(intent);db.commit()
    path='/api/smart-searches/'+job['id']
    assert auth.post(path+'/action',json={'action':'pause'}).status_code==200
    assert auth.post(path+'/action',json={'action':'resume'}).status_code==200
    run_until_idle(general)
    assert general.queries[0].category=='hamburgueria'
    assert auth.get(path).json()['status']=='partial'
