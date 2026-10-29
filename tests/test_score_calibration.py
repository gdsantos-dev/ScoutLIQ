import copy
import json
from uuid import uuid4
import pytest
from sqlalchemy import select
from backend.db import SessionLocal
from backend.models import Lead, LeadActivity
from backend.score_criteria import BASELINE
from backend.scoring import score
from backend.learning_models import CalibrationChange, ScoreConfiguration
from test_commercial_learning import record, preview, commit


def prepared(auth, lead_data):
    ids, evaluations = [], []
    for split in ('development','validation'):
        lead = auth.post('/api/leads', json={**lead_data,'name':'Caso '+split,'address':'Rua '+split}).json()
        ids.append(lead['id'])
        data=record(split,lead_id=lead['id'],split=split,classification='unsuitable')
        data.pop('company')
        p=preview(auth,[data]); assert p['valid']; assert commit(auth,p).status_code==200
        r=auth.post('/api/learning/evaluations',json={'request_key':str(uuid4()),'dataset':'ORLIQ revisão','split':split})
        assert r.status_code==200,r.text
        evaluations.append(r.json())
    return ids,evaluations


def proposal(auth, evaluations, **updates):
    return auth.post('/api/learning/calibrations/proposals',json={'request_key':str(uuid4()),
        'development_id':evaluations[0]['id'],'validation_id':evaluations[1]['id'], 'expected_version':0,
        'criteria':dict(BASELINE,selection_threshold=95),
        'reason':'Hipótese controlada: reduzir falsos positivos nesta amostra.',**updates})


def apply(auth,p,**updates):
    return auth.post('/api/learning/calibrations/proposals/'+p['id']+'/apply',json={
        'expected_version':p['base_version'],'report_hash':p['report_hash'],
        'approve_score_change':True,'acknowledge_sample_limits':True,**updates})


def test_proposal_is_offline_apply_and_rollback_preserve_history(auth,lead_data):
    ids,evaluations=prepared(auth,lead_data)
    with SessionLocal() as db:
        before=score(db.get(Lead,ids[0]))
    p=proposal(auth,evaluations).json()
    assert p['report']['development']['before']['metrics']['fp']==1
    assert p['report']['development']['after']['metrics']['fp']==0
    assert p['report']['validation']['improvements']==1
    assert p['report']['validation']['after']['metrics']['tn']==1
    with SessionLocal() as db: assert score(db.get(Lead,ids[0]))==before
    assert apply(auth,p,approve_score_change=False).status_code==422
    assert apply(auth,p,report_hash='0'*64).status_code==409
    changed=apply(auth,p)
    assert changed.status_code==200,changed.text
    assert apply(auth,p).json()==changed.json()
    with SessionLocal() as db:
        now=score(db.get(Lead,ids[0]))
        assert now['status']=='evaluated' and now['value']==before['value']
        assert now['previous']['status']==before['status']
        assert now['version'].startswith('3.0-')
        activity=db.scalars(select(LeadActivity).where(LeadActivity.lead_id==ids[0])).all()
        assert any(json.loads(a.metadata_json).get('event')=='score_calibration' for a in activity)
    new=auth.post('/api/leads',json={**lead_data,'name':'Novo após aprovação'}).json()
    with SessionLocal() as db: assert score(db.get(Lead,new['id']))['status']=='evaluated'
    original_eval=auth.get('/api/learning/evaluations/'+evaluations[0]['id']).json()
    assert original_eval['report']['metrics']['fp']==1
    undo=auth.post('/api/learning/calibrations/changes/'+changed.json()['id']+'/rollback',json={
        'expected_version':changed.json()['config_version'],'reason':'Reverter hipótese controlada para o Score padrão.','approve_score_change':True})
    assert undo.status_code==200,undo.text
    with SessionLocal() as db:
        after=score(db.get(Lead,ids[0])); after.pop('previous'); baseline=dict(before);baseline.pop('previous')
        assert after==baseline
        assert db.get(ScoreConfiguration,db.get(Lead,ids[0]).user_id).config_json=='{}'
        assert len(db.scalars(select(CalibrationChange)).all())==2
    assert len(auth.get('/api/learning/calibrations/changes').json()['changes'])==2


def test_invalid_weights_and_protected_gates(auth,lead_data):
    _,evaluations=prepared(auth,lead_data)
    for cfg in [dict(BASELINE,minimum_coverage=0),dict(BASELINE,need_threshold=0),dict(BASELINE,allow_blocked=True),
                dict(BASELINE,weights={'target_fit':100,'need':0,'impact':0,'viability':0,'activity':0}),
                dict(BASELINE,weights={**BASELINE['weights'],'activity':11})]:
        assert proposal(auth,evaluations,criteria=cfg).status_code==422


def test_stale_proposal_and_changed_human_reviews(auth,lead_data):
    ids,evaluations=prepared(auth,lead_data)
    p=proposal(auth,evaluations).json()
    data=record('development',lead_id=ids[0],split='development',classification='suitable',expected_version=1);data.pop('company')
    commit(auth,preview(auth,[data]))
    assert apply(auth,p).status_code==409
    assert auth.get('/api/learning/calibrations/configuration').json()['version']==0


