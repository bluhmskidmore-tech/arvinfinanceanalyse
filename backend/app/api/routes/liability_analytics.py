from __future__ import annotations

from datetime import date
from typing import Annotated

from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
from backend.app.services.liability_analytics_service import (
    cockpit_warnings_payload,
    contribution_split_payload,
    liabilities_monthly_payload,
    liability_counterparty_payload,
    liability_risk_buckets_payload,
    liability_yield_by_period_payload,
    liability_yield_metrics_payload,
)
from backend.app.services.liability_knowledge_service import (
    liability_knowledge_brief_envelope,
)
from fastapi import APIRouter, Depends, HTTPException, Query

router = APIRouter(tags=["liability-analytics"])


def _ensure_liability_analytics_read_allowed(auth: AuthContext) -> None:
    try:
        ensure_user_allowed(
            auth=auth,
            settings=get_settings(),
            resource="liability_analytics",
            action="read",
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


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
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: str | None = Query(None, description="Report date in YYYY-MM-DD format."),
) -> dict[str, object]:
    validated = _validate_optional_report_date(report_date)
    _ensure_liability_analytics_read_allowed(auth)
    return liability_risk_buckets_payload(
        duckdb_path=str(get_settings().duckdb_path),
        report_date=validated,
    )


@router.get("/api/analysis/yield_metrics")
def liability_yield_metrics(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: str | None = Query(None, description="Report date in YYYY-MM-DD format."),
) -> dict[str, object]:
    validated = _validate_optional_report_date(report_date)
    _ensure_liability_analytics_read_allowed(auth)
    return liability_yield_metrics_payload(
        duckdb_path=str(get_settings().duckdb_path),
        report_date=validated,
    )


@router.get("/api/analysis/yield-by-period")
def liability_yield_by_period(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    year: int = Query(..., ge=2000, le=2100, description="Calendar year for period rollups."),
    period_type: str = Query(
        "monthly",
        description="V1-compatible period grouping: monthly | quarterly | yearly.",
    ),
) -> dict[str, object]:
    _ensure_liability_analytics_read_allowed(auth)
    return liability_yield_by_period_payload(
        duckdb_path=str(get_settings().duckdb_path),
        year=year,
        period_type=period_type,
    )


@router.get("/api/analysis/liabilities/counterparty")
def liability_counterparty(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: str | None = Query(None, description="Report date in YYYY-MM-DD format."),
    top_n: int = Query(10, ge=1, le=5000),
) -> dict[str, object]:
    validated = _validate_optional_report_date(report_date)
    _ensure_liability_analytics_read_allowed(auth)
    return liability_counterparty_payload(
        duckdb_path=str(get_settings().duckdb_path),
        report_date=validated,
        top_n=top_n,
    )


@router.get("/api/liabilities/monthly")
def liabilities_monthly(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    year: int | None = Query(None, ge=2000, le=2100),
) -> dict[str, object]:
    _ensure_liability_analytics_read_allowed(auth)
    resolved_year = year or date.today().year
    return liabilities_monthly_payload(
        duckdb_path=str(get_settings().duckdb_path),
        year=resolved_year,
    )


@router.get("/ui/liability/business-context")
def liability_business_context(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict[str, object]:
    _ensure_liability_analytics_read_allowed(auth)
    return liability_knowledge_brief_envelope()


@router.get("/api/analysis/liabilities/cockpit-warnings")
def liability_cockpit_warnings(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: str | None = Query(None, description="Report date in YYYY-MM-DD format."),
) -> dict[str, object]:
    validated = _validate_optional_report_date(report_date)
    _ensure_liability_analytics_read_allowed(auth)
    return cockpit_warnings_payload(
        duckdb_path=str(get_settings().duckdb_path),
        report_date=validated,
    )


@router.get("/api/analysis/liabilities/contribution-split")
def liability_contribution_split(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: str | None = Query(None, description="Report date in YYYY-MM-DD format."),
) -> dict[str, object]:
    validated = _validate_optional_report_date(report_date)
    _ensure_liability_analytics_read_allowed(auth)
    return contribution_split_payload(
        duckdb_path=str(get_settings().duckdb_path),
        report_date=validated,
    )
