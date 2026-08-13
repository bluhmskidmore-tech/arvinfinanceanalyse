"""盘前操作清单只读路由（今天开盘我该做什么，观察面）。"""
from __future__ import annotations

from typing import Annotated

from backend.app.api.deps import ensure_read_allowed
from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
from backend.app.services.pretrade_checklist_service import pretrade_checklist_envelope
from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(prefix="/api/pretrade-checklist", tags=["pretrade-checklist"])


def _ensure_pretrade_checklist_read_allowed(auth: AuthContext) -> None:
    ensure_read_allowed(auth, "pretrade_checklist", settings=get_settings(), authorize=ensure_user_allowed)


@router.get("")
def pretrade_checklist(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict[str, object]:
    _ensure_pretrade_checklist_read_allowed(auth)
    envelope = pretrade_checklist_envelope()
    if envelope is None:
        raise HTTPException(status_code=404, detail="Pretrade checklist is not available.")
    return envelope
