from __future__ import annotations

from typing import Annotated

from backend.app.api.deps import ensure_read_allowed
from backend.app.governance.settings import Settings, get_settings
from backend.app.repositories.system_read_publication_repo import current_system_read_context
from backend.app.security.auth_context import AuthContext, get_auth_context
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/system-read-publication", tags=["system-read-publication"])


class SystemReadPublicationStatus(BaseModel):
    enabled: bool
    generation: str | None = None
    coverage_dates: dict[str, list[str]] = Field(default_factory=dict)


@router.get("", response_model=SystemReadPublicationStatus)
def system_read_publication_status(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    settings: Settings = Depends(get_settings),
) -> SystemReadPublicationStatus:
    ensure_read_allowed(auth, "data_health", settings=settings, allow_dev_fallback=True)
    if not settings.system_read_publication_enabled:
        return SystemReadPublicationStatus(enabled=False)

    context = current_system_read_context()
    if context is None:
        raise HTTPException(
            status_code=503,
            detail="A valid system read publication is unavailable.",
        )
    return SystemReadPublicationStatus(
        enabled=True,
        generation=context.generation,
        coverage_dates={name: list(dates) for name, dates in context.coverage_dates.items()},
    )
