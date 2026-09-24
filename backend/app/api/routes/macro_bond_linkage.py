from __future__ import annotations

from datetime import date
from typing import Annotated

from backend.app.api.deps import ensure_read_allowed
from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
from backend.app.services.macro_bond_linkage_service import get_macro_bond_linkage
from fastapi import APIRouter, Depends, Query

router = APIRouter(prefix="/api/macro-bond-linkage", tags=["macro-analysis"])


def _ensure_macro_bond_linkage_read_allowed(auth: AuthContext) -> None:
    ensure_read_allowed(auth, "macro_bond_linkage", settings=get_settings(), authorize=ensure_user_allowed)


@router.get("/analysis")
def macro_bond_analysis(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: date = Query(...),
) -> dict[str, object]:
    _ensure_macro_bond_linkage_read_allowed(auth)
    return get_macro_bond_linkage(report_date)
