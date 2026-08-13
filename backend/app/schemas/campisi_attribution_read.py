"""Response models for `/api/pnl-attribution/campisi/*`.

Derived from six observed runtime states per endpoint: an empty DuckDB, a
populated portfolio, and four degradation branches (no yield curve, missing
maturity dates, an unclosed formal-PnL bridge, and positions without coupon or
YTM). Fields that only some of those branches emit are optional here and the
routes serialize with `exclude_unset`, so "absent" stays absent instead of being
materialized as an explicit null.

`extra="forbid"` matches the rest of the contract gate: FastAPI would otherwise
drop an undeclared key silently with a 200, which on an attribution surface
means a missing effect nobody notices.

Two structures are deliberately left as keyed maps rather than fixed models:
`buckets` is keyed by maturity bucket label and `input_quality.missing_fields`
is keyed by whichever source columns were actually missing. Both are data-driven
key sets, so the outer map is governed and the inner row shape is pinned.
"""
from __future__ import annotations

from backend.app.schemas.result_meta import ResultMeta
from pydantic import BaseModel, ConfigDict

# JSON numbers arrive as either int or float depending on whether the effect
# computed to an exact zero. A smart union keeps each one as it was, so the
# serialized body is byte-identical to what the service produced.
Number = float | int


class _StrictCampisiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CampisiEffectAvailabilityDetail(_StrictCampisiModel):
    status: str
    reason: str | None = None
    basis: str | None = None
    unavailable_bonds: int | None = None
    unavailable_market_value_start: Number | None = None
    min_required_shared_tenors: int | None = None
    shared_positive_tenors: int | None = None


class CampisiEffectAvailability(_StrictCampisiModel):
    bonds: int
    accrued_interest: CampisiEffectAvailabilityDetail
    spread_effect: CampisiEffectAvailabilityDetail
    treasury_effect: CampisiEffectAvailabilityDetail
    # Only the enhanced shape carries these three amounts, and only the
    # formal-bridge path leaves them undecomposed, so the entries are optional:
    # their presence (`status="not_decomposed"`) is what tells a consumer the 0
    # is a framework artefact rather than an observed second-order contribution.
    convexity_effect: CampisiEffectAvailabilityDetail | None = None
    cross_effect: CampisiEffectAvailabilityDetail | None = None
    reinvestment_effect: CampisiEffectAvailabilityDetail | None = None


class CampisiDuplicateSideStat(_StrictCampisiModel):
    rows: int
    market_value: Number
    instrument_codes: int | None = None
    position_keys: int | None = None


class CampisiDuplicateStat(_StrictCampisiModel):
    start: CampisiDuplicateSideStat
    end: CampisiDuplicateSideStat


class CampisiMissingFieldStat(_StrictCampisiModel):
    rows: int
    market_value: Number


class CampisiMissingFields(_StrictCampisiModel):
    # Keys are the source columns that were actually missing, so the map is
    # data-driven; the per-column statistic is not.
    start: dict[str, CampisiMissingFieldStat]
    end: dict[str, CampisiMissingFieldStat]


class CampisiCreditSpreadCoverageRow(_StrictCampisiModel):
    field: str
    rating: str
    positions: int
    market_value_start: Number
    start_available: bool
    end_available: bool
    missing_sides: list[str] | None = None


class CampisiTreasuryEffectCoverage(_StrictCampisiModel):
    status: str
    reason: str | None = None
    start_curve_rows_present: bool
    end_curve_rows_present: bool
    start_usable_tenors: int
    end_usable_tenors: int
    shared_positive_tenors: int


class CampisiTreasuryTenorCoverage(_StrictCampisiModel):
    required_keys: list[str]
    start_missing: list[str]
    end_missing: list[str]
    shared_positive_tenors: int


class CampisiMarketCurveCoverage(_StrictCampisiModel):
    treasury_effect: CampisiTreasuryEffectCoverage
    treasury_tenors: CampisiTreasuryTenorCoverage
    required_credit_spread_3y: list[CampisiCreditSpreadCoverageRow]
    missing_credit_spread_3y: list[CampisiCreditSpreadCoverageRow]


class CampisiInputQuality(_StrictCampisiModel):
    start_rows: int
    end_rows: int
    merged_positions: int
    position_key_fields: list[str]
    duplicate_instrument_codes: CampisiDuplicateStat
    duplicate_position_keys: CampisiDuplicateStat
    missing_fields: CampisiMissingFields
    market_curve_coverage: CampisiMarketCurveCoverage
    warnings: list[str]


