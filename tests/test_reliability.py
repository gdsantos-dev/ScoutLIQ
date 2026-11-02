import json
import threading
from uuid import uuid4
from sqlalchemy.exc import OperationalError
from backend import research_worker as worker, diagnostics, main
from backend.worker_health import beat
from scripts.check_repository import inspect
from database_fixture import postgres_database
import pytest


def test_worker_survives_database_and_failure_heartbeat_outage(monkeypatch, caplog):
    calls = []
    class Stop:
        count = 0
        def is_set(self): return self.count >= 2
        def wait(self, _): self.count += 1
        def set(self): self.count = 2
    def heartbeat(*args, **kwargs):
        calls.append(args)
        if len(calls) <= 2 or args[1:] == ('stopped',):
            raise OperationalError('private SQL', {}, Exception('secret-password-and-payload'))
    import backend.worker_health as health
    import signal
    monkeypatch.setattr(worker, 'MODE', 'worker')
    monkeypatch.setattr(worker, 'claim', lambda: None)
    monkeypatch.setattr(threading, 'Event', Stop)
    monkeypatch.setattr(signal, 'signal', lambda *_: None)
    monkeypatch.setattr(health, 'beat', heartbeat)
    worker.run()
    assert len(calls) >= 5  # A later cycle and shutdown were reached.
    events = [json.loads(r.message) for r in caplog.records if r.name == 'scoutliq.operations']
    assert any(e['event'] == 'worker_cycle_failed' for e in events)
    assert all(e['retryable'] for e in events)
    assert 'secret-password' not in caplog.text and 'private SQL' not in caplog.text


def test_diagnostics_use_aggregates_and_preserve_unavailable_state(auth, monkeypatch):
    state = diagnostics.collect()
    assert state['database'] == 'ok' and state['schema']['applied'] == ['033']
    beat(str(uuid4()))
    assert diagnostics.collect()['status'] == 'ok'
    assert 'test@example.com' not in json.dumps(state)
    def unavailable(): raise RuntimeError('private-connection-url')
    monkeypatch.setattr(diagnostics, 'SessionLocal', unavailable)
    result = diagnostics.collect()
    assert result['status'] == 'unavailable' and 'private-connection-url' not in json.dumps(result)


def test_health_database_outage_is_safe_503(client, monkeypatch):
    class Down:
        def execute(self, *_): raise OperationalError('private SQL', {}, Exception('secret'))
    main.app.dependency_overrides[main.get_db] = lambda: Down()
    try:
        for route in ['/api/health', '/api/health/ready', '/api/health/worker']:
            response = client.get(route)
            assert response.status_code == 503
            assert response.json() == {'status': 'unavailable'}
    finally:
        main.app.dependency_overrides.pop(main.get_db)


def test_readiness_rejects_old_schema_even_without_combined_worker(client, monkeypatch):
    monkeypatch.setenv('SCOUTLIQ_PROCESS_MODE', 'web')
    monkeypatch.setattr(diagnostics, 'schema_ready', lambda _: False)
    assert client.get('/api/health').status_code == 200
    response = client.get('/api/health/ready')
    assert response.status_code == 503 and response.json() == {'status': 'unavailable'}


def test_migration_startup_failure_is_redacted_and_does_not_bootstrap(monkeypatch, caplog):
    from scripts import start
    import subprocess
    monkeypatch.setattr(start, 'prepare_volume', lambda: None)
    monkeypatch.setattr(start, 'validate_environment', lambda: 'combined')
    def fail(*args, **kwargs):
        assert kwargs['stdout'] == subprocess.DEVNULL and kwargs['stderr'] == subprocess.DEVNULL
        raise RuntimeError('secret-connection-url-and-private-data')
    monkeypatch.setattr(start.subprocess, 'run', fail)
    with pytest.raises(RuntimeError, match='Startup failed') as error:
        start.main()
    assert 'secret-connection' not in str(error.value) + caplog.text
    events = [json.loads(r.message) for r in caplog.records if r.name == 'scoutliq.operations']
    assert events == [{'event': 'startup_failed', 'component': 'supervisor', 'state': 'migration', 'retryable': False}]


@pytest.mark.parametrize('name', ['.env', 'config/.env.local', 'data/user.db', 'backups/user.json', 'secret.pem'])
def test_publication_guard_rejects_sensitive_paths(name):
    assert 'sensitive_path' in inspect(name, b'')


def test_publication_guard_redacts_patterns_and_accepts_template():
    assert inspect('.env.example', b'API_KEY=') == []
    assert 'github_token' in inspect('app.py', b'gh' + b'p_' + b'x' * 40)


@pytest.mark.parametrize('url', ['postgresql://localhost/scoutliq_test_x',
    'postgresql+psycopg://remote.example/scoutliq_test_x',
    'postgresql+psycopg://localhost/production',
    'postgresql+psycopg://localhost/scoutliq_test_x?options=-csearch_path=public'])
def test_postgres_fixture_refuses_nonisolated_targets(url):
    with pytest.raises(RuntimeError): postgres_database(url)
