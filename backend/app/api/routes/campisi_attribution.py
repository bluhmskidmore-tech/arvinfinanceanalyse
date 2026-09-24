"""Campisi 完整归因 API 路由。"""
from importlib import import_module
from typing import Annotated, Literal

from backend.app.api.deps import ensure_read_allowed
from backend.app.api.response_cache import (
    campisi_four_effects_cache_key,
    market_home_response_cache,
)
from backend.app.governance.settings import get_settings
from backend.app.schemas.campisi_attribution_read import (
    CampisiEnhancedEnvelope,
    CampisiFourEffectsReadEnvelope,
    CampisiMaturityBucketEnvelope,
)
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
from fastapi import APIRouter, Depends, Query

router = APIRouter(prefix="/api/pnl-attribution")


def _svc():
    return import_module("backend.app.services.campisi_attribution_service")


def _ensure_pnl_attribution_read_allowed(auth: AuthContext) -> None:
    ensure_read_allowed(auth, "pnl_attribution", settings=get_settings(), authorize=ensure_user_allowed)


@router.get(
    "/campisi/four-effects",
    response_model=CampisiFourEffectsReadEnvelope,
    response_model_exclude_unset=True,
)
def campisi_four_effects(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    start_date: str | None = Query(None, description="期初日期 YYYY-MM-DD"),
    end_date: str | None = Query(None, description="期末日期 YYYY-MM-DD"),
    lookback_days: int = Query(30, ge=1, le=365, description="无 start_date 时的回溯天数"),
    detail: Literal["full", "summary"] = Query(
        "full",
        description="full includes per-bond details; summary omits them",
    ),
) -> dict[str, object]:
    _ensure_pnl_attribution_read_allowed(auth)
    if detail != "summary":
        # full envelopes carry per-bond detail (~500KB each) and the cache key
        # includes a user-selectable date, so only the summary projection used by
        # the dashboard home first screen is cached.
        return _svc().campisi_four_effects_envelope(
            start_date=start_date,
            end_date=end_date,
            lookback_days=lookback_days,
        )
    return market_home_response_cache.get_or_build(
        campisi_four_effects_cache_key(
            str(get_settings().duckdb_path),
            detail=detail,
            start_date=start_date,
            end_date=end_date,
            lookback_days=lookback_days,
        ),
        lambda: _svc().campisi_four_effects_summary_envelope(
            start_date=start_date,
            end_date=end_date,
            lookback_days=lookback_days,
        ),
    )


@router.get(
    "/campisi/enhanced",
    response_model=CampisiEnhancedEnvelope,
    response_model_exclude_unset=True,
)
def campisi_enhanced(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    start_date: str | None = Query(None, description="期初日期 YYYY-MM-DD"),
    end_date: str | None = Query(None, description="期末日期 YYYY-MM-DD"),
    lookback_days: int = Query(30, ge=1, le=365, description="无 start_date 时的回溯天数"),
) -> dict[str, object]:
    _ensure_pnl_attribution_read_allowed(auth)
    return _svc().campisi_enhanced_envelope(
        start_date=start_date,
        end_date=end_date,
        lookback_days=lookback_days,
    )


@router.get(
    "/campisi/maturity-buckets",
    response_model=CampisiMaturityBucketEnvelope,
    response_model_exclude_unset=True,
)
def campisi_maturity_buckets(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    start_date: str | None = Query(None, description="期初日期 YYYY-MM-DD"),
    end_date: str | None = Query(None, description="期末日期 YYYY-MM-DD"),
    lookback_days: int = Query(30, ge=1, le=365, description="无 start_date 时的回溯天数"),
) -> dict[str, object]:
    _ensure_pnl_attribution_read_allowed(auth)
    return _svc().campisi_maturity_bucket_envelope(
        start_date=start_date,
        end_date=end_date,
        lookback_days=lookback_days,
    )


@router.get("/campisi/decision-grade")
def campisi_decision_grade(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    start_date: str | None = Query(None, description="期初日期 YYYY-MM-DD"),
    end_date: str | None = Query(None, description="期末日期 YYYY-MM-DD"),
    lookback_days: int = Query(
        30,
        ge=1,
        le=365,
        description="已废弃：无 start_date 时期初固定对齐 PnL 报告月上月末（月度期间口径），该参数不再参与推导",
    ),
) -> dict[str, object]:
    _ensure_pnl_attribution_read_allowed(auth)
    return _svc().campisi_decision_grade_envelope(
        start_date=start_date,
        end_date=end_date,
        lookback_days=lookback_days,
    )
