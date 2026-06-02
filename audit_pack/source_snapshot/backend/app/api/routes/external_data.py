"""HTTP routes for external-data catalog (M1 — read-only directory) + M2b series data."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

import duckdb
from backend.app.governance.settings import get_settings
from backend.app.repositories.external_data_catalog_repo import ExternalDataCatalogRepository
from backend.app.services.external_data_query_service import (
    fetch_series_data_page,
    fetch_series_data_recent,
)
from backend.app.services.external_data_service import default_service
from fastapi import APIRouter, HTTPException, Query
from fastapi.encoders import jsonable_encoder

router = APIRouter(prefix="/api/external-data", tags=["external-data"])

DomainParam = Literal["macro", "news", "yield_curve", "fx", "other"]


@router.get("/catalog")
def list_catalog() -> list[dict[str, object]]:
    svc = default_service()
    return [e.model_dump() for e in svc.list_catalog()]


@router.get("/catalog/{series_id}")
def get_catalog_entry(series_id: str) -> dict[str, object]:
    svc = default_service()
    entry = svc.get_catalog_entry(series_id.strip())
    if entry is None:
        raise HTTPException(status_code=404, detail="series_id not found")
    return entry.model_dump()


@router.get("/catalog/by-domain/{domain}")
def list_catalog_by_domain(domain: DomainParam) -> list[dict[str, object]]:
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
    series_id: str,
    limit: int = Query(100, ge=1, le=10_000),
    offset: int = Query(0, ge=0),
) -> dict[str, object]:
    settings = get_settings()
    path = str(settings.duckdb_path)
    conn = duckdb.connect(path, read_only=True)
    try:
        repo = ExternalDataCatalogRepository(conn=conn)
        entry = repo.get_by_series_id(series_id.strip())
        if entry is None:
            raise HTTPException(status_code=404, detail="series_id not found")
        page = fetch_series_data_page(conn, entry, limit=limit, offset=offset)
    finally:
        conn.close()
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
    series_id: str,
    days: int = Query(30, ge=1, le=3650),
    limit: int = Query(10_000, ge=1, le=50_000),
) -> dict[str, object]:
    settings = get_settings()
    path = str(settings.duckdb_path)
    conn = duckdb.connect(path, read_only=True)
    try:
        repo = ExternalDataCatalogRepository(conn=conn)
        entry = repo.get_by_series_id(series_id.strip())
        if entry is None:
            raise HTTPException(status_code=404, detail="series_id not found")
        page = fetch_series_data_recent(conn, entry, days=days, limit=limit)
    finally:
        conn.close()
    return jsonable_encoder(
        {
            "series_id": series_id,
            "table_name": page.table_name,
            "days": days,
            "count": len(page.rows),
            "rows": [_json_safe_row(r) for r in page.rows],
        },
    )
