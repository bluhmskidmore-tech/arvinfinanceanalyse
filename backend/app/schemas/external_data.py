"""Schemas for external-data catalog (M1)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ExternalDataCatalogEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    series_id: str = Field(..., min_length=1)
    series_name: str
    vendor_name: str
    source_family: str
    domain: Literal["macro", "news", "yield_curve", "fx", "other"]
    frequency: str | None = None
    unit: str | None = None
    refresh_tier: str | None = None
    fetch_mode: str | None = None
    raw_zone_path: str | None = None
    standardized_table: str | None = None
    view_name: str | None = None
    access_path: str | None = None
    catalog_version: str
    created_at: str
