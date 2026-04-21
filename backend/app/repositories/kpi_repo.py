from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from calendar import monthrange

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.app.models.base import Base
from backend.app.models.kpi import KpiMetric, KpiMetricValue, KpiOwner


def _normalize_sqlalchemy_dsn(dsn: str) -> str:
    normalized = str(dsn or "").strip()
    if normalized.startswith("postgresql+psycopg://"):
        return normalized
    if normalized.startswith("postgresql://"):
        return "postgresql+psycopg://" + normalized[len("postgresql://") :]
    return normalized


def _to_decimal_string(value: object | None) -> str | None:
    if value is None:
        return None
    return format(Decimal(str(value)), "f")


def _period_bounds(*, year: int, period_type: str, period_value: int | None) -> tuple[date, date, str]:
    normalized = str(period_type).upper().strip()
    if normalized == "YEAR":
        start = date(year, 1, 1)
        end = date(year, 12, 31)
        return start, end, f"{year}年度"
    if normalized == "MONTH":
        if period_value is None or not 1 <= int(period_value) <= 12:
            raise ValueError("period_value must be between 1 and 12 when period_type=MONTH")
        month = int(period_value)
        start = date(year, month, 1)
        end = date(year, month, monthrange(year, month)[1])
        return start, end, f"{year}年{month}月"
    if normalized == "QUARTER":
        if period_value is None or not 1 <= int(period_value) <= 4:
            raise ValueError("period_value must be between 1 and 4 when period_type=QUARTER")
        quarter = int(period_value)
        start_month = (quarter - 1) * 3 + 1
        end_month = start_month + 2
        start = date(year, start_month, 1)
        end = date(year, end_month, monthrange(year, end_month)[1])
        return start, end, f"{year}年Q{quarter}"
    raise ValueError(f"Unsupported period_type={period_type!r}")


@dataclass
class KpiRepository:
    dsn: str

    def __post_init__(self) -> None:
        self.engine = create_engine(_normalize_sqlalchemy_dsn(self.dsn), future=True)
        self._session_factory = sessionmaker(self.engine, future=True)
        if self.engine.dialect.name == "sqlite":
            Base.metadata.create_all(
                self.engine,
                tables=[
                    KpiOwner.__table__,
                    KpiMetric.__table__,
                    KpiMetricValue.__table__,
                ],
            )

    def list_owners(self, *, year: int | None = None, is_active: bool | None = None) -> list[dict[str, object]]:
        with self._session_factory() as session:
            stmt = select(KpiOwner)
            if year is not None:
                stmt = stmt.where(KpiOwner.year == int(year))
            if is_active is not None:
                stmt = stmt.where(KpiOwner.is_active.is_(bool(is_active)))
            stmt = stmt.order_by(KpiOwner.year.desc(), KpiOwner.owner_id.asc())
            rows = session.execute(stmt).scalars().all()
        return [
            {
                "owner_id": row.owner_id,
                "owner_name": row.owner_name,
                "org_unit": row.org_unit,
                "person_name": row.person_name,
                "year": row.year,
                "scope_type": row.scope_type,
                "scope_key": json.loads(row.scope_key_json) if row.scope_key_json else None,
                "is_active": row.is_active,
                "created_at": row.created_at.isoformat(),
                "updated_at": row.updated_at.isoformat(),
            }
            for row in rows
        ]

    def fetch_period_summary(
        self,
        *,
        owner_id: int,
        year: int,
        period_type: str,
        period_value: int | None = None,
    ) -> dict[str, object]:
        start_date, end_date, period_label = _period_bounds(
            year=year,
            period_type=period_type,
            period_value=period_value,
        )
        with self._session_factory() as session:
            owner = session.get(KpiOwner, int(owner_id))
            if owner is None:
                raise ValueError(f"Unknown KPI owner_id={owner_id}")

            metrics = session.execute(
                select(KpiMetric)
                .where(KpiMetric.owner_id == int(owner_id))
                .where(KpiMetric.year == int(year))
                .where(KpiMetric.is_active.is_(True))
                .order_by(KpiMetric.metric_id.asc())
            ).scalars().all()

            metric_ids = [metric.metric_id for metric in metrics]
            values = session.execute(
                select(KpiMetricValue)
                .where(KpiMetricValue.metric_id.in_(metric_ids) if metric_ids else False)
                .where(KpiMetricValue.as_of_date >= start_date)
                .where(KpiMetricValue.as_of_date <= end_date)
                .order_by(
                    KpiMetricValue.metric_id.asc(),
                    KpiMetricValue.as_of_date.desc(),
                    KpiMetricValue.updated_at.desc(),
                )
            ).scalars().all()

        latest_by_metric: dict[int, KpiMetricValue] = {}
        for row in values:
            latest_by_metric.setdefault(row.metric_id, row)

        metric_rows: list[dict[str, object]] = []
        total_weight = Decimal("0")
        total_score = Decimal("0")
        for metric in metrics:
            latest = latest_by_metric.get(metric.metric_id)
            total_weight += Decimal(str(metric.score_weight or 0))
            total_score += Decimal(str(latest.score_value or 0)) if latest is not None else Decimal("0")
            metric_rows.append(
                {
                    "metric_id": metric.metric_id,
                    "metric_code": metric.metric_code,
                    "metric_name": metric.metric_name,
                    "major_category": metric.major_category,
                    "indicator_category": metric.indicator_category,
                    "target_value": _to_decimal_string(metric.target_value),
                    "unit": metric.unit,
                    "score_weight": _to_decimal_string(metric.score_weight) or "0",
                    "period_actual_value": _to_decimal_string(getattr(latest, "actual_value", None)),
                    "period_completion_ratio": _to_decimal_string(getattr(latest, "completion_ratio", None)),
                    "period_progress_pct": _to_decimal_string(getattr(latest, "progress_pct", None)),
                    "period_score_value": _to_decimal_string(getattr(latest, "score_value", None)),
                    "period_start_date": start_date.isoformat(),
                    "period_end_date": end_date.isoformat(),
                    "data_date": latest.as_of_date.isoformat() if latest is not None else None,
                }
            )

        return {
            "owner_id": owner.owner_id,
            "owner_name": owner.owner_name,
            "year": year,
            "period_type": period_type,
            "period_value": period_value,
            "period_label": period_label,
            "period_start_date": start_date.isoformat(),
            "period_end_date": end_date.isoformat(),
            "metrics": metric_rows,
            "total": len(metric_rows),
            "total_weight": format(total_weight, "f"),
            "total_score": format(total_score, "f"),
        }
