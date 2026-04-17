from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base


class KpiOwner(Base):
    __tablename__ = "kpi_owner"

    owner_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_name: Mapped[str] = mapped_column(Text, nullable=False)
    org_unit: Mapped[str] = mapped_column(Text, nullable=False)
    person_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    scope_type: Mapped[str] = mapped_column(Text, nullable=False)
    scope_key_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class KpiMetric(Base):
    __tablename__ = "kpi_metric"

    metric_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    metric_code: Mapped[str] = mapped_column(Text, nullable=False)
    owner_id: Mapped[int] = mapped_column(ForeignKey("kpi_owner.owner_id"), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    major_category: Mapped[str] = mapped_column(Text, nullable=False)
    indicator_category: Mapped[str | None] = mapped_column(Text, nullable=True)
    metric_name: Mapped[str] = mapped_column(Text, nullable=False)
    target_value: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    target_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    score_weight: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    unit: Mapped[str | None] = mapped_column(Text, nullable=True)
    scoring_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    scoring_rule_type: Mapped[str] = mapped_column(Text, nullable=False)
    data_source_type: Mapped[str] = mapped_column(Text, nullable=False)
    progress_plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class KpiMetricValue(Base):
    __tablename__ = "kpi_metric_value"

    value_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    metric_id: Mapped[int] = mapped_column(ForeignKey("kpi_metric.metric_id"), nullable=False, index=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    actual_value: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    actual_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    completion_ratio: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    progress_pct: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    score_value: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    source: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
