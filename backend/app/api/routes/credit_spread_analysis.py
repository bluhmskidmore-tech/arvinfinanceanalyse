from __future__ import annotations

from datetime import date
from typing import Annotated

from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
from backend.app.services.credit_spread_analysis_service import get_credit_spread_analysis
from fastapi import APIRouter, Depends, HTTPException, Query

router = APIRouter(prefix="/api/credit-spread-analysis", tags=["credit-spread"])


def _ensure_credit_spread_analysis_read_allowed(auth: AuthContext) -> None:
    try:
        ensure_user_allowed(
            auth=auth,
            settings=get_settings(),
            resource="credit_spread_analysis",
            action="read",
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/detail")
def credit_spread_detail(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: date = Query(...),
):
    _ensure_credit_spread_analysis_read_allowed(auth)
    return get_credit_spread_analysis(report_date)
