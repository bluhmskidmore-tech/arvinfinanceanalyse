from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class AdvancedAttributionBundlePayload(BaseModel):
    """Contract for balance-analysis advanced attribution (analytical only; not formal workbook)."""

    model_config = ConfigDict(extra="forbid")

    report_date: str
    status: Literal["not_ready"]
    missing_inputs: list[str]
    blocked_components: list[str]
    warnings: list[str]
