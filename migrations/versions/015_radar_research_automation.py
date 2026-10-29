"""Radar Research & Automation 2.0 part 1: monitored saved searches."""
from alembic import op
import sqlalchemy as sa

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("radar_saved_searches") as batch:
        batch.add_column(sa.Column("monitor_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("monitor_interval", sa.String(length=12), nullable=False, server_default="daily"))
        batch.add_column(sa.Column("next_monitor_at", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("last_monitor_at", sa.Integer(), nullable=True))
    op.create_index("ix_radar_saved_searches_next_monitor_at", "radar_saved_searches", ["next_monitor_at"])


def downgrade():
    op.drop_index("ix_radar_saved_searches_next_monitor_at", table_name="radar_saved_searches")
    with op.batch_alter_table("radar_saved_searches") as batch:
        batch.drop_column("last_monitor_at")
        batch.drop_column("next_monitor_at")
        batch.drop_column("monitor_interval")
        batch.drop_column("monitor_enabled")
