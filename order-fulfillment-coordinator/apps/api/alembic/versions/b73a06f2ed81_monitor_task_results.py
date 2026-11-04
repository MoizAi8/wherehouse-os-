"""Keep completed monitor-task results across broker redelivery."""

import sqlalchemy as sa
from alembic import op

revision = "b73a06f2ed81"
down_revision = "a40d73b9e219"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "monitor_task_results",
        sa.Column("task_id", sa.String(255), primary_key=True),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("monitor_task_results")