class CampisiFormalClosure(_StrictCampisiModel):
    basis: str
    report_date: str
    status: str
    campisi_total_return: Number
    formal_actual_pnl: Number
    residual_to_formal_pnl: Number
    residual_ratio: Number
    bridge_quality_flag: str
    bridge_vendor_status: str
    bridge_fallback_mode: str
    message: str


class CampisiFourEffectsTotals(_StrictCampisiModel):
    market_value_start: Number
    income_return: Number
    treasury_effect: Number
    spread_effect: Number
    selection_effect: Number
    total_return: Number


class CampisiEnhancedTotals(CampisiFourEffectsTotals):
    # The empty-portfolio branch of `/campisi/enhanced` returns the plain
    # four-effects totals, without the three enhanced effects.
    convexity_effect: Number | None = None
    cross_effect: Number | None = None
    reinvestment_effect: Number | None = None


class CampisiFourEffectsAssetClassRow(_StrictCampisiModel):
    asset_class: str
    market_value_start: Number
    weight_pct: Number
    income_return: Number
    income_return_pct: Number
    treasury_effect: Number
    treasury_effect_pct: Number
    spread_effect: Number
    spread_effect_pct: Number
    selection_effect: Number
    selection_effect_pct: Number
    total_return: Number
    total_return_pct: Number | None = None


class CampisiEnhancedAssetClassRow(CampisiFourEffectsAssetClassRow):
    convexity_effect: Number
    convexity_effect_pct: Number
    cross_effect: Number
    cross_effect_pct: Number
    reinvestment_effect: Number
    reinvestment_effect_pct: Number


class CampisiFourEffectsBondRow(_StrictCampisiModel):
    bond_code: str
    asset_class: str
    maturity_bucket: str
    mod_duration: Number
    market_value_start: Number
    income_return: Number
    treasury_effect: Number
    spread_effect: Number
    selection_effect: Number
    total_return: Number
    has_accrued_interest: bool
    treasury_effect_available: bool
    spread_effect_available: bool


class CampisiEnhancedBondRow(CampisiFourEffectsBondRow):
    convexity_effect: Number
    cross_effect: Number
    reinvestment_effect: Number


class CampisiFourEffectsPayload(_StrictCampisiModel):
    period_start: str
    period_end: str
    report_date: str
    num_days: int
    totals: CampisiFourEffectsTotals
    by_asset_class: list[CampisiFourEffectsAssetClassRow]
    by_bond: list[CampisiFourEffectsBondRow]
    warnings: list[str]
    # Emitted only once there is at least one position to analyse.
    diagnostics: list[str] | None = None
    effect_availability: CampisiEffectAvailability | None = None
    formal_closure: CampisiFormalClosure | None = None
    input_quality: CampisiInputQuality | None = None


class CampisiFourEffectsReadEnvelope(_StrictCampisiModel):
    result_meta: ResultMeta
    result: CampisiFourEffectsPayload


class CampisiEnhancedPayload(_StrictCampisiModel):
    period_start: str
    period_end: str
    report_date: str
    num_days: int
    totals: CampisiEnhancedTotals
    by_asset_class: list[CampisiEnhancedAssetClassRow]
    by_bond: list[CampisiEnhancedBondRow]
    warnings: list[str]
    diagnostics: list[str] | None = None
    effect_availability: CampisiEffectAvailability | None = None
    input_quality: CampisiInputQuality | None = None


class CampisiEnhancedEnvelope(_StrictCampisiModel):
    result_meta: ResultMeta
    result: CampisiEnhancedPayload


class CampisiMaturityBucketRow(_StrictCampisiModel):
    market_value_start: Number
    income_return: Number
    treasury_effect: Number
    spread_effect: Number
    selection_effect: Number
    total_return: Number


class CampisiMaturityBucketPayload(_StrictCampisiModel):
    period_start: str
    period_end: str
    # Keyed by maturity bucket label (`0-1Y` … `10Y+`, plus `UNKNOWN` for
    # positions with no maturity date), which is data-driven.
    buckets: dict[str, CampisiMaturityBucketRow]
    warnings: list[str] | None = None
    input_quality: CampisiInputQuality | None = None


class CampisiMaturityBucketEnvelope(_StrictCampisiModel):
    result_meta: ResultMeta
    result: CampisiMaturityBucketPayload
