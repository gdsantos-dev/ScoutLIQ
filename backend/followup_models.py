"""Operator preferences only; communication facts remain in their canonical tables."""
from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


class FollowupSettings(Base):
    __tablename__ = 'followup_settings'
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    interval_days: Mapped[int] = mapped_column(Integer, default=7)
    version: Mapped[int] = mapped_column(Integer, default=1)
    __mapper_args__ = {'version_id_col': version}


class FollowupPreference(Base):
    __tablename__ = 'followup_preferences'
    lead_id: Mapped[str] = mapped_column(ForeignKey('leads.id', ondelete='CASCADE'), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    disabled: Mapped[int] = mapped_column(Integer, default=0)
    snooze_until: Mapped[str] = mapped_column(String(10), default='')
    dismissed_key: Mapped[str] = mapped_column(String(64), default='')
    version: Mapped[int] = mapped_column(Integer, default=1)
    __mapper_args__ = {'version_id_col': version}
