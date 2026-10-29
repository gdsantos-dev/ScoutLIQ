import json, time
from uuid import uuid4
import pytest
from sqlalchemy import select,func
from backend import research_worker as worker
from backend import absorption_recovery as recovery
from backend.db import SessionLocal
from backend.models import Lead,User,ResearchExecutor
from backend.absorption_models import AbsorptionRecovery,AbsorptionItem
from backend.absorption_input import parse,normalize,ParseError
from test_absorption import record,preview,commit,URL


def intake(auth,rows,**extra):
    return auth.post(URL+'/intake',json={'raw':json.dumps(rows),'request_key':str(uuid4()),**extra})

def read(auth,b):return auth.get(URL+'/batches/'+b['id']).json()
def edit(auth,b,index=0,**changes):
    i=b['items'][index]
    return auth.patch(f"{URL}/batches/{b['id']}/items/{i['id']}",json={'version':i['version'],'changes':changes})
def start(auth,b,**extra):
    return auth.post(f"{URL}/batches/{b['id']}/recover",json={'version':b['version'],'request_key':str(uuid4()),**extra})
def pending(auth,**extra):return intake(auth,[record(address='Rua Azul, 10',latitude=None,longitude=None,**extra)]).json()
def control(auth,b,action):return auth.post(f"{URL}/batches/{b['id']}/recovery/{b['recovery']['id']}",json={'version':b['version'],'action':action})
def tick(provider=None):
    task=worker.claim();assert task and task['kind']=='absorption',task
    worker.execute(task,provider=provider)
    return task

def stub(monkeypatch,rows):
    def lookup(provider,row,reserve):reserve();return rows,''
    monkeypatch.setattr(recovery,'lookup',lookup)


def test_csv_bom_quotes_decimal_mapping_and_original(auth):
    raw='\ufeffEmpresa;Categoria;Cidade;País;Latitude;Longitude;URL;Observações\n"Café; Azul";Cafeteria;Recife;Brasil;-8,05;-34,90;EXAMPLE.ORG;"linha um\nlinha dois"'
    data=parse(raw);assert data['mapping_required']
    mapping={'6':'website'}
    r=auth.post(URL+'/intake',json={'raw':raw,'mapping':mapping,'request_key':str(uuid4()),'source':'csv'})
    assert r.status_code==201,r.text
    i=r.json()['items'][0];assert i['status']=='ready'
    assert i['record']['website']=='https://example.org' and i['record']['latitude']==-8.05
    assert i['original']['cells'][0]=='Café; Azul' and i['original']['cells'][4]=='-8,05'


def test_table_duplicate_headers_require_explicit_mapping():
    raw='Nome\tEmpresa\tCidade\nAlfa\tBeta\tRecife'
    assert parse(raw)['mapping_required']
    assert not parse(raw,mapping={'1':'ignore'})['mapping_required']
    with pytest.raises(ParseError):parse(raw,mapping={'1':'owner_id'})


@pytest.mark.parametrize('raw',[json.dumps([{}]*51),'a'*48001,'Nome;Cidade\n"bad;Recife'],ids=['row-limit','size-limit','bad-quotes'])
def test_bounded_parser(raw):
    with pytest.raises(ParseError):parse(raw)


def test_row_local_errors_and_no_inferred_country(auth):
    r=intake(auth,[record(),record('Inválida',website='javascript:alert(1)'),{'name':'Sem país'},42,record('Parcial',latitude=None)])
    assert r.status_code==201,r.text
    b=r.json();assert b['counts']['ready']==1 and b['counts']['pending']==4
    assert b['items'][2]['record']['country']==''
    assert all(i['issues'] for i in [b['items'][1],b['items'][3],b['items'][4]])


def test_normalization_no_country_dialing_assumption():
    value,issues=normalize(record(country='Brasil',phone='(81) 99999-0000',instagram='@empresa',website='EXAMPLE.ORG',name=' Café  Azul\u200b '))
    assert not issues
    assert value['phone']=='81999990000' and value['country']=='BR' and value['name']=='Café Azul'
    assert value['instagram']=='https://www.instagram.com/empresa/'


