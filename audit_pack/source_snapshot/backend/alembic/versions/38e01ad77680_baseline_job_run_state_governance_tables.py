"""baseline: job_run_state, governance tables

Revision ID: 38e01ad77680
Revises:
Create Date: 2026-04-13 10:36:24.757488

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "38e01ad77680"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "job_run_state",
        sa.Column("run_id", sa.String(length=255), nullable=False),
        sa.Column("job_name", sa.String(length=255), nullable=False),
        sa.Column("cache_key", sa.String(length=255), nullable=False),
        sa.Column("report_date", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source_version", sa.String(length=255), nullable=False),
        sa.Column("vendor_version", sa.String(length=255), nullable=False),
        sa.Column("rule_version", sa.String(length=255), nullable=True),
        sa.Column("input_source_version", sa.String(length=255), nullable=True),
        sa.Column("input_rule_version", sa.String(length=255), nullable=True),
        sa.Column("trace_id", sa.String(length=255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("queued_at", sa.String(length=64), nullable=True),
        sa.Column("started_at", sa.String(length=64), nullable=True),
        sa.Column("finished_at", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.String(length=64), nullable=False),
        sa.Column("updated_at", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_index(op.f("ix_job_run_state_cache_key"), "job_run_state", ["cache_key"], unique=False)
    op.create_index(op.f("ix_job_run_state_job_name"), "job_run_state", ["job_name"], unique=False)
    op.create_index(op.f("ix_job_run_state_report_date"), "job_run_state", ["report_date"], unique=False)
    op.create_index(op.f("ix_job_run_state_status"), "job_run_state", ["status"], unique=False)

    op.create_table(
        "cache_build_run",
        sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("job_name", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("cache_key", sa.Text(), nullable=False),
        sa.Column("lock", sa.Text(), nullable=True),
        sa.Column("source_version", sa.Text(), nullable=True),
        sa.Column("vendor_version", sa.Text(), nullable=True),
        sa.Column("rule_version", sa.Text(), nullable=True),
        sa.Column("started_at", sa.Text(), nullable=True),
        sa.Column("finished_at", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("row_id"),
    )
    op.create_table(
        "cache_manifest",
        sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("cache_key", sa.Text(), nullable=False),
        sa.Column("source_version", sa.Text(), nullable=True),
        sa.Column("vendor_version", sa.Text(), nullable=True),
        sa.Column("rule_version", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("row_id"),
    )
    op.create_table(
        "source_version_registry",
        sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_name", sa.Text(), nullable=False),
        sa.Column("source_version", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("row_id"),
    )
    op.create_table(
        "rule_version_registry",
        sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("rule_name", sa.Text(), nullable=False),
        sa.Column("rule_version", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("row_id"),
    )


def downgrade() -> None:
    op.drop_table("rule_version_registry")
    op.drop_table("source_version_registry")
    op.drop_table("cache_manifest")
    op.drop_table("cache_build_run")
    op.drop_index(op.f("ix_job_run_state_status"), table_name="job_run_state")
    op.drop_index(op.f("ix_job_run_state_report_date"), table_name="job_run_state")
    op.drop_index(op.f("ix_job_run_state_job_name"), table_name="job_run_state")
    op.drop_index(op.f("ix_job_run_state_cache_key"), table_name="job_run_state")
    op.drop_table("job_run_state")
