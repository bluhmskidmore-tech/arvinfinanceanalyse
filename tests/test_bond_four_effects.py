"""
Unit tests for bond_four_effects.py — single-bond four-effect attribution.

Covers:
- Income effect: coupon accrual over period
- Treasury effect: price change from benchmark yield move
- Spread effect: price change from spread change
- Selection effect: residual = total - income - treasury - spread
- Four effects sum to total return (within 1bp tolerance)
- Edge cases: zero coupon bond, negative yield, zero duration
"""
import pytest
from datetime import date
from decimal import Decimal

from backend.app.core_finance.bond_four_effects import compute_bond_four_effects


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_bond(
    coupon_rate=0.03,
    face_value=10_000_000.0,
    market_value_start=10_000_000.0,
    market_value_end=10_050_000.0,
    ytm=0.035,
    asset_class="AAA企业债",
    maturity_date=date(2030, 12, 31),
    bond_code="TEST001.IB",
    accrued_interest_start=None,
    accrued_interest_end=None,
):
    bond = {
        "bond_code": bond_code,
        "coupon_rate_start": coupon_rate,
        "face_value_start": face_value,
        "market_value_start": market_value_start,
        "market_value_end": market_value_end,
        "yield_to_maturity_start": ytm,
        "asset_class_start": asset_class,
        "maturity_date_start": maturity_date,
    }
    if accrued_interest_start is not None:
        bond["accrued_interest_start"] = accrued_interest_start
    if accrued_interest_end is not None:
        bond["accrued_interest_end"] = accrued_interest_end
    return bond


# ---------------------------------------------------------------------------
# Income effect
# ---------------------------------------------------------------------------

class TestIncomeEffect:
    """Income = coupon_rate * face_value * num_days / 365."""

    def test_basic_income_accrual(self):
        bond = _make_bond(coupon_rate=0.03, face_value=10_000_000.0)
        result = compute_bond_four_effects(
            bond,
            num_days=30,
            benchmark_yield_change=Decimal("0"),
            spread_change=Decimal("0"),
            report_date=date(2026, 1, 1),
        )
        # 0.03 * 10_000_000 * 30 / 365
        expected = Decimal("0.03") * Decimal("10000000") * Decimal("30") / Decimal("365")
        assert float(result["income_return"]) == pytest.approx(float(expected), rel=1e-6)

    def test_percent_coupon_input_is_normalized_before_accrual(self):
        bond = _make_bond(coupon_rate=3.0, face_value=10_000_000.0)
        result = compute_bond_four_effects(
            bond,
            num_days=30,
            benchmark_yield_change=Decimal("0"),
            spread_change=Decimal("0"),
            report_date=date(2026, 1, 1),
        )
        expected = Decimal("0.03") * Decimal("10000000") * Decimal("30") / Decimal("365")
        assert result["income_return"] == pytest.approx(expected)

    def test_income_scales_with_days(self):
        bond = _make_bond(coupon_rate=0.04, face_value=5_000_000.0)
        r30 = compute_bond_four_effects(
            bond, 30, Decimal("0"), Decimal("0"), date(2026, 1, 1)
        )
        r60 = compute_bond_four_effects(
            bond, 60, Decimal("0"), Decimal("0"), date(2026, 1, 1)
        )
        assert float(r60["income_return"]) == pytest.approx(
            float(r30["income_return"]) * 2, rel=1e-6
        )

    def test_income_scales_with_coupon(self):
        bond_low = _make_bond(coupon_rate=0.02, face_value=10_000_000.0)
        bond_high = _make_bond(coupon_rate=0.04, face_value=10_000_000.0)
        r_low = compute_bond_four_effects(
            bond_low, 30, Decimal("0"), Decimal("0"), date(2026, 1, 1)
        )
        r_high = compute_bond_four_effects(
            bond_high, 30, Decimal("0"), Decimal("0"), date(2026, 1, 1)
        )
        assert float(r_high["income_return"]) == pytest.approx(
            float(r_low["income_return"]) * 2, rel=1e-6
        )


# ---------------------------------------------------------------------------
# Treasury effect
# ---------------------------------------------------------------------------

