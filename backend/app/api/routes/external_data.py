"""HTTP routes for external-data catalog (M1 — read-only directory) + M2b series data."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from backend.app.api.deps import ensure_read_allowed
from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
from backend.app.services.external_data_service import default_service
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder

router = APIRouter(prefix="/api/external-data", tags=["external-data"])

DomainParam = Literal["macro", "news", "yield_curve", "fx", "other"]


def _ensure_external_data_read_allowed(auth: AuthContext) -> None:
    ensure_read_allowed(auth, "external_data", settings=get_settings(), authorize=ensure_user_allowed)


@router.get("/catalog")
def list_catalog(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> list[dict[str, object]]:
    _ensure_external_data_read_allowed(auth)
    svc = default_service()
    return [e.model_dump() for e in svc.list_catalog()]


@router.get("/watermarks")
def get_watermark_ledger(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict[str, object]:
    _ensure_external_data_read_allowed(auth)
    svc = default_service()
    return svc.get_watermark_ledger().model_dump()


@router.get("/catalog/{series_id}")
def get_catalog_entry(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    series_id: str,
) -> dict[str, object]:
    _ensure_external_data_read_allowed(auth)
    svc = default_service()
    entry = svc.get_catalog_entry(series_id.strip())
    if entry is None:
        raise HTTPException(status_code=404, detail="series_id not found")
    return entry.model_dump()


@router.get("/catalog/by-domain/{domain}")
def list_catalog_by_domain(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    domain: DomainParam,
) -> list[dict[str, object]]:
    _ensure_external_data_read_allowed(auth)
    svc = default_service()
    return [e.model_dump() for e in svc.list_by_domain(domain)]


def _json_safe_row(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in row.items():
        if isinstance(v, (datetime, date)):
            out[k] = v.isoformat()
        elif isinstance(v, Decimal):
            out[k] = str(v)
        else:
            out[k] = v
    return out


@router.get("/series/{series_id}/data")
def get_series_data(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    series_id: str,
    limit: int = Query(100, ge=1, le=10_000),
    offset: int = Query(0, ge=0),
) -> dict[str, object]:
    _ensure_external_data_read_allowed(auth)
    svc = default_service()
    page = svc.get_series_data_page(series_id.strip(), limit=limit, offset=offset)
    if page is None:
        raise HTTPException(status_code=404, detail="series_id not found")
    return jsonable_encoder(
        {
            "series_id": series_id,
            "table_name": page.table_name,
            "limit": page.limit,
            "offset": page.offset,
            "count": len(page.rows),
            "rows": [_json_safe_row(r) for r in page.rows],
        },
    )


@router.get("/series/{series_id}/data/recent")
def get_series_data_recent(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    series_id: str,
    days: int = Query(30, ge=1, le=3650),
    limit: int = Query(10_000, ge=1, le=50_000),
) -> dict[str, object]:
    _ensure_external_data_read_allowed(auth)
    svc = default_service()
    page = svc.get_series_data_recent(series_id.strip(), days=days, limit=limit)
    if page is None:
        raise HTTPException(status_code=404, detail="series_id not found")
    return jsonable_encoder(
        {
            "series_id": series_id,
            "table_name": page.table_name,
            "days": days,
            "count": len(page.rows),
            "rows": [_json_safe_row(r) for r in page.rows],
        },
    )
