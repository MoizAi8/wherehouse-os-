"""Track local monitor checks independently from carrier updates."""
from alembic import op
import sqlalchemy as sa

revision = "d106e54b8732"
down_revision = "c43901d7fe52"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("shipments", sa.Column("last_monitored_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("shipments", "last_monitored_at")
