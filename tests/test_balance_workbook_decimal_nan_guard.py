"""共享 M-3 + 2026-07-20 审计 P2：balance workbook Decimal 助手不得传播 NaN。

测试对象说明（2026-08-12）：生产权威实现是单体 balance_analysis_workbook.py；
`balance_workbook/` 包（`_utils` 等）是不在生产调用路径上的拆分副本，包级公开入口
`builder.py` 仅为委托壳。NaN 防线已双侧统一到 `_to_finite_decimal` 模式：
`_sum_decimal` / `_weighted_average` / `_merged_weighted_average` / `_rate_value` /
`_decimal_value` 在两侧对 NaN/None/非法输入具有相同语义（→ 0 或跳过权重）。
本测试对两侧逐一断言，防止休眠副本与权威实现在 NaN 语义上漂移。
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

from backend.app.core_finance import balance_analysis_workbook as authoritative_module
from backend.app.core_finance.balance_analysis_workbook import _decimal_value
from backend.app.core_finance.balance_workbook import _utils as package_module
from backend.app.core_finance.balance_workbook._utils import _sum_decimal, _to_finite_decimal

_BOTH_SIDES = (authoritative_module, package_module)


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


def test_decimal_helpers_share_nan_defense_on_both_sides() -> None:
    rows = [
        SimpleNamespace(amount=Decimal("10")),
        SimpleNamespace(amount=Decimal("NaN")),
        SimpleNamespace(amount=Decimal("5")),
    ]
    for module in _BOTH_SIDES:
        assert module._to_finite_decimal(Decimal("NaN")) == Decimal("0")
        assert module._sum_decimal(rows, lambda r: r.amount) == Decimal("15")
        assert module._decimal_value(Decimal("NaN")) == Decimal("0")
        assert module._decimal_value(None) == Decimal("0")
        assert module._rate_value(Decimal("NaN")) == Decimal("0")
        assert module._rate_value(None) == Decimal("0")


def test_weighted_average_helpers_skip_nan_weight_on_both_sides() -> None:
    rows = [
        SimpleNamespace(weight=Decimal("NaN"), value=Decimal("4")),
        SimpleNamespace(weight=Decimal("2"), value=Decimal("3")),
    ]
    for module in _BOTH_SIDES:
        assert module._weighted_average(rows, lambda r: r.weight, lambda r: r.value) == Decimal("3")
        assert (
            module._merged_weighted_average([(rows, lambda r: r.weight, lambda r: r.value)])
            == Decimal("3")
        )


def test_weighted_average_helpers_map_nan_value_to_zero_on_both_sides() -> None:
    rows = [
        SimpleNamespace(weight=Decimal("2"), value=Decimal("NaN")),
        SimpleNamespace(weight=Decimal("2"), value=Decimal("6")),
    ]
    for module in _BOTH_SIDES:
        assert module._weighted_average(rows, lambda r: r.weight, lambda r: r.value) == Decimal("3")
        assert (
            module._merged_weighted_average([(rows, lambda r: r.weight, lambda r: r.value)])
            == Decimal("3")
        )
