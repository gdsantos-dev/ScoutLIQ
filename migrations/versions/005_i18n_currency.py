"""Internationalization preferences and per-record currencies."""
from alembic import op
import sqlalchemy as sa

revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('locale', sa.String(10), nullable=False, server_default='pt-BR'))
    op.add_column('users', sa.Column('default_currency', sa.String(3), nullable=False, server_default='BRL'))
    op.add_column('leads', sa.Column('potential_currency', sa.String(3), nullable=False, server_default='BRL'))
    op.add_column('sales', sa.Column('currency', sa.String(3), nullable=False, server_default='BRL'))
    op.add_column('payments', sa.Column('currency', sa.String(3), nullable=False, server_default='BRL'))
    op.add_column('expenses', sa.Column('currency', sa.String(3), nullable=False, server_default='BRL'))
    op.add_column('sites', sa.Column('currency', sa.String(3), nullable=False, server_default='BRL'))


def downgrade():
    op.drop_column('sites', 'currency')
    op.drop_column('expenses', 'currency')
    op.drop_column('payments', 'currency')
    op.drop_column('sales', 'currency')
    op.drop_column('leads', 'potential_currency')
    op.drop_column('users', 'default_currency')
    op.drop_column('users', 'locale')
