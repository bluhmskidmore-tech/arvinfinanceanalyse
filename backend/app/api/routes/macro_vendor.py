from fastapi import APIRouter, HTTPException, Query

from backend.app.governance.settings import get_settings
from backend.app.services.macro_vendor_service import (
    ChoiceMacroRefreshServiceError,
    choice_macro_refresh_status,
    choice_macro_latest_envelope,
    fx_analytical_envelope,
    fx_formal_status_envelope,
    macro_vendor_envelope,
    queue_choice_macro_refresh,
)

router = APIRouter()


@router.get("/ui/preview/macro-foundation")
def macro_foundation() -> dict[str, object]:
    settings = get_settings()
    return macro_vendor_envelope(settings.duckdb_path)


@router.get("/ui/macro/choice-series/latest")
def choice_series_latest() -> dict[str, object]:
    settings = get_settings()
    return choice_macro_latest_envelope(settings.duckdb_path)


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
    backfill_days: int = Query(default=0, ge=0, le=90),
) -> dict[str, object]:
    settings = get_settings()
    try:
        return queue_choice_macro_refresh(settings, backfill_days=backfill_days)
    except ChoiceMacroRefreshServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/ui/macro/choice-series/refresh-status")
def choice_series_refresh_status(
    run_id: str = Query(default=""),
) -> dict[str, object]:
    settings = get_settings()
    return choice_macro_refresh_status(settings, run_id=run_id)
