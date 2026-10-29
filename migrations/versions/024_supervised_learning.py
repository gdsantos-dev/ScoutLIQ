"""Reviewed cases, immutable revisions and evaluation datasets. No Score changes."""
from alembic import op
import sqlalchemy as sa

revision = '024'
down_revision = '023'
branch_labels = depends_on = None


def upgrade():
    op.create_table('learning_gate', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('version', sa.Integer(), nullable=False))
    op.execute(sa.text('INSERT INTO learning_gate (id, version) VALUES (1, 0)'))
    def identity():
        return [sa.Column('id', sa.String(36), primary_key=True),
                sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)]
    def s(name, size): return sa.Column(name, sa.String(size), nullable=False)
    def t(name): return sa.Column(name, sa.Text(), nullable=False)
    def i(name): return sa.Column(name, sa.Integer(), nullable=False)
    op.create_table('learning_cases', *identity(),
        sa.Column('lead_id', sa.String(36), sa.ForeignKey('leads.id', ondelete='SET NULL'), nullable=True),
        s('source', 30), s('external_id', 100), s('identity_key', 64), s('dataset', 80), s('split', 20),
        t('record_json'), t('system_json'), s('record_hash', 64), i('version'), i('updated_at'),
        sa.UniqueConstraint('user_id', 'source', 'external_id', name='uq_learning_source'),
        sa.UniqueConstraint('user_id', 'identity_key', name='uq_learning_identity'))
    op.create_table('learning_revisions', *identity(),
        sa.Column('case_id', sa.String(36), sa.ForeignKey('learning_cases.id', ondelete='CASCADE'), nullable=False),
        i('version'), t('snapshot_json'), i('recorded_at'), sa.UniqueConstraint('case_id', 'version', name='uq_learning_revision'))
    op.create_table('learning_imports', *identity(), s('request_key', 36), s('input_hash', 64),
        t('preview_json'), t('receipt_json'), i('expires_at'), sa.Column('committed_at', sa.Integer(), nullable=True),
        sa.UniqueConstraint('user_id', 'request_key', name='uq_learning_import'))
    op.create_table('learning_evaluations', *identity(), s('request_key', 36), s('input_hash', 64), s('dataset', 80),
        t('snapshot_json'), t('report_json'), i('created_at'),
        sa.UniqueConstraint('user_id', 'request_key', name='uq_learning_evaluation'))
    for table in ('learning_cases', 'learning_revisions', 'learning_imports', 'learning_evaluations'):
        op.create_index('ix_' + table + '_user_id', table, ['user_id'])
    op.create_index('ix_learning_cases_lead_id', 'learning_cases', ['lead_id'])
    op.create_index('ix_learning_revisions_case_id', 'learning_revisions', ['case_id'])


def downgrade():
    for table in ('learning_evaluations', 'learning_imports', 'learning_revisions', 'learning_cases', 'learning_gate'):
        op.drop_table(table)
