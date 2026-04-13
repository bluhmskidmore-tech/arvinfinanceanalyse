"""
Bond Analytics Pydantic v2 models.

Covers 6 analytical sub-modules plus an accounting-class audit view:

1. Return Decomposition  -- PnL attribution by carry / roll / rate / spread / trading
2. Benchmark Excess      -- portfolio vs benchmark, Brinson-style decomposition
3. KRD Curve Risk        -- key-rate duration, DV01, scenario analysis
4. Credit Spread Migration -- spread sensitivity, rating migration, concentration
5. Action Attribution    -- trade-action PnL and risk-delta attribution
6. Accounting Class Audit -- inferred vs mapped accounting classification check

All monetary / rate / ratio fields are serialised as str (Decimal-safe).
Response models carry report_date, computed_at, and warnings but do
**not** embed ResultMeta -- the V3 API envelope adds that separately.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class PeriodType(str, Enum):
    """Analysis period granularity."""

    MOM = "MoM"   # Month over Month
    YTD = "YTD"   # Year to Date
    TTM = "TTM"   # Trailing Twelve Months


# ---------------------------------------------------------------------------
# Module 1: Return Decomposition
# ---------------------------------------------------------------------------

class AssetClassBreakdown(BaseModel):
    """PnL decomposition for a single asset-class (or accounting-class) bucket."""

    asset_class: str
    carry: str = "0"
    roll_down: str = "0"
    rate_effect: str = "0"
    spread_effect: str = "0"
    convexity_effect: str = "0"
    trading: str = "0"
    total: str = "0"
    bond_count: int = 0
    market_value: str = "0"


class BondLevelDecomposition(BaseModel):
    """Per-bond PnL decomposition detail."""

    bond_code: str
    bond_name: Optional[str] = None
    asset_class: str
    accounting_class: str
    market_value: str
    carry: str = "0"
    roll_down: str = "0"
    rate_effect: str = "0"
    spread_effect: str = "0"
    convexity_effect: str = "0"
    trading: str = "0"
    total: str = "0"
    explained_for_recon: str = "0"
    economic_only_effects: str = "0"


class ReturnDecompositionResponse(BaseModel):
    """Return-decomposition (Campisi-style) response."""

    report_date: date
    period_type: str
    period_start: date
    period_end: date

    # Core decomposition (CNY)
    carry: str = Field(description="Coupon + accrual contribution")
    roll_down: str = Field(description="Roll-down return from curve aging")
    rate_effect: str = Field(description="Risk-free rate movement effect")
    spread_effect: str = Field(description="Credit spread movement effect")
    trading: str = Field(description="Realised trading PnL")
    fx_effect: str = Field(default="0", description="FX movement effect")
    convexity_effect: str = Field(default="0", description="Convexity residual")

    # Reconciliation
    explained_pnl: str = Field(description="Sum of decomposed components")
    explained_pnl_accounting: str = Field(default="0", description="Accounting-basis explained PnL")
    explained_pnl_economic: str = Field(default="0", description="Economic-basis explained PnL")
    oci_reserve_impact: str = Field(
        default="0",
        description="OCI reserve change (economic effect not hitting P&L)",
    )
    actual_pnl: str = Field(description="Accounting-basis actual PnL")
    recon_error: str = Field(description="Reconciliation gap = actual - explained")
    recon_error_pct: str = Field(description="Reconciliation gap as percentage")

    # Bucketed breakdowns
    by_asset_class: list[AssetClassBreakdown] = Field(
        default_factory=list, description="Breakdown by asset class",
    )
    by_accounting_class: list[AssetClassBreakdown] = Field(
        default_factory=list, description="Breakdown by accounting class",
    )
    bond_details: list[BondLevelDecomposition] = Field(
        default_factory=list, description="Per-bond detail rows",
    )

    # Metadata
    bond_count: int = 0
    total_market_value: str = "0"
    computed_at: str = ""
    warnings: list[str] = Field(default_factory=list, description="Warning messages")


# ---------------------------------------------------------------------------
# Module 2: Benchmark Excess
# ---------------------------------------------------------------------------

class ExcessSourceBreakdown(BaseModel):
    """Single source of excess return (Brinson attribution bucket)."""

    source: str  # duration / curve / spread / selection / allocation
    contribution: str  # bp
    description: str


class BenchmarkExcessResponse(BaseModel):
    """Benchmark excess-return decomposition response."""

    report_date: date
    period_type: str
    period_start: date
    period_end: date
    benchmark_id: str
    benchmark_name: str

    # Returns
    portfolio_return: str  # %
    benchmark_return: str  # %
    excess_return: str     # bp

    # Risk metrics
    tracking_error: Optional[str] = None
    information_ratio: Optional[str] = None

    # Excess decomposition (bp)
    duration_effect: str = "0"
    curve_effect: str = "0"
    spread_effect: str = "0"
    selection_effect: str = "0"
    allocation_effect: str = "0"

    # Reconciliation
    explained_excess: str
    recon_error: str

    # Duration comparison
    portfolio_duration: str
    benchmark_duration: str
    duration_diff: str

    excess_sources: list[ExcessSourceBreakdown] = Field(
        default_factory=list, description="Excess-source detail rows",
    )
    computed_at: str = ""
    warnings: list[str] = Field(default_factory=list, description="Warning messages")



# ---------------------------------------------------------------------------
# Module 3: KRD Curve Risk
# ---------------------------------------------------------------------------

class KRDBucket(BaseModel):
    """Key-rate duration for a single tenor bucket."""

    tenor: str       # "1Y", "2Y", "3Y", ...
    krd: str
    dv01: str        # CNY per bp
    market_value_weight: str


class ScenarioResult(BaseModel):
    """Result of a single curve-shock scenario."""

    scenario_name: str
    scenario_description: str
    shocks: dict[str, float]  # e.g. {"1Y": 50, "10Y": 50}

    pnl_economic: str
    pnl_oci: str
    pnl_tpl: str

    rate_contribution: str
    convexity_contribution: str

    by_asset_class: dict[str, dict[str, str]] = Field(
        default_factory=dict, description="Nested breakdown by asset class",
    )


class AssetClassRiskSummary(BaseModel):
    """Aggregated risk metrics for one asset class."""

    asset_class: str
    market_value: str
    duration: str
    dv01: str
    weight: str


class KRDCurveRiskResponse(BaseModel):
    """KRD / curve-risk analysis response."""

    report_date: date

    # Portfolio-level risk metrics
    portfolio_duration: str
    portfolio_modified_duration: str
    portfolio_dv01: str        # CNY per bp
    portfolio_convexity: str

    # KRD distribution
    krd_buckets: list[KRDBucket] = Field(
        default_factory=list, description="Key-rate duration buckets",
    )

    # Scenario analysis
    scenarios: list[ScenarioResult] = Field(
        default_factory=list, description="Scenario analysis results",
    )

    # By asset class
    by_asset_class: list[AssetClassRiskSummary] = Field(
        default_factory=list, description="Risk summary by asset class",
    )

    computed_at: str = ""
    warnings: list[str] = Field(default_factory=list, description="Warning messages")



# ---------------------------------------------------------------------------
# Module 4: Credit Spread Migration
# ---------------------------------------------------------------------------

class SpreadScenarioResult(BaseModel):
    """PnL impact of a parallel spread shock."""

    scenario_name: str
    spread_change_bp: float
    pnl_impact: str
    oci_impact: str
    tpl_impact: str


class MigrationScenarioResult(BaseModel):
    """PnL impact of a hypothetical rating migration."""

    scenario_name: str
    from_rating: str
    to_rating: str
    affected_bonds: int
    affected_market_value: str
    pnl_impact: str
    oci_impact: Optional[str] = None


class ConcentrationItem(BaseModel):
    """Single item in a concentration ranking."""

    name: str
    weight: str
    market_value: str


class ConcentrationMetrics(BaseModel):
    """Concentration statistics for one dimension."""

    dimension: str  # issuer / industry / rating / tenor
    hhi: str
    top5_concentration: str
    top_items: list[ConcentrationItem] = Field(
        default_factory=list, description="Top concentration items",
    )


class CreditSpreadMigrationResponse(BaseModel):
    """Credit spread sensitivity and migration risk response."""

    report_date: date

    # Credit bond summary
    credit_bond_count: int
    credit_market_value: str
    credit_weight: str
    rating_aa_and_below_weight: str = Field(
        default="0",
        description=(
            "信用债中评级为 AA 及以下（含 AA，不含 AA+）的市值占组合总市值；"
            "未识别的 rating 不计入分子。"
        ),
    )

    # Spread sensitivity
    spread_dv01: str                    # CNY per bp
    weighted_avg_spread: str            # bp
    weighted_avg_spread_duration: str

    # Spread scenarios
    spread_scenarios: list[SpreadScenarioResult] = Field(
        default_factory=list, description="Spread scenario results",
    )

    # Rating migration scenarios
    migration_scenarios: list[MigrationScenarioResult] = Field(
        default_factory=list, description="Migration scenario results",
    )

    # Concentration
    concentration_by_issuer: Optional[ConcentrationMetrics] = None
    concentration_by_industry: Optional[ConcentrationMetrics] = None
    concentration_by_rating: Optional[ConcentrationMetrics] = None
    concentration_by_tenor: Optional[ConcentrationMetrics] = None

    # OCI sensitivity
    oci_credit_exposure: str = "0"
    oci_spread_dv01: str = "0"
    oci_sensitivity_25bp: str = "0"

    computed_at: str = ""
    warnings: list[str] = Field(default_factory=list, description="Warning messages")



# ---------------------------------------------------------------------------
# Module 5: Action Attribution
# ---------------------------------------------------------------------------

class ActionDetail(BaseModel):
    """Single trade-action detail row."""

    action_id: str
    action_type: str
    action_date: str
    bonds_involved: list[str]
    description: str

    pnl_economic: str
    pnl_accounting: str

    delta_duration: str
    delta_dv01: str
    delta_spread_dv01: str

    opportunity_cost: Optional[str] = None
    opportunity_cost_method: Optional[str] = None


class ActionTypeSummary(BaseModel):
    """Aggregated stats for one action type."""

    action_type: str
    action_type_name: str
    action_count: int
    total_pnl_economic: str
    total_pnl_accounting: str
    avg_pnl_per_action: str


class ActionAttributionResponse(BaseModel):
    """Trade-action attribution response."""

    report_date: date
    period_type: str
    period_start: date
    period_end: date

    # Summary
    total_actions: int
    total_pnl_from_actions: str

    # By action type
    by_action_type: list[ActionTypeSummary] = Field(
        default_factory=list, description="Summary by action type",
    )

    # Detail rows
    action_details: list[ActionDetail] = Field(
        default_factory=list, description="Individual action details",
    )

    # Risk change over period
    period_start_duration: str
    period_end_duration: str
    duration_change_from_actions: str
    period_start_dv01: str
    period_end_dv01: str

    computed_at: str = ""
    warnings: list[str] = Field(default_factory=list, description="Warning messages")



# ---------------------------------------------------------------------------
# Action type Chinese display names
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Module 6: Accounting Class Audit
# ---------------------------------------------------------------------------

class AccountingClassAuditItem(BaseModel):
    """Single row comparing inferred vs mapped accounting classification."""

    asset_class: str
    position_count: int
    market_value: str
    market_value_weight: str
    infer_accounting_class: str
    map_accounting_class: str
    infer_rule_id: str
    infer_match: Optional[str] = None
    map_rule_id: str
    map_match: Optional[str] = None
    is_divergent: bool = False
    is_map_unclassified: bool = False


class AccountingClassAuditResponse(BaseModel):
    """Accounting-class audit response."""

    report_date: date
    total_positions: int = 0
    total_market_value: str = "0"
    distinct_asset_classes: int = 0
    divergent_asset_classes: int = 0
    divergent_position_count: int = 0
    divergent_market_value: str = "0"
    map_unclassified_asset_classes: int = 0
    map_unclassified_position_count: int = 0
    map_unclassified_market_value: str = "0"
    rows: list[AccountingClassAuditItem] = Field(
        default_factory=list, description="Audit detail rows",
    )
    computed_at: str = ""
    warnings: list[str] = Field(default_factory=list, description="Warning messages")
