"""Isolated nonproduction browser-test server. No access to real app database."""
import argparse
import os
import subprocess
import sys
from pathlib import Path
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--preview', action='store_true', help='Use a separate demo database on port 8002')
parser.add_argument('--port', type=int)
args = parser.parse_args()
root = Path(__file__).resolve().parent.parent
os.chdir(root)
port = str(args.port or (8002 if args.preview else 8001))
database = 'preview' if args.preview else 'e2e'
os.environ.update(
    APP_ENV='test', DATABASE_URL=f'sqlite:///./data/{database}.db',
    ADMIN_EMAIL='e2e@example.test', ADMIN_PASSWORD='E2e-only-not-for-production!',
    APP_ORIGIN=f'http://localhost:{port}', DEMO_SEED='true',
)
subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], check=True)
os.execv(sys.executable, [
    sys.executable, '-m', 'uvicorn', 'backend.main:app',
    '--host', '127.0.0.1', '--port', port, '--no-server-header',
])