def test_incremental_confirm_preserves_imported_and_original(auth):
    b=intake(auth,[record('Primeira'),record('Segunda',latitude=None,longitude=None)]).json()
    done=commit(auth,b).json();assert done['status']=='partial' and done['counts']['imported']==1
    first=done['items'][0]['lead_id']
    assert edit(auth,done,0,name='Não pode').status_code==409
    updated=edit(auth,done,1,latitude=-8.07,longitude=-34.88);assert updated.status_code==200,updated.text
    b=updated.json();assert b['counts']['ready']==1 and b['items'][1]['original']['latitude'] is None
    r=auth.post(f"{URL}/batches/{b['id']}/commit",json={'payload_hash':b['payload_hash'],'version':b['version'],'confirm':True})
    assert r.status_code==200 and r.json()['counts']['imported']==2
    assert r.json()['items'][0]['lead_id']==first
    assert auth.post(f"{URL}/batches/{b['id']}/commit",json={'payload_hash':b['payload_hash'],'version':b['version'],'confirm':True}).status_code==200
    with SessionLocal() as db:assert db.scalar(select(func.count()).select_from(Lead))==2


def test_edit_versions_mass_assignment_and_invalid_pair(auth):
    b=pending(auth)
    assert edit(auth,b,owner_id='other').status_code==422
    assert edit(auth,b,latitude=-8).status_code==422
    assert edit(auth,b,country='XX').status_code==422
    r=edit(auth,b,category='Odontologia');assert r.status_code==200,r.text
    assert edit(auth,b,category='Cafeteria').status_code==409


def test_internal_recovery_avoids_external_and_duplicates(auth,monkeypatch):
    data=record(address='Rua Azul, 10');data.pop('source_url');lead=auth.post('/api/leads',json=data)
    assert lead.status_code==201,lead.text
    b=pending(auth)
    # Confirmed duplicates are already resolved by dedup, no provider necessary.
    assert b['counts']['duplicate']==1
    assert start(auth,b).status_code==422


def test_external_only_after_explicit_action_auto_fill_and_provenance(auth,monkeypatch):
    calls=[]
    def lookup(provider,row,reserve):reserve();calls.append(row);return [record(address='Rua Azul, 10',source_name='geoapify',source_id='poi-123')],''
    monkeypatch.setattr(recovery,'lookup',lookup)
    b=pending(auth);read(auth,b);assert not calls
    r=start(auth,b,allow_external=True);assert r.status_code==202,r.text
    tick();b=read(auth,b);i=b['items'][0]
    assert i['status']=='ready' and len(calls)==1
    assert i['history'][0]['provenance']['automatic'] is True
    assert i['original']['latitude'] is None
    with SessionLocal() as db:assert db.scalar(select(func.count()).select_from(Lead))==0
    assert b['recovery']['calls']==1 and b['recovery']['status']=='completed'


def test_no_external_by_default_and_no_centroid(auth,monkeypatch):
    def fail(*args):raise AssertionError('Must not query')
    monkeypatch.setattr(recovery,'lookup',fail)
    b=pending(auth);start(auth,b);tick();b=read(auth,b)
    assert b['counts']['pending']==1 and b['items'][0]['record']['latitude'] is None
    assert b['recovery']['calls']==0


def test_ambiguous_suggestions_require_human_and_rejection_persists(auth,monkeypatch):
    stub(monkeypatch,[record(address='Rua Azul, 10',source_name='geoapify',source_id='one'),record(address='Rua Azul, 10',source_name='geoapify',source_id='two')])
    b=pending(auth);start(auth,b,allow_external=True);tick();b=read(auth,b);i=b['items'][0]
    assert len(i['suggestions'])==2 and i['record']['latitude'] is None
    r=auth.post(f"{URL}/batches/{b['id']}/items/{i['id']}/decision",json={'version':i['version'],'action':'reject','suggestion_id':i['suggestions'][0]['id'],'reason':'Não corresponde ao estabelecimento.'})
    assert r.status_code==200,r.text
    assert r.json()['items'][0]['suggestions']==[]
    assert r.json()['items'][0]['history'][-1]['action']=='reject'


def test_possible_candidate_accept_never_auto_creates_lead(auth,monkeypatch):
    stub(monkeypatch,[record(address='Rua Azul, 10')]);b=intake(auth,[record(latitude=None,longitude=None)]).json()
    start(auth,b,allow_external=True);tick();b=read(auth,b);i=b['items'][0]
    assert i['suggestions'] and i['status']=='pending'
    r=auth.post(f"{URL}/batches/{b['id']}/items/{i['id']}/decision",json={'version':i['version'],'action':'accept','suggestion_id':i['suggestions'][0]['id'],'reason':'Conferi os dados do estabelecimento.'})
    assert r.status_code==200,r.text
    assert r.json()['counts']['ready']==1
    with SessionLocal() as db:assert db.scalar(select(func.count()).select_from(Lead))==0


