"""Validate production-only behavior in a separate interpreter/configuration."""
import os
import subprocess
import sys

def test_production_cookies_origin_headers_and_private_docs(tmp_path):
    env={**os.environ,'APP_ENV':'production','APP_ORIGIN':'https://scout.example.test','DATABASE_URL':'sqlite:///'+str(tmp_path/'production.db'),'ADMIN_EMAIL':'prod@example.test','ADMIN_PASSWORD':'Production-test-only-123!','DEMO_SEED':'false'}
    code='''
from alembic import command
from alembic.config import Config
command.upgrade(Config('alembic.ini'),'head')
from fastapi.testclient import TestClient
from backend.main import app
from backend.db import engine
with TestClient(app,base_url='https://scout.example.test') as client:
    result=client.post('/api/auth/login',json={'email':'prod@example.test','password':'Production-test-only-123!'},headers={'Origin':'https://scout.example.test'})
    assert result.status_code==200,result.text
    cookie=result.headers['set-cookie']
    assert 'Secure' in cookie and 'HttpOnly' in cookie and 'SameSite=strict' in cookie
    assert result.headers['strict-transport-security'].startswith('max-age=31536000')
    assert "script-src 'self'" in result.headers['content-security-policy']
    assert client.get('/api/docs').status_code==404
    assert client.get('/api/openapi.json').status_code==404
    assert client.get('/api/leads').json()==[]
    assert client.post('/api/auth/login',json={'email':'prod@example.test','password':'Production-test-only-123!'},headers={'Origin':'https://attacker.example'}).status_code==403
engine.dispose()
'''
    result=subprocess.run([sys.executable,'-c',code],env=env,capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stdout+result.stderr
