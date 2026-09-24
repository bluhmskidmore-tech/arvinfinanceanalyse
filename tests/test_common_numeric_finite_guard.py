"""Regression tests for non-finite values in shared Numeric serialization."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from backend.app.schemas.common_numeric import NumericUnit, null_numeric, numeric_from_raw


NON_FINITE_VALUES: list[Any] = [
    float("nan"),
    float("inf"),
    float("-inf"),
    Decimal("NaN"),
]

COMMON_UNITS: list[NumericUnit] = ["yuan", "pct", "dv01"]


@pytest.mark.parametrize("raw", NON_FINITE_VALUES)
@pytest.mark.parametrize("unit", COMMON_UNITS)
def test_numeric_from_raw_non_finite_values_return_null_numeric(unit: NumericUnit, raw: Any) -> None:
    numeric = numeric_from_raw(raw=raw, unit=unit, precision=3, sign_aware=False)
    expected = null_numeric(unit=unit, precision=3, sign_aware=False)

    assert numeric == expected
    assert numeric.raw is None
    assert numeric.display == "—"


@pytest.mark.parametrize("unit", COMMON_UNITS)
def test_numeric_from_raw_none_still_returns_null_numeric(unit: NumericUnit) -> None:
    numeric = numeric_from_raw(raw=None, unit=unit, precision=1, sign_aware=True)
    expected = null_numeric(unit=unit, precision=1, sign_aware=True)

    assert numeric == expected


def test_numeric_from_raw_finite_value_is_unchanged() -> None:
    numeric = numeric_from_raw(raw=1.25, unit="pct", precision=2, sign_aware=True, raw_scale="percent")

    assert numeric.raw == 0.0125
    assert numeric.display == "+1.25%"
    assert numeric.unit == "pct"
