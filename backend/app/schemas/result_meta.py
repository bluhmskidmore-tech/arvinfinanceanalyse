from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


SourceSurface = Literal[
    "executive_analytical",
    "formal_attribution",
    "formal_pnl",
    "formal_balance",
    "formal_liability",
    "bond_analytics",
    "risk_tensor",
    "cashflow",
    "pnl_bridge",
]

_GOVERNED_RESULT_KIND_PREFIXES = (
    "executive.",
    "pnl_attribution.",
    "balance-analysis.",
    "liability_analytics.",
    "bond_analytics.",
    "bond_dashboard.",
    "risk.tensor",
    "cashflow_projection.",
    "pnl.bridge",
)


class ResultMeta(BaseModel):
    trace_id: str = Field(..., description="Trace identifier for governance and audit.")
    basis: Literal["formal", "scenario", "analytical"] = "formal"
    result_kind: str = "analysis_view"
    formal_use_allowed: bool = True
    source_version: str
    vendor_version: str = "vv_none"
    rule_version: str
    cache_version: str
    quality_flag: Literal["ok", "warning", "error", "stale"] = "ok"
    vendor_status: Literal["ok", "vendor_stale", "vendor_unavailable"] = "ok"
    fallback_mode: Literal["none", "latest_snapshot"] = "none"
    scenario_flag: bool = False
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    filters_applied: dict[str, Any] = Field(default_factory=dict)
    tables_used: list[str] = Field(default_factory=list)
    evidence_rows: int | None = None
    next_drill: list[str | dict[str, Any]] = Field(default_factory=list)
    source_surface: SourceSurface | None = None

    @model_validator(mode="after")
    def _require_source_surface_for_governed_result_kinds(self) -> "ResultMeta":
        if any(self.result_kind.startswith(prefix) for prefix in _GOVERNED_RESULT_KIND_PREFIXES):
            if self.source_surface is None:
                raise ValueError(
                    f"source_surface is required for governed result_kind={self.result_kind!r}."
                )
        return self
