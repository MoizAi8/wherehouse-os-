"""Durable provider-agnostic booking intents and isolated sandbox receipts."""

from alembic import op
import sqlalchemy as sa

revision = "f328a76da954"
down_revision = "e217f65c9843"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "carrier_bookings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("shipment_id", sa.String(36), sa.ForeignKey("shipments.id"), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("idempotency_key", sa.String(36), unique=True, nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("request", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("sandbox", sa.Boolean(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True)),
        sa.Column("claim_token", sa.String(36)),
        sa.Column("provider_reference", sa.String(100)),
        sa.Column("tracking_number", sa.String(255)),
        sa.Column("error_code", sa.String(100)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('queued','submitting','retry','booked','failed','unknown','cancelled')",
            name="ck_carrier_booking_status",
        ),
    )
    op.create_index("ix_carrier_bookings_shipment_id", "carrier_bookings", ["shipment_id"])
    op.create_index("ix_carrier_bookings_status", "carrier_bookings", ["status"])
    op.create_index(
        "uq_carrier_booking_active_shipment",
        "carrier_bookings",
        ["shipment_id"],
        unique=True,
        postgresql_where=sa.text("active"),
        sqlite_where=sa.text("active = 1"),
    )
    op.create_table(
        "sandbox_carrier_receipts",
        sa.Column("idempotency_key", sa.String(36), primary_key=True),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("receipt", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM carrier_bookings")):
        raise RuntimeError(
            "Refusing to erase carrier booking history; retain schema for application rollback"
        )
    op.drop_table("sandbox_carrier_receipts")
    op.drop_table("carrier_bookings")
