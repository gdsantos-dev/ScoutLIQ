import json
import time
from uuid import uuid4
from sqlalchemy import select
from backend.db import SessionLocal
from backend.models import Lead, LeadResearch, ResearchBatchItem, ResearchExecutor, ResearchBatch, LeadActivity
from backend.opportunity_models import OpportunityEvidence
from backend import main, research_worker as worker
from backend.research import ResearchError
from test_opportunity_workflow import setup_flow, approve
from backend.models import RadarSavedSearch
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor

def test_reconcile_contradiction_and_collection_failure(auth, lead_data):
    lead, base, _, _, draft = setup_flow(auth, lead_data)
    with SessionLocal() as db:
        obj = db.get(Lead, lead['id'])
        r = LeadResearch(user_id=obj.user_id, lead_id=obj.id, status='confirmed', website_url='https://example.org',
            checked_at=int(time.time()), checks_json='[{"key":"viewport","state":"fail"}]')
        db.add(r); db.commit()
    assert auth.post(base+'/evidence/capture').json()['added'] == 1
    with SessionLocal() as db:
        r = db.scalar(select(LeadResearch).where(LeadResearch.lead_id == lead['id']))
        r.checked_at += 1; db.commit()
    assert auth.post(base+'/evidence/capture').json()['added'] == 0
    with SessionLocal() as db:
        r = db.scalar(select(LeadResearch).where(LeadResearch.lead_id == lead['id']))
        r.checked_at += 1; r.checks_json='[{"key":"viewport","state":"pass"}]'; db.commit()
    assert auth.post(base+'/evidence/capture').json()['added'] == 1
    data = auth.get(base+'/workflow').json()
    assert sum(e['relation']=='superseded' for e in data['evidence']) == 1
    assert data['insight']['reliability']['state'] == 'divergent'
    with SessionLocal() as db:
        r = db.scalar(select(LeadResearch).where(LeadResearch.lead_id == lead['id']))
        r.status='error'; r.checked_at += 1; db.commit()
    assert auth.post(base+'/evidence/capture').status_code == 409
    assert len(auth.get(base+'/workflow').json()['evidence']) == 3
    assert any(a['metadata'].get('event') == 'evidence_contradicted' for a in auth.get(base+'/activities').json())

def test_coverage_not_a_confirmed_ratio_and_action_has_command(auth, lead_data):
    lead, base, _, _, _ = setup_flow(auth, lead_data)
    flow=auth.get(base+'/workflow').json()
    assert flow['score']==lead['score']
    assert flow['insight']['coverage']['investigated']==['content']
    assert flow['insight']['coverage']['missing']
    assert flow['recommendation']['command']=='draft'
    assert flow['recommendation']['as_of'] > 0

def test_english_manual_assertion_requires_reviewed_translation(auth, lead_data):
    _, base, evidence, payload, _ = setup_flow(auth, lead_data)
    auth.patch(base+'/evidence/'+evidence['id'], json={'version':evidence['version'],
        'classification':'confirmed','reason':'Nova revisão sem tradução fornecida.'})
    response=auth.post(base+'/outreach/drafts',json={**payload,'request_id':str(uuid4()),'locale':'en-US'})
    assert response.status_code == 409
    assert 'tradução' in response.json()['detail']

def test_content_approval_is_not_send_permission(auth, lead_data):
    _, base, _, _, draft=setup_flow(auth,lead_data)
    response=auth.post(f"{base}/outreach/drafts/{draft['id']}/approve",json={'version':draft['version']})
    assert response.status_code==200
    assert response.json()['content_blocker']==''
    assert response.json()['eligibility_state']=='unknown'
    assert not response.json()['dispatch_available']

def test_exact_recipient_optout_across_leads_without_domain_merging(auth, lead_data):
    _, base, _, _, draft=setup_flow(auth,lead_data)
    _, other, _, payload, _=setup_flow(auth,{**lead_data,'name':'Outra identidade'})
    policy={'channel':'email','recipient':'CONTACT@example.org','blocked':True,'reason':'Destinatário pediu remoção por mensagem.','market':'BR'}
    response=auth.put(base+'/recipient-policy',json=policy)
    assert response.status_code==200, response.text
    assert auth.post(other+'/outreach/drafts',json={**payload,'request_id':str(uuid4())}).status_code==409
    assert auth.post(other+'/outreach/drafts',json={**payload,'request_id':str(uuid4()),'recipient':'another@example.org'}).status_code==201
    assert next(d for d in auth.get(other+'/workflow').json()['drafts'] if d['recipient']=='contact@example.org')['status']=='paused'
    assert auth.put(base+'/recipient-policy',json={**policy,'blocked':False,'version':0}).status_code==409

def test_policy_change_revokes_content_and_free_text_never_proves_permission(auth, lead_data):
    _, base, _, _, draft=setup_flow(auth,lead_data)
    approved=approve(auth,base,draft).json()
    result=auth.put(base+'/recipient-policy',json={'channel':'email','recipient':draft['recipient'],
        'basis':'explicit_permission','reference':'Operator declaration only','reason':'Registro fornecido para avaliação posterior.','market':'US'})
    assert result.status_code==200
    row=auth.get(base+'/workflow').json()['drafts'][0]
    assert row['status']=='draft' and row['content_blocker']
    assert row['eligibility_state']=='pending_verification'
    assert auth.post(f"{base}/outreach/drafts/{draft['id']}/dispatch",json={'version':approved['version']}).status_code==409

def test_strategy_preconditions_and_initial_no_unverified_claims(auth,lead_data):
    _,base,_,payload,_=setup_flow(auth,lead_data)
    assert auth.post(base+'/outreach/drafts',json={**payload,'request_id':str(uuid4()),'strategy':'follow_up'}).status_code==409
    initial=auth.post(base+'/outreach/drafts',json={**payload,'request_id':str(uuid4()),'strategy':'initial','evidence_ids':[],'locale':'en-US'})
    assert initial.status_code==201
    assert 'We design and maintain websites' in initial.json()['body']
    assert 'PDF' not in initial.json()['body']

class ControlledResearcher:
    def __init__(self, hook=None, failure=False): self.hook=hook; self.failure=failure
    def research(self, lead, locale):
        if self.hook: self.hook()
        if self.failure: raise ResearchError('SECRET-provider-details')
        return {'status':'confirmed','provider':'controlled','website_url':'https://example.org',
            'website_status':'poor','checked_at':int(time.time()),'checks':[{'key':'viewport','state':'fail'}]}

def batch(auth,lead_data,count=2):
    ids=[auth.post('/api/leads',json={**lead_data,'name':f'Controlled {i}'}).json()['id'] for i in range(count)]
    result=auth.post('/api/research/batches',json={'lead_ids':ids,'mode':'web','stale_days':0})
    assert result.status_code==201,result.text
    return result.json()['batch']['id']

def reset_delay():
    with SessionLocal() as db:
        db.get(ResearchExecutor,1).next_at=0
        for item in db.scalars(select(ResearchBatchItem)).all(): item.retry_at=0
        db.commit()

def test_claim_excludes_duplicate_and_commit_is_idempotent(auth,lead_data):
    identifier=batch(auth,lead_data)
    task=worker.claim()
    assert task and worker.claim() is None
    assert worker.execute(task,ControlledResearcher())
    assert worker.execute(task,ControlledResearcher()) is False
    assert auth.get(f'/api/research/batches/{identifier}').json()['batch']['processed']==1
    assert worker.execute(worker.claim(),ControlledResearcher())
    assert auth.get(f'/api/research/batches/{identifier}').json()['batch']['status']=='completed'

def test_simultaneous_executor_claims_have_one_winner(auth,lead_data):
    batch(auth,lead_data)
    with ThreadPoolExecutor(max_workers=2) as pool:
        claimed=list(pool.map(lambda _: worker.claim(),range(2)))
    assert sum(task is not None for task in claimed)==1

def test_crash_expiration_recovers_and_fences_old_executor(auth,lead_data):
    identifier=batch(auth,lead_data,1)
    lost=worker.claim()
    with SessionLocal() as db:
        db.get(ResearchExecutor,1).lease_until=0
        db.get(ResearchBatchItem,lost['id']).lease_until=0
        db.commit()
    recovered=worker.claim()
    assert recovered['token']!=lost['token']
    assert worker.execute(lost,ControlledResearcher()) is False
    assert worker.execute(recovered,ControlledResearcher())
    data=auth.get(f'/api/research/batches/{identifier}').json()['batch']
    assert data['done']==1 and data['items'][0]['attempts']==2

def test_pause_and_cancel_during_request_discard_results(auth,lead_data):
    identifier=batch(auth,lead_data,1)
    task=worker.claim()
    assert not worker.execute(task,ControlledResearcher(hook=lambda: auth.post(f'/api/research/batches/{identifier}/pause')))
    assert auth.get(f'/api/research/batches/{identifier}').json()['batch']['status']=='paused'
    assert worker.claim() is None
    auth.post(f'/api/research/batches/{identifier}/resume')
    task=worker.claim()
    assert not worker.execute(task,ControlledResearcher(hook=lambda: auth.post(f'/api/research/batches/{identifier}/cancel')))
    assert auth.get(f'/api/research/batches/{identifier}').json()['batch']['status']=='cancelled'
    with SessionLocal() as db: assert not db.scalar(select(LeadResearch.id))

def test_provider_backoff_limit_and_no_exception_leak(auth,lead_data):
    identifier=batch(auth,lead_data,1)
    for attempt in range(3):
        reset_delay()
        task=worker.claim(); assert task
        worker.execute(task,ControlledResearcher(failure=True))
        if attempt<2: assert worker.claim() is None
    data=auth.get(f'/api/research/batches/{identifier}').json()['batch']
    assert data['errors']==1 and data['items'][0]['attempts']==3
    assert 'SECRET' not in json.dumps(data)

def test_worker_mode_rejects_browser_execution_and_budget_is_persistent(auth,lead_data,monkeypatch):
    identifier=batch(auth,lead_data)
    monkeypatch.setattr(worker,'MODE','worker')
    assert auth.post(f'/api/research/batches/{identifier}/step').status_code==409
    monkeypatch.setattr(worker,'BUDGET',1)
    worker.execute(worker.claim(),ControlledResearcher())
    assert worker.claim() is None

def test_monitor_uses_existing_search_and_server_authority(auth, monkeypatch):
    monkeypatch.setattr(worker, 'MODE', 'worker')
    saved = auth.post('/api/radar/saved-searches', json={'name':'Controlled monitor',
        'query':{'location':'Recife','country':'BR'},'result_ids':[]}).json()
    enabled = auth.patch(f"/api/radar/saved-searches/{saved['id']}/monitor", json={
        'version':saved['version'],'enabled':True,'interval':'daily'})
    assert enabled.status_code==200, enabled.text
    assert auth.post(f"/api/radar/saved-searches/{saved['id']}/schedule").status_code==200
    class Provider:
        name='controlled'
        def search(self, query):
            return SimpleNamespace(results=[], provider='controlled',location_label='Recife',
                                   complete=True,scanned=0,result_limit=None,scope='region')
    monkeypatch.setattr(main,'radar_provider',Provider())
    task=worker.claim()
    assert task['kind']=='smart'  # Historical monitors share the search executor.
    assert worker.execute(task,provider=Provider())
    updated=auth.get('/api/radar/saved-searches').json()[0]
    assert updated['last_monitor_at'] and updated['next_monitor_at']>int(time.time())
    assert not updated['worker_error']
    assert auth.patch(f"/api/radar/saved-searches/{saved['id']}/results",json={
        'version':updated['version'],'result_ids':[]}).status_code==409

def test_legacy_evidence_can_be_recaptured_without_duplicate_key(auth,lead_data):
    lead=auth.post('/api/leads',json=lead_data).json()
    now=int(time.time())
    with SessionLocal() as db:
        l=db.get(Lead,lead['id'])
        db.add(LeadResearch(user_id=l.user_id,lead_id=l.id,status='confirmed',website_url='https://example.org',
            checked_at=now,checks_json='[{"key":"viewport","state":"fail"}]'))
        db.add(OpportunityEvidence(user_id=l.user_id,lead_id=l.id,source_key=f'research:{now}:viewport',
            statement='Requer verificação.',source_url='https://example.org',method='research_snapshot',
            classification='confirmed',observed_at=now,valid_until=now+86400))
        db.commit()
    base=f"/api/leads/{lead['id']}"
    assert auth.post(base+'/evidence/capture').status_code==200
    rows=auth.get(base+'/workflow').json()['evidence']
    assert len(rows)==1 and rows[0]['classification']=='probable'
    assert rows[0]['observation_key']=='viewport'

def test_contradiction_at_capacity_removes_old_claim_from_use(auth, lead_data):
    lead=auth.post('/api/leads',json=lead_data).json()
    now=int(time.time())
    with SessionLocal() as db:
        obj=db.get(Lead,lead['id'])
        for i in range(200):
            db.add(OpportunityEvidence(user_id=obj.user_id,lead_id=obj.id,source_key=f'capacity:{i}',
                statement='A página não contém viewport.',source_url='https://example.org',method='research_snapshot',
                classification='confirmed',observed_at=now-1,valid_until=now+86400,category='mobile',
                observation_key='viewport' if i==0 else '',observation_state='fail'))
        db.add(LeadResearch(user_id=obj.user_id,lead_id=obj.id,status='confirmed',website_url='https://example.org',
            checked_at=now,checks_json='[{"key":"viewport","state":"pass"}]'))
        db.commit()
    base=f"/api/leads/{lead['id']}"
    assert auth.post(base+'/evidence/capture').status_code==200
    rows=auth.get(base+'/workflow').json()['evidence']
    old=next(e for e in rows if e['observation_key']=='viewport')
    assert old['relation']=='superseded'
    assert len(rows)==200
    assert any(a['metadata'].get('event')=='evidence_contradicted_at_capacity' for a in auth.get(base+'/activities').json())
