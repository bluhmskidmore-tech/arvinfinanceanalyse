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
import pytest
from datetime import date
from decimal import Decimal

from backend.app.core_finance.campisi import (
    interpolate_treasury_yield_pct,
    _coerce_percent_curve,
    benchmark_yield_change_decimal,
    credit_spread_change_decimal,
    campisi_attribution,
    infer_credit_rating_from_asset_class,
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
        """Linear interpolation between tenors."""
        market = {
            "treasury_1y": 2.0,
            "treasury_3y": 3.0,
            "treasury_5y": 4.0,
            "treasury_7y": 4.5,
            "treasury_10y": 5.0,
            "treasury_30y": 6.0,
        }
        # Between 1y and 3y: 2.0 + (3.0 - 2.0) * (2 - 1) / (3 - 1) = 2.5
        assert interpolate_treasury_yield_pct(market, 2.0) == 2.5
        # Between 3y and 5y: 3.0 + (4.0 - 3.0) * (4 - 3) / (5 - 3) = 3.5
        assert interpolate_treasury_yield_pct(market, 4.0) == 3.5

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
        assert result["treasury_3y"] == 2.80
        assert result["treasury_5y"] == 3.10

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
        assert result == Decimal("0.002")

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

    def test_decimal_precision(self):
        """Verify Decimal precision is maintained."""
        market_start = {"treasury_1y": 2.555, "treasury_3y": 2.8, "treasury_5y": 3.0,
                       "treasury_7y": 3.2, "treasury_10y": 3.5, "treasury_30y": 4.0}
        market_end = {"treasury_1y": 2.565, "treasury_3y": 2.81, "treasury_5y": 3.01,
                     "treasury_7y": 3.21, "treasury_10y": 3.51, "treasury_30y": 4.01}
        result = benchmark_yield_change_decimal(market_start, market_end, 1.0)
        # 2.565 - 2.555 = 0.01, / 100 = 0.0001
        assert result == Decimal("0.0001")


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
