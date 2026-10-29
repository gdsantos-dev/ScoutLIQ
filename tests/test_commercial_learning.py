import copy
import json
import time
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import select, func
from backend.db import SessionLocal
from backend.models import Lead, User, LeadActivity
from backend.learning_models import LearningCase, LearningRevision, LearningImport
from backend.security import hasher
from backend.scoring import score
from backend.selection_quality import reviewed_metrics


def record(key='orliq-001', **updates):
    return {'source': 'orliq_manual', 'external_id': key, 'dataset': 'ORLIQ revisão', 'split': 'validation',
        'company': {'name': 'Café Revisado ' + key, 'city': 'Recife', 'country': 'BR', 'sector': 'Cafeteria',
                    'address': 'Rua Controlada, ' + key},
        'reviewed_on': '2026-01-01', 'reviewer': 'Operador de teste', 'label_origin': 'human',
        'classification': 'suitable', 'justification': 'Caso controlado: atividade e necessidade verificadas.',
        'evidence': [{'statement': 'Site ausente na avaliação manual.', 'reference': 'Caderno ORLIQ, caso controlado 001'}],
        **updates}


def preview(auth, records, key=None):
    response = auth.post('/api/learning/imports/preview', json={'request_key': key or str(uuid4()), 'records': records})
    assert response.status_code == 200, response.text
    return response.json()


def commit(auth, value):
    return auth.post('/api/learning/imports/' + value['id'] + '/commit',
        json={'preview_hash': value['preview_hash'], 'confirm_human_reviews': True})


def test_preview_commit_idempotence_and_no_second_lead(auth):
    key = str(uuid4())
    p = preview(auth, [record()], key)
    assert p['valid'] and p['rows'][0]['action'] == 'create'
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(LearningCase)) == 0
    assert preview(auth, [record()], key) == p
    receipt = commit(auth, p)
    assert receipt.status_code == 200 and receipt.json()['created'] == 1
    assert commit(auth, p).json() == receipt.json()
    again = preview(auth, [record()])
    assert again['rows'][0]['action'] == 'unchanged'
    assert commit(auth, again).json()['unchanged'] == 1
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Lead)) == 0
        assert db.scalar(select(func.count()).select_from(LearningCase)) == 1
        assert db.scalar(select(func.count()).select_from(LearningRevision)) == 1
    response = auth.post('/api/learning/imports/preview', json={'request_key': key, 'records': [record(classification='unsuitable')]})
    assert response.status_code == 409


@pytest.mark.parametrize('bad', [dict(label_origin='ai'), dict(user_id='foreign'), dict(services=['invented']),
    dict(reviewed_on='2099-01-01'), dict(company=None), dict(outcome='won'), dict(expected_version=True)])
def test_per_record_errors_and_atomic_rejection(auth, bad):
    value = preview(auth, [record('valid'), record('bad', **bad)])
    assert not value['valid'] and value['rows'][1]['errors']
    assert commit(auth, value).status_code == 409
    assert auth.get('/api/learning/cases').json()['cases'] == []


def test_duplicate_identity_homonym_and_duplicate_record(auth):
    a = record()
    b = record('other', company=a['company'])
    assert not preview(auth, [a, b])['valid']
    assert not preview(auth, [a, a])['valid']
    p = preview(auth, [a]); assert commit(auth, p).status_code == 200
    assert not preview(auth, [b])['valid']
    b['company'] = dict(a['company'], address='Outra rua, 100')
    assert preview(auth, [b])['valid']  # Name/city alone do not merge businesses.


def test_correction_history_conflict_and_replay(auth):
    p = preview(auth, [record()]); receipt = commit(auth, p).json(); cid = receipt['cases'][0]['id']
    corrected = record(classification='unsuitable', expected_version=1, justification='Revisão humana corrigida: operação incompatível.')
    p2 = preview(auth, [corrected]); racing = preview(auth, [record(classification='uncertain', expected_version=1)])
    assert p2['rows'][0]['before']['record']['classification'] == 'suitable'
    assert commit(auth, p2).json()['updated'] == 1
    assert commit(auth, racing).status_code == 409
    history = auth.get(f'/api/learning/cases/{cid}/history').json()['revisions']
    assert [r['version'] for r in history] == [2, 1]
    assert [r['record']['classification'] for r in history] == ['unsuitable', 'suitable']
    assert all(r['human_attested'] for r in history)
    assert commit(auth, p).json() == receipt  # Old committed receipt never rewrites a correction.


