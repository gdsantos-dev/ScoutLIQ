"""Operational records; Lead, SmartSearch and ResearchBatch remain canonical."""
import time
from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base
from .models import uid


class RoutineRun(Base):
    __tablename__ = 'routine_runs'
    __table_args__ = (UniqueConstraint('saved_search_id', 'scheduled_at', name='uq_routine_slot'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    saved_search_id: Mapped[str] = mapped_column(ForeignKey('radar_saved_searches.id', ondelete='CASCADE'), index=True)
    scheduled_at: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[int] = mapped_column(Integer)
    finished_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    search_id: Mapped[str | None] = mapped_column(ForeignKey('smart_searches.id', ondelete='SET NULL'), nullable=True)
    batch_id: Mapped[str | None] = mapped_column(ForeignKey('research_batches.id', ondelete='SET NULL'), nullable=True)
    config_json: Mapped[str] = mapped_column(Text)
    result_json: Mapped[str] = mapped_column(Text, default='{}')
    status: Mapped[str] = mapped_column(String(20), default='running', index=True)
    reason: Mapped[str] = mapped_column(String(300), default='')


class RoutineEvent(Base):
    __tablename__ = 'routine_events'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    saved_search_id: Mapped[str] = mapped_column(ForeignKey('radar_saved_searches.id', ondelete='CASCADE'), index=True)
    action: Mapped[str] = mapped_column(String(30))
    detail_json: Mapped[str] = mapped_column(Text, default='{}')
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()))


class WorkAttempt(Base):
    __tablename__ = 'work_attempts'
    token: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    run_id: Mapped[str | None] = mapped_column(ForeignKey('routine_runs.id', ondelete='SET NULL'), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(20))
    item_id: Mapped[str] = mapped_column(String(36))
    started_at: Mapped[int] = mapped_column(Integer, index=True)
    finished_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default='claimed')


class ProviderOperation(Base):
    __tablename__ = 'provider_operations'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    token: Mapped[str] = mapped_column(ForeignKey('work_attempts.token', ondelete='CASCADE'), index=True)
    provider: Mapped[str] = mapped_column(String(30), index=True)
    started_at: Mapped[int] = mapped_column(Integer, index=True)
    finished_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default='reserved')


class WorkerHeartbeat(Base):
    __tablename__ = 'worker_heartbeats'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    started_at: Mapped[int] = mapped_column(Integer)
    heartbeat_at: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(20))
    task_deadline: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(String(160), default='')
