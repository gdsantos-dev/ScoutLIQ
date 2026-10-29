"""Persist autonomous territory research batches."""
from alembic import op
import sqlalchemy as sa

revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'research_batches',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('mode', sa.String(20), nullable=False, server_default='deep'),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('requested_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('skipped_recent', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.Integer(), nullable=False),
        sa.Column('completed_at', sa.Integer(), nullable=True),
    )
    op.create_index('ix_research_batches_user_id', 'research_batches', ['user_id'])
    op.create_index('ix_research_batches_status', 'research_batches', ['status'])
    op.create_index('ix_research_batches_created_at', 'research_batches', ['created_at'])

    op.create_table(
        'research_batch_items',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('batch_id', sa.String(36), sa.ForeignKey('research_batches.id', ondelete='CASCADE'), nullable=False),
        sa.Column('lead_id', sa.String(36), sa.ForeignKey('leads.id', ondelete='CASCADE'), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('outcome', sa.String(40), nullable=False, server_default=''),
        sa.Column('error', sa.String(300), nullable=False, server_default=''),
        sa.Column('started_at', sa.Integer(), nullable=True),
        sa.Column('finished_at', sa.Integer(), nullable=True),
        sa.UniqueConstraint('batch_id', 'lead_id', name='uq_research_batch_item'),
    )
    op.create_index('ix_research_batch_items_batch_id', 'research_batch_items', ['batch_id'])
    op.create_index('ix_research_batch_items_lead_id', 'research_batch_items', ['lead_id'])
    op.create_index('ix_research_batch_items_status', 'research_batch_items', ['status'])


def downgrade():
    op.drop_index('ix_research_batch_items_status', table_name='research_batch_items')
    op.drop_index('ix_research_batch_items_lead_id', table_name='research_batch_items')
    op.drop_index('ix_research_batch_items_batch_id', table_name='research_batch_items')
    op.drop_table('research_batch_items')
    op.drop_index('ix_research_batches_created_at', table_name='research_batches')
    op.drop_index('ix_research_batches_status', table_name='research_batches')
    op.drop_index('ix_research_batches_user_id', table_name='research_batches')
    op.drop_table('research_batches')
