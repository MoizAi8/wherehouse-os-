"""Record the last timestamped carrier event for replay and ordering checks."""

import sqlalchemy as sa
from alembic import op

revision = "c43901d7fe52"
down_revision = "b9e31a4c7620"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("shipments", sa.Column("carrier_event_at", sa.DateTime(timezone=True)))
    op.add_column("shipments", sa.Column("carrier_event_hash", sa.String(64)))


def downgrade() -> None:
    op.drop_column("shipments", "carrier_event_hash")
    op.drop_column("shipments", "carrier_event_at")
