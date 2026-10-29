"""Controlled geography and launch tests; no external calls or real company claims."""
import json
import time
from uuid import uuid4
import pytest
from pydantic import ValidationError
from sqlalchemy import select
from backend import main, locations, research_worker as worker
from backend.db import SessionLocal
from backend.models import SmartSearch
from backend.providers import GeoapifyProvider, OpenStreetMapProvider, DiscoveryBatch
from backend.search_location import SearchLocation
from backend.search_intent import interpret
from backend.search_sources import capabilities, search_page
from backend.smart_search import query_for


def place(**changes):
    values=dict(id='controlled_recife',name='Recife',formatted='Recife, Pernambuco, Brasil',
        administrative_type='city',city='Recife',state='Pernambuco',state_code='PE',
        country='Brasil',country_code='BR',latitude=-8.05,longitude=-34.9,
        bbox=[-35.1,-8.2,-34.7,-7.9],source='geoapify',resolved_at=int(time.time()))
    values.update(changes)
    return SearchLocation(**values)


class ControlledSource:
    name='controlled'
    def __init__(self): self.queries=[]
    def capabilities(self, sector): return dict(supported=True,pagination=True,coverage='Controlled',reason='')
    def location_capabilities(self, location): return dict(supported=True,coverage='Controlled boundary')
    def search_page(self, query, offset, limit):
        self.queries.append(query)
        return DiscoveryBatch(provider=self.name,location_label=query.location,results=[],complete=True)


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(worker,'MODE','worker')
    monkeypatch.delenv('SCOUT_SEMANTIC_AUTO_POLICY',raising=False)
    source=ControlledSource()
    monkeypatch.setattr(main,'radar_provider',source)
    monkeypatch.setattr(locations,'search_locations',lambda *a,**k:[{'resolved':place().model_dump()}])
    return source


def request(**changes):
    values=dict(text='Hamburguerias',location={'id':'controlled_recife','query':'Recife'},target=50,request_key=str(uuid4()))
    values.update(changes)
    return values


def test_simple_launch_reaches_existing_worker_and_keeps_geography(auth,configured):
    data=request()
    response=auth.post('/api/smart-searches/launch',json=data)
    assert response.status_code==200,response.text
    job=response.json()['job']
    assert job['intent']['sectors']==['hamburgueria']
    assert job['intent']['unresolved']==[]
    assert job['intent']['location']['id']=='controlled_recife'
    assert job['intent']['target']==50
    worker.execute(worker.claim(),provider=configured)
    assert configured.queries[0].resolved_location.id=='controlled_recife'
    assert configured.queries[0].category=='hamburgueria'
    final=auth.get('/api/smart-searches/'+job['id']).json()
    assert final['status']=='partial' and final['counters']['qualified']==0
    assert auth.post('/api/smart-searches/launch',json=data).json()['job']['id']==job['id']
    assert auth.post('/api/smart-searches/launch',json={**data,'target':25}).status_code==409


def test_homonym_requires_exact_selected_identifier(auth,configured):
    assert auth.post('/api/smart-searches/launch',json=request(location={'id':'other_recife','query':'Recife'})).status_code==422


def test_explicit_location_conflict_requires_correction_before_queue(auth,configured):
    data=request(text='Hamburguerias em São Paulo, Brasil')
    answer=auth.post('/api/smart-searches/launch',json=data).json()
    assert answer['status']=='location_conflict'
    assert auth.get('/api/smart-searches').json()==[]
    answer=auth.post('/api/smart-searches/launch',json={**data,'confirm_location':True}).json()
    assert answer['job']['intent']['market']['city']=='Recife'


def test_unsupported_criteria_do_not_silently_disappear(auth,configured):
    answer=auth.post('/api/smart-searches/launch',json=request(text='Hamburguerias com mais de 200 avaliações')).json()
    assert answer['status']=='clarification'
    assert auth.get('/api/smart-searches').json()==[]


def test_default_does_not_call_semantic_even_when_available(auth,configured,monkeypatch):
    from backend import semantic_intent
    monkeypatch.setattr(semantic_intent,'interpret_optional',lambda *args:pytest.fail('Unapproved model call'))
    auth.post('/api/smart-searches/launch',json=request(text='Empresas com receita alta'))


def test_unsupported_boundary_is_partial_without_radius_or_network(auth,configured,monkeypatch):
    source=OpenStreetMapProvider()
    monkeypatch.setattr(main,'radar_provider',source)
    monkeypatch.setattr(source,'search',lambda *a:pytest.fail('Unsupported area must not call source'))
    result=auth.post('/api/smart-searches/launch',json=request()).json()['job']
    assert result['status']=='partial' and 'raio' in result['reason']
    assert worker.claim() is None


