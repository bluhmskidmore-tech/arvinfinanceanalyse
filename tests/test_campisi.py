"""
Unit tests for campisi.py — Campisi attribution logic.

Covers:
- Treasury yield interpolation at known tenors
- Rate unit coercion (_coerce_percent_curve) with both pct and decimal inputs
- benchmark_yield_change_decimal: (y1 - y0) / 100
- credit_spread_change_decimal: (s1 - s0) / 10000
- Full Campisi attribution: income + treasury + spread + selection = total_return
- Edge cases: flat curve, zero spread, missing curve data
"""
from datetime import date
from decimal import Decimal

import pytest

from backend.app.core_finance import campisi as campisi_module
from backend.app.core_finance.campisi import (
    _coerce_percent_curve,
    benchmark_yield_change_decimal,
    campisi_attribution,
    campisi_enhanced,
    credit_spread_change_decimal,
    infer_credit_rating_from_asset_class,
    interpolate_treasury_yield_pct,
    treasury_tenor_coverage,
    usable_spread_bp,
)


class TestTreasuryYieldInterpolation:
    """Test treasury yield curve interpolation."""

    def test_interpolate_at_known_tenor(self):
        """Interpolate at exact tenor points should return exact values."""
        market = {
            "treasury_1y": 2.0,
            "treasury_3y": 2.5,
            "treasury_5y": 3.0,
            "treasury_7y": 3.2,
            "treasury_10y": 3.5,
            "treasury_30y": 4.0,
        }
        assert interpolate_treasury_yield_pct(market, 1.0) == 2.0
        assert interpolate_treasury_yield_pct(market, 3.0) == 2.5
        assert interpolate_treasury_yield_pct(market, 5.0) == 3.0
        assert interpolate_treasury_yield_pct(market, 10.0) == 3.5
        assert interpolate_treasury_yield_pct(market, 30.0) == 4.0

    def test_interpolate_between_tenors(self):
        """Interpolation between tenors (cubic spline may differ from strict linear midpoint)."""
        market = {
            "treasury_1y": 2.0,
            "treasury_3y": 3.0,
            "treasury_5y": 4.0,
            "treasury_7y": 4.5,
            "treasury_10y": 5.0,
            "treasury_30y": 6.0,
        }
        # Between 1y and 3y: cubic spline value near 2.5 (linear midpoint)
        assert interpolate_treasury_yield_pct(market, 2.0) == pytest.approx(2.5, abs=0.15)
        # Between 3y and 5y: cubic spline value near 3.5
        assert interpolate_treasury_yield_pct(market, 4.0) == pytest.approx(3.5, abs=0.15)

    def test_extrapolate_below_min_tenor(self):
        """Values below 1y should return 1y yield."""
        market = {
            "treasury_1y": 2.0,
            "treasury_3y": 2.5,
            "treasury_5y": 3.0,
            "treasury_7y": 3.2,
            "treasury_10y": 3.5,
            "treasury_30y": 4.0,
        }
        assert interpolate_treasury_yield_pct(market, 0.5) == 2.0
        assert interpolate_treasury_yield_pct(market, 0.0) == 2.0

    def test_extrapolate_above_max_tenor(self):
        """Values above 30y should return 30y yield."""
        market = {
            "treasury_1y": 2.0,
            "treasury_3y": 2.5,
            "treasury_5y": 3.0,
            "treasury_7y": 3.2,
            "treasury_10y": 3.5,
            "treasury_30y": 4.0,
        }
        assert interpolate_treasury_yield_pct(market, 40.0) == 4.0
        assert interpolate_treasury_yield_pct(market, 50.0) == 4.0

    def test_empty_market_data(self):
        """Empty or None market data should return 0."""
        assert interpolate_treasury_yield_pct(None, 5.0) == 0.0
        assert interpolate_treasury_yield_pct({}, 5.0) == 0.0

    def test_single_positive_tenor_returns_zero_with_warning(self, caplog):
        market = {"treasury_10y": 3.5}

        caplog.set_level("WARNING", logger="backend.app.core_finance.campisi")

        assert interpolate_treasury_yield_pct(market, 5.0) == 0.0
        assert any("at least 2 positive tenors" in record.message for record in caplog.records)

    def test_missing_long_tenor_is_not_used_as_zero_spline_knot(self):
        """Missing 30Y data should clamp to the last available tenor, not 0%."""
        market = {
            "treasury_1y": 2.0,
            "treasury_3y": 2.5,
            "treasury_5y": 3.0,
            "treasury_7y": 3.2,
            "treasury_10y": 3.5,
        }

        assert interpolate_treasury_yield_pct(market, 20.0) == pytest.approx(3.5)

    def test_zero_long_tenor_is_not_used_as_zero_spline_knot(self):
        """Explicit 0% tenor data is treated as unavailable for interpolation."""
        market = {
            "treasury_1y": 2.0,
            "treasury_3y": 2.5,
            "treasury_5y": 3.0,
            "treasury_7y": 3.2,
            "treasury_10y": 3.5,
            "treasury_30y": 0.0,
        }

        assert interpolate_treasury_yield_pct(market, 20.0) == pytest.approx(3.5)


