"""Client site management."""
from alembic import op
import sqlalchemy as sa

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None

def upgrade():
    columns = [sa.Column('id',sa.String(36),primary_key=True),
               sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),
               sa.Column('sale_id',sa.String(36),sa.ForeignKey('sales.id'),nullable=False)]
    for name, length in [('name',160),('url',500),('domain',253),('domain_owner',160),
                         ('hosting',160),('plan',160),('ssl_status',20),('analytics_url',500),
                         ('repository_url',500),('admin_url',500),('status',20)]:
        columns.append(sa.Column(name,sa.String(length),nullable=False))
    for name in ['renewal_on','ssl_expires_on']:
        columns.append(sa.Column(name,sa.String(10),nullable=True))
    for name in ['maintenance','notes']:
        columns.append(sa.Column(name,sa.Text(),nullable=False))
    for name in ['monthly_revenue_cents','monthly_cost_cents','annual_domain_cost_cents','version']:
        columns.append(sa.Column(name,sa.Integer(),nullable=False))
    columns.append(sa.Column('demo',sa.Boolean(),nullable=False))
    op.create_table('sites',*columns)
    op.create_index('ix_sites_user_id','sites',['user_id'])

def downgrade():
    op.drop_table('sites')