def test_pause_cancel_fence_inflight_and_resume(auth,monkeypatch):
    b=pending(auth);start(auth,b,allow_external=True);b=read(auth,b)
    assert control(auth,b,'pause').status_code==200
    assert worker.claim() is None
    b=read(auth,b);assert control(auth,b,'resume').status_code==200
    def lookup(provider,row,reserve):
        reserve();latest=read(auth,b);assert control(auth,latest,'cancel').status_code==200
        return [record(address='Rua Azul, 10')],''
    monkeypatch.setattr(recovery,'lookup',lookup);tick();b=read(auth,b)
    assert b['recovery']['status']=='cancelled' and b['recovery']['calls']==1
    assert b['items'][0]['record']['latitude'] is None
    with SessionLocal() as db:assert db.get(ResearchExecutor,1).lease_until==0


def test_user_edit_fences_late_result(auth,monkeypatch):
    b=pending(auth);start(auth,b,allow_external=True)
    def lookup(provider,row,reserve):
        reserve();assert edit(auth,read(auth,b),city='Olinda').status_code==200
        return [record(address='Rua Azul, 10')],''
    monkeypatch.setattr(recovery,'lookup',lookup);tick();i=read(auth,b)['items'][0]
    assert i['record']['city']=='Olinda' and i['record']['latitude'] is None


def test_reservations_survive_retry_and_budget_stops(auth,monkeypatch):
    def lookup(provider,row,reserve):reserve();raise TimeoutError('secret provider URL must never appear')
    monkeypatch.setattr(recovery,'lookup',lookup);b=pending(auth);start(auth,b,allow_external=True,limit=1);tick()
    with SessionLocal() as db:
        job=db.scalar(select(AbsorptionRecovery));job.retry_at=0;db.commit()
    tick();b=read(auth,b)
    assert b['recovery']['calls']==1 and b['recovery']['status']=='partial'
    assert 'secret' not in json.dumps(b)


def test_expired_claim_recovers_with_single_result(auth,monkeypatch):
    stub(monkeypatch,[record(address='Rua Azul, 10')]);b=pending(auth);start(auth,b,allow_external=True)
    old=worker.claim()
    with SessionLocal() as db:
        db.get(ResearchExecutor,1).lease_until=0;job=db.get(AbsorptionRecovery,old['id']);job.lease_until=0;db.commit()
    tick();assert worker.execute(old) is False
    b=read(auth,b);assert b['counts']['ready']==1 and len(b['items'][0]['history'])==1


def test_duplicate_human_decision_survives_commit(auth):
    b=intake(auth,[record('Mesma marca',latitude=None,longitude=None),record('Mesma marca')]).json()
    commit(auth,b);b=read(auth,b)
    # Reclassification after canonical lead creation identifies a possible duplicate.
    b=edit(auth,b,category='Cafeteria').json();i=b['items'][0];assert i['matches']
    r=auth.post(f"{URL}/batches/{b['id']}/items/{i['id']}/decision",json={'version':i['version'],'action':'duplicate','reason':'Conferi que é a mesma unidade.'})
    assert r.status_code==200,r.text
    assert commit(auth,r.json()).json()['items'][0]['status']=='duplicate'


def test_new_routes_bola_csrf_and_recovery_idempotency(auth):
    b=pending(auth);key=str(uuid4());data={'version':b['version'],'request_key':key}
    r=auth.post(f"{URL}/batches/{b['id']}/recover",json=data);assert r.status_code==202
    assert auth.post(f"{URL}/batches/{b['id']}/recover",json=data).json()['recovery']['id']==r.json()['recovery']['id']
    assert auth.patch(f"{URL}/batches/{b['id']}/items/{b['items'][0]['id']}",headers={'X-CSRF-Token':'bad'},json={}).status_code==403
    with SessionLocal() as db:
        other=User(email='alien@example.com',password_hash='unused',email_verified_at=1);db.add(other);db.flush()
        from backend.absorption_models import AbsorptionBatch
        db.get(AbsorptionBatch,b['id']).user_id=other.id;db.commit()
    assert edit(auth,b,category='Outra').status_code==404
    assert start(auth,b).status_code==404
    assert control(auth,r.json(),'cancel').status_code==404


