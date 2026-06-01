from typing import Annotated

from backend.app.api.perf_logging import timed_api_call
from backend.app.governance.settings import get_settings
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    GovernanceRepository,
)
from backend.app.schemas.macro_vendor import ChoiceMacroRefreshTier
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
from backend.app.services.macro_vendor_service import (
    choice_macro_formal_envelope,
    choice_macro_latest_envelope,
    fx_analytical_envelope,
    fx_formal_status_envelope,
    macro_foundation_formal_envelope,
    macro_vendor_envelope,
)
from backend.app.tasks.choice_macro import (
    refresh_choice_macro_snapshot,
    refresh_public_cross_asset_headlines,
)
from fastapi import APIRouter, Depends, HTTPException, Query

router = APIRouter()

CHOICE_MACRO_REFRESH_JOB_NAME = "choice_macro_refresh"
CHOICE_MACRO_REFRESH_CACHE_KEY = "choice_macro.latest"


# ── Formal market-data endpoints (Phase 1 promotion) ───────────────

@router.get("/ui/market-data/rates")
def market_data_rates() -> dict[str, object]:
    """Formal-basis rates for the market-data page (stable series only)."""
    settings = get_settings()
    return timed_api_call(
        "/ui/market-data/rates",
        lambda: choice_macro_formal_envelope(settings.duckdb_path),
    )


@router.get("/ui/market-data/catalog")
def market_data_catalog() -> dict[str, object]:
    """Formal-basis macro catalog for the market-data page."""
    settings = get_settings()
    return macro_foundation_formal_envelope(settings.duckdb_path)


# ── Analytical / preview endpoints (unlocked from 503) ─────────────

@router.get("/ui/preview/macro-foundation")
def macro_foundation() -> dict[str, object]:
    settings = get_settings()
    return macro_vendor_envelope(settings.duckdb_path)


@router.get("/ui/macro/choice-series/latest")
def choice_series_latest(category: ChoiceMacroRefreshTier | None = None) -> dict[str, object]:
    settings = get_settings()
    return choice_macro_latest_envelope(settings.duckdb_path, category=category)


@router.get("/ui/market-data/fx/formal-status")
def fx_formal_status() -> dict[str, object]:
    settings = get_settings()
    return fx_formal_status_envelope(settings.duckdb_path)


@router.get("/ui/market-data/fx/analytical")
def fx_analytical() -> dict[str, object]:
    settings = get_settings()
    return fx_analytical_envelope(settings.duckdb_path)


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
    choice_payload = choice_refresh(backfill_days=backfill_days)
    public_payload = _run_public_cross_asset_headline_refresh()
    return _merge_choice_and_public_refresh_payloads(choice_payload, public_payload)


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


def _merge_choice_and_public_refresh_payloads(
    choice_payload: dict[str, object],
    public_payload: dict[str, object],
) -> dict[str, object]:
    warnings: list[str] = []
    for payload in (choice_payload, public_payload):
        payload_warnings = payload.get("warnings")
        if isinstance(payload_warnings, list):
            warnings.extend(str(item) for item in payload_warnings if str(item).strip())

    return {
        **choice_payload,
        "choice_macro": choice_payload,
        "public_cross_asset": public_payload,
        "warnings": warnings,
    }


@router.get("/ui/macro/choice-series/refresh-status")
def choice_series_refresh_status(
    run_id: str = Query(default=""),
) -> dict[str, object]:
    settings = get_settings()
    records = [
        record
        for record in GovernanceRepository(base_dir=settings.governance_path).read_all(CACHE_BUILD_RUN_STREAM)
        if str(record.get("job_name")) == CHOICE_MACRO_REFRESH_JOB_NAME
        and str(record.get("cache_key")) == CHOICE_MACRO_REFRESH_CACHE_KEY
    ]
    if run_id:
        records = [record for record in records if str(record.get("run_id")) == run_id]
        if not records:
            raise HTTPException(status_code=404, detail=f"Unknown choice macro refresh run_id={run_id}")
    if not records:
        return {
            "status": "idle",
            "job_name": CHOICE_MACRO_REFRESH_JOB_NAME,
            "cache_key": CHOICE_MACRO_REFRESH_CACHE_KEY,
            "trigger_mode": "idle",
        }
    latest = records[-1]
    status = str(latest.get("status", "unknown"))
    return {
        **latest,
        "trigger_mode": "async" if status in {"queued", "running"} else "terminal",
    }
