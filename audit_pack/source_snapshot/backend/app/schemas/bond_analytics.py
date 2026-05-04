"""Bond analytics Pydantic v2 models.

Wave 5.1 migrates governed numeric payload fields from legacy decimal-safe
``str`` / selected ``float`` values to ``Numeric`` while preserving current
service callsites. Each schema accepts legacy numeric strings / floats plus
native ``Numeric`` values, and serializes back to the shared Numeric shape.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, ClassVar, Optional

from pydantic import BaseModel, Field, model_validator

from backend.app.schemas.common_numeric import Numeric, NumericUnit, numeric_from_raw


def _coerce_value_to_numeric(value: Any, unit: NumericUnit, sign_aware: bool) -> Any:
    """Coerce legacy numeric inputs into a Numeric-compatible structure."""
    if value is None:
        return None
    if isinstance(value, Numeric):
        return value
    if isinstance(value, dict) and {"raw", "unit", "display", "precision", "sign_aware"} <= set(value.keys()):
        return value
    if isinstance(value, str):
        normalized = value.strip().replace(",", "")
        if not normalized:
            return None
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


class PeriodType(str, Enum):
    """Analysis period granularity."""

    MOM = "MoM"
    YTD = "YTD"
    TTM = "TTM"


class AssetClassBreakdown(BaseModel):
    """PnL decomposition for a single asset-class (or accounting-class) bucket."""

    asset_class: str
    carry: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="yuan", sign_aware=True))
    roll_down: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="yuan", sign_aware=True))
    rate_effect: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="yuan", sign_aware=True))
    spread_effect: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="yuan", sign_aware=True))
    convexity_effect: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="yuan", sign_aware=True))
    trading: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="yuan", sign_aware=True))
    total: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="yuan", sign_aware=True))
    bond_count: int = 0
    market_value: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="yuan", sign_aware=False))

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "carry": ("yuan", True),
        "roll_down": ("yuan", True),
        "rate_effect": ("yuan", True),
        "spread_effect": ("yuan", True),
        "convexity_effect": ("yuan", True),
        "trading": ("yuan", True),
        "total": ("yuan", True),
        "market_value": ("yuan", False),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class BondLevelDecomposition(BaseModel):
    """Per-bond PnL decomposition detail."""

    bond_code: str
    bond_name: Optional[str] = None
    asset_class: str
    accounting_class: str
    market_value: Numeric
    carry: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="yuan", sign_aware=True))
    roll_down: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="yuan", sign_aware=True))
    rate_effect: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="yuan", sign_aware=True))
    spread_effect: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="yuan", sign_aware=True))
    convexity_effect: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="yuan", sign_aware=True))
    trading: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="yuan", sign_aware=True))
    total: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="yuan", sign_aware=True))
    explained_for_recon: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="yuan", sign_aware=True))
    economic_only_effects: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="yuan", sign_aware=True))

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "market_value": ("yuan", False),
        "carry": ("yuan", True),
        "roll_down": ("yuan", True),
        "rate_effect": ("yuan", True),
        "spread_effect": ("yuan", True),
        "convexity_effect": ("yuan", True),
        "trading": ("yuan", True),
        "total": ("yuan", True),
        "explained_for_recon": ("yuan", True),
        "economic_only_effects": ("yuan", True),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class ReturnDecompositionResponse(BaseModel):
    """Return-decomposition (Campisi-style) response."""

    report_date: date
    period_type: str
    period_start: date
    period_end: date
    carry: Numeric = Field(description="Coupon + accrual contribution")
    roll_down: Numeric = Field(description="Roll-down return from curve aging")
    rate_effect: Numeric = Field(description="Risk-free rate movement effect")
    spread_effect: Numeric = Field(description="Credit spread movement effect")
    trading: Numeric = Field(description="Realised trading PnL")
    fx_effect: Numeric = Field(
        default_factory=lambda: numeric_from_raw(raw=0.0, unit="yuan", sign_aware=True),
        description="FX movement effect",
    )
    convexity_effect: Numeric = Field(
        default_factory=lambda: numeric_from_raw(raw=0.0, unit="yuan", sign_aware=True),
        description="Convexity residual",
    )
    explained_pnl: Numeric = Field(description="Sum of decomposed components")
    explained_pnl_accounting: Numeric = Field(
        default_factory=lambda: numeric_from_raw(raw=0.0, unit="yuan", sign_aware=True),
        description="Accounting-basis explained PnL",
    )
    explained_pnl_economic: Numeric = Field(
        default_factory=lambda: numeric_from_raw(raw=0.0, unit="yuan", sign_aware=True),
        description="Economic-basis explained PnL",
    )
    oci_reserve_impact: Numeric = Field(
        default_factory=lambda: numeric_from_raw(raw=0.0, unit="yuan", sign_aware=True),
        description="OCI reserve change (economic effect not hitting P&L)",
    )
    actual_pnl: Numeric = Field(description="Accounting-basis actual PnL")
    recon_error: Numeric = Field(description="Reconciliation gap = actual - explained")
    recon_error_pct: Numeric = Field(description="Reconciliation gap as percentage")
    by_asset_class: list[AssetClassBreakdown] = Field(default_factory=list, description="Breakdown by asset class")
    by_accounting_class: list[AssetClassBreakdown] = Field(
        default_factory=list,
        description="Breakdown by accounting class",
    )
    bond_details: list[BondLevelDecomposition] = Field(default_factory=list, description="Per-bond detail rows")
    bond_count: int = 0
    total_market_value: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="yuan", sign_aware=False))
    computed_at: str = ""
    warnings: list[str] = Field(default_factory=list, description="Warning messages")
    warnings_detail: list[dict[str, str]] = Field(
        default_factory=list,
        description="Structured warnings with stable codes (e.g., trading placeholder).",
    )

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "carry": ("yuan", True),
        "roll_down": ("yuan", True),
        "rate_effect": ("yuan", True),
        "spread_effect": ("yuan", True),
        "trading": ("yuan", True),
        "fx_effect": ("yuan", True),
        "convexity_effect": ("yuan", True),
        "explained_pnl": ("yuan", True),
        "explained_pnl_accounting": ("yuan", True),
        "explained_pnl_economic": ("yuan", True),
        "oci_reserve_impact": ("yuan", True),
        "actual_pnl": ("yuan", True),
        "recon_error": ("yuan", True),
        "recon_error_pct": ("pct", True),
        "total_market_value": ("yuan", False),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class ExcessSourceBreakdown(BaseModel):
    """Single source of excess return (Brinson attribution bucket)."""

    source: str
    contribution: Numeric
    description: str

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "contribution": ("bp", True),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class BenchmarkExcessResponse(BaseModel):
    """Benchmark excess-return decomposition response."""

    report_date: date
    period_type: str
    period_start: date
    period_end: date
    benchmark_id: str
    benchmark_name: str
    portfolio_return: Numeric
    benchmark_return: Numeric
    excess_return: Numeric
    tracking_error: Numeric | None = None
    information_ratio: Numeric | None = None
    duration_effect: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="bp", sign_aware=True))
    curve_effect: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="bp", sign_aware=True))
    spread_effect: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="bp", sign_aware=True))
    selection_effect: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="bp", sign_aware=True))
    allocation_effect: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="bp", sign_aware=True))
    explained_excess: Numeric
    recon_error: Numeric
    portfolio_duration: Numeric
    benchmark_duration: Numeric
    duration_diff: Numeric
    excess_sources: list[ExcessSourceBreakdown] = Field(default_factory=list, description="Excess-source detail rows")
    computed_at: str = ""
    warnings: list[str] = Field(default_factory=list, description="Warning messages")

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "portfolio_return": ("pct", True),
        "benchmark_return": ("pct", True),
        "excess_return": ("bp", True),
        "tracking_error": ("pct", False),
        "information_ratio": ("ratio", True),
        "duration_effect": ("bp", True),
        "curve_effect": ("bp", True),
        "spread_effect": ("bp", True),
        "selection_effect": ("bp", True),
        "allocation_effect": ("bp", True),
        "explained_excess": ("bp", True),
        "recon_error": ("bp", True),
        "portfolio_duration": ("ratio", False),
        "benchmark_duration": ("ratio", False),
        "duration_diff": ("ratio", True),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class KRDBucket(BaseModel):
    """Key-rate duration for a single tenor bucket."""

    tenor: str
    krd: Numeric
    dv01: Numeric
    market_value_weight: Numeric

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "krd": ("ratio", True),
        "dv01": ("dv01", False),
        "market_value_weight": ("ratio", False),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class ScenarioResult(BaseModel):
    """Result of a single curve-shock scenario."""

    scenario_name: str
    scenario_description: str
    shocks: dict[str, float]
    pnl_economic: Numeric
    pnl_oci: Numeric
    pnl_tpl: Numeric
    rate_contribution: Numeric
    convexity_contribution: Numeric
    by_asset_class: dict[str, dict[str, Numeric]] = Field(
        default_factory=dict,
        description="Nested breakdown by asset class",
    )

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "pnl_economic": ("yuan", True),
        "pnl_oci": ("yuan", True),
        "pnl_tpl": ("yuan", True),
        "rate_contribution": ("yuan", True),
        "convexity_contribution": ("yuan", True),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        out = _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)
        if not isinstance(out, dict):
            return out
        nested = out.get("by_asset_class")
        if isinstance(nested, dict):
            out["by_asset_class"] = {
                asset_class: {
                    metric_name: _coerce_value_to_numeric(metric_value, "yuan", True)
                    for metric_name, metric_value in metric_values.items()
                }
                for asset_class, metric_values in nested.items()
                if isinstance(metric_values, dict)
            }
        return out


class AssetClassRiskSummary(BaseModel):
    """Aggregated risk metrics for one asset class."""

    asset_class: str
    market_value: Numeric
    duration: Numeric
    dv01: Numeric
    weight: Numeric

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "market_value": ("yuan", False),
        "duration": ("ratio", False),
        "dv01": ("dv01", False),
        "weight": ("ratio", False),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class KRDCurveRiskResponse(BaseModel):
    """KRD / curve-risk analysis response."""

    report_date: date
    portfolio_duration: Numeric
    portfolio_modified_duration: Numeric
    portfolio_dv01: Numeric
    portfolio_convexity: Numeric
    krd_buckets: list[KRDBucket] = Field(default_factory=list, description="Key-rate duration buckets")
    scenarios: list[ScenarioResult] = Field(default_factory=list, description="Scenario analysis results")
    by_asset_class: list[AssetClassRiskSummary] = Field(
        default_factory=list,
        description="Risk summary by asset class",
    )
    computed_at: str = ""
    warnings: list[str] = Field(default_factory=list, description="Warning messages")

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "portfolio_duration": ("ratio", False),
        "portfolio_modified_duration": ("ratio", False),
        "portfolio_dv01": ("dv01", False),
        "portfolio_convexity": ("ratio", False),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class SpreadScenarioResult(BaseModel):
    """PnL impact of a parallel spread shock."""

    scenario_name: str
    spread_change_bp: Numeric
    pnl_impact: Numeric
    oci_impact: Numeric
    tpl_impact: Numeric

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "spread_change_bp": ("bp", True),
        "pnl_impact": ("yuan", True),
        "oci_impact": ("yuan", True),
        "tpl_impact": ("yuan", True),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class MigrationScenarioResult(BaseModel):
    """PnL impact of a hypothetical rating migration."""

    scenario_name: str
    from_rating: str
    to_rating: str
    affected_bonds: int
    affected_market_value: Numeric
    pnl_impact: Numeric
    oci_impact: Numeric | None = None

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "affected_market_value": ("yuan", False),
        "pnl_impact": ("yuan", True),
        "oci_impact": ("yuan", True),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class ConcentrationItem(BaseModel):
    """Single item in a concentration ranking."""

    name: str
    weight: Numeric
    market_value: Numeric

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "weight": ("ratio", False),
        "market_value": ("yuan", False),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class ConcentrationMetrics(BaseModel):
    """Concentration statistics for one dimension."""

    dimension: str
    hhi: Numeric
    top5_concentration: Numeric
    top_items: list[ConcentrationItem] = Field(default_factory=list, description="Top concentration items")

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "hhi": ("ratio", False),
        "top5_concentration": ("ratio", False),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class CreditSpreadMigrationResponse(BaseModel):
    """Credit spread sensitivity and migration risk response."""

    report_date: date
    credit_bond_count: int
    credit_market_value: Numeric
    credit_weight: Numeric
    rating_aa_and_below_weight: Numeric = Field(
        default_factory=lambda: numeric_from_raw(raw=0.0, unit="ratio", sign_aware=False),
        description=(
            "淇＄敤鍊轰腑璇勭骇涓?AA 鍙婁互涓嬶紙鍚?AA锛屼笉鍚?AA+锛夌殑甯傚€煎崰缁勫悎鎬诲競鍊硷紱"
            "鏈瘑鍒殑 rating 涓嶈鍏ュ垎瀛愩€?"
        ),
    )
    spread_dv01: Numeric
    weighted_avg_spread: Numeric
    weighted_avg_spread_duration: Numeric
    spread_scenarios: list[SpreadScenarioResult] = Field(default_factory=list, description="Spread scenario results")
    migration_scenarios: list[MigrationScenarioResult] = Field(
        default_factory=list,
        description="Migration scenario results",
    )
    concentration_by_issuer: Optional[ConcentrationMetrics] = None
    concentration_by_industry: Optional[ConcentrationMetrics] = None
    concentration_by_rating: Optional[ConcentrationMetrics] = None
    concentration_by_tenor: Optional[ConcentrationMetrics] = None
    oci_credit_exposure: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="yuan", sign_aware=False))
    oci_spread_dv01: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="dv01", sign_aware=False))
    oci_sensitivity_25bp: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="yuan", sign_aware=True))
    computed_at: str = ""
    warnings: list[str] = Field(default_factory=list, description="Warning messages")

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "credit_market_value": ("yuan", False),
        "credit_weight": ("ratio", False),
        "rating_aa_and_below_weight": ("ratio", False),
        "spread_dv01": ("dv01", False),
        "weighted_avg_spread": ("bp", False),
        "weighted_avg_spread_duration": ("ratio", False),
        "oci_credit_exposure": ("yuan", False),
        "oci_spread_dv01": ("dv01", False),
        "oci_sensitivity_25bp": ("yuan", True),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class ActionDetail(BaseModel):
    """Single trade-action detail row."""

    action_id: str
    action_type: str
    action_date: str
    bonds_involved: list[str]
    description: str
    pnl_economic: Numeric
    pnl_accounting: Numeric
    delta_duration: Numeric
    delta_dv01: Numeric
    delta_spread_dv01: Numeric
    opportunity_cost: Numeric | None = None
    opportunity_cost_method: Optional[str] = None

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "pnl_economic": ("yuan", True),
        "pnl_accounting": ("yuan", True),
        "delta_duration": ("ratio", True),
        "delta_dv01": ("dv01", True),
        "delta_spread_dv01": ("dv01", True),
        "opportunity_cost": ("yuan", True),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class ActionTypeSummary(BaseModel):
    """Aggregated stats for one action type."""

    action_type: str
    action_type_name: str
    action_count: int
    total_pnl_economic: Numeric
    total_pnl_accounting: Numeric
    avg_pnl_per_action: Numeric

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "total_pnl_economic": ("yuan", True),
        "total_pnl_accounting": ("yuan", True),
        "avg_pnl_per_action": ("yuan", True),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class ActionAttributionResponse(BaseModel):
    """Trade-action attribution response."""

    report_date: date
    period_type: str
    period_start: date
    period_end: date
    total_actions: int
    total_pnl_from_actions: Numeric
    by_action_type: list[ActionTypeSummary] = Field(default_factory=list, description="Summary by action type")
    action_details: list[ActionDetail] = Field(default_factory=list, description="Individual action details")
    period_start_duration: Numeric
    period_end_duration: Numeric
    duration_change_from_actions: Numeric
    period_start_dv01: Numeric
    period_end_dv01: Numeric
    status: str = "ready"
    available_components: list[str] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    blocked_components: list[str] = Field(default_factory=list)
    computed_at: str = ""
    warnings: list[str] = Field(default_factory=list, description="Warning messages")
    warnings_detail: list[dict[str, str]] = Field(
        default_factory=list,
        description="Structured warnings with stable codes (parallel to string warnings).",
    )

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "total_pnl_from_actions": ("yuan", True),
        "period_start_duration": ("ratio", False),
        "period_end_duration": ("ratio", False),
        "duration_change_from_actions": ("ratio", True),
        "period_start_dv01": ("dv01", False),
        "period_end_dv01": ("dv01", False),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


ACTION_TYPE_NAMES: dict[str, str] = {
    "ADD_DURATION": "加久期",
    "REDUCE_DURATION": "减久期",
    "SWITCH": "换券",
    "CREDIT_DOWN": "信用下沉",
    "CREDIT_UP": "信用上收",
    "TIMING_BUY": "择时买入",
    "TIMING_SELL": "择时卖出",
    "HEDGE": "对冲操作",
}


class AccountingClassAuditItem(BaseModel):
    """Single row comparing inferred vs mapped accounting classification."""

    asset_class: str
    position_count: int
    market_value: Numeric
    market_value_weight: Numeric
    infer_accounting_class: str
    map_accounting_class: str
    infer_rule_id: str
    infer_match: Optional[str] = None
    map_rule_id: str
    map_match: Optional[str] = None
    is_divergent: bool = False
    is_map_unclassified: bool = False

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "market_value": ("yuan", False),
        "market_value_weight": ("ratio", False),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class AccountingClassAuditResponse(BaseModel):
    """Accounting-class audit response."""

    report_date: date
    total_positions: int = 0
    total_market_value: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="yuan", sign_aware=False))
    distinct_asset_classes: int = 0
    divergent_asset_classes: int = 0
    divergent_position_count: int = 0
    divergent_market_value: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="yuan", sign_aware=False))
    map_unclassified_asset_classes: int = 0
    map_unclassified_position_count: int = 0
    map_unclassified_market_value: Numeric = Field(default_factory=lambda: numeric_from_raw(raw=0.0, unit="yuan", sign_aware=False))
    rows: list[AccountingClassAuditItem] = Field(default_factory=list, description="Audit detail rows")
    computed_at: str = ""
    warnings: list[str] = Field(default_factory=list, description="Warning messages")

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "total_market_value": ("yuan", False),
        "divergent_market_value": ("yuan", False),
        "map_unclassified_market_value": ("yuan", False),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class PortfolioHeadlinesResponse(BaseModel):
    """Cross-sectional portfolio KPIs and asset-class risk summary."""

    report_date: date
    total_market_value: Numeric
    weighted_ytm: Numeric = Field(description="MV-weighted YTM in percent points (e.g. 2.38 => 2.38%).")
    weighted_duration: Numeric = Field(description="MV-weighted modified duration (years).")
    weighted_coupon: Numeric = Field(description="MV-weighted coupon rate in percent points.")
    total_dv01: Numeric
    bond_count: int
    credit_weight: Numeric
    issuer_hhi: Numeric
    issuer_top5_weight: Numeric
    by_asset_class: list[AssetClassRiskSummary] = Field(default_factory=list)
    computed_at: str = ""
    warnings: list[str] = Field(default_factory=list, description="Warning messages")

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "total_market_value": ("yuan", False),
        "weighted_ytm": ("pct", True),
        "weighted_duration": ("ratio", False),
        "weighted_coupon": ("pct", True),
        "total_dv01": ("dv01", False),
        "credit_weight": ("ratio", False),
        "issuer_hhi": ("ratio", False),
        "issuer_top5_weight": ("ratio", False),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class BondTopHoldingItem(BaseModel):
    """Single row in top-holdings by market value."""

    instrument_code: str
    instrument_name: Optional[str] = None
    issuer_name: Optional[str] = None
    rating: Optional[str] = None
    asset_class: str
    market_value: Numeric
    face_value: Numeric
    ytm: Numeric
    modified_duration: Numeric
    weight: Numeric

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "market_value": ("yuan", False),
        "face_value": ("yuan", False),
        "ytm": ("pct", True),
        "modified_duration": ("ratio", False),
        "weight": ("ratio", False),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)


class BondTopHoldingsResponse(BaseModel):
    """Largest positions by market value."""

    report_date: date
    top_n: int
    items: list[BondTopHoldingItem] = Field(default_factory=list)
    total_market_value: Numeric
    computed_at: str = ""
    warnings: list[str] = Field(default_factory=list, description="Warning messages")

    _NUMERIC_FIELDS: ClassVar[dict[str, tuple[NumericUnit, bool]]] = {
        "total_market_value": ("yuan", False),
    }

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        return _apply_numeric_coercion(cls._NUMERIC_FIELDS, data)
