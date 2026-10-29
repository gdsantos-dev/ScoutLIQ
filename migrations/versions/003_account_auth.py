"""Public account registration, e-mail verification and recovery."""
import time
from alembic import op
import sqlalchemy as sa

revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('email_verified_at', sa.Integer(), nullable=True))
    op.execute(sa.text('UPDATE users SET email_verified_at = :verified').bindparams(verified=int(time.time())))
    op.create_table(
        'account_tokens',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('purpose', sa.String(40), nullable=False),
        sa.Column('token_hash', sa.String(64), nullable=False, unique=True),
        sa.Column('expires', sa.Integer(), nullable=False),
        sa.Column('used_at', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.Integer(), nullable=False),
    )
    op.create_index('ix_account_tokens_user_id', 'account_tokens', ['user_id'])
    op.create_index('ix_account_tokens_purpose', 'account_tokens', ['purpose'])
    op.create_index('ix_account_tokens_token_hash', 'account_tokens', ['token_hash'])
    op.create_index('ix_account_tokens_expires', 'account_tokens', ['expires'])


def downgrade():
    op.drop_table('account_tokens')
    op.drop_column('users', 'email_verified_at')
