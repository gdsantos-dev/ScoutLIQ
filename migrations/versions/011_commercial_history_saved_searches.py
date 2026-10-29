"""Add commercial history, smart-list timestamps, and saved Radar searches."""
from alembic import op
import sqlalchemy as sa

revision = '011'
down_revision = '010'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('leads') as batch:
        batch.add_column(sa.Column('pipeline_added_at', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('last_contact_at', sa.Integer(), nullable=True))
    op.create_index('ix_leads_pipeline_added_at', 'leads', ['pipeline_added_at'])
    op.create_index('ix_leads_last_contact_at', 'leads', ['last_contact_at'])

    # Existing pipeline rows predate this field. created_at is the safest useful baseline.
    op.execute("UPDATE leads SET pipeline_added_at = created_at WHERE in_pipeline = 1 AND pipeline_added_at IS NULL")

    op.create_table(
        'lead_activities',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('lead_id', sa.String(length=36), nullable=False),
        sa.Column('kind', sa.String(length=30), nullable=False),
        sa.Column('body', sa.Text(), nullable=False, server_default=''),
        sa.Column('metadata_json', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_lead_activities_user_id', 'lead_activities', ['user_id'])
    op.create_index('ix_lead_activities_lead_id', 'lead_activities', ['lead_id'])
    op.create_index('ix_lead_activities_kind', 'lead_activities', ['kind'])
    op.create_index('ix_lead_activities_created_at', 'lead_activities', ['created_at'])

    op.create_table(
        'radar_saved_searches',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=80), nullable=False),
        sa.Column('query_json', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('result_ids_json', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('last_new_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_run_at', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.Integer(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'name', name='uq_radar_saved_search_user_name'),
    )
    op.create_index('ix_radar_saved_searches_user_id', 'radar_saved_searches', ['user_id'])
    op.create_index('ix_radar_saved_searches_updated_at', 'radar_saved_searches', ['updated_at'])


def downgrade():
    op.drop_index('ix_radar_saved_searches_updated_at', table_name='radar_saved_searches')
    op.drop_index('ix_radar_saved_searches_user_id', table_name='radar_saved_searches')
    op.drop_table('radar_saved_searches')

    op.drop_index('ix_lead_activities_created_at', table_name='lead_activities')
    op.drop_index('ix_lead_activities_kind', table_name='lead_activities')
    op.drop_index('ix_lead_activities_lead_id', table_name='lead_activities')
    op.drop_index('ix_lead_activities_user_id', table_name='lead_activities')
    op.drop_table('lead_activities')

    op.drop_index('ix_leads_last_contact_at', table_name='leads')
    op.drop_index('ix_leads_pipeline_added_at', table_name='leads')
    with op.batch_alter_table('leads') as batch:
        batch.drop_column('last_contact_at')
        batch.drop_column('pipeline_added_at')
