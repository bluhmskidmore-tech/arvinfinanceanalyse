"""PnL attribution workbench HTTP API (`/api/pnl-attribution/*`)."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query

from backend.app.services.pnl_attribution_service import (
    advanced_attribution_summary_envelope,
    attribution_analysis_summary_envelope,
    campisi_attribution_envelope,
    carry_roll_down_envelope,
    krd_attribution_envelope,
    pnl_composition_envelope,
    spread_attribution_envelope,
    tpl_market_correlation_envelope,
    volume_rate_attribution_envelope,
)

router = APIRouter(prefix="/api/pnl-attribution", tags=["pnl-attribution"])


@router.get("/volume-rate")
def volume_rate(
    report_date: str | None = Query(None, description="YYYY-MM-DD; defaults to latest available date"),
    compare_type: Literal["mom", "yoy"] = Query("mom"),
) -> dict[str, object]:
    return volume_rate_attribution_envelope(report_date=report_date, compare_type=compare_type)


@router.get("/tpl-market")
def tpl_market(
    months: int = Query(12, ge=1, le=120),
) -> dict[str, object]:
    return tpl_market_correlation_envelope(months=months)


@router.get("/composition")
def composition(
    report_date: str | None = Query(None),
    include_trend: bool = Query(True),
    trend_months: int = Query(6, ge=1, le=60),
) -> dict[str, object]:
    return pnl_composition_envelope(
        report_date=report_date,
        include_trend=include_trend,
        trend_months=trend_months,
    )


@router.get("/summary")
def summary(
    report_date: str | None = Query(None),
) -> dict[str, object]:
    return attribution_analysis_summary_envelope(report_date=report_date)


@router.get("/advanced/carry-rolldown")
def carry_rolldown(
    report_date: str | None = Query(None),
) -> dict[str, object]:
    return carry_roll_down_envelope(report_date=report_date)


@router.get("/advanced/spread")
def spread(
    report_date: str | None = Query(None),
    lookback_days: int = Query(30, ge=1, le=365),
) -> dict[str, object]:
    return spread_attribution_envelope(report_date=report_date, lookback_days=lookback_days)


@router.get("/advanced/krd")
def krd(
    report_date: str | None = Query(None),
    lookback_days: int = Query(30, ge=1, le=365),
) -> dict[str, object]:
    return krd_attribution_envelope(report_date=report_date, lookback_days=lookback_days)


@router.get("/advanced/summary")
def advanced_summary(
    report_date: str | None = Query(None),
) -> dict[str, object]:
    return advanced_attribution_summary_envelope(report_date=report_date)


@router.get("/advanced/campisi")
def campisi(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    lookback_days: int = Query(30, ge=1, le=365),
) -> dict[str, object]:
    return campisi_attribution_envelope(
        start_date=start_date,
        end_date=end_date,
        lookback_days=lookback_days,
    )
