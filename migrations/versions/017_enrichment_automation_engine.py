"""Research & Automation 2.0 part 3: enrichment provenance and automation engine."""
from alembic import op
import sqlalchemy as sa

revision = '017'
down_revision = '016'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('leads') as batch:
        batch.add_column(sa.Column('enrichment_json', sa.Text(), nullable=False, server_default='{}'))
        batch.add_column(sa.Column('enrichment_analyzed_at', sa.Integer(), nullable=True))
    op.create_index('ix_leads_enrichment_analyzed_at', 'leads', ['enrichment_analyzed_at'])

    op.create_table(
        'automation_rules',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('trigger', sa.String(30), nullable=False),
        sa.Column('conditions_json', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('actions_json', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('stop_json', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('last_run_at', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.Integer(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
    )
    op.create_index('ix_automation_rules_user_id', 'automation_rules', ['user_id'])
    op.create_index('ix_automation_rules_enabled', 'automation_rules', ['enabled'])
    op.create_index('ix_automation_rules_trigger', 'automation_rules', ['trigger'])
    op.create_index('ix_automation_rules_last_run_at', 'automation_rules', ['last_run_at'])
    op.create_index('ix_automation_rules_created_at', 'automation_rules', ['created_at'])

    op.create_table(
        'automation_runs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('rule_id', sa.String(36), sa.ForeignKey('automation_rules.id', ondelete='CASCADE'), nullable=False),
        sa.Column('lead_id', sa.String(36), sa.ForeignKey('leads.id', ondelete='CASCADE'), nullable=False),
        sa.Column('trigger', sa.String(30), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('reason', sa.String(160), nullable=False, server_default=''),
        sa.Column('actions_json', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('created_at', sa.Integer(), nullable=False),
    )
    op.create_index('ix_automation_runs_user_id', 'automation_runs', ['user_id'])
    op.create_index('ix_automation_runs_rule_id', 'automation_runs', ['rule_id'])
    op.create_index('ix_automation_runs_lead_id', 'automation_runs', ['lead_id'])
    op.create_index('ix_automation_runs_trigger', 'automation_runs', ['trigger'])
    op.create_index('ix_automation_runs_status', 'automation_runs', ['status'])
    op.create_index('ix_automation_runs_created_at', 'automation_runs', ['created_at'])


def downgrade():
    for name in (
        'ix_automation_runs_created_at','ix_automation_runs_status','ix_automation_runs_trigger',
        'ix_automation_runs_lead_id','ix_automation_runs_rule_id','ix_automation_runs_user_id',
    ):
        op.drop_index(name, table_name='automation_runs')
    op.drop_table('automation_runs')
    for name in (
        'ix_automation_rules_created_at','ix_automation_rules_last_run_at','ix_automation_rules_trigger',
        'ix_automation_rules_enabled','ix_automation_rules_user_id',
    ):
        op.drop_index(name, table_name='automation_rules')
    op.drop_table('automation_rules')
    op.drop_index('ix_leads_enrichment_analyzed_at', table_name='leads')
    with op.batch_alter_table('leads') as batch:
        batch.drop_column('enrichment_analyzed_at')
        batch.drop_column('enrichment_json')
