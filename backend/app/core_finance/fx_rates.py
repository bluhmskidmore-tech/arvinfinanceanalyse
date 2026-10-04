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


def formal_fx_observation_date(
    target_date: date | str, *, base_currency: str, quote_currency: str = "CNY"
) -> date:
    """Required fixing date: today or the immediately preceding publication day."""
    probe = date.fromisoformat(target_date) if isinstance(target_date, str) else target_date
    for _ in range(_FORMAL_CARRY_FORWARD_MAX_LOOKBACK_DAYS + 1):
        if not is_cfets_fx_non_business_day(
            probe, base_currency=base_currency, quote_currency=quote_currency
        ):
            return probe
        probe -= timedelta(days=1)
    raise ValueError(f"CFETS previous publication date unavailable for target_date={target_date}.")


def validate_formal_fx_observation(
    *,
    target_date: date | str,
    observed_date: date | str | None,
    base_currency: str,
    quote_currency: str = "CNY",
    is_business_day: bool | None,
    is_carry_forward: bool | None,
) -> None:
    """Reject stale observations and stored flags inconsistent with fixing dates."""
    target = date.fromisoformat(target_date) if isinstance(target_date, str) else target_date
    expected = formal_fx_observation_date(
        target, base_currency=base_currency, quote_currency=quote_currency
    )
    direct = expected == target
    if is_business_day is True and is_carry_forward is True:
        raise ValueError(
            f"Invalid formal fx metadata for base_currency={base_currency} report_date={target}: "
            "business-day row cannot be carry-forward."
        )
    if is_business_day is not direct or is_carry_forward is not (not direct):
        kind = "metadata" if is_business_day else "carry-forward metadata"
        raise ValueError(
            f"Invalid formal fx {kind} for base_currency={base_currency} report_date={target}: "
            "carry-forward is only allowed for confirmed non-business-day rows; "
            "business/carry flags must match the CFETS publication calendar."
        )
    observed = date.fromisoformat(observed_date) if isinstance(observed_date, str) else observed_date
    if observed != expected:
        requirement = "same-day publication" if direct else "previous publication"
        raise ValueError(
            f"Invalid formal fx observed date for base_currency={base_currency} report_date={target}: "
            f"{requirement} required at {expected}, observed_trade_date={observed}."
        )


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

    if not allow_stale_fallback:
        expected = formal_fx_observation_date(target_date, base_currency="USD")
        if target_is_business_day is not None and target_is_business_day != (expected == target_date):
            raise FxRateUnavailableError(
                f"USD/CNY formal calendar metadata conflicts with publication date for target_date={target_date}."
            )
        formal_rate = dict(valid).get(expected)
        if formal_rate is not None:
            if expected != target_date:
                warnings.append(
                    f"USD/CNY formal non-business-day carry-forward: target_date={target_date}, observed_date={expected}"
                )
            return formal_rate, expected, warnings
        raise FxRateUnavailableError(
            f"USD/CNY formal middle-rate unavailable for target_date={target_date}: missing official input row."
        )

    for d, r in valid:
        if d == target_date:
            return r, d, warnings

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
