"""Durable evidence and reviewed outreach, preserving existing CRM and research."""
from alembic import op
import sqlalchemy as sa

revision = '019'
down_revision = '018'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('leads', sa.Column('contact_blocked', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('leads', sa.Column('contact_block_reason', sa.String(500), nullable=False, server_default=''))
    shared = lambda: [
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('lead_id', sa.String(36), sa.ForeignKey('leads.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
    ]
    op.create_table('opportunity_evidence', *shared(),
        sa.Column('source_key', sa.String(100), nullable=False),
        sa.Column('statement', sa.String(600), nullable=False),
        sa.Column('source_url', sa.String(1000), nullable=False),
        sa.Column('method', sa.String(30), nullable=False),
        sa.Column('classification', sa.String(20), nullable=False),
        sa.Column('observed_at', sa.Integer(), nullable=False),
        sa.Column('valid_until', sa.Integer(), nullable=False),
        sa.UniqueConstraint('lead_id', 'source_key', name='uq_evidence_source'))
    op.create_table('outreach_drafts', *shared(),
        sa.Column('request_id', sa.String(36), nullable=False),
        sa.Column('channel', sa.String(20), nullable=False),
        sa.Column('locale', sa.String(10), nullable=False),
        sa.Column('recipient', sa.String(254), nullable=False),
        sa.Column('subject', sa.String(200), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('evidence_json', sa.Text(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('approval_hash', sa.String(64), nullable=False),
        sa.Column('authorization_ref', sa.String(500), nullable=False),
        sa.Column('authorized_until', sa.Integer(), nullable=True),
        sa.Column('approved_at', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.Integer(), nullable=False),
        sa.UniqueConstraint('user_id', 'request_id', name='uq_outreach_request'))
    for table in ('opportunity_evidence', 'outreach_drafts'):
        for field in ('user_id', 'lead_id'):
            op.create_index(f'ix_{table}_{field}', table, [field])


def downgrade():
    op.drop_table('outreach_drafts')
    op.drop_table('opportunity_evidence')
    with op.batch_alter_table('leads') as batch:
        batch.drop_column('contact_block_reason')
        batch.drop_column('contact_blocked')
