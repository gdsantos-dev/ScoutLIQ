"""Initial schema. Frozen table definitions for reproducible deployments."""
from alembic import op
import sqlalchemy as sa

revision = '001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('users', sa.Column('id',sa.String(36),primary_key=True),sa.Column('email',sa.String(254),nullable=False,unique=True),sa.Column('password_hash',sa.Text(),nullable=False),sa.Column('name',sa.String(80),nullable=False),sa.Column('accent',sa.String(20),nullable=False),sa.Column('motion',sa.String(20),nullable=False),sa.Column('timezone',sa.String(64),nullable=False))
    op.create_table('sessions',sa.Column('token_hash',sa.String(64),primary_key=True),sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),sa.Column('csrf',sa.String(64),nullable=False),sa.Column('expires',sa.Integer(),nullable=False))
    op.create_table('leads',sa.Column('id',sa.String(36),primary_key=True),sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),*[sa.Column(n,sa.String(size),nullable=False) for n,size in [('name',160),('category',80),('city',100),('country',2),('address',250),('website',500),('website_status',20),('instagram',500),('phone',30),('whatsapp',20),('contact',100),('stage',20),('source',50)]],sa.Column('latitude',sa.Float(),nullable=False),sa.Column('longitude',sa.Float(),nullable=False),sa.Column('rating',sa.Float()),sa.Column('reviews',sa.Integer()),sa.Column('instagram_active',sa.Boolean(),nullable=False),sa.Column('in_pipeline',sa.Boolean(),nullable=False),sa.Column('potential_cents',sa.Integer(),nullable=False),sa.Column('notes',sa.Text(),nullable=False),sa.Column('source_id',sa.String(160)),sa.Column('demo',sa.Boolean(),nullable=False),sa.Column('version',sa.Integer(),nullable=False),sa.Column('created_at',sa.Integer(),nullable=False))
    op.create_index('ix_leads_user_id','leads',['user_id'])
    op.create_index('ix_leads_stage','leads',['stage'])
    op.create_table('sales',sa.Column('id',sa.String(36),primary_key=True),sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),sa.Column('lead_id',sa.String(36),sa.ForeignKey('leads.id'),nullable=False,unique=True),sa.Column('service',sa.String(160),nullable=False),sa.Column('amount_cents',sa.Integer(),nullable=False),sa.Column('recurring_cents',sa.Integer(),nullable=False),sa.Column('project_status',sa.String(20),nullable=False),sa.Column('sold_on',sa.String(10),nullable=False),sa.Column('due_on',sa.String(10),nullable=False),sa.Column('demo',sa.Boolean(),nullable=False),sa.Column('export_id',sa.String(36),nullable=False,unique=True))
    op.create_index('ix_sales_user_id','sales',['user_id'])
    op.create_index('ix_sales_sold_on','sales',['sold_on'])
    op.create_table('payments',sa.Column('id',sa.String(36),primary_key=True),sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),sa.Column('sale_id',sa.String(36),sa.ForeignKey('sales.id'),nullable=False),sa.Column('amount_cents',sa.Integer(),nullable=False),sa.Column('paid_on',sa.String(10),nullable=False),sa.Column('export_id',sa.String(36),nullable=False,unique=True),sa.Column('request_id',sa.String(36),nullable=False,unique=True))
    op.create_index('ix_payments_user_id','payments',['user_id'])
    op.create_table('expenses',sa.Column('id',sa.String(36),primary_key=True),sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),sa.Column('description',sa.String(160),nullable=False),sa.Column('amount_cents',sa.Integer(),nullable=False),sa.Column('incurred_on',sa.String(10),nullable=False),sa.Column('demo',sa.Boolean(),nullable=False),sa.Column('export_id',sa.String(36),nullable=False,unique=True),sa.Column('request_id',sa.String(36),nullable=False,unique=True))
    op.create_index('ix_expenses_user_id','expenses',['user_id'])

def downgrade():
    for name in ['expenses','payments','sales','leads','sessions','users']:
        op.drop_table(name)
