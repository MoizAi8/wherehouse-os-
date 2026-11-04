"""Add SKU inventory, order reservations, and stock movements."""

import sqlalchemy as sa
from alembic import op

revision = "e4f71ab892cd"
down_revision = "d5e8f1a2b3c4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inventory_products",
        sa.Column("sku", sa.String(80), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
    )
    op.create_table(
        "inventory_stock",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("sku", sa.String(80), sa.ForeignKey("inventory_products.sku"), nullable=False),
        sa.Column("center_id", sa.String(36), sa.ForeignKey("fulfillment_centers.id"), nullable=False),
        sa.Column("on_hand", sa.Integer(), nullable=False),
        sa.Column("reserved", sa.Integer(), nullable=False),
        sa.Column("low_stock_threshold", sa.Integer(), nullable=False),
        sa.UniqueConstraint("sku", "center_id", name="uq_inventory_stock_location"),
        sa.CheckConstraint("reserved >= 0 AND on_hand >= reserved", name="ck_inventory_stock_balance"),
        sa.CheckConstraint("low_stock_threshold >= 0", name="ck_inventory_stock_threshold"),
    )
    op.create_table(
        "inventory_reservations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("stock_id", sa.String(36), sa.ForeignKey("inventory_stock.id"), nullable=False),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.UniqueConstraint("stock_id", "order_id", name="uq_inventory_reservation_order_stock"),
        sa.CheckConstraint("quantity > 0", name="ck_inventory_reservation_quantity"),
        sa.CheckConstraint("status IN ('reserved', 'released', 'consumed')", name="ck_inventory_reservation_status"),
    )
    op.create_index("ix_inventory_reservations_order_id", "inventory_reservations", ["order_id"])
    op.create_table(
        "inventory_movements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("stock_id", sa.String(36), sa.ForeignKey("inventory_stock.id"), nullable=False),
        sa.Column("reservation_id", sa.String(36), sa.ForeignKey("inventory_reservations.id"), nullable=True),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("on_hand_delta", sa.Integer(), nullable=False),
        sa.Column("reserved_delta", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(250), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_inventory_movements_stock_id", "inventory_movements", ["stock_id"])


def downgrade() -> None:
    if op.get_bind().execute(sa.text("SELECT 1 FROM inventory_products LIMIT 1")).first():
        raise RuntimeError("Inventory contains business records. Export and reconcile them before downgrade.")
    op.drop_table("inventory_movements")
    op.drop_table("inventory_reservations")
    op.drop_table("inventory_stock")
    op.drop_table("inventory_products")
