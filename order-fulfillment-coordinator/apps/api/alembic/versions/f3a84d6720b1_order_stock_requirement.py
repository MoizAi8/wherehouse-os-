"""Preserve the inventory gate for orders created for allocation."""

import sqlalchemy as sa
from alembic import op

revision = "f3a84d6720b1"
down_revision = "e4f71ab892cd"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("requires_stock", sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade() -> None:
    if op.get_bind().execute(sa.text("SELECT 1 FROM orders WHERE requires_stock LIMIT 1")).first():
        raise RuntimeError("Orders require inventory allocation. Reconcile these orders before downgrade.")
    op.drop_column("orders", "requires_stock")
