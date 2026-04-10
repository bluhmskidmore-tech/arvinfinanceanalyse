from fastapi import APIRouter

from backend.app.governance.settings import get_settings
from backend.app.services.macro_vendor_service import (
    choice_macro_latest_envelope,
    macro_vendor_envelope,
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
