from __future__ import annotations

from dataclasses import asdict
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, ClassVar

from pydantic import BaseModel, Field, model_validator

from backend.app.core_finance.risk_tensor import PortfolioRiskTensor
from backend.app.schemas.common_numeric import Numeric, NumericUnit, numeric_from_raw


class Dv01StressScenario(BaseModel):
    scenario_key: str
    label: str
    shock_bp: Numeric
    estimated_pnl_impact: Numeric


class Dv01ControlsPayload(BaseModel):
    basis: str
    limit_status: str
    approved_limit_dv01: Numeric | None = None
    limit_usage_ratio: Numeric | None = None
    volatility_status: str
    daily_rate_volatility_bp: Numeric | None = None
    dominant_krd_bucket: str
    dominant_krd: Numeric
    stress_scenarios: list[Dv01StressScenario] = Field(default_factory=list)
    control_message: str
    action_hint: str


def _coerce_value_to_numeric(value: Any, unit: NumericUnit, sign_aware: bool) -> Any:
    if value is None:
        return None
    if isinstance(value, Numeric):
        return value
    if isinstance(value, dict) and {"raw", "unit", "display", "precision", "sign_aware"} <= set(value.keys()):
        return value
    if isinstance(value, Decimal):
        return numeric_from_raw(raw=float(value), unit=unit, sign_aware=sign_aware).model_dump(mode="json")
    if isinstance(value, str):
        normalized = value.strip().replace(",", "")
        if not normalized:
            return value
        try:
            raw = float(Decimal(normalized))
        except InvalidOperation:
            return value
        return numeric_from_raw(raw=raw, unit=unit, sign_aware=sign_aware).model_dump(mode="json")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return numeric_from_raw(raw=float(value), unit=unit, sign_aware=sign_aware).model_dump(mode="json")
    return value


def _apply_numeric_coercion(
    field_map: dict[str, tuple[NumericUnit, bool]],
    data: Any,
) -> Any:
    if not isinstance(data, dict):
        return data
    out = dict(data)
    for field_name, (unit, sign_aware) in field_map.items():
        if field_name in out:
            out[field_name] = _coerce_value_to_numeric(out[field_name], unit, sign_aware)
    return out


class RiskTensorPayload(BaseModel):
    report_date: date
    portfolio_dv01: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="dv01", sign_aware=False))
    regulatory_dv01: Numeric | None = None
    krd_1y: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="ratio", sign_aware=True))
    krd_3y: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="ratio", sign_aware=True))
    krd_5y: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="ratio", sign_aware=True))
    krd_7y: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="ratio", sign_aware=True))
    krd_10y: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="ratio", sign_aware=True))
    krd_30y: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="ratio", sign_aware=True))
    cs01: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="dv01", sign_aware=False))
    portfolio_convexity: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="ratio", sign_aware=False))
    portfolio_modified_duration: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="ratio", sign_aware=False))
    issuer_concentration_hhi: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="ratio", sign_aware=False))
    issuer_top5_weight: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="ratio", sign_aware=False))
    asset_cashflow_30d: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="yuan", sign_aware=False))
    asset_cashflow_90d: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="yuan", sign_aware=False))
    liability_cashflow_30d: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="yuan", sign_aware=False))
    liability_cashflow_90d: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="yuan", sign_aware=False))
    liquidity_gap_30d: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="yuan", sign_aware=True))
    liquidity_gap_90d: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="yuan", sign_aware=True))
    liquidity_gap_30d_ratio: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="ratio", sign_aware=True))
    total_market_value: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="yuan", sign_aware=False))
    bond_count: int = 0
    quality_flag: str = "ok"
    warnings: list[str] = Field(default_factory=list)
    dv01_controls: Dv01ControlsPayload | None = None

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "portfolio_dv01": ("dv01", False),
        "regulatory_dv01": ("dv01", False),
        "krd_1y": ("ratio", True),
        "krd_3y": ("ratio", True),
        "krd_5y": ("ratio", True),
        "krd_7y": ("ratio", True),
        "krd_10y": ("ratio", True),
        "krd_30y": ("ratio", True),
        "cs01": ("dv01", False),
        "portfolio_convexity": ("ratio", False),
        "portfolio_modified_duration": ("ratio", False),
        "issuer_concentration_hhi": ("ratio", False),
        "issuer_top5_weight": ("ratio", False),
        "asset_cashflow_30d": ("yuan", False),
        "asset_cashflow_90d": ("yuan", False),
        "liability_cashflow_30d": ("yuan", False),
        "liability_cashflow_90d": ("yuan", False),
        "liquidity_gap_30d": ("yuan", True),
        "liquidity_gap_90d": ("yuan", True),
        "liquidity_gap_30d_ratio": ("ratio", True),
        "total_market_value": ("yuan", False),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)

    @classmethod
    def from_tensor(cls, tensor: PortfolioRiskTensor) -> "RiskTensorPayload":
        return cls(**asdict(tensor))
