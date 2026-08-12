"""
Unit tests for rate_units.py — explicit unit conversions and normalization.
"""
from decimal import Decimal

import pytest

from backend.app.core_finance.rate_units import (
    bp_to_decimal,
    bp_to_pct,
    decimal_to_bp,
    decimal_to_pct,
    detect_percent_unit_from_curve,
    normalize_annual_rate_to_decimal,
    normalize_percent_rate_to_decimal,
    pct_to_bp,
    pct_to_decimal,
)


class TestPctToDecimal:
    """Test percentage to decimal conversion."""

    def test_standard_conversion(self):
        """2.55% → 0.0255"""
        assert pct_to_decimal(2.55) == Decimal("0.0255")

    def test_zero(self):
        """0.0% → 0.0"""
        assert pct_to_decimal(0.0) == Decimal("0")

    def test_hundred_percent(self):
        """100.0% → 1.0"""
        assert pct_to_decimal(100.0) == Decimal("1")

    def test_small_percentage(self):
        """0.01% → 0.0001"""
        assert pct_to_decimal(Decimal("0.01")) == Decimal("0.0001")

    def test_large_percentage(self):
        """250.0% → 2.5"""
        assert pct_to_decimal(250.0) == Decimal("2.5")

    def test_returns_decimal(self):
        assert isinstance(pct_to_decimal(2.55), Decimal)


class TestDecimalToPct:
    """Test decimal to percentage conversion."""

    def test_standard_conversion(self):
        """0.0255 → 2.55%"""
        assert decimal_to_pct(Decimal("0.0255")) == Decimal("2.55")

    def test_zero(self):
        """0.0 → 0.0%"""
        assert decimal_to_pct(0.0) == Decimal("0")

    def test_one(self):
        """1.0 → 100.0%"""
        assert decimal_to_pct(1.0) == Decimal("100")

    def test_small_decimal(self):
        """0.0001 → 0.01%"""
        assert decimal_to_pct(Decimal("0.0001")) == Decimal("0.01")


class TestBpToDecimal:
    """Test basis points to decimal conversion."""

    def test_standard_conversion(self):
        """50 BP → 0.005"""
        assert bp_to_decimal(50) == Decimal("0.005")

    def test_zero(self):
        """0 BP → 0.0"""
        assert bp_to_decimal(0) == Decimal("0")

    def test_ten_thousand_bp(self):
        """10000 BP → 1.0"""
        assert bp_to_decimal(10000) == Decimal("1")

    def test_one_bp(self):
        """1 BP → 0.0001"""
        assert bp_to_decimal(1) == Decimal("0.0001")

    def test_large_bp(self):
        """25000 BP → 2.5"""
        assert bp_to_decimal(25000) == Decimal("2.5")


class TestDecimalToBp:
    """Test decimal to basis points conversion."""

    def test_standard_conversion(self):
        """0.005 → 50 BP"""
        assert decimal_to_bp(Decimal("0.005")) == Decimal("50")

    def test_zero(self):
        """0.0 → 0 BP"""
        assert decimal_to_bp(0.0) == Decimal("0")

    def test_one(self):
        """1.0 → 10000 BP"""
        assert decimal_to_bp(1.0) == Decimal("10000")

    def test_small_decimal(self):
        """0.0001 → 1 BP"""
        assert decimal_to_bp(Decimal("0.0001")) == Decimal("1")


class TestPctToBp:
    """Test percentage to basis points conversion."""

    def test_standard_conversion(self):
        """2.55% → 255 BP"""
        assert pct_to_bp(Decimal("2.55")) == Decimal("255.00")

    def test_zero(self):
        """0.0% → 0 BP"""
        assert pct_to_bp(0.0) == Decimal("0")

    def test_one_percent(self):
        """1.0% → 100 BP"""
        assert pct_to_bp(1.0) == Decimal("100")

    def test_hundred_percent(self):
        """100.0% → 10000 BP"""
        assert pct_to_bp(100.0) == Decimal("10000")


class TestBpToPct:
    """Test basis points to percentage conversion."""

    def test_standard_conversion(self):
        """255 BP → 2.55%"""
        assert bp_to_pct(255) == Decimal("2.55")

    def test_zero(self):
        """0 BP → 0.0%"""
        assert bp_to_pct(0) == Decimal("0")

    def test_hundred_bp(self):
        """100 BP → 1.0%"""
        assert bp_to_pct(100) == Decimal("1")

    def test_ten_thousand_bp(self):
        """10000 BP → 100.0%"""
        assert bp_to_pct(10000) == Decimal("100")


