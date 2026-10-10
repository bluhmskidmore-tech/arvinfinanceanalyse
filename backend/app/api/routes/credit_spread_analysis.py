from __future__ import annotations

from datetime import date
from typing import Annotated

from backend.app.api.deps import ensure_read_allowed
from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
from backend.app.services.credit_spread_analysis_service import get_credit_spread_analysis
from fastapi import APIRouter, Depends, Query

router = APIRouter(prefix="/api/credit-spread-analysis", tags=["credit-spread"])


def _ensure_credit_spread_analysis_read_allowed(auth: AuthContext) -> None:
    ensure_read_allowed(auth, "credit_spread_analysis", settings=get_settings(), authorize=ensure_user_allowed)


@router.get("/detail")
def credit_spread_detail(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: date = Query(...),
):
    _ensure_credit_spread_analysis_read_allowed(auth)
    return get_credit_spread_analysis(report_date)
