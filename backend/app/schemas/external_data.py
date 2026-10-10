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


class ExternalDataWatermarkEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    series_id: str
    series_name: str
    vendor_name: str
    source_family: str
    domain: Literal["macro", "news", "yield_curve", "fx", "other"]
    frequency: str | None = None
    unit: str | None = None
    refresh_tier: str | None = None
    fetch_mode: str | None = None
    relation_name: str | None = None
    date_column: str | None = None
    row_count: int = Field(..., ge=0)
    latest_business_date: str | None = None
    latest_loaded_at: str | None = None
    age_days: int | None = None
    freshness_tier: Literal["fresh", "stale", "expired", "unknown"] | None = None
    data_status: Literal["available", "no_data", "unavailable"]
    error_message: str | None = None


class ExternalDataWatermarkSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    catalog_count: int = Field(..., ge=0)
    available_count: int = Field(..., ge=0)
    no_data_count: int = Field(..., ge=0)
    unavailable_count: int = Field(..., ge=0)
    oldest_available_business_date: str | None = None
    newest_available_business_date: str | None = None
    # Derived top-level meta: max(latest_loaded_at) across all series, null when
    # nothing has ever been loaded. No dedicated ingest-log table behind it.
    last_successful_ingest: str | None = None


class ExternalDataWatermarkLedger(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    summary: ExternalDataWatermarkSummary
    entries: list[ExternalDataWatermarkEntry]
