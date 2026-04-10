from fastapi import APIRouter, HTTPException, Query

from backend.app.governance.settings import get_settings
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


def _validate_source_family(source_family: str) -> str:
    normalized = str(source_family)
    if normalized not in SUPPORTED_PREVIEW_SOURCE_FAMILIES:
        raise HTTPException(status_code=400, detail=f"Unsupported source_family: {source_family}")
    return normalized


@router.get("/source-foundation")
def source_foundation() -> dict[str, object]:
    settings = get_settings()
    return source_preview_envelope(settings.duckdb_path)


@router.get("/source-foundation/history")
def source_foundation_history(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    source_family: str | None = None,
) -> dict[str, object]:
    settings = get_settings()
    normalized_family = (
        _validate_source_family(source_family) if source_family is not None else None
    )
    return source_preview_history_envelope(
        duckdb_path=settings.duckdb_path,
        limit=limit,
        offset=offset,
        source_family=normalized_family,
    )


@router.post("/source-foundation/refresh")
def refresh() -> dict[str, object]:
    try:
        return refresh_source_preview(get_settings())
    except SourcePreviewRefreshConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except SourcePreviewRefreshServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/source-foundation/refresh-status")
def refresh_status(run_id: str | None = Query(default=None)) -> dict[str, object]:
    try:
        return source_preview_refresh_status(get_settings(), run_id=run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/source-foundation/{source_family}/rows")
def source_rows(
    source_family: str,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    ingest_batch_id: str | None = None,
) -> dict[str, object]:
    settings = get_settings()
    normalized_family = _validate_source_family(source_family)
    return preview_rows_envelope(
        duckdb_path=settings.duckdb_path,
        source_family=normalized_family,
        limit=limit,
        offset=offset,
        ingest_batch_id=ingest_batch_id,
    )


@router.get("/source-foundation/{source_family}/traces")
def source_traces(
    source_family: str,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    ingest_batch_id: str | None = None,
) -> dict[str, object]:
    settings = get_settings()
    normalized_family = _validate_source_family(source_family)
    return preview_traces_envelope(
        duckdb_path=settings.duckdb_path,
        source_family=normalized_family,
        limit=limit,
        offset=offset,
        ingest_batch_id=ingest_batch_id,
    )
