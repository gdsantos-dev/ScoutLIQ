"""Research & Automation 2.0 part 2: watchlist state."""
from alembic import op
import sqlalchemy as sa

revision = '016'
down_revision = '015'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('leads') as batch:
        batch.add_column(sa.Column('watchlisted', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column('watch_started_at', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('watch_last_checked_at', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('watch_last_event_at', sa.Integer(), nullable=True))
    op.create_index('ix_leads_watchlisted', 'leads', ['watchlisted'])
    op.create_index('ix_leads_watch_last_checked_at', 'leads', ['watch_last_checked_at'])
    op.create_index('ix_leads_watch_last_event_at', 'leads', ['watch_last_event_at'])


def downgrade():
    op.drop_index('ix_leads_watch_last_event_at', table_name='leads')
    op.drop_index('ix_leads_watch_last_checked_at', table_name='leads')
    op.drop_index('ix_leads_watchlisted', table_name='leads')
    with op.batch_alter_table('leads') as batch:
        batch.drop_column('watch_last_event_at')
        batch.drop_column('watch_last_checked_at')
        batch.drop_column('watch_started_at')
        batch.drop_column('watchlisted')
