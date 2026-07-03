from __future__ import annotations

from datetime import date

from backend.app.core_finance.fx_calendar import is_cfets_fx_non_business_day


def test_cfets_fx_calendar_marks_weekend_non_business_day() -> None:
    assert is_cfets_fx_non_business_day(
        "2026-01-03",
        base_currency="USD",
        quote_currency="CNY",
    )


def test_cfets_fx_calendar_marks_usd_currency_holiday() -> None:
    assert is_cfets_fx_non_business_day(
        date(2026, 1, 19),
        base_currency="USD",
        quote_currency="CNY",
    )


def test_cfets_fx_calendar_is_pair_symmetric() -> None:
    assert is_cfets_fx_non_business_day(
        "2026-01-19",
        base_currency="CNY",
        quote_currency="USD",
    )


def test_cfets_fx_calendar_rejects_regular_business_day() -> None:
    assert not is_cfets_fx_non_business_day(
        "2025-12-31",
        base_currency="USD",
        quote_currency="CNY",
    )
