"""Campos administrativos federados da ORLIQ."""
import time
from alembic import op
import sqlalchemy as sa

revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade():
    now = int(time.time())
    op.add_column('users', sa.Column('role', sa.String(20), nullable=False, server_default='user'))
    op.add_column('users', sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column('users', sa.Column('created_at', sa.Integer(), nullable=False, server_default=str(now)))
    op.add_column('users', sa.Column('last_login_at', sa.Integer(), nullable=True))
    op.create_index('ix_users_role', 'users', ['role'])
    op.create_index('ix_users_is_active', 'users', ['is_active'])
    op.create_index('ix_users_created_at', 'users', ['created_at'])
    primary_email = __import__('os').getenv('ADMIN_EMAIL', '').strip().casefold()
    if primary_email:
        op.execute(sa.text('UPDATE users SET role = :role WHERE lower(email) = :email').bindparams(role='admin', email=primary_email))


def downgrade():
    op.drop_index('ix_users_created_at', table_name='users')
    op.drop_index('ix_users_is_active', table_name='users')
    op.drop_index('ix_users_role', table_name='users')
    op.drop_column('users', 'last_login_at')
    op.drop_column('users', 'created_at')
    op.drop_column('users', 'is_active')
    op.drop_column('users', 'role')