class TestTreasuryEffect:
    """Treasury effect = -mod_duration * benchmark_yield_change * mv_start."""

    def test_positive_yield_rise_negative_treasury_effect(self):
        """Rising yields → negative price impact."""
        bond = _make_bond(
            coupon_rate=0.03,
            face_value=10_000_000.0,
            market_value_start=10_000_000.0,
            market_value_end=9_950_000.0,
            ytm=0.03,
            maturity_date=date(2031, 1, 1),
        )
        result = compute_bond_four_effects(
            bond,
            num_days=30,
            benchmark_yield_change=Decimal("0.005"),  # +50bp
            spread_change=Decimal("0"),
            report_date=date(2026, 1, 1),
        )
        assert float(result["treasury_effect"]) < 0

    def test_yield_fall_positive_treasury_effect(self):
        """Falling yields → positive price impact."""
        bond = _make_bond(
            coupon_rate=0.03,
            face_value=10_000_000.0,
            market_value_start=10_000_000.0,
            market_value_end=10_050_000.0,
            ytm=0.03,
            maturity_date=date(2031, 1, 1),
        )
        result = compute_bond_four_effects(
            bond,
            num_days=30,
            benchmark_yield_change=Decimal("-0.005"),  # -50bp
            spread_change=Decimal("0"),
            report_date=date(2026, 1, 1),
        )
        assert float(result["treasury_effect"]) > 0

    def test_zero_yield_change_zero_treasury_effect(self):
        """No yield change → zero treasury effect."""
        bond = _make_bond(maturity_date=date(2031, 1, 1))
        result = compute_bond_four_effects(
            bond, 30, Decimal("0"), Decimal("0"), date(2026, 1, 1)
        )
        assert float(result["treasury_effect"]) == pytest.approx(0.0, abs=1e-6)

    def test_treasury_effect_proportional_to_mv(self):
        """Treasury effect scales linearly with market value."""
        bond_small = _make_bond(
            market_value_start=5_000_000.0,
            market_value_end=4_975_000.0,
            maturity_date=date(2031, 1, 1),
        )
        bond_large = _make_bond(
            market_value_start=10_000_000.0,
            market_value_end=9_950_000.0,
            maturity_date=date(2031, 1, 1),
        )
        r_small = compute_bond_four_effects(
            bond_small, 30, Decimal("0.005"), Decimal("0"), date(2026, 1, 1)
        )
        r_large = compute_bond_four_effects(
            bond_large, 30, Decimal("0.005"), Decimal("0"), date(2026, 1, 1)
        )
        assert float(r_large["treasury_effect"]) == pytest.approx(
            float(r_small["treasury_effect"]) * 2, rel=1e-4
        )


# ---------------------------------------------------------------------------
# Spread effect
# ---------------------------------------------------------------------------

class TestSpreadEffect:
    """Spread effect = -mod_duration * spread_change * mv_start."""

    def test_spread_widening_negative_effect(self):
        """Spread widening → negative price impact."""
        bond = _make_bond(maturity_date=date(2031, 1, 1))
        result = compute_bond_four_effects(
            bond,
            num_days=30,
            benchmark_yield_change=Decimal("0"),
            spread_change=Decimal("0.001"),  # +10bp
            report_date=date(2026, 1, 1),
        )
        assert float(result["spread_effect"]) < 0

    def test_spread_tightening_positive_effect(self):
        """Spread tightening → positive price impact."""
        bond = _make_bond(maturity_date=date(2031, 1, 1))
        result = compute_bond_four_effects(
            bond,
            num_days=30,
            benchmark_yield_change=Decimal("0"),
            spread_change=Decimal("-0.001"),  # -10bp
            report_date=date(2026, 1, 1),
        )
        assert float(result["spread_effect"]) > 0

    def test_zero_spread_change_zero_spread_effect(self):
        """No spread change → zero spread effect."""
        bond = _make_bond(maturity_date=date(2031, 1, 1))
        result = compute_bond_four_effects(
            bond, 30, Decimal("0"), Decimal("0"), date(2026, 1, 1)
        )
        assert float(result["spread_effect"]) == pytest.approx(0.0, abs=1e-6)


# ---------------------------------------------------------------------------
# Selection effect
# ---------------------------------------------------------------------------

class TestSelectionEffect:
    """Selection = total_return - income - treasury - spread."""

    def test_selection_is_residual(self):
        """Selection effect is exactly the residual."""
        bond = _make_bond(
            market_value_start=10_000_000.0,
            market_value_end=10_080_000.0,
            maturity_date=date(2031, 1, 1),
        )
        result = compute_bond_four_effects(
            bond,
            num_days=30,
            benchmark_yield_change=Decimal("0.002"),
            spread_change=Decimal("0.0005"),
            report_date=date(2026, 1, 1),
        )
        expected_selection = (
            float(result["total_return"])
            - float(result["income_return"])
            - float(result["treasury_effect"])
            - float(result["spread_effect"])
        )
        assert float(result["selection_effect"]) == pytest.approx(expected_selection, abs=1e-6)


