"""团队绩效考核底稿只读路由（2025 静态工作簿，非正式绩效口径）。"""
from __future__ import annotations

from typing import Annotated

from backend.app.api.deps import ensure_read_allowed
from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
from backend.app.services.team_performance_service import assessment_workbook_envelope
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/api/team-performance", tags=["team-performance"])


def _ensure_team_performance_read_allowed(auth: AuthContext) -> None:
    ensure_read_allowed(
        auth,
        "team_performance",
        settings=get_settings(),
        allow_dev_fallback=True,
        authorize=ensure_user_allowed,
    )


@router.get("/assessment-workbook")
def assessment_workbook(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict[str, object]:
    _ensure_team_performance_read_allowed(auth)
    return assessment_workbook_envelope()
