"""Channel credentials and execution records; Lead/Draft/RecipientPolicy stay canonical."""
import time
from sqlalchemy import String, Integer, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base
from .models import uid


class ChannelAccount(Base):
    __tablename__ = 'channel_accounts'
    __table_args__ = (UniqueConstraint('user_id', 'provider', 'identity', name='uq_channel_identity'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    provider: Mapped[str] = mapped_column(String(20), default='gmail')
    channel: Mapped[str] = mapped_column(String(20), default='email')
    identity: Mapped[str] = mapped_column(String(254))
    status: Mapped[str] = mapped_column(String(30), default='connected')
    credentials: Mapped[str] = mapped_column(Text, default='')
    scopes: Mapped[str] = mapped_column(Text, default='')
    version: Mapped[int] = mapped_column(Integer, default=1)
    cursor: Mapped[str] = mapped_column(String(100), default='')
    sync_json: Mapped[str] = mapped_column(Text, default='{}')
    next_sync_at: Mapped[int] = mapped_column(Integer, default=0)
    sync_enabled: Mapped[int] = mapped_column(Integer, default=0)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    lease_token: Mapped[str] = mapped_column(String(36), default='')
    lease_until: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(String(300), default='')
    updated_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()))


class OAuthState(Base):
    __tablename__ = 'communication_oauth_states'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # Only hash, never bearer state.
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    session_id: Mapped[str] = mapped_column(String(64))
    verifier: Mapped[str] = mapped_column(Text)
    account_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    expires_at: Mapped[int] = mapped_column(Integer)
    used_at: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ContactVerification(Base):
    __tablename__ = 'contact_verifications'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    policy_id: Mapped[str] = mapped_column(ForeignKey('recipient_policies.id', ondelete='CASCADE'), index=True)
    policy_version: Mapped[int] = mapped_column(Integer)
    record_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[int] = mapped_column(Integer)


class OutboxMessage(Base):
    __tablename__ = 'communication_outbox'
    __table_args__ = (UniqueConstraint('user_id', 'request_key', name='uq_outbox_request'),
                     UniqueConstraint('draft_id', 'draft_version', name='uq_outbox_draft_revision'))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    lead_id: Mapped[str | None] = mapped_column(ForeignKey('leads.id', ondelete='SET NULL'), index=True, nullable=True)
    draft_id: Mapped[str | None] = mapped_column(ForeignKey('outreach_drafts.id', ondelete='SET NULL'), nullable=True)
    account_id: Mapped[str] = mapped_column(ForeignKey('channel_accounts.id', ondelete='CASCADE'), index=True)
    request_key: Mapped[str] = mapped_column(String(36))
    input_hash: Mapped[str] = mapped_column(String(64))
    draft_version: Mapped[int] = mapped_column(Integer)
    channel: Mapped[str] = mapped_column(String(20))
    recipient: Mapped[str] = mapped_column(String(254))
    snapshot_json: Mapped[str] = mapped_column(Text)
    authorization_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default='queued', index=True)
    due_at: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[int] = mapped_column(Integer)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    lease_token: Mapped[str] = mapped_column(String(36), default='')
    lease_until: Mapped[int] = mapped_column(Integer, default=0)
    wire_started_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message_id: Mapped[str] = mapped_column(String(200))
    provider_id: Mapped[str] = mapped_column(String(200), default='')
    thread_id: Mapped[str] = mapped_column(String(200), default='')
    error: Mapped[str] = mapped_column(String(300), default='')
    cancel_requested: Mapped[int] = mapped_column(Integer, default=0)
    reconcile_at: Mapped[int] = mapped_column(Integer, default=0)
    reconcile_count: Mapped[int] = mapped_column(Integer, default=0)


class MessageEvent(Base):
    __tablename__ = 'communication_events'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    outbox_id: Mapped[str] = mapped_column(ForeignKey('communication_outbox.id', ondelete='CASCADE'), index=True)
    event: Mapped[str] = mapped_column(String(40))
    detail: Mapped[str] = mapped_column(String(500), default='')
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()))


class ReceivedMessage(Base):
    __tablename__ = 'communication_received'
    __table_args__ = (UniqueConstraint('account_id', 'provider_id', name='uq_received_message'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    account_id: Mapped[str] = mapped_column(ForeignKey('channel_accounts.id', ondelete='CASCADE'), index=True)
    lead_id: Mapped[str | None] = mapped_column(ForeignKey('leads.id', ondelete='SET NULL'), nullable=True)
    provider_id: Mapped[str] = mapped_column(String(200))
    thread_id: Mapped[str] = mapped_column(String(200))
    classification: Mapped[str] = mapped_column(String(30))
    association: Mapped[str] = mapped_column(String(30))
    text: Mapped[str] = mapped_column(Text, default='')
    sent_at: Mapped[int] = mapped_column(Integer)
    received_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()))
