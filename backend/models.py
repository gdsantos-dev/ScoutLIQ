import time
import uuid
from sqlalchemy import String, Integer, Float, Boolean, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

def uid():
    return str(uuid.uuid4())

class User(Base):
    __tablename__ = 'users'
    investigation_json: Mapped[str] = mapped_column(Text, default='{}')
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(String(80), default='Minha operação')
    accent: Mapped[str] = mapped_column(String(20), default='crimson')
    motion: Mapped[str] = mapped_column(String(20), default='full')
    timezone: Mapped[str] = mapped_column(String(64), default='America/Sao_Paulo')
    locale: Mapped[str] = mapped_column(String(10), default='pt-BR')
    default_currency: Mapped[str] = mapped_column(String(3), default='BRL')
    email_verified_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    role: Mapped[str] = mapped_column(String(20), default='user', index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()), index=True)
    last_login_at: Mapped[int | None] = mapped_column(Integer, nullable=True)

class AccountToken(Base):
    __tablename__ = 'account_tokens'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    purpose: Mapped[str] = mapped_column(String(40), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires: Mapped[int] = mapped_column(Integer, index=True)
    used_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()))

class Session(Base):
    __tablename__ = 'sessions'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    csrf: Mapped[str] = mapped_column(String(64))
    expires: Mapped[int] = mapped_column(Integer)

class Lead(Base):
    score_criteria_json: Mapped[str] = mapped_column(Text, default='{}')
    qualification_json: Mapped[str] = mapped_column(Text, default='{}')
    previous_score_json: Mapped[str] = mapped_column(Text, default='{}')
    __tablename__ = 'leads'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    name: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(80))
    city: Mapped[str] = mapped_column(String(100))
    country: Mapped[str] = mapped_column(String(2), default='BR')
    address: Mapped[str] = mapped_column(String(250), default='')
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    reviews: Mapped[int | None] = mapped_column(Integer, nullable=True)
    website: Mapped[str] = mapped_column(String(500), default='')
    website_status: Mapped[str] = mapped_column(String(20), default='unknown')
    website_intelligence_json: Mapped[str] = mapped_column(Text, default='{}')
    website_analyzed_at: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    competitive_context_json: Mapped[str] = mapped_column(Text, default='{}')
    competitive_analyzed_at: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    commercial_signal_json: Mapped[str] = mapped_column(Text, default='{}')
    commercial_signal_analyzed_at: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    watchlisted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    watch_started_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    watch_last_checked_at: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    watch_last_event_at: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    enrichment_json: Mapped[str] = mapped_column(Text, default='{}')
    enrichment_analyzed_at: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    outcome_snapshot_json: Mapped[str] = mapped_column(Text, default='{}')
    outcome_recorded_at: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    instagram: Mapped[str] = mapped_column(String(500), default='')
    instagram_active: Mapped[bool] = mapped_column(Boolean, default=False)
    phone: Mapped[str] = mapped_column(String(30), default='')
    whatsapp: Mapped[str] = mapped_column(String(20), default='')
    contact: Mapped[str] = mapped_column(String(100), default='')
    contact_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    contact_block_reason: Mapped[str] = mapped_column(String(500), default='')
    stage: Mapped[str] = mapped_column(String(20), default='discovered', index=True)
    in_pipeline: Mapped[bool] = mapped_column(Boolean, default=False)
    potential_cents: Mapped[int] = mapped_column(Integer, default=0)
    potential_currency: Mapped[str] = mapped_column(String(3), default='BRL')
    notes: Mapped[str] = mapped_column(Text, default='')
    next_action: Mapped[str] = mapped_column(String(180), default='')
    next_action_on: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    pipeline_added_at: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    last_contact_at: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(50), default='manual')
    source_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    demo: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()))
    __mapper_args__ = {'version_id_col': version}

class LeadResearch(Base):
    __tablename__ = 'lead_research'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    lead_id: Mapped[str] = mapped_column(ForeignKey('leads.id', ondelete='CASCADE'), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default='unverified')
    provider: Mapped[str] = mapped_column(String(50), default='direct')
    website_url: Mapped[str] = mapped_column(String(500), default='')
    website_status: Mapped[str] = mapped_column(String(20), default='unknown')
    confidence: Mapped[int] = mapped_column(Integer, default=0)
    evidence_json: Mapped[str] = mapped_column(Text, default='[]')
    checks_json: Mapped[str] = mapped_column(Text, default='[]')
    sources_json: Mapped[str] = mapped_column(Text, default='[]')
    page_json: Mapped[str] = mapped_column(Text, default='{}')
    audit_level: Mapped[str] = mapped_column(String(20), default='none')
    audit_json: Mapped[str] = mapped_column(Text, default='{}')
    audited_at: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    search_configured: Mapped[bool] = mapped_column(Boolean, default=False)
    candidates_checked: Mapped[int] = mapped_column(Integer, default=0)
    fetch_errors: Mapped[int] = mapped_column(Integer, default=0)
    checked_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()), index=True)