class TestNormalizeAnnualRateToDecimal:
    """Test heuristic normalization to decimal format."""

    def test_percentage_input(self):
        """2.55 (percentage) → 0.0255"""
        result = normalize_annual_rate_to_decimal(2.55)
        assert result == 0.0255

    def test_decimal_input(self):
        """0.0255 (already decimal) → 0.0255"""
        result = normalize_annual_rate_to_decimal(0.0255)
        assert result == 0.0255

    def test_zero(self):
        """0.0 → 0.0"""
        result = normalize_annual_rate_to_decimal(0.0)
        assert result == 0.0

    def test_one_decimal_boundary(self):
        """1.0 (edge case) remains decimal form."""
        result = normalize_annual_rate_to_decimal(1.0)
        assert result == 1.0

    def test_below_percent_correction_threshold(self):
        """1.5 remains decimal form; only values above 2 are corrected."""
        result = normalize_annual_rate_to_decimal(1.5)
        assert result == 1.5

    def test_hundred_returns_none(self):
        """100.0 is dirty rate data under the >20 guardrail."""
        result = normalize_annual_rate_to_decimal(100.0)
        assert result is None

    def test_above_twenty_returns_none(self):
        """150.0 (dirty data) → None"""
        result = normalize_annual_rate_to_decimal(150.0)
        assert result is None

    def test_negative_returns_none(self):
        """-2.5 (invalid) → None"""
        result = normalize_annual_rate_to_decimal(-2.5)
        assert result is None

    def test_none_input(self):
        """None → None"""
        result = normalize_annual_rate_to_decimal(None)
        assert result is None

    def test_nan_returns_none(self):
        """NaN → None"""
        result = normalize_annual_rate_to_decimal(float('nan'))
        assert result is None

    def test_inf_returns_none(self):
        """Infinity → None"""
        result = normalize_annual_rate_to_decimal(float('inf'))
        assert result is None

    def test_string_number(self):
        """'2.55' (string) → 0.0255"""
        result = normalize_annual_rate_to_decimal('2.55')
        assert result == 0.0255

    def test_invalid_string_returns_none(self):
        """'invalid' → None"""
        result = normalize_annual_rate_to_decimal('invalid')
        assert result is None

    def test_small_decimal(self):
        """0.0001 (already decimal) → 0.0001"""
        result = normalize_annual_rate_to_decimal(0.0001)
        assert result == 0.0001

    def test_boundary_at_one(self):
        """Test boundary behavior around 1.0."""
        # Exactly 1.0 is treated as decimal form.
        assert normalize_annual_rate_to_decimal(1.0) == 1.0

        # Just above 1.0 is also treated as decimal form.
        assert normalize_annual_rate_to_decimal(1.0001) == 1.0001

    def test_typical_bond_yields(self):
        """Test typical bond yield values."""
        # 3.5% stored as percentage
        assert normalize_annual_rate_to_decimal(3.5) == 0.035

        # 3.5% stored as decimal
        assert normalize_annual_rate_to_decimal(0.035) == 0.035

        # 12% stored as percentage
        assert normalize_annual_rate_to_decimal(12.0) == 0.12

    def test_one_percent_decimal_unchanged(self):
        """1% 存为 0.01，不应被误判"""
        assert normalize_annual_rate_to_decimal(0.01) == pytest.approx(0.01)

    def test_boundary_below_2_unchanged(self):
        """1.99 < 2，视为小数（199%），不触发 /100"""
        assert normalize_annual_rate_to_decimal(1.99) == pytest.approx(1.99)

    def test_boundary_exactly_2_unchanged(self):
        """2.0 不触发 /100（> 2 为 False），视为 200% 小数"""
        assert normalize_annual_rate_to_decimal(2.0) == pytest.approx(2.0)

    def test_boundary_exactly_20_corrected(self):
        """20.0 触发 /100（> 2 为 True，> 20 为 False），返回 0.20"""
        result = normalize_annual_rate_to_decimal(20.0)
        assert result == pytest.approx(0.20)

    def test_dirty_data_just_above_20_returns_none(self):
        """超过 20 的值视为脏数据，返回 None（含 20.01 / 25.0 边界）"""
        assert normalize_annual_rate_to_decimal(20.01) is None
        assert normalize_annual_rate_to_decimal(25.0) is None

    def test_string_decimal_input(self):
        assert normalize_annual_rate_to_decimal("0.0255") == pytest.approx(0.0255)

    def test_warning_logged_on_correction(self, caplog):
        """触发 /100 修正时应记录 WARNING"""
        import logging
        with caplog.at_level(logging.WARNING):
            normalize_annual_rate_to_decimal(3.5)
        assert "3.5" in caplog.text

    def test_warning_logged_on_dirty_data(self, caplog):
        """脏数据应记录 WARNING"""
        import logging
        with caplog.at_level(logging.WARNING):
            normalize_annual_rate_to_decimal(25.0)
        assert "25.0" in caplog.text


