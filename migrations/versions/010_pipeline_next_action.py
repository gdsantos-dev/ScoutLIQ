"""Persist the next commercial action on pipeline opportunities."""
from alembic import op
import sqlalchemy as sa

revision = '010'
down_revision = '009'
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table('leads') as batch:
        batch.add_column(sa.Column('next_action', sa.String(180), nullable=False, server_default=''))
        batch.add_column(sa.Column('next_action_on', sa.String(10), nullable=True))
    op.create_index('ix_leads_next_action_on', 'leads', ['next_action_on'])

def downgrade():
    op.drop_index('ix_leads_next_action_on', table_name='leads')
    with op.batch_alter_table('leads') as batch:
        batch.drop_column('next_action_on')
        batch.drop_column('next_action')
