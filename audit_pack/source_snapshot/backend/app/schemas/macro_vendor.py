from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ChoiceMacroOptionValue = str | int | float | bool
ChoiceMacroFetchMode = Literal["date_slice", "latest"]
ChoiceMacroFetchGranularity = Literal["batch", "single"]
ChoiceMacroRefreshTier = Literal["stable", "fallback", "isolated"]
FxAnalyticalGroupKey = Literal["middle_rate", "fx_index", "fx_swap_curve"]


class ChoiceMacroSeriesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    series_id: str
    series_name: str
    vendor_series_code: str
    frequency: str
    unit: str
    theme: str = "unknown"
    is_core: bool = False
    tags: list[str] = Field(default_factory=list)


class ChoiceMacroBatchConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    batch_id: str
    request_options: str
    series: list[ChoiceMacroSeriesConfig]
    catalog_version: str | None = None
    fetch_mode: ChoiceMacroFetchMode = "date_slice"
    fetch_granularity: ChoiceMacroFetchGranularity = "batch"
    refresh_tier: ChoiceMacroRefreshTier = "stable"
    policy_note: str | None = None


class ChoiceMacroCatalogBatchConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    batch_id: str
    request_options: dict[str, ChoiceMacroOptionValue]
    series: list[ChoiceMacroSeriesConfig]
    fetch_mode: ChoiceMacroFetchMode = "date_slice"
    fetch_granularity: ChoiceMacroFetchGranularity = "batch"
    refresh_tier: ChoiceMacroRefreshTier = "stable"
    policy_note: str | None = None


class ChoiceMacroCatalogAsset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    catalog_version: str
    vendor_name: str
    generated_at: datetime
    generated_from: str
    batches: list[ChoiceMacroCatalogBatchConfig]


class ChoiceMacroPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    series_id: str
    series_name: str
    vendor_series_code: str
    vendor_name: str
    trade_date: str
    value_numeric: float
    frequency: str
    unit: str
    vendor_version: str


class ChoiceMacroSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vendor_name: str
    vendor_version: str
    captured_at: datetime
    series: list[ChoiceMacroPoint]
    raw_payload: dict[str, object]


class MacroVendorSeries(BaseModel):
    model_config = ConfigDict(extra="forbid")

    series_id: str
    series_name: str
    vendor_name: str
    vendor_version: str
    frequency: str
    unit: str
    refresh_tier: ChoiceMacroRefreshTier | None = None
    fetch_mode: ChoiceMacroFetchMode | None = None
    fetch_granularity: ChoiceMacroFetchGranularity | None = None
    policy_note: str | None = None


class MacroVendorPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    read_target: Literal["duckdb"] = "duckdb"
    series: list[MacroVendorSeries]


class ChoiceMacroRecentPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trade_date: str
    value_numeric: float
    source_version: str
    vendor_version: str
    quality_flag: Literal["ok", "warning", "error", "stale"] = "warning"


class ChoiceMacroLatestPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    series_id: str
    series_name: str
    trade_date: str
    value_numeric: float
    frequency: str
    unit: str
    source_version: str
    vendor_version: str
    vendor_name: str | None = None
    refresh_tier: ChoiceMacroRefreshTier | None = None
    fetch_mode: ChoiceMacroFetchMode | None = None
    fetch_granularity: ChoiceMacroFetchGranularity | None = None
    policy_note: str | None = None
    quality_flag: Literal["ok", "warning", "error", "stale"] = "warning"
    latest_change: float | None = None
    recent_points: list[ChoiceMacroRecentPoint] = Field(default_factory=list)


class ChoiceMacroLatestPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    read_target: Literal["duckdb"] = "duckdb"
    series: list[ChoiceMacroLatestPoint]


class FxFormalStatusRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_currency: str
    quote_currency: str
    pair_label: str
    series_id: str
    series_name: str
    vendor_series_code: str
    trade_date: str | None = None
    observed_trade_date: str | None = None
    mid_rate: float | None = None
    source_name: str | None = None
    vendor_name: str | None = None
    vendor_version: str | None = None
    source_version: str | None = None
    is_business_day: bool | None = None
    is_carry_forward: bool | None = None
    status: Literal["ok", "missing"] = "missing"


class FxFormalStatusPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    read_target: Literal["duckdb"] = "duckdb"
    vendor_priority: list[str] = Field(default_factory=lambda: ["choice", "akshare", "fail_closed"])
    candidate_count: int
    materialized_count: int
    latest_trade_date: str | None = None
    carry_forward_count: int = 0
    rows: list[FxFormalStatusRow]


class FxAnalyticalSeriesPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group_key: FxAnalyticalGroupKey
    series_id: str
    series_name: str
    trade_date: str
    value_numeric: float
    frequency: str
    unit: str
    source_version: str
    vendor_version: str
    refresh_tier: ChoiceMacroRefreshTier | None = None
    fetch_mode: ChoiceMacroFetchMode | None = None
    fetch_granularity: ChoiceMacroFetchGranularity | None = None
    policy_note: str | None = None
    quality_flag: Literal["ok", "warning", "error", "stale"] = "warning"
    latest_change: float | None = None
    recent_points: list[ChoiceMacroRecentPoint] = Field(default_factory=list)


class FxAnalyticalGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group_key: FxAnalyticalGroupKey
    title: str
    description: str
    series: list[FxAnalyticalSeriesPoint]


class FxAnalyticalPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    read_target: Literal["duckdb"] = "duckdb"
    groups: list[FxAnalyticalGroup]
