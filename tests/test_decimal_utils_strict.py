# 回归：decimal_utils.to_decimal_strict 严格性；to_decimal(None) 仍为宽松 0。
from __future__ import annotations

from decimal import Decimal

import pytest

from backend.app.core_finance.decimal_utils import to_decimal, to_decimal_strict


def test_to_decimal_strict_rejects_none() -> None:
    with pytest.raises(TypeError):
        to_decimal_strict(None)


def test_to_decimal_strict_rejects_nan_inf() -> None:
    with pytest.raises(ValueError):
        to_decimal_strict(float("nan"))
    with pytest.raises(ValueError):
        to_decimal_strict(float("inf"))


def test_to_decimal_strict_accepts_values() -> None:
    assert to_decimal_strict(Decimal("123.45")) == Decimal("123.45")
    assert to_decimal_strict(0) == Decimal("0")
    assert to_decimal_strict("123.45") == Decimal("123.45")


def test_to_decimal_lenient_none_still_zero() -> None:
    assert to_decimal(None) == Decimal("0")
