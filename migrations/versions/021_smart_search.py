"""Durable bounded search, additive qualification and previous score snapshot."""
from alembic import op
import sqlalchemy as sa
import json
from types import SimpleNamespace

revision = '021'
down_revision = '020'
branch_labels = depends_on = None

def upgrade():
    op.add_column('leads', sa.Column('qualification_json', sa.Text(), nullable=False, server_default='{}'))
    op.add_column('leads', sa.Column('previous_score_json', sa.Text(), nullable=False, server_default='{}'))
    op.create_table('smart_searches',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),
        sa.Column('request_key',sa.String(36),nullable=False), sa.Column('intent_json',sa.Text(),nullable=False),
        sa.Column('state_json',sa.Text(),nullable=False,server_default='{}'),
        sa.Column('batch_id',sa.String(36),sa.ForeignKey('research_batches.id',ondelete='SET NULL')),
        sa.Column('status',sa.String(20),nullable=False,server_default='pending'),
        sa.Column('attempts',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('retry_at',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('lease_until',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('lease_token',sa.String(36),nullable=False,server_default=''),
        sa.Column('error',sa.String(300),nullable=False,server_default=''),
        sa.Column('created_at',sa.Integer(),nullable=False), sa.Column('updated_at',sa.Integer(),nullable=False),
        sa.Column('deadline',sa.Integer(),nullable=False),
        sa.UniqueConstraint('user_id','request_key',name='uq_smart_request'))
    op.create_index('ix_smart_searches_user_id','smart_searches',['user_id'])
    op.create_index('ix_smart_searches_status','smart_searches',['status'])
    # Same data, old formula, frozen at upgrade; no account/stage/contact changes.
    from backend.scoring import _technical_score
    connection = op.get_bind()
    rows = connection.execute(sa.text('SELECT * FROM leads')).mappings().all()
    for row in rows:
        old = _technical_score(SimpleNamespace(**dict(row)))
        snapshot = json.dumps({'version':'2.5','value':old['value'],'dimensions':old['dimensions'],'basis':'migration-021'})
        connection.execute(sa.text('UPDATE leads SET previous_score_json=:snapshot WHERE id=:id'),{'snapshot':snapshot,'id':row['id']})

def downgrade():
    op.drop_table('smart_searches')
    # Native DROP COLUMN avoids rebuilding a parent table with cascading FKs.
    op.drop_column('leads','previous_score_json')
    op.drop_column('leads','qualification_json')
