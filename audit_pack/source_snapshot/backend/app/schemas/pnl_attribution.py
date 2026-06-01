"""Pydantic mirrors of frontend `contracts.ts` PnL attribution payloads.

W3.1: numeric fields migrated from bare ``float`` to ``Numeric``. A
module-level ``model_validator(mode="before")`` on each class automatically
coerces legacy ``float`` / ``int`` callsites into display-only ``Numeric``
dicts via ``numeric_from_raw``. Service layer (W3.2) will construct Numeric
directly; this transitional shim keeps pre-W3.2 callsites working.
"""
from __future__ import annotations

from typing import Any, ClassVar, Literal

from pydantic import BaseModel, model_validator

from backend.app.schemas.common_numeric import Numeric, NumericUnit, numeric_from_raw


def _coerce_value_to_numeric(value: Any, unit: NumericUnit, sign_aware: bool) -> Any:
    """Coerce float / int / dict into a Numeric-compatible structure.

    - ``None`` → ``None``
    - ``Numeric`` instance → pass through
    - ``dict`` with Numeric 5-key shape → pass through
    - ``float`` / ``int`` → coerced via ``numeric_from_raw`` and dumped to dict
    - other types → pass through (pydantic will raise)
    """
    if value is None:
        return None
    if isinstance(value, Numeric):
        return value
    if isinstance(value, dict) and {"raw", "unit", "display", "precision", "sign_aware"} <= set(value.keys()):
        return value
    if isinstance(value, (int, float)):
        return numeric_from_raw(
            raw=float(value), unit=unit, sign_aware=sign_aware
        ).model_dump(mode="json")
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


# =========================================================================
# VolumeRate
# =========================================================================


class VolumeRateAttributionItem(BaseModel):
    category: str
    category_type: str
    level: int
    current_scale: Numeric
    current_pnl: Numeric
    current_yield_pct: Numeric | None = None
    previous_scale: Numeric | None = None
    previous_pnl: Numeric | None = None
    previous_yield_pct: Numeric | None = None
    pnl_change: Numeric | None = None
    pnl_change_pct: Numeric | None = None
    volume_effect: Numeric | None = None
    rate_effect: Numeric | None = None
    interaction_effect: Numeric | None = None
    attrib_sum: Numeric | None = None
    recon_error: Numeric | None = None
    volume_contribution_pct: Numeric | None = None
    rate_contribution_pct: Numeric | None = None

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "current_scale": ("yuan", False),
        "current_pnl": ("yuan", True),
        "current_yield_pct": ("pct", True),
        "previous_scale": ("yuan", False),
        "previous_pnl": ("yuan", True),
        "previous_yield_pct": ("pct", True),
        "pnl_change": ("yuan", True),
        "pnl_change_pct": ("pct", True),
        "volume_effect": ("yuan", True),
        "rate_effect": ("yuan", True),
        "interaction_effect": ("yuan", True),
        "attrib_sum": ("yuan", True),
        "recon_error": ("yuan", True),
        "volume_contribution_pct": ("pct", True),
        "rate_contribution_pct": ("pct", True),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class VolumeRateAttributionPayload(BaseModel):
    current_period: str
    previous_period: str
    compare_type: str
    total_current_pnl: Numeric
    total_previous_pnl: Numeric | None = None
    total_pnl_change: Numeric | None = None
    total_volume_effect: Numeric | None = None
    total_rate_effect: Numeric | None = None
    total_interaction_effect: Numeric | None = None
    items: list[VolumeRateAttributionItem]
    has_previous_data: bool

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "total_current_pnl": ("yuan", True),
        "total_previous_pnl": ("yuan", True),
        "total_pnl_change": ("yuan", True),
        "total_volume_effect": ("yuan", True),
        "total_rate_effect": ("yuan", True),
        "total_interaction_effect": ("yuan", True),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


# =========================================================================
# TPLMarket
# =========================================================================


class TPLMarketDataPoint(BaseModel):
    period: str
    period_label: str
    tpl_fair_value_change: Numeric
    tpl_total_pnl: Numeric
    tpl_scale: Numeric
    treasury_10y: Numeric | None = None
    treasury_10y_change: Numeric | None = None
    dr007: Numeric | None = None

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "tpl_fair_value_change": ("yuan", True),
        "tpl_total_pnl": ("yuan", True),
        "tpl_scale": ("yuan", False),
        "treasury_10y": ("pct", True),
        "treasury_10y_change": ("pct", True),
        "dr007": ("pct", True),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class TPLMarketCorrelationPayload(BaseModel):
    start_period: str
    end_period: str
    num_periods: int
    correlation_coefficient: Numeric | None = None
    correlation_interpretation: str
    total_tpl_fv_change: Numeric
    avg_treasury_10y_change: Numeric | None = None
    treasury_10y_total_change_bp: Numeric | None = None
    data_points: list[TPLMarketDataPoint]
    analysis_summary: str

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "correlation_coefficient": ("ratio", True),
        "total_tpl_fv_change": ("yuan", True),
        "avg_treasury_10y_change": ("pct", True),
        "treasury_10y_total_change_bp": ("bp", True),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


