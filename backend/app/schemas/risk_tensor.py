from __future__ import annotations

from dataclasses import asdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from pydantic import BaseModel, Field, field_serializer

from backend.app.core_finance.risk_tensor import PortfolioRiskTensor

Q8 = Decimal("0.00000000")


class RiskTensorPayload(BaseModel):
    report_date: date
    portfolio_dv01: Decimal = Decimal("0")
    krd_1y: Decimal = Decimal("0")
    krd_3y: Decimal = Decimal("0")
    krd_5y: Decimal = Decimal("0")
    krd_7y: Decimal = Decimal("0")
    krd_10y: Decimal = Decimal("0")
    krd_30y: Decimal = Decimal("0")
    cs01: Decimal = Decimal("0")
    portfolio_convexity: Decimal = Decimal("0")
    portfolio_modified_duration: Decimal = Decimal("0")
    issuer_concentration_hhi: Decimal = Decimal("0")
    issuer_top5_weight: Decimal = Decimal("0")
    liquidity_gap_30d: Decimal = Decimal("0")
    liquidity_gap_90d: Decimal = Decimal("0")
    liquidity_gap_30d_ratio: Decimal = Decimal("0")
    total_market_value: Decimal = Decimal("0")
    bond_count: int = 0
    quality_flag: str = "ok"
    warnings: list[str] = Field(default_factory=list)

    @field_serializer(
        "portfolio_dv01",
        "krd_1y",
        "krd_3y",
        "krd_5y",
        "krd_7y",
        "krd_10y",
        "krd_30y",
        "cs01",
        "portfolio_convexity",
        "portfolio_modified_duration",
        "issuer_concentration_hhi",
        "issuer_top5_weight",
        "liquidity_gap_30d",
        "liquidity_gap_90d",
        "liquidity_gap_30d_ratio",
        "total_market_value",
        when_used="json",
    )
    def _serialize_decimal(self, value: Decimal) -> str:
        return format(value.quantize(Q8, rounding=ROUND_HALF_UP), "f")

    @classmethod
    def from_tensor(cls, tensor: PortfolioRiskTensor) -> "RiskTensorPayload":
        return cls(**asdict(tensor))