def test_saved_intent_keeps_location(auth,configured):
    job=auth.post('/api/smart-searches/launch',json=request()).json()['job']
    saved=auth.post(f"/api/smart-searches/{job['id']}/save",json={'name':'Hamburguerias Recife'})
    assert saved.status_code==200,saved.text
    row=auth.get('/api/radar/saved-searches').json()[0]
    assert row['query']['commercial_intent']['location']==job['intent']['location']


def test_geoapify_uses_selected_boundary_without_geocoding(monkeypatch):
    monkeypatch.setenv('RADAR_GEOAPIFY_API_KEY','fixture-not-real')
    source=GeoapifyProvider()
    monkeypatch.setattr(source,'_geocode',lambda *a:pytest.fail('Selection must not be re-geocoded'))
    calls=[]
    def response(path,params,**kwargs):
        calls.append((path,params)); return {'features':[]}
    monkeypatch.setattr(source,'_request_json',response)
    intent=interpret('Hamburguerias'); intent.location=place()
    result=search_page(source,query_for(intent,{'sector':0}),0,50)
    assert calls[0][1]['filter']=='place:controlled_recife'
    assert calls[0][1]['categories']=='catering.fast_food.burger,catering.restaurant.burger'
    assert result.scope=='region'
    assert not capabilities(source,'hamburgueria',place(source='ibge',id='2611606'))['supported']


@pytest.mark.parametrize('kind,name',[('suburb','Boa Viagem'),('city','Recife'),('state','Pernambuco'),('country','Brasil')])
def test_catalog_preserves_administrative_identity(kind,name):
    raw=dict(result_type=kind,place_id='fixture_place',name=name,formatted=name,city='Recife',state='Pernambuco',
             country='Brasil',country_code='br',lat=-8.05,lon=-34.9,bbox={'lon1':-35.1,'lat1':-8.2,'lon2':-34.7,'lat2':-7.9})
    raw[kind]=name
    resolved=locations._administrative_result(raw)
    assert resolved.name==name
    assert resolved.administrative_type==('district' if kind=='suburb' else kind)
    assert resolved.bbox==[-35.1,-8.2,-34.7,-7.9]
    assert locations._administrative_result({**raw,'result_type':'street'}) is None
    assert locations._administrative_result({**raw,'lat':float('nan')}) is None


@pytest.mark.parametrize('patch',[{'bbox':[1,2,0,3]},{'latitude':None},{'longitude':float('inf')},{'id':'x,circle:0,0,5000'}])
def test_invalid_geography_rejected(patch):
    with pytest.raises(ValidationError): place(**patch)


def test_new_endpoints_require_authentication(client,configured):
    assert client.get('/api/smart-searches/locations?q=Recife').status_code==401
    assert client.post('/api/smart-searches/launch',json=request()).status_code==401
    assert client.post('/api/smart-searches/prepare',json={'text':'Hamburguerias'}).status_code==401


@pytest.mark.parametrize('text',['Hamburguerias','Burger restaurants','Hamburgueserías'])
def test_burger_aliases_keep_specific_sector(text):
    assert interpret(text).sectors==['hamburgueria']


@pytest.mark.parametrize('text',[
    'Empresas especializadas em burgers em Recife, Brasil',
    'Businesses specialized in burgers in Recife, Brazil',
    'Empresas especializadas en hamburguesas en Recife, Brasil',
])
def test_specialization_is_not_interpreted_as_location(text):
    intent=interpret(text)
    assert intent.market.city=='recife'
    assert intent.market.country=='BR'
    assert intent.sectors==['hamburgueria']


@pytest.mark.parametrize('collision',[False,True])
def test_launch_recovers_unique_key_race(auth,configured,monkeypatch,collision):
    from backend import smart_search
    create=smart_search.create_search
    def competing_commit(db,user,intent,key,provider,now,options=None):
        competing_options={**options}
        if collision: competing_options['launch_hash']='different payload'
        create(db,user,intent,key,provider,now,options=competing_options)
        db.commit()  # A durable winner appeared after launch's first read.
        return create(db,user,intent,key,provider,now,options=options)
    monkeypatch.setattr(smart_search,'create_search',competing_commit)
    response=auth.post('/api/smart-searches/launch',json=request())
    assert response.status_code==(409 if collision else 200),response.text
    jobs=auth.get('/api/smart-searches').json()
    assert len(jobs)==1
    if not collision: assert response.json()['job']['id']==jobs[0]['id']


