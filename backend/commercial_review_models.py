"""Human triage plus a disposable index of canonical commercial assessments."""
import time
from sqlalchemy import String, Integer, Text, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base
from .models import uid


class CommercialReview(Base):
    __tablename__ = 'commercial_reviews'
    __table_args__ = (Index('ix_review_queue', 'user_id', 'dirty', 'classification', 'score_cache'),
        Index('ix_followup_queue','user_id','followup_dirty','followup_rank','followup_due'))
    lead_id: Mapped[str] = mapped_column(ForeignKey('leads.id', ondelete='CASCADE'), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    state: Mapped[str] = mapped_column(String(24), default='unreviewed')
    version: Mapped[int] = mapped_column(Integer, default=1)
    author_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    decided_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason: Mapped[str] = mapped_column(String(500), default='')
    review_hash: Mapped[str] = mapped_column(String(64), default='')
    context_hash: Mapped[str] = mapped_column(String(64), default='')
    score_cache: Mapped[int] = mapped_column(Integer, default=0)
    classification: Mapped[str] = mapped_column(String(20), default='pending')
    generation: Mapped[int] = mapped_column(Integer, default=0)
    dirty: Mapped[int] = mapped_column(Integer, default=1)
    refresh_at: Mapped[int] = mapped_column(Integer, default=0)
    followup_json: Mapped[str] = mapped_column(Text, default='{}')
    followup_category: Mapped[str] = mapped_column(String(24), default='pending')
    followup_rank: Mapped[int] = mapped_column(Integer, default=50)
    followup_due: Mapped[str] = mapped_column(String(10), default='')
    followup_confidence: Mapped[int] = mapped_column(Integer, default=0)
    followup_last: Mapped[int] = mapped_column(Integer, default=0)
    followup_dirty: Mapped[int] = mapped_column(Integer, default=1)
    followup_generation: Mapped[int] = mapped_column(Integer, default=0)
    followup_refresh_at: Mapped[int] = mapped_column(Integer, default=0)
    __mapper_args__ = {'version_id_col': version}


class CommercialOperation(Base):
    __tablename__ = 'commercial_operations'
    __table_args__ = (UniqueConstraint('user_id', 'request_key', name='uq_commercial_operation'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    request_key: Mapped[str] = mapped_column(String(36))
    request_hash: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(20), default='preview')
    payload_json: Mapped[str] = mapped_column(Text)
    preview_json: Mapped[str] = mapped_column(Text)
    result_json: Mapped[str] = mapped_column(Text, default='[]')
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()))
    committed_at: Mapped[int | None] = mapped_column(Integer, nullable=True)

