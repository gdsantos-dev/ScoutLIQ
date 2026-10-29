"""Add bounded prospecting plans over canonical routines (032 -> 033)."""
from alembic import op
import sqlalchemy as sa
revision = '033'
down_revision = '032'
branch_labels = depends_on = None


def upgrade():
    op.create_table('prospecting_plans',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('config_json', sa.Text(), nullable=False),
        sa.Column('state', sa.String(20), nullable=False, server_default='disabled'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('timezone', sa.String(64), nullable=False),
        sa.Column('authorization', sa.String(64), nullable=False, server_default=''),
        sa.Column('next_check_at', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('reason', sa.String(300), nullable=False, server_default='Plano desativado.'),
        sa.Column('created_at', sa.Integer(), nullable=False))
    op.create_index('ix_prospecting_plans_next_check_at', 'prospecting_plans', ['next_check_at'])
    op.create_table('prospecting_plan_members',
        sa.Column('plan_id', sa.String(36), sa.ForeignKey('prospecting_plans.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('saved_search_id', sa.String(36), sa.ForeignKey('radar_saved_searches.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='1'))
    op.create_table('prospecting_plan_decisions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('plan_id', sa.String(36), sa.ForeignKey('prospecting_plans.id', ondelete='CASCADE'), nullable=False),
        sa.Column('key', sa.String(100), nullable=False),
        sa.Column('at', sa.Integer(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(30), nullable=False),
        sa.Column('reason', sa.String(300), nullable=False),
        sa.Column('details_json', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('run_id', sa.String(36), sa.ForeignKey('routine_runs.id', ondelete='SET NULL'), nullable=True, unique=True),
        sa.UniqueConstraint('plan_id', 'key', name='uq_plan_decision_key'))
    for name in ('plan_id', 'at'):
        op.create_index('ix_prospecting_plan_decisions_'+name, 'prospecting_plan_decisions', [name])
    op.create_table('prospecting_plan_incorporations',
        sa.Column('lead_id', sa.String(36), sa.ForeignKey('leads.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('decision_id', sa.String(36), sa.ForeignKey('prospecting_plan_decisions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('search_id', sa.String(36), sa.ForeignKey('smart_searches.id', ondelete='SET NULL'), nullable=True),
        sa.Column('discarded', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('at', sa.Integer(), nullable=False))
    for name in ('decision_id', 'at'):
        op.create_index('ix_prospecting_plan_incorporations_'+name, 'prospecting_plan_incorporations', [name])
    op.create_index('ix_leads_owner_created', 'leads', ['user_id', 'created_at'])


def downgrade():
    if op.get_bind().execute(sa.text('SELECT id FROM prospecting_plans LIMIT 1')).first():
        raise RuntimeError('A revisão 033 contém planejamento humano. Preserve o banco e restaure um backup compatível; downgrade destrutivo recusado.')
    op.drop_index('ix_leads_owner_created', table_name='leads')
    for table in ('prospecting_plan_incorporations', 'prospecting_plan_decisions', 'prospecting_plan_members', 'prospecting_plans'):
        op.drop_table(table)
