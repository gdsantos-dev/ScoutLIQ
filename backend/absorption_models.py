"""Staging for externally researched opportunities. Never creates a second Lead/Score."""
import time
from sqlalchemy import String, Integer, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base
from .models import uid

class AbsorptionBatch(Base):
    __tablename__ = 'absorption_batches'
    __table_args__ = (UniqueConstraint('user_id', 'request_key', name='uq_absorption_request'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    request_key: Mapped[str] = mapped_column(String(36))
    source: Mapped[str] = mapped_column(String(20))
    payload_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default='previewed')
    version: Mapped[int] = mapped_column(Integer, default=1)
    ordinal: Mapped[int] = mapped_column(Integer, default=0)
    input_hash: Mapped[str] = mapped_column(String(64), default='')
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()))
    committed_at: Mapped[int | None] = mapped_column(Integer, nullable=True)

class AbsorptionItem(Base):
    __tablename__ = 'absorption_items'
    __table_args__ = (UniqueConstraint('batch_id', 'position', name='uq_absorption_position'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey('absorption_batches.id', ondelete='CASCADE'), index=True)
    position: Mapped[int] = mapped_column(Integer)
    payload_json: Mapped[str] = mapped_column(Text)
    original_json: Mapped[str] = mapped_column(Text, default='{}')
    history_json: Mapped[str] = mapped_column(Text, default='[]')
    issues_json: Mapped[str] = mapped_column(Text, default='[]')
    matches_json: Mapped[str] = mapped_column(Text, default='[]')
    review_json: Mapped[str] = mapped_column(Text, default='{}')
    suggestions_json: Mapped[str] = mapped_column(Text, default='[]')
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(String(240), default='')
    lead_id: Mapped[str | None] = mapped_column(ForeignKey('leads.id', ondelete='SET NULL'), nullable=True)


class AbsorptionRecovery(Base):
    __tablename__ = 'absorption_recoveries'
    __table_args__ = (UniqueConstraint('user_id','request_key',name='uq_absorption_recovery_request'),)
    id: Mapped[str] = mapped_column(String(36),primary_key=True,default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id',ondelete='CASCADE'),index=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey('absorption_batches.id',ondelete='CASCADE'),index=True)
    request_key: Mapped[str] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(20),default='pending',index=True)
    state_json: Mapped[str] = mapped_column(Text,default='{}')
    attempts: Mapped[int] = mapped_column(Integer,default=0)
    lease_token: Mapped[str] = mapped_column(String(36),default='')
    lease_until: Mapped[int] = mapped_column(Integer,default=0)
    retry_at: Mapped[int] = mapped_column(Integer,default=0)
    created_at: Mapped[int] = mapped_column(Integer,default=lambda:int(time.time()))
    deadline: Mapped[int] = mapped_column(Integer)
    error: Mapped[str] = mapped_column(String(240),default='')
