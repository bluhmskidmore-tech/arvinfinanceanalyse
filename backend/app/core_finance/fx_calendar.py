from __future__ import annotations

from datetime import date

CFETS_2026_NOTICE_URL = "https://www.chinamoney.com.cn/chinese/rdgz/20251218/3254567.html"

_DEFAULT_WEEKEND_DAYS = frozenset({5, 6})
_WEEKEND_DAYS_BY_CURRENCY = {
    "SAR": frozenset({4, 5}),
}

_CFETS_CURRENCY_HOLIDAYS = {
    "CNY": frozenset({date(2026, 6, 19)}),
    "USD": frozenset({date(2026, 1, 19)}),
}


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
    return any(
        target_date.weekday() in _weekend_days(currency)
        or target_date in _CFETS_CURRENCY_HOLIDAYS.get(currency, frozenset())
        for currency in currencies
        if currency
    )


def _normalize_currency_code(value: str) -> str:
    return str(value or "").strip().upper()


def _weekend_days(currency: str) -> frozenset[int]:
    return _WEEKEND_DAYS_BY_CURRENCY.get(currency, _DEFAULT_WEEKEND_DAYS)


__all__ = ["CFETS_2026_NOTICE_URL", "is_cfets_fx_non_business_day"]
