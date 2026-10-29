"""Optional semantic preview reservations; no changes to P0.1 or score weights."""
from alembic import op
import sqlalchemy as sa
revision = '023'
down_revision = '022'
branch_labels = depends_on = None


def upgrade():
    op.create_table('semantic_gate', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('version', sa.Integer(), nullable=False))
    op.execute(sa.text('INSERT INTO semantic_gate (id, version) VALUES (1, 0)'))
    op.create_table('semantic_attempts',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('request_key', sa.String(36), nullable=False),
        sa.Column('input_hash', sa.String(64), nullable=False),
        sa.Column('model', sa.String(120), nullable=False),
        sa.Column('started_at', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(30), nullable=False),
        sa.Column('reserved_tokens', sa.Integer(), nullable=False),
        sa.Column('actual_tokens', sa.Integer()),
        sa.UniqueConstraint('user_id', 'request_key', name='uq_semantic_request'))
    for column in ('user_id', 'started_at'): op.create_index('ix_semantic_attempts_' + column, 'semantic_attempts', [column])


def downgrade():
    op.drop_table('semantic_attempts')
    op.drop_table('semantic_gate')