def test_geo_adapter_uses_boundary_only_and_observed_poi(monkeypatch):
    from backend.providers import GeoapifyProvider
    provider=object.__new__(GeoapifyProvider);provider.api_key='synthetic-only';provider.timeout=8
    provider._geocode=lambda query:{'place_id':'city-boundary','city':'Recife','country_code':'br','lat':0,'lon':0}
    captured=[]
    def request(path,params,**kwargs):
        captured.append((path,params,kwargs))
        return {'features':[{'properties':{'place_id':'poi-123','name':'Café Atlântico','city':'Recife','country_code':'br',
            'lat':-8.065432,'lon':-34.876543,'formatted':'Rua Azul, 10','categories':['catering.cafe']}}]}
    provider._request_json=request
    reserved=[];rows,error=recovery.lookup(provider,record(address='Rua Azul, 10',latitude=None,longitude=None),lambda:reserved.append(1))
    assert not error and len(rows)==1
    assert rows[0]['latitude']==-8.065432 and rows[0]['source_id']=='poi-123'
    assert captured[0][1]['filter']=='place:city-boundary' and captured[0][1]['limit']==5
    assert len(reserved)==2
    provider._request_json=lambda *a,**k:{'features':[{'properties':{'name':'Café Atlântico','place_id':'bad','lat':0,'lon':0}}]}
    rows,error=recovery.lookup(provider,record(),lambda:None);assert not rows


def test_geo_wrong_city_boundary_and_unsupported_sources_are_safe():
    from backend.providers import GeoapifyProvider
    provider=object.__new__(GeoapifyProvider)
    provider._geocode=lambda query:{'place_id':'wrong','city':'Olinda','country_code':'br','lat':0,'lon':0}
    rows,error=recovery.lookup(provider,record(),lambda:None);assert not rows and error
    rows,error=recovery.lookup(object(),record(),lambda:pytest.fail('unsupported provider must not reserve'));assert not rows and error


def test_recovery_deadline_and_three_crashes_stop(auth):
    b=pending(auth);start(auth,b)
    with SessionLocal() as db:
        job=db.scalar(select(AbsorptionRecovery));job.deadline=int(time.time())-1;db.commit()
    assert worker.claim() is None
    assert read(auth,b)['recovery']['status']=='partial'
    b=read(auth,b);start(auth,b)
    with SessionLocal() as db:
        job=db.scalar(select(AbsorptionRecovery).where(AbsorptionRecovery.status=='pending'));job.attempts=3;db.commit()
    assert worker.claim() is None


def test_concurrent_edits_only_one_version_wins(auth):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    b=pending(auth);barrier=Barrier(2)
    def change(category):barrier.wait();return edit(auth,b,category=category).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:statuses=list(pool.map(change,['Padaria','Cafeteria']))
    assert sorted(statuses)==[200,409]


def test_cross_batch_source_identifiers_are_retained_after_commit(auth):
    first=preview(auth,[record(source_name='geoapify',source_id='fixed-poi')]).json();commit(auth,first)
    second=intake(auth,[record(source_name='geoapify',source_id='fixed-poi',city='',latitude=None,longitude=None)]).json()
    assert second['counts']['duplicate']==1


def test_recheck_releases_duplicate_after_earlier_record_correction(auth):
    first=preview(auth,[record('Mesmo local')]).json();second=preview(auth,[record('Mesmo local')]).json()
    assert second['counts']['duplicate']==1
    assert edit(auth,first,name='Outro estabelecimento').status_code==200
    refreshed=auth.post(f"{URL}/batches/{second['id']}/recheck")
    assert refreshed.status_code==200 and refreshed.json()['counts']['ready']==1


def test_latest_recovery_sequence_does_not_depend_on_uuid_order(auth,monkeypatch):
    b=pending(auth)
    first=start(auth,b).json();assert control(auth,first,'cancel').status_code==200
    second=start(auth,read(auth,b)).json()
    assert second['recovery']['id']!=first['recovery']['id']
    assert second['recovery']['status']=='pending'