# =========================================================================
# Composition
# =========================================================================


class PnlCompositionItem(BaseModel):
    category: str
    category_type: str
    level: int
    total_pnl: Numeric
    interest_income: Numeric
    fair_value_change: Numeric
    capital_gain: Numeric
    other_income: Numeric
    interest_pct: Numeric
    fair_value_pct: Numeric
    capital_gain_pct: Numeric
    other_pct: Numeric

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "total_pnl": ("yuan", True),
        "interest_income": ("yuan", True),
        "fair_value_change": ("yuan", True),
        "capital_gain": ("yuan", True),
        "other_income": ("yuan", True),
        "interest_pct": ("pct", True),
        "fair_value_pct": ("pct", True),
        "capital_gain_pct": ("pct", True),
        "other_pct": ("pct", True),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class PnlCompositionTrendItem(BaseModel):
    period: str
    period_label: str
    interest_income: Numeric
    fair_value_change: Numeric
    capital_gain: Numeric
    other_income: Numeric
    total_pnl: Numeric

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "interest_income": ("yuan", True),
        "fair_value_change": ("yuan", True),
        "capital_gain": ("yuan", True),
        "other_income": ("yuan", True),
        "total_pnl": ("yuan", True),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class PnlCompositionPayload(BaseModel):
    report_period: str
    report_date: str
    total_pnl: Numeric
    total_interest_income: Numeric
    total_fair_value_change: Numeric
    total_capital_gain: Numeric
    total_other_income: Numeric
    interest_pct: Numeric
    fair_value_pct: Numeric
    capital_gain_pct: Numeric
    other_pct: Numeric
    items: list[PnlCompositionItem]
    trend_data: list[PnlCompositionTrendItem]

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "total_pnl": ("yuan", True),
        "total_interest_income": ("yuan", True),
        "total_fair_value_change": ("yuan", True),
        "total_capital_gain": ("yuan", True),
        "total_other_income": ("yuan", True),
        "interest_pct": ("pct", True),
        "fair_value_pct": ("pct", True),
        "capital_gain_pct": ("pct", True),
        "other_pct": ("pct", True),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class PnlAttributionAnalysisSummary(BaseModel):
    report_date: str
    primary_driver: Literal["volume", "rate", "market", "unknown"]
    primary_driver_pct: Numeric
    key_findings: list[str]
    tpl_market_aligned: bool
    tpl_market_note: str

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "primary_driver_pct": ("pct", True),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


# =========================================================================
# Carry / RollDown
# =========================================================================


class CarryRollDownItem(BaseModel):
    category: str
    category_type: str
    market_value: Numeric
    weight: Numeric
    coupon_rate: Numeric
    ytm: Numeric | None = None
    funding_cost: Numeric
    carry: Numeric
    carry_pnl: Numeric
    duration: Numeric
    curve_slope: Numeric | None = None
    rolldown: Numeric
    rolldown_pnl: Numeric
    static_return: Numeric
    static_pnl: Numeric

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "market_value": ("yuan", False),
        "weight": ("ratio", False),
        "coupon_rate": ("pct", True),
        "ytm": ("pct", True),
        "funding_cost": ("pct", True),
        "carry": ("pct", True),
        "carry_pnl": ("yuan", True),
        "duration": ("ratio", False),
        "curve_slope": ("ratio", True),
        "rolldown": ("pct", True),
        "rolldown_pnl": ("yuan", True),
        "static_return": ("pct", True),
        "static_pnl": ("yuan", True),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class CarryRollDownPayload(BaseModel):
    report_date: str
    total_market_value: Numeric
    portfolio_carry: Numeric
    portfolio_rolldown: Numeric
    portfolio_static_return: Numeric
    total_carry_pnl: Numeric
    total_rolldown_pnl: Numeric
    total_static_pnl: Numeric
    ftp_rate: Numeric
    items: list[CarryRollDownItem]

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "total_market_value": ("yuan", False),
        "portfolio_carry": ("pct", True),
        "portfolio_rolldown": ("pct", True),
        "portfolio_static_return": ("pct", True),
        "total_carry_pnl": ("yuan", True),
        "total_rolldown_pnl": ("yuan", True),
        "total_static_pnl": ("yuan", True),
        "ftp_rate": ("pct", True),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


# =========================================================================
# Spread
# =========================================================================


