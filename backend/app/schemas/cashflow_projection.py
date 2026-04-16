from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class CashflowProjectionResponse(BaseModel):
    report_date: date
    duration_gap: str
    asset_duration: str
    liability_duration: str
    equity_duration: str
    rate_sensitivity_1bp: str
    reinvestment_risk_12m: str
    monthly_buckets: list[dict]
    top_maturing_assets_12m: list[dict]
    warnings: list[str] = Field(default_factory=list)
    computed_at: str
