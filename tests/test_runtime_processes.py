import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
from urllib.request import urlopen
import pytest
from sqlalchemy import select, func
from backend.db import SessionLocal
from backend.models import User, Lead, ResearchBatch, ResearchBatchItem
from backend.autonomy_models import WorkAttempt, ProviderOperation
from backend.communication_models import OutboxMessage
from backend import research_worker as worker
from test_operational_autonomy import create, action, Source, Researcher

ROOT = Path(__file__).resolve().parents[1]
FLAGS = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0


def wait_until(predicate, seconds=45):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate(): return
        time.sleep(.25)
    raise AssertionError('Bounded process wait expired.')


@pytest.mark.parametrize('kind', ['search', 'investigation'])
def test_killed_worker_recovers_real_expired_lease_without_duplicate_effects(auth, monkeypatch, tmp_path, kind):
    monkeypatch.setattr(worker, 'MODE', 'worker')
    if kind == 'search':
        row, _ = create(auth, monkeypatch, Source(verified=True), investigation_limit=0)
        action(auth, row, 'run_now')
    else:
        with SessionLocal() as db:
            user = db.scalar(select(User))
            lead = Lead(user_id=user.id, name='Interrupted investigation', category='Cafe', city='Recife', latitude=-8, longitude=-34)
            db.add(lead); db.flush()
            batch = ResearchBatch(user_id=user.id, mode='web', status='pending', requested_count=1)
            db.add(batch); db.flush()
            db.add(ResearchBatchItem(batch_id=batch.id, lead_id=lead.id, status='pending')); db.commit()
    marker = tmp_path / 'synthetic-claim.json'
    env = {**os.environ, 'APP_ENV': 'test', 'RESEARCH_EXECUTION_MODE': 'worker', 'RESEARCH_LEASE_SECONDS': '60'}
    with (tmp_path / 'child.txt').open('w') as log:
        process = subprocess.Popen([sys.executable, 'tests/runtime_process_fixture.py', 'hold', str(marker)],
            cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, creationflags=FLAGS)
        try:
            wait_until(lambda: marker.exists() or process.poll() is not None)
            assert marker.exists(), 'Synthetic child exited before entering provider operation.'
            task = json.loads(marker.read_text(encoding='utf8'))
            process.kill(); process.wait(timeout=10)
        finally:
            if process.poll() is None: process.kill(); process.wait(timeout=10)
    # Respect the actual minimum lease; no clock mutation, budget reset or fencing bypass.
    wait_until(lambda: time.time() > task['expires'] + 1, 65)
    result = subprocess.run([sys.executable, 'tests/runtime_process_fixture.py', 'finish', str(marker)],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=50, creationflags=FLAGS)
    assert result.returncode == 0, result.stderr
    assert not worker.execute(task, provider=Source(verified=True), researcher=Researcher())
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Lead)) == 1
        attempts = db.scalars(select(WorkAttempt).where(WorkAttempt.item_id == task['id'])).all()
        assert len(attempts) == 2 and {a.status for a in attempts} == {'expired', 'committed'}
        assert db.scalar(select(func.count()).select_from(ProviderOperation)) == 2
        assert db.scalar(select(func.count()).select_from(OutboxMessage)) == 0
        if kind == 'investigation': assert db.get(ResearchBatchItem, task['id']).status == 'done'


def test_clean_supervisor_start_stop_restart_and_persistence(tmp_path):
    database = tmp_path / 'scoutliq-runtime.db'
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0)); port = listener.getsockname()[1]
    env = {**os.environ, 'DATABASE_URL': 'sqlite:///' + str(database), 'APP_ENV': 'test',
        'APP_ORIGIN': f'http://localhost:{port}', 'PORT': str(port), 'ADMIN_EMAIL': 'runtime@example.test',
        'ADMIN_PASSWORD': 'Synthetic-runtime-only-1389!', 'DEMO_SEED': 'false', 'EMAIL_MODE': 'memory',
        'RESEARCH_EXECUTION_MODE': 'worker', 'SCOUTLIQ_PROCESS_MODE': 'combined', 'RADAR_PROVIDER': 'demo'}
    env.pop('SCOUT_TEST_POSTGRES_URL', None)
    def healthy():
        try:
            with urlopen(f'http://localhost:{port}/api/health/ready', timeout=2) as response:
                return response.status == 200
        except Exception: return False
    for cycle in range(2):
        with (tmp_path / f'supervisor-{cycle}.txt').open('w') as log:
            process = subprocess.Popen([sys.executable, 'scripts/start.py'], cwd=ROOT, env=env,
                stdout=log, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0)
            try:
                wait_until(lambda: healthy() or process.poll() is not None, 60)
                assert process.poll() is None and healthy()
                import sqlite3
                with sqlite3.connect(database) as db:
                    assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0] == '033'
                    assert db.execute('SELECT count(*) FROM users').fetchone()[0] == 1
                    assert db.execute('SELECT count(*) FROM communication_outbox').fetchone()[0] == 0
            finally:
                if process.poll() is None:
                    process.send_signal(signal.CTRL_BREAK_EVENT if os.name == 'nt' else signal.SIGTERM)
                    try: process.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        if os.name == 'nt': subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True)
                        else: process.kill()
                        process.wait(timeout=10)
        wait_until(lambda: not healthy(), 10)
