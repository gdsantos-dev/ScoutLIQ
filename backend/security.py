import hashlib
import re
import secrets
import time
from collections import defaultdict, deque
from threading import Lock, BoundedSemaphore
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select, delete
from sqlalchemy.orm import Session as DBSession
from .db import get_db
from .models import User, Session


EMAIL_PATTERN = re.compile(
    r"^[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?"
    r"(?:\.[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?)+$",
    re.IGNORECASE,
)

def normalize_email(value):
    email = str(value or '').strip().casefold()
    if len(email) > 254 or not EMAIL_PATTERN.fullmatch(email):
        raise ValueError('Informe um endereço de e-mail válido.')
    return email

hasher = PasswordHasher(time_cost=3, memory_cost=19456, parallelism=1)
dummy_hash = hasher.hash(secrets.token_urlsafe(32))
verification_slots = BoundedSemaphore(2)

def verify(password, encoded):
    try:
        with verification_slots:
            return hasher.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False

def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()

class Limiter:
    def __init__(self):
        self.events = defaultdict(deque)
        self.lock = Lock()
    def check(self, key, limit=20, seconds=60):
        now = time.monotonic()
        with self.lock:
            if len(self.events) > 5000:
                self.events = defaultdict(deque, {k:v for k,v in self.events.items() if v and v[-1] > now-900})
                if len(self.events) > 10000:
                    raise HTTPException(429,'Servidor ocupado. Tente novamente em instantes.')
            queue = self.events[key]
            while queue and queue[0] <= now-seconds:
                queue.popleft()
            if len(queue) >= limit:
                raise HTTPException(429,'Muitas tentativas. Aguarde antes de tentar novamente.',headers={'Retry-After':str(seconds)})
            queue.append(now)

limiter = Limiter()

def current_user(request: Request, db: DBSession = Depends(get_db)):
    raw = request.cookies.get('scout_session','')
    session = db.get(Session,digest(raw)) if raw else None
    if not session or session.expires <= int(time.time()):
        raise HTTPException(401,'Entre para continuar.')
    user = db.get(User, session.user_id)
    if not user:
        raise HTTPException(401,'Sessão inválida.')
    if not user.is_active:
        raise HTTPException(403,'Conta suspensa.')
    if request.method not in ('GET','HEAD','OPTIONS'):
        if not secrets.compare_digest(request.headers.get('X-CSRF-Token',''),session.csrf):
            raise HTTPException(403,'Sessão de segurança inválida. Atualize a página.')
        limiter.check('write:'+user.id,120,60)
    request.state.session = session
    return user
