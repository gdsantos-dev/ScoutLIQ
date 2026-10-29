"""Converge both historical v1.5 audit schemas into the deep-audit schema.

Compatibility note:
This file intentionally keeps its historical filename so patch-only installs
that already contain ``007_deep_site_audit.py`` overwrite the duplicate
revision instead of leaving two Alembic revision 007 files on disk.
"""
from alembic import op
import sqlalchemy as sa

revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def _columns() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column['name'] for column in inspector.get_columns('lead_research')}


def upgrade():
    columns = _columns()

    # The newer deep-audit schema uses audit_level. Add it when upgrading from
    # the earlier v1.5 audit schema, but leave databases that already received
    # the newer 007 migration untouched.
    if 'audit_level' not in columns:
        with op.batch_alter_table('lead_research') as batch:
            batch.add_column(sa.Column('audit_level', sa.String(20), nullable=False, server_default='none'))

        # Preserve useful prior audit state when the earlier schema was used.
        columns = _columns()
        if 'audit_status' in columns:
            op.execute(sa.text(
                "UPDATE lead_research SET audit_level = 'deep' "
                "WHERE audit_status = 'completed'"
            ))

    # audit_json/audited_at are shared by both historical schemas. Add them
    # only if a partially-applied/manual database is missing either column.
    columns = _columns()
    with op.batch_alter_table('lead_research') as batch:
        if 'audit_json' not in columns:
            batch.add_column(sa.Column('audit_json', sa.Text(), nullable=False, server_default='{}'))
        if 'audited_at' not in columns:
            batch.add_column(sa.Column('audited_at', sa.Integer(), nullable=True))

    # The first v1.5 implementation had audit_status/audit_score. They are no
    # longer part of the application model, so remove them after state is
    # converted. batch_alter_table keeps this portable for SQLite/Postgres.
    columns = _columns()
    with op.batch_alter_table('lead_research') as batch:
        if 'audit_status' in columns:
            batch.drop_column('audit_status')
        if 'audit_score' in columns:
            batch.drop_column('audit_score')

    # Ensure the timestamp index exists. Inspect first to make this migration
    # safe for databases that previously received the newer 007 migration.
    inspector = sa.inspect(op.get_bind())
    indexes = {index['name'] for index in inspector.get_indexes('lead_research')}
    if 'ix_lead_research_audited_at' not in indexes:
        op.create_index('ix_lead_research_audited_at', 'lead_research', ['audited_at'])


def downgrade():
    # Downgrade to the earlier v1.5 schema represented by revision 007.
    columns = _columns()
    with op.batch_alter_table('lead_research') as batch:
        if 'audit_status' not in columns:
            batch.add_column(sa.Column('audit_status', sa.String(20), nullable=False, server_default='not_run'))
        if 'audit_score' not in columns:
            batch.add_column(sa.Column('audit_score', sa.Integer(), nullable=False, server_default='0'))

    columns = _columns()
    if 'audit_level' in columns:
        op.execute(sa.text(
            "UPDATE lead_research SET audit_status = 'completed' "
            "WHERE audit_level = 'deep'"
        ))
        with op.batch_alter_table('lead_research') as batch:
            batch.drop_column('audit_level')
