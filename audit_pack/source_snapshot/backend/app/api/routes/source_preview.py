from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import AuthContext, get_auth_context
from backend.app.services.source_preview_refresh_service import (
    SourcePreviewRefreshConflictError,
    SourcePreviewRefreshServiceError,
    refresh_source_preview,
    source_preview_refresh_status,
)
from backend.app.services.source_preview_service import (
    source_preview_history_envelope,
    preview_rows_envelope,
    preview_traces_envelope,
    source_preview_envelope,
    SUPPORTED_PREVIEW_SOURCE_FAMILIES,
)

router = APIRouter(prefix="/ui/preview")


def _raise_source_preview_reserved_surface() -> None:
    raise HTTPException(
        status_code=503,
        detail="Source preview surfaces are reserved by the current boundary.",
    )


def _validate_source_family(source_family: str) -> str:
    normalized = str(source_family)
    if normalized not in SUPPORTED_PREVIEW_SOURCE_FAMILIES:
        raise HTTPException(status_code=400, detail=f"Unsupported source_family: {source_family}")
    return normalized


@router.get("/source-foundation")
def source_foundation() -> dict[str, object]:
    _raise_source_preview_reserved_surface()


@router.get("/source-foundation/history")
def source_foundation_history(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    source_family: str | None = None,
) -> dict[str, object]:
    _raise_source_preview_reserved_surface()


@router.post("/source-foundation/refresh")
def refresh(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict[str, object]:
    _raise_source_preview_reserved_surface()


@router.get("/source-foundation/refresh-status")
def refresh_status(run_id: str | None = Query(default=None)) -> dict[str, object]:
    _raise_source_preview_reserved_surface()


@router.get("/source-foundation/{source_family}/rows")
def source_rows(
    source_family: str,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    ingest_batch_id: str | None = None,
) -> dict[str, object]:
    _raise_source_preview_reserved_surface()


@router.get("/source-foundation/{source_family}/traces")
def source_traces(
    source_family: str,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    ingest_batch_id: str | None = None,
) -> dict[str, object]:
    _raise_source_preview_reserved_surface()
