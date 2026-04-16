"""Pydantic mirrors of frontend `contracts.ts` PnL attribution payloads (numeric fields as float)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class VolumeRateAttributionItem(BaseModel):
    category: str
    category_type: str
    level: int
    current_scale: float
    current_pnl: float
    current_yield: float | None
    previous_scale: float | None
    previous_pnl: float | None
    previous_yield: float | None
    pnl_change: float | None
    pnl_change_pct: float | None
    volume_effect: float | None
    rate_effect: float | None
    interaction_effect: float | None
    attrib_sum: float | None
    recon_error: float | None
    volume_contribution_pct: float | None
    rate_contribution_pct: float | None


class VolumeRateAttributionPayload(BaseModel):
    current_period: str
    previous_period: str
    compare_type: str
    total_current_pnl: float
    total_previous_pnl: float | None
    total_pnl_change: float | None
    total_volume_effect: float | None
    total_rate_effect: float | None
    total_interaction_effect: float | None
    items: list[VolumeRateAttributionItem]
    has_previous_data: bool


class TPLMarketDataPoint(BaseModel):
    period: str
    period_label: str
    tpl_fair_value_change: float
    tpl_total_pnl: float
    tpl_scale: float
    treasury_10y: float | None
    treasury_10y_change: float | None
    dr007: float | None


class TPLMarketCorrelationPayload(BaseModel):
    start_period: str
    end_period: str
    num_periods: int
    correlation_coefficient: float | None
    correlation_interpretation: str
    total_tpl_fv_change: float
    avg_treasury_10y_change: float | None
    treasury_10y_total_change: float | None
    data_points: list[TPLMarketDataPoint]
    analysis_summary: str


class PnlCompositionItem(BaseModel):
    category: str
    category_type: str
    level: int
    total_pnl: float
    interest_income: float
    fair_value_change: float
    capital_gain: float
    other_income: float
    interest_pct: float
    fair_value_pct: float
    capital_gain_pct: float
    other_pct: float


class PnlCompositionTrendItem(BaseModel):
    period: str
    period_label: str
    interest_income: float
    fair_value_change: float
    capital_gain: float
    total_pnl: float


class PnlCompositionPayload(BaseModel):
    report_period: str
    report_date: str
    total_pnl: float
    total_interest_income: float
    total_fair_value_change: float
    total_capital_gain: float
    total_other_income: float
    interest_pct: float
    fair_value_pct: float
    capital_gain_pct: float
    other_pct: float
    items: list[PnlCompositionItem]
    trend_data: list[PnlCompositionTrendItem]


class PnlAttributionAnalysisSummary(BaseModel):
    report_date: str
    primary_driver: Literal["volume", "rate", "market", "unknown"]
    primary_driver_pct: float
    key_findings: list[str]
    tpl_market_aligned: bool
    tpl_market_note: str


class CarryRollDownItem(BaseModel):
    category: str
    category_type: str
    market_value: float
    weight: float
    coupon_rate: float
    ytm: float | None
    funding_cost: float
    carry: float
    carry_pnl: float
    duration: float
    curve_slope: float | None
    rolldown: float
    rolldown_pnl: float
    static_return: float
    static_pnl: float


class CarryRollDownPayload(BaseModel):
    report_date: str
    total_market_value: float
    portfolio_carry: float
    portfolio_rolldown: float
    portfolio_static_return: float
    total_carry_pnl: float
    total_rolldown_pnl: float
    total_static_pnl: float
    ftp_rate: float
    items: list[CarryRollDownItem]


class SpreadAttributionItem(BaseModel):
    category: str
    category_type: str
    market_value: float
    duration: float
    weight: float
    yield_change: float | None
    treasury_change: float | None
    spread_change: float | None
    treasury_effect: float
    spread_effect: float
    total_price_effect: float
    treasury_contribution_pct: float
    spread_contribution_pct: float


class SpreadAttributionPayload(BaseModel):
    report_date: str
    start_date: str
    end_date: str
    treasury_10y_start: float | None
    treasury_10y_end: float | None
    treasury_10y_change: float | None
    total_market_value: float
    portfolio_duration: float
    total_treasury_effect: float
    total_spread_effect: float
    total_price_change: float
    primary_driver: str
    interpretation: str
    items: list[SpreadAttributionItem]


class KRDAttributionBucket(BaseModel):
    tenor: str
    tenor_years: float
    market_value: float
    weight: float
    bond_count: int
    bucket_duration: float
    krd: float
    yield_change: float | None
    duration_contribution: float
    contribution_pct: float


class KRDAttributionPayload(BaseModel):
    report_date: str
    start_date: str
    end_date: str
    total_market_value: float
    portfolio_duration: float
    portfolio_dv01: float
    total_duration_effect: float
    curve_shift_type: str
    curve_interpretation: str
    buckets: list[KRDAttributionBucket]
    max_contribution_tenor: str
    max_contribution_value: float


class AdvancedAttributionSummary(BaseModel):
    report_date: str
    portfolio_carry: float
    portfolio_rolldown: float
    static_return_annualized: float
    treasury_effect_total: float
    spread_effect_total: float
    spread_driver: str
    max_krd_tenor: str
    curve_shape_change: str
    key_insights: list[str]


class CampisiAttributionItem(BaseModel):
    category: str
    market_value: float
    weight: float
    total_return: float
    total_return_pct: float
    income_return: float
    income_return_pct: float
    treasury_effect: float
    treasury_effect_pct: float
    spread_effect: float
    spread_effect_pct: float
    selection_effect: float
    selection_effect_pct: float


class CampisiAttributionPayload(BaseModel):
    report_date: str
    period_start: str
    period_end: str
    num_days: int
    total_market_value: float
    total_return: float
    total_return_pct: float
    total_income: float
    total_treasury_effect: float
    total_spread_effect: float
    total_selection_effect: float
    income_contribution_pct: float
    treasury_contribution_pct: float
    spread_contribution_pct: float
    selection_contribution_pct: float
    primary_driver: str
    interpretation: str
    items: list[CampisiAttributionItem]
