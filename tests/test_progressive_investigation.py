"""Controlled providers only: queue, policy, isolation, persistence and no outreach."""
import json
import time
from uuid import uuid4
import pytest
from sqlalchemy import select, func
from backend import main, research_worker as worker, consumption
from backend.db import SessionLocal, engine
from backend.models import Lead, User, LeadResearch, ResearchBatch, ResearchBatchItem, ResearchExecutor
from backend.investigation import Preferences, local_plan, deepen, projection
from backend.scoring import score
from backend.autonomy_models import ProviderOperation
from backend.opportunity_models import OutreachDraft
from backend.communication_models import OutboxMessage
from test_absorption import preview, commit, record

def create(auth, lead_data, count=1, **changes):
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == 'test@example.com'))
        rows = [Lead(**{**lead_data, 'name': 'Café Independente '+str(i), 'website_status': 'unknown', **changes}, user_id=user.id) for i in range(count)]
        db.add_all(rows); db.commit()
        return [r.id for r in rows]

def request(auth, ids, key=None):
    response = auth.post('/api/investigation/requests', json={'lead_ids': ids, 'request_key': key or str(uuid4())})
    assert response.status_code == 201, response.text
    return response.json()

def prefs(auth, **changes):
    response = auth.put('/api/investigation/preferences', json={**Preferences().model_dump(), **changes})
    assert response.status_code == 200, response.text

class Researcher:
    def __init__(self, confirmed=True, fail=False): self.calls = self.deep = 0; self.confirmed = confirmed; self.fail = fail
    def research(self, lead, locale):
        self.calls += 1
        if self.fail: raise TimeoutError('secret provider error must not leak')
        return {'status': 'confirmed' if self.confirmed else 'not_found', 'provider': 'controlled',
            'website_url': 'https://example.org' if self.confirmed else '', 'website_status': 'unknown',
            'checked_at': int(time.time()), 'page': {'pages_checked': 1} if self.confirmed else {},
            'fetch_errors': 0, 'confidence': 90 if self.confirmed else 0,
            'checks': [{'key': 'viewport', 'state': 'fail'}] if self.confirmed else []}
    def deep_audit(self, lead, url):
        self.deep += 1
        return {'website_status': 'poor', 'pages_checked': 2, 'quality_score': 35, 'signals': {'forms': 1}, 'findings': []}

def step(researcher, batch_id=None):
    with SessionLocal() as db: db.get(ResearchExecutor, 1).next_at = 0; db.commit()
    task = worker.claim(batch_id=batch_id)
    if task: assert worker.execute(task, researcher=researcher)
    return task

def drain(researcher, count=25):
    for _ in range(count):
        if not step(researcher): return
    pytest.fail('Unexpected unbounded queue')

def test_manual_progressive_persists_canonical_score_without_messages(auth, lead_data):
    ids = create(auth, lead_data, 2); row = request(auth, ids)['batch']; researcher = Researcher()
    drain(researcher)
    done = auth.get('/api/research/batches/'+row['id']).json()['batch']
    assert done['done'] == 2 and done['status'] == 'completed'
    assert researcher.calls == researcher.deep == 2
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(LeadResearch)) == 2
        for entry in done['items']:
            lead = db.get(Lead, entry['lead_id'])
            assert entry['qualification']['score'] == score(lead)['value']
            assert lead.stage == 'discovered' and not lead.in_pipeline
        assert db.scalar(select(func.count()).select_from(OutreachDraft)) == 0
        assert db.scalar(select(func.count()).select_from(OutboxMessage)) == 0

def test_100_queue_persistence_active_arrivals_dedup_and_replay(auth, lead_data):
    ids = create(auth, lead_data, 100); key = str(uuid4())
    first = request(auth, ids[:1])
    added = request(auth, ids, key)
    assert sum(b['total'] for b in added['batches']) == 100
    assert max(b['total'] for b in added['batches']) <= 20
    assert sum(i['outcome'] == 'already_pending' for b in added['batches'] for i in b['items']) == 1
    engine.dispose()  # independent connection/restart boundary, no memory queue
    assert request(auth, ids, key)['batches'] == added['batches']
    assert auth.post('/api/investigation/requests', json={'lead_ids': ids[1:], 'request_key': key}).status_code == 409
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(ResearchBatchItem).where(ResearchBatchItem.status == 'pending')) == 100
    task = worker.claim()
    with SessionLocal() as db: assert db.get(ResearchBatchItem, task['id']).batch_id == first['batch']['id']