class TestNormalizePercentRateToDecimal:
    """百分数口径字段（zqtz 快照/余额事实的 coupon_rate、ytm_value）的显式归一。

    2026-07-19 取证（docs/audits/2026-07-19-system-calculation-audit.md）：
    落库单位为百分数（1.82 = 1.82%），[0.2, 2) 灰区约 39 万行不允许用
    >2 启发式静默放行。
    """

    def test_gray_zone_low_coupon_divided(self):
        """灰区核心回归：1.82（=1.82%）必须除以 100，不得当作小数 182%"""
        assert normalize_percent_rate_to_decimal(1.82) == pytest.approx(0.0182)

    def test_typical_percent_divided(self):
        assert normalize_percent_rate_to_decimal(2.38) == pytest.approx(0.0238)
        assert normalize_percent_rate_to_decimal(3.5) == pytest.approx(0.035)

    def test_sub_gray_zone_low_yield_divided(self):
        """百分数口径下 0.09 = 0.09%，同样除以 100"""
        assert normalize_percent_rate_to_decimal(0.09) == pytest.approx(0.0009)

    def test_dirty_data_above_20_percent_returns_none(self):
        """债券年利率超过 20% 视为脏数据（取证发现 ytm 最大值 20720.93）"""
        assert normalize_percent_rate_to_decimal(20.01) is None
        assert normalize_percent_rate_to_decimal(20720.9302) is None

    def test_boundary_exactly_20_percent_kept(self):
        assert normalize_percent_rate_to_decimal(20.0) == pytest.approx(0.20)

    def test_negative_returns_none(self):
        assert normalize_percent_rate_to_decimal(-0.75) is None

    def test_none_and_invalid_return_none(self):
        assert normalize_percent_rate_to_decimal(None) is None
        assert normalize_percent_rate_to_decimal("abc") is None
        assert normalize_percent_rate_to_decimal(float("nan")) is None
        assert normalize_percent_rate_to_decimal(float("inf")) is None

    def test_zero_returns_zero(self):
        assert normalize_percent_rate_to_decimal(0) == pytest.approx(0.0)

    def test_string_percent_input(self):
        assert normalize_percent_rate_to_decimal("1.61") == pytest.approx(0.0161)

    def test_dirty_data_warning_logged(self, caplog):
        import logging
        with caplog.at_level(logging.WARNING):
            normalize_percent_rate_to_decimal(25.0)
        assert "25.0" in caplog.text


class TestDetectPercentUnitFromCurve:
    def test_empty_returns_true(self):
        """空列表视为百分数（保守：不乘 100）"""
        assert detect_percent_unit_from_curve([]) is True

    def test_china_treasury_range(self):
        """中国国债 1.5-3.5% 视为百分数"""
        assert detect_percent_unit_from_curve([1.5, 2.5, 3.0, 3.5]) is True

    def test_decimal_form_detected(self):
        """0.015-0.035 小数形式被识别"""
        assert detect_percent_unit_from_curve([0.015, 0.025, 0.03]) is False

    def test_boundary_exactly_0_5(self):
        """0.5 边界：>= 0.5 视为百分数"""
        assert detect_percent_unit_from_curve([0.5]) is True

    def test_boundary_below_0_5(self):
        """0.49 视为小数"""
        assert detect_percent_unit_from_curve([0.49, 0.3]) is False


class TestRoundTripConversions:
    """Test round-trip conversions maintain precision."""

    def test_pct_decimal_roundtrip(self):
        """Percentage → Decimal → Percentage"""
        original = Decimal("2.55")
        result = decimal_to_pct(pct_to_decimal(original))
        assert result == original

    def test_bp_decimal_roundtrip(self):
        """BP → Decimal → BP"""
        original = Decimal("50")
        result = decimal_to_bp(bp_to_decimal(original))
        assert result == original

    def test_pct_bp_roundtrip(self):
        """Percentage → BP → Percentage"""
        original = Decimal("2.55")
        result = bp_to_pct(pct_to_bp(original))
        assert result == original
