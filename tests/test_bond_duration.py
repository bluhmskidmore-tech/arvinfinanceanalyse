"""
Unit tests for bond_duration.py — Macaulay duration, modified duration, convexity.
"""
from decimal import Decimal
from datetime import date


from backend.app.core_finance.bond_duration import (
    compute_macaulay_duration,
    modified_duration_from_macaulay,
    estimate_convexity_bond,
    _estimate_macaulay_duration_years,
    estimate_duration,
)


class TestComputeMacaulayDuration:
    """Test Macaulay duration closed-form formula."""

    def test_standard_coupon_bond(self):
        """Standard coupon bond with positive yield."""
        years = Decimal("5.0")
        coupon = Decimal("0.04")  # 4%
        ytm = Decimal("0.05")  # 5%
        frequency = 1

        duration = compute_macaulay_duration(years, coupon, ytm, frequency)

        assert duration > Decimal("0")
        assert duration <= years
        assert duration < years  # Duration < maturity for coupon bonds

    def test_zero_coupon_bond(self):
        """Zero coupon bond: duration = maturity."""
        years = Decimal("10.0")
        coupon = Decimal("0.0")
        ytm = Decimal("0.05")
        frequency = 1

        duration = compute_macaulay_duration(years, coupon, ytm, frequency)

        assert duration == years

    def test_matured_bond(self):
        """Bond at maturity: duration = 0."""
        years = Decimal("0.0")
        coupon = Decimal("0.04")
        ytm = Decimal("0.05")
        frequency = 1

        duration = compute_macaulay_duration(years, coupon, ytm, frequency)

        assert duration == Decimal("0")

    def test_short_maturity_bond(self):
        """Very short maturity (< 0.25 years): duration = maturity."""
        years = Decimal("0.1")
        coupon = Decimal("0.04")
        ytm = Decimal("0.05")
        frequency = 1

        duration = compute_macaulay_duration(years, coupon, ytm, frequency)

        assert duration == years

    def test_near_zero_yield(self):
        """Near-zero yield: use approximation formula."""
        years = Decimal("5.0")
        coupon = Decimal("0.04")
        ytm = Decimal("0.00005")  # Very low yield
        frequency = 1

        duration = compute_macaulay_duration(years, coupon, ytm, frequency)

        assert duration > Decimal("0")
        assert duration <= years

    def test_negative_yield(self):
        """Negative yield: fallback to maturity."""
        years = Decimal("5.0")
        coupon = Decimal("0.04")
        ytm = Decimal("-0.01")
        frequency = 1

        duration = compute_macaulay_duration(years, coupon, ytm, frequency)

        # Should use approximation or fallback
        assert duration > Decimal("0")

    def test_semiannual_frequency(self):
        """Bond with semiannual coupon payments."""
        years = Decimal("5.0")
        coupon = Decimal("0.04")
        ytm = Decimal("0.05")
        frequency = 2

        duration = compute_macaulay_duration(years, coupon, ytm, frequency)

        assert duration > Decimal("0")
        assert duration <= years

    def test_duration_decreases_with_higher_yield(self):
        """Duration decreases as yield increases (inverse relationship)."""
        years = Decimal("10.0")
        coupon = Decimal("0.05")
        frequency = 1

        duration_low_yield = compute_macaulay_duration(years, coupon, Decimal("0.03"), frequency)
        duration_high_yield = compute_macaulay_duration(years, coupon, Decimal("0.07"), frequency)

        assert duration_low_yield > duration_high_yield


class TestModifiedDuration:
    """Test modified duration = Macaulay / (1 + y/freq)."""

    def test_standard_conversion(self):
        """Standard Macaulay to modified duration conversion."""
        macaulay = Decimal("4.5")
        ytm = Decimal("0.05")
        frequency = 1

        modified = modified_duration_from_macaulay(macaulay, ytm, frequency)

        expected = macaulay / (Decimal("1") + ytm / Decimal("1"))
        assert abs(modified - expected) < Decimal("0.0001")

    def test_semiannual_frequency(self):
        """Modified duration with semiannual frequency."""
        macaulay = Decimal("4.5")
        ytm = Decimal("0.06")
        frequency = 2

        modified = modified_duration_from_macaulay(macaulay, ytm, frequency)

        expected = macaulay / (Decimal("1") + ytm / Decimal("2"))
        assert abs(modified - expected) < Decimal("0.0001")

    def test_zero_yield(self):
        """Zero yield: modified = Macaulay."""
        macaulay = Decimal("5.0")
        ytm = Decimal("0.0")
        frequency = 1

        modified = modified_duration_from_macaulay(macaulay, ytm, frequency)

        assert modified == macaulay

    def test_negative_yield(self):
        """Negative yield: fallback to Macaulay."""
        macaulay = Decimal("5.0")
        ytm = Decimal("-0.02")
        frequency = 1

        modified = modified_duration_from_macaulay(macaulay, ytm, frequency)

        assert modified == macaulay

    def test_wind_override(self):
        """Wind modified duration overrides calculation."""
        macaulay = Decimal("5.0")
        ytm = Decimal("0.05")
        frequency = 1
        wind_mod_dur = Decimal("4.2")

        modified = modified_duration_from_macaulay(macaulay, ytm, frequency, wind_mod_dur)

        assert modified == wind_mod_dur


