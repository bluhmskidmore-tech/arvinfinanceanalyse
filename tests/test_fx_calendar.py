from __future__ import annotations

from datetime import date

import pytest

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


def test_cfets_fx_calendar_marks_2026_dragon_boat_cny_holiday() -> None:
    assert is_cfets_fx_non_business_day(
        date(2026, 6, 19),
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


def test_cfets_fx_calendar_marks_2026_spring_festival_weekdays() -> None:
    """春节整周（国办发明电〔2025〕7号：2/15-2/23）此前完全缺失于假日表。"""
    for day in ("2026-02-16", "2026-02-17", "2026-02-18", "2026-02-19", "2026-02-20", "2026-02-23"):
        assert is_cfets_fx_non_business_day(
            day,
            base_currency="USD",
            quote_currency="CNY",
        ), day


def test_cfets_fx_calendar_marks_2026_national_day_and_new_year() -> None:
    assert is_cfets_fx_non_business_day(
        "2026-10-01",
        base_currency="USD",
        quote_currency="CNY",
    )
    assert is_cfets_fx_non_business_day(
        "2026-01-01",
        base_currency="USD",
        quote_currency="CNY",
    )


def test_cfets_fx_calendar_marks_2025_spring_festival() -> None:
    assert is_cfets_fx_non_business_day(
        "2025-01-29",
        base_currency="USD",
        quote_currency="CNY",
    )


def test_cfets_fx_calendar_fails_loud_for_uncovered_year_weekday() -> None:
    """覆盖年份之外的工作日无法判定假日，必须报错而不是静默判为业务日。"""
    with pytest.raises(ValueError, match="does not cover year 2027"):
        is_cfets_fx_non_business_day(
            "2027-01-04",
            base_currency="USD",
            quote_currency="CNY",
        )


def test_cfets_fx_calendar_uncovered_year_weekend_is_still_non_business() -> None:
    assert is_cfets_fx_non_business_day(
        "2027-01-02",
        base_currency="USD",
        quote_currency="CNY",
    )
