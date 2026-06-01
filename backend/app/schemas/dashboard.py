"""Pydantic contracts for consolidated dashboard KPI endpoints."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from backend.app.schemas.common_numeric import Numeric


class CoreMetricsCardData(BaseModel):
    total_amount: Numeric
    weighted_avg_rate: Numeric
    change_amount: Numeric
    change_pct: Numeric
    top_3_details: list[dict[str, object]] = Field(default_factory=list)


class CoreMetricsPayload(BaseModel):
    report_date: str
    bond_investments: CoreMetricsCardData
    interbank_assets: CoreMetricsCardData
    interbank_liabilities: CoreMetricsCardData


class DailyChangePeriod(BaseModel):
    period: Literal["day", "week", "month"]
    bond_investments_change: Numeric
    interbank_assets_change: Numeric
    interbank_liabilities_change: Numeric
    net_change: Numeric


class DailyChangesPayload(BaseModel):
    report_date: str
    periods: list[DailyChangePeriod]
