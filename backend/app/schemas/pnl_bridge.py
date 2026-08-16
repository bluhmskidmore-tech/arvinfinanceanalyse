from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, ClassVar, Literal

from backend.app.schemas.common_numeric import Numeric, NumericUnit, numeric_from_raw
from pydantic import BaseModel, ConfigDict, Field, model_validator

# 曲线类效应的可用性口径。金额字段（treasury_curve / credit_spread 及其合计）不受
# 影响：它们仍然是 0，explained_pnl / residual 一分不变。这里新增的只是"那个 0 是
# 观测出来的还是被缺失输入顶出来的"这一条元信息——没有它，页面上的"利率效应 0"
# 会被读成"利率没动"，而 2026-07-31 的真相是"没有曲线可比"。
#
# 取值与 `core_finance.pnl_bridge` 的 CURVE_EFFECT_* 常量一一对应，由那里派生；
# 此处用 Literal 复述一遍，是为了让契约在 schema 层可见、并让 OpenAPI/前端拿到闭集。
PnlBridgeEffectAvailability = Literal["ok", "unavailable", "not_applicable"]
PnlBridgeEffectCoverage = Literal["ok", "partial", "unavailable", "not_applicable"]
PnlBridgeEffectAvailabilityReason = Literal[
    # unavailable：缺输入，需要补数据
    "curve_unavailable",
    "same_source_curve",
    "market_value_base_missing",
    "roll_window_missing",
    "tenor_outside_curve_support",
    # not_applicable：这一行本来就不会有这个效应，不需要补数据
    "non_fvtpl_basis",
    "not_credit_book",
    "no_curve_sensitivity",
    "balance_row_missing",
]


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


class PnlBridgeEffectAvailabilitySchema(BaseModel):
    """汇总级效应可用性块。

    键名与 Campisi 的 ``effect_availability`` 条目对齐（status / 计数 / 成因），
    这样页面对"某个效应不可用"只需要一套渲染分支，而不必先分辨 payload 来自哪条
    计算路径。``applicable_rows`` 是分母：非 FVTPL 行按口径不参与市场效应，被排除
    在外，否则"多少行不可用"会被结构性豁免行稀释。
    """

    model_config = ConfigDict(extra="forbid")

    status: PnlBridgeEffectCoverage = "ok"
    unavailable_rows: int = 0
    applicable_rows: int = 0
    reasons: list[PnlBridgeEffectAvailabilityReason] = Field(default_factory=list)


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
    residual_ratio: Numeric | None
    quality_flag: Literal["ok", "warning", "error"]
    current_balance_found: bool
    prior_balance_found: bool
    balance_diagnostics: list[str]
    # `balance_diagnostics` 里的带前缀诊断保持原样下发（下游可能有文本匹配器）；
    # 下面六个字段是同一判断的结构化并行通道，消费方不必再做字符串前缀匹配。
    # roll_down 单独一组：它只用当期曲线，却额外要求一个有效的滚动窗口，
    # 因此可用性与 treasury_curve 并不同步。
    roll_down_availability: PnlBridgeEffectAvailability = "ok"
    roll_down_availability_reason: PnlBridgeEffectAvailabilityReason | None = None
    treasury_curve_availability: PnlBridgeEffectAvailability = "ok"
    treasury_curve_availability_reason: PnlBridgeEffectAvailabilityReason | None = None
    credit_spread_availability: PnlBridgeEffectAvailability = "ok"
    credit_spread_availability_reason: PnlBridgeEffectAvailabilityReason | None = None

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
    # total_roll_down / total_treasury_curve / total_credit_spread 的数值不变；
    # 这三块说明合计里的 0 有多少来自缺失输入而非"市场没动"。
    roll_down_availability: PnlBridgeEffectAvailabilitySchema = Field(
        default_factory=PnlBridgeEffectAvailabilitySchema
    )
    treasury_curve_availability: PnlBridgeEffectAvailabilitySchema = Field(
        default_factory=PnlBridgeEffectAvailabilitySchema
    )
    credit_spread_availability: PnlBridgeEffectAvailabilitySchema = Field(
        default_factory=PnlBridgeEffectAvailabilitySchema
    )

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