class TestRateUnitCoercion:
    """Test _coerce_percent_curve heuristic for rate unit detection."""

    def test_percent_input_unchanged(self):
        """Percent values (>2) should remain unchanged."""
        market = {
            "treasury_1y": 2.55,
            "treasury_3y": 2.80,
            "treasury_5y": 3.10,
            "treasury_7y": 3.25,
            "treasury_10y": 3.50,
            "treasury_30y": 4.00,
        }
        result = _coerce_percent_curve(market)
        assert result["treasury_1y"] == 2.55
        assert result["treasury_3y"] == 2.80
        assert result["treasury_5y"] == 3.10

    def test_decimal_input_scaled_up(self):
        """Decimal values (<2) should be scaled by 100."""
        market = {
            "treasury_1y": 0.0255,
            "treasury_3y": 0.0280,
            "treasury_5y": 0.0310,
            "treasury_7y": 0.0325,
            "treasury_10y": 0.0350,
            "treasury_30y": 0.0400,
        }
        result = _coerce_percent_curve(market)
        assert result["treasury_1y"] == pytest.approx(2.55, abs=1e-6)
        assert result["treasury_3y"] == pytest.approx(2.80, abs=1e-6)
        assert result["treasury_5y"] == pytest.approx(3.10, abs=1e-6)

    def test_low_percent_input_under_two_is_not_scaled(self):
        """Chinese government yields can be valid percent values below 2%."""
        market = {
            "treasury_1y": 1.42,
            "treasury_3y": 1.58,
            "treasury_5y": 1.68,
            "treasury_7y": 1.81,
            "treasury_10y": 1.91,
            "treasury_30y": 1.95,
        }
        result = _coerce_percent_curve(market)
        assert result["treasury_1y"] == pytest.approx(1.42)
        assert result["treasury_10y"] == pytest.approx(1.91)

    def test_mixed_zero_values(self):
        """Zero values should not trigger scaling."""
        market = {
            "treasury_1y": 0.0,
            "treasury_3y": 2.80,
            "treasury_5y": 3.10,
            "treasury_7y": 0.0,
            "treasury_10y": 3.50,
            "treasury_30y": 4.00,
        }
        result = _coerce_percent_curve(market)
        # Max non-zero is 4.0 > 2, so no scaling
        assert "treasury_1y" not in result
        assert result["treasury_3y"] == 2.80
        assert result["treasury_5y"] == 3.10
        assert "treasury_7y" not in result

    def test_none_market_returns_empty(self):
        """None input should return empty dict."""
        result = _coerce_percent_curve(None)
        assert result == {}


class TestBenchmarkYieldChange:
    """Test benchmark_yield_change_decimal conversion."""

    def test_positive_yield_change(self):
        """Positive yield change: (y1 - y0) / 100."""
        market_start = {
            "treasury_1y": 2.0,
            "treasury_3y": 2.5,
            "treasury_5y": 3.0,
            "treasury_7y": 3.2,
            "treasury_10y": 3.5,
            "treasury_30y": 4.0,
        }
        market_end = {
            "treasury_1y": 2.2,
            "treasury_3y": 2.7,
            "treasury_5y": 3.2,
            "treasury_7y": 3.4,
            "treasury_10y": 3.7,
            "treasury_30y": 4.2,
        }
        # At 5y: 3.2 - 3.0 = 0.2, divided by 100 = 0.002
        result = benchmark_yield_change_decimal(market_start, market_end, 5.0)
        assert abs(result - Decimal("0.002")) < Decimal("1e-12")

    def test_negative_yield_change(self):
        """Negative yield change."""
        market_start = {
            "treasury_1y": 2.5,
            "treasury_3y": 3.0,
            "treasury_5y": 3.5,
            "treasury_7y": 3.7,
            "treasury_10y": 4.0,
            "treasury_30y": 4.5,
        }
        market_end = {
            "treasury_1y": 2.0,
            "treasury_3y": 2.5,
            "treasury_5y": 3.0,
            "treasury_7y": 3.2,
            "treasury_10y": 3.5,
            "treasury_30y": 4.0,
        }
        # At 5y: 3.0 - 3.5 = -0.5, divided by 100 = -0.005
        result = benchmark_yield_change_decimal(market_start, market_end, 5.0)
        assert result == Decimal("-0.005")

    def test_zero_yield_change(self):
        """No yield change should return 0."""
        market = {
            "treasury_1y": 2.0,
            "treasury_3y": 2.5,
            "treasury_5y": 3.0,
            "treasury_7y": 3.2,
            "treasury_10y": 3.5,
            "treasury_30y": 4.0,
        }
        result = benchmark_yield_change_decimal(market, market, 5.0)
        assert result == Decimal("0")

    def test_benchmark_yield_change_uses_shared_positive_tenor_intersection(self):
        market_start = {
            "treasury_1y": 2.0,
            "treasury_3y": 2.5,
            "treasury_5y": 3.0,
            "treasury_7y": 3.2,
            "treasury_10y": 3.5,
            "treasury_30y": 4.5,
        }
        market_end = {
            "treasury_1y": 2.0,
            "treasury_3y": 2.5,
            "treasury_5y": 3.0,
            "treasury_7y": 3.2,
            "treasury_10y": 3.5,
        }

        result = benchmark_yield_change_decimal(market_start, market_end, 20.0)

        assert result == Decimal("0")

    def test_decimal_precision(self):
        """Verify Decimal precision is maintained."""
        market_start = {"treasury_1y": 2.555, "treasury_3y": 2.8, "treasury_5y": 3.0,
                       "treasury_7y": 3.2, "treasury_10y": 3.5, "treasury_30y": 4.0}
        market_end = {"treasury_1y": 2.565, "treasury_3y": 2.81, "treasury_5y": 3.01,
                     "treasury_7y": 3.21, "treasury_10y": 3.51, "treasury_30y": 4.01}
        result = benchmark_yield_change_decimal(market_start, market_end, 1.0)
        # 2.565 - 2.555 = 0.01, / 100 = 0.0001
        assert abs(result - Decimal("0.0001")) < Decimal("1e-12")


