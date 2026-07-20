"""共享 M-3：balance workbook Decimal 助手不得传播 NaN。"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

from backend.app.core_finance.balance_analysis_workbook import _decimal_value
from backend.app.core_finance.balance_workbook._utils import _sum_decimal, _to_finite_decimal


def test_decimal_value_maps_nan_to_zero() -> None:
    assert _decimal_value(Decimal("NaN")) == Decimal("0")
    assert _decimal_value("NaN") == Decimal("0")
    assert _decimal_value(None) == Decimal("0")


def test_to_finite_decimal_and_sum_skip_nan() -> None:
    assert _to_finite_decimal(Decimal("NaN")) == Decimal("0")
    rows = [
        SimpleNamespace(amount=Decimal("10")),
        SimpleNamespace(amount=Decimal("NaN")),
        SimpleNamespace(amount=Decimal("5")),
    ]
    assert _sum_decimal(rows, lambda r: r.amount) == Decimal("15")
