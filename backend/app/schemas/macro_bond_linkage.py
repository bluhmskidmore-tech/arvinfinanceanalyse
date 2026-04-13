from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field

AlignmentMode = Literal["conservative", "market_timing"]


class MacroBondCorrelationItem(BaseModel):
    series_id: str
    series_name: str
    target_yield: str
    target_family: str
    target_tenor: str | None = None
    correlation_3m: float | None = None
    correlation_6m: float | None = None
    correlation_1y: float | None = None
    lead_lag_days: int
    direction: str
    alignment_mode: AlignmentMode | None = None
    sample_size: int | None = None
    winsorized: bool = False
    zscore_applied: bool = False
    lead_lag_confidence: float | None = None
    effective_observation_span_days: int | None = None


class MacroBondLinkageMethodMeta(BaseModel):
    """Per-variant metadata for macro–bond linkage correlation tracks."""

    variant: AlignmentMode
    description: str | None = None
    warnings: list[str] = Field(default_factory=list)


class MacroBondLinkageMethodVariant(BaseModel):
    method_meta: MacroBondLinkageMethodMeta
    top_correlations: list[MacroBondCorrelationItem] = Field(default_factory=list)


class MacroBondLinkageMethodVariants(BaseModel):
    conservative: MacroBondLinkageMethodVariant
    market_timing: MacroBondLinkageMethodVariant


class MacroBondLinkageResponse(BaseModel):
    report_date: date
    environment_score: dict[str, Any] = Field(default_factory=dict)
    portfolio_impact: dict[str, Any] = Field(default_factory=dict)
    top_correlations: list[MacroBondCorrelationItem] = Field(default_factory=list)
    method_variants: MacroBondLinkageMethodVariants
    warnings: list[str] = Field(default_factory=list)
    computed_at: str
