from typing import Annotated

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
from backend.app.tasks.choice_macro import (
    refresh_choice_macro_snapshot,
    refresh_public_cross_asset_headlines,
    refresh_tushare_ncd_shibor_proxy,
)
from fastapi import APIRouter, Depends, HTTPException, Query

router = APIRouter()


def _ensure_macro_vendor_read_allowed(auth: AuthContext) -> None:
    try:
        ensure_user_allowed(
            auth=auth,
            settings=get_settings(),
            resource="macro_vendor",
            action="read",
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


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
    choice_refresh = getattr(refresh_choice_macro_snapshot, "fn", refresh_choice_macro_snapshot)
    try:
        choice_payload = choice_refresh(backfill_days=backfill_days)
    except RuntimeError as exc:
        choice_payload = _choice_macro_refresh_failure_payload(exc)
    public_payload = _run_public_cross_asset_headline_refresh()
    tushare_ncd_shibor_payload = None
    if str(choice_payload.get("status") or "") == "failed":
        tushare_ncd_shibor_payload = _run_tushare_ncd_shibor_refresh()
    # Fresh upstream snapshot just landed; drop cached market reads so the next
    # page load reflects it instead of waiting out the TTL.
    if _refresh_payload_succeeded(choice_payload, public_payload, tushare_ncd_shibor_payload):
        market_home_response_cache.invalidate()
    return _merge_choice_and_public_refresh_payloads(choice_payload, public_payload, tushare_ncd_shibor_payload)


def _choice_macro_refresh_failure_payload(exc: RuntimeError) -> dict[str, object]:
    error_text = str(exc) or exc.__class__.__name__
    return {
        "status": "failed",
        "error_message": error_text,
        "warnings": [f"Choice macro refresh failed: {error_text}"],
    }


def _run_public_cross_asset_headline_refresh() -> dict[str, object]:
    try:
        public_refresh = getattr(refresh_public_cross_asset_headlines, "fn", refresh_public_cross_asset_headlines)
        return public_refresh()
    except RuntimeError as exc:
        error_text = str(exc)
        return {
            "status": "failed",
            "error_message": error_text,
            "warnings": [f"public_cross_asset refresh failed: {error_text}"],
        }


def _run_tushare_ncd_shibor_refresh() -> dict[str, object]:
    try:
        tushare_refresh = getattr(refresh_tushare_ncd_shibor_proxy, "fn", refresh_tushare_ncd_shibor_proxy)
        return tushare_refresh()
    except RuntimeError as exc:
        error_text = str(exc)
        return {
            "status": "failed",
            "error_message": error_text,
            "warnings": [f"tushare_ncd_shibor refresh failed: {error_text}"],
        }


def _refresh_payload_succeeded(*payloads: dict[str, object] | None) -> bool:
    # "degraded" means data was written successfully but a non-fatal warning was
    # raised (see backend/app/tasks/choice_macro.py); it must count as a success
    # so the response cache is invalidated and the refreshed data is served.
    return any(
        str(payload.get("status") or "") in {"completed", "partial", "degraded"} for payload in payloads if payload
    )


def _format_refresh_warning(item: object) -> str:
    # Task-level warnings (backend/app/tasks/choice_macro.py) are structured
    # {"code", "message"} dicts; flatten them to "code: message" instead of the
    # raw dict repr so the merged top-level warnings list is display-ready.
    if isinstance(item, dict):
        code = str(item.get("code") or "").strip()
        message = str(item.get("message") or "").strip()
        if code and message:
            return f"{code}: {message}"
        return code or message
    return str(item).strip()


def _merge_choice_and_public_refresh_payloads(
    choice_payload: dict[str, object],
    public_payload: dict[str, object],
    tushare_ncd_shibor_payload: dict[str, object] | None = None,
) -> dict[str, object]:
    warnings: list[str] = []
    backup_payloads = [public_payload]
    if tushare_ncd_shibor_payload is not None:
        backup_payloads.append(tushare_ncd_shibor_payload)
    for payload in (choice_payload, *backup_payloads):
        payload_warnings = payload.get("warnings")
        if isinstance(payload_warnings, list):
            warnings.extend(
                text for text in (_format_refresh_warning(item) for item in payload_warnings) if text
            )

    result = {
        **choice_payload,
        "choice_macro": choice_payload,
        "public_cross_asset": public_payload,
        "warnings": warnings,
    }
    if tushare_ncd_shibor_payload is not None:
        result["tushare_ncd_shibor"] = tushare_ncd_shibor_payload
    if str(choice_payload.get("status") or "") == "failed":
        backup_succeeded = _refresh_payload_succeeded(*backup_payloads)
        result["status"] = "partial" if backup_succeeded else "failed"
        if backup_succeeded and not result.get("run_id"):
            result["run_id"] = next(
                (
                    payload.get("run_id")
                    for payload in backup_payloads
                    if str(payload.get("status") or "") == "completed" and payload.get("run_id")
                ),
                None,
            )
    return result


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