class TestCreditSpreadChange:
    """Test credit_spread_change_decimal BP conversion."""

    def test_aaa_spread_change(self):
        """AAA spread change: (s1 - s0) / 10000."""
        market_start = {"credit_spread_aaa_3y": 50.0}
        market_end = {"credit_spread_aaa_3y": 60.0}
        result = credit_spread_change_decimal(market_start, market_end, "AAA")
        # (60 - 50) / 10000 = 0.001
        assert result == Decimal("0.001")

    def test_aa_plus_spread_change(self):
        """AA+ spread change."""
        market_start = {"credit_spread_aa_plus_3y": 80.0}
        market_end = {"credit_spread_aa_plus_3y": 70.0}
        result = credit_spread_change_decimal(market_start, market_end, "AA+")
        # (70 - 80) / 10000 = -0.001
        assert result == Decimal("-0.001")

    def test_aa_spread_change(self):
        """AA spread change."""
        market_start = {"credit_spread_aa_3y": 100.0}
        market_end = {"credit_spread_aa_3y": 120.0}
        result = credit_spread_change_decimal(market_start, market_end, "AA")
        # (120 - 100) / 10000 = 0.002
        assert result == Decimal("0.002")

    def test_gov_rating_zero_spread(self):
        """GOV rating should always return 0 spread change."""
        market_start = {"credit_spread_aaa_3y": 50.0}
        market_end = {"credit_spread_aaa_3y": 60.0}
        result = credit_spread_change_decimal(market_start, market_end, "GOV")
        assert result == Decimal("0")

    def test_unknown_rating_zero_spread(self):
        """Unknown rating should return 0."""
        market_start = {"credit_spread_aaa_3y": 50.0}
        market_end = {"credit_spread_aaa_3y": 60.0}
        result = credit_spread_change_decimal(market_start, market_end, "BBB")
        assert result == Decimal("0")

    def test_missing_spread_data(self):
        """Missing spread data should return 0."""
        result = credit_spread_change_decimal(None, None, "AAA")
        assert result == Decimal("0")

    def test_one_sided_missing_spread_is_not_a_spread_change(self, caplog):
        """Start=60bp / end missing must not become a fictitious -60bp change."""
        caplog.set_level("WARNING", logger="backend.app.core_finance.campisi")

        result = credit_spread_change_decimal({"credit_spread_aaa_3y": 60.0}, {}, "AAA")

        assert result == Decimal("0")
        assert any("on both sides" in record.message for record in caplog.records)

    def test_one_sided_missing_spread_start_side(self):
        result = credit_spread_change_decimal({}, {"credit_spread_aaa_3y": 60.0}, "AAA")
        assert result == Decimal("0")

    def test_zero_spread_value_treated_as_unavailable(self):
        result = credit_spread_change_decimal(
            {"credit_spread_aa_3y": 0.0},
            {"credit_spread_aa_3y": 120.0},
            "AA",
        )
        assert result == Decimal("0")

    def test_unparseable_spread_value_treated_as_unavailable(self, caplog):
        caplog.set_level("WARNING", logger="backend.app.core_finance.campisi")

        result = credit_spread_change_decimal(
            {"credit_spread_aaa_3y": "n/a"},
            {"credit_spread_aaa_3y": 60.0},
            "AAA",
        )

        assert result == Decimal("0")
        assert any("Unparseable credit spread" in record.message for record in caplog.records)

    def test_usable_spread_bp_validity_rule(self):
        assert usable_spread_bp({"credit_spread_aaa_3y": 60.0}, "AAA") == 60.0
        assert usable_spread_bp({"credit_spread_aaa_3y": 0.0}, "AAA") is None
        assert usable_spread_bp({"credit_spread_aaa_3y": -5.0}, "AAA") is None
        assert usable_spread_bp({"credit_spread_aaa_3y": None}, "AAA") is None
        assert usable_spread_bp({}, "AAA") is None
        assert usable_spread_bp(None, "AAA") is None
        assert usable_spread_bp({"credit_spread_aaa_3y": 60.0}, "GOV") is None


