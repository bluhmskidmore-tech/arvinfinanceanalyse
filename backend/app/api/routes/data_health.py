"""数据健康总览只读路由（系统级体温计，观察面）。"""
from __future__ import annotations

from typing import Annotated

from backend.app.api.deps import ensure_read_allowed
from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
from backend.app.services.data_health_service import data_health_envelope
from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(prefix="/api/data-health", tags=["data-health"])


def _ensure_data_health_read_allowed(auth: AuthContext) -> None:
    ensure_read_allowed(
        auth,
        "data_health",
        settings=get_settings(),
        allow_dev_fallback=True,
        authorize=ensure_user_allowed,
    )


@router.get("")
def data_health_overview(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict[str, object]:
    _ensure_data_health_read_allowed(auth)
    envelope = data_health_envelope()
    if envelope is None:
        raise HTTPException(status_code=404, detail="Data health overview is not available.")
    return envelope
