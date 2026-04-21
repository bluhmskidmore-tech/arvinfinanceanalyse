"""HTTP routes for external-data catalog (M1 — read-only directory)."""

from __future__ import annotations

from typing import Literal

from backend.app.services.external_data_service import default_service
from fastapi import APIRouter, HTTPException

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
