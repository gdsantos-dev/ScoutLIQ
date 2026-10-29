import time
from sqlalchemy import select
from backend.db import SessionLocal
from backend.models import AccountToken, Session, User
from backend.email_service import MEMORY_OUTBOX


def test_registration_verification_and_login(client):
    payload={
        'name':'Guilherme Teste',
        'email':'novo@example.com',
        'password':'senha-segura-123!',
    }
    created=client.post('/api/auth/register',json=payload)
    assert created.status_code==201,created.text
    assert created.json()['email']=='novo@example.com'
    assert created.json()['email_sent'] is True
    assert len(MEMORY_OUTBOX)==1
    assert client.post('/api/auth/login',json={'email':'novo@example.com','password':payload['password']}).status_code==403

    token=MEMORY_OUTBOX[-1]['token']
    verified=client.post('/api/auth/verify-email',json={'token':token})
    assert verified.status_code==200,verified.text
    logged=client.post('/api/auth/login',json={'email':'NOVO@example.com','password':payload['password']})
    assert logged.status_code==200,logged.text
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.email=='novo@example.com'))
        assert user and user.email_verified_at is not None


def test_registration_duplicate_and_resend(client):
    payload={'name':'Nova Conta','email':'pending@example.com','password':'senha-pending-123!'}
    assert client.post('/api/auth/register',json=payload).status_code==201
    assert client.post('/api/auth/register',json=payload).status_code==409
    first=MEMORY_OUTBOX[-1]['token']
    resend=client.post('/api/auth/resend-verification',json={'email':'pending@example.com'})
    assert resend.status_code==200
    second=MEMORY_OUTBOX[-1]['token']
    assert first!=second
    assert client.post('/api/auth/verify-email',json={'token':first}).status_code==400
    assert client.post('/api/auth/verify-email',json={'token':second}).status_code==200


def test_password_recovery_is_generic_and_revokes_sessions(client):
    login=client.post('/api/auth/login',json={'email':'test@example.com','password':'testing-password-123!'})
    assert login.status_code==200
    before=len(MEMORY_OUTBOX)
    unknown=client.post('/api/auth/forgot-password',json={'email':'unknown@example.com'})
    assert unknown.status_code==200
    assert len(MEMORY_OUTBOX)==before

    known=client.post('/api/auth/forgot-password',json={'email':'test@example.com'})
    assert known.status_code==200
    token=MEMORY_OUTBOX[-1]['token']
    reset=client.post('/api/auth/reset-password',json={'token':token,'password':'nova-senha-segura-456!'})
    assert reset.status_code==200,reset.text
    assert client.get('/api/leads').status_code==401
    assert client.post('/api/auth/reset-password',json={'token':token,'password':'outra-senha-segura-789!'}).status_code==400
    assert client.post('/api/auth/login',json={'email':'test@example.com','password':'testing-password-123!'}).status_code==401
    assert client.post('/api/auth/login',json={'email':'test@example.com','password':'nova-senha-segura-456!'}).status_code==200


def test_expired_verification_token_is_rejected(client):
    client.post('/api/auth/register',json={'name':'Expirada','email':'expirada@example.com','password':'senha-expirada-123!'})
    token=MEMORY_OUTBOX[-1]['token']
    with SessionLocal() as db:
        item=db.scalar(select(AccountToken).where(AccountToken.user_id==select(User.id).where(User.email=='expirada@example.com').scalar_subquery()))
        item.expires=int(time.time())-1
        db.commit()
    response=client.post('/api/auth/verify-email',json={'token':token})
    assert response.status_code==400


def test_auth_config(client):
    config=client.get('/api/auth/config')
    assert config.status_code==200
    assert config.json()=={'registration_enabled':True,'email_configured':True}
