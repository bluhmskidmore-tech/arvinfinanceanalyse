from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ResearchWindow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_date: str
    end_date: str
    as_of_date: str


class ResearchRunManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    run_kind: Literal["analysis", "backtest", "experiment", "strategy"]
    basis: Literal["analytical", "scenario", "formal"] = "analytical"
    source_version: str
    vendor_version: str = "vv_none"
    rule_version: str
    parameter_hash: str
    parameters: dict[str, object] = Field(default_factory=dict)
    window: ResearchWindow
    universe: dict[str, object] = Field(default_factory=dict)
    temporal_policy: Literal["fail_closed"] = "fail_closed"
    code_version: str | None = None
    code_ref: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def model_dump(self, *args, **kwargs):
        kwargs.setdefault("exclude_none", True)
        return super().model_dump(*args, **kwargs)
