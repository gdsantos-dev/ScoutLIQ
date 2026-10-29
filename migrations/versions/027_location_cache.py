"""Add bounded geographic cache; reservations reuse the existing consumption ledger."""
from alembic import op
import sqlalchemy as sa

revision = '027'
down_revision = '026'
branch_labels = depends_on = None


def upgrade():
    op.create_table('location_gate', sa.Column('id', sa.Integer(), primary_key=True),
                    sa.Column('version', sa.Integer(), nullable=False))
    op.execute(sa.text('INSERT INTO location_gate (id, version) VALUES (1, 0)'))
    op.create_table('location_cache', sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('expires_at', sa.Integer(), nullable=False), sa.Column('payload', sa.Text(), nullable=False))
    op.create_index('ix_location_cache_user_id', 'location_cache', ['user_id'])
    op.create_index('ix_location_cache_expires_at', 'location_cache', ['expires_at'])


def downgrade():
    # Keep cost reservations and all business data; only disposable cache is removed.
    op.drop_table('location_cache')
    op.drop_table('location_gate')