class ResearchBatch(Base):
    __tablename__ = 'research_batches'
    ordinal: Mapped[int] = mapped_column(Integer, default=0)
    config_json: Mapped[str] = mapped_column(Text, default='{}')
    request_key: Mapped[str | None] = mapped_column(String(80), nullable=True)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    mode: Mapped[str] = mapped_column(String(20), default='deep')
    status: Mapped[str] = mapped_column(String(20), default='pending', index=True)
    requested_count: Mapped[int] = mapped_column(Integer, default=0)
    skipped_recent: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()), index=True)
    updated_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()))
    completed_at: Mapped[int | None] = mapped_column(Integer, nullable=True)


class SmartSearch(Base):
    """Orchestration only; identities and investigations remain Lead/ResearchBatch."""
    __tablename__ = 'smart_searches'
    __table_args__ = (UniqueConstraint('user_id', 'request_key', name='uq_smart_request'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    request_key: Mapped[str] = mapped_column(String(36))
    intent_json: Mapped[str] = mapped_column(Text)
    state_json: Mapped[str] = mapped_column(Text, default='{}')
    batch_id: Mapped[str | None] = mapped_column(ForeignKey('research_batches.id', ondelete='SET NULL'), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default='pending', index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    retry_at: Mapped[int] = mapped_column(Integer, default=0)
    lease_until: Mapped[int] = mapped_column(Integer, default=0)
    lease_token: Mapped[str] = mapped_column(String(36), default='')
    error: Mapped[str] = mapped_column(String(300), default='')
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()))
    updated_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()))
    deadline: Mapped[int] = mapped_column(Integer)

class ResearchBatchItem(Base):
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    retry_at: Mapped[int] = mapped_column(Integer, default=0)
    lease_until: Mapped[int] = mapped_column(Integer, default=0)
    lease_token: Mapped[str] = mapped_column(String(36), default='')
    __tablename__ = 'research_batch_items'
    phase: Mapped[str] = mapped_column(String(20), default='local')
    plan_json: Mapped[str] = mapped_column(Text, default='{}')
    charged_at: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (UniqueConstraint('batch_id', 'lead_id', name='uq_research_batch_item'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    batch_id: Mapped[str] = mapped_column(ForeignKey('research_batches.id', ondelete='CASCADE'), index=True)
    lead_id: Mapped[str] = mapped_column(ForeignKey('leads.id', ondelete='CASCADE'), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default='pending', index=True)
    outcome: Mapped[str] = mapped_column(String(40), default='')
    error: Mapped[str] = mapped_column(String(300), default='')
    started_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    finished_at: Mapped[int | None] = mapped_column(Integer, nullable=True)

class LeadActivity(Base):
    __tablename__ = 'lead_activities'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    lead_id: Mapped[str] = mapped_column(ForeignKey('leads.id', ondelete='CASCADE'), index=True)
    kind: Mapped[str] = mapped_column(String(30), index=True)
    body: Mapped[str] = mapped_column(Text, default='')
    metadata_json: Mapped[str] = mapped_column(Text, default='{}')
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()), index=True)

class RadarSavedSearch(Base):
    routine_config_json: Mapped[str] = mapped_column(Text, default='{}')
    routine_state: Mapped[str] = mapped_column(String(20), default='disabled', index=True)
    routine_next_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    routine_last_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    routine_seen_json: Mapped[str] = mapped_column(Text, default='[]')
    routine_reason: Mapped[str] = mapped_column(String(300), default='')
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    retry_at: Mapped[int] = mapped_column(Integer, default=0)
    lease_until: Mapped[int] = mapped_column(Integer, default=0)
    lease_token: Mapped[str] = mapped_column(String(36), default='')
    worker_error: Mapped[str] = mapped_column(String(300), default='')
    __tablename__ = 'radar_saved_searches'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    name: Mapped[str] = mapped_column(String(80))
    query_json: Mapped[str] = mapped_column(Text, default='{}')
    result_ids_json: Mapped[str] = mapped_column(Text, default='[]')
    last_new_count: Mapped[int] = mapped_column(Integer, default=0)
    last_run_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    monitor_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    monitor_interval: Mapped[str] = mapped_column(String(12), default='daily')
    next_monitor_at: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    last_monitor_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()))
    updated_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()))
    version: Mapped[int] = mapped_column(Integer, default=1)
    __table_args__ = (UniqueConstraint('user_id','name',name='uq_radar_saved_search_user_name'),)
    __mapper_args__ = {'version_id_col': version}


class AutomationRule(Base):
    __tablename__ = 'automation_rules'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    name: Mapped[str] = mapped_column(String(100))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    trigger: Mapped[str] = mapped_column(String(30), index=True)
    conditions_json: Mapped[str] = mapped_column(Text, default='[]')
    actions_json: Mapped[str] = mapped_column(Text, default='[]')
    stop_json: Mapped[str] = mapped_column(Text, default='{}')
    last_run_at: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()), index=True)
    updated_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()))
    version: Mapped[int] = mapped_column(Integer, default=1)
    __mapper_args__ = {'version_id_col': version}


