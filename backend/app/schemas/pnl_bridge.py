from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, model_validator

from backend.app.schemas.common_numeric import Numeric, NumericUnit, numeric_from_raw


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
    if is_dataclass(data):
        out = asdict(data)
    elif isinstance(data, dict):
        out = dict(data)
    else:
        return data
    for field_name, (unit, sign_aware) in field_map.items():
        if field_name in out:
            out[field_name] = _coerce_value_to_numeric(out[field_name], unit, sign_aware)
    return out


class PnlBridgeRowSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    report_date: date
    instrument_code: str
    portfolio_name: str
    cost_center: str
    accounting_basis: str
    beginning_dirty_mv: Numeric
    ending_dirty_mv: Numeric
    carry: Numeric
    roll_down: Numeric
    treasury_curve: Numeric
    credit_spread: Numeric
    fx_translation: Numeric
    realized_trading: Numeric
    unrealized_fv: Numeric
    manual_adjustment: Numeric
    explained_pnl: Numeric
    actual_pnl: Numeric
    residual: Numeric
    residual_ratio: Numeric
    quality_flag: Literal["ok", "warning", "error"]
    current_balance_found: bool
    prior_balance_found: bool
    balance_diagnostics: list[str]

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "beginning_dirty_mv": ("yuan", False),
        "ending_dirty_mv": ("yuan", False),
        "carry": ("yuan", True),
        "roll_down": ("yuan", True),
        "treasury_curve": ("yuan", True),
        "credit_spread": ("yuan", True),
        "fx_translation": ("yuan", True),
        "realized_trading": ("yuan", True),
        "unrealized_fv": ("yuan", True),
        "manual_adjustment": ("yuan", True),
        "explained_pnl": ("yuan", True),
        "actual_pnl": ("yuan", True),
        "residual": ("yuan", True),
        "residual_ratio": ("ratio", True),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class PnlBridgeSummarySchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    row_count: int
    ok_count: int
    warning_count: int
    error_count: int
    total_beginning_dirty_mv: Numeric
    total_ending_dirty_mv: Numeric
    total_carry: Numeric
    total_roll_down: Numeric
    total_treasury_curve: Numeric
    total_credit_spread: Numeric
    total_fx_translation: Numeric
    total_realized_trading: Numeric
    total_unrealized_fv: Numeric
    total_manual_adjustment: Numeric
    total_explained_pnl: Numeric
    total_actual_pnl: Numeric
    total_residual: Numeric
    quality_flag: Literal["ok", "warning", "error"]

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "total_beginning_dirty_mv": ("yuan", False),
        "total_ending_dirty_mv": ("yuan", False),
        "total_carry": ("yuan", True),
        "total_roll_down": ("yuan", True),
        "total_treasury_curve": ("yuan", True),
        "total_credit_spread": ("yuan", True),
        "total_fx_translation": ("yuan", True),
        "total_realized_trading": ("yuan", True),
        "total_unrealized_fv": ("yuan", True),
        "total_manual_adjustment": ("yuan", True),
        "total_explained_pnl": ("yuan", True),
        "total_actual_pnl": ("yuan", True),
        "total_residual": ("yuan", True),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class PnlBridgePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_date: str
    rows: list[PnlBridgeRowSchema]
    summary: PnlBridgeSummarySchema
    warnings: list[str]
