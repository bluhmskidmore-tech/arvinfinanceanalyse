from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, ClassVar

from pydantic import BaseModel, Field, model_validator

from backend.app.schemas.common_numeric import Numeric, NumericUnit, numeric_from_raw


def _coerce_value_to_numeric(value: Any, unit: NumericUnit, sign_aware: bool) -> Any:
    if value is None:
        return None
    if isinstance(value, Numeric):
        return value
    if isinstance(value, dict) and {"raw", "unit", "display", "precision", "sign_aware"} <= set(value.keys()):
        return value
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

class CashflowMonthlyBucketPayload(BaseModel):
    year_month: str
    asset_inflow: Numeric
    liability_outflow: Numeric
    net_cashflow: Numeric
    cumulative_net: Numeric

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "asset_inflow": ("yuan", False),
        "liability_outflow": ("yuan", False),
        "net_cashflow": ("yuan", True),
        "cumulative_net": ("yuan", True),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class CashflowMaturingAssetPayload(BaseModel):
    instrument_code: str
    instrument_name: str
    maturity_date: str
    face_value: Numeric
    market_value: Numeric
    currency_code: str

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "face_value": ("yuan", False),
        "market_value": ("yuan", False),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class CashflowProjectionResponse(BaseModel):
    report_date: date
    duration_gap: Numeric
    asset_duration: Numeric
    liability_duration: Numeric
    equity_duration: Numeric
    rate_sensitivity_1bp: Numeric
    reinvestment_risk_12m: Numeric
    monthly_buckets: list[CashflowMonthlyBucketPayload]
    top_maturing_assets_12m: list[CashflowMaturingAssetPayload]
    warnings: list[str] = Field(default_factory=list)
    computed_at: str

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "duration_gap": ("ratio", True),
        "asset_duration": ("ratio", False),
        "liability_duration": ("ratio", False),
        "equity_duration": ("ratio", True),
        "rate_sensitivity_1bp": ("yuan", True),
        "reinvestment_risk_12m": ("pct", False),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)