class TestTreasuryTenorCoverage:
    """Coverage helper must apply the same validity rule as interpolation."""

    _FULL = {
        "treasury_1y": 2.0,
        "treasury_3y": 2.5,
        "treasury_5y": 3.0,
        "treasury_7y": 3.2,
        "treasury_10y": 3.5,
        "treasury_30y": 4.5,
    }

    def test_full_coverage(self):
        coverage = treasury_tenor_coverage(self._FULL, self._FULL)

        assert coverage["start_missing"] == []
        assert coverage["end_missing"] == []
        assert coverage["shared_positive_tenors"] == 6

    def test_missing_and_zero_tenors_reported_per_side(self):
        start = {k: v for k, v in self._FULL.items() if k != "treasury_30y"}
        end = dict(self._FULL, treasury_1y=0.0)

        coverage = treasury_tenor_coverage(start, end)

        assert coverage["start_missing"] == ["treasury_30y"]
        assert coverage["end_missing"] == ["treasury_1y"]
        assert coverage["shared_positive_tenors"] == 4

    def test_degraded_period_flagged_below_two_shared_tenors(self):
        coverage = treasury_tenor_coverage(
            {"treasury_10y": 3.5},
            {"treasury_1y": 2.0},
        )

        assert coverage["shared_positive_tenors"] == 0


class TestCreditRatingInference:
    """Test infer_credit_rating_from_asset_class."""

    def test_government_bonds(self):
        """Government bond types should return GOV."""
        assert infer_credit_rating_from_asset_class("国债") == "GOV"
        assert infer_credit_rating_from_asset_class("地方政府债") == "GOV"
        assert infer_credit_rating_from_asset_class("政策性金融债") == "GOV"
        assert infer_credit_rating_from_asset_class("国开债") == "GOV"

    def test_aaa_rating(self):
        """High quality bonds should return AAA."""
        assert infer_credit_rating_from_asset_class("AAA企业债") == "AAA"
        assert infer_credit_rating_from_asset_class("国企债") == "AAA"
        assert infer_credit_rating_from_asset_class("央企债") == "AAA"

    def test_aa_plus_rating(self):
        """Medium-high quality bonds should return AA+."""
        assert infer_credit_rating_from_asset_class("AA+企业债") == "AA+"
        assert infer_credit_rating_from_asset_class("城投债") == "AA+"
        assert infer_credit_rating_from_asset_class("银行债") == "AA+"

    def test_default_aa_rating(self):
        """Unknown types should default to AA."""
        assert infer_credit_rating_from_asset_class("其他债券") == "AA"
        assert infer_credit_rating_from_asset_class(None) == "AA"


