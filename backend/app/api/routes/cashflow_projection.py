from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query

from backend.app.services.cashflow_projection_service import get_cashflow_projection

router = APIRouter(prefix="/api/cashflow-projection", tags=["cashflow-projection"])


@router.get("")
def cashflow_projection(report_date: str = Query(...)) -> dict:
    try:
        report_date_value = date.fromisoformat(report_date)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid report_date. Expected YYYY-MM-DD.") from exc

    try:
        return get_cashflow_projection(report_date_value)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
