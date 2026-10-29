"""Add persisted website intelligence used by Score Engine 2.0."""
from alembic import op
import sqlalchemy as sa

revision = '012'
down_revision = '011'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('leads') as batch:
        batch.add_column(sa.Column('website_intelligence_json', sa.Text(), nullable=False, server_default='{}'))
        batch.add_column(sa.Column('website_analyzed_at', sa.Integer(), nullable=True))
    op.create_index('ix_leads_website_analyzed_at', 'leads', ['website_analyzed_at'])


def downgrade():
    op.drop_index('ix_leads_website_analyzed_at', table_name='leads')
    with op.batch_alter_table('leads') as batch:
        batch.drop_column('website_analyzed_at')
        batch.drop_column('website_intelligence_json')