def test_default_off_and_absorption_optin_disable_preserves_history(auth):
    assert not auth.get('/api/investigation/preferences').json()['absorption']
    commit(auth, preview(auth, [record('Café Inicial')]).json())
    assert auth.get('/api/investigation/queue').json()['batches'] == []
    prefs(auth, absorption=True)
    b = preview(auth, [record('Café Segundo', latitude=-8.2)]).json(); commit(auth, b); commit(auth, b)
    queue = auth.get('/api/investigation/queue').json()['batches']; assert len(queue) == 1
    prefs(auth)
    commit(auth, preview(auth, [record('Café Terceiro', latitude=-8.3)]).json())
    assert len(auth.get('/api/investigation/queue').json()['batches']) == 1

def test_unified_discovery_auto_queues_once(auth, monkeypatch):
    from test_general_search import BroadSource, launch
    from test_smart_search import candidate
    prefs(auth, search=True)
    monkeypatch.setattr(worker, 'MODE', 'worker')
    source = BroadSource([[candidate(1)]])
    monkeypatch.setattr(main, 'radar_provider', source)
    from test_unified_search import place
    from backend import locations
    monkeypatch.setattr(locations, 'search_locations', lambda *a, **k: [{'resolved': place().model_dump()}])
    launch(auth)
    task = worker.claim(); assert task['kind'] == 'smart'
    assert worker.execute(task, provider=source)
    with SessionLocal() as db:
        items = db.scalars(select(ResearchBatchItem).where(ResearchBatchItem.status == 'pending')).all()
        assert len(items) == 1
        assert db.get(ResearchBatch, items[0].batch_id).mode == 'progressive'

@pytest.mark.parametrize('kind', ['incompatible', 'insufficient', 'fresh', 'fresh_deep'])
def test_economic_and_cache_no_unnecessary_network(auth, lead_data, kind):
    changes = {'name': 'Starbucks Centro'} if kind == 'incompatible' else {'category': 'Serviços'} if kind == 'insufficient' else {}
    ids = create(auth, lead_data, **changes)
    if kind.startswith('fresh'):
        with SessionLocal() as db:
            lead = db.get(Lead, ids[0])
            db.add(LeadResearch(user_id=lead.user_id, lead_id=lead.id, status='not_found' if kind == 'fresh' else 'confirmed',
                checked_at=int(time.time()), website_url='https://example.org' if kind == 'fresh_deep' else '',
                audit_level='deep', audited_at=int(time.time())))
            db.commit()
    row = request(auth, ids)['batch']; researcher = Researcher(); drain(researcher)
    done = auth.get('/api/research/batches/'+row['id']).json()['batch']
    assert done['done'] == 1 and researcher.calls == researcher.deep == 0

@pytest.mark.parametrize('allow_deep,confirmed', [(False, True), (True, False)])
def test_selective_depth_and_no_site_remains_promising(auth, lead_data, allow_deep, confirmed):
    prefs(auth, allow_deep=allow_deep)
    row = request(auth, create(auth, lead_data))['batch']; researcher = Researcher(confirmed=confirmed); drain(researcher)
    done = auth.get('/api/research/batches/'+row['id']).json()['batch']['items'][0]
    assert researcher.calls == 1 and researcher.deep == 0
    if not confirmed:
        assert done['qualification']['class'] == 'promising'
        assert any('não comprova' in text for text in done['qualification']['pending'])

def test_daily_cap_persists_backlog_until_next_utc_day(auth, lead_data, monkeypatch):
    prefs(auth, daily_limit=1, allow_deep=False)
    request(auth, create(auth, lead_data, 2)); researcher = Researcher(False); drain(researcher)
    assert researcher.calls == 1
    with SessionLocal() as db:
        pending = db.scalar(select(ResearchBatchItem).where(ResearchBatchItem.status == 'pending'))
        later = pending.retry_at
    monkeypatch.setattr(time, 'time', lambda: later+1)
    drain(researcher); assert researcher.calls == 2

@pytest.mark.parametrize('action', ['pause', 'cancel'])
def test_control_revokes_late_result_even_after_resume(auth, lead_data, action):
    row = request(auth, create(auth, lead_data))['batch']; researcher = Researcher()
    step(researcher); task = worker.claim()
    assert task
    auth.post('/api/research/batches/'+row['id']+'/'+action)
    if action == 'pause': auth.post('/api/research/batches/'+row['id']+'/resume')
    assert not worker.execute(task, researcher=researcher)
    assert researcher.calls == 0
    if action == 'pause': drain(researcher); assert researcher.calls == 1

