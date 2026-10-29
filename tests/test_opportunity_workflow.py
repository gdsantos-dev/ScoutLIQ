import json
import time
from uuid import uuid4
import pytest
from sqlalchemy import select
from backend.db import SessionLocal
from backend.models import Lead, LeadResearch, User
from backend.opportunity_models import OpportunityEvidence
from backend.security import hasher


def setup_flow(auth, lead_data):
    lead = auth.post('/api/leads', json=lead_data).json()
    base = f"/api/leads/{lead['id']}"
    evidence = auth.post(base + '/evidence', json={
        'statement': 'O site apresenta um menu em PDF sem versão HTML.', 'source_url': 'https://example.org/menu', 'category': 'content'}).json()
    response = auth.patch(base + '/evidence/' + evidence['id'], json={
        'version': evidence['version'], 'classification': 'confirmed', 'reason': 'Conferido na página de serviços.', 'translations': {'en-US': 'The published menu is available as a PDF, without an HTML version.', 'es': 'El menú publicado está disponible en PDF, sin una versión HTML.'}})
    assert response.status_code == 200, response.text
    evidence = response.json()
    payload = {'request_id': str(uuid4()), 'channel': 'email', 'recipient': 'contact@example.org', 'evidence_ids': [evidence['id']]}
    response = auth.post(base + '/outreach/drafts', json=payload)
    assert response.status_code == 201, response.text
    return lead, base, evidence, payload, response.json()


def approve(auth, base, draft):
    return auth.post(f"{base}/outreach/drafts/{draft['id']}/approve", json={
        'version': draft['version'], 'authorization_ref': 'Solicitação por e-mail registrada pelo operador.'})


def test_evidence_draft_approval_crm_no_false_delivery(auth, lead_data):
    lead, base, evidence, payload, draft = setup_flow(auth, lead_data)
    assert evidence['statement'] in draft['body']
    assert auth.post(base + '/outreach/drafts', json=payload).json()['id'] == draft['id']
    approved = approve(auth, base, draft)
    assert approved.status_code == 200, approved.text
    draft = approved.json()
    assert draft['review_blocker'] == ''
    assert draft['dispatch_available'] is False
    dispatch = auth.post(f"{base}/outreach/drafts/{draft['id']}/dispatch", json={'version': draft['version']})
    assert dispatch.status_code == 503
    workflow = auth.get(base + '/workflow').json()
    assert workflow['drafts'][0]['status'] == 'approved'
    assert workflow['score'] == lead['score']
    history = auth.get(base + '/activities').json()
    assert len([a for a in history if a['metadata'].get('event') == 'outreach_prepared']) == 1
    assert any(a['metadata'].get('event') == 'outreach_approved' for a in history)
    assert not any(a['kind'] in ('email', 'whatsapp') for a in history)
    exported = auth.get('/api/export').json()
    assert exported['opportunity_evidence'][0]['id'] == evidence['id']
    assert exported['outreach_drafts'][0]['id'] == draft['id']
    assert 'approval_hash' not in exported['outreach_drafts'][0]


def test_edit_revokes_approval_and_conflict(auth, lead_data):
    _, base, _, _, draft = setup_flow(auth, lead_data)
    draft = approve(auth, base, draft).json()
    path = f"{base}/outreach/drafts/{draft['id']}"
    edit = {'version': draft['version'], 'body': 'Mensagem revisada pelo operador.', 'subject': 'Novo assunto'}
    changed = auth.put(path, json=edit).json()
    assert changed['status'] == 'draft' and changed['approved_at'] is None
    approval = next(a for a in auth.get(base + '/activities').json() if a['metadata'].get('event') == 'outreach_approved')
    assert approval['metadata']['snapshot']['body'] == draft['body']
    assert auth.put(path, json=edit).status_code == 409
    assert auth.post(path + '/dispatch', json={'version': changed['version']}).status_code == 409


def test_revision_invalidates_approved_content(auth, lead_data):
    _, base, evidence, _, draft = setup_flow(auth, lead_data)
    draft = approve(auth, base, draft).json()
    auth.patch(base + '/evidence/' + evidence['id'], json={'version': evidence['version'], 'classification': 'refuted', 'reason': 'Página reavaliada pelo operador.'})
    assert auth.get(base + '/workflow').json()['drafts'][0]['review_blocker']
    assert auth.post(f"{base}/outreach/drafts/{draft['id']}/dispatch", json={'version': draft['version']}).status_code == 409


def test_expired_evidence_cannot_be_approved(auth, lead_data):
    _, base, evidence, _, draft = setup_flow(auth, lead_data)
    with SessionLocal() as db:
        db.get(OpportunityEvidence, evidence['id']).valid_until = int(time.time()) - 1
        db.commit()
    assert approve(auth, base, draft).status_code == 409
    assert auth.get(base + '/workflow').json()['coverage']['confirmed'] == 0


def test_reply_pauses_both_channels(auth, lead_data):
    _, base, _, payload, draft = setup_flow(auth, lead_data)
    approve(auth, base, draft)
    payload.update(request_id=str(uuid4()), channel='whatsapp', recipient='5581999999999')
    assert auth.post(base + '/outreach/drafts', json=payload).status_code == 201
    assert auth.post(base + '/activities', json={'kind': 'reply', 'body': 'Retorno registrado manualmente.'}).status_code == 201
    assert {d['status'] for d in auth.get(base + '/workflow').json()['drafts']} == {'paused'}


