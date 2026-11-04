"""Persist typed order lines and link automatic reservations."""

import sqlalchemy as sa
from alembic import op

revision = "c8e2401a52df"
down_revision = "f3a84d6720b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "order_lines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sku", sa.String(80), sa.ForeignKey("inventory_products.sku"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.UniqueConstraint("order_id", "sku", name="uq_order_lines_sku"),
        sa.CheckConstraint("quantity > 0", name="ck_order_lines_quantity"),
    )
    with op.batch_alter_table("inventory_reservations") as batch:
        batch.add_column(sa.Column("order_line_id", sa.String(36), nullable=True))
        batch.create_foreign_key("fk_reservation_order_line", "order_lines", ["order_line_id"], ["id"])
        batch.create_unique_constraint("uq_reservation_order_line", ["order_line_id"])


def downgrade() -> None:
    if op.get_bind().execute(sa.text("SELECT 1 FROM order_lines LIMIT 1")).first():
        raise RuntimeError("Typed order lines exist. Reconcile them before downgrade.")
    with op.batch_alter_table("inventory_reservations") as batch:
        batch.drop_constraint("uq_reservation_order_line", type_="unique")
        batch.drop_constraint("fk_reservation_order_line", type_="foreignkey")
        batch.drop_column("order_line_id")
    op.drop_table("order_lines")
