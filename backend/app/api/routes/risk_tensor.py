from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query

from backend.app.governance.settings import get_settings
from backend.app.services.risk_tensor_service import risk_tensor_envelope

router = APIRouter(prefix="/api/risk", tags=["risk"])


@router.get("/tensor")
def risk_tensor(report_date: str = Query(...)) -> dict:
    try:
        date.fromisoformat(report_date)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid report_date. Expected YYYY-MM-DD.") from exc

    settings = get_settings()
    try:
        return risk_tensor_envelope(
            duckdb_path=str(settings.duckdb_path),
            governance_dir=str(settings.governance_path),
            report_date=report_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