# ---------------------------------------------------------------------------
# Four effects sum to total return
# ---------------------------------------------------------------------------

class TestFourEffectsSumToTotal:
    """income + treasury + spread + selection == total_return within 1bp tolerance."""

    def _assert_sum(self, result, mv_start, tolerance_bp=1):
        """Assert sum of effects equals total within tolerance (in absolute yuan)."""
        total = float(result["total_return"])
        components = (
            float(result["income_return"])
            + float(result["treasury_effect"])
            + float(result["spread_effect"])
            + float(result["selection_effect"])
        )
        # 1bp tolerance relative to mv_start
        tolerance = mv_start * 0.0001
        assert abs(components - total) < tolerance, (
            f"Sum of effects {components:.4f} != total_return {total:.4f}, "
            f"diff={abs(components - total):.4f}"
        )

    def test_standard_bond_no_accrued(self):
        """Standard bond without accrued interest fields."""
        bond = _make_bond(
            coupon_rate=0.03,
            face_value=10_000_000.0,
            market_value_start=10_000_000.0,
            market_value_end=10_060_000.0,
            ytm=0.035,
            maturity_date=date(2030, 6, 30),
        )
        result = compute_bond_four_effects(
            bond, 30, Decimal("0.002"), Decimal("0.0005"), date(2026, 1, 1)
        )
        self._assert_sum(result, 10_000_000.0)

    def test_bond_with_accrued_interest(self):
        """Bond with accrued interest uses full-price basis."""
        bond = _make_bond(
            coupon_rate=0.03,
            face_value=10_000_000.0,
            market_value_start=10_000_000.0,
            market_value_end=10_050_000.0,
            ytm=0.035,
            maturity_date=date(2030, 6, 30),
            accrued_interest_start=25_000.0,
            accrued_interest_end=50_000.0,
        )
        result = compute_bond_four_effects(
            bond, 30, Decimal("0.001"), Decimal("0.0003"), date(2026, 1, 1)
        )
        self._assert_sum(result, 10_000_000.0)

    def test_yield_rise_scenario(self):
        """Rising yield environment."""
        bond = _make_bond(
            market_value_start=8_000_000.0,
            market_value_end=7_920_000.0,
            ytm=0.04,
            maturity_date=date(2033, 3, 31),
        )
        result = compute_bond_four_effects(
            bond, 90, Decimal("0.01"), Decimal("0.002"), date(2026, 1, 1)
        )
        self._assert_sum(result, 8_000_000.0)

    def test_yield_fall_scenario(self):
        """Falling yield environment."""
        bond = _make_bond(
            market_value_start=12_000_000.0,
            market_value_end=12_180_000.0,
            ytm=0.025,
            maturity_date=date(2028, 9, 30),
        )
        result = compute_bond_four_effects(
            bond, 60, Decimal("-0.005"), Decimal("-0.001"), date(2026, 1, 1)
        )
        self._assert_sum(result, 12_000_000.0)


# ---------------------------------------------------------------------------
# AC class
# ---------------------------------------------------------------------------

