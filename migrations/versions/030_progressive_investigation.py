"""Add progressive state to the existing shared research queue."""
from alembic import op
import sqlalchemy as sa
revision = '030'
down_revision = '029'
branch_labels = depends_on = None

def upgrade():
    op.add_column('users', sa.Column('investigation_json', sa.Text(), nullable=False, server_default='{}'))
    op.add_column('research_batches', sa.Column('ordinal', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('research_batches', sa.Column('config_json', sa.Text(), nullable=False, server_default='{}'))
    op.add_column('research_batches', sa.Column('request_key', sa.String(80), nullable=True))
    op.create_index('uq_research_request', 'research_batches', ['user_id', 'request_key'], unique=True)
    for column in [sa.Column('phase', sa.String(20), nullable=False, server_default='local'),
                   sa.Column('plan_json', sa.Text(), nullable=False, server_default='{}'),
                   sa.Column('charged_at', sa.Integer(), nullable=False, server_default='0')]:
        op.add_column('research_batch_items', column)

def downgrade():
    if (op.get_bind().execute(sa.text("SELECT COUNT(*) FROM research_batches WHERE mode='progressive'")).scalar()
            or op.get_bind().execute(sa.text("SELECT COUNT(*) FROM users WHERE investigation_json!='{}'")).scalar()):
        raise RuntimeError('Preserve o histórico de investigação antes de reverter a migração 030.')
    for name in ['phase', 'plan_json', 'charged_at']:
        op.drop_column('research_batch_items', name)
    op.drop_index('uq_research_request', table_name='research_batches')
    for name in ['config_json', 'request_key', 'ordinal']:
        op.drop_column('research_batches', name)
    op.drop_column('users', 'investigation_json')
