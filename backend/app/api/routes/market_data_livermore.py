from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query

from backend.app.governance.settings import get_settings
from backend.app.services.market_data_livermore_service import livermore_strategy_envelope

router = APIRouter(prefix="/ui/market-data", tags=["market-data"])


@router.get("/livermore")
def livermore_strategy(as_of_date: str | None = Query(None)) -> dict[str, object]:
    if as_of_date is not None:
        try:
            date.fromisoformat(as_of_date)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid as_of_date. Expected YYYY-MM-DD.") from exc

    settings = get_settings()
    return livermore_strategy_envelope(
        duckdb_path=str(settings.duckdb_path),
        as_of_date=as_of_date,
    )