def test_validation_data_cannot_be_used_as_development(auth,lead_data):
    _,evaluations=prepared(auth,lead_data)
    assert proposal(auth,evaluations,development_id=evaluations[1]['id']).status_code==422
    assert proposal(auth,evaluations,validation_id=str(uuid4())).status_code==404


def test_suggestion_uses_development_and_does_not_apply(auth,lead_data):
    _,evaluations=prepared(auth,lead_data)
    p=proposal(auth,evaluations,criteria=None)
    assert p.status_code==200,p.text
    assert p.json()['report']['method']=='development_threshold_search'
    assert auth.get('/api/learning/calibrations/configuration').json()['version']==0


def test_score_default_matches_full_134_on_controlled_variations():
    """Compare the current canonical path with the frozen 1.34 formula, including evidence gates."""
    from types import SimpleNamespace
    import random
    from backend.score_criteria import commercial_priority
    random.seed(135)
    for _ in range(1000):
        dims={k:{'value':random.choice([None,0,15,55,65,80,95]),'weight':w,'state':'verified','max':100,'reason':'controlled'} for k,w in BASELINE['weights'].items()}
        dims['viability']['value']=random.choice([None,0,80])
        fit={'status':random.choice(['compatible','incompatible','indeterminate'])}
        contradictory=random.choice([True,False]); dims['need']['state']='contradictory' if contradictory else 'verified'
        coverage=sum(d['weight'] for d in dims.values() if d['value'] is not None)
        value=round(sum(d['weight']*d['value'] for d in dims.values() if d['value'] is not None)/coverage) if coverage else 0
        need=dims['need']['value']; blocked=dims['viability']['value']==0; contact=dims['viability']['value']==80
        sufficient=coverage>=80 and dims['activity']['value'] is not None and need is not None and contact and fit['status']=='compatible' and not contradictory and not blocked
        state='qualified' if sufficient and value>=60 and need>=65 else 'evaluated' if sufficient else 'provisional' if coverage>=40 else 'insufficient'
        if fit['status']=='incompatible' or blocked:value,state=0,'incompatible'
        elif not sufficient:value=min(value,49)
        result=commercial_priority(dims,fit)
        assert (result['value'],result['status'],result['coverage'])==(value,state,coverage)


def test_block_active_discovery_and_mass_assignment(auth,lead_data):
    from backend.models import SmartSearch
    ids,evaluations=prepared(auth,lead_data)
    p=proposal(auth,evaluations).json()
    with SessionLocal() as db:
        user_id=db.get(Lead,ids[0]).user_id
        job=SmartSearch(user_id=user_id,request_key=str(uuid4()),intent_json='{}',state_json='{}',status='investigating',deadline=2000000000)
        db.add(job);db.commit()
    assert apply(auth,p).status_code==409
    with SessionLocal() as db: assert db.get(Lead,ids[0]).score_criteria_json=='{}'
    assert auth.post('/api/leads',json={**lead_data,'score_criteria_json':'{"weights":{}}'}).status_code==422


def test_calibration_and_rollback_cannot_cross_accounts(auth,lead_data):
    from backend.models import User
    from backend.security import hasher
    import time
    ids,evaluations=prepared(auth,lead_data)
    p=proposal(auth,evaluations).json()
    changed=apply(auth,p).json()
    with SessionLocal() as db:
        other=User(email='calibration-other@example.test',password_hash=hasher.hash('testing-password-123!'),email_verified_at=int(time.time()))
        db.add(other);db.commit()
    auth.post('/api/auth/logout')
    response=auth.post('/api/auth/login',json={'email':'calibration-other@example.test','password':'testing-password-123!'})
    auth.headers['X-CSRF-Token']=response.json()['csrf']
    assert auth.get('/api/learning/calibrations/proposals/'+p['id']).status_code==404
    assert apply(auth,p).status_code==404
    assert auth.post('/api/learning/calibrations/changes/'+changed['id']+'/rollback',json={
        'expected_version':changed['config_version'],'reason':'Outra conta não pode reverter os critérios.','approve_score_change':True}).status_code==404
    assert auth.get('/api/learning/calibrations/configuration').json()['version']==0
    exported=auth.get('/api/export').json()['commercial_learning']
    assert exported['cases']==exported['revisions']==exported['calibrations']==exported['criteria_history']==[]


def test_concurrent_apply_has_one_change(auth,lead_data):
    from concurrent.futures import ThreadPoolExecutor
    _,evaluations=prepared(auth,lead_data);p=proposal(auth,evaluations).json()
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses=list(pool.map(lambda _:apply(auth,p),range(2)))
    assert all(r.status_code==200 for r in responses)
    assert responses[0].json()==responses[1].json()
    with SessionLocal() as db: assert len(db.scalars(select(CalibrationChange)).all())==1
