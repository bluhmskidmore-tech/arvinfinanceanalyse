from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ChoiceMacroOptionValue = str | int | float | bool


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


class ChoiceMacroCatalogBatchConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    batch_id: str
    request_options: dict[str, ChoiceMacroOptionValue]
    series: list[ChoiceMacroSeriesConfig]


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


class MacroVendorPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    read_target: Literal["duckdb"] = "duckdb"
    series: list[MacroVendorSeries]


class ChoiceMacroLatestPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    series_id: str
    series_name: str
    trade_date: str
    value_numeric: float
    unit: str
    source_version: str
    vendor_version: str


class ChoiceMacroLatestPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    read_target: Literal["duckdb"] = "duckdb"
    series: list[ChoiceMacroLatestPoint]
