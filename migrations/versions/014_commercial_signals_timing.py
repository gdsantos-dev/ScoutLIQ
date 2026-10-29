"""Add commercial signal history for Score Engine 2.0 part 5."""
from alembic import op
import sqlalchemy as sa

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("leads") as batch:
        batch.add_column(sa.Column("commercial_signal_json", sa.Text(), nullable=False, server_default="{}"))
        batch.add_column(sa.Column("commercial_signal_analyzed_at", sa.Integer(), nullable=True))
    op.create_index("ix_leads_commercial_signal_analyzed_at", "leads", ["commercial_signal_analyzed_at"])


def downgrade():
    op.drop_index("ix_leads_commercial_signal_analyzed_at", table_name="leads")
    with op.batch_alter_table("leads") as batch:
        batch.drop_column("commercial_signal_analyzed_at")
        batch.drop_column("commercial_signal_json")
