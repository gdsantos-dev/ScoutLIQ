"""Add human triage and bounded, previewed commercial operations."""
from alembic import op
import sqlalchemy as sa
revision = '031'
down_revision = '030'
branch_labels = depends_on = None


def upgrade():
    op.create_table('commercial_reviews',
        sa.Column('lead_id', sa.String(36), sa.ForeignKey('leads.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('state', sa.String(24), nullable=False, server_default='unreviewed'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('author_id', sa.String(36)), sa.Column('decided_at', sa.Integer()),
        sa.Column('reason', sa.String(500), nullable=False, server_default=''),
        sa.Column('review_hash', sa.String(64), nullable=False, server_default=''),
        sa.Column('context_hash', sa.String(64), nullable=False, server_default=''),
        sa.Column('score_cache', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('classification', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('generation', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('dirty', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('refresh_at', sa.Integer(), nullable=False, server_default='0'))
    op.create_index('ix_commercial_reviews_user_id', 'commercial_reviews', ['user_id'])
    op.create_index('ix_review_queue', 'commercial_reviews', ['user_id', 'dirty', 'classification', 'score_cache'])
    op.create_table('commercial_operations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('request_key', sa.String(36), nullable=False), sa.Column('request_hash', sa.String(64), nullable=False),
        sa.Column('action', sa.String(24), nullable=False), sa.Column('status', sa.String(20), nullable=False),
        sa.Column('payload_json', sa.Text(), nullable=False), sa.Column('preview_json', sa.Text(), nullable=False),
        sa.Column('result_json', sa.Text(), nullable=False), sa.Column('created_at', sa.Integer(), nullable=False),
        sa.Column('committed_at', sa.Integer()),
        sa.UniqueConstraint('user_id', 'request_key', name='uq_commercial_operation'))
    op.create_index('ix_commercial_operations_user_id', 'commercial_operations', ['user_id'])


def downgrade():
    db = op.get_bind()
    if (db.execute(sa.text('SELECT COUNT(*) FROM commercial_operations')).scalar()
            or db.execute(sa.text('SELECT COUNT(*) FROM commercial_reviews WHERE decided_at IS NOT NULL')).scalar()):
        raise RuntimeError('Preserve as decisoes e operacoes comerciais antes de reverter a revisao 031.')
    op.drop_table('commercial_operations')
    op.drop_table('commercial_reviews')
