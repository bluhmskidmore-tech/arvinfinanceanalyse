"""add kpi tables

Revision ID: b5a7d4a9f2c1
Revises: 9c4f1e7a2b6d
Create Date: 2026-04-16 23:10:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b5a7d4a9f2c1"
down_revision: Union[str, Sequence[str], None] = "9c4f1e7a2b6d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "kpi_owner",
        sa.Column("owner_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_name", sa.Text(), nullable=False),
        sa.Column("org_unit", sa.Text(), nullable=False),
        sa.Column("person_name", sa.Text(), nullable=True),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("scope_type", sa.Text(), nullable=False),
        sa.Column("scope_key_json", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("owner_id"),
    )
    op.create_index(op.f("ix_kpi_owner_year"), "kpi_owner", ["year"], unique=False)

    op.create_table(
        "kpi_metric",
        sa.Column("metric_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("metric_code", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("major_category", sa.Text(), nullable=False),
        sa.Column("indicator_category", sa.Text(), nullable=True),
        sa.Column("metric_name", sa.Text(), nullable=False),
        sa.Column("target_value", sa.Numeric(18, 6), nullable=True),
        sa.Column("target_text", sa.Text(), nullable=True),
        sa.Column("score_weight", sa.Numeric(18, 6), nullable=False),
        sa.Column("unit", sa.Text(), nullable=True),
        sa.Column("scoring_text", sa.Text(), nullable=True),
        sa.Column("scoring_rule_type", sa.Text(), nullable=False),
        sa.Column("data_source_type", sa.Text(), nullable=False),
        sa.Column("progress_plan", sa.Text(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["kpi_owner.owner_id"]),
        sa.PrimaryKeyConstraint("metric_id"),
    )
    op.create_index(op.f("ix_kpi_metric_owner_id"), "kpi_metric", ["owner_id"], unique=False)
    op.create_index(op.f("ix_kpi_metric_year"), "kpi_metric", ["year"], unique=False)

    op.create_table(
        "kpi_metric_value",
        sa.Column("value_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("metric_id", sa.Integer(), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("actual_value", sa.Numeric(18, 6), nullable=True),
        sa.Column("actual_text", sa.Text(), nullable=True),
        sa.Column("completion_ratio", sa.Numeric(18, 6), nullable=True),
        sa.Column("progress_pct", sa.Numeric(18, 6), nullable=True),
        sa.Column("score_value", sa.Numeric(18, 6), nullable=True),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["metric_id"], ["kpi_metric.metric_id"]),
        sa.PrimaryKeyConstraint("value_id"),
    )
    op.create_index(op.f("ix_kpi_metric_value_as_of_date"), "kpi_metric_value", ["as_of_date"], unique=False)
    op.create_index(op.f("ix_kpi_metric_value_metric_id"), "kpi_metric_value", ["metric_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_kpi_metric_value_metric_id"), table_name="kpi_metric_value")
    op.drop_index(op.f("ix_kpi_metric_value_as_of_date"), table_name="kpi_metric_value")
    op.drop_table("kpi_metric_value")
    op.drop_index(op.f("ix_kpi_metric_year"), table_name="kpi_metric")
    op.drop_index(op.f("ix_kpi_metric_owner_id"), table_name="kpi_metric")
    op.drop_table("kpi_metric")
    op.drop_index(op.f("ix_kpi_owner_year"), table_name="kpi_owner")
    op.drop_table("kpi_owner")
