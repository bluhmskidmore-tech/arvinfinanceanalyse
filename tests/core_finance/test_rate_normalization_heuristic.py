"""Tests for rate unit normalization — boundary cases and deterministic paths."""

import logging

import pytest

from backend.app.core_finance.adb_rate_normalize import (
    RATE_INPUT_OVERRIDES,
    _normalize_auto_value,
    normalize_rate_values,
)


class TestDeterministicPaths:
    """All known fields should now use deterministic (non-auto) paths."""

    @pytest.mark.parametrize(
        "field_name,expected_mode",
        [
            ("yield_to_maturity", "percent"),
            ("coupon_rate", "percent"),
            ("interest_rate", "percent"),
            ("interbank_interest_rate", "percent"),
        ],
    )
    def test_all_known_fields_use_percent_mode(self, field_name, expected_mode):
        assert RATE_INPUT_OVERRIDES.get(field_name) == expected_mode

    @pytest.mark.parametrize(
        "input_values,field,expected",
        [
            # 2.55% 存储为 2.55 → 应输出 0.0255
            ([2.55], "interest_rate", [0.0255]),
            # 0.5% 存储为 0.5 → 应输出 0.005（旧 auto 模式会错误返回 0.5）
            ([0.5], "interest_rate", [0.005]),
            # 0.08% 存储为 0.08 → 应输出 0.0008
            ([0.08], "interest_rate", [0.0008]),
            # 边界：1.0% → 0.01
            ([1.0], "interest_rate", [0.01]),
            # 边界：100% → 1.0
            ([100.0], "interest_rate", [1.0]),
            # None → 0.0
            ([None], "interest_rate", [0.0]),
            # 混合
            ([2.4, 0.5, None, "bad"], "interest_rate", [0.024, 0.005, 0.0, 0.0]),
        ],
    )
    def test_interest_rate_percent_mode(self, input_values, field, expected):
        result = normalize_rate_values(input_values, field)
        assert result == pytest.approx(expected, abs=1e-10)

    @pytest.mark.parametrize(
        "input_values,field,expected",
        [
            # yield_to_maturity: 3.5% → 0.035
            ([3.5], "yield_to_maturity", [0.035]),
            # coupon_rate: 2.85% → 0.0285
            ([2.85], "coupon_rate", [0.0285]),
        ],
    )
    def test_bond_rate_fields_percent_mode(self, input_values, field, expected):
        result = normalize_rate_values(input_values, field)
        assert result == pytest.approx(expected, abs=1e-10)


class TestAutoModeDeprecationWarning:
    """Auto mode should emit a deprecation warning."""

    def test_unknown_field_triggers_warning(self, caplog):
        with caplog.at_level(logging.WARNING):
            result = normalize_rate_values([2.5], "some_unknown_field")
        assert "auto rate normalization is deprecated" in caplog.text
        # auto mode still works as fallback
        assert result == [0.025]  # 2.5 in [1,100] → /100


class TestAutoModeEdgeCases:
    """Document the known edge cases of the deprecated auto heuristic."""

    @pytest.mark.parametrize(
        "value,expected",
        [
            (0.5, 0.5),  # BUG: 0.5% misclassified as decimal 0.5
            (0.99, 0.99),  # BUG: same issue
            (1.0, 0.01),  # boundary: treated as percent
            (100.0, 1.0),  # boundary: treated as percent
            (100.1, 100.1),  # above range: treated as decimal (likely dirty data)
            (0.035, 0.035),  # below range: treated as decimal (correct for actual decimals)
        ],
    )
    def test_auto_heuristic_known_behavior(self, value, expected, caplog):
        """Documents auto mode behavior — these are NOT all correct, just documented."""
        with caplog.at_level(logging.WARNING):
            result = _normalize_auto_value(value)
        assert "_normalize_auto_value is deprecated" in caplog.text
        assert result == pytest.approx(expected, abs=1e-10)
