"""PnL attribution workbench HTTP API (`/api/pnl-attribution/*`)."""
from __future__ import annotations

from typing import Annotated, Literal

from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
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
from fastapi import APIRouter, Depends, HTTPException, Query

router = APIRouter(prefix="/api/pnl-attribution", tags=["pnl-attribution"])


def _ensure_pnl_attribution_read_allowed(auth: AuthContext) -> None:
    try:
        ensure_user_allowed(
            auth=auth,
            settings=get_settings(),
            resource="pnl_attribution",
            action="read",
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/volume-rate")
def volume_rate(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: str | None = Query(None, description="YYYY-MM-DD; defaults to latest available date"),
    compare_type: Literal["mom", "yoy"] = Query("mom"),
) -> dict[str, object]:
    _ensure_pnl_attribution_read_allowed(auth)
    return volume_rate_attribution_envelope(report_date=report_date, compare_type=compare_type)


@router.get("/tpl-market")
def tpl_market(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    months: int = Query(12, ge=1, le=120),
    report_date: str | None = Query(None, description="YYYY-MM-DD; defaults to latest available PnL date"),
) -> dict[str, object]:
    _ensure_pnl_attribution_read_allowed(auth)
    return tpl_market_correlation_envelope(months=months, report_date=report_date)


@router.get("/composition")
def composition(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: str | None = Query(None),
    include_trend: bool = Query(True),
    trend_months: int = Query(6, ge=1, le=60),
) -> dict[str, object]:
    _ensure_pnl_attribution_read_allowed(auth)
    return pnl_composition_envelope(
        report_date=report_date,
        include_trend=include_trend,
        trend_months=trend_months,
    )


@router.get("/summary")
def summary(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: str | None = Query(None),
) -> dict[str, object]:
    _ensure_pnl_attribution_read_allowed(auth)
    return attribution_analysis_summary_envelope(report_date=report_date)


@router.get("/advanced/carry-rolldown")
def carry_rolldown(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: str | None = Query(None),
) -> dict[str, object]:
    _ensure_pnl_attribution_read_allowed(auth)
    return carry_roll_down_envelope(report_date=report_date)


@router.get("/advanced/spread")
def spread(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: str | None = Query(None),
    lookback_days: int = Query(30, ge=1, le=365),
) -> dict[str, object]:
    _ensure_pnl_attribution_read_allowed(auth)
    return spread_attribution_envelope(report_date=report_date, lookback_days=lookback_days)


@router.get("/advanced/krd")
def krd(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: str | None = Query(None),
    lookback_days: int = Query(30, ge=1, le=365),
) -> dict[str, object]:
    _ensure_pnl_attribution_read_allowed(auth)
    return krd_attribution_envelope(report_date=report_date, lookback_days=lookback_days)


@router.get("/advanced/summary")
def advanced_summary(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: str | None = Query(None),
) -> dict[str, object]:
    _ensure_pnl_attribution_read_allowed(auth)
    return advanced_attribution_summary_envelope(report_date=report_date)


@router.get("/advanced/campisi")
def campisi(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    lookback_days: int = Query(30, ge=1, le=365),
) -> dict[str, object]:
    _ensure_pnl_attribution_read_allowed(auth)
    return campisi_attribution_envelope(
        start_date=start_date,
        end_date=end_date,
        lookback_days=lookback_days,
    )
