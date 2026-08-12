from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from backend.app.core_finance.pnl_bridge import _modified_duration

REPORT = date(2025, 12, 31)
MATURITY = date(2030, 12, 31)


def _balance_row(**overrides: object) -> dict:
    row: dict = {
        "report_date": REPORT,
        "instrument_code": "240001.IB",
        "maturity_date": MATURITY,
        # 落库口径为百分数：2.38 表示 2.38%（fact_formal_zqtz_balance_daily）
        "coupon_rate": Decimal("2.38"),
        "ytm_value": Decimal("2.38"),
    }
    row.update(overrides)
    return row


def test_fallback_normalizes_percent_coupon_and_ytm_to_decimal():
    """回退路径必须把百分数口径归一为小数，否则 5 年期券久期塌缩到 0.4 年。"""
    duration = _modified_duration(report_date=REPORT, row=_balance_row())

    # 票息=收益率的 5 年平价券：Macaulay≈4.77，修正久期≈4.77/1.0238≈4.66
    assert float(duration) == pytest.approx(4.6619, abs=1e-3)
    # 未归一（2.38 当作 238%）时结果约 0.42，此断言锁死塌缩回归
    assert duration > Decimal("2")
    assert Decimal("4") < duration < Decimal("5")


def test_fallback_uses_years_to_maturity_when_rates_are_dirty():
    """脏利率（>20% 视为脏数据）按 0 处理，久期回退为剩余年限，不静默放大。"""
    duration = _modified_duration(
        report_date=REPORT,
        row=_balance_row(coupon_rate=Decimal("20720.93"), ytm_value=Decimal("20720.93")),
    )

    # (2030-12-31 - 2025-12-31) = 1826 天 / 365 ≈ 5.0027 年
    assert float(duration) == pytest.approx(5.0027, abs=1e-3)


def test_materialized_modified_duration_still_wins_over_fallback():
    """余额行若携带物化修正久期，仍直接采用，不进入归一回退路径。"""
    duration = _modified_duration(
        report_date=REPORT,
        row=_balance_row(modified_duration="3.75"),
    )

    assert duration == Decimal("3.75")


def test_missing_maturity_date_returns_zero():
    duration = _modified_duration(report_date=REPORT, row=_balance_row(maturity_date=None))

    assert duration == Decimal("0")
