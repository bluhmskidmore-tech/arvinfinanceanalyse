from __future__ import annotations

from typing import Annotated

from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
from backend.app.services.market_data_ncd_proxy_service import ncd_funding_proxy_envelope
from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(prefix="/ui/market-data", tags=["market-data"])


def _ensure_ncd_proxy_read_allowed(auth: AuthContext) -> None:
    try:
        ensure_user_allowed(
            auth=auth,
            settings=get_settings(),
            resource="market_data_ncd_proxy",
            action="read",
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/ncd-funding-proxy")
def ncd_funding_proxy(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict[str, object]:
    _ensure_ncd_proxy_read_allowed(auth)
    return ncd_funding_proxy_envelope()
