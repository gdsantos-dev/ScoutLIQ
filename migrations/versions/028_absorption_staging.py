"""Add staging for external research absorption, no mutation of historical leads."""
from alembic import op
import sqlalchemy as sa

revision = '028'
down_revision = '027'
branch_labels = depends_on = None

def upgrade():
    op.create_table('absorption_batches',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('request_key', sa.String(36), nullable=False),
        sa.Column('source', sa.String(20), nullable=False),
        sa.Column('payload_hash', sa.String(64), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.Column('committed_at', sa.Integer(), nullable=True),
        sa.UniqueConstraint('user_id', 'request_key', name='uq_absorption_request'))
    op.create_index('ix_absorption_batches_user_id', 'absorption_batches', ['user_id'])
    op.create_table('absorption_items',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('batch_id', sa.String(36), sa.ForeignKey('absorption_batches.id', ondelete='CASCADE'), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('payload_json', sa.Text(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('reason', sa.String(240), nullable=False),
        sa.Column('lead_id', sa.String(36), sa.ForeignKey('leads.id', ondelete='SET NULL'), nullable=True),
        sa.UniqueConstraint('batch_id', 'position', name='uq_absorption_position'))
    op.create_index('ix_absorption_items_user_id', 'absorption_items', ['user_id'])
    op.create_index('ix_absorption_items_batch_id', 'absorption_items', ['batch_id'])

def downgrade():
    # Staged external leads are auditable data. Downgrade cannot silently erase them.
    count = op.get_bind().execute(sa.text('SELECT COUNT(*) FROM absorption_batches')).scalar()
    if count:
        raise RuntimeError('Existem lotes de absorção. Exporte e preserve o histórico antes do downgrade.')
    op.drop_table('absorption_items')
    op.drop_table('absorption_batches')
