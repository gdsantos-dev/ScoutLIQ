"""Persist deep website audit results for lead research."""
from alembic import op
import sqlalchemy as sa

revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('lead_research') as batch:
        batch.add_column(sa.Column('audit_status', sa.String(20), nullable=False, server_default='not_run'))
        batch.add_column(sa.Column('audit_score', sa.Integer(), nullable=False, server_default='0'))
        batch.add_column(sa.Column('audit_json', sa.Text(), nullable=False, server_default='{}'))
        batch.add_column(sa.Column('audited_at', sa.Integer(), nullable=True))
    op.create_index('ix_lead_research_audited_at', 'lead_research', ['audited_at'])


def downgrade():
    op.drop_index('ix_lead_research_audited_at', table_name='lead_research')
    with op.batch_alter_table('lead_research') as batch:
        batch.drop_column('audited_at')
        batch.drop_column('audit_json')
        batch.drop_column('audit_score')
        batch.drop_column('audit_status')
