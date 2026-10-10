"""``macro/helpers.py`` 共享 Decimal 工具的 NaN/Inf 防护回归测试。

审计发现（High）：``to_decimal_safe`` / ``to_decimal_or_none`` 对 NaN/Inf 未做拦截，
NaN 会原样进入 ``economic_cycle.py`` / ``macro_portfolio_impact.py`` /
``leading_indicator.py`` 的评分算术，静默传播或在比较运算时抛
``InvalidOperation``。修复后：

- ``to_decimal_safe``：非有限值（含字符串 "nan"/"inf" 经 Decimal 解析产生的
  非有限值）归 0，并委托共享版 ``decimal_utils.to_decimal`` 记录一次性告警。
- ``to_decimal_or_none``：非有限值返回 None，对齐其 docstring 承诺的
  "缺失分项不得以 0 参与加权"。
"""

from __future__ import annotations

import math
from decimal import Decimal

import pytest

from backend.app.core_finance.macro.helpers import to_decimal_or_none, to_decimal_safe


@pytest.mark.parametrize(
    "raw",
    [float("nan"), float("inf"), float("-inf"), "nan", "inf", "-inf", Decimal("NaN"), Decimal("Infinity")],
)
def test_to_decimal_safe_coerces_non_finite_to_zero(raw) -> None:
    result = to_decimal_safe(raw)
    assert result == Decimal("0")
    assert result.is_finite()


@pytest.mark.parametrize(
    "raw",
    [float("nan"), float("inf"), float("-inf"), "nan", "inf", "-inf", Decimal("NaN"), Decimal("Infinity")],
)
def test_to_decimal_or_none_returns_none_for_non_finite(raw) -> None:
    assert to_decimal_or_none(raw) is None


def test_to_decimal_safe_none_returns_zero_and_warns_once(caplog) -> None:
    with caplog.at_level("WARNING", logger="backend.app.core_finance.decimal_utils"):
        assert to_decimal_safe(None) == Decimal("0")
        assert to_decimal_safe(None) == Decimal("0")
    messages = [
        record.getMessage()
        for record in caplog.records
        if record.name == "backend.app.core_finance.decimal_utils"
    ]
    assert len(messages) == 1
    assert "to_decimal coerced" in messages[0]
    assert "reason=missing" in messages[0]


def test_to_decimal_safe_normal_value_round_trips() -> None:
    assert to_decimal_safe("1.5") == Decimal("1.5")
    assert to_decimal_safe(2) == Decimal("2")
    assert to_decimal_safe(Decimal("3.25")) == Decimal("3.25")


def test_to_decimal_safe_invalid_string_still_coerces_to_zero() -> None:
    result = to_decimal_safe("not-a-number")
    assert result == Decimal("0")


def test_to_decimal_or_none_none_returns_none() -> None:
    assert to_decimal_or_none(None) is None


def test_to_decimal_or_none_normal_value_round_trips() -> None:
    assert to_decimal_or_none("1.5") == Decimal("1.5")
    assert to_decimal_or_none(2) == Decimal("2")
    assert to_decimal_or_none(Decimal("3.25")) == Decimal("3.25")


def test_to_decimal_or_none_invalid_string_returns_none() -> None:
    assert to_decimal_or_none("not-a-number") is None


def test_to_decimal_safe_output_never_feeds_nan_into_arithmetic() -> None:
    # 回归防御：修复前 to_decimal_safe(nan) 直接返回 Decimal('NaN')，
    # 参与算术后结果仍是 NaN，比较运算会抛 InvalidOperation。
    value = to_decimal_safe(float("nan"))
    total = value + Decimal("10")
    assert total == Decimal("10")
    assert not math.isnan(float(total))
