from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from backend.app.core_finance.data_freshness import (
    FRESHNESS_TIER_EXPIRED,
    FRESHNESS_TIER_FRESH,
    FRESHNESS_TIER_STALE,
    FRESHNESS_TIER_UNKNOWN,
    assess_freshness,
)

AS_OF = date(2026, 7, 1)


def test_daily_tiers_boundaries() -> None:
    assert assess_freshness(date(2026, 7, 1), AS_OF).tier == FRESHNESS_TIER_FRESH
    assert assess_freshness(date(2026, 6, 28), AS_OF).tier == FRESHNESS_TIER_FRESH  # age 3
    assert assess_freshness(date(2026, 6, 27), AS_OF).tier == FRESHNESS_TIER_STALE  # age 4
    assert assess_freshness(date(2026, 6, 16), AS_OF).tier == FRESHNESS_TIER_STALE  # age 15
    assert assess_freshness(date(2026, 6, 15), AS_OF).tier == FRESHNESS_TIER_EXPIRED  # age 16


def test_monthly_cadence_wider_window() -> None:
    # age 40: stale for daily, still fresh for monthly prints
    result = assess_freshness(date(2026, 5, 22), AS_OF, cadence="monthly")
    assert result.tier == FRESHNESS_TIER_FRESH
    assert result.age_days == 40
    assert assess_freshness(date(2026, 5, 1), AS_OF, cadence="monthly").tier == FRESHNESS_TIER_STALE  # age 61
    assert assess_freshness(date(2026, 3, 1), AS_OF, cadence="monthly").tier == FRESHNESS_TIER_EXPIRED  # age 122


def test_unknown_cadence_falls_back_to_daily() -> None:
    assert assess_freshness(date(2026, 6, 20), AS_OF, cadence="quarterly").tier == FRESHNESS_TIER_STALE


def test_missing_dates_return_unknown() -> None:
    for latest, as_of in ((None, AS_OF), (AS_OF, None), ("not-a-date", AS_OF)):
        result = assess_freshness(latest, as_of)
        assert result.tier == FRESHNESS_TIER_UNKNOWN
        assert result.age_days is None
        assert result.confidence == Decimal("0")


def test_accepts_iso_strings_and_datetimes() -> None:
    result = assess_freshness("2026-06-30", datetime(2026, 7, 1, 15, 30))
    assert result.age_days == 1
    assert result.tier == FRESHNESS_TIER_FRESH


def test_future_dated_series_keeps_negative_age_as_fresh() -> None:
    result = assess_freshness(date(2026, 7, 3), AS_OF)
    assert result.age_days == -2
    assert result.tier == FRESHNESS_TIER_FRESH
    assert result.confidence == Decimal("1")


def test_confidence_mapping() -> None:
    assert assess_freshness(date(2026, 6, 30), AS_OF).confidence == Decimal("1")
    assert assess_freshness(date(2026, 6, 20), AS_OF).confidence == Decimal("0.5")
    assert assess_freshness(date(2026, 5, 1), AS_OF).confidence == Decimal("0")
