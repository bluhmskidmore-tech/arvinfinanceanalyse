from __future__ import annotations

from datetime import date, timedelta

CFETS_2026_NOTICE_URL = "https://www.chinamoney.com.cn/chinese/rdgz/20251218/3254567.html"

_DEFAULT_WEEKEND_DAYS = frozenset({5, 6})
_WEEKEND_DAYS_BY_CURRENCY = {
    "SAR": frozenset({4, 5}),
}


def _date_range(start: date, end: date) -> list[date]:
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


# 中国法定节假日（国务院办公厅年度放假通知；含落在周末的假日，周末本就非业务日，无害）。
# 2024: 国办发明电〔2023〕7号；2025: 国办发明电〔2024〕8号；2026: 国办发明电〔2025〕7号。
# 注意：调休补班的周六/周日（如 2026-02-14、2026-10-10）银行间市场照常交易，
# 但本函数按周末判为非业务日——该保守偏差只会放宽 carry-forward 准入，
# 当供应商在补班日返回真实汇率时精确匹配优先，不会引入错误数据。
_CNY_HOLIDAYS: frozenset[date] = frozenset(
    [
        # 2024
        date(2024, 1, 1),
        *_date_range(date(2024, 2, 10), date(2024, 2, 17)),
        *_date_range(date(2024, 4, 4), date(2024, 4, 6)),
        *_date_range(date(2024, 5, 1), date(2024, 5, 5)),
        *_date_range(date(2024, 6, 8), date(2024, 6, 10)),
        *_date_range(date(2024, 9, 15), date(2024, 9, 17)),
        *_date_range(date(2024, 10, 1), date(2024, 10, 7)),
        # 2025
        date(2025, 1, 1),
        *_date_range(date(2025, 1, 28), date(2025, 2, 4)),
        *_date_range(date(2025, 4, 4), date(2025, 4, 6)),
        *_date_range(date(2025, 5, 1), date(2025, 5, 5)),
        *_date_range(date(2025, 5, 31), date(2025, 6, 2)),
        *_date_range(date(2025, 10, 1), date(2025, 10, 8)),
        # 2026
        *_date_range(date(2026, 1, 1), date(2026, 1, 3)),
        *_date_range(date(2026, 2, 15), date(2026, 2, 23)),
        *_date_range(date(2026, 4, 4), date(2026, 4, 6)),
        *_date_range(date(2026, 5, 1), date(2026, 5, 5)),
        *_date_range(date(2026, 6, 19), date(2026, 6, 21)),
        *_date_range(date(2026, 9, 25), date(2026, 9, 27)),
        *_date_range(date(2026, 10, 1), date(2026, 10, 7)),
    ]
)

# 美国联邦假日（银行/FX 清算休市）。
_USD_HOLIDAYS: frozenset[date] = frozenset(
    [
        # 2024
        date(2024, 1, 1),
        date(2024, 1, 15),
        date(2024, 2, 19),
        date(2024, 5, 27),
        date(2024, 6, 19),
        date(2024, 7, 4),
        date(2024, 9, 2),
        date(2024, 10, 14),
        date(2024, 11, 11),
        date(2024, 11, 28),
        date(2024, 12, 25),
        # 2025
        date(2025, 1, 1),
        date(2025, 1, 20),
        date(2025, 2, 17),
        date(2025, 5, 26),
        date(2025, 6, 19),
        date(2025, 7, 4),
        date(2025, 9, 1),
        date(2025, 10, 13),
        date(2025, 11, 11),
        date(2025, 11, 27),
        date(2025, 12, 25),
        # 2026（7/4 周六 -> 7/3 观察日）
        date(2026, 1, 1),
        date(2026, 1, 19),
        date(2026, 2, 16),
        date(2026, 5, 25),
        date(2026, 6, 19),
        date(2026, 7, 3),
        date(2026, 9, 7),
        date(2026, 10, 12),
        date(2026, 11, 11),
        date(2026, 11, 26),
        date(2026, 12, 25),
    ]
)

_CFETS_CURRENCY_HOLIDAYS = {
    "CNY": _CNY_HOLIDAYS,
    "USD": _USD_HOLIDAYS,
}

# 假日数据覆盖的年份。覆盖范围之外的工作日无法判定是否假日，必须 fail-loud，
# 防止 2026-06-10 审计 / 2026-07-19 审计共享 H-3 指出的"下一个未登记假日
# 让正式 FX 物化静默断裂或误放行"。新年份的官方放假通知发布后在此登记。
_CFETS_CALENDAR_COVERED_YEARS = frozenset({2024, 2025, 2026})


def is_cfets_fx_non_business_day(
    target_date: date | str,
    *,
    base_currency: str,
    quote_currency: str,
) -> bool:
    if isinstance(target_date, str):
        target_date = date.fromisoformat(target_date)

    currencies = {
        _normalize_currency_code(base_currency),
        _normalize_currency_code(quote_currency),
    }
    currencies.discard("")

    if any(target_date.weekday() in _weekend_days(currency) for currency in currencies):
        return True

    for currency in currencies:
        holidays = _CFETS_CURRENCY_HOLIDAYS.get(currency)
        if holidays is None:
            continue
        if target_date.year not in _CFETS_CALENDAR_COVERED_YEARS:
            raise ValueError(
                f"CFETS holiday calendar does not cover year {target_date.year} for "
                f"currency {currency}; register the official holiday schedule in "
                "backend/app/core_finance/fx_calendar.py before processing "
                f"target_date={target_date.isoformat()}."
            )
        if target_date in holidays:
            return True
    return False


def _normalize_currency_code(value: str) -> str:
    return str(value or "").strip().upper()


def _weekend_days(currency: str) -> frozenset[int]:
    return _WEEKEND_DAYS_BY_CURRENCY.get(currency, _DEFAULT_WEEKEND_DAYS)


__all__ = ["CFETS_2026_NOTICE_URL", "is_cfets_fx_non_business_day"]
