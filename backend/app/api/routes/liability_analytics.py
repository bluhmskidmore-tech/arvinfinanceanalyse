from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query

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


def _raise_liability_analytics_not_promoted() -> None:
    raise HTTPException(
        status_code=503,
        detail="Liability analytics compatibility routes are reserved and not backed by the current governed rollout yet.",
    )


@router.get("/api/risk/buckets")
def liability_risk_buckets(
    report_date: str | None = Query(None, description="Report date in YYYY-MM-DD format."),
) -> dict[str, object]:
    _validate_optional_report_date(report_date)
    _raise_liability_analytics_not_promoted()


@router.get("/api/analysis/yield_metrics")
def liability_yield_metrics(
    report_date: str | None = Query(None, description="Report date in YYYY-MM-DD format."),
) -> dict[str, object]:
    _validate_optional_report_date(report_date)
    _raise_liability_analytics_not_promoted()


@router.get("/api/analysis/liabilities/counterparty")
def liability_counterparty(
    report_date: str | None = Query(None, description="Report date in YYYY-MM-DD format."),
    top_n: int = Query(10, ge=1, le=5000),
) -> dict[str, object]:
    _validate_optional_report_date(report_date)
    _raise_liability_analytics_not_promoted()


@router.get("/api/liabilities/monthly")
def liabilities_monthly(
    year: int | None = Query(None, ge=2000, le=2100),
) -> dict[str, object]:
    _raise_liability_analytics_not_promoted()
