"""Wire contracts for the seven bond reads consumed by the desktop home.

Service construction models use Numeric internally. Most of these reads then
collapse those values to legacy Q8 strings; response validation must preserve
that representation rather than run the construction models' coercion again.
Position changes and yield curves retain Numeric JSON on the wire.
"""
from __future__ import annotations

from typing import Annotated, Literal

from backend.app.schemas.common_numeric import Numeric
from backend.app.schemas.result_meta import ResultMeta
from pydantic import BaseModel, ConfigDict, Field

Q8Text = Annotated[str, Field(pattern=r"^-?\d+\.\d{8}$")]


class _StrictBondReadModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class BondReadNumeric(Numeric):
    """Reuse Numeric without accepting or silently dropping undeclared keys."""

    model_config = ConfigDict(extra="forbid", strict=True)


class BondReadResultMeta(ResultMeta):
    model_config = ConfigDict(extra="forbid")


class _BondReadEnvelope(_StrictBondReadModel):
    result_meta: BondReadResultMeta


class _BondReadPayload(_StrictBondReadModel):
    report_date: str
    computed_at: str
    warnings: list[str]
    warning_codes: list[str] | None = None


class BondTopHoldingReadItem(_StrictBondReadModel):
    instrument_code: str
    instrument_name: str | None
    issuer_name: str | None
    rating: str | None
    asset_class: str
    market_value: Q8Text
    face_value: Q8Text
    ytm: Q8Text
    modified_duration: Q8Text | None
    duration_quality_flag: str | None
    maturity_category: str
    weight: Q8Text


class BondTopHoldingsReadPayload(_BondReadPayload):
    top_n: int
    items: list[BondTopHoldingReadItem]
    total_market_value: Q8Text


class BondTopHoldingsReadEnvelope(_BondReadEnvelope):
    result: BondTopHoldingsReadPayload


class BondPositionChangeReadItem(_StrictBondReadModel):
    instrument_code: str
    instrument_name: str | None
    issuer_name: str | None
    rating: str | None
    asset_class: str
    previous_market_value: BondReadNumeric
    current_market_value: BondReadNumeric
    change_market_value: BondReadNumeric
    previous_weight: BondReadNumeric
    current_weight: BondReadNumeric
    change_weight: BondReadNumeric
    direction: Literal["increase", "decrease", "flat"]
    reason_label: str
    source_status: Literal["ready", "empty", "stale"]


class BondPositionChangesReadPayload(_BondReadPayload):
    prev_report_date: str | None
    top_n: int
    source_status: Literal["ready", "empty", "stale"]
    items: list[BondPositionChangeReadItem]
    total_market_value: BondReadNumeric
    prev_total_market_value: BondReadNumeric


class BondPositionChangesReadEnvelope(_BondReadEnvelope):
    result: BondPositionChangesReadPayload


class BondAssetClassRiskReadSummary(_StrictBondReadModel):
    asset_class: str
    market_value: Q8Text
    duration: Q8Text
    dv01: Q8Text
    weight: Q8Text


class BondPortfolioHeadlinesReadPayload(_BondReadPayload):
    total_market_value: Q8Text
    weighted_ytm: Q8Text
    weighted_duration: Q8Text
    weighted_coupon: Q8Text
    total_dv01: Q8Text
    bond_count: int
    credit_weight: Q8Text
    issuer_hhi: Q8Text
    issuer_top5_weight: Q8Text
    by_asset_class: list[BondAssetClassRiskReadSummary]


class BondPortfolioHeadlinesReadEnvelope(_BondReadEnvelope):
    result: BondPortfolioHeadlinesReadPayload


class BondSpreadScenarioReadResult(_StrictBondReadModel):
    scenario_name: str
    spread_change_bp: BondReadNumeric
    pnl_impact: Q8Text
    oci_impact: Q8Text
    tpl_impact: Q8Text


class BondMigrationScenarioReadResult(_StrictBondReadModel):
    scenario_name: str
    from_rating: str
    to_rating: str
    affected_bonds: int
    affected_market_value: Q8Text
    pnl_impact: Q8Text
    oci_impact: Q8Text | None


class BondConcentrationReadItem(_StrictBondReadModel):
    name: str
    weight: Q8Text
    market_value: Q8Text


class BondConcentrationReadMetrics(_StrictBondReadModel):
    dimension: str
    hhi: Q8Text
    top5_concentration: Q8Text
    top_items: list[BondConcentrationReadItem]


class BondConcentrationReadDisplayLimits(_StrictBondReadModel):
    issuer_single_max: float
    issuer_top5_max: float
    hhi_warning: float
    below_aa_max: float
    credit_weight_max: float


