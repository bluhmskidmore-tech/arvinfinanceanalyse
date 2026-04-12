from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class AdvancedAttributionBundlePayload(BaseModel):
    """Contract for balance-analysis advanced attribution (analytical/scenario only; never formal workbook)."""

    model_config = ConfigDict(extra="forbid")

    report_date: str
    mode: Literal["analytical", "scenario"] = "analytical"
    scenario_name: str | None = None
    scenario_inputs: dict[str, int] = {}
    status: Literal["not_ready"]
    missing_inputs: list[str]
    blocked_components: list[str]
    warnings: list[str]
