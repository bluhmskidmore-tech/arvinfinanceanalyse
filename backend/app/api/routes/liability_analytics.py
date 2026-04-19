from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query

from backend.app.governance.settings import settings
from backend.app.services.liability_analytics_service import (
    liabilities_monthly_payload,
    liability_counterparty_payload,
    liability_risk_buckets_payload,
    liability_yield_metrics_payload,
)
from backend.app.services.liability_knowledge_service import (
    liability_knowledge_brief_envelope,
)

router = APIRouter(tags=["liability-analytics"])


def _validate_optional_report_date(report_date: str | None) -> str | None:
    candidate = str(report_date or "").strip()
    if not candidate:
        return None
    try:
        date.fromisoformat(candidate)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid report_date. Expected YYYY-MM-DD.") from exc
    return candidate


@router.get("/api/risk/buckets")
def liability_risk_buckets(
    report_date: str | None = Query(None, description="Report date in YYYY-MM-DD format."),
) -> dict[str, object]:
    validated = _validate_optional_report_date(report_date)
    return liability_risk_buckets_payload(
        duckdb_path=str(settings.duckdb_path),
        report_date=validated,
    )


@router.get("/api/analysis/yield_metrics")
def liability_yield_metrics(
    report_date: str | None = Query(None, description="Report date in YYYY-MM-DD format."),
) -> dict[str, object]:
    validated = _validate_optional_report_date(report_date)
    return liability_yield_metrics_payload(
        duckdb_path=str(settings.duckdb_path),
        report_date=validated,
    )


@router.get("/api/analysis/liabilities/counterparty")
def liability_counterparty(
    report_date: str | None = Query(None, description="Report date in YYYY-MM-DD format."),
    top_n: int = Query(10, ge=1, le=5000),
) -> dict[str, object]:
    validated = _validate_optional_report_date(report_date)
    return liability_counterparty_payload(
        duckdb_path=str(settings.duckdb_path),
        report_date=validated,
        top_n=top_n,
    )


@router.get("/api/liabilities/monthly")
def liabilities_monthly(
    year: int | None = Query(None, ge=2000, le=2100),
) -> dict[str, object]:
    resolved_year = year or date.today().year
    return liabilities_monthly_payload(
        duckdb_path=str(settings.duckdb_path),
        year=resolved_year,
    )


@router.get("/ui/liability/business-context")
def liability_business_context() -> dict[str, object]:
    return liability_knowledge_brief_envelope()