class TestACClass:
    """AC (held-to-maturity) bonds: only income effect, rest zeroed."""

    def test_ac_class_zeroes_market_effects(self):
        bond = _make_bond(
            asset_class="持有至到期债券",
            market_value_start=5_000_000.0,
            market_value_end=5_200_000.0,
            maturity_date=date(2035, 12, 31),
        )
        result = compute_bond_four_effects(
            bond, 90, Decimal("0.01"), Decimal("0.002"), date(2026, 1, 1)
        )
        assert result["treasury_effect"] == Decimal("0")
        assert result["spread_effect"] == Decimal("0")
        assert result["selection_effect"] == Decimal("0")
        assert result["total_return"] == result["income_return"]

    def test_ac_摊余成本_class(self):
        bond = _make_bond(asset_class="摊余成本法债券")
        result = compute_bond_four_effects(
            bond, 30, Decimal("0.005"), Decimal("0.001"), date(2026, 1, 1)
        )
        assert result["treasury_effect"] == Decimal("0")
        assert result["spread_effect"] == Decimal("0")


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge cases: zero coupon, negative yield, zero duration, missing maturity."""

    def test_zero_coupon_bond(self):
        """Zero coupon bond: income effect should be zero."""
        bond = _make_bond(
            coupon_rate=0.0,
            face_value=10_000_000.0,
            market_value_start=9_000_000.0,
            market_value_end=9_100_000.0,
            ytm=0.03,
            maturity_date=date(2030, 12, 31),
        )
        result = compute_bond_four_effects(
            bond, 30, Decimal("0.001"), Decimal("0"), date(2026, 1, 1)
        )
        assert float(result["income_return"]) == pytest.approx(0.0, abs=1e-6)
        # Duration should still be computed (equals years to maturity for zero coupon)
        assert float(result["mod_duration"]) > 0

    def test_negative_yield(self):
        """Negative YTM should not crash; duration falls back gracefully."""
        bond = _make_bond(
            coupon_rate=0.01,
            ytm=-0.005,
            market_value_start=10_500_000.0,
            market_value_end=10_520_000.0,
            maturity_date=date(2028, 6, 30),
        )
        result = compute_bond_four_effects(
            bond, 30, Decimal("-0.001"), Decimal("0"), date(2026, 1, 1)
        )
        # Should complete without exception
        assert "income_return" in result
        assert "total_return" in result

    def test_missing_maturity_date(self):
        """Missing maturity uses proxy years (3.0) per bond_duration._estimate_duration_proxy_years."""
        bond = _make_bond(maturity_date=None)
        result = compute_bond_four_effects(
            bond, 30, Decimal("0.002"), Decimal("0.001"), date(2026, 1, 1)
        )
        md = float(result["mod_duration"])
        assert 0.15 < md < 0.35
        assert "total_return" in result

    def test_zero_market_value_start(self):
        """Zero market value start: treasury and spread effects should be zero."""
        bond = _make_bond(
            market_value_start=0.0,
            market_value_end=0.0,
            face_value=0.0,
            coupon_rate=0.03,
            maturity_date=date(2030, 12, 31),
        )
        result = compute_bond_four_effects(
            bond, 30, Decimal("0.005"), Decimal("0.001"), date(2026, 1, 1)
        )
        assert float(result["treasury_effect"]) == pytest.approx(0.0, abs=1e-6)
        assert float(result["spread_effect"]) == pytest.approx(0.0, abs=1e-6)
        assert float(result["income_return"]) == pytest.approx(0.0, abs=1e-6)

    def test_very_short_maturity(self):
        """Bond maturing in 1 day: duration should be near zero."""
        bond = _make_bond(
            maturity_date=date(2026, 1, 2),  # 1 day from report_date
            coupon_rate=0.03,
            ytm=0.03,
        )
        result = compute_bond_four_effects(
            bond, 1, Decimal("0.001"), Decimal("0"), date(2026, 1, 1)
        )
        assert float(result["mod_duration"]) < 0.1

    def test_long_maturity_bond(self):
        """30-year bond: duration should be substantial."""
        bond = _make_bond(
            coupon_rate=0.04,
            ytm=0.04,
            maturity_date=date(2056, 1, 1),
            market_value_start=10_000_000.0,
            market_value_end=9_800_000.0,
        )
        result = compute_bond_four_effects(
            bond, 30, Decimal("0.005"), Decimal("0"), date(2026, 1, 1)
        )
        # Long bond should have significant duration
        assert float(result["mod_duration"]) > 5.0
        # Large yield rise should produce significant negative treasury effect
        assert float(result["treasury_effect"]) < -100_000

    def test_single_day_period(self):
        """Single day period: income should be 1/365 of annual coupon."""
        bond = _make_bond(coupon_rate=0.0365, face_value=10_000_000.0)
        result = compute_bond_four_effects(
            bond, 1, Decimal("0"), Decimal("0"), date(2026, 1, 1)
        )
        # 0.0365 * 10_000_000 * 1 / 365 = 1000
        assert float(result["income_return"]) == pytest.approx(1000.0, rel=1e-4)

    def test_result_keys_present(self):
        """All expected keys should be present in result."""
        bond = _make_bond()
        result = compute_bond_four_effects(
            bond, 30, Decimal("0"), Decimal("0"), date(2026, 1, 1)
        )
        expected_keys = {
            "income_return",
            "treasury_effect",
            "spread_effect",
            "selection_effect",
            "total_return",
            "total_price_change",
            "mod_duration",
        }
        assert expected_keys.issubset(result.keys())

    def test_total_price_change_is_mv_diff(self):
        """total_price_change should always equal mv_end - mv_start."""
        bond = _make_bond(
            market_value_start=10_000_000.0,
            market_value_end=10_075_000.0,
        )
        result = compute_bond_four_effects(
            bond, 30, Decimal("0.001"), Decimal("0"), date(2026, 1, 1)
        )
        assert float(result["total_price_change"]) == pytest.approx(75_000.0, abs=1e-4)