class TestFullCampisiAttribution:
    """Test full Campisi attribution: income + treasury + spread + selection = total."""

    def test_simple_bond_attribution(self):
        """Single bond with all effects should sum to total return."""
        positions = [
            {
                "bond_code": "123456.IB",
                "instrument_id": "123456.IB",
                "market_value_start": 10000000.0,
                "market_value_end": 10050000.0,
                "face_value_start": 10000000.0,
                "coupon_rate_start": 0.03,  # 3% coupon
                "yield_to_maturity_start": 0.035,
                "asset_class_start": "AAA企业债",
                "maturity_date_start": date(2028, 12, 31),
            }
        ]
        market_start = {
            "treasury_1y": 2.0,
            "treasury_3y": 2.5,
            "treasury_5y": 3.0,
            "treasury_7y": 3.2,
            "treasury_10y": 3.5,
            "treasury_30y": 4.0,
            "credit_spread_aaa_3y": 50.0,
        }
        market_end = {
            "treasury_1y": 2.1,
            "treasury_3y": 2.6,
            "treasury_5y": 3.1,
            "treasury_7y": 3.3,
            "treasury_10y": 3.6,
            "treasury_30y": 4.1,
            "credit_spread_aaa_3y": 55.0,
        }
        start_date = date(2026, 1, 1)
        end_date = date(2026, 1, 31)

        result = campisi_attribution(positions, market_start, market_end, start_date, end_date)

        # Check that effects sum to total (within tolerance)
        totals = result.totals
        sum_effects = (
            totals["income_return"]
            + totals["treasury_effect"]
            + totals["spread_effect"]
            + totals["selection_effect"]
        )
        assert abs(sum_effects - totals["total_return"]) < 1.0  # Within 1 yuan

    def test_full_price_total_return_uses_accrued_interest_when_available(self):
        """Campisi total return should use full-price change when accrued interest is supplied."""
        positions = [
            {
                "bond_code": "AI.IB",
                "instrument_id": "AI.IB",
                "market_value_start": 1000.0,
                "market_value_end": 1010.0,
                "face_value_start": 1000.0,
                "coupon_rate_start": 0.03,
                "yield_to_maturity_start": 0.03,
                "asset_class_start": "credit AAA",
                "maturity_date_start": date(2028, 12, 31),
                "accrued_interest_start": 5.0,
                "accrued_interest_end": 8.0,
            }
        ]

        result = campisi_attribution(positions, {}, {}, date(2026, 1, 1), date(2026, 1, 31))

        assert result.totals["total_return"] == pytest.approx(13.0)

    def test_ac_class_zeroes_market_effects(self):
        """AC class bonds should have zero treasury/spread/selection effects."""
        positions = [
            {
                "bond_code": "AC123.IB",
                "instrument_id": "AC123.IB",
                "market_value_start": 5000000.0,
                "market_value_end": 5100000.0,
                "face_value_start": 5000000.0,
                "coupon_rate_start": 0.04,
                "yield_to_maturity_start": 0.04,
                "asset_class_start": "AC类债券",
                "maturity_date_start": date(2030, 6, 30),
            }
        ]
        market_start = {
            "treasury_1y": 2.0, "treasury_3y": 2.5, "treasury_5y": 3.0,
            "treasury_7y": 3.2, "treasury_10y": 3.5, "treasury_30y": 4.0,
            "credit_spread_aaa_3y": 50.0,
        }
        market_end = {
            "treasury_1y": 3.0, "treasury_3y": 3.5, "treasury_5y": 4.0,
            "treasury_7y": 4.2, "treasury_10y": 4.5, "treasury_30y": 5.0,
            "credit_spread_aaa_3y": 100.0,
        }
        start_date = date(2026, 1, 1)
        end_date = date(2026, 12, 31)

        result = campisi_attribution(positions, market_start, market_end, start_date, end_date)

        # AC class should have zero market effects
        assert result.totals["treasury_effect"] == 0.0
        assert result.totals["spread_effect"] == 0.0
        assert result.totals["selection_effect"] == 0.0
        # Total return should equal income return
        assert result.totals["total_return"] == result.totals["income_return"]

    def test_flat_curve_zero_treasury_effect(self):
        """Flat yield curve (no change) should produce zero treasury effect."""
        positions = [
            {
                "bond_code": "FLAT.IB",
                "instrument_id": "FLAT.IB",
                "market_value_start": 8000000.0,
                "market_value_end": 8020000.0,
                "face_value_start": 8000000.0,
                "coupon_rate_start": 0.025,
                "yield_to_maturity_start": 0.03,
                "asset_class_start": "AAA企业债",
                "maturity_date_start": date(2029, 3, 15),
            }
        ]
        market = {
            "treasury_1y": 2.5, "treasury_3y": 2.5, "treasury_5y": 2.5,
            "treasury_7y": 2.5, "treasury_10y": 2.5, "treasury_30y": 2.5,
            "credit_spread_aaa_3y": 60.0,
        }
        start_date = date(2026, 2, 1)
        end_date = date(2026, 2, 28)

        result = campisi_attribution(positions, market, market, start_date, end_date)

        # No yield change means zero treasury effect
        assert abs(result.totals["treasury_effect"]) < 0.01

    def test_zero_spread_change(self):
        """Zero spread change should produce zero spread effect."""
        positions = [
            {
                "bond_code": "ZERO.IB",
                "instrument_id": "ZERO.IB",
                "market_value_start": 6000000.0,
                "market_value_end": 6015000.0,
                "face_value_start": 6000000.0,
                "coupon_rate_start": 0.035,
                "yield_to_maturity_start": 0.04,
                "asset_class_start": "AAA企业债",
                "maturity_date_start": date(2027, 9, 30),
            }
        ]
        market_start = {
            "treasury_1y": 2.0, "treasury_3y": 2.5, "treasury_5y": 3.0,
            "treasury_7y": 3.2, "treasury_10y": 3.5, "treasury_30y": 4.0,
            "credit_spread_aaa_3y": 50.0,
        }
        market_end = {
            "treasury_1y": 2.2, "treasury_3y": 2.7, "treasury_5y": 3.2,
            "treasury_7y": 3.4, "treasury_10y": 3.7, "treasury_30y": 4.2,
            "credit_spread_aaa_3y": 50.0,  # No spread change
        }
        start_date = date(2026, 3, 1)
        end_date = date(2026, 3, 31)

        result = campisi_attribution(positions, market_start, market_end, start_date, end_date)

        # No spread change means zero spread effect
        assert abs(result.totals["spread_effect"]) < 0.01

    def test_missing_curve_data_fallback(self):
        """Missing curve data should not crash, use fallback values."""
        positions = [
            {
                "bond_code": "MISSING.IB",
                "instrument_id": "MISSING.IB",
                "market_value_start": 3000000.0,
                "market_value_end": 3010000.0,
                "face_value_start": 3000000.0,
                "coupon_rate_start": 0.03,
                "yield_to_maturity_start": 0.035,
                "asset_class_start": "企业债",
                "maturity_date_start": date(2028, 6, 30),
            }
        ]
        # Empty market data
        result = campisi_attribution(positions, None, None, date(2026, 1, 1), date(2026, 1, 31))

        # Should complete without error
        assert result.totals["income_return"] > 0  # Income should still be calculated
        assert result.totals["treasury_effect"] == 0.0  # No curve data means no effect
        assert result.totals["spread_effect"] == 0.0

    def test_multiple_bonds_aggregation(self):
        """Multiple bonds should aggregate correctly."""
        positions = [
            {
                "bond_code": "BOND1.IB",
                "instrument_id": "BOND1.IB",
                "market_value_start": 5000000.0,
                "market_value_end": 5025000.0,
                "face_value_start": 5000000.0,
                "coupon_rate_start": 0.03,
                "yield_to_maturity_start": 0.035,
                "asset_class_start": "AAA企业债",
                "maturity_date_start": date(2028, 12, 31),
            },
            {
                "bond_code": "BOND2.IB",
                "instrument_id": "BOND2.IB",
                "market_value_start": 3000000.0,
                "market_value_end": 3015000.0,
                "face_value_start": 3000000.0,
                "coupon_rate_start": 0.04,
                "yield_to_maturity_start": 0.045,
                "asset_class_start": "AA+企业债",
                "maturity_date_start": date(2027, 6, 30),
            },
        ]
        market_start = {
            "treasury_1y": 2.0, "treasury_3y": 2.5, "treasury_5y": 3.0,
            "treasury_7y": 3.2, "treasury_10y": 3.5, "treasury_30y": 4.0,
            "credit_spread_aaa_3y": 50.0,
            "credit_spread_aa_plus_3y": 80.0,
        }
        market_end = {
            "treasury_1y": 2.1, "treasury_3y": 2.6, "treasury_5y": 3.1,
            "treasury_7y": 3.3, "treasury_10y": 3.6, "treasury_30y": 4.1,
            "credit_spread_aaa_3y": 55.0,
            "credit_spread_aa_plus_3y": 85.0,
        }
        start_date = date(2026, 1, 1)
        end_date = date(2026, 1, 31)

        result = campisi_attribution(positions, market_start, market_end, start_date, end_date)

        # Check totals are sum of individual bonds
        assert len(result.by_bond) == 2
        assert result.totals["market_value_start"] == 8000000.0

        # Sum of effects should equal total
        sum_effects = (
            result.totals["income_return"]
            + result.totals["treasury_effect"]
            + result.totals["spread_effect"]
            + result.totals["selection_effect"]
        )
        assert abs(sum_effects - result.totals["total_return"]) < 1.0


