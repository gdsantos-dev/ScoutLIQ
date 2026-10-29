"""Controlled map-to-worker contract; never invokes a real provider."""
import pytest
from pydantic import ValidationError
from backend import main, locations, research_worker as worker, semantic_intent
from backend.providers import DiscoveryBatch, DiscoveryResult, GeoapifyProvider, OpenStreetMapProvider
from backend.schemas import LeadInput
from backend.search_location import SearchArea
from backend.search_intent import Intent
from backend.smart_search import query_for
from test_unified_search import configured, request, ControlledSource


def area(kind='bounds'):
    return dict(kind=kind,bounds=[-34.92,-8.07,-34.88,-8.03],
                polygon=[[-34.92,-8.07],[-34.88,-8.07],[-34.92,-8.03]] if kind=='polygon' else [])


class AreaSource(ControlledSource):
    def area_capabilities(self,selection): return {'supported':True,'coverage':'Controlled map area'}
    def search_page(self,query,offset,limit):
        self.queries.append(query)
        rows=[]
        for index,(lat,lng) in enumerate([(-8.06,-34.91),(-8.04,-34.89),(-8.05,-34.7)]):
            rows.append(DiscoveryResult(source_id=f'area-{index}',lead=LeadInput(
                name=f'Empresa área {index}',category='Hamburgueria',city='Recife',country='BR',latitude=lat,longitude=lng)))
        return DiscoveryBatch(provider=self.name,location_label=query.location,results=rows,scanned=3,complete=True)


@pytest.fixture
def source(configured,monkeypatch):
    value=AreaSource()
    monkeypatch.setattr(main,'radar_provider',value)
    monkeypatch.setattr(locations,'search_locations',lambda *a,**k:pytest.fail('Map area must not be geocoded'))
    return value


@pytest.mark.parametrize('kind,count',[('bounds',2),('polygon',1)])
def test_map_launch_filters_exact_geometry_through_existing_worker(auth,source,kind,count):
    data=request(location=None,area=area(kind))
    response=auth.post('/api/smart-searches/launch',json=data)
    assert response.status_code==200,response.text
    job=response.json()['job']
    assert job['intent']['area']==area(kind)
    assert job['intent']['market']=={'city':'','country':'','region':''}
    assert job['intent']['location'] is None
    worker.execute(worker.claim(),provider=source)
    assert source.queries[0].scope==kind
    assert source.queries[0].bounds==area(kind)['bounds']
    final=auth.get('/api/smart-searches/'+job['id']).json()
    assert len(final['results'])==count
    assert auth.post('/api/smart-searches/launch',json=data).json()['job']['id']==job['id']
    changed={**data,'area':{**area(),'bounds':[-34.93,-8.07,-34.88,-8.03]}}
    assert auth.post('/api/smart-searches/launch',json=changed).status_code==409


def test_map_intent_saved_and_reused_without_losing_shape(auth,source):
    job=auth.post('/api/smart-searches/launch',json=request(location=None,area=area('polygon'))).json()['job']
    saved=auth.post(f"/api/smart-searches/{job['id']}/save",json={'name':'Área triangular'}).json()
    row=next(r for r in auth.get('/api/radar/saved-searches').json() if r['id']==saved['id'])
    assert row['query']['scope']=='polygon'
    assert row['query']['polygon']==area('polygon')['polygon']
    assert row['query']['commercial_intent']['area']==area('polygon')
    intent=Intent.model_validate(row['query']['commercial_intent'])
    assert query_for(intent,{'sector':0}).polygon==area('polygon')['polygon']
    routine=auth.put(f"/api/operations/routines/{saved['id']}/configuration",json={'version':row['version'],'enabled':True,'config':{}})
    assert routine.status_code==200,routine.text
    assert routine.json()['intent']['area']==area('polygon')


def test_map_conflicting_text_requires_explicit_confirmation(auth,source):
    data=request(text='Hamburguerias em Recife, Brasil',location=None,area=area())
    assert auth.post('/api/smart-searches/launch',json=data).json()['status']=='location_conflict'
    assert auth.get('/api/smart-searches').json()==[]
    final=auth.post('/api/smart-searches/launch',json={**data,'confirm_location':True}).json()['job']
    assert final['intent']['market']['city']==''


def test_unsupported_map_source_does_not_guess_country_or_call_network(auth,source,monkeypatch):
    provider=ControlledSource()
    monkeypatch.setattr(provider,'search_page',lambda *a:pytest.fail('Unsupported geography'))
    monkeypatch.setattr(main,'radar_provider',provider)
    job=auth.post('/api/smart-searches/launch',json=request(location=None,area=area())).json()['job']
    assert job['status']=='partial'
    assert 'país' in job['reason']
    assert worker.claim() is None


@pytest.mark.parametrize('patch',[
    {'location':None},
    {'area':area()},
    {'location':None,'area':{**area(),'owner_id':'other'}},
    {'location':None,'area':{**area(),'bounds':[-36,-9,-34,-7]}},
    {'location':None,'area':{**area(),'bounds':[0,0,0,0]}},
    {'location':None,'area':{**area(),'polygon':[[0,0],[1,1],[2,2]]}},
    {'location':None,'area':{**area('polygon'),'polygon':[[-34.92,-8.07],[-34.88,-8.03],[-34.92,-8.03],[-34.88,-8.07]]}},
    {'location':None,'area':{**area('polygon'),'polygon':[[-34.92,-8.07],[-34.88,-8.07],[-34.92,-8.07]]}},
])
def test_invalid_area_rejected_before_executor(auth,source,patch):
    assert auth.post('/api/smart-searches/launch',json=request(**patch)).status_code==422
    assert auth.get('/api/smart-searches').json()==[]


def test_geometry_is_not_part_of_semantic_contract():
    schema=semantic_intent.schema()
    assert 'area' not in schema['properties']
    assert 'SearchArea' not in schema.get('$defs',{})
    with pytest.raises(ValidationError):
        SearchArea(**{**area(),'bounds':[-34.92,float('nan'),-34.88,-8.03]})


def test_geoapify_map_results_need_observed_city_and_country(monkeypatch):
    monkeypatch.setenv('RADAR_GEOAPIFY_API_KEY','controlled-offline-test')
    provider=GeoapifyProvider()
    query=query_for(Intent(query='Hamburguerias',sectors=['hamburgueria'],area=SearchArea(**area())),{'sector':0})
    props=dict(name='Empresa controlada',place_id='controlled-place',lat=-8.05,lon=-34.9,
               categories=['catering.fast_food.burger'],city='Recife',country_code='br')
    def convert(values): return provider._place_to_result({'properties':values},'Área visível do mapa',query,'',(-8.05,-34.9))
    assert convert(props).lead.city=='Recife'
    assert convert({**props,'country_code':''}) is None
    assert convert({**props,'city':''}) is None
