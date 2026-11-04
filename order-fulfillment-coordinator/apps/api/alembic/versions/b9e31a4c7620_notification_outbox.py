"""Persist notification intents and delivery attempts."""

import sqlalchemy as sa
from alembic import op

revision = "b9e31a4c7620"
down_revision = "b73a06f2ed81"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("notifications") as batch:
        batch.add_column(sa.Column("delivery_key", sa.String(64)))
        batch.add_column(sa.Column("delivery_attempts", sa.Integer()))
        batch.add_column(sa.Column("delivery_due_at", sa.DateTime(timezone=True)))
        batch.create_unique_constraint("uq_notification_delivery_key", ["delivery_key"])
        batch.create_index("ix_notifications_delivery_due_at", ["delivery_due_at"])


def downgrade() -> None:
    if op.get_bind().execute(sa.text("SELECT 1 FROM notifications WHERE delivery_key IS NOT NULL LIMIT 1")).first():
        raise RuntimeError("Preserve durable notification records before downgrade")
    with op.batch_alter_table("notifications") as batch:
        batch.drop_index("ix_notifications_delivery_due_at")
        batch.drop_constraint("uq_notification_delivery_key", type_="unique")
        batch.drop_column("delivery_due_at")
        batch.drop_column("delivery_attempts")
        batch.drop_column("delivery_key")
