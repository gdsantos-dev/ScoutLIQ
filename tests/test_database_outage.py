"""Real worker and PostgreSQL connection loss through a disposable loopback proxy."""
import os
import select
import socket
import subprocess
import sys
import threading
from uuid import uuid4
import pytest
from sqlalchemy.engine import make_url
from backend.db import SessionLocal
from backend.autonomy_models import WorkerHeartbeat
from test_runtime_processes import ROOT, FLAGS, wait_until

pytestmark = pytest.mark.skipif(not os.getenv('SCOUT_TEST_POSTGRES_URL'), reason='Requires isolated PostgreSQL.')


def test_worker_reconnects_after_real_connection_loss(auth, tmp_path):
    url = make_url(os.environ['DATABASE_URL'])
    assert url.host in ('localhost', '127.0.0.1') and url.database.startswith('scoutliq_test_')
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0)); listener.listen(); listener.settimeout(.2)
    port = listener.getsockname()[1]
    available, stopped = threading.Event(), threading.Event()
    available.set()
    threads = []

    def forward(client):
        with client:
            try:
                with socket.create_connection((url.host, url.port), timeout=2) as upstream:
                    while not stopped.is_set() and available.is_set():
                        readable, _, _ = select.select([client, upstream], [], [], .1)
                        for source in readable:
                            data = source.recv(65536)
                            if not data: return
                            (upstream if source is client else client).sendall(data)
            except OSError:
                pass

    def serve():
        while not stopped.is_set():
            try: client, _ = listener.accept()
            except socket.timeout: continue
            except OSError: return
            if not available.is_set(): client.close(); continue
            thread = threading.Thread(target=forward, args=(client,), daemon=True)
            threads.append(thread); thread.start()

    proxy = threading.Thread(target=serve, daemon=True); proxy.start()
    identifier = str(uuid4())
    env = {**os.environ, 'DATABASE_URL': url.set(port=port).render_as_string(hide_password=False),
           'RESEARCH_EXECUTION_MODE': 'worker', 'SCOUTLIQ_WORKER_ID': identifier}
    log_path = tmp_path / 'worker-outage.txt'
    def heartbeat():
        with SessionLocal() as db:
            row = db.get(WorkerHeartbeat, identifier)
            return row.heartbeat_at if row and row.state == 'idle' else 0
    try:
        with log_path.open('w', encoding='utf8') as log:
            process = subprocess.Popen([sys.executable, '-m', 'backend.research_worker'], cwd=ROOT,
                env=env, stdout=log, stderr=subprocess.STDOUT, creationflags=FLAGS)
            try:
                wait_until(lambda: heartbeat() > 0)
                before = heartbeat()
                available.clear()
                wait_until(lambda: 'heartbeat_unavailable' in log_path.read_text(encoding='utf8'))
                assert process.poll() is None
                available.set()
                wait_until(lambda: heartbeat() > before)
                assert process.poll() is None
            finally:
                process.terminate(); process.wait(timeout=15)
        output = log_path.read_text(encoding='utf8')
        assert 'worker_cycle_failed' in output
        assert url.password not in output and url.database not in output and 'Traceback' not in output
    finally:
        stopped.set(); listener.close(); proxy.join(timeout=3)
        for thread in threads: thread.join(timeout=3)
