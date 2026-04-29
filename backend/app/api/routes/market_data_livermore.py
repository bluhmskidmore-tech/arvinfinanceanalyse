from __future__ import annotations

from datetime import date

from backend.app.governance.settings import get_settings
from backend.app.repositories.choice_stock_adapter import load_choice_stock_readiness
from backend.app.services.market_data_livermore_service import livermore_strategy_envelope
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/ui/market-data", tags=["market-data"])


@router.get("/livermore")
def livermore_strategy(as_of_date: str | None = Query(None)) -> dict[str, object]:
    if as_of_date is not None:
        try:
            date.fromisoformat(as_of_date)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid as_of_date. Expected YYYY-MM-DD.") from exc

    settings = get_settings()
    stock_readiness = load_choice_stock_readiness(settings.choice_stock_catalog_file)
    return livermore_strategy_envelope(
        duckdb_path=str(settings.duckdb_path),
        as_of_date=as_of_date,
        stock_readiness=stock_readiness,
    )
