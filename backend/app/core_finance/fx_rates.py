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


# 春节最长 9 天假期 + 相邻周末/调休的安全上限。
_FORMAL_CARRY_FORWARD_MAX_LOOKBACK_DAYS = 14


def is_valid_fx_mid_rate(value: Decimal | None) -> bool:
    """Return whether an FX middle rate is safe for formal conversion."""
    return value is not None and value.is_finite() and value > 0


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

    valid: list[tuple[date, Decimal]] = []
    for observed_date, value in rows:
        if value is None:
            continue
        rate = to_decimal(value)
        if is_valid_fx_mid_rate(rate):
            valid.append((observed_date, rate))
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
            # 按"上一营业日"语义回看（calc_rules §7.1）：只允许跳过连续非营业日，
            # 覆盖春节等长假（2026 春节 2/15-2/23 共 9 天，原固定 3 天窗口会误失败）；
            # 一旦回看到营业日仍缺中间价则 fail-closed。
            by_date = dict(valid)
            probe = target_date - timedelta(days=1)
            for _ in range(_FORMAL_CARRY_FORWARD_MAX_LOOKBACK_DAYS):
                rate = by_date.get(probe)
                if rate is not None:
                    warnings.append(
                        f"USD/CNY formal non-business-day carry-forward: target_date={target_date}, observed_date={probe}"
                    )
                    return rate, probe, warnings
                if not is_cfets_fx_non_business_day(
                    probe,
                    base_currency="USD",
                    quote_currency="CNY",
                ):
                    break
                probe -= timedelta(days=1)
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

    # 兜底也只允许取 target_date 之前的行：历史回放时输入集可能包含晚于
    # target_date 的行，取 valid[-1] 会引入未来汇率（前视偏差，2026-07-19 审计 共享 H-2）。
    older = [(d, r) for d, r in valid if d < target_date]
    if not older:
        raise FxRateUnavailableError(
            f"USD/CNY analytical fallback unavailable for target_date={target_date}: "
            "all valid input rows are on or after target_date."
        )
    d, r = older[-1]
    warnings.append(
        f"USD/CNY analytical stale fallback beyond 30 days: target_date={target_date}, observed_date={d}"
    )
    return r, d, warnings