class TestConvexity:
    """Test convexity estimation."""

    def test_positive_convexity(self):
        """Standard bond has positive convexity."""
        duration = Decimal("5.0")
        ytm = Decimal("0.05")
        frequency = 2

        convexity = estimate_convexity_bond(duration, ytm, coupon_frequency=frequency)

        assert convexity > Decimal("0")

    def test_zero_yield(self):
        """Zero yield: use approximation formula."""
        duration = Decimal("5.0")
        ytm = Decimal("0.0")
        frequency = 2

        convexity = estimate_convexity_bond(duration, ytm, coupon_frequency=frequency)

        assert convexity > Decimal("0")

    def test_negative_yield(self):
        """Negative yield: fallback formula."""
        duration = Decimal("5.0")
        ytm = Decimal("-0.01")
        frequency = 2

        convexity = estimate_convexity_bond(duration, ytm, coupon_frequency=frequency)

        assert convexity > Decimal("0")

    def test_wind_override(self):
        """Wind convexity overrides calculation."""
        duration = Decimal("5.0")
        ytm = Decimal("0.05")
        frequency = 2
        wind_convexity = Decimal("30.0")

        convexity = estimate_convexity_bond(duration, ytm, wind_convexity, frequency)

        assert convexity == wind_convexity

    def test_annual_frequency(self):
        """Convexity with annual frequency."""
        duration = Decimal("5.0")
        ytm = Decimal("0.05")
        frequency = 1

        convexity = estimate_convexity_bond(duration, ytm, coupon_frequency=frequency)

        assert convexity > Decimal("0")


class TestEstimateMacaulayDurationYears:
    """Test duration estimation from dates."""

    def test_standard_bond(self):
        """Standard bond with maturity in future."""
        maturity = date(2030, 12, 31)
        report = date(2026, 4, 17)
        coupon = Decimal("0.04")
        ytm = Decimal("0.05")

        duration = _estimate_macaulay_duration_years(maturity, report, coupon, ytm)

        assert duration > Decimal("0")
        years_to_maturity = Decimal((maturity - report).days) / Decimal("365")
        assert duration <= years_to_maturity

    def test_matured_bond(self):
        """Bond past maturity: duration = 0."""
        maturity = date(2020, 12, 31)
        report = date(2026, 4, 17)
        coupon = Decimal("0.04")
        ytm = Decimal("0.05")

        duration = _estimate_macaulay_duration_years(maturity, report, coupon, ytm)

        assert duration == Decimal("0")

    def test_zero_coupon_no_ytm(self):
        """Zero coupon bond without YTM: duration = maturity."""
        maturity = date(2030, 12, 31)
        report = date(2026, 4, 17)
        coupon = Decimal("0.0")
        ytm = None

        duration = _estimate_macaulay_duration_years(maturity, report, coupon, ytm)

        years_to_maturity = Decimal((maturity - report).days) / Decimal("365")
        assert duration == years_to_maturity

    def test_no_ytm_uses_coupon_as_yield(self):
        """No YTM provided: use coupon rate as yield."""
        maturity = date(2030, 12, 31)
        report = date(2026, 4, 17)
        coupon = Decimal("0.04")
        ytm = None

        duration = _estimate_macaulay_duration_years(maturity, report, coupon, ytm)

        assert duration > Decimal("0")


class TestEstimateDuration:
    """Test high-level duration estimation with fallbacks."""

    def test_short_term_paper(self):
        """Short-term commercial paper (SA/SCP): duration = 0.25."""
        maturity = date(2026, 7, 17)
        report = date(2026, 4, 17)
        coupon = Decimal("0.03")
        bond_code = "SA123456"

        duration = estimate_duration(maturity, report, coupon, bond_code)

        assert duration == Decimal("0.25")

    def test_scp_code(self):
        """SCP code: duration = 0.25."""
        maturity = date(2026, 7, 17)
        report = date(2026, 4, 17)
        coupon = Decimal("0.03")
        bond_code = "SCP123456"

        duration = estimate_duration(maturity, report, coupon, bond_code)

        assert duration == Decimal("0.25")

    def test_wind_metrics_override(self):
        """Wind metrics override calculation."""
        maturity = date(2030, 12, 31)
        report = date(2026, 4, 17)
        coupon = Decimal("0.04")
        bond_code = "123456.IB"
        wind_metrics = {"123456.IB": {"duration": Decimal("4.8")}}

        duration = estimate_duration(maturity, report, coupon, bond_code, wind_metrics=wind_metrics)

        assert duration == Decimal("4.8")

    def test_missing_maturity_uses_proxy(self):
        """Missing maturity: use proxy duration."""
        maturity = None
        report = date(2026, 4, 17)
        coupon = Decimal("0.04")
        bond_code = "123456.IB"

        duration = estimate_duration(maturity, report, coupon, bond_code)

        # Should return proxy duration (default 3.0)
        assert duration == Decimal("3.0")

    def test_standard_bond_with_ytm(self):
        """Standard bond with YTM provided."""
        maturity = date(2030, 12, 31)
        report = date(2026, 4, 17)
        coupon = Decimal("0.04")
        bond_code = "123456.IB"
        ytm = Decimal("0.05")

        duration = estimate_duration(maturity, report, coupon, bond_code, ytm=ytm)

        assert duration > Decimal("0")
        years_to_maturity = Decimal((maturity - report).days) / Decimal("365")
        assert duration <= years_to_maturity