def test_conflict_rolls_back_other_records(auth):
    p = preview(auth, [record()]); commit(auth, p)
    batch = preview(auth, [record('new'), record(classification='unsuitable', expected_version=1)])
    competing = preview(auth, [record(classification='uncertain', expected_version=1)]); commit(auth, competing)
    assert commit(auth, batch).status_code == 409
    assert len(auth.get('/api/learning/cases').json()['cases']) == 1


def test_linked_snapshot_history_score_preservation_and_stale_preview(auth, lead_data):
    lid = auth.post('/api/leads', json=lead_data).json()['id']
    data = record(lead_id=lid); data.pop('company')
    with SessionLocal() as db:
        lead = db.get(Lead, lid); before = score(lead); version = lead.version
    p = preview(auth, [data]); assert p['rows'][0]['system']['origin'] == 'scoutliq_live'
    assert p['rows'][0]['system']['score'] == before['value']
    assert commit(auth, p).status_code == 200
    with SessionLocal() as db:
        lead = db.get(Lead, lid)
        assert score(lead) == before and lead.version == version
        activity = db.scalar(select(LeadActivity).where(LeadActivity.lead_id == lid, LeadActivity.body == 'Revisão humana de oportunidade registrada.'))
        assert activity and json.loads(activity.metadata_json)['event'] == 'commercial_review'
    p2 = preview(auth, [dict(data, expected_version=1, classification='unsuitable')])
    with SessionLocal() as db:
        db.get(Lead, lid).contact_blocked = True; db.commit()
    assert commit(auth, p2).status_code == 409


def test_tenant_isolation_and_csrf(auth):
    p = preview(auth, [record()]); cid = commit(auth, p).json()['cases'][0]['id']
    result = auth.post('/api/learning/evaluations', json={'request_key':str(uuid4()),'dataset':'ORLIQ revisão','split':'validation'})
    eid = result.json()['id']
    with SessionLocal() as db:
        db.add(User(email='other@example.test', password_hash=hasher.hash('testing-password-123!'), email_verified_at=int(time.time())))
        db.commit()
    auth.post('/api/auth/logout')
    login = auth.post('/api/auth/login', json={'email':'other@example.test','password':'testing-password-123!'})
    auth.headers['X-CSRF-Token'] = login.json()['csrf']
    for path in [f'/cases/{cid}', f'/cases/{cid}/history', f'/imports/{p["id"]}', f'/evaluations/{eid}']:
        assert auth.get('/api/learning' + path).status_code == 404
    assert commit(auth, p).status_code == 404
    assert auth.get('/api/learning/cases').json()['cases'] == []
    auth.headers.pop('X-CSRF-Token')
    assert auth.post('/api/learning/imports/preview', json={'request_key':str(uuid4()),'records':[record()]}).status_code == 403


def test_foreign_lead_and_evidence_are_not_importable(auth, lead_data):
    with SessionLocal() as db:
        other = User(email='foreign@example.test', password_hash='unused'); db.add(other); db.flush()
        lead = Lead(user_id=other.id, **lead_data); db.add(lead); db.commit(); lid = lead.id
    data = record(lead_id=lid); data.pop('company')
    p = preview(auth, [data]); assert not p['valid']
    assert 'Registro não encontrado' in str(p['rows'][0]['errors'])
    p = preview(auth, [record(evidence=[{'statement':'Observação controlada', 'reference':'Arquivo manual 001','evidence_id':str(uuid4())}])])
    assert not p['valid']


def test_preview_hash_expiration_and_unattested_commit(auth):
    p = preview(auth, [record()])
    url = '/api/learning/imports/' + p['id'] + '/commit'
    assert auth.post(url,json={'preview_hash':'0'*64,'confirm_human_reviews':True}).status_code == 409
    assert auth.post(url,json={'preview_hash':p['preview_hash'],'confirm_human_reviews':False}).status_code == 422
    with SessionLocal() as db:
        db.get(LearningImport,p['id']).expires_at = 1; db.commit()
    assert commit(auth,p).status_code == 409


