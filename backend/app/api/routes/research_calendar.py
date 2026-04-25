from __future__ import annotations

from datetime import date

from backend.app.governance.settings import get_settings
from backend.app.services.research_calendar_service import (
    supply_auction_calendar_envelope,
)
from fastapi import APIRouter, Query

router = APIRouter(prefix="/ui/calendar", tags=["calendar"])


@router.get("/supply-auctions")
def supply_auctions(
    start_date: date | None = Query(default=None, description="Inclusive event start date"),
    end_date: date | None = Query(default=None, description="Inclusive event end date"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    settings = get_settings()
    return supply_auction_calendar_envelope(
        str(settings.duckdb_path),
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )
