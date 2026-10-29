"""Explicit recurring goals, consumption ledger and process health."""
from alembic import op
import sqlalchemy as sa

revision = '022'
down_revision = '021'
branch_labels = depends_on = None


def upgrade():
    for column in (
        sa.Column('routine_config_json', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('routine_state', sa.String(20), nullable=False, server_default='disabled'),
        sa.Column('routine_next_at', sa.Integer(), nullable=True),
        sa.Column('routine_last_at', sa.Integer(), nullable=True),
        sa.Column('routine_seen_json', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('routine_reason', sa.String(300), nullable=False, server_default=''),
    ): op.add_column('radar_saved_searches', column)
    op.create_index('ix_radar_saved_searches_routine_state', 'radar_saved_searches', ['routine_state'])
    op.create_table('routine_runs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('saved_search_id', sa.String(36), sa.ForeignKey('radar_saved_searches.id', ondelete='CASCADE'), nullable=False),
        sa.Column('scheduled_at', sa.Integer(), nullable=False), sa.Column('started_at', sa.Integer(), nullable=False),
        sa.Column('finished_at', sa.Integer()),
        sa.Column('search_id', sa.String(36), sa.ForeignKey('smart_searches.id', ondelete='SET NULL')),
        sa.Column('batch_id', sa.String(36), sa.ForeignKey('research_batches.id', ondelete='SET NULL')),
        sa.Column('config_json', sa.Text(), nullable=False), sa.Column('result_json', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('status', sa.String(20), nullable=False, server_default='running'),
        sa.Column('reason', sa.String(300), nullable=False, server_default=''),
        sa.UniqueConstraint('saved_search_id', 'scheduled_at', name='uq_routine_slot'))
    op.create_table('routine_events',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('saved_search_id', sa.String(36), sa.ForeignKey('radar_saved_searches.id', ondelete='CASCADE'), nullable=False),
        sa.Column('action', sa.String(30), nullable=False), sa.Column('detail_json', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.Integer(), nullable=False))
    op.create_table('work_attempts',
        sa.Column('token', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('run_id', sa.String(36), sa.ForeignKey('routine_runs.id', ondelete='SET NULL')),
        sa.Column('kind', sa.String(20), nullable=False), sa.Column('item_id', sa.String(36), nullable=False),
        sa.Column('started_at', sa.Integer(), nullable=False), sa.Column('finished_at', sa.Integer()),
        sa.Column('status', sa.String(20), nullable=False, server_default='claimed'))
    op.create_table('provider_operations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('token', sa.String(36), sa.ForeignKey('work_attempts.token', ondelete='CASCADE'), nullable=False),
        sa.Column('provider', sa.String(30), nullable=False), sa.Column('started_at', sa.Integer(), nullable=False),
        sa.Column('finished_at', sa.Integer()), sa.Column('status', sa.String(20), nullable=False, server_default='reserved'))
    op.create_table('worker_heartbeats',
        sa.Column('id', sa.String(36), primary_key=True), sa.Column('started_at', sa.Integer(), nullable=False),
        sa.Column('heartbeat_at', sa.Integer(), nullable=False), sa.Column('state', sa.String(20), nullable=False),
        sa.Column('task_deadline', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error', sa.String(160), nullable=False, server_default=''))
    for table, columns in {'routine_runs':['user_id','saved_search_id','status'], 'routine_events':['user_id','saved_search_id'],
                           'work_attempts':['user_id','run_id','started_at'], 'provider_operations':['token','provider','started_at']}.items():
        for column in columns: op.create_index(f'ix_{table}_{column}', table, [column])


def downgrade():
    for table in ('provider_operations','work_attempts','routine_events','routine_runs','worker_heartbeats'): op.drop_table(table)
    op.drop_index('ix_radar_saved_searches_routine_state', table_name='radar_saved_searches')
    for name in ('routine_config_json','routine_state','routine_next_at','routine_last_at','routine_seen_json','routine_reason'):
        op.drop_column('radar_saved_searches', name)
