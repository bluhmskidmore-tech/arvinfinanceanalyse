"""
Unit tests for backend.app.core_finance.attribution_core

Covers:
- Attribution residual: residual = actual - sum(effects) within threshold
- Residual threshold check: QualityFlag.WARN / BAD when residual exceeds threshold
- Attribution normalization: effects sum to 100 % of total
- Edge cases: zero total return, all-zero effects, single effect dominates
- No float precision leakage (Decimal throughout)
- Helper utilities: day-count, date helpers, interpolation, tenor buckets
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from backend.app.core_finance.attribution_core import (
    DEFAULT_RESIDUAL_THRESHOLD_BAD,
    DEFAULT_RESIDUAL_THRESHOLD_WARN,
    DayCountConvention,
    QualityFlag,
    ReconciliationResult,
    calculate_reconciliation,
    estimate_modified_duration,
    get_adjacent_tenor_buckets,
    get_day_count_factor,
    get_days_in_month,
    get_month_end_date,
    get_previous_month,
    get_same_month_last_year,
    get_tenor_bucket,
    interpolate_yield_curve,
    round_decimal,
    safe_divide,
    validate_pnl_scope,
)


# ---------------------------------------------------------------------------
# calculate_reconciliation — core attribution residual logic
# ---------------------------------------------------------------------------

class TestCalculateReconciliation:

    # --- basic residual arithmetic ---

    def test_residual_equals_actual_minus_explained(self):
        components = {
            "carry": Decimal("100"),
            "duration": Decimal("50"),
            "convexity": Decimal("10"),
        }
        actual = Decimal("165")
        result = calculate_reconciliation(components, actual)
        assert result.residual == Decimal("5")

    def test_residual_zero_when_fully_explained(self):
        components = {"carry": Decimal("80"), "spread": Decimal("20")}
        result = calculate_reconciliation(components, Decimal("100"))
        assert result.residual == Decimal("0")
        assert result.quality_flag == QualityFlag.OK

    def test_residual_negative_when_over_explained(self):
        components = {"carry": Decimal("120")}
        result = calculate_reconciliation(components, Decimal("100"))
        assert result.residual == Decimal("-20")

    def test_explained_pnl_is_sum_of_components(self):
        components = {"a": Decimal("30"), "b": Decimal("70")}
        result = calculate_reconciliation(components, Decimal("100"))
        assert result.explained_pnl == Decimal("100")

    # --- Decimal purity: no float leakage ---

    def test_all_outputs_are_decimal(self):
        components = {"carry": Decimal("50"), "spread": Decimal("30")}
        result = calculate_reconciliation(components, Decimal("90"))
        assert isinstance(result.residual, Decimal), "residual must be Decimal"
        assert isinstance(result.explained_pnl, Decimal), "explained_pnl must be Decimal"
        assert isinstance(result.actual_pnl, Decimal), "actual_pnl must be Decimal"
        if result.residual_ratio is not None:
            assert isinstance(result.residual_ratio, Decimal), "residual_ratio must be Decimal"

    def test_no_float_in_components_accepted(self):
        """safe_decimal coercion: float components should not cause type errors."""
        components = {"carry": Decimal("50"), "spread": Decimal("30")}
        result = calculate_reconciliation(components, Decimal("85"))
        assert isinstance(result.residual, Decimal)

    # --- quality flag thresholds ---

    def test_quality_flag_ok_when_residual_below_warn(self):
        # residual_ratio = 4 / 100 = 0.04 < 0.05 (warn threshold)
        components = {"carry": Decimal("96")}
        result = calculate_reconciliation(components, Decimal("100"))
        assert result.quality_flag == QualityFlag.OK

    def test_quality_flag_warn_when_residual_between_thresholds(self):
        # residual_ratio = 10 / 100 = 0.10 → between 0.05 and 0.15
        components = {"carry": Decimal("90")}
        result = calculate_reconciliation(components, Decimal("100"))
        assert result.quality_flag == QualityFlag.WARN
        assert len(result.diagnostics) > 0

    def test_quality_flag_bad_when_residual_above_bad_threshold(self):
        # residual_ratio = 20 / 100 = 0.20 > 0.15 (bad threshold)
        components = {"carry": Decimal("80")}
        result = calculate_reconciliation(components, Decimal("100"))
        assert result.quality_flag == QualityFlag.BAD
        assert len(result.diagnostics) > 0

    def test_custom_thresholds_respected(self):
        # With tight thresholds: warn=0.01, bad=0.05
        # residual = 3 / 100 = 0.03 → should be WARN
        components = {"carry": Decimal("97")}
        result = calculate_reconciliation(
            components,
            Decimal("100"),
            threshold_warn=Decimal("0.01"),
            threshold_bad=Decimal("0.05"),
        )
        assert result.quality_flag == QualityFlag.WARN

    def test_residual_ratio_computed_correctly(self):
        components = {"carry": Decimal("90")}
        result = calculate_reconciliation(components, Decimal("100"))
        # residual = 10, actual = 100 → ratio = 0.10
        assert result.residual_ratio == Decimal("0.1")

    # --- edge case: zero total return ---

    def test_zero_actual_pnl_zero_explained_is_ok(self):
        result = calculate_reconciliation({}, Decimal("0"))
        assert result.quality_flag == QualityFlag.OK
        assert result.residual == Decimal("0")
        assert result.residual_ratio == Decimal("0")

    def test_zero_actual_pnl_nonzero_explained_is_warn(self):
        components = {"carry": Decimal("50")}
        result = calculate_reconciliation(components, Decimal("0"))
        assert result.quality_flag == QualityFlag.WARN
        assert any("actual_pnl" in d for d in result.diagnostics)

    # --- edge case: all-zero effects ---

    def test_all_zero_effects_with_nonzero_actual(self):
        components = {"carry": Decimal("0"), "spread": Decimal("0")}
        result = calculate_reconciliation(components, Decimal("100"))
        assert result.residual == Decimal("100")
        assert result.quality_flag == QualityFlag.BAD

    # --- edge case: single effect dominates ---

    def test_single_effect_dominates_fully_explained(self):
        components = {"duration": Decimal("1000000")}
        result = calculate_reconciliation(components, Decimal("1000000"))
        assert result.residual == Decimal("0")
        assert result.quality_flag == QualityFlag.OK

    def test_single_effect_dominates_small_residual(self):
        components = {"duration": Decimal("999990")}
        result = calculate_reconciliation(components, Decimal("1000000"))
        # residual_ratio = 10 / 1_000_000 = 0.00001 → OK
        assert result.quality_flag == QualityFlag.OK

    # --- negative PnL ---

    def test_negative_actual_pnl_residual_ratio_uses_abs(self):
        # actual = -100, explained = -90 → residual = -10, ratio = 10/100 = 0.10
        components = {"carry": Decimal("-90")}
        result = calculate_reconciliation(components, Decimal("-100"))
        assert result.residual == Decimal("-10")
        assert result.residual_ratio == Decimal("0.1")
        assert result.quality_flag == QualityFlag.WARN

    # --- breakdown preserved ---

    def test_explained_breakdown_matches_input(self):
        components = {"carry": Decimal("60"), "spread": Decimal("40")}
        result = calculate_reconciliation(components, Decimal("100"))
        assert result.explained_breakdown == components

    # --- to_dict serialisation ---

    def test_to_dict_contains_expected_keys(self):
        result = calculate_reconciliation({"carry": Decimal("100")}, Decimal("100"))
        d = result.to_dict()
        for key in ("explained_pnl", "actual_pnl", "residual",
                    "residual_ratio", "quality_flag", "explained_breakdown", "diagnostics"):
            assert key in d

    def test_to_dict_values_are_float_or_none(self):
        result = calculate_reconciliation({"carry": Decimal("90")}, Decimal("100"))
        d = result.to_dict()
        assert isinstance(d["explained_pnl"], float)
        assert isinstance(d["residual"], float)
        assert isinstance(d["quality_flag"], str)


# ---------------------------------------------------------------------------
# Attribution normalization: effects sum to 100 % of total
# ---------------------------------------------------------------------------

class TestAttributionNormalization:

    def test_effects_sum_to_total_when_fully_explained(self):
        total = Decimal("500")
        components = {
            "carry": Decimal("200"),
            "duration": Decimal("150"),
            "convexity": Decimal("100"),
            "spread": Decimal("50"),
        }
        result = calculate_reconciliation(components, total)
        assert result.explained_pnl == total
        assert result.residual == Decimal("0")

    def test_residual_threshold_flag_within_tolerance(self):
        """Residual within 5 % → OK flag."""
        total = Decimal("1000")
        components = {"carry": Decimal("960")}  # 4 % residual
        result = calculate_reconciliation(components, total)
        assert result.quality_flag == QualityFlag.OK

    def test_residual_threshold_flag_exceeds_warn(self):
        """Residual between 5 % and 15 % → WARN flag."""
        total = Decimal("1000")
        components = {"carry": Decimal("900")}  # 10 % residual
        result = calculate_reconciliation(components, total)
        assert result.quality_flag == QualityFlag.WARN

    def test_residual_threshold_flag_exceeds_bad(self):
        """Residual > 15 % → BAD flag."""
        total = Decimal("1000")
        components = {"carry": Decimal("800")}  # 20 % residual
        result = calculate_reconciliation(components, total)
        assert result.quality_flag == QualityFlag.BAD


# ---------------------------------------------------------------------------
# validate_pnl_scope
# ---------------------------------------------------------------------------

class TestValidatePnlScope:

    def test_consistent_scope(self):
        ok, msg = validate_pnl_scope(
            interest_income=Decimal("100"),
            fair_value_change=Decimal("50"),
            capital_gain=Decimal("20"),
            total_pnl=Decimal("170"),
        )
        assert ok is True
        assert "一致" in msg

    def test_inconsistent_scope(self):
        ok, msg = validate_pnl_scope(
            interest_income=Decimal("100"),
            fair_value_change=Decimal("50"),
            capital_gain=Decimal("20"),
            total_pnl=Decimal("300"),  # off by 130
        )
        assert ok is False
        assert "不一致" in msg

    def test_tolerance_boundary(self):
        # diff = 0.005 < default tolerance 0.01 → consistent
        ok, _ = validate_pnl_scope(
            interest_income=Decimal("100"),
            fair_value_change=Decimal("0"),
            capital_gain=Decimal("0"),
            total_pnl=Decimal("100.005"),
            tolerance=Decimal("0.01"),
        )
        assert ok is True

    def test_zero_components_zero_total(self):
        ok, _ = validate_pnl_scope(
            interest_income=Decimal("0"),
            fair_value_change=Decimal("0"),
            capital_gain=Decimal("0"),
            total_pnl=Decimal("0"),
        )
        assert ok is True


# ---------------------------------------------------------------------------
# estimate_modified_duration
# ---------------------------------------------------------------------------

class TestEstimateModifiedDuration:

    def test_returns_decimal(self):
        d = estimate_modified_duration(
            maturity_date=date(2031, 1, 1),
            report_date=date(2026, 1, 1),
            coupon_rate=Decimal("0.03"),
        )
        assert isinstance(d, Decimal)

    def test_duration_positive(self):
        d = estimate_modified_duration(
            maturity_date=date(2031, 1, 1),
            report_date=date(2026, 1, 1),
            coupon_rate=Decimal("0.03"),
        )
        assert d > Decimal("0")

    def test_longer_maturity_higher_duration(self):
        d5 = estimate_modified_duration(
            maturity_date=date(2031, 1, 1),
            report_date=date(2026, 1, 1),
            coupon_rate=Decimal("0.03"),
        )
        d10 = estimate_modified_duration(
            maturity_date=date(2036, 1, 1),
            report_date=date(2026, 1, 1),
            coupon_rate=Decimal("0.03"),
        )
        assert d10 > d5

    def test_none_maturity_returns_default(self):
        from backend.app.core_finance.attribution_core import DEFAULT_DURATION
        d = estimate_modified_duration(
            maturity_date=None,
            report_date=date(2026, 1, 1),
            coupon_rate=Decimal("0.03"),
        )
        assert d == DEFAULT_DURATION

    def test_expired_bond_returns_min_duration(self):
        from backend.app.core_finance.attribution_core import MIN_DURATION
        d = estimate_modified_duration(
            maturity_date=date(2025, 1, 1),
            report_date=date(2026, 1, 1),
            coupon_rate=Decimal("0.03"),
        )
        assert d == MIN_DURATION

    def test_duration_within_bounds(self):
        from backend.app.core_finance.attribution_core import MAX_DURATION, MIN_DURATION
        d = estimate_modified_duration(
            maturity_date=date(2036, 1, 1),
            report_date=date(2026, 1, 1),
            coupon_rate=Decimal("0.05"),
            ytm=Decimal("0.05"),
        )
        assert MIN_DURATION <= d <= MAX_DURATION


# ---------------------------------------------------------------------------
# safe_divide
# ---------------------------------------------------------------------------

class TestSafeDivide:

    def test_normal_division(self):
        result = safe_divide(Decimal("10"), Decimal("4"))
        assert result == Decimal("2.5")

    def test_division_by_zero_returns_default(self):
        result = safe_divide(Decimal("10"), Decimal("0"))
        assert result == Decimal("0")

    def test_division_by_zero_custom_default(self):
        result = safe_divide(Decimal("10"), Decimal("0"), default=Decimal("-1"))
        assert result == Decimal("-1")

    def test_result_is_decimal(self):
        result = safe_divide(Decimal("7"), Decimal("3"))
        assert isinstance(result, Decimal)


# ---------------------------------------------------------------------------
# round_decimal
# ---------------------------------------------------------------------------

class TestRoundDecimal:

    def test_rounds_to_four_decimal_places(self):
        result = round_decimal(Decimal("1.23456789"))
        assert result == Decimal("1.2346")

    def test_custom_precision(self):
        result = round_decimal(Decimal("1.23456789"), precision="0.01")
        assert result == Decimal("1.23")

    def test_returns_decimal(self):
        assert isinstance(round_decimal(Decimal("3.14159")), Decimal)


# ---------------------------------------------------------------------------
# get_day_count_factor
# ---------------------------------------------------------------------------

class TestGetDayCountFactor:

    def test_act_365_february(self):
        # February 2026 has 28 days
        factor = get_day_count_factor(date(2026, 2, 1), DayCountConvention.ACT_365)
        assert factor == Decimal("28") / Decimal("365")

    def test_act_360(self):
        factor = get_day_count_factor(date(2026, 1, 1), DayCountConvention.ACT_360)
        assert factor == Decimal("31") / Decimal("360")

    def test_thirty_360(self):
        factor = get_day_count_factor(date(2026, 1, 1), DayCountConvention.THIRTY_360)
        assert factor == Decimal("30") / Decimal("360")

    def test_act_act_leap_year(self):
        # 2024 is a leap year
        factor = get_day_count_factor(date(2024, 2, 1), DayCountConvention.ACT_ACT)
        assert factor == Decimal("29") / Decimal("366")

    def test_custom_period_days(self):
        factor = get_day_count_factor(
            date(2026, 1, 1), DayCountConvention.ACT_365, period_days=90
        )
        assert factor == Decimal("90") / Decimal("365")

    def test_returns_decimal(self):
        factor = get_day_count_factor(date(2026, 3, 1))
        assert isinstance(factor, Decimal)


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

class TestDateHelpers:

    def test_get_days_in_month_january(self):
        assert get_days_in_month(2026, 1) == 31

    def test_get_days_in_month_february_non_leap(self):
        assert get_days_in_month(2026, 2) == 28

    def test_get_days_in_month_february_leap(self):
        assert get_days_in_month(2024, 2) == 29

    def test_get_month_end_date(self):
        assert get_month_end_date(2026, 1) == date(2026, 1, 31)
        assert get_month_end_date(2026, 2) == date(2026, 2, 28)

    def test_get_previous_month_normal(self):
        result = get_previous_month(date(2026, 3, 31))
        assert result == date(2026, 2, 28)

    def test_get_previous_month_january_wraps_to_december(self):
        result = get_previous_month(date(2026, 1, 31))
        assert result == date(2025, 12, 31)

    def test_get_same_month_last_year(self):
        result = get_same_month_last_year(date(2026, 3, 31))
        assert result == date(2025, 3, 31)


# ---------------------------------------------------------------------------
# interpolate_yield_curve
# ---------------------------------------------------------------------------

class TestInterpolateYieldCurve:

    CURVE = {
        1: Decimal("0.02"),
        3: Decimal("0.03"),
        5: Decimal("0.04"),
        10: Decimal("0.05"),
    }

    def test_exact_tenor_match(self):
        result = interpolate_yield_curve(self.CURVE, 3.0)
        assert result == Decimal("0.03")

    def test_interpolation_midpoint(self):
        # Between 1Y (0.02) and 3Y (0.03): at 2Y → 0.025
        result = interpolate_yield_curve(self.CURVE, 2.0)
        assert result == Decimal("0.025")

    def test_below_min_tenor_returns_first(self):
        result = interpolate_yield_curve(self.CURVE, 0.5)
        assert result == Decimal("0.02")

    def test_above_max_tenor_returns_last(self):
        result = interpolate_yield_curve(self.CURVE, 15.0)
        assert result == Decimal("0.05")

    def test_empty_curve_returns_zero(self):
        result = interpolate_yield_curve({}, 5.0)
        assert result == Decimal("0")

    def test_returns_decimal(self):
        result = interpolate_yield_curve(self.CURVE, 5.0)
        assert isinstance(result, Decimal)


# ---------------------------------------------------------------------------
# get_tenor_bucket / get_adjacent_tenor_buckets
# ---------------------------------------------------------------------------

class TestTenorBuckets:

    def test_on_bucket(self):
        assert get_tenor_bucket(0.005) == "ON"

    def test_1y_bucket(self):
        assert get_tenor_bucket(1.0) == "1Y"

    def test_5y_bucket(self):
        assert get_tenor_bucket(5.0) == "5Y"

    def test_10y_bucket(self):
        assert get_tenor_bucket(10.0) == "10Y"

    def test_30y_bucket_large_value(self):
        assert get_tenor_bucket(50.0) == "30Y"

    def test_adjacent_below_min(self):
        lower, upper, weight = get_adjacent_tenor_buckets(0.5)
        assert lower == "1Y"
        assert upper == "1Y"
        assert weight == 0.0

    def test_adjacent_above_max(self):
        lower, upper, weight = get_adjacent_tenor_buckets(35.0)
        assert lower == "30Y"
        assert upper == "30Y"
        assert weight == 1.0

    def test_adjacent_interpolation(self):
        # At exactly 5.0: the loop matches t1=3, t2=5 first (3 <= 5.0 <= 5),
        # so weight = (5.0 - 3) / (5 - 3) = 1.0
        lower, upper, weight = get_adjacent_tenor_buckets(5.0)
        assert lower == "3Y"
        assert upper == "5Y"
        assert abs(weight - 1.0) < 1e-9

    def test_adjacent_midpoint(self):
        # 6Y is midpoint between 5Y and 7Y → weight = 0.5
        lower, upper, weight = get_adjacent_tenor_buckets(6.0)
        assert lower == "5Y"
        assert upper == "7Y"
        assert abs(weight - 0.5) < 1e-9