def test_bounded_import(auth):
    assert auth.post('/api/learning/imports/preview', json={'request_key':str(uuid4()), 'records':[record(str(i)) for i in range(51)]}).status_code == 422
    assert auth.post('/api/learning/imports/preview', content='x'*65537).status_code == 413


def test_evaluation_freezes_revisions_and_separates_outcomes(auth):
    observed = {'score':80, 'decision':'selected', 'criteria_version':'3.0', 'evaluated_on':'2026-01-01','reason':'Exportação de teste do Score existente.'}
    p = preview(auth, [record(system_observation=observed, outcome='no_reply',outcome_on='2026-01-02',outcome_reference='Histórico controlado 001')]); commit(auth,p)
    params = {'request_key':str(uuid4()),'dataset':'ORLIQ revisão','split':'validation','k':10}
    response = auth.post('/api/learning/evaluations',json=params)
    assert response.status_code == 200, response.text
    evaluated = response.json(); m = evaluated['report']['metrics']
    assert m['tp'] == 1 and m['precision'] == 1 and not m['sufficient_sample'] and m['effective_k'] == 1
    assert evaluated['report']['outcomes'] == {'no_reply':1}
    update = record(system_observation=observed,classification='unsuitable',expected_version=1)
    commit(auth,preview(auth,[update]))
    assert auth.post('/api/learning/evaluations',json=params).json() == evaluated
    frozen = auth.get('/api/learning/evaluations/'+evaluated['id']).json()
    assert frozen['cases'][0]['record']['classification'] == 'suitable'
    params['request_key'] = str(uuid4())
    assert auth.post('/api/learning/evaluations',json=params).json()['report']['metrics']['fp'] == 1
    params.update(request_key=str(uuid4()),split='development')
    assert auth.post('/api/learning/evaluations',json=params).status_code == 409


def test_metrics_distinguish_false_negatives_from_abstentions():
    cases = []
    for i,(human,decision,value) in enumerate([('suitable','selected',90),('unsuitable','selected',80),('suitable','rejected',70),('unsuitable','rejected',60),('suitable','abstained',None),('uncertain','selected',95)]):
        data = record(str(i),classification=human)
        data.update(review_status='reviewed',outcome='unknown'); data['company']['region']='PE'
        cases.append({'id':str(i),'version':1,'record':data,'system':{'origin':'scoutliq_live','criteria_version':'3.0','decision':decision,'score':value}})
    report = reviewed_metrics(cases,2); m=report['metrics']
    assert [m[k] for k in ('tp','fp','fn','tn')] == [1,1,1,1]
    assert m['precision'] == m['recall'] == m['precision_at_k'] == .5
    assert m['abstention_rate'] == .2 and m['abstained_positive'] == 1 and m['label_coverage'] == 5/6
    assert report['by_sector'][0]['cases'] == 6


def test_concurrent_commit_does_not_duplicate(auth):
    p = preview(auth,[record()])
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: commit(auth,p),range(2)))
    assert all(r.status_code == 200 for r in responses)
    assert responses[0].json() == responses[1].json()
    assert len(auth.get('/api/learning/cases').json()['cases']) == 1


def test_export_and_existing_evaluator_use_reviewed_cases(auth,tmp_path):
    import subprocess
    import sys
    p=preview(auth,[record()]);commit(auth,p)
    exported=auth.get('/api/export').json()
    assert len(exported['commercial_learning']['cases'])==1
    assert len(exported['commercial_learning']['revisions'])==1
    source=tmp_path/'export.json';output=tmp_path/'report.json'
    source.write_text(json.dumps(exported),encoding='utf-8')
    process=subprocess.run([sys.executable,'scripts/evaluate_commercial_quality.py','--reviewed-export',str(source),
        '--dataset','ORLIQ revisão','--split','validation','--output',str(output)],capture_output=True,text=True)
    assert process.returncode==0,process.stderr
    report=json.loads(output.read_text(encoding='utf-8'))
    assert report['report']['metrics']['cases']==1 and report['report']['metrics']['abstention_rate']==1
    assert report['human_reviews_declared_not_independently_verified'] is True
