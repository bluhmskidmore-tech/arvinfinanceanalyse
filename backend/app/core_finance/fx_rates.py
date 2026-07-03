"""
USD/CNY 汇率解析（自 MOSS-V2 core_finance 迁入，纯函数）。

rows: (trade_date, usdcny) 可无序，内部排序。
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from .decimal_utils import to_decimal
from .fx_calendar import is_cfets_fx_non_business_day


class FxRateUnavailableError(RuntimeError):
    """Raised when formal USD/CNY middle-rate input is insufficient."""


def is_weekend_non_business_day(target_date: date | str) -> bool:
    if isinstance(target_date, str):
        target_date = date.fromisoformat(target_date)
    return target_date.weekday() >= 5


def get_usd_cny_rate(
    rows: list[tuple[date, Decimal | None]],
    target_date: date,
    *,
    allow_stale_fallback: bool = False,
    target_is_business_day: bool | None = None,
) -> tuple[Decimal, date | None, list[str]]:
    warnings: list[str] = []

    valid = [(d, to_decimal(v)) for d, v in rows if v is not None and to_decimal(v) > 0]
    if not valid:
        if allow_stale_fallback:
            raise FxRateUnavailableError(
                f"USD/CNY analytical fallback unavailable for target_date={target_date}: no valid input rows."
            )
        raise FxRateUnavailableError(
            f"USD/CNY formal middle-rate unavailable for target_date={target_date}: no valid input rows."
        )

    valid.sort(key=lambda x: x[0])

    for d, r in valid:
        if d == target_date:
            return r, d, warnings

    if not allow_stale_fallback:
        is_non_business_day = (
            not target_is_business_day
            if target_is_business_day is not None
            else is_cfets_fx_non_business_day(
                target_date,
                base_currency="USD",
                quote_currency="CNY",
            )
        )
        if is_non_business_day:
            start = target_date - timedelta(days=3)
            before = [(d, r) for d, r in valid if start <= d < target_date]
            if before:
                d, r = before[-1]
                warnings.append(
                    f"USD/CNY formal non-business-day carry-forward: target_date={target_date}, observed_date={d}"
                )
                return r, d, warnings
        raise FxRateUnavailableError(
            f"USD/CNY formal middle-rate unavailable for target_date={target_date}: missing official input row."
        )

    start = target_date - timedelta(days=30)
    before = [(d, r) for d, r in valid if start <= d < target_date]
    if before:
        d, r = before[-1]
        warnings.append(
            f"USD/CNY analytical LOCF: target_date={target_date}, observed_date={d}"
        )
        return r, d, warnings

    d, r = valid[-1]
    warnings.append(
        f"USD/CNY analytical stale fallback beyond 30 days: target_date={target_date}, observed_date={d}"
    )
    return r, d, warnings
