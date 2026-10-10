"""共享 M-3 + 2026-07-20 审计 P2：balance workbook Decimal 助手不得传播 NaN。

测试对象说明（2026-08-19）：生产权威实现是单体 balance_analysis_workbook.py；
`balance_workbook/` 包（`_utils` 等）只保留历史 import 的兼容导出，直接复用权威
函数对象。NaN 防线由唯一的 `_to_finite_decimal` 计算源负责；本测试同时通过
权威路径与兼容路径调用，防止兼容层重新形成第二套语义。
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


def test_weighted_average_helpers_exclude_nan_value_row_on_both_sides() -> None:
    # 缺失值不是 0：NaN 值行必须整行退出加权平均，不进分子也不进分母。
    rows = [
        SimpleNamespace(weight=Decimal("2"), value=Decimal("NaN")),
        SimpleNamespace(weight=Decimal("2"), value=Decimal("6")),
    ]
    for module in _BOTH_SIDES:
        assert module._weighted_average(rows, lambda r: r.weight, lambda r: r.value) == Decimal("6")
        assert (
            module._merged_weighted_average([(rows, lambda r: r.weight, lambda r: r.value)])
            == Decimal("6")
        )


def test_weighted_average_helpers_treat_none_and_nan_values_identically() -> None:
    # 同一“票面利率缺失”事实，来源给 None 与给 NaN 必须得到同一答案。
    none_rows = [
        SimpleNamespace(weight=Decimal("2"), value=None),
        SimpleNamespace(weight=Decimal("2"), value=Decimal("6")),
    ]
    nan_rows = [
        SimpleNamespace(weight=Decimal("2"), value=Decimal("NaN")),
        SimpleNamespace(weight=Decimal("2"), value=Decimal("6")),
    ]
    unparsable_rows = [
        SimpleNamespace(weight=Decimal("2"), value="n/a"),
        SimpleNamespace(weight=Decimal("2"), value=Decimal("6")),
    ]
    for module in _BOTH_SIDES:
        baseline = module._weighted_average(none_rows, lambda r: r.weight, lambda r: r.value)
        assert baseline == Decimal("6")
        for rows in (nan_rows, unparsable_rows):
            assert module._weighted_average(rows, lambda r: r.weight, lambda r: r.value) == baseline
            assert (
                module._merged_weighted_average([(rows, lambda r: r.weight, lambda r: r.value)])
                == baseline
            )


def test_weighted_average_helpers_return_none_when_every_value_is_missing() -> None:
    rows = [
        SimpleNamespace(weight=Decimal("2"), value=Decimal("NaN")),
        SimpleNamespace(weight=Decimal("3"), value=None),
    ]
    for module in _BOTH_SIDES:
        assert module._weighted_average(rows, lambda r: r.weight, lambda r: r.value) is None
        assert (
            module._merged_weighted_average([(rows, lambda r: r.weight, lambda r: r.value)]) is None
        )
