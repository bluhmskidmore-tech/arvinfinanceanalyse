"""add launch governance lineage columns

Revision ID: 9c4f1e7a2b6d
Revises: 4f2f6efb0c3f
Create Date: 2026-04-15 16:45:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "9c4f1e7a2b6d"
down_revision: Union[str, Sequence[str], None] = "4f2f6efb0c3f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("cache_build_run", sa.Column("cache_version", sa.Text(), nullable=True))
    op.add_column("cache_build_run", sa.Column("report_date", sa.Text(), nullable=True))
    op.add_column("cache_build_run", sa.Column("queued_at", sa.Text(), nullable=True))
    op.add_column("cache_build_run", sa.Column("failure_category", sa.Text(), nullable=True))
    op.add_column("cache_build_run", sa.Column("failure_reason", sa.Text(), nullable=True))
    op.add_column("cache_manifest", sa.Column("cache_version", sa.Text(), nullable=True))
    op.add_column("cache_manifest", sa.Column("module_name", sa.Text(), nullable=True))
    op.add_column("cache_manifest", sa.Column("basis", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("cache_manifest", "basis")
    op.drop_column("cache_manifest", "module_name")
    op.drop_column("cache_manifest", "cache_version")
    op.drop_column("cache_build_run", "failure_reason")
    op.drop_column("cache_build_run", "failure_category")
    op.drop_column("cache_build_run", "queued_at")
    op.drop_column("cache_build_run", "report_date")
    op.drop_column("cache_build_run", "cache_version")
