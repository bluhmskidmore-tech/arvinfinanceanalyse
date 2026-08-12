"""
Unit tests for bond_duration.py — Macaulay duration, modified duration, convexity.
"""
from datetime import date
from decimal import Decimal

from backend.app.core_finance.bond_duration import (
    _estimate_macaulay_duration_years,
    compute_macaulay_duration,
    estimate_convexity_bond,
    estimate_duration,
    infer_accounting_class,
    modified_duration_from_macaulay,
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

    def test_invalid_frequency_falls_back_to_annual(self):
        """Invalid coupon frequency should not mask duration fallback with NameError."""
        years = Decimal("5.0")
        coupon = Decimal("0.04")
        ytm = Decimal("0.05")

        duration = compute_macaulay_duration(years, coupon, ytm, 0)
        annual_duration = compute_macaulay_duration(years, coupon, ytm, 1)

        assert duration == annual_duration

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

    def test_invalid_frequency_returns_macaulay(self):
        """Invalid coupon frequency should fail closed to Macaulay duration."""
        macaulay = Decimal("5.0")
        ytm = Decimal("0.05")

        modified = modified_duration_from_macaulay(macaulay, ytm, 0)

        assert modified == macaulay

    def test_wind_override(self):
        """Wind modified duration overrides calculation."""
        macaulay = Decimal("5.0")
        ytm = Decimal("0.05")
        frequency = 1
        wind_mod_dur = Decimal("4.2")

        modified = modified_duration_from_macaulay(macaulay, ytm, frequency, wind_mod_dur)

        assert modified == wind_mod_dur

    def test_mod_dur_less_than_macaulay(self):
        """修正久期应小于麦考利久期（正利率）"""
        mac = Decimal("5.0")
        mod = modified_duration_from_macaulay(mac, Decimal("0.03"), 2, wind_mod_dur=None)
        assert mod < mac


class TestInferAccountingClass:
    """会计分类推断（从 backend/tests 迁入）。"""

    def test_ac_from_amortized_cost(self):
        assert infer_accounting_class("摊余成本债权投资") == "AC"

    def test_ac_from_bare_amortized(self):
        assert infer_accounting_class("摊余") == "AC"

    def test_oci_from_fvoci(self):
        assert infer_accounting_class("其他债权投资OCI") == "OCI"

    def test_oci_from_available_for_sale(self):
        assert infer_accounting_class("可供出售金融资产") == "OCI"

    def test_tpl_from_trading(self):
        assert infer_accounting_class("交易性金融资产") == "TPL"

    def test_none_returns_tpl(self):
        assert infer_accounting_class(None) == "TPL"

    def test_empty_string_returns_tpl(self):
        assert infer_accounting_class("") == "TPL"

    def test_unknown_returns_tpl(self):
        assert infer_accounting_class("未知资产类别XYZ") == "TPL"


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

    def test_normal_bond_duration_in_range(self):
        """正常债券久期应在合理范围内"""
        dur = estimate_duration(
            maturity_date=date(2027, 12, 31),
            report_date=date(2024, 1, 31),
            coupon_rate=Decimal("0.03"),
            ytm=Decimal("0.03"),
        )
        assert Decimal("1") < dur < Decimal("5")

    def test_short_term_bond_low_duration(self):
        """短期债券久期应小于长期债券"""
        short = estimate_duration(
            maturity_date=date(2024, 6, 30),
            report_date=date(2024, 1, 31),
            coupon_rate=Decimal("0.03"),
            ytm=Decimal("0.03"),
        )
        long_ = estimate_duration(
            maturity_date=date(2034, 1, 31),
            report_date=date(2024, 1, 31),
            coupon_rate=Decimal("0.03"),
            ytm=Decimal("0.03"),
        )
        assert short < long_

    def test_zero_coupon_duration_equals_maturity(self):
        """零息债券久期应接近到期年限"""
        dur = estimate_duration(
            maturity_date=date(2029, 1, 31),
            report_date=date(2024, 1, 31),
            coupon_rate=Decimal("0"),
            ytm=Decimal("0.03"),
        )
        # 2024-01-31 到 2029-01-31 实际约 5.003 年（含闰年），允许 ±0.1
        assert Decimal("4.9") < dur < Decimal("5.1")

    def test_returns_decimal(self):
        dur = estimate_duration(
            maturity_date=date(2027, 12, 31),
            report_date=date(2024, 1, 31),
            coupon_rate=Decimal("0.03"),
        )
        assert isinstance(dur, Decimal)
