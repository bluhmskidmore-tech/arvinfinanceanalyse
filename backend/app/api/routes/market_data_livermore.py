from __future__ import annotations

from datetime import date

from backend.app.governance.settings import get_settings
from backend.app.repositories.choice_stock_adapter import load_choice_stock_readiness
from backend.app.services.market_data_livermore_service import livermore_strategy_envelope
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/ui/market-data", tags=["market-data"])


def _raise_livermore_reserved_surface() -> None:
    raise HTTPException(
        status_code=503,
        detail="Livermore analytical surface is reserved by the current boundary and is not available in this wave.",
    )


@router.get("/livermore")
def livermore_strategy(as_of_date: str | None = Query(None)) -> dict[str, object]:
    _raise_livermore_reserved_surface()
