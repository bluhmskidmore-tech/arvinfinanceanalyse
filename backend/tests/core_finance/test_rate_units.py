"""Tests for rate_units.normalize_annual_rate_to_decimal."""
import pytest
from backend.app.core_finance.rate_units import normalize_annual_rate_to_decimal


class TestNormalizeAnnualRateToDecimal:

    def test_decimal_input_unchanged(self):
        """小数格式输入不应被除以100"""
        assert normalize_annual_rate_to_decimal(0.0255) == pytest.approx(0.0255)

    def test_small_decimal_unchanged(self):
        """0.5% 存为 0.005，不应被误判为百分数"""
        assert normalize_annual_rate_to_decimal(0.005) == pytest.approx(0.005)

    def test_one_percent_decimal_unchanged(self):
        """1% 存为 0.01，不应被误判"""
        assert normalize_annual_rate_to_decimal(0.01) == pytest.approx(0.01)

    def test_boundary_below_2_unchanged(self):
        """1.99 < 2，视为小数（199%），不触发 /100"""
        assert normalize_annual_rate_to_decimal(1.99) == pytest.approx(1.99)

    def test_boundary_exactly_2_unchanged(self):
        """2.0 不触发 /100（> 2 为 False），视为 200% 小数"""
        assert normalize_annual_rate_to_decimal(2.0) == pytest.approx(2.0)

    def test_boundary_above_2_corrected(self):
        """2.55 > 2，视为百分数误入，除以100 → 0.0255"""
        assert normalize_annual_rate_to_decimal(2.55) == pytest.approx(0.0255)

    def test_large_percent_corrected(self):
        """明显的百分数（如 3.5）应被除以100"""
        assert normalize_annual_rate_to_decimal(3.5) == pytest.approx(0.035)

    def test_boundary_exactly_20_corrected(self):
        """20.0 触发 /100（> 2 为 True，> 20 为 False），返回 0.20"""
        result = normalize_annual_rate_to_decimal(20.0)
        assert result == pytest.approx(0.20)

    def test_dirty_data_above_20_returns_none(self):
        """超过 20 的值视为脏数据，返回 None"""
        assert normalize_annual_rate_to_decimal(20.01) is None
        assert normalize_annual_rate_to_decimal(25.0) is None
        assert normalize_annual_rate_to_decimal(100.0) is None

    def test_negative_returns_none(self):
        assert normalize_annual_rate_to_decimal(-0.01) is None

    def test_none_returns_none(self):
        assert normalize_annual_rate_to_decimal(None) is None

    def test_string_decimal_input(self):
        assert normalize_annual_rate_to_decimal("0.0255") == pytest.approx(0.0255)

    def test_string_percent_input(self):
        assert normalize_annual_rate_to_decimal("3.5") == pytest.approx(0.035)

    def test_zero_returns_zero(self):
        assert normalize_annual_rate_to_decimal(0) == pytest.approx(0.0)

    def test_nan_returns_none(self):
        import math
        assert normalize_annual_rate_to_decimal(float("nan")) is None

    def test_inf_returns_none(self):
        assert normalize_annual_rate_to_decimal(float("inf")) is None

    def test_invalid_string_returns_none(self):
        assert normalize_annual_rate_to_decimal("abc") is None

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
