"""add release control tables

Revision ID: c2e94f6a8b10
Revises: 7d1a2c3e4f50
Create Date: 2026-08-31 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c2e94f6a8b10"
down_revision: str | Sequence[str] | None = "7d1a2c3e4f50"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "release_manifest",
        sa.Column("release_id", sa.String(length=255), nullable=False),
        sa.Column("target_environment", sa.String(length=32), nullable=False),
        sa.Column("manifest_kind", sa.String(length=64), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "length(content_sha256) = 64",
            name="ck_release_manifest_content_sha256_length",
        ),
        sa.PrimaryKeyConstraint("release_id"),
        sa.UniqueConstraint(
            "target_environment",
            "content_sha256",
            name="uq_release_manifest_environment_content_sha256",
        ),
    )
    op.create_index(
        "ix_release_manifest_environment_kind_created",
        "release_manifest",
        ["target_environment", "manifest_kind", "created_at"],
        unique=False,
    )

    op.create_table(
        "release_event",
        sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.String(length=255), nullable=False),
        sa.Column("release_id", sa.String(length=255), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("from_state", sa.String(length=32), nullable=False),
        sa.Column("to_state", sa.String(length=32), nullable=False),
        sa.Column("manifest_sha256", sa.String(length=64), nullable=False),
        sa.Column("target_environment", sa.String(length=32), nullable=False),
        sa.Column("scope_kind", sa.String(length=32), nullable=True),
        sa.Column("scope_key", sa.String(length=255), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("request_sha256", sa.String(length=64), nullable=True),
        sa.Column("event_payload_json", sa.Text(), nullable=False),
        sa.Column("receipt_json", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "length(manifest_sha256) = 64",
            name="ck_release_event_manifest_sha256_length",
        ),
        sa.CheckConstraint(
            "request_sha256 IS NULL OR length(request_sha256) = 64",
            name="ck_release_event_request_sha256_length",
        ),
        sa.ForeignKeyConstraint(
            ["release_id"],
            ["release_manifest.release_id"],
            name="fk_release_event_release_id",
        ),
        sa.PrimaryKeyConstraint("row_id"),
        sa.UniqueConstraint("event_id", name="uq_release_event_event_id"),
        sa.UniqueConstraint(
            "action",
            "target_environment",
            "release_id",
            "idempotency_key",
            name="uq_release_event_scoped_idempotency_key",
        ),
    )
    op.create_index(
        "ix_release_event_release_occurred",
        "release_event",
        ["release_id", "occurred_at"],
        unique=False,
    )
    op.create_index(
        "ix_release_event_scope_occurred",
        "release_event",
        ["target_environment", "scope_kind", "scope_key", "occurred_at"],
        unique=False,
    )

    op.create_table(
        "release_alias",
        sa.Column("target_environment", sa.String(length=32), nullable=False),
        sa.Column("scope_kind", sa.String(length=32), nullable=False),
        sa.Column("scope_key", sa.String(length=255), nullable=False),
        sa.Column("current_release_id", sa.String(length=255), nullable=False),
        sa.Column("previous_release_id", sa.String(length=255), nullable=True),
        sa.Column("revision", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("alias_payload_json", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "revision >= 0",
            name="ck_release_alias_revision_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["current_release_id"],
            ["release_manifest.release_id"],
            name="fk_release_alias_current_release_id",
        ),
        sa.ForeignKeyConstraint(
            ["previous_release_id"],
            ["release_manifest.release_id"],
            name="fk_release_alias_previous_release_id",
        ),
        sa.PrimaryKeyConstraint("target_environment", "scope_kind", "scope_key"),
    )
    op.create_index(
        "ix_release_alias_current_release_id",
        "release_alias",
        ["current_release_id"],
        unique=False,
    )
    op.create_index(
        "ix_release_alias_previous_release_id",
        "release_alias",
        ["previous_release_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_release_alias_previous_release_id", table_name="release_alias")
    op.drop_index("ix_release_alias_current_release_id", table_name="release_alias")
    op.drop_table("release_alias")
    op.drop_index("ix_release_event_scope_occurred", table_name="release_event")
    op.drop_index("ix_release_event_release_occurred", table_name="release_event")
    op.drop_table("release_event")
    op.drop_index(
        "ix_release_manifest_environment_kind_created",
        table_name="release_manifest",
    )
    op.drop_table("release_manifest")
