from __future__ import annotations

from datetime import date

from backend.app.governance.settings import get_settings
from backend.app.repositories.choice_stock_adapter import load_choice_stock_readiness
from backend.app.services.livermore_gate_supplement_compute_service import (
    compute_and_materialize_gate_supplement,
)
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


@router.post("/livermore/refresh-gate-supplement")
def refresh_gate_supplement(
    as_of_date: str | None = Query(None),
    lookback_days: int = Query(default=30, ge=7, le=365),
) -> dict[str, object]:
    """Compute and write breadth_5d + limit_up_quality_ok from landed CSI300 data."""
    parsed_date: date | None = None
    if as_of_date is not None:
        try:
            parsed_date = date.fromisoformat(as_of_date)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid as_of_date. Expected YYYY-MM-DD.") from exc

    settings = get_settings()
    try:
        result = compute_and_materialize_gate_supplement(
            duckdb_path=str(settings.duckdb_path),
            as_of_date=parsed_date,
            lookback_days=lookback_days,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return result
