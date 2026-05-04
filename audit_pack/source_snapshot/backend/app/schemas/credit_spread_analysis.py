from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class CreditSpreadAnalysisResponse(BaseModel):
    report_date: date
    credit_bond_count: int
    total_credit_market_value: str
    weighted_avg_spread_bps: str
    spread_term_structure: list[dict] = Field(default_factory=list)
    top_spread_bonds: list[dict] = Field(default_factory=list)
    bottom_spread_bonds: list[dict] = Field(default_factory=list)
    historical_context: dict | None = None
    warnings: list[str] = Field(default_factory=list)
    computed_at: str
