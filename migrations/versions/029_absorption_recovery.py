"""Add versioned corrections and bounded recovery to existing absorption staging."""
from alembic import op
import sqlalchemy as sa
revision='029'
down_revision='028'
branch_labels=depends_on=None

def upgrade():
    for column in [sa.Column('version',sa.Integer(),nullable=False,server_default='1'),
                   sa.Column('ordinal',sa.Integer(),nullable=False,server_default='0'),
                   sa.Column('input_hash',sa.String(64),nullable=False,server_default='')]:
        op.add_column('absorption_batches',column)
    for name,default in [('original_json','{}'),('history_json','[]'),('issues_json','[]'),
                         ('matches_json','[]'),('review_json','{}'),('suggestions_json','[]')]:
        op.add_column('absorption_items',sa.Column(name,sa.Text(),nullable=False,server_default=default))
    op.add_column('absorption_items',sa.Column('version',sa.Integer(),nullable=False,server_default='1'))
    bind=op.get_bind()
    bind.execute(sa.text('UPDATE absorption_batches SET input_hash=payload_hash'))
    bind.execute(sa.text('UPDATE absorption_items SET original_json=payload_json'))
    counts={}
    for row in bind.execute(sa.text('SELECT id,user_id FROM absorption_batches ORDER BY created_at,id')).mappings().all():
        counts[row['user_id']]=counts.get(row['user_id'],0)+1
        bind.execute(sa.text('UPDATE absorption_batches SET ordinal=:ordinal WHERE id=:id'),dict(id=row['id'],ordinal=counts[row['user_id']]))
    op.create_table('absorption_recoveries',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),
        sa.Column('batch_id',sa.String(36),sa.ForeignKey('absorption_batches.id',ondelete='CASCADE'),nullable=False),
        sa.Column('request_key',sa.String(36),nullable=False),sa.Column('status',sa.String(20),nullable=False),
        sa.Column('state_json',sa.Text(),nullable=False),sa.Column('attempts',sa.Integer(),nullable=False),
        sa.Column('lease_token',sa.String(36),nullable=False),sa.Column('lease_until',sa.Integer(),nullable=False),
        sa.Column('retry_at',sa.Integer(),nullable=False),sa.Column('created_at',sa.Integer(),nullable=False),
        sa.Column('deadline',sa.Integer(),nullable=False),sa.Column('error',sa.String(240),nullable=False),
        sa.UniqueConstraint('user_id','request_key',name='uq_absorption_recovery_request'))
    for field in ['user_id','batch_id','status']:
        op.create_index('ix_absorption_recoveries_'+field,'absorption_recoveries',[field])

def downgrade():
    bind=op.get_bind()
    if bind.execute(sa.text('SELECT COUNT(*) FROM absorption_recoveries')).scalar() or bind.execute(sa.text("SELECT COUNT(*) FROM absorption_items WHERE version>1 OR history_json!='[]' OR original_json!=payload_json")).scalar():
        raise RuntimeError('Preserve correções e recuperações antes de reverter a migração 029.')
    op.drop_table('absorption_recoveries')
    # Native DROP COLUMN avoids rebuilding the parent table with FK cascades.
    for name in ['original_json','history_json','issues_json','matches_json','review_json','suggestions_json','version']:
        op.drop_column('absorption_items',name)
    for name in ['version','ordinal','input_hash']:
        op.drop_column('absorption_batches',name)
