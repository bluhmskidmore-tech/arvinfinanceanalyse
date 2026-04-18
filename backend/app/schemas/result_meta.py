from datetime import datetime, timezone
from typing import Any
from typing import Literal

from pydantic import BaseModel, Field


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
