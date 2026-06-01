"""Campisi 完整归因 API 路由。"""
from importlib import import_module

from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/pnl-attribution")


def _svc():
    return import_module("backend.app.services.campisi_attribution_service")


@router.get("/campisi/four-effects")
def campisi_four_effects(
    start_date: str | None = Query(None, description="期初日期 YYYY-MM-DD"),
    end_date: str | None = Query(None, description="期末日期 YYYY-MM-DD"),
    lookback_days: int = Query(30, description="无 start_date 时的回溯天数"),
) -> dict[str, object]:
    return _svc().campisi_four_effects_envelope(
        start_date=start_date,
        end_date=end_date,
        lookback_days=lookback_days,
    )


@router.get("/campisi/enhanced")
def campisi_enhanced(
    start_date: str | None = Query(None, description="期初日期 YYYY-MM-DD"),
    end_date: str | None = Query(None, description="期末日期 YYYY-MM-DD"),
    lookback_days: int = Query(30, description="无 start_date 时的回溯天数"),
) -> dict[str, object]:
    return _svc().campisi_enhanced_envelope(
        start_date=start_date,
        end_date=end_date,
        lookback_days=lookback_days,
    )


@router.get("/campisi/maturity-buckets")
def campisi_maturity_buckets(
    start_date: str | None = Query(None, description="期初日期 YYYY-MM-DD"),
    end_date: str | None = Query(None, description="期末日期 YYYY-MM-DD"),
    lookback_days: int = Query(30, description="无 start_date 时的回溯天数"),
) -> dict[str, object]:
    return _svc().campisi_maturity_bucket_envelope(
        start_date=start_date,
        end_date=end_date,
        lookback_days=lookback_days,
    )


@router.get("/campisi/decision-grade")
def campisi_decision_grade(
    start_date: str | None = Query(None, description="鏈熷垵鏃ユ湡 YYYY-MM-DD"),
    end_date: str | None = Query(None, description="鏈熸湯鏃ユ湡 YYYY-MM-DD"),
    lookback_days: int = Query(30, description="鏃?start_date 鏃剁殑鍥炴函澶╂暟"),
) -> dict[str, object]:
    return _svc().campisi_decision_grade_envelope(
        start_date=start_date,
        end_date=end_date,
        lookback_days=lookback_days,
    )
