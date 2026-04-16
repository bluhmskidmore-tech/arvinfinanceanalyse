from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_serializer


class PnlBridgeRowSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    report_date: date
    instrument_code: str
    portfolio_name: str
    cost_center: str
    accounting_basis: str
    beginning_dirty_mv: Decimal
    ending_dirty_mv: Decimal
    carry: Decimal
    roll_down: Decimal
    treasury_curve: Decimal
    credit_spread: Decimal
    fx_translation: Decimal
    realized_trading: Decimal
    unrealized_fv: Decimal
    manual_adjustment: Decimal
    explained_pnl: Decimal
    actual_pnl: Decimal
    residual: Decimal
    residual_ratio: Decimal
    quality_flag: Literal["ok", "warning", "error"]
    current_balance_found: bool
    prior_balance_found: bool
    balance_diagnostics: list[str]

    @field_serializer(
        "beginning_dirty_mv",
        "ending_dirty_mv",
        "carry",
        "roll_down",
        "treasury_curve",
        "credit_spread",
        "fx_translation",
        "realized_trading",
        "unrealized_fv",
        "manual_adjustment",
        "explained_pnl",
        "actual_pnl",
        "residual",
        "residual_ratio",
        when_used="json",
    )
    def _serialize_decimal(self, value: Decimal) -> str:
        return format(value, "f")


class PnlBridgeSummarySchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    row_count: int
    ok_count: int
    warning_count: int
    error_count: int
    total_beginning_dirty_mv: Decimal
    total_ending_dirty_mv: Decimal
    total_carry: Decimal
    total_roll_down: Decimal
    total_treasury_curve: Decimal
    total_credit_spread: Decimal
    total_fx_translation: Decimal
    total_realized_trading: Decimal
    total_unrealized_fv: Decimal
    total_manual_adjustment: Decimal
    total_explained_pnl: Decimal
    total_actual_pnl: Decimal
    total_residual: Decimal
    quality_flag: Literal["ok", "warning", "error"]

    @field_serializer(
        "total_beginning_dirty_mv",
        "total_ending_dirty_mv",
        "total_carry",
        "total_roll_down",
        "total_treasury_curve",
        "total_credit_spread",
        "total_fx_translation",
        "total_realized_trading",
        "total_unrealized_fv",
        "total_manual_adjustment",
        "total_explained_pnl",
        "total_actual_pnl",
        "total_residual",
        when_used="json",
    )
    def _serialize_decimal(self, value: Decimal) -> str:
        return format(value, "f")


class PnlBridgePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_date: str
    rows: list[PnlBridgeRowSchema]
    summary: PnlBridgeSummarySchema
    warnings: list[str]
