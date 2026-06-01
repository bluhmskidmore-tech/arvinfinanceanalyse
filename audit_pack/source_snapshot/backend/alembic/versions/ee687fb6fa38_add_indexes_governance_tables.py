"""add indexes governance tables

Revision ID: ee687fb6fa38
Revises: b5a7d4a9f2c1
Create Date: 2026-04-17 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "ee687fb6fa38"
down_revision: str | Sequence[str] | None = "b5a7d4a9f2c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # cache_build_run.cache_key — filter/join key
    op.create_index(
        op.f("ix_cache_build_run_cache_key"),
        "cache_build_run",
        ["cache_key"],
        unique=False,
    )
    # cache_manifest.cache_key — primary lookup key, latest row wins but history must remain append-only
    op.create_index(
        op.f("ix_cache_manifest_cache_key"),
        "cache_manifest",
        ["cache_key"],
        unique=False,
    )
    # user_role_scope.user_id — join/filter key
    op.create_index(
        op.f("ix_user_role_scope_user_id"),
        "user_role_scope",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_user_role_scope_user_id"), table_name="user_role_scope")
    op.drop_index(op.f("ix_cache_manifest_cache_key"), table_name="cache_manifest")
    op.drop_index(op.f("ix_cache_build_run_cache_key"), table_name="cache_build_run")