def test_expired_lease_obsolete_input_and_restart(auth, lead_data):
    ids = create(auth, lead_data); row = request(auth, ids)['batch']; researcher = Researcher()
    task = worker.claim()
    with SessionLocal() as db:
        db.get(ResearchExecutor, 1).lease_until = 0
        db.get(ResearchExecutor, 1).next_at = 0
        db.get(ResearchBatchItem, task['id']).lease_until = 0; db.commit()
    new = worker.claim(); assert new['token'] != task['token']
    assert not worker.execute(task, researcher=researcher)
    assert worker.execute(new, researcher=researcher)
    class Edited(Researcher):
        def research(self, lead, locale):
            with SessionLocal() as db:
                db.get(Lead, lead.id).name = 'Editada durante consulta'; db.commit()
            return super().research(lead, locale)
    step(Edited())
    result = auth.get('/api/research/batches/'+row['id']).json()['batch']
    assert result['errors'] == 1 and 'obsoleto' in result['items'][0]['error']
    with SessionLocal() as db: assert db.scalar(select(func.count()).select_from(LeadResearch)) == 0

def test_timeout_bounded_retry_and_redacted_error(auth, lead_data, monkeypatch):
    row = request(auth, create(auth, lead_data))['batch']; researcher = Researcher(fail=True)
    step(researcher)
    for _ in range(3):
        step(researcher)
        with SessionLocal() as db:
            item = db.scalar(select(ResearchBatchItem).where(ResearchBatchItem.batch_id == row['id']))
            later = item.retry_at
        monkeypatch.setattr(time, 'time', lambda: later+1)
    done = auth.get('/api/research/batches/'+row['id']).json()['batch']
    assert researcher.calls == 3 and done['errors'] == 1 and 'secret' not in str(done)
    assert done['items'][0]['qualification']['class'] == 'unavailable'

def test_budget_reservation_and_deep_failure_preserve_web_result(auth, lead_data):
    prefs(auth, operation_limit=1)
    row = request(auth, create(auth, lead_data))['batch']
    class Metered(Researcher):
        @consumption.metered('website')
        def research(self, lead, locale): return super().research(lead, locale)
        @consumption.metered('website')
        def deep_audit(self, lead, url): return super().deep_audit(lead, url)
    researcher = Metered(); drain(researcher)
    done = auth.get('/api/research/batches/'+row['id']).json()['batch']
    assert done['errors'] == 1 and researcher.calls == 1 and researcher.deep == 0
    with SessionLocal() as db:
        assert db.scalar(select(LeadResearch)).status == 'confirmed'
        assert db.scalar(select(func.count()).select_from(ProviderOperation)) == 1

def test_cross_user_ids_preferences_and_controls_are_denied(auth, lead_data):
    ids = create(auth, lead_data); row = request(auth, ids)['batch']
    with SessionLocal() as db:
        other = User(email='other@example.test', password_hash='unused'); db.add(other); db.flush()
        db.get(Lead, ids[0]).user_id = other.id
        db.get(ResearchBatch, row['id']).user_id = other.id; db.commit()
    assert auth.post('/api/investigation/requests', json={'lead_ids': ids, 'request_key': str(uuid4())}).status_code == 404
    for path in ['pause', 'resume', 'cancel']:
        assert auth.post('/api/research/batches/'+row['id']+'/'+path).status_code == 404
    assert auth.get('/api/research/batches/'+row['id']).status_code == 404
    assert auth.get('/api/investigation/queue').json()['batches'] == []
    assert auth.put('/api/investigation/preferences', json={'user_id': other.id}).status_code == 422
    assert auth.put('/api/investigation/preferences', json={'daily_limit': 101}).status_code == 422

def test_legacy_batch_no_longer_swallows_new_leads(auth, lead_data):
    ids = create(auth, lead_data, 2)
    first = auth.post('/api/research/batches', json={'lead_ids': ids[:1]}).json()
    second = auth.post('/api/research/batches', json={'lead_ids': ids[1:]}).json()
    assert first['batch']['id'] != second['batch']['id']
    assert second['batch']['items'][0]['lead_id'] == ids[1]

def test_fetch_failure_is_unavailable_without_losing_partial_research(auth, lead_data):
    row = request(auth, create(auth, lead_data))['batch']
    class FailedFetch(Researcher):
        def research(self, lead, locale): return {**super().research(lead, locale), 'status':'not_found', 'website_url':'', 'fetch_errors':3}
    drain(FailedFetch(False))
    done = auth.get('/api/research/batches/'+row['id']).json()['batch']
    assert done['items'][0]['qualification']['class'] == 'unavailable'
    with SessionLocal() as db: assert db.scalar(select(LeadResearch)).fetch_errors == 3

