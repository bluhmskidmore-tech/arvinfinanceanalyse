from __future__ import annotations

from datetime import date
from typing import Annotated

from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
from backend.app.services.macro_bond_linkage_service import get_macro_bond_linkage
from fastapi import APIRouter, Depends, HTTPException, Query

router = APIRouter(prefix="/api/macro-bond-linkage", tags=["macro-analysis"])


def _ensure_macro_bond_linkage_read_allowed(auth: AuthContext) -> None:
    try:
        ensure_user_allowed(
            auth=auth,
            settings=get_settings(),
            resource="macro_bond_linkage",
            action="read",
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/analysis")
def macro_bond_analysis(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: date = Query(...),
) -> dict[str, object]:
    _ensure_macro_bond_linkage_read_allowed(auth)
    return get_macro_bond_linkage(report_date)
