"""Bounded autocomplete cache and durable reservations in the existing ledger."""
import hashlib
import json
import os
import time
from uuid import uuid4
from sqlalchemy import Integer, String, Text, ForeignKey, select, update, delete, func
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base, SessionLocal
from .autonomy_models import WorkAttempt, ProviderOperation
from .locations import LocationCatalogError


class LocationGate(Base):
    __tablename__ = 'location_gate'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[int] = mapped_column(Integer, default=0)


class LocationCache(Base):
    __tablename__ = 'location_cache'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    expires_at: Mapped[int] = mapped_column(Integer, index=True)
    payload: Mapped[str] = mapped_column(Text)


def search(user_id, query, country='', lang='pt', *, administrative=True):
    from .locations import search_locations
    if not 2 <= len(query.strip()) <= 160:
        raise LocationCatalogError("Invalid location query length")
    key = os.getenv('RADAR_GEOAPIFY_API_KEY', '').strip()
    if not key:
        return search_locations(query, country, lang, administrative=administrative)
    try:
        daily = int(os.getenv('RADAR_LOCATION_DAILY_CALLS', '300'))
        per_user = int(os.getenv('RADAR_LOCATION_USER_DAILY_CALLS', '100'))
        ttl = int(os.getenv('RADAR_LOCATION_CACHE_SECONDS', '3600'))
        if not (0 <= per_user <= daily <= 100000 and 60 <= ttl <= 86400): raise ValueError()
    except ValueError:
        raise LocationCatalogError('Autocomplete budget configuration invalid') from None
    now = int(time.time())
    # No query, credentials or provider URL is written to the ledger.
    signature = hashlib.sha256(json.dumps([user_id, query.strip().casefold(), country, lang,
        administrative, key, os.getenv('RADAR_GEOAPIFY_URL', '')]).encode()).hexdigest()
    token = str(uuid4())
    with SessionLocal() as db:
        db.execute(update(LocationGate).where(LocationGate.id == 1).values(version=LocationGate.version + 1))
        db.execute(delete(LocationCache).where(LocationCache.expires_at <= now))
        cached = db.get(LocationCache, signature)
        if cached:
            result = json.loads(cached.payload)
            db.commit()
            return result
        counted = select(func.count()).select_from(WorkAttempt).where(
            WorkAttempt.kind == 'location', WorkAttempt.started_at >= now // 86400 * 86400)
        if db.scalar(counted) >= daily or db.scalar(counted.where(WorkAttempt.user_id == user_id)) >= per_user:
            raise LocationCatalogError('Autocomplete daily limit reached')
        db.add(WorkAttempt(token=token, user_id=user_id, kind='location', item_id=token, started_at=now))
        db.flush()
        db.add(ProviderOperation(id=token, token=token, provider='geoapify-location', started_at=now))
        db.commit()  # An interruption never refunds a possibly consumed request.
    result = None
    try:
        result = search_locations(query, country, lang, administrative=administrative)
        return result
    finally:
        with SessionLocal() as db:
            db.execute(update(LocationGate).where(LocationGate.id == 1).values(version=LocationGate.version + 1))
            operation = db.get(ProviderOperation, token)
            attempt = db.get(WorkAttempt, token)
            operation.status = attempt.status = 'done' if result is not None else 'error'
            operation.finished_at = attempt.finished_at = int(time.time())
            if result is not None:
                cached = db.get(LocationCache, signature)
                if not cached:
                    cached = LocationCache(id=signature, user_id=user_id)
                    db.add(cached)
                cached.payload = json.dumps(result)
                cached.expires_at = now + ttl
            db.commit()
