import os
import tempfile
from pathlib import Path

# Isolate test data before importing the application, never use the user's database.
_dir=tempfile.TemporaryDirectory(prefix='scoutliq-tests-')
os.environ['DATABASE_URL']='sqlite:///'+str(Path(_dir.name)/'test.db')
os.environ['APP_ENV']='test'
os.environ['RESEARCH_EXECUTION_MODE']='legacy'
os.environ['ADMIN_EMAIL']='test@example.com'
os.environ['ADMIN_PASSWORD']='testing-password-123!'
os.environ['DEMO_SEED']='false'
os.environ['APP_ORIGIN']='http://localhost:8000'
os.environ['EMAIL_MODE']='memory'
os.environ['EMAIL_FROM_EMAIL']='auth@orliq.test'
os.environ['EMAIL_FROM_NAME']='ScoutLIQ'
os.environ['REGISTRATION_MODE']='open'

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from backend.main import app
from backend.db import SessionLocal, engine
from backend.models import User, AccountToken, Session, Lead, LeadActivity, RadarSavedSearch, LeadResearch, ResearchBatch, ResearchBatchItem, AutomationRule, AutomationRun, Campaign, CampaignLead, Sale, Payment, Expense, Site
from backend.opportunity_models import OpportunityEvidence, OutreachDraft, RecipientPolicy
from backend.absorption_models import AbsorptionBatch, AbsorptionItem, AbsorptionRecovery
from backend.security import limiter, hasher
from backend.email_service import MEMORY_OUTBOX
from sqlalchemy import delete

command.upgrade(Config('alembic.ini'),'head')

def pytest_sessionfinish(session, exitstatus):
    engine.dispose()
    _dir.cleanup()

@pytest.fixture
def client():
    import time
    from backend import research_worker
    from backend.models import ResearchExecutor
    research_worker.INTERVAL = 0
    with SessionLocal() as db:
        slot = db.get(ResearchExecutor, 1)
        slot.token, slot.lease_until, slot.next_at, slot.day, slot.used = '', 0, 0, 0, 0
        db.commit()
    limiter.events.clear()
    MEMORY_OUTBOX.clear()
    with SessionLocal() as db:
        for table in (AbsorptionRecovery,AbsorptionItem,AbsorptionBatch,RecipientPolicy,OutreachDraft,OpportunityEvidence,Site,Payment,Expense,Sale,CampaignLead,Campaign,AutomationRun,AutomationRule,ResearchBatchItem,ResearchBatch,LeadResearch,LeadActivity,RadarSavedSearch,Lead,Session,AccountToken,User):
            db.execute(delete(table))
        db.add(User(email='test@example.com',password_hash=hasher.hash('testing-password-123!'),email_verified_at=int(time.time())))
        db.commit()
    with TestClient(app) as c:
        yield c

@pytest.fixture
def auth(client):
    response=client.post('/api/auth/login',json={'email':'test@example.com','password':'testing-password-123!'})
    assert response.status_code==200
    client.headers['X-CSRF-Token']=response.json()['csrf']
    client.headers['Origin']='http://localhost:8000'
    return client

@pytest.fixture
def lead_data():
    return {'name':'Empresa Teste','category':'Cafeteria','city':'Recife','country':'BR','latitude':-8.05,'longitude':-34.9,'website_status':'none','rating':4.8,'reviews':312,'instagram':'https://instagram.com/example','instagram_active':True,'phone':'+55 81 99999-9999','whatsapp':'5581999999999','potential_cents':250000}
