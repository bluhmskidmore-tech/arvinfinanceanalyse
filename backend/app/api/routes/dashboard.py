"""Consolidated product dashboard — analytical KPI read models."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from backend.app.api.perf_logging import timed_api_call
from backend.app.services.dashboard_service import get_core_metrics, get_daily_changes

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/core_metrics")
def core_metrics(
    report_date: Annotated[
        str | None,
        Query(description="Trading date anchor (YYYY-MM-DD); omit for latest merged date."),
    ] = None,
) -> dict[str, object]:
    return timed_api_call(
        "/api/dashboard/core_metrics",
        lambda: get_core_metrics(report_date),
    )


@router.get("/daily-changes")
def daily_changes(
    report_date: Annotated[
        str | None,
        Query(description="Trading date anchor (YYYY-MM-DD); omit for latest merged date."),
    ] = None,
) -> dict[str, object]:
    return timed_api_call(
        "/api/dashboard/daily-changes",
        lambda: get_daily_changes(report_date),
    )
