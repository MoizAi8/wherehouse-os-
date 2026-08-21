"""add app_settings table

Revision ID: b3a0c1e2f4a1
Revises: afe1b0e38c11
Create Date: 2026-08-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b3a0c1e2f4a1'
down_revision: Union[str, None] = 'afe1b0e38c11'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'app_settings',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('payload_json', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('app_settings')