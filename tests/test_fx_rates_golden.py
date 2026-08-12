"""FX 中间价与营业日选择的封闭黄金测试。

全部期望值均由直接报价定义或日历事实独立给出，不调用被测实现生成期望值：

* ``USD/CNY = q`` 表示 1 USD = q CNY，因此外币折人民币为
  ``CNY = USD × q``，不能取倒数。
* formal 业务日必须有当日官方中间价；非营业日只允许沿用前一营业日。
* 观测日不得晚于目标日；中间价必须有限且严格大于零。

已知 Medium 缺口：``fx_calendar.py`` 只登记 CNY/USD 假日，而正式物化还支持
EUR/AUD/CAD/HKD。下方测试如实锁定这些币种当前只受周末和 CNY 已登记假日约束；
这不是对该日历完整性的认可，补齐币种假日仍待业务口径裁决。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from backend.app.core_finance.fx_calendar import is_cfets_fx_non_business_day
from backend.app.core_finance.fx_rates import (
    FxRateUnavailableError,
    get_usd_cny_rate,
    is_valid_fx_mid_rate,
)


def test_usd_cny_mid_rate_direction_is_foreign_currency_to_cny_golden() -> None:
    """125 USD × 7.20 CNY/USD = 900 CNY；除以 7.20 是反向报价，不能使用。"""
    target_date = date(2026, 3, 31)
    rate, observed_date, warnings = get_usd_cny_rate(
        [(target_date, Decimal("7.20"))],
        target_date,
    )

    assert rate == Decimal("7.20")
    assert observed_date == target_date
    assert warnings == []
    assert Decimal("125") * rate == Decimal("900.00")
    assert Decimal("125") / rate != Decimal("900.00")


def test_formal_business_day_missing_exact_rate_fails_closed() -> None:
    """2026-03-03（周二）缺当日行时，不得拿 3 月 2 日汇率补业务日。"""
    with pytest.raises(FxRateUnavailableError, match="missing official input row"):
        get_usd_cny_rate(
            [(date(2026, 3, 2), Decimal("7.10"))],
            date(2026, 3, 3),
        )


def test_formal_weekend_carries_previous_business_day_rate_golden() -> None:
    """2026-03-01（周日）的上一营业日为 2026-02-27（周五）。"""
    rate, observed_date, warnings = get_usd_cny_rate(
        [
            (date(2026, 3, 2), Decimal("9.99")),  # 未来值不得被选中
            (date(2026, 2, 27), Decimal("7.15")),
        ],
        date(2026, 3, 1),
    )

    assert rate == Decimal("7.15")
    assert observed_date == date(2026, 2, 27)
    assert warnings == [
        "USD/CNY formal non-business-day carry-forward: "
        "target_date=2026-03-01, observed_date=2026-02-27"
    ]


def test_formal_carry_forward_stops_when_previous_business_day_is_missing() -> None:
    """周日向前跨过周六后，周五仍缺值就失败，不能继续拿周四 7.08。"""
    with pytest.raises(FxRateUnavailableError, match="missing official input row"):
        get_usd_cny_rate(
            [(date(2026, 2, 26), Decimal("7.08"))],
            date(2026, 3, 1),
        )


def test_analytical_fallback_rejects_future_only_rate() -> None:
    """目标日 3 月 31 日不能使用 4 月 1 日汇率，避免前视偏差。"""
    with pytest.raises(
        FxRateUnavailableError,
        match="all valid input rows are on or after target_date",
    ):
        get_usd_cny_rate(
            [(date(2026, 4, 1), Decimal("7.30"))],
            date(2026, 3, 31),
            allow_stale_fallback=True,
        )


@pytest.mark.parametrize(
    "invalid_rate",
    [
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("-Infinity"),
    ],
)
def test_non_finite_mid_rates_are_rejected(invalid_rate: Decimal) -> None:
    assert is_valid_fx_mid_rate(invalid_rate) is False
    with pytest.raises(FxRateUnavailableError, match="no valid input rows"):
        get_usd_cny_rate(
            [(date(2026, 3, 31), invalid_rate)],
            date(2026, 3, 31),
        )


def test_registered_cny_and_usd_holidays_are_non_business_days() -> None:
    # 2026-02-18 在中国春节假期；2026-01-19 是美国 Martin Luther King Jr. Day。
    assert is_cfets_fx_non_business_day(
        date(2026, 2, 18),
        base_currency="USD",
        quote_currency="CNY",
    )
    assert is_cfets_fx_non_business_day(
        date(2026, 1, 19),
        base_currency="USD",
        quote_currency="CNY",
    )


@pytest.mark.parametrize(
    ("base_currency", "unregistered_local_holiday"),
    [
        ("EUR", date(2026, 12, 25)),  # TARGET/欧元区 Christmas Day
        ("AUD", date(2026, 1, 26)),   # Australia Day
        ("CAD", date(2026, 7, 1)),    # Canada Day
        ("HKD", date(2026, 7, 1)),    # 香港特别行政区成立纪念日
    ],
)
def test_materialized_non_usd_currency_holidays_are_currently_unregistered(
    base_currency: str,
    unregistered_local_holiday: date,
) -> None:
    """锁定已知缺口：这些工作日不是 CNY 假日，当前实现会误判为业务日。"""
    assert (
        is_cfets_fx_non_business_day(
            unregistered_local_holiday,
            base_currency=base_currency,
            quote_currency="CNY",
        )
        is False
    )