class AutomationRun(Base):
    __tablename__ = 'automation_runs'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    rule_id: Mapped[str] = mapped_column(ForeignKey('automation_rules.id', ondelete='CASCADE'), index=True)
    lead_id: Mapped[str] = mapped_column(ForeignKey('leads.id', ondelete='CASCADE'), index=True)
    trigger: Mapped[str] = mapped_column(String(30), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    reason: Mapped[str] = mapped_column(String(160), default='')
    actions_json: Mapped[str] = mapped_column(Text, default='[]')
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()), index=True)


class Campaign(Base):
    __tablename__ = 'campaigns'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default='')
    status: Mapped[str] = mapped_column(String(20), default='active', index=True)
    source_saved_search_id: Mapped[str | None] = mapped_column(ForeignKey('radar_saved_searches.id', ondelete='SET NULL'), nullable=True, index=True)
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()), index=True)
    updated_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()))
    version: Mapped[int] = mapped_column(Integer, default=1)
    __table_args__ = (UniqueConstraint('user_id','name',name='uq_campaign_user_name'),)
    __mapper_args__ = {'version_id_col': version}


class CampaignLead(Base):
    __tablename__ = 'campaign_leads'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    campaign_id: Mapped[str] = mapped_column(ForeignKey('campaigns.id', ondelete='CASCADE'), index=True)
    lead_id: Mapped[str] = mapped_column(ForeignKey('leads.id', ondelete='CASCADE'), index=True)
    source: Mapped[str] = mapped_column(String(30), default='manual')
    added_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()), index=True)
    __table_args__ = (UniqueConstraint('campaign_id','lead_id',name='uq_campaign_lead'),)


class Sale(Base):
    __tablename__ = 'sales'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    lead_id: Mapped[str] = mapped_column(ForeignKey('leads.id'), unique=True)
    campaign_id: Mapped[str | None] = mapped_column(ForeignKey('campaigns.id', ondelete='SET NULL'), nullable=True, index=True)
    service: Mapped[str] = mapped_column(String(160))
    amount_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default='BRL')
    recurring_cents: Mapped[int] = mapped_column(Integer, default=0)
    project_status: Mapped[str] = mapped_column(String(20), default='progress')
    sold_on: Mapped[str] = mapped_column(String(10), index=True)
    due_on: Mapped[str] = mapped_column(String(10))
    demo: Mapped[bool] = mapped_column(Boolean, default=False)
    export_id: Mapped[str] = mapped_column(String(36), unique=True, default=uid)

class Payment(Base):
    __tablename__ = 'payments'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    sale_id: Mapped[str] = mapped_column(ForeignKey('sales.id'))
    amount_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default='BRL')
    paid_on: Mapped[str] = mapped_column(String(10))
    export_id: Mapped[str] = mapped_column(String(36), unique=True, default=uid)
    request_id: Mapped[str] = mapped_column(String(36), unique=True)

class Site(Base):
    __tablename__ = 'sites'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    sale_id: Mapped[str] = mapped_column(ForeignKey('sales.id'))
    name: Mapped[str] = mapped_column(String(160))
    url: Mapped[str] = mapped_column(String(500), default='')
    domain: Mapped[str] = mapped_column(String(253), default='')
    domain_owner: Mapped[str] = mapped_column(String(160), default='')
    renewal_on: Mapped[str | None] = mapped_column(String(10), nullable=True)
    hosting: Mapped[str] = mapped_column(String(160), default='')
    plan: Mapped[str] = mapped_column(String(160), default='')
    maintenance: Mapped[str] = mapped_column(Text, default='')
    monthly_revenue_cents: Mapped[int] = mapped_column(Integer, default=0)
    monthly_cost_cents: Mapped[int] = mapped_column(Integer, default=0)
    annual_domain_cost_cents: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(3), default='BRL')
    ssl_status: Mapped[str] = mapped_column(String(20), default='unknown')
    ssl_expires_on: Mapped[str | None] = mapped_column(String(10), nullable=True)
    analytics_url: Mapped[str] = mapped_column(String(500), default='')
    repository_url: Mapped[str] = mapped_column(String(500), default='')
    admin_url: Mapped[str] = mapped_column(String(500), default='')
    status: Mapped[str] = mapped_column(String(20), default='building')
    notes: Mapped[str] = mapped_column(Text, default='')
    demo: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    __mapper_args__ = {'version_id_col': version}

class Expense(Base):
    __tablename__ = 'expenses'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    description: Mapped[str] = mapped_column(String(160))
    amount_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default='BRL')
    incurred_on: Mapped[str] = mapped_column(String(10))
    demo: Mapped[bool] = mapped_column(Boolean, default=False)
    export_id: Mapped[str] = mapped_column(String(36), unique=True, default=uid)
    request_id: Mapped[str] = mapped_column(String(36), unique=True)


class ResearchExecutor(Base):
    __tablename__ = 'research_executor'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token: Mapped[str] = mapped_column(String(36), default='')
    lease_until: Mapped[int] = mapped_column(Integer, default=0)
    next_at: Mapped[int] = mapped_column(Integer, default=0)
    day: Mapped[int] = mapped_column(Integer, default=0)
    used: Mapped[int] = mapped_column(Integer, default=0)