def test_optout_blocks_preparation_approval_and_legacy_log(auth, lead_data):
    lead, base, _, payload, draft = setup_flow(auth, lead_data)
    response = auth.patch(base + '/contact-policy', json={'version': lead['version'], 'blocked': True, 'reason': 'Destinatário pediu para não ser contatado.'})
    assert response.status_code == 200, response.text
    payload['request_id'] = str(uuid4())
    assert auth.post(base + '/outreach/drafts', json=payload).status_code == 409
    current = auth.get(base + '/workflow').json()['drafts'][0]
    assert approve(auth, base, current).status_code == 409
    assert auth.post(base + '/activities', json={'kind': 'email', 'body': 'Teste'}).status_code == 409
    assert auth.post(base + '/activities', json={'kind': 'note', 'body': 'Recusa documentada.'}).status_code == 201


def test_research_capture_idempotent_and_new_collection_preserves_evidence(auth, lead_data):
    lead = auth.post('/api/leads', json=lead_data).json()
    base = f"/api/leads/{lead['id']}"
    assert auth.post(base + '/evidence/capture').status_code == 409
    with SessionLocal() as db:
        obj = db.get(Lead, lead['id'])
        db.add(LeadResearch(user_id=obj.user_id, lead_id=obj.id, status='confirmed', website_url='https://example.org',
            checked_at=int(time.time()), checks_json=json.dumps([{'key': 'viewport', 'state': 'fail'}])))
        db.commit()
    assert auth.post(base + '/evidence/capture').json() == {'added': 1}
    assert auth.post(base + '/evidence/capture').json() == {'added': 0}
    evidence = auth.get(base + '/workflow').json()['evidence'][0]
    assert evidence['classification'] == 'probable'
    assert 'não foi atendido' in evidence['statement']
    with SessionLocal() as db:
        db.scalar(select(LeadResearch).where(LeadResearch.lead_id == lead['id'])).checked_at += 1
        db.commit()
    assert not auth.get(base + '/workflow').json()['evidence'][0]['stale']


def test_cross_lead_evidence_and_idempotency_conflict(auth, lead_data):
    _, base, _, payload, _ = setup_flow(auth, lead_data)
    other = auth.post('/api/leads', json={**lead_data, 'name': 'Outra empresa'}).json()
    assert auth.post(f"/api/leads/{other['id']}/outreach/drafts", json={**payload, 'request_id': str(uuid4())}).status_code == 409
    assert auth.post(base + '/outreach/drafts', json={**payload, 'recipient': 'other@example.org'}).status_code == 409


def test_other_user_cannot_access_workflow_or_children(auth, lead_data):
    _, base, evidence, _, draft = setup_flow(auth, lead_data)
    with SessionLocal() as db:
        db.add(User(email='other@example.org', password_hash=hasher.hash('another-password-123'), email_verified_at=int(time.time())))
        db.commit()
    result = auth.post('/api/auth/login', json={'email': 'other@example.org', 'password': 'another-password-123'}).json()
    auth.headers['X-CSRF-Token'] = result['csrf']
    assert auth.get(base + '/workflow').status_code == 404
    assert auth.patch(base + '/evidence/' + evidence['id'], json={'version': 2, 'classification': 'confirmed', 'reason': 'Tentativa de acesso por outro usuário.'}).status_code == 404
    assert approve(auth, base, draft).status_code == 404


def test_csrf_and_mass_assignment(auth, lead_data):
    lead, base, _, payload, draft = setup_flow(auth, lead_data)
    assert auth.post(base + '/outreach/drafts', json={**payload, 'user_id': 'injected'}).status_code == 422
    assert auth.post(base + '/outreach/drafts', json={**payload, 'status': 'approved'}).status_code == 422
    del auth.headers['X-CSRF-Token']
    assert approve(auth, base, draft).status_code == 403


@pytest.mark.parametrize('source', ['javascript:alert(1)', 'https://user:password@example.org', 'file:///etc/passwd'])
def test_evidence_unsafe_urls_rejected(auth, lead_data, source):
    lead = auth.post('/api/leads', json=lead_data).json()
    assert auth.post(f"/api/leads/{lead['id']}/evidence", json={'statement': 'Observação segura', 'source_url': source}).status_code == 422


@pytest.mark.parametrize('locale', ['pt-BR', 'en-US', 'es'])
def test_draft_language_and_original_evidence(auth, lead_data, locale):
    _, base, evidence, payload, _ = setup_flow(auth, lead_data)
    result = auth.post(base + '/outreach/drafts', json={**payload, 'request_id': str(uuid4()), 'locale': locale})
    assert result.status_code == 201
    assert result.json()['locale'] == locale
    expected = evidence['statement'] if locale == 'pt-BR' else evidence['translations'][locale]
    assert expected in result.json()['body']
    if locale != 'pt-BR': assert evidence['statement'] not in result.json()['body']