class BondCreditSpreadMigrationReadPayload(_BondReadPayload):
    credit_bond_count: int
    credit_market_value: Q8Text
    credit_weight: Q8Text
    rating_aa_and_below_weight: Q8Text
    spread_dv01: Q8Text
    weighted_avg_spread: Q8Text
    weighted_avg_spread_duration: Q8Text
    spread_scenarios: list[BondSpreadScenarioReadResult]
    migration_scenarios: list[BondMigrationScenarioReadResult]
    concentration_by_issuer: BondConcentrationReadMetrics | None
    concentration_by_industry: BondConcentrationReadMetrics | None
    concentration_by_rating: BondConcentrationReadMetrics | None
    concentration_by_tenor: BondConcentrationReadMetrics | None
    display_limits: BondConcentrationReadDisplayLimits | None
    oci_credit_exposure: Q8Text
    oci_spread_dv01: Q8Text
    oci_sensitivity_25bp: Q8Text


class BondCreditSpreadMigrationReadEnvelope(_BondReadEnvelope):
    result: BondCreditSpreadMigrationReadPayload


class BondAssetClassReturnReadBreakdown(_StrictBondReadModel):
    asset_class: str
    carry: Q8Text
    roll_down: Q8Text
    rate_effect: Q8Text
    spread_effect: Q8Text
    convexity_effect: Q8Text
    trading: Q8Text
    total: Q8Text
    bond_count: int
    market_value: Q8Text


class BondReturnReadDetail(_StrictBondReadModel):
    bond_code: str
    bond_name: str | None
    asset_class: str
    accounting_class: str
    market_value: Q8Text
    carry: Q8Text
    roll_down: Q8Text
    rate_effect: Q8Text
    spread_effect: Q8Text
    convexity_effect: Q8Text
    trading: Q8Text
    total: Q8Text
    explained_for_recon: Q8Text
    economic_only_effects: Q8Text


class BondReturnReadWarning(_StrictBondReadModel):
    code: str
    level: str
    message: str | None = None
    component: str | None = None
    detail: str | None = None


class BondReturnDecompositionReadPayload(_BondReadPayload):
    period_type: str
    period_start: str
    period_end: str
    carry: Q8Text
    roll_down: Q8Text
    rate_effect: Q8Text
    spread_effect: Q8Text
    trading: Q8Text
    fx_effect: Q8Text
    convexity_effect: Q8Text
    explained_pnl: Q8Text
    explained_pnl_accounting: Q8Text
    explained_pnl_economic: Q8Text
    oci_reserve_impact: Q8Text
    actual_pnl: Q8Text
    recon_error: Q8Text
    recon_error_pct: Q8Text
    by_asset_class: list[BondAssetClassReturnReadBreakdown]
    by_accounting_class: list[BondAssetClassReturnReadBreakdown]
    bond_details: list[BondReturnReadDetail]
    bond_count: int
    total_market_value: Q8Text
    warnings_detail: list[BondReturnReadWarning]


class BondReturnDecompositionReadEnvelope(_BondReadEnvelope):
    result: BondReturnDecompositionReadPayload


class BondYieldCurveReadPoint(_StrictBondReadModel):
    tenor: str
    yield_pct: BondReadNumeric | None
    delta_bp_prev: BondReadNumeric | None


class BondYieldCurveReadCurve(_StrictBondReadModel):
    curve_type: str
    trade_date_requested: str
    trade_date_resolved: str | None
    points: list[BondYieldCurveReadPoint]
    source_version: str
    rule_version: str
    vendor_name: str
    vendor_version: str


class BondYieldCurveTermStructureReadPayload(_StrictBondReadModel):
    report_date: str
    curves: list[BondYieldCurveReadCurve]
    warnings: list[str]
    computed_at: str


class BondYieldCurveTermStructureReadEnvelope(_BondReadEnvelope):
    result: BondYieldCurveTermStructureReadPayload


class BondKRDReadBucket(_StrictBondReadModel):
    tenor: str
    avg_modified_duration: Q8Text
    dv01: Q8Text
    market_value_weight: Q8Text
    krd: Q8Text | None


class BondKRDReadScenarioAssetClass(_StrictBondReadModel):
    pnl_economic: Q8Text
    pnl_oci: Q8Text
    pnl_tpl: Q8Text


class BondKRDReadScenario(_StrictBondReadModel):
    scenario_name: str
    scenario_description: str
    shocks: dict[str, float]
    pnl_economic: Q8Text
    pnl_oci: Q8Text
    pnl_tpl: Q8Text
    rate_contribution: Q8Text
    convexity_contribution: Q8Text
    by_asset_class: dict[str, BondKRDReadScenarioAssetClass]


class BondKRDCurveRiskReadPayload(_BondReadPayload):
    portfolio_duration: Q8Text
    portfolio_modified_duration: Q8Text
    portfolio_dv01: Q8Text
    portfolio_convexity: Q8Text
    krd_buckets: list[BondKRDReadBucket]
    scenarios: list[BondKRDReadScenario]
    by_asset_class: list[BondAssetClassRiskReadSummary]


class BondKRDCurveRiskReadEnvelope(_BondReadEnvelope):
    result: BondKRDCurveRiskReadPayload