@pytest.mark.parametrize('enabled',[False,True])
def test_complex_semantics_requires_policy_and_complete_configuration(auth,configured,monkeypatch,enabled):
    from backend import semantic_intent
    monkeypatch.setenv('SCOUT_SEMANTIC_AUTO_POLICY','complex_only')
    monkeypatch.setattr(semantic_intent,'configuration',lambda:{'enabled':enabled})
    calls=[]
    def semantic(text,target,user,key):
        calls.append(text)
        intent=interpret('Hamburguerias',target)
        return intent,{'mode':'semantic','reason':''}
    monkeypatch.setattr(semantic_intent,'interpret_optional',semantic)
    data=request(text='Empresas especializadas em burgers com receita alta')
    response=auth.post('/api/smart-searches/launch',json=data)
    assert response.status_code==200,response.text
    assert len(calls)==int(enabled)
    if enabled:
        job=response.json()['job']
        assert job['intent']['query']==data['text']
        assert job['intent']['location']['id']=='controlled_recife'
        assert job['intent']['market']['city']=='Recife'
    else:
        assert response.json()['status']=='clarification'


def reviewed_criteria(text='Hamburguerias'):
    intent=interpret(text)
    return {key:intent.model_dump()[key] for key in ('sectors','profile','requirements','preferences','exclusions','requirement_mode')}


@pytest.mark.parametrize('warning',[
    'Informe uma cidade antes de executar.',
    'Confirme o país antes de executar.',
    'País inferido pelo modelo; confirme o país no resumo antes de executar.',
    'Critério comercial pendente de confirmação.',
])
def test_semantic_geography_does_not_override_verified_selection(auth,configured,monkeypatch,warning):
    from backend import semantic_intent
    monkeypatch.setenv('SCOUT_SEMANTIC_AUTO_POLICY','complex_only')
    monkeypatch.setattr(semantic_intent,'configuration',lambda:{'enabled':True})
    def semantic(text,target,user,key):
        intent=interpret('Hamburguerias',target)
        intent.unresolved=[warning]
        intent.market.city='model city'
        intent.market.country='US'
        return intent,{'mode':'semantic','reason':''}
    monkeypatch.setattr(semantic_intent,'interpret_optional',semantic)
    result=auth.post('/api/smart-searches/launch',json=request(text='Hamburguerias com receita alta')).json()
    if warning.startswith('Critério'):
        assert result['status']=='clarification'
        assert result['messages']==[warning]
        assert auth.get('/api/smart-searches').json()==[]
    else:
        assert result['status']=='started'
        assert result['job']['intent']['market']['city']=='Recife'
        assert result['job']['intent']['market']['country']=='BR'


def test_optional_criteria_reuse_pipeline_and_never_spend_on_semantics(auth,configured,monkeypatch):
    from backend import semantic_intent
    monkeypatch.setenv('SCOUT_SEMANTIC_AUTO_POLICY','complex_only')
    monkeypatch.setattr(semantic_intent,'interpret_optional',lambda *a:pytest.fail('Explicit criteria must not invoke a model'))
    preview=auth.post('/api/smart-searches/prepare',json={'text':'Hamburguerias','target':25})
    assert preview.status_code==200
    assert preview.json()['warnings']==[]
    criteria=reviewed_criteria()
    criteria.update(requirements=['whatsapp','no_site'],preferences=['active'],requirement_mode='any')
    job=auth.post('/api/smart-searches/launch',json=request(criteria=criteria)).json()['job']
    assert job['intent']['requirements']==['whatsapp','no_site']
    assert job['intent']['preferences']==['active']
    assert job['intent']['requirement_mode']=='any'
    assert job['intent']['location']['id']=='controlled_recife'


def test_discarding_unrecognized_criteria_requires_explicit_acknowledgement(auth,configured):
    data=request(text='Hamburguerias com receita alta',criteria=reviewed_criteria())
    assert auth.post('/api/smart-searches/launch',json=data).json()['status']=='clarification'
    assert auth.get('/api/smart-searches').json()==[]
    data['criteria']['accept_unresolved']=True
    job=auth.post('/api/smart-searches/launch',json=data).json()['job']
    assert job['intent']['unresolved']==[]
    assert job['intent']['requirements']==[]


@pytest.mark.parametrize('patch',[
    {'sectors':['arbitrary-provider-query']},
    {'requirements':['sql']},
    {'user_id':'other-user'},
    {'market':{'city':'spoofed'}},
    {'exclusions':['hamburgueria']},
])
def test_adjusted_criteria_are_validated_on_backend(auth,configured,patch):
    response=auth.post('/api/smart-searches/launch',json=request(criteria={**reviewed_criteria(),**patch}))
    assert response.status_code==422,response.text
    assert auth.get('/api/smart-searches').json()==[]
