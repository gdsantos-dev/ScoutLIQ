"""Explicitly approved and reversible Score 3.0 configuration; defaults remain identical."""
from alembic import op
import sqlalchemy as sa
revision = '025'
down_revision = '024'
branch_labels = depends_on = None


def upgrade():
    op.add_column('leads', sa.Column('score_criteria_json', sa.Text(), nullable=False, server_default='{}'))
    def user(): return sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    def s(name, n): return sa.Column(name, sa.String(n), nullable=False)
    def t(name): return sa.Column(name, sa.Text(), nullable=False)
    def i(name): return sa.Column(name, sa.Integer(), nullable=False)
    op.create_table('score_configurations', sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True), t('config_json'), i('version'))
    op.create_table('calibration_proposals', sa.Column('id', sa.String(36), primary_key=True), user(), s('request_key',36), s('input_hash',64),
        t('report_json'), i('base_version'), i('created_at'), sa.UniqueConstraint('user_id','request_key',name='uq_calibration_request'))
    op.create_table('calibration_changes', sa.Column('id',sa.String(36),primary_key=True), user(),
        sa.Column('proposal_id',sa.String(36),sa.ForeignKey('calibration_proposals.id',ondelete='SET NULL'),nullable=True),
        sa.Column('reverted_change_id',sa.String(36),nullable=True),t('previous_json'),t('applied_json'),i('config_version'),s('reason',1000),i('created_at'))
    for table in ('calibration_proposals','calibration_changes'):
        op.create_index('ix_'+table+'_user_id',table,['user_id'])


def downgrade():
    # Rollback to baseline explicitly before dropping configuration; no data/score reconstruction here.
    active = op.get_bind().execute(sa.text("SELECT COUNT(*) FROM score_configurations WHERE config_json != '{}'")).scalar()
    if active: raise RuntimeError('Reverta as calibrações para a configuração padrão antes do downgrade 025.')
    op.drop_table('calibration_changes')
    op.drop_table('calibration_proposals')
    op.drop_table('score_configurations')
    # Native DROP COLUMN avoids recreating Lead and triggering cascading deletes.
    op.drop_column('leads', 'score_criteria_json')
