from fastapi import APIRouter, Query
from fastapi import HTTPException

from backend.app.governance.settings import get_settings
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    GovernanceRepository,
)
from backend.app.services.macro_vendor_service import (
    choice_macro_latest_envelope,
    fx_analytical_envelope,
    fx_formal_status_envelope,
    macro_vendor_envelope,
)
from backend.app.tasks.choice_macro import refresh_choice_macro_snapshot

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
    try:
        return refresh_choice_macro_snapshot.fn(backfill_days=backfill_days)
    except RuntimeError as exc:
        error_text = str(exc)
        normalized_error = error_text.lower()
        if "no access for this api" in normalized_error:
            raise HTTPException(
                status_code=424,
                detail="Choice API permission denied for current account. Refresh cannot run until API entitlement is enabled.",
            ) from exc
        raise


@router.get("/ui/macro/choice-series/refresh-status")
def choice_series_refresh_status(
    run_id: str = Query(default=""),
) -> dict[str, object]:
    settings = get_settings()
    repo = GovernanceRepository(base_dir=settings.governance_path)
    records = repo.read_all(CACHE_BUILD_RUN_STREAM)
    macro_records = [
        r for r in records if r.get("job_name") == "choice_macro_refresh"
    ]
    if run_id:
        macro_records = [r for r in macro_records if r.get("run_id") == run_id]
    if not macro_records:
        return {"status": "unknown", "run_id": run_id}
    latest = macro_records[-1]
    return {
        "status": str(latest.get("status", "unknown")),
        "run_id": str(latest.get("run_id", "")),
        "error_message": latest.get("error_message"),
    }
