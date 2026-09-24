"""Behavior tests for core_finance.fx_rates (USD/CNY middle-rate resolution).

自 tests/test_caliber_rule_fx_mid_conversion.py 纯迁移（仅移动 + import 修正，断言语义不变）；
caliber 规则本身（DESCRIPTOR/矩阵/日期选择策略）的用例仍留在原文件。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from backend.app.core_finance.fx_rates import FxRateUnavailableError, get_usd_cny_rate


def test_formal_canonical_usd_cny_rate_fails_closed_when_input_rows_are_empty() -> None:
    with pytest.raises(FxRateUnavailableError) as excinfo:
        get_usd_cny_rate([], date(2026, 3, 31))

    assert "USD/CNY" in str(excinfo.value)
    assert "formal" in str(excinfo.value)


@pytest.mark.parametrize(
    "invalid_rate",
    [
        Decimal("0"),
        Decimal("-7.2"),
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("-Infinity"),
    ],
)
def test_formal_canonical_usd_cny_rate_rejects_nonpositive_or_nonfinite_input(
    invalid_rate: Decimal,
) -> None:
    with pytest.raises(FxRateUnavailableError, match="no valid input rows"):
        get_usd_cny_rate(
            [(date(2026, 3, 31), invalid_rate)],
            date(2026, 3, 31),
        )


def test_formal_canonical_usd_cny_rate_fails_closed_when_only_stale_rows_exist() -> None:
    with pytest.raises(FxRateUnavailableError) as excinfo:
        get_usd_cny_rate(
            [(date(2026, 2, 1), "7.1100")],
            date(2026, 3, 31),
        )

    assert "USD/CNY" in str(excinfo.value)
    assert "formal" in str(excinfo.value)
    assert "7.25" not in str(excinfo.value)


def test_formal_canonical_usd_cny_rate_carries_forward_explicit_non_business_day() -> None:
    rate, observed_date, warnings = get_usd_cny_rate(
        [(date(2026, 2, 16), "7.1100")],
        date(2026, 2, 18),
        target_is_business_day=False,
    )

    assert rate == Decimal("7.1100")
    assert observed_date == date(2026, 2, 16)
    assert warnings
    assert "formal" in warnings[0]


def test_formal_canonical_usd_cny_rate_uses_cfets_currency_holiday_calendar() -> None:
    rate, observed_date, warnings = get_usd_cny_rate(
        [(date(2026, 1, 16), "7.1100")],
        date(2026, 1, 19),
    )

    assert rate == Decimal("7.1100")
    assert observed_date == date(2026, 1, 16)
    assert warnings
    assert "observed_date=2026-01-16" in warnings[0]


def test_formal_carry_forward_spans_2026_spring_festival_long_holiday() -> None:
    """春节 2/15-2/23 连续非营业日：2/22（假日）应能沿用 2/13（上一营业日，周五）中间价。

    2026-06-10 审计 P2 / 2026-07-19 审计 余额 M-7：原固定 3 天回看窗口在长假第 4 天起误失败。
    """
    rate, observed_date, warnings = get_usd_cny_rate(
        [(date(2026, 2, 13), "7.1200")],
        date(2026, 2, 22),
    )

    assert rate == Decimal("7.1200")
    assert observed_date == date(2026, 2, 13)
    assert warnings
    assert "carry-forward" in warnings[0]


def test_formal_carry_forward_fails_closed_when_previous_business_day_rate_missing() -> None:
    """回看途中遇到营业日但缺中间价，必须 fail-closed，不得继续跳过。"""
    with pytest.raises(FxRateUnavailableError):
        get_usd_cny_rate(
            # 2026-02-12（周四）有值，但 2/13（周五营业日）缺值；目标 2/22 在春节假期内。
            [(date(2026, 2, 12), "7.1200")],
            date(2026, 2, 22),
        )


def test_analytical_fallback_never_uses_future_rate() -> None:
    """分析口径兜底不得取 target_date 之后的汇率（2026-07-19 审计 共享 H-2 前视偏差）。"""
    with pytest.raises(FxRateUnavailableError):
        get_usd_cny_rate(
            [(date(2026, 5, 8), "7.2000")],
            date(2026, 3, 31),
            allow_stale_fallback=True,
        )


def test_analytical_stale_fallback_beyond_30_days_uses_latest_prior_rate_only() -> None:
    rate, observed_date, warnings = get_usd_cny_rate(
        [
            (date(2026, 1, 15), "7.0900"),
            (date(2026, 5, 8), "7.2000"),
        ],
        date(2026, 3, 31),
        allow_stale_fallback=True,
    )

    assert rate == Decimal("7.0900")
    assert observed_date == date(2026, 1, 15)
    assert any("stale fallback" in warning for warning in warnings)
