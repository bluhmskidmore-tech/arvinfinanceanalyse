"""add agent governance stream tables

Revision ID: 7d1a2c3e4f50
Revises: ee687fb6fa38
Create Date: 2026-08-27 13:20:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "7d1a2c3e4f50"
down_revision: str | Sequence[str] | None = "ee687fb6fa38"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_audit",
        sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("row_id"),
    )
    op.create_table(
        "agent_prompt",
        sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("row_id"),
    )


def downgrade() -> None:
    op.drop_table("agent_prompt")
    op.drop_table("agent_audit")
