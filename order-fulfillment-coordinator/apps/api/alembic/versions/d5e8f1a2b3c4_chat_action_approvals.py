"""Add one-use chat approvals without changing customer tables.

Revision ID: d5e8f1a2b3c4
Revises: c4d7e9f0a1b2
"""
from alembic import op
import sqlalchemy as sa

revision = "d5e8f1a2b3c4"
down_revision = "c4d7e9f0a1b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("chat_approvals",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("session_key", sa.String(64), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("message_hash", sa.String(64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed", sa.Boolean(), nullable=False))


def downgrade() -> None:
    op.drop_table("chat_approvals")
