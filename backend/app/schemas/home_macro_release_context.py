from __future__ import annotations

from datetime import date
from typing import Literal

from backend.app.schemas.result_meta import ResultMeta
from pydantic import BaseModel, ConfigDict, Field, model_validator

HomeMacroSourceStatus = Literal[
    "ready",
    "partial",
    "stale",
    "fallback",
    "source_pending",
    "error",
]
HomeMacroDisplayUnit = Literal["index", "pct", "persons"]
HomeMacroChangeUnit = Literal["index_point", "pct_point", "persons", "bp"]
HomeMacroDirection = Literal["up", "down", "flat", "unavailable"]


class _StrictHomeMacroModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class HomeMacroMetric(_StrictHomeMacroModel):
    metric_key: str = Field(min_length=1)
    label: str = Field(min_length=1)
    actual_value: float | None = None
    previous_value: float | None = None
    change_value: float | None = None
    display_unit: HomeMacroDisplayUnit
    change_unit: HomeMacroChangeUnit
    precision: int = Field(ge=0, le=6)
    direction: HomeMacroDirection


class HomeMacroHistoryItem(_StrictHomeMacroModel):
    indicator_key: str = Field(min_length=1)
    title: str = Field(min_length=1)
    region: Literal["CN", "US"]
    category: Literal["activity", "inflation", "growth", "employment", "monetary_policy"]
    importance: Literal["high", "medium", "low"]
    observation_date: date | None = None
    previous_observation_date: date | None = None
    reference_period: str | None = None
    previous_reference_period: str | None = None
    release_date: date | None = None
    source_status: HomeMacroSourceStatus
    source_name: str | None = None
    metrics: list[HomeMacroMetric] = Field(min_length=1)
    notes: list[str] = Field(default_factory=list)


class HomeMacroCoverage(_StrictHomeMacroModel):
    configured_count: int = Field(ge=0)
    ready_count: int = Field(ge=0)
    partial_count: int = Field(ge=0)
    stale_count: int = Field(ge=0)
    fallback_count: int = Field(ge=0)
    source_pending_count: int = Field(ge=0)
    error_count: int = Field(ge=0)


class HomeMacroReleaseContextResult(_StrictHomeMacroModel):
    window_start_date: date
    window_end_date: date
    history_items: list[HomeMacroHistoryItem]
    coverage: HomeMacroCoverage
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_window(self) -> HomeMacroReleaseContextResult:
        if self.window_end_date < self.window_start_date:
            raise ValueError("window_end_date must be on or after window_start_date")
        return self


class HomeMacroReleaseContextMeta(ResultMeta):
    model_config = ConfigDict(extra="forbid")

    trace_id: Literal["tr_home_macro_release_context"] = "tr_home_macro_release_context"
    basis: Literal["analytical"] = "analytical"
    result_kind: Literal["home.macro_release_context"] = "home.macro_release_context"
    formal_use_allowed: Literal[False] = False
    source_surface: Literal["market_data"] = "market_data"


class HomeMacroReleaseContextEnvelope(_StrictHomeMacroModel):
    result_meta: HomeMacroReleaseContextMeta
    result: HomeMacroReleaseContextResult
