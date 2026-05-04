from typing import Annotated

from backend.app.governance.settings import get_settings
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    GovernanceRepository,
)
from backend.app.schemas.macro_vendor import ChoiceMacroRefreshTier
from backend.app.security.auth_context import AuthContext, get_auth_context
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
from fastapi import APIRouter, Depends, HTTPException, Query

router = APIRouter()


def _raise_macro_vendor_reserved_surface() -> None:
    raise HTTPException(
        status_code=503,
        detail="Macro vendor and market-data analytical surfaces are reserved by the current boundary.",
    )

@router.get("/ui/preview/macro-foundation")
def macro_foundation() -> dict[str, object]:
    _raise_macro_vendor_reserved_surface()


@router.get("/ui/macro/choice-series/latest")
def choice_series_latest(category: ChoiceMacroRefreshTier | None = None) -> dict[str, object]:
    _raise_macro_vendor_reserved_surface()


@router.get("/ui/market-data/fx/formal-status")
def fx_formal_status() -> dict[str, object]:
    _raise_macro_vendor_reserved_surface()


@router.get("/ui/market-data/fx/analytical")
def fx_analytical() -> dict[str, object]:
    _raise_macro_vendor_reserved_surface()


@router.post("/ui/macro/choice-series/refresh")
def choice_series_refresh(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    backfill_days: int = Query(default=0, ge=0, le=90),
) -> dict[str, object]:
    _raise_macro_vendor_reserved_surface()


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
    _raise_macro_vendor_reserved_surface()
