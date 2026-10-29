"""Add persisted local competitive context for Score Engine 2.0 part 4."""
from alembic import op
import sqlalchemy as sa

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("leads") as batch:
        batch.add_column(sa.Column("competitive_context_json", sa.Text(), nullable=False, server_default="{}"))
        batch.add_column(sa.Column("competitive_analyzed_at", sa.Integer(), nullable=True))
    op.create_index("ix_leads_competitive_analyzed_at", "leads", ["competitive_analyzed_at"])


def downgrade():
    op.drop_index("ix_leads_competitive_analyzed_at", table_name="leads")
    with op.batch_alter_table("leads") as batch:
        batch.drop_column("competitive_analyzed_at")
        batch.drop_column("competitive_context_json")
