from __future__ import annotations

from datetime import date
from typing import Annotated

from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
from backend.app.services.risk_tensor_service import (
    risk_tensor_dates_envelope,
    risk_tensor_envelope,
)
from fastapi import APIRouter, Depends, HTTPException, Query

router = APIRouter(prefix="/api/risk", tags=["risk"])


def _ensure_risk_tensor_read_allowed(auth: AuthContext, settings) -> None:
    try:
        ensure_user_allowed(
            auth=auth,
            settings=settings,
            resource="risk_tensor",
            action="read",
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/tensor/dates")
def risk_tensor_dates(auth: Annotated[AuthContext, Depends(get_auth_context)]) -> dict:
    settings = get_settings()
    _ensure_risk_tensor_read_allowed(auth, settings)
    try:
        return risk_tensor_dates_envelope(
            duckdb_path=str(settings.duckdb_path),
            governance_dir=str(settings.governance_path),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/tensor")
def risk_tensor(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: str = Query(...),
) -> dict:
    try:
        date.fromisoformat(report_date)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid report_date. Expected YYYY-MM-DD.") from exc

    settings = get_settings()
    _ensure_risk_tensor_read_allowed(auth, settings)
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
