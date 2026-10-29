"""Shared communication execution, credentials, consent reviews and receipts."""
from alembic import op
import sqlalchemy as sa

revision = '026'
down_revision = '025'
branch_labels = depends_on = None


def upgrade():
    def s(n, size=36, **kw): return sa.Column(n, sa.String(size), nullable=False, **kw)
    def i(n): return sa.Column(n, sa.Integer(), nullable=False)
    def t(n): return sa.Column(n, sa.Text(), nullable=False)
    def fk(n, target, action='CASCADE', nullable=False):
        return sa.Column(n, sa.String(36), sa.ForeignKey(target, ondelete=action), nullable=nullable)
    def identity(): return [s('id', primary_key=True), fk('user_id', 'users.id')]
    op.create_table('channel_accounts', *identity(), s('provider',20), s('channel',20), s('identity',254),
        s('status',30), t('credentials'), t('scopes'), i('version'), s('cursor',100), t('sync_json'),
        i('next_sync_at'), i('sync_enabled'), i('attempts'), s('lease_token'), i('lease_until'),
        s('error',300), i('updated_at'), sa.UniqueConstraint('user_id','provider','identity',name='uq_channel_identity'))
    op.create_table('communication_oauth_states', s('id',64,primary_key=True), fk('user_id','users.id'),
        s('session_id',64), t('verifier'), sa.Column('account_id',sa.String(36),nullable=True),
        i('expires_at'), sa.Column('used_at',sa.Integer(),nullable=True))
    op.create_table('contact_verifications', *identity(), fk('policy_id','recipient_policies.id'),
        i('policy_version'), t('record_json'), i('created_at'), i('expires_at'))
    op.create_table('communication_outbox', *identity(), fk('lead_id','leads.id','SET NULL',True),
        fk('draft_id','outreach_drafts.id','SET NULL',True), fk('account_id','channel_accounts.id'),
        s('request_key'), s('input_hash',64), i('draft_version'), s('channel',20), s('recipient',254),
        t('snapshot_json'), t('authorization_json'), s('status',30), i('due_at'), i('expires_at'),
        i('created_at'), i('updated_at'), i('attempts'), s('lease_token'), i('lease_until'),
        sa.Column('wire_started_at',sa.Integer(),nullable=True), s('message_id',200), s('provider_id',200),
        s('thread_id',200), s('error',300), i('cancel_requested'), i('reconcile_at'), i('reconcile_count'),
        sa.UniqueConstraint('user_id','request_key',name='uq_outbox_request'),
        sa.UniqueConstraint('draft_id','draft_version',name='uq_outbox_draft_revision'))
    op.create_table('communication_events', *identity(), fk('outbox_id','communication_outbox.id'),
        s('event',40), s('detail',500), i('created_at'))
    op.create_table('communication_received', *identity(), fk('account_id','channel_accounts.id'),
        fk('lead_id','leads.id','SET NULL',True), s('provider_id',200), s('thread_id',200),
        s('classification',30), s('association',30), t('text'), i('sent_at'), i('received_at'),
        sa.UniqueConstraint('account_id','provider_id',name='uq_received_message'))
    indexes = {'channel_accounts':['user_id'], 'communication_oauth_states':['user_id'],
        'contact_verifications':['user_id','policy_id'], 'communication_outbox':['user_id','lead_id','account_id','status'],
        'communication_events':['user_id','outbox_id'], 'communication_received':['user_id','account_id']}
    for table, columns in indexes.items():
        for col in columns: op.create_index('ix_'+table+'_'+col,table,[col])


def downgrade():
    # Dropping uncertainty records could make an already accepted message look safe to resend.
    if op.get_bind().execute(sa.text("SELECT COUNT(*) FROM communication_outbox WHERE wire_started_at IS NOT NULL OR status IN ('queued','scheduled','executing','uncertain')")).scalar():
        raise RuntimeError('Preserve o ledger de comunicação. Downgrade recusado com envios pendentes ou tentados; restaure um backup anterior com o worker parado.')
    for table in ('communication_received','communication_events','communication_outbox','contact_verifications',
                  'communication_oauth_states','channel_accounts'):
        op.drop_table(table)
