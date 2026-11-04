"""Support cancellation of an internal shipment before carrier handoff."""

import sqlalchemy as sa
from alembic import op

revision = "a40d73b9e219"
down_revision = "c8e2401a52df"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TYPE public.shipment_status ADD VALUE IF NOT EXISTS 'cancelled'")


def downgrade() -> None:
    db = op.get_bind()
    table = "public.shipments" if db.dialect.name == "postgresql" else "shipments"
    if db.execute(sa.text(f"SELECT 1 FROM {table} WHERE status = 'cancelled' LIMIT 1")).first():
        raise RuntimeError("Cancelled shipment records require compatible application code")
    # Leave the unused enum value in place to avoid rewriting the shipment table.
