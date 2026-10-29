import json
import time
from uuid import uuid4
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import select, delete, func
from backend import main, semantic_intent as semantic
from backend.db import SessionLocal
from backend.models import User, Lead, LeadResearch
from backend.search_intent import interpret
from backend.website_context import inspect, public_contacts, persist
from backend.opportunity_models import OpportunityEvidence
from backend import discovery_plan

TEXT = 'Clínicas odontológicas em Recife, Brasil com WhatsApp'


@pytest.fixture
def semantic_config(auth, monkeypatch):
    for key, value in {'ENABLED':'true','MODEL':'controlled-model','API_KEY':'synthetic-not-a-real-key',
                       'DAILY_TOKENS':'200000','USER_DAILY_TOKENS':'100000','MAX_OUTPUT_TOKENS':'2048'}.items():
        monkeypatch.setenv('SCOUT_SEMANTIC_' + key, value)
    with SessionLocal() as db:
        db.execute(delete(semantic.SemanticAttempt)); db.commit()
        return db.scalar(select(User.id))


def output(intent=None):
    return {'status':'completed','usage':{'total_tokens':500},'output':[{'type':'message','content':[
        {'type':'output_text','text':(intent or interpret(TEXT)).model_dump_json()}]}]}


def test_semantic_opt_in_and_configuration_are_fail_closed(auth, monkeypatch):
    monkeypatch.delenv('SCOUT_SEMANTIC_ENABLED', raising=False)
    monkeypatch.setattr(semantic, 'request_model', lambda *a: pytest.fail('network must not run'))
    assert not auth.get('/api/smart-searches/interpretation-config').json()['available']
    result=auth.post('/api/smart-searches/interpret',json={'text':TEXT,'mode':'semantic','request_key':str(uuid4())}).json()
    assert result['interpretation']['mode']=='deterministic'
    assert result['intent']==interpret(TEXT).model_dump()
    assert auth.post('/api/smart-searches/interpret',json={'text':TEXT,'mode':'semantic'}).status_code==422


def test_semantic_schema_and_request_have_no_tools_or_retention(semantic_config, monkeypatch):
    calls=[]
    def model(body,cfg):
        calls.append(body)
        assert body['store'] is False and 'tools' not in body
        assert body['model']=='controlled-model'
        assert body['text']['format']['strict'] is True
        assert body['text']['format']['schema']['additionalProperties'] is False
        return output()
    monkeypatch.setattr(semantic,'request_model',model)
    key=str(uuid4())
    intent, meta=semantic.interpret_optional(TEXT,50,semantic_config,key)
    assert meta['mode']=='semantic' and intent==interpret(TEXT)
    _, repeated=semantic.interpret_optional(TEXT,50,semantic_config,key)
    assert repeated['mode']=='deterministic' and len(calls)==1
    with SessionLocal() as db:
        row=db.scalar(select(semantic.SemanticAttempt))
        assert row.status=='completed' and row.actual_tokens==500 and row.reserved_tokens>500
        assert row.input_hash!=TEXT


@pytest.mark.parametrize('bad', ['extra','country','city','target','sector','conflict','refusal','incomplete','missing','overspend'])
def test_semantic_validation_and_ambiguity(semantic_config,monkeypatch,bad):
    intent=interpret(TEXT).model_dump(); response=output()
    if bad=='extra': intent['role']='admin'
    if bad=='country': intent['market']['country']='US'
    if bad=='city': intent['market']['city']='Lisboa'
    if bad=='target': intent['target']=100
    if bad=='sector': intent['sectors']=['invented']
    if bad=='conflict': intent['exclusions'].append('odontologia')
    if bad=='missing': del intent['query']
    response['output'][0]['content'][0]['text']=json.dumps(intent)
    if bad=='refusal': response['output'][0]['content']=[{'type':'refusal','refusal':'No'}]
    if bad=='incomplete': response['status']='incomplete'
    if bad=='overspend': response['usage']['total_tokens']=999999
    monkeypatch.setattr(semantic,'request_model',lambda *a:response)
    result, meta=semantic.interpret_optional(TEXT,50,semantic_config,str(uuid4()))
    if bad=='country':
        assert result.unresolved and meta['mode']=='semantic'
    else:
        assert meta['mode']=='deterministic' and result==interpret(TEXT)