class TestCarryDayCountConvention:
    """M-5 冻结：carry 天数口径为 (end_date - start_date).days，不含头含尾。

    2026-01-01 -> 2026-01-31 为 30 天（不是 31 天）；income_return 按 30/365 计提。
    """

    _POSITION = {
        "bond_code": "DAYCOUNT.IB",
        "instrument_id": "DAYCOUNT.IB",
        "market_value_start": 10_000_000.0,
        "market_value_end": 10_000_000.0,
        "face_value_start": 10_000_000.0,
        "coupon_rate_start": 0.03,
        "yield_to_maturity_start": 0.03,
        "asset_class_start": "AAA企业债",
        "maturity_date_start": date(2028, 12, 31),
    }

    def test_num_days_is_exclusive_of_start_date(self):
        result = campisi_attribution(
            [self._POSITION], None, None, date(2026, 1, 1), date(2026, 1, 31)
        )
        assert result.num_days == 30

    def test_income_return_uses_exclusive_day_count(self):
        result = campisi_attribution(
            [self._POSITION], None, None, date(2026, 1, 1), date(2026, 1, 31)
        )
        expected = 0.03 * 10_000_000.0 * 30 / 365
        assert result.totals["income_return"] == pytest.approx(expected, rel=1e-9)

    def test_enhanced_uses_same_day_count(self):
        result = campisi_enhanced(
            [self._POSITION], None, None, date(2026, 1, 1), date(2026, 1, 31)
        )
        assert result["num_days"] == 30

    def test_same_day_window_floors_to_one_day(self):
        result = campisi_attribution(
            [self._POSITION], None, None, date(2026, 1, 31), date(2026, 1, 31)
        )
        assert result.num_days == 1


