"""add user_role_scope table

Revision ID: 4f2f6efb0c3f
Revises: 38e01ad77680
Create Date: 2026-04-15 10:10:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "4f2f6efb0c3f"
down_revision: Union[str, Sequence[str], None] = "38e01ad77680"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_role_scope",
        sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=True),
        sa.Column("resource", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("scope_key", sa.Text(), nullable=True),
        sa.Column("scope_value", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("row_id"),
    )


def downgrade() -> None:
    op.drop_table("user_role_scope")
