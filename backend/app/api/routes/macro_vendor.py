from typing import Annotated

from backend.app.api.deps import ensure_read_allowed
from backend.app.api.perf_logging import timed_api_call
from backend.app.api.response_cache import (
    market_home_catalog_cache_key,
    market_home_choice_latest_cache_key,
    market_home_rates_cache_key,
    market_home_response_cache,
)
from backend.app.governance.settings import get_settings
from backend.app.schemas.macro_vendor import ChoiceMacroRefreshTier
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
from backend.app.services.macro_vendor_refresh_service import (
    _refresh_payload_succeeded,  # noqa: F401 - preserved route-level test contract
    refresh_choice_macro_snapshot,
    refresh_public_cross_asset_headlines,
    refresh_tushare_ncd_shibor_proxy,
    run_choice_macro_refresh,
)
from backend.app.services.macro_vendor_service import (
    choice_macro_formal_envelope,
    choice_macro_latest_envelope,
    choice_macro_refresh_status,
    fx_analytical_envelope,
    fx_formal_status_envelope,
    macro_foundation_formal_envelope,
    macro_vendor_envelope,
    market_data_bond_futures_rankings_envelope,
    market_data_coverage_summary_envelope,
    tushare_supplement_envelope,
)
from fastapi import APIRouter, Depends, HTTPException, Query

router = APIRouter()


def _ensure_macro_vendor_read_allowed(auth: AuthContext) -> None:
    ensure_read_allowed(auth, "macro_vendor", settings=get_settings(), authorize=ensure_user_allowed)


# ── Formal market-data endpoints (Phase 1 promotion) ───────────────

@router.get("/ui/market-data/rates")
def market_data_rates(auth: Annotated[AuthContext, Depends(get_auth_context)]) -> dict[str, object]:
    """Formal-basis rates for the market-data page (stable series only)."""
    _ensure_macro_vendor_read_allowed(auth)
    settings = get_settings()
    return market_home_response_cache.get_or_build(
        market_home_rates_cache_key(settings.duckdb_path),
        lambda: timed_api_call(
            "/ui/market-data/rates",
            lambda: choice_macro_formal_envelope(settings.duckdb_path),
        ),
    )


@router.get("/ui/market-data/catalog")
def market_data_catalog(auth: Annotated[AuthContext, Depends(get_auth_context)]) -> dict[str, object]:
    """Formal-basis macro catalog for the market-data page."""
    _ensure_macro_vendor_read_allowed(auth)
    settings = get_settings()
    return market_home_response_cache.get_or_build(
        market_home_catalog_cache_key(settings.duckdb_path),
        lambda: macro_foundation_formal_envelope(settings.duckdb_path),
    )


# ── Analytical / preview endpoints (unlocked from 503) ─────────────

@router.get("/ui/preview/macro-foundation")
def macro_foundation(auth: Annotated[AuthContext, Depends(get_auth_context)]) -> dict[str, object]:
    _ensure_macro_vendor_read_allowed(auth)
    settings = get_settings()
    return macro_vendor_envelope(settings.duckdb_path)


@router.get("/ui/macro/choice-series/latest")
def choice_series_latest(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    category: ChoiceMacroRefreshTier | None = None,
) -> dict[str, object]:
    _ensure_macro_vendor_read_allowed(auth)
    settings = get_settings()
    return market_home_response_cache.get_or_build(
        market_home_choice_latest_cache_key(settings.duckdb_path, category),
        lambda: choice_macro_latest_envelope(settings.duckdb_path, category=category),
    )


@router.get("/ui/market-data/fx/formal-status")
def fx_formal_status(auth: Annotated[AuthContext, Depends(get_auth_context)]) -> dict[str, object]:
    _ensure_macro_vendor_read_allowed(auth)
    settings = get_settings()
    return fx_formal_status_envelope(settings.duckdb_path)


@router.get("/ui/market-data/fx/analytical")
def fx_analytical(auth: Annotated[AuthContext, Depends(get_auth_context)]) -> dict[str, object]:
    _ensure_macro_vendor_read_allowed(auth)
    settings = get_settings()
    return fx_analytical_envelope(settings.duckdb_path)


@router.get("/ui/market-data/tushare-supplement")
def market_data_tushare_supplement(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    money_supply_limit: int = Query(default=12, ge=0, le=120),
    eco_cal_limit: int = Query(default=30, ge=0, le=300),
) -> dict[str, object]:
    _ensure_macro_vendor_read_allowed(auth)
    settings = get_settings()
    return tushare_supplement_envelope(
        settings.duckdb_path,
        money_supply_limit=money_supply_limit,
        eco_cal_limit=eco_cal_limit,
    )


@router.get("/ui/market-data/bond-futures/rankings")
def market_data_bond_futures_rankings(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    contract: str = Query(default="T.CFE", min_length=1, max_length=24),
    trade_date: str | None = Query(default=None, min_length=8, max_length=10),
    limit: int = Query(default=10, ge=0, le=100),
) -> dict[str, object]:
    _ensure_macro_vendor_read_allowed(auth)
    settings = get_settings()
    return market_data_bond_futures_rankings_envelope(
        settings.duckdb_path,
        contract=contract,
        trade_date=trade_date,
        limit=limit,
    )


@router.get("/ui/market-data/coverage-summary")
def market_data_coverage_summary(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict[str, object]:
    _ensure_macro_vendor_read_allowed(auth)
    settings = get_settings()
    return market_data_coverage_summary_envelope(settings.duckdb_path)


@router.post("/ui/macro/choice-series/refresh")
def choice_series_refresh(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    backfill_days: int = Query(default=0, ge=0, le=90),
) -> dict[str, object]:
    settings = get_settings()
    try:
        ensure_user_allowed(
            auth=auth,
            settings=settings,
            resource="macro_vendor.choice_series",
            action="refresh",
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        # Scope-store unavailability is a service failure, not a denial
        # (same mapping as api/deps.py::ensure_read_allowed).
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    payload, refresh_succeeded = run_choice_macro_refresh(
        backfill_days=backfill_days,
        choice_refresh_task=refresh_choice_macro_snapshot,
        public_refresh_task=refresh_public_cross_asset_headlines,
        tushare_ncd_shibor_refresh_task=refresh_tushare_ncd_shibor_proxy,
    )
    if refresh_succeeded:
        market_home_response_cache.invalidate()
    return payload


@router.get("/ui/macro/choice-series/refresh-status")
def choice_series_refresh_status(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    run_id: str = Query(default=""),
) -> dict[str, object]:
    _ensure_macro_vendor_read_allowed(auth)
    settings = get_settings()
    try:
        return choice_macro_refresh_status(settings.governance_path, run_id=run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
