"""Research & Automation 2.0 part 4: campaigns, attribution and outcome snapshots."""
from alembic import op
import sqlalchemy as sa

revision = '018'
down_revision = '017'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('leads') as batch:
        batch.add_column(sa.Column('outcome_snapshot_json', sa.Text(), nullable=False, server_default='{}'))
        batch.add_column(sa.Column('outcome_recorded_at', sa.Integer(), nullable=True))
    op.create_index('ix_leads_outcome_recorded_at', 'leads', ['outcome_recorded_at'])

    op.create_table(
        'campaigns',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(120), nullable=False),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('source_saved_search_id', sa.String(36), sa.ForeignKey('radar_saved_searches.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.Integer(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.UniqueConstraint('user_id', 'name', name='uq_campaign_user_name'),
    )
    op.create_index('ix_campaigns_user_id', 'campaigns', ['user_id'])
    op.create_index('ix_campaigns_status', 'campaigns', ['status'])
    op.create_index('ix_campaigns_source_saved_search_id', 'campaigns', ['source_saved_search_id'])
    op.create_index('ix_campaigns_created_at', 'campaigns', ['created_at'])

    op.create_table(
        'campaign_leads',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('campaign_id', sa.String(36), sa.ForeignKey('campaigns.id', ondelete='CASCADE'), nullable=False),
        sa.Column('lead_id', sa.String(36), sa.ForeignKey('leads.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source', sa.String(30), nullable=False, server_default='manual'),
        sa.Column('added_at', sa.Integer(), nullable=False),
        sa.UniqueConstraint('campaign_id', 'lead_id', name='uq_campaign_lead'),
    )
    op.create_index('ix_campaign_leads_user_id', 'campaign_leads', ['user_id'])
    op.create_index('ix_campaign_leads_campaign_id', 'campaign_leads', ['campaign_id'])
    op.create_index('ix_campaign_leads_lead_id', 'campaign_leads', ['lead_id'])
    op.create_index('ix_campaign_leads_added_at', 'campaign_leads', ['added_at'])

    with op.batch_alter_table('sales') as batch:
        batch.add_column(sa.Column('campaign_id', sa.String(36), sa.ForeignKey('campaigns.id', name='fk_sales_campaign_id_campaigns', ondelete='SET NULL'), nullable=True))
    op.create_index('ix_sales_campaign_id', 'sales', ['campaign_id'])


def downgrade():
    op.drop_index('ix_sales_campaign_id', table_name='sales')
    with op.batch_alter_table('sales') as batch:
        batch.drop_column('campaign_id')

    for name in ('ix_campaign_leads_added_at','ix_campaign_leads_lead_id','ix_campaign_leads_campaign_id','ix_campaign_leads_user_id'):
        op.drop_index(name, table_name='campaign_leads')
    op.drop_table('campaign_leads')

    for name in ('ix_campaigns_created_at','ix_campaigns_source_saved_search_id','ix_campaigns_status','ix_campaigns_user_id'):
        op.drop_index(name, table_name='campaigns')
    op.drop_table('campaigns')

    op.drop_index('ix_leads_outcome_recorded_at', table_name='leads')
    with op.batch_alter_table('leads') as batch:
        batch.drop_column('outcome_recorded_at')
        batch.drop_column('outcome_snapshot_json')
