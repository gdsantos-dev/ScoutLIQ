"""Evidence context, exact-recipient policies and recoverable existing queues."""
from alembic import op
import sqlalchemy as sa

revision = '020'
down_revision = '019'
branch_labels = depends_on = None

EVIDENCE = {
    'category': (sa.String(30), 'general'), 'scope': (sa.String(500), ''),
    'research_id': (sa.String(36), None), 'verified_at': (sa.Integer(), None),
    'review_reason': (sa.String(500), ''), 'observation_key': (sa.String(40), ''),
    'observation_state': (sa.String(20), ''), 'analyzer_version': (sa.String(30), 'legacy-v1'),
    'relation': (sa.String(20), 'current'), 'related_id': (sa.String(36), None),
    'translations_json': (sa.Text(), '{}'),
}
TASK = {'attempts': (sa.Integer(), '0'), 'retry_at': (sa.Integer(), '0'),
        'lease_until': (sa.Integer(), '0'), 'lease_token': (sa.String(36), '')}

def upgrade():
    for name, (kind, default) in EVIDENCE.items():
        op.add_column('opportunity_evidence', sa.Column(name, kind, nullable=default is None, server_default=default))
    op.add_column('outreach_drafts', sa.Column('strategy', sa.String(30), nullable=False, server_default='verified_opportunity'))
    op.add_column('outreach_drafts', sa.Column('generation_method', sa.String(30), nullable=False, server_default='legacy-v1'))
    for table in ('research_batch_items', 'radar_saved_searches'):
        for name, (kind, default) in TASK.items():
            op.add_column(table, sa.Column(name, kind, nullable=False, server_default=default))
    op.add_column('radar_saved_searches', sa.Column('worker_error', sa.String(300), nullable=False, server_default=''))
    op.create_table('recipient_policies',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('channel', sa.String(20), nullable=False), sa.Column('recipient', sa.String(254), nullable=False),
        sa.Column('blocked', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('basis', sa.String(30), nullable=False), sa.Column('reference', sa.String(1000), nullable=False),
        sa.Column('reason', sa.String(500), nullable=False), sa.Column('market', sa.String(2), nullable=False),
        sa.Column('recorded_at', sa.Integer(), nullable=False), sa.Column('valid_until', sa.Integer()),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.UniqueConstraint('user_id', 'channel', 'recipient', name='uq_recipient_policy'))
    op.create_index('ix_recipient_policies_user_id', 'recipient_policies', ['user_id'])
    op.create_table('research_executor', sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('token', sa.String(36), nullable=False), sa.Column('lease_until', sa.Integer(), nullable=False),
        sa.Column('next_at', sa.Integer(), nullable=False), sa.Column('day', sa.Integer(), nullable=False),
        sa.Column('used', sa.Integer(), nullable=False))
    op.execute(sa.text("INSERT INTO research_executor (id,token,lease_until,next_at,day,used) VALUES (1,'',0,0,0,0)"))

def downgrade():
    op.drop_table('research_executor')
    op.drop_table('recipient_policies')
    for table in ('research_batch_items', 'radar_saved_searches'):
        with op.batch_alter_table(table) as batch:
            for name in TASK: batch.drop_column(name)
            if table == 'radar_saved_searches': batch.drop_column('worker_error')
    with op.batch_alter_table('outreach_drafts') as batch:
        batch.drop_column('strategy')
        batch.drop_column('generation_method')
    with op.batch_alter_table('opportunity_evidence') as batch:
        for name in EVIDENCE: batch.drop_column(name)
