"""共享 M-3：balance workbook Decimal 助手不得传播 NaN。

测试对象说明（2026-08-12）：生产权威实现是单体 balance_analysis_workbook.py；
`balance_workbook/` 包（`_utils` 等）是不在生产调用路径上的拆分副本，包级公开入口
`builder.py` 仅为委托壳。本测试同时钉住两侧的 NaN 防护语义：
- 单体侧防护入口是 `_decimal_value`（NaN/None → 0）；
- 副本侧防护入口是 `_utils._to_finite_decimal` / `_utils._sum_decimal`。
两侧断言都保留，防止休眠副本与权威实现在 NaN 语义上漂移。
"""

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
