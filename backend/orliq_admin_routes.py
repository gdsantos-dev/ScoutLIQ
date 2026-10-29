from __future__ import annotations

import os
import secrets
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session as DBSession

from .config import ORLIQ_ADMIN_API_KEY
from .db import get_db
from .models import Session, User

router = APIRouter(prefix='/api/orliq-admin', tags=['ORLIQ Admin'])


class AdminUserUpdate(BaseModel):
    role: str | None = Field(default=None, pattern='^(user|admin)$')
    is_active: bool | None = None


def require_orliq_admin(x_orliq_admin_key: str = Header(default='')):
    if not ORLIQ_ADMIN_API_KEY or not secrets.compare_digest(x_orliq_admin_key, ORLIQ_ADMIN_API_KEY):
        raise HTTPException(401, 'Credencial administrativa inválida.')
    return True


def serialize_user(user: User) -> dict:
    return {
        'id': user.id,
        'name': user.name,
        'email': user.email,
        'role': user.role,
        'is_active': bool(user.is_active),
        'email_verified': user.email_verified_at is not None,
        'created_at': user.created_at,
        'last_login_at': user.last_login_at,
    }


@router.get('/users')
def list_users(_auth=Depends(require_orliq_admin), db: DBSession = Depends(get_db)):
    users = list(db.scalars(select(User).order_by(User.created_at.desc(), User.email.asc())).all())
    return {
        'summary': {
            'total': len(users),
            'active': sum(bool(item.is_active) for item in users),
            'pending': sum(item.email_verified_at is None for item in users),
            'admins': sum(item.role == 'admin' for item in users),
        },
        'items': [serialize_user(item) for item in users],
    }


@router.patch('/users/{user_id}')
def update_user(user_id: str, payload: AdminUserUpdate, _auth=Depends(require_orliq_admin), db: DBSession = Depends(get_db)):
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(404, 'Usuário não encontrado.')
    primary_email = os.getenv('ADMIN_EMAIL', '').strip().casefold()
    if primary_email and target.email.casefold() == primary_email:
        if payload.is_active is False:
            raise HTTPException(400, 'A conta administrativa principal não pode ser suspensa.')
        if payload.role == 'user':
            raise HTTPException(400, 'A conta administrativa principal deve continuar como administradora.')
    if payload.role is not None:
        target.role = payload.role
    if payload.is_active is not None:
        target.is_active = payload.is_active
        if not target.is_active:
            db.execute(delete(Session).where(Session.user_id == target.id))
    db.commit()
    db.refresh(target)
    return serialize_user(target)


@router.post('/users/{user_id}/revoke-sessions')
def revoke_sessions(user_id: str, _auth=Depends(require_orliq_admin), db: DBSession = Depends(get_db)):
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(404, 'Usuário não encontrado.')
    db.execute(delete(Session).where(Session.user_id == target.id))
    db.commit()
    return {'ok': True, 'message': 'Sessões revogadas.'}
