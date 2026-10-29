"""Evidence and approval records supplement Lead; CRM history remains LeadActivity."""
import time
from sqlalchemy import String, Integer, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base
from .models import uid


class OpportunityEvidence(Base):
    __tablename__ = 'opportunity_evidence'
    __table_args__ = (UniqueConstraint('lead_id', 'source_key', name='uq_evidence_source'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    lead_id: Mapped[str] = mapped_column(ForeignKey('leads.id', ondelete='CASCADE'), index=True)
    source_key: Mapped[str] = mapped_column(String(100))
    statement: Mapped[str] = mapped_column(String(600))
    source_url: Mapped[str] = mapped_column(String(1000))
    method: Mapped[str] = mapped_column(String(30))
    classification: Mapped[str] = mapped_column(String(20), default='unverified')
    observed_at: Mapped[int] = mapped_column(Integer)
    valid_until: Mapped[int] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(Integer, default=1)
    category: Mapped[str] = mapped_column(String(30), default='general')
    scope: Mapped[str] = mapped_column(String(500), default='')
    research_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    verified_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    review_reason: Mapped[str] = mapped_column(String(500), default='')
    observation_key: Mapped[str] = mapped_column(String(40), default='')
    observation_state: Mapped[str] = mapped_column(String(20), default='')
    analyzer_version: Mapped[str] = mapped_column(String(30), default='operator')
    relation: Mapped[str] = mapped_column(String(20), default='current')
    related_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    translations_json: Mapped[str] = mapped_column(Text, default='{}')
    __mapper_args__ = {'version_id_col': version}


class OutreachDraft(Base):
    __tablename__ = 'outreach_drafts'
    __table_args__ = (UniqueConstraint('user_id', 'request_id', name='uq_outreach_request'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    lead_id: Mapped[str] = mapped_column(ForeignKey('leads.id', ondelete='CASCADE'), index=True)
    request_id: Mapped[str] = mapped_column(String(36))
    channel: Mapped[str] = mapped_column(String(20))
    locale: Mapped[str] = mapped_column(String(10))
    recipient: Mapped[str] = mapped_column(String(254))
    subject: Mapped[str] = mapped_column(String(200), default='')
    body: Mapped[str] = mapped_column(Text)
    evidence_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default='draft')
    approval_hash: Mapped[str] = mapped_column(String(64), default='')
    authorization_ref: Mapped[str] = mapped_column(String(500), default='')
    authorized_until: Mapped[int | None] = mapped_column(Integer, nullable=True)
    approved_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()))
    updated_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()))
    version: Mapped[int] = mapped_column(Integer, default=1)
    strategy: Mapped[str] = mapped_column(String(30), default='verified_opportunity')
    generation_method: Mapped[str] = mapped_column(String(30), default='deterministic-v2')
    __mapper_args__ = {'version_id_col': version}


class RecipientPolicy(Base):
    """Exact recipient identity within one account; no domain/person inference."""
    __tablename__ = 'recipient_policies'
    __table_args__ = (UniqueConstraint('user_id', 'channel', 'recipient', name='uq_recipient_policy'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    channel: Mapped[str] = mapped_column(String(20))
    recipient: Mapped[str] = mapped_column(String(254))
    blocked: Mapped[int] = mapped_column(Integer, default=0)
    basis: Mapped[str] = mapped_column(String(30), default='unknown')
    reference: Mapped[str] = mapped_column(String(1000), default='')
    reason: Mapped[str] = mapped_column(String(500), default='')
    market: Mapped[str] = mapped_column(String(2), default='')
    recorded_at: Mapped[int] = mapped_column(Integer)
    valid_until: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    __mapper_args__ = {'version_id_col': version}
