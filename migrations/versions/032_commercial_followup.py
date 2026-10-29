"""Local, supervised follow-up preferences and disposable operational index."""
from alembic import op
import sqlalchemy as sa
revision = '032'
down_revision = '031'
branch_labels = depends_on = None


def upgrade():
    op.create_table('followup_settings',
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('interval_days', sa.Integer(), nullable=False, server_default='7'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'))
    op.create_table('followup_preferences',
        sa.Column('lead_id', sa.String(36), sa.ForeignKey('leads.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('disabled', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('snooze_until', sa.String(10), nullable=False, server_default=''),
        sa.Column('dismissed_key', sa.String(64), nullable=False, server_default=''),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'))
    op.create_index('ix_followup_preferences_user_id', 'followup_preferences', ['user_id'])
    with op.batch_alter_table('commercial_reviews') as batch:
        for name, typ, default in [('followup_json', sa.Text(), '{}'), ('followup_category', sa.String(24), 'pending'),
                ('followup_rank', sa.Integer(), '50'), ('followup_due', sa.String(10), ''),
                ('followup_confidence', sa.Integer(), '0'), ('followup_last', sa.Integer(), '0'),
                ('followup_dirty', sa.Integer(), '1'), ('followup_generation',sa.Integer(),'0'), ('followup_refresh_at', sa.Integer(), '0')]:
            batch.add_column(sa.Column(name, typ, nullable=False, server_default=default))
        batch.create_index('ix_followup_queue', ['user_id', 'followup_dirty', 'followup_rank', 'followup_due'])


def downgrade():
    db = op.get_bind()
    if (db.execute(sa.text('SELECT COUNT(*) FROM followup_preferences')).scalar()
            or db.execute(sa.text('SELECT COUNT(*) FROM followup_settings')).scalar()
            or db.execute(sa.text("SELECT COUNT(*) FROM commercial_operations WHERE action LIKE 'followup_%'")).scalar()):
        raise RuntimeError('Preserve preferencias e operacoes de acompanhamento antes de reverter 032.')
    with op.batch_alter_table('commercial_reviews') as batch:
        batch.drop_index('ix_followup_queue')
        for name in ('followup_json', 'followup_category', 'followup_rank', 'followup_due', 'followup_confidence', 'followup_last', 'followup_dirty', 'followup_generation', 'followup_refresh_at'):
            batch.drop_column(name)
    op.drop_table('followup_preferences')
    op.drop_table('followup_settings')
