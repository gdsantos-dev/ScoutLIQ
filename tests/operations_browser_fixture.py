"""Canonical synthetic records served by the real application. No provider calls."""
import os
import sys
import time
import json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import unified_browser_fixture as unified
from alembic import command
from alembic.config import Config
from sqlalchemy import select
from backend.db import SessionLocal
from backend.bootstrap import bootstrap
from backend.security import hasher
from backend.models import User, LeadActivity
from backend.commercial_review_models import CommercialReview
from backend.communication_models import ReceivedMessage
from test_operational_intelligence import company, search, absorb, accepted, uid


if __name__=='__main__':
    assert sys.argv[1]=='server'
    os.environ['DEMO_SEED']='false'
    command.upgrade(Config('alembic.ini'),'head');bootstrap()
    now=int(time.time())
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.email=='e2e@example.test'))
        if not db.scalar(select(User).where(User.email=='empty@example.test')):
            db.add(User(email='empty@example.test',password_hash=hasher.hash('E2e-only-not-for-production!'),email_verified_at=now))
            l=company(db,user,contact='hello@example.test',created_at=now-500,in_pipeline=True,next_action='Revisar proposta',next_action_on='2026-01-01')
            search(db,user,[l],[l],status='completed',updated_at=now-100)
            absorb(db,user,lead=l)
            absorb(db,user,status='pending')
            db.add(CommercialReview(user_id=user.id,lead_id=l.id,state='selected',decided_at=now-200,classification='priority',dirty=0,refresh_at=now+86400))
            b=accepted(db,user,l,now-100)
            db.add(ReceivedMessage(user_id=user.id,lead_id=l.id,account_id=b.account_id,provider_id=uid(),thread_id=b.thread_id,
                classification='information_request',association='matched',sent_at=now-50))
            db.add(LeadActivity(user_id=user.id,lead_id=l.id,kind='reply',metadata_json=json.dumps({'event':'outreach_reply','message_id':'synthetic'}),created_at=now-50))
            company(db,user,created_at=now-120*86400)
            company(db,user,demo=True)
            db.commit()
    import uvicorn
    uvicorn.run(unified.fixture.main.app,host='127.0.0.1',port=unified.fixture.port,server_header=False)