def test_pause_during_network_revokes_reservations_and_result(auth, lead_data):
    row = request(auth, create(auth, lead_data))['batch']
    class Interrupted(Researcher):
        def research(self, lead, locale):
            result = super().research(lead, locale)
            auth.post('/api/research/batches/'+row['id']+'/pause')
            auth.post('/api/research/batches/'+row['id']+'/resume')
            with pytest.raises(consumption.ConsumptionLimit): consumption.reserve('website')
            return result
    researcher = Interrupted(); step(researcher)
    task = worker.claim(); assert not worker.execute(task, researcher=researcher)
    with SessionLocal() as db: assert db.scalar(select(func.count()).select_from(LeadResearch)) == 0
    drain(Researcher())
    assert auth.get('/api/research/batches/'+row['id']).json()['batch']['done'] == 1

def test_deleted_lead_during_network_does_not_stall_executor(auth, lead_data):
    ids = create(auth, lead_data); row = request(auth, ids)['batch']
    class Deleted(Researcher):
        def research(self, lead, locale):
            with SessionLocal() as db: db.delete(db.get(Lead, lead.id)); db.commit()
            return super().research(lead, locale)
    step(Researcher()); task = worker.claim()
    assert not worker.execute(task, researcher=Deleted())
    assert worker.claim() is None
    assert auth.get('/api/research/batches/'+row['id']).json()['batch']['status'] == 'completed'
    with SessionLocal() as db: assert db.get(ResearchExecutor, 1).lease_until == 0

def test_concurrent_enqueue_deduplicates_under_user_lock(auth, lead_data):
    from concurrent.futures import ThreadPoolExecutor
    from backend.investigation import enqueue
    ids = create(auth, lead_data, 3)
    def submit():
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.email == 'test@example.com'))
            rows = enqueue(db, user, ids); db.commit(); return [r.id for r in rows]
    with ThreadPoolExecutor(max_workers=2) as pool: results = list(pool.map(lambda _: submit(), range(2)))
    assert results[0] != results[1]
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(ResearchBatchItem).where(ResearchBatchItem.status == 'pending')) == 3

def test_csrf_and_automatic_ingress_transaction_rollback(auth, lead_data, monkeypatch):
    prefs(auth, absorption=True)
    b = preview(auth, [record()]).json()
    from backend import investigation
    def fail(*args, **kwargs): raise RuntimeError('controlled enqueue failure')
    monkeypatch.setattr(investigation, 'enqueue', fail)
    with pytest.raises(RuntimeError): commit(auth, b)
    with SessionLocal() as db: assert db.scalar(select(func.count()).select_from(Lead)) == 0
    auth.headers['X-CSRF-Token'] = 'invalid'
    assert auth.put('/api/investigation/preferences', json={}).status_code == 403
    assert auth.post('/api/investigation/requests', json={'lead_ids':[str(uuid4())], 'request_key':str(uuid4())}).status_code == 403

def test_recent_good_site_is_low_priority_without_research(auth, lead_data):
    ids = create(auth, lead_data, website='https://example.org', website_status='good',
        website_intelligence_json=json.dumps({'pages_checked':2, 'quality_score':95}), website_analyzed_at=int(time.time()))
    row = request(auth, ids)['batch']; researcher = Researcher(); drain(researcher)
    result = auth.get('/api/research/batches/'+row['id']).json()['batch']['items'][0]
    assert result['qualification']['class'] == 'low'
    assert researcher.calls == researcher.deep == 0

def test_daily_network_budget_defers_deep_without_losing_web(auth, lead_data, monkeypatch):
    prefs(auth, daily_limit=1, daily_operation_limit=1)
    row = request(auth, create(auth, lead_data))['batch']
    class Metered(Researcher):
        @consumption.metered('website')
        def research(self, lead, locale): return super().research(lead, locale)
        @consumption.metered('website')
        def deep_audit(self, lead, url): return super().deep_audit(lead, url)
    researcher = Metered(); drain(researcher)
    with SessionLocal() as db:
        item = db.scalar(select(ResearchBatchItem).where(ResearchBatchItem.batch_id == row['id']))
        assert item.phase == 'deep' and item.status == 'pending'
        later = item.retry_at
        assert db.scalar(select(LeadResearch)).status == 'confirmed'
    request(auth, create(auth, lead_data, name='Café Aguardando'))
    monkeypatch.setattr(time, 'time', lambda: later+1)
    drain(researcher); assert researcher.calls == researcher.deep == 1
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(ResearchBatchItem).where(ResearchBatchItem.status == 'pending')) == 1
