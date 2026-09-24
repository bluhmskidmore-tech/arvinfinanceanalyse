"""策略验证报告只读路由(walk-forward 样本外验证展示面)。"""
from __future__ import annotations

from typing import Annotated

from backend.app.api.deps import ensure_read_allowed
from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
from backend.app.services.strategy_report_service import walk_forward_summary_envelope
from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(prefix="/api/strategy-reports", tags=["strategy-reports"])


def _ensure_strategy_reports_read_allowed(auth: AuthContext) -> None:
    ensure_read_allowed(
        auth,
        "strategy_reports",
        settings=get_settings(),
        allow_dev_fallback=True,
        authorize=ensure_user_allowed,
    )


@router.get("/walk-forward")
def walk_forward_report(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict[str, object]:
    _ensure_strategy_reports_read_allowed(auth)
    envelope = walk_forward_summary_envelope()
    if envelope is None:
        raise HTTPException(status_code=404, detail="Walk-forward validation report is not available.")
    return envelope
