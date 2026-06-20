"""Campisi 完整归因 API 路由。"""
from importlib import import_module
from typing import Annotated

from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
from fastapi import APIRouter, Depends, HTTPException, Query

router = APIRouter(prefix="/api/pnl-attribution")


def _svc():
    return import_module("backend.app.services.campisi_attribution_service")


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


@router.get("/campisi/four-effects")
def campisi_four_effects(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    start_date: str | None = Query(None, description="期初日期 YYYY-MM-DD"),
    end_date: str | None = Query(None, description="期末日期 YYYY-MM-DD"),
    lookback_days: int = Query(30, description="无 start_date 时的回溯天数"),
) -> dict[str, object]:
    _ensure_pnl_attribution_read_allowed(auth)
    return _svc().campisi_four_effects_envelope(
        start_date=start_date,
        end_date=end_date,
        lookback_days=lookback_days,
    )


@router.get("/campisi/enhanced")
def campisi_enhanced(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    start_date: str | None = Query(None, description="期初日期 YYYY-MM-DD"),
    end_date: str | None = Query(None, description="期末日期 YYYY-MM-DD"),
    lookback_days: int = Query(30, description="无 start_date 时的回溯天数"),
) -> dict[str, object]:
    _ensure_pnl_attribution_read_allowed(auth)
    return _svc().campisi_enhanced_envelope(
        start_date=start_date,
        end_date=end_date,
        lookback_days=lookback_days,
    )


@router.get("/campisi/maturity-buckets")
def campisi_maturity_buckets(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    start_date: str | None = Query(None, description="期初日期 YYYY-MM-DD"),
    end_date: str | None = Query(None, description="期末日期 YYYY-MM-DD"),
    lookback_days: int = Query(30, description="无 start_date 时的回溯天数"),
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
    lookback_days: int = Query(30, description="无 start_date 时的回溯天数"),
) -> dict[str, object]:
    _ensure_pnl_attribution_read_allowed(auth)
    return _svc().campisi_decision_grade_envelope(
        start_date=start_date,
        end_date=end_date,
        lookback_days=lookback_days,
    )
