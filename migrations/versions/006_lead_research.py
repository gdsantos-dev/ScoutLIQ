"""Persist evidence-based lead web research."""
from alembic import op
import sqlalchemy as sa

revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'lead_research',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('lead_id', sa.String(36), sa.ForeignKey('leads.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='unverified'),
        sa.Column('provider', sa.String(50), nullable=False, server_default='direct'),
        sa.Column('website_url', sa.String(500), nullable=False, server_default=''),
        sa.Column('website_status', sa.String(20), nullable=False, server_default='unknown'),
        sa.Column('confidence', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('evidence_json', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('checks_json', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('sources_json', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('page_json', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('search_configured', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('candidates_checked', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('fetch_errors', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('checked_at', sa.Integer(), nullable=False),
        sa.UniqueConstraint('lead_id', name='uq_lead_research_lead_id'),
    )
    op.create_index('ix_lead_research_user_id', 'lead_research', ['user_id'])
    op.create_index('ix_lead_research_lead_id', 'lead_research', ['lead_id'], unique=True)
    op.create_index('ix_lead_research_checked_at', 'lead_research', ['checked_at'])


def downgrade():
    op.drop_index('ix_lead_research_checked_at', table_name='lead_research')
    op.drop_index('ix_lead_research_lead_id', table_name='lead_research')
    op.drop_index('ix_lead_research_user_id', table_name='lead_research')
    op.drop_table('lead_research')
