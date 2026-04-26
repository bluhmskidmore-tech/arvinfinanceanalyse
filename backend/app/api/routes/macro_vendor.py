from backend.app.governance.settings import get_settings
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    GovernanceRepository,
)
from backend.app.schemas.macro_vendor import ChoiceMacroRefreshTier
from backend.app.services.macro_vendor_service import (
    choice_macro_latest_envelope,
    fx_analytical_envelope,
    fx_formal_status_envelope,
    macro_vendor_envelope,
)
from backend.app.tasks.choice_macro import (
    refresh_choice_macro_snapshot,
    refresh_public_cross_asset_headlines,
)
from fastapi import APIRouter, HTTPException, Query

router = APIRouter()

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
    backfill_days: int = Query(default=0, ge=0, le=90),
) -> dict[str, object]:
    try:
        choice_payload = refresh_choice_macro_snapshot.fn(backfill_days=backfill_days)
    except RuntimeError as exc:
        error_text = str(exc)
        normalized_error = error_text.lower()
        if "no access for this api" in normalized_error:
            raise HTTPException(
                status_code=424,
                detail="Choice API permission denied for current account. Refresh cannot run until API entitlement is enabled.",
            ) from exc
        raise
    public_payload = _run_public_cross_asset_headline_refresh()
    return _merge_choice_and_public_refresh_payloads(choice_payload, public_payload)


def _run_public_cross_asset_headline_refresh() -> dict[str, object]:
    try:
        return refresh_public_cross_asset_headlines()
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