def test_semantic_failure_reservation_survives_and_hides_error(semantic_config,monkeypatch):
    def fail(*args): raise TimeoutError('secret input private@example.com')
    monkeypatch.setattr(semantic,'request_model',fail)
    _, meta=semantic.interpret_optional(TEXT,50,semantic_config,str(uuid4()))
    assert 'secret' not in str(meta) and 'private@' not in str(meta)
    with SessionLocal() as db:
        attempt=db.scalar(select(semantic.SemanticAttempt))
        assert attempt.status=='fallback' and attempt.reserved_tokens>0
        # An account deletion must not release global consumed budget.
        db.delete(db.get(User,semantic_config));db.commit()
        assert db.get(semantic.SemanticAttempt,attempt.id).reserved_tokens>0


def test_semantic_parallel_budget_and_crash_reservation(semantic_config,monkeypatch):
    cfg=semantic.configuration(); reserve=len(json.dumps(semantic.payload(TEXT,50,cfg),ensure_ascii=False).encode())+4096+cfg['output']
    monkeypatch.setenv('SCOUT_SEMANTIC_DAILY_TOKENS',str(reserve))
    monkeypatch.setenv('SCOUT_SEMANTIC_USER_DAILY_TOKENS',str(reserve))
    calls=[]
    def model(*args): calls.append(1);return output()
    monkeypatch.setattr(semantic,'request_model',model)
    with ThreadPoolExecutor(max_workers=2) as pool:
        values=list(pool.map(lambda _:semantic.interpret_optional(TEXT,50,semantic_config,str(uuid4())),range(2)))
    assert len(calls)==1 and sum(meta['mode']=='semantic' for _,meta in values)==1
    with SessionLocal() as db:
        row=db.scalar(select(semantic.SemanticAttempt));row.status='reserved';db.commit()
    _, meta=semantic.interpret_optional(TEXT,50,semantic_config,str(uuid4()))
    assert meta['mode']=='deterministic' and len(calls)==1


def page(**values):
    defaults=dict(final_url='https://example.org/',links=[],form_count=0,booking=False,truncated=False)
    defaults.update(values)
    return SimpleNamespace(**defaults)


def test_contact_exact_hosts_and_no_guessed_people_or_ambiguous_values():
    snapshot=page(links=[('https://evil.test/?u=wa.me/5581999999999',''),
        ('https://instagram.com.evil.test/person',''),('https://wa.me/5581999999999?text=123456',''),
        ('mailto:business@example.org?subject=Hi',''),('mailto:a@example.org,b@example.org',''),
        ('https://api.whatsapp.com/send?phone=5581999999999&text=123',''),
        ('tel:+55 (81) 99999-9999',''),('https://instagram.com/p/123',''),
        ('https://instagram.com/business','')])
    contacts=public_contacts(snapshot)
    assert {c['field'] for c in contacts}=={'email','whatsapp','phone','instagram'}
    assert len(contacts)==4
    assert next(c['value'] for c in contacts if c['field']=='whatsapp')=='5581999999999'
    assert all(not c['contact_authorized'] for c in contacts)
    from backend.research import _extract_contacts
    snapshot.links.append(('tel:5581888888888',''))
    assert _extract_contacts(snapshot)['phone']==''


def test_context_does_not_infer_missing_on_truncated_snapshot():
    assert inspect([page(truncated=True)])['checks']==[]
    complete=inspect([page(links=[('https://example.org/services','Serviços')])])
    assert complete['checks'][0]['state']=='pass'
    assert not any('score' in key for key in complete)


def test_context_persists_scoped_evidence_provenance_and_preserves_operator(auth,lead_data):
    lead_id=auth.post('/api/leads',json=lead_data).json()['id']
    now=int(time.time())
    home=page(links=[('tel:5581777777777',''),('mailto:business@example.org','')])
    other=page(final_url='https://example.org/contact',links=[('tel:5581666666666','')])
    with SessionLocal() as db:
        lead=db.get(Lead,lead_id); user=db.get(User,lead.user_id); before=lead.phone
        research=main._persist_research_result(db,user,lead,dict(status='confirmed',provider='controlled',website_url=home.final_url,
            website_status='poor',checked_at=now,page={'pages_checked':1},context=inspect([home])))
        research.audit_json=json.dumps({'pages':[{'url':home.final_url},{'url':other.final_url}]})
        persist(db,lead,research,inspect([home,other]),now+1);db.commit()
        assert lead.phone==before
        profile=json.loads(lead.enrichment_json)
        assert len(profile['observed_contacts'])==3
        evidence=db.scalars(select(OpportunityEvidence).where(OpportunityEvidence.lead_id==lead_id)).all()
        assert {e.source_url for e in evidence}=={home.final_url,other.final_url}
        assert all(e.classification=='probable' for e in evidence)
        assert all(e.user_id==lead.user_id for e in evidence)
    assert auth.get('/api/leads/'+lead_id+'/research').status_code==200


