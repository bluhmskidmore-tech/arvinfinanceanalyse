from __future__ import annotations

from datetime import date
from typing import Annotated

from backend.app.api.deps import ensure_read_allowed
from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
from backend.app.services.cashflow_projection_service import get_cashflow_projection
from fastapi import APIRouter, Depends, HTTPException, Query

router = APIRouter(prefix="/api/cashflow-projection", tags=["cashflow-projection"])


@router.get("")
def cashflow_projection(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: str = Query(...),
) -> dict:
    _ensure_cashflow_projection_read_allowed(auth)
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


def _ensure_cashflow_projection_read_allowed(auth: AuthContext) -> None:
    ensure_read_allowed(auth, "cashflow_projection", settings=get_settings(), authorize=ensure_user_allowed)
