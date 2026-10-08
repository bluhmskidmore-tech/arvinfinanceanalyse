"""Existing PnL half-up policy must not depend on the caller's decimal context."""
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_EVEN, localcontext

import pytest

from backend.app.tasks.pnl_by_business_precompute import _quantize_decimal, _quantize_ratio


@pytest.mark.parametrize("rounding", [ROUND_HALF_EVEN, ROUND_DOWN])
@pytest.mark.parametrize(("value", "expected"), [
    ("100.005", "100.01"), ("-100.005", "-100.01"),
    ("0.005", "0.01"), ("-0.005", "-0.01"),
    ("100.004", "100.00"), ("0", "0.00"),
])
def test_precompute_amount_uses_existing_half_up(value, expected, rounding):
    with localcontext() as ctx:
        ctx.rounding = rounding
        assert _quantize_decimal(Decimal(value)) == Decimal(expected)


@pytest.mark.parametrize("rounding", [ROUND_HALF_EVEN, ROUND_DOWN])
@pytest.mark.parametrize(("value", "expected"), [
    ("0.0000005", "0.000001"), ("-0.0000005", "-0.000001"),
    ("0.1234564", "0.123456"),
])
def test_precompute_ratio_preserves_six_places(value, expected, rounding):
    with localcontext() as ctx:
        ctx.rounding = rounding
        assert _quantize_ratio(Decimal(value)) == Decimal(expected)


def test_synthetic_two_day_average_is_independently_hand_calculated():
    # Two real observations in the same CNY unit: (100 + 100.01) / 2 = 100.005.
    assert _quantize_decimal((Decimal("100.00") + Decimal("100.01")) / 2) == Decimal("100.01")