def test_cached_candidates_are_owned_and_avoid_provider_calls(auth,monkeypatch):
    from backend.location_budget import LocationCache
    from backend.absorption import fingerprint,canonical_json
    from backend import main
    b=pending(auth);record_data=b['items'][0]['record']
    with SessionLocal() as db:
        user=db.scalar(select(User));provider=main.radar_provider
        cache_key=fingerprint(['absorption-v1',user.id,record_data,getattr(provider,'name',''),getattr(provider,'base_url',''),getattr(provider,'api_key','')])
        candidates=recovery.candidates_for(record_data,[record(address='Rua Azul, 10')],'geoapify')
        db.add(LocationCache(id=cache_key,user_id=user.id,expires_at=int(time.time())+60,payload=canonical_json(candidates)));db.commit()
    monkeypatch.setattr(recovery,'lookup',lambda *a:pytest.fail('must reuse owned cache'))
    start(auth,b,allow_external=True);tick();b=read(auth,b)
    assert b['counts']['ready']==1 and b['recovery']['calls']==0
    assert b['items'][0]['history'][0]['provenance']['cache'] is True


def test_worker_actual_metering_and_global_budget(auth,monkeypatch):
    from backend.providers import GeoapifyProvider
    from backend import providers,consumption
    from backend.autonomy_models import ProviderOperation,WorkAttempt
    provider=object.__new__(GeoapifyProvider);provider.api_key='synthetic';provider.base_url='https://api.geoapify.com';provider.timeout=8;provider.user_agent='test'
    provider._geocode=lambda query:{'place_id':'boundary','city':'Recife','country_code':'br'}
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,*args):return json.dumps({'features':[{'properties':{'name':'Café Atlântico','place_id':'poi','city':'Recife','country_code':'br','lat':-8.065432,'lon':-34.876543,'formatted':'Rua Azul, 10','categories':['catering.cafe']}}]}).encode()
    monkeypatch.setattr(providers,'urlopen',lambda *a,**k:Response())
    b=pending(auth);start(auth,b,allow_external=True);task=tick(provider);b=read(auth,b)
    assert b['counts']['ready']==1 and b['recovery']['calls']==2
    with SessionLocal() as db:
        operation=db.scalar(select(ProviderOperation).where(ProviderOperation.token==task['token']))
        assert operation.provider=='geoapify' and operation.status=='completed'
        assert db.get(WorkAttempt,task['token']).kind=='absorption'
    # Another user-visible company cannot bypass the shared HTTP budget.
    b=intake(auth,[record('Outro café',address='Rua Azul, 10',latitude=None,longitude=None)]).json()
    monkeypatch.setattr(consumption,'HTTP_BUDGET',0)
    start(auth,b,allow_external=True);tick(provider);b=read(auth,b)
    assert b['recovery']['status']=='partial' and b['counts']['pending']==1


def test_geographic_state_conflict_and_admin_feature_never_fill_company():
    from backend.providers import GeoapifyProvider
    provider=object.__new__(GeoapifyProvider);provider.api_key='synthetic'
    provider._geocode=lambda q:{'place_id':'city','city':'Recife','country_code':'br','state':'Outro estado','state_code':'XX'}
    rows,error=recovery.lookup(provider,record(state='PE'),lambda:None)
    assert not rows and 'Estado' in error
    provider._geocode=lambda q:{'place_id':'city','city':'Recife','country_code':'br'}
    provider._request_json=lambda *a,**kw:{'features':[{'properties':{'name':'Café Atlântico','place_id':'city','city':'Recife','country_code':'br','lat':0,'lon':0,'categories':['administrative.city']}}]}
    rows,error=recovery.lookup(provider,record(),lambda:None);assert not rows

@pytest.mark.parametrize('value',['NaN','Infinity','-Infinity','1e999'])
def test_nonfinite_json_is_rejected_before_original_can_break_response(auth,value):
    response=auth.post(URL+'/intake',json={'raw':'[{"name":"Invalid","rating":'+value+'}]','request_key':str(uuid4())})
    assert response.status_code==422


def test_numeric_normalization_finite_scientific_and_comma():
    value,issues=normalize(record(latitude='-8.065e-1',longitude='-,5'))
    assert not issues and value['latitude']==-.8065 and value['longitude']==-.5
    value,issues=normalize(record(latitude='1e999'))
    assert issues and value['latitude'] is None
