from __future__ import annotations

from typing import Annotated

from backend.app.api.deps import ensure_read_allowed
from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
from backend.app.services.market_data_ncd_proxy_service import ncd_funding_proxy_envelope
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/ui/market-data", tags=["market-data"])


def _ensure_ncd_proxy_read_allowed(auth: AuthContext) -> None:
    ensure_read_allowed(auth, "market_data_ncd_proxy", settings=get_settings(), authorize=ensure_user_allowed)


@router.get("/ncd-funding-proxy")
def ncd_funding_proxy(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict[str, object]:
    _ensure_ncd_proxy_read_allowed(auth)
    return ncd_funding_proxy_envelope()
