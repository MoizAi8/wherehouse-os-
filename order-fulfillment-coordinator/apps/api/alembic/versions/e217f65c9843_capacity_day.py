"""Scope fulfillment capacity counters to a UTC business day."""
from alembic import op
import sqlalchemy as sa

revision = "e217f65c9843"
down_revision = "d106e54b8732"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("fulfillment_centers", sa.Column("capacity_day", sa.Date(), nullable=False, server_default=sa.func.current_date()))


def downgrade() -> None:
    op.drop_column("fulfillment_centers", "capacity_day")
