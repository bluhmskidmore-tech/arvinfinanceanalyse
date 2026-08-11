"""Consolidated product dashboard — analytical KPI read models."""
from __future__ import annotations

from typing import Annotated

from backend.app.api.deps import ensure_read_allowed
from backend.app.api.perf_logging import timed_api_call
from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
from backend.app.services.dashboard_service import get_core_metrics, get_daily_changes
from fastapi import APIRouter, Depends, Query

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _ensure_dashboard_read_allowed(auth: AuthContext) -> None:
    ensure_read_allowed(auth, "dashboard", settings=get_settings(), authorize=ensure_user_allowed)


@router.get("/core_metrics")
def core_metrics(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: Annotated[
        str | None,
        Query(description="Trading date anchor (YYYY-MM-DD); omit for latest merged date."),
    ] = None,
) -> dict[str, object]:
    _ensure_dashboard_read_allowed(auth)
    return timed_api_call(
        "/api/dashboard/core_metrics",
        lambda: get_core_metrics(report_date),
    )


@router.get("/daily-changes")
def daily_changes(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: Annotated[
        str | None,
        Query(description="Trading date anchor (YYYY-MM-DD); omit for latest merged date."),
    ] = None,
) -> dict[str, object]:
    _ensure_dashboard_read_allowed(auth)
    return timed_api_call(
        "/api/dashboard/daily-changes",
        lambda: get_daily_changes(report_date),
    )