class TestLargePortfolioAggregationPrecision:
    """Regression guard for the by_bond -> totals aggregation precision fix.

    `campisi_attribution` used to build `by_bond` records with each effect
    independently cast to float, then aggregate `totals` with Python's
    built-in `sum()` over those already-rounded floats. Per-bond, the four
    effects sum *exactly* to `total_return` in the Decimal domain (selection
    is defined as the residual), but once each effect is rounded to float
    independently, the four rounded floats no longer sum to exactly the
    rounded `total_return`; with many bonds, naive float accumulation can
    compound this drift.

    Note: on Python >= 3.12, CPython's built-in `sum()` for floats already
    uses a compensated (Neumaier) summation algorithm, which absorbs most of
    this drift in practice — this test's 0.01-yuan tolerance therefore does
    not reliably fail on unfixed code under every Python runtime. This repo's
    `backend/pyproject.toml` declares `requires-python = ">=3.11"`, where the
    built-in `sum()` has no such compensation and the drift is real. The fix
    (aggregating in the Decimal domain end-to-end and converting to float
    only at the `CampisiResult` boundary) removes the dependency on the
    Python runtime's `sum()` implementation entirely.
    """

    def test_500_plus_bonds_effects_sum_closes_to_total_return(self):
        """Combined four effects must close to total_return within 1 fen (0.01 yuan)."""
        n = 600
        positions = []
        ratings_cycle = ["AAA企业债", "AA+企业债", "AA企业债", "国债"]
        for i in range(n):
            # Deliberately non-binary-friendly fractions (0.1 / 0.03 style cents).
            mv = 1_000_000.1 + (i % 97) * 733.03 + (i % 7) * 0.03
            positions.append(
                {
                    "bond_code": f"BOND{i:04d}.IB",
                    "instrument_id": f"BOND{i:04d}.IB",
                    "market_value_start": mv,
                    "market_value_end": mv * (1.001 + (i % 5) * 0.0001 - 0.0003),
                    "face_value_start": mv,
                    "coupon_rate_start": 0.031 + (i % 11) * 0.0003,
                    "yield_to_maturity_start": 0.035 + (i % 13) * 0.0002,
                    "asset_class_start": ratings_cycle[i % 4],
                    "maturity_date_start": date(2027 + (i % 6), 1 + (i % 12), 1 + (i % 27)),
                }
            )

        market_start = {
            "treasury_1y": 2.0, "treasury_3y": 2.5, "treasury_5y": 3.0,
            "treasury_7y": 3.2, "treasury_10y": 3.5, "treasury_30y": 4.0,
            "credit_spread_aaa_3y": 50.0, "credit_spread_aa_plus_3y": 80.0,
            "credit_spread_aa_3y": 110.0,
        }
        market_end = {
            "treasury_1y": 2.13, "treasury_3y": 2.67, "treasury_5y": 3.21,
            "treasury_7y": 3.38, "treasury_10y": 3.71, "treasury_30y": 4.23,
            "credit_spread_aaa_3y": 57.0, "credit_spread_aa_plus_3y": 88.0,
            "credit_spread_aa_3y": 121.0,
        }

        result = campisi_attribution(
            positions, market_start, market_end, date(2026, 1, 1), date(2026, 1, 31)
        )

        assert len(result.by_bond) == n
        totals = result.totals
        sum_effects = (
            totals["income_return"]
            + totals["treasury_effect"]
            + totals["spread_effect"]
            + totals["selection_effect"]
        )
        assert sum_effects == pytest.approx(totals["total_return"], abs=0.01)

    def test_totals_match_independent_decimal_reconstruction(self):
        """totals must equal a from-scratch Decimal-domain re-aggregation of by_bond.

        This is runtime-independent: it does not rely on any particular
        Python `sum()` implementation to happen to mask the old bug.
        """
        n = 500
        positions = []
        for i in range(n):
            mv = 2_000_000.03 + (i % 53) * 1_111.1
            positions.append(
                {
                    "bond_code": f"B{i:04d}.IB",
                    "instrument_id": f"B{i:04d}.IB",
                    "market_value_start": mv,
                    "market_value_end": mv * (1.0005 + (i % 9) * 0.0001),
                    "face_value_start": mv,
                    "coupon_rate_start": 0.028 + (i % 7) * 0.0003,
                    "yield_to_maturity_start": 0.032 + (i % 5) * 0.0004,
                    "asset_class_start": ["AAA企业债", "AA+企业债", "AA企业债"][i % 3],
                    "maturity_date_start": date(2028 + (i % 4), 1 + (i % 12), 1 + (i % 27)),
                }
            )
        market_start = {
            "treasury_1y": 2.1, "treasury_3y": 2.4, "treasury_5y": 2.9,
            "treasury_7y": 3.1, "treasury_10y": 3.4, "treasury_30y": 3.9,
            "credit_spread_aaa_3y": 45.0, "credit_spread_aa_plus_3y": 75.0,
            "credit_spread_aa_3y": 105.0,
        }
        market_end = {
            "treasury_1y": 1.98, "treasury_3y": 2.29, "treasury_5y": 2.77,
            "treasury_7y": 2.96, "treasury_10y": 3.27, "treasury_30y": 3.76,
            "credit_spread_aaa_3y": 41.0, "credit_spread_aa_plus_3y": 70.0,
            "credit_spread_aa_3y": 99.0,
        }

        result = campisi_attribution(
            positions, market_start, market_end, date(2026, 3, 1), date(2026, 3, 31)
        )

        for key in ("income_return", "treasury_effect", "spread_effect", "selection_effect", "total_return"):
            reconstructed = float(
                sum((Decimal(str(r[key])) for r in result.by_bond), Decimal("0"))
            )
            assert result.totals[key] == pytest.approx(reconstructed, abs=1e-6)

    def test_enhanced_totals_close_and_match_decimal_reconstruction(self, monkeypatch):
        """Six-effect totals use Decimal aggregation before the float output boundary."""
        effect_cycle = (
            Decimal("6.82472E-13"),
            Decimal("6.01752E-13"),
            Decimal("-8.67655E-13"),
            Decimal("-4.65081E-13"),
            Decimal("-7.52706E-13"),
            Decimal("3.9003E-14"),
            Decimal("5.95854E-13"),
        )

        def fake_six_effects(bond, *_args, **_kwargs):
            idx = int(str(bond["bond_code"])[3:7])
            value = effect_cycle[idx % len(effect_cycle)]
            return {
                "income_return": value,
                "treasury_effect": Decimal("0"),
                "spread_effect": Decimal("0"),
                "convexity_effect": Decimal("0"),
                "cross_effect": Decimal("0"),
                "reinvestment_effect": Decimal("0"),
                "selection_effect": Decimal("0"),
                "total_return": value,
                "mod_duration": Decimal("7.7"),
                "has_accrued_interest": False,
                "diagnostics": [],
            }

        monkeypatch.setattr(campisi_module, "compute_bond_six_effects", fake_six_effects)
        n = 600
        start_date = date(2026, 4, 1)
        end_date = date(2026, 5, 1)
        positions = []
        asset_classes = ["AAA credit bond", "AA+ credit bond", "AA credit bond", "treasury bond"]
        for i in range(n):
            positions.append(
                {
                    "bond_code": f"ENH{i:04d}.IB",
                    "instrument_id": f"ENH{i:04d}.IB",
                    "market_value_start": Decimal("0.1"),
                    "market_value_end": Decimal("0.1"),
                    "face_value_start": Decimal("0.1"),
                    "coupon_rate_start": 0.027 + (i % 10) * 0.00031,
                    "yield_to_maturity_start": 0.031 + (i % 9) * 0.00037,
                    "asset_class_start": asset_classes[i % 4],
                    "maturity_date_start": date(2028 + (i % 7), 1 + (i % 12), 1 + (i % 27)),
                }
            )
        market_start = {
            "treasury_1y": 2.05, "treasury_3y": 2.36, "treasury_5y": 2.82,
            "treasury_7y": 3.04, "treasury_10y": 3.32, "treasury_30y": 3.88,
            "credit_spread_aaa_3y": 46.0, "credit_spread_aa_plus_3y": 76.0,
            "credit_spread_aa_3y": 106.0,
        }
        market_end = {
            "treasury_1y": 2.17, "treasury_3y": 2.51, "treasury_5y": 2.99,
            "treasury_7y": 3.19, "treasury_10y": 3.48, "treasury_30y": 4.07,
            "credit_spread_aaa_3y": 52.0, "credit_spread_aa_plus_3y": 83.0,
            "credit_spread_aa_3y": 115.0,
        }

        result = campisi_enhanced(positions, market_start, market_end, start_date, end_date)

        keys = (
            "income_return",
            "treasury_effect",
            "spread_effect",
            "convexity_effect",
            "cross_effect",
            "reinvestment_effect",
            "selection_effect",
            "total_return",
        )
        sum_effects = sum(result["totals"][key] for key in keys if key != "total_return")
        assert sum_effects == pytest.approx(result["totals"]["total_return"], abs=0.01)

        expected = {key: Decimal("0") for key in (*keys, "market_value_start")}
        for row in positions:
            expected["market_value_start"] += Decimal(str(row.get("market_value_start") or 0))
            value = effect_cycle[int(row["bond_code"][3:7]) % len(effect_cycle)]
            expected["income_return"] += value
            expected["total_return"] += value

        for key, expected_value in expected.items():
            assert result["totals"][key] == float(expected_value)
