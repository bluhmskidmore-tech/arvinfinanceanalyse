from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from backend.app.core_finance.data_freshness import (
    CONFIDENCE_BY_TIER,
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


def test_weekly_tier_boundaries() -> None:
    # weekly thresholds: stale after 10 days, expired after 30 days
    assert assess_freshness(date(2026, 6, 21), AS_OF, cadence="weekly").tier == FRESHNESS_TIER_FRESH  # age 10
    assert assess_freshness(date(2026, 6, 20), AS_OF, cadence="weekly").tier == FRESHNESS_TIER_STALE  # age 11
    assert assess_freshness(date(2026, 6, 1), AS_OF, cadence="weekly").tier == FRESHNESS_TIER_STALE  # age 30
    assert assess_freshness(date(2026, 5, 31), AS_OF, cadence="weekly").tier == FRESHNESS_TIER_EXPIRED  # age 31


def test_monthly_tier_boundaries() -> None:
    # monthly thresholds: stale after 45 days, expired after 100 days
    assert assess_freshness(date(2026, 5, 17), AS_OF, cadence="monthly").tier == FRESHNESS_TIER_FRESH  # age 45
    assert assess_freshness(date(2026, 5, 16), AS_OF, cadence="monthly").tier == FRESHNESS_TIER_STALE  # age 46
    assert assess_freshness(date(2026, 3, 23), AS_OF, cadence="monthly").tier == FRESHNESS_TIER_STALE  # age 100
    assert assess_freshness(date(2026, 3, 22), AS_OF, cadence="monthly").tier == FRESHNESS_TIER_EXPIRED  # age 101


def test_monthly_cadence_wider_window() -> None:
    # age 40: stale for daily, still fresh for monthly prints
    result = assess_freshness(date(2026, 5, 22), AS_OF, cadence="monthly")
    assert result.tier == FRESHNESS_TIER_FRESH
    assert result.age_days == 40
    assert assess_freshness(date(2026, 5, 1), AS_OF, cadence="monthly").tier == FRESHNESS_TIER_STALE  # age 61
    assert assess_freshness(date(2026, 3, 1), AS_OF, cadence="monthly").tier == FRESHNESS_TIER_EXPIRED  # age 122


def test_cadence_normalization_case_and_whitespace() -> None:
    # 'Monthly' (age 72) must use monthly thresholds (45 < 72 <= 100 -> stale),
    # not silently fall back to daily thresholds (72 > 15 -> expired).
    result = assess_freshness(date(2026, 4, 20), AS_OF, cadence="Monthly")
    assert result.age_days == 72
    assert result.tier == FRESHNESS_TIER_STALE
    assert result.cadence_fallback is False

    # ' WEEKLY ' (age 10) is fresh under weekly thresholds; a silent daily
    # fallback would have reported stale (10 > 3).
    result = assess_freshness(date(2026, 6, 21), AS_OF, cadence=" WEEKLY ")
    assert result.tier == FRESHNESS_TIER_FRESH
    assert result.cadence_fallback is False

    result = assess_freshness(date(2026, 5, 16), AS_OF, cadence="MONTHLY")
    assert result.tier == FRESHNESS_TIER_STALE  # age 46
    assert result.cadence_fallback is False


def test_unknown_cadence_falls_back_to_daily_with_disclosure() -> None:
    result = assess_freshness(date(2026, 6, 20), AS_OF, cadence="quarterly")
    assert result.tier == FRESHNESS_TIER_STALE  # age 11 under daily thresholds
    assert result.cadence_fallback is True

    # Known cadences never raise the fallback flag.
    assert assess_freshness(date(2026, 6, 20), AS_OF, cadence="daily").cadence_fallback is False
    assert assess_freshness(date(2026, 6, 20), AS_OF, cadence="weekly").cadence_fallback is False


def test_missing_dates_return_unknown() -> None:
    for latest, as_of in ((None, AS_OF), (AS_OF, None), ("not-a-date", AS_OF)):
        result = assess_freshness(latest, as_of)
        assert result.tier == FRESHNESS_TIER_UNKNOWN
        assert result.age_days is None
        assert result.confidence == Decimal("0")
        assert result.lookahead is False
        assert result.cadence_fallback is False


def test_accepts_iso_strings_and_datetimes() -> None:
    result = assess_freshness("2026-06-30", datetime(2026, 7, 1, 15, 30))
    assert result.age_days == 1
    assert result.tier == FRESHNESS_TIER_FRESH


def test_future_dated_series_stays_fresh_with_lookahead_disclosure() -> None:
    result = assess_freshness(date(2026, 7, 3), AS_OF)
    assert result.age_days == -2
    assert result.tier == FRESHNESS_TIER_FRESH
    # tier<->confidence invariant: fresh tier carries fresh confidence.
    assert result.confidence == CONFIDENCE_BY_TIER[FRESHNESS_TIER_FRESH]
    assert result.lookahead is True
    assert result.notes == ("LOOKAHEAD_DATE_DETECTED",)


def test_lookahead_boundary_age_zero_vs_negative() -> None:
    same_day = assess_freshness(date(2026, 7, 1), AS_OF)
    assert same_day.age_days == 0
    assert same_day.tier == FRESHNESS_TIER_FRESH
    assert same_day.lookahead is False
    assert same_day.notes == ()

    one_day_ahead = assess_freshness(date(2026, 7, 2), AS_OF)
    assert one_day_ahead.age_days == -1
    assert one_day_ahead.lookahead is True


def test_unknown_cadence_lookahead_discloses_both_flags() -> None:
    result = assess_freshness(date(2026, 7, 3), AS_OF, cadence="Quarterly ")
    assert result.age_days == -2
    assert result.tier == FRESHNESS_TIER_FRESH
    assert result.confidence == CONFIDENCE_BY_TIER[FRESHNESS_TIER_FRESH]
    assert result.lookahead is True
    assert result.cadence_fallback is True


def test_confidence_mapping() -> None:
    assert assess_freshness(date(2026, 6, 30), AS_OF).confidence == Decimal("1")
    assert assess_freshness(date(2026, 6, 20), AS_OF).confidence == Decimal("0.5")
    assert assess_freshness(date(2026, 5, 1), AS_OF).confidence == Decimal("0")


def test_confidence_always_matches_tier_invariant() -> None:
    cases = (
        (date(2026, 6, 30), AS_OF, "daily"),  # fresh
        (date(2026, 6, 20), AS_OF, "daily"),  # stale
        (date(2026, 5, 1), AS_OF, "daily"),  # expired
        (date(2026, 7, 3), AS_OF, "daily"),  # lookahead
        (None, AS_OF, "daily"),  # unknown
        (date(2026, 4, 20), AS_OF, "Monthly"),  # normalized cadence
        (date(2026, 6, 20), AS_OF, "quarterly"),  # cadence fallback
    )
    for latest, as_of, cadence in cases:
        result = assess_freshness(latest, as_of, cadence=cadence)
        assert result.confidence == CONFIDENCE_BY_TIER[result.tier]