def test_unverified_research_never_enriches_contacts():
    from backend.enrichment import research_values
    assert research_values({'status':'unverified','website_url':'https://homonym.test','contacts':{'phone':'5581999999999'}})=={}


def test_adaptive_plan_covers_then_allocates_and_preserves_cursors():
    coverage=[{'sector':s,'supported':s!='industria','pagination':True} for s in ['clinica','restaurante','industria']]
    info=dict(coverage=coverage,plan=discovery_plan.initialize(coverage),candidates=[],sector=0,offset=0)
    discovery_plan.choose(info); assert info['sector']==0
    discovery_plan.record(info,SimpleNamespace(scanned=10,results=[1],complete=False),['a'])
    info['candidates']=[{'id':'a','group':'qualified'}]
    discovery_plan.choose(info); assert info['sector']==1 and info['offset']==0
    discovery_plan.record(info,SimpleNamespace(scanned=5,results=[2],complete=False),['b'])
    info['candidates'].append({'id':'b','group':'discarded'})
    discovery_plan.choose(info); assert info['sector']==0 and info['offset']==10
    recovered=json.loads(json.dumps(info));discovery_plan.choose(recovered)
    assert recovered==info and recovered['plan']['steps'][2]['exhausted']
    # Two repeated pages exhaust this sector, not all other sectors.
    for _ in range(2): discovery_plan.record(info,SimpleNamespace(scanned=10,results=[1],complete=False),['a'])
    discovery_plan.choose(info); assert info['sector']==1


def test_new_plan_runs_inside_existing_worker(auth,monkeypatch):
    from test_smart_search import Source, candidate, start, run_until_idle
    from backend import research_worker
    monkeypatch.setattr(research_worker,'MODE','worker')
    class Mixed(Source):
        def capabilities(self,sector): return {'supported':sector!='industria','pagination':True,'coverage':'Controlled','reason':''}
    source=Mixed([[candidate(1)],[candidate(2)]])
    job=start(auth,monkeypatch,source,sectors=['industria','odontologia'])
    run_until_idle(source)
    result=auth.get('/api/smart-searches/'+job['id']).json()
    assert result['counters']['qualified']==2 and result['plan']['steps'][0]['pages']==0
    assert result['plan']['steps'][1]['pages']==2


def test_interpretation_requires_authentication_and_csrf(client):
    assert client.get('/api/smart-searches/interpretation-config').status_code==401
    login=client.post('/api/auth/login',json={'email':'test@example.com','password':'testing-password-123!'})
    assert login.status_code==200
    assert client.post('/api/smart-searches/interpret',json={'text':TEXT}).status_code==403


def test_quality_metrics_count_errors_and_do_not_fake_empty_precision():
    from backend.selection_quality import metrics
    rows=[{'expected':True,'selected':True,'score':80}, {'expected':False,'selected':True,'score':90},
          {'expected':True,'selected':False,'score':40},{'expected':False,'selected':False,'score':10}]
    result=metrics(rows,k=2)
    assert (result['tp'],result['fp'],result['fn'],result['tn'])==(1,1,1,1)
    assert result['precision']==result['recall']==result['precision_at_k']==0.5
    assert 0 < result['ndcg_at_k'] < 1
    assert metrics([])['precision'] is None and metrics([])['ndcg_at_k'] is None


def test_controlled_quality_preserves_score_and_discloses_missing_real_labels():
    from scripts.evaluate_commercial_quality import evaluate
    result=evaluate()
    assert result['candidate_v134']==result['baseline_v133']
    assert result['human_reviewed_cases']==0 and result['real_commercial_quality'] is None
