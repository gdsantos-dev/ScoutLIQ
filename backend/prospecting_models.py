"""Planning metadata only. Runs, companies and investigations remain canonical."""
import time
from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base
from .models import uid


class ProspectingPlan(Base):
    __tablename__ = 'prospecting_plans'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), unique=True)
    config_json: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(20), default='disabled')
    version: Mapped[int] = mapped_column(Integer, default=1)
    timezone: Mapped[str] = mapped_column(String(64))
    authorization: Mapped[str] = mapped_column(String(64), default='')
    next_check_at: Mapped[int] = mapped_column(Integer, default=0, index=True)
    reason: Mapped[str] = mapped_column(String(300), default='Plano desativado.')
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()))
    __mapper_args__ = {'version_id_col': version}


class PlanMember(Base):
    __tablename__ = 'prospecting_plan_members'
    plan_id: Mapped[str] = mapped_column(ForeignKey('prospecting_plans.id', ondelete='CASCADE'), primary_key=True)
    saved_search_id: Mapped[str] = mapped_column(ForeignKey('radar_saved_searches.id', ondelete='CASCADE'), primary_key=True)
    priority: Mapped[int] = mapped_column(Integer, default=1)


class PlanDecision(Base):
    __tablename__ = 'prospecting_plan_decisions'
    __table_args__ = (UniqueConstraint('plan_id', 'key', name='uq_plan_decision_key'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    plan_id: Mapped[str] = mapped_column(ForeignKey('prospecting_plans.id', ondelete='CASCADE'), index=True)
    key: Mapped[str] = mapped_column(String(100))
    at: Mapped[int] = mapped_column(Integer, index=True)
    version: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str] = mapped_column(String(300))
    details_json: Mapped[str] = mapped_column(Text, default='{}')
    run_id: Mapped[str | None] = mapped_column(ForeignKey('routine_runs.id', ondelete='SET NULL'), nullable=True, unique=True)


class PlanIncorporation(Base):
    __tablename__ = 'prospecting_plan_incorporations'
    lead_id: Mapped[str] = mapped_column(ForeignKey('leads.id', ondelete='CASCADE'), primary_key=True)
    decision_id: Mapped[str | None] = mapped_column(ForeignKey('prospecting_plan_decisions.id', ondelete='SET NULL'), nullable=True, index=True)
    search_id: Mapped[str | None] = mapped_column(ForeignKey('smart_searches.id', ondelete='SET NULL'), nullable=True)
    discarded: Mapped[bool] = mapped_column(Boolean, default=False)
    at: Mapped[int] = mapped_column(Integer, index=True)