class SpreadAttributionItem(BaseModel):
    category: str
    category_type: str
    market_value: Numeric
    duration: Numeric
    weight: Numeric
    yield_change: Numeric | None = None
    treasury_change: Numeric | None = None
    spread_change: Numeric | None = None
    treasury_effect: Numeric
    spread_effect: Numeric
    total_price_effect: Numeric
    treasury_contribution_pct: Numeric
    spread_contribution_pct: Numeric

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "market_value": ("yuan", False),
        "duration": ("ratio", False),
        "weight": ("ratio", False),
        "yield_change": ("pct", True),
        "treasury_change": ("pct", True),
        "spread_change": ("pct", True),
        "treasury_effect": ("yuan", True),
        "spread_effect": ("yuan", True),
        "total_price_effect": ("yuan", True),
        "treasury_contribution_pct": ("pct", True),
        "spread_contribution_pct": ("pct", True),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class SpreadAttributionPayload(BaseModel):
    report_date: str
    start_date: str
    end_date: str
    treasury_10y_start: Numeric | None = None
    treasury_10y_end: Numeric | None = None
    treasury_10y_change: Numeric | None = None
    total_market_value: Numeric
    portfolio_duration: Numeric
    total_treasury_effect: Numeric
    total_spread_effect: Numeric
    total_price_change: Numeric
    primary_driver: str
    interpretation: str
    items: list[SpreadAttributionItem]

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "treasury_10y_start": ("pct", True),
        "treasury_10y_end": ("pct", True),
        "treasury_10y_change": ("pct", True),
        "total_market_value": ("yuan", False),
        "portfolio_duration": ("ratio", False),
        "total_treasury_effect": ("yuan", True),
        "total_spread_effect": ("yuan", True),
        "total_price_change": ("yuan", True),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


# =========================================================================
# KRD
# =========================================================================


class KRDAttributionBucket(BaseModel):
    tenor: str
    tenor_years: Numeric
    market_value: Numeric
    weight: Numeric
    bond_count: int
    bucket_duration: Numeric
    krd: Numeric
    yield_change: Numeric | None = None
    duration_contribution: Numeric
    contribution_pct: Numeric

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "tenor_years": ("ratio", False),
        "market_value": ("yuan", False),
        "weight": ("ratio", False),
        "bucket_duration": ("ratio", False),
        "krd": ("ratio", True),
        "yield_change": ("pct", True),
        "duration_contribution": ("yuan", True),
        "contribution_pct": ("pct", True),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class KRDAttributionPayload(BaseModel):
    report_date: str
    start_date: str
    end_date: str
    total_market_value: Numeric
    portfolio_duration: Numeric
    portfolio_dv01: Numeric
    total_duration_effect: Numeric
    curve_shift_type: str
    curve_interpretation: str
    buckets: list[KRDAttributionBucket]
    max_contribution_tenor: str
    max_contribution_value: Numeric

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "total_market_value": ("yuan", False),
        "portfolio_duration": ("ratio", False),
        "portfolio_dv01": ("dv01", False),
        "total_duration_effect": ("yuan", True),
        "max_contribution_value": ("yuan", True),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


# =========================================================================
# AdvancedAttributionSummary
# =========================================================================


class AdvancedAttributionSummary(BaseModel):
    report_date: str
    portfolio_carry: Numeric
    portfolio_rolldown: Numeric
    static_return_annualized: Numeric
    treasury_effect_total: Numeric
    spread_effect_total: Numeric
    spread_driver: str
    max_krd_tenor: str
    curve_shape_change: str
    key_insights: list[str]

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "portfolio_carry": ("pct", True),
        "portfolio_rolldown": ("pct", True),
        "static_return_annualized": ("pct", True),
        "treasury_effect_total": ("yuan", True),
        "spread_effect_total": ("yuan", True),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


# =========================================================================
# Campisi
# =========================================================================


class CampisiAttributionItem(BaseModel):
    category: str
    market_value: Numeric
    weight: Numeric
    total_return: Numeric
    total_return_pct: Numeric
    income_return: Numeric
    income_return_pct: Numeric
    treasury_effect: Numeric
    treasury_effect_pct: Numeric
    spread_effect: Numeric
    spread_effect_pct: Numeric
    selection_effect: Numeric
    selection_effect_pct: Numeric

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "market_value": ("yuan", False),
        "weight": ("ratio", False),
        "total_return": ("yuan", True),
        "total_return_pct": ("pct", True),
        "income_return": ("yuan", True),
        "income_return_pct": ("pct", True),
        "treasury_effect": ("yuan", True),
        "treasury_effect_pct": ("pct", True),
        "spread_effect": ("yuan", True),
        "spread_effect_pct": ("pct", True),
        "selection_effect": ("yuan", True),
        "selection_effect_pct": ("pct", True),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class CampisiAttributionPayload(BaseModel):
    report_date: str
    period_start: str
    period_end: str
    num_days: int
    total_market_value: Numeric
    total_return: Numeric
    total_return_pct: Numeric
    total_income: Numeric
    total_treasury_effect: Numeric
    total_spread_effect: Numeric
    total_selection_effect: Numeric
    income_contribution_pct: Numeric
    treasury_contribution_pct: Numeric
    spread_contribution_pct: Numeric
    selection_contribution_pct: Numeric
    primary_driver: str
    interpretation: str
    items: list[CampisiAttributionItem]

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "total_market_value": ("yuan", False),
        "total_return": ("yuan", True),
        "total_return_pct": ("pct", True),
        "total_income": ("yuan", True),
        "total_treasury_effect": ("yuan", True),
        "total_spread_effect": ("yuan", True),
        "total_selection_effect": ("yuan", True),
        "income_contribution_pct": ("pct", True),
        "treasury_contribution_pct": ("pct", True),
        "spread_contribution_pct": ("pct", True),
        "selection_contribution_pct": ("pct", True),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)
