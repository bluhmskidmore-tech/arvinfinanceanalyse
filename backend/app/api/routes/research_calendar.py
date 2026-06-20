from __future__ import annotations

from datetime import date
from typing import Annotated

from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
from backend.app.services.research_calendar_service import (
    supply_auction_calendar_envelope,
)
from fastapi import APIRouter, Depends, HTTPException, Query

router = APIRouter(prefix="/ui/calendar", tags=["calendar"])


def _ensure_research_calendar_read_allowed(auth: AuthContext) -> None:
    try:
        ensure_user_allowed(
            auth=auth,
            settings=get_settings(),
            resource="research_calendar",
            action="read",
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/supply-auctions")
def supply_auctions(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    start_date: date | None = Query(default=None, description="Inclusive event start date"),
    end_date: date | None = Query(default=None, description="Inclusive event end date"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    _ensure_research_calendar_read_allowed(auth)
    settings = get_settings()
    return supply_auction_calendar_envelope(
        str(settings.duckdb_path),
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )
