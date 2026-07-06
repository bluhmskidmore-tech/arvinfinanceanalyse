"""Shared data-freshness policy for macro / market-data inputs.

Consumers (external data watermark, Livermore input checks) call
``assess_freshness`` with the latest business date of a series and the
as-of date of the computation. Thresholds are calendar days on purpose:
they must stay explainable to the user and independent of any trading
calendar table.

This module must stay stdlib-only so both ``app.`` and ``backend.app.``
import roots can use it without pulling extra project dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

FRESHNESS_TIER_FRESH = "fresh"
FRESHNESS_TIER_STALE = "stale"
FRESHNESS_TIER_EXPIRED = "expired"
FRESHNESS_TIER_UNKNOWN = "unknown"

# Calendar-day thresholds per series cadence. Daily curves lagging more
# than 3 calendar days are suspect even across a long weekend; monthly
# macro prints lag by publication design, so the window is wider.
STALE_AFTER_DAYS: dict[str, int] = {"daily": 3, "weekly": 10, "monthly": 45}
EXPIRED_AFTER_DAYS: dict[str, int] = {"daily": 15, "weekly": 30, "monthly": 100}

CONFIDENCE_BY_TIER: dict[str, Decimal] = {
    FRESHNESS_TIER_FRESH: Decimal("1"),
    FRESHNESS_TIER_STALE: Decimal("0.5"),
    FRESHNESS_TIER_EXPIRED: Decimal("0"),
    FRESHNESS_TIER_UNKNOWN: Decimal("0"),
}


@dataclass(frozen=True)
class FreshnessAssessment:
    # Raw as_of - latest gap; negative means the series is dated after
    # as_of (a look-ahead smell the consumer may want to surface).
    age_days: int | None
    tier: str
    confidence: Decimal
    notes: tuple[str, ...] = ()


def _coerce_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip()[:10])
        except ValueError:
            return None
    return None


def assess_freshness(
    latest_business_date: Any,
    as_of_date: Any,
    *,
    cadence: str = "daily",
) -> FreshnessAssessment:
    latest = _coerce_date(latest_business_date)
    as_of = _coerce_date(as_of_date)
    if latest is None or as_of is None:
        return FreshnessAssessment(
            age_days=None,
            tier=FRESHNESS_TIER_UNKNOWN,
            confidence=CONFIDENCE_BY_TIER[FRESHNESS_TIER_UNKNOWN],
        )
    age_days = (as_of - latest).days
    key = cadence if cadence in STALE_AFTER_DAYS else "daily"
    if age_days < 0:
        return FreshnessAssessment(
            age_days=age_days,
            tier=FRESHNESS_TIER_FRESH,
            confidence=CONFIDENCE_BY_TIER[FRESHNESS_TIER_STALE],
            notes=("LOOKAHEAD_DATE_DETECTED",),
        )
    if age_days > EXPIRED_AFTER_DAYS[key]:
        tier = FRESHNESS_TIER_EXPIRED
    elif age_days > STALE_AFTER_DAYS[key]:
        tier = FRESHNESS_TIER_STALE
    else:
        tier = FRESHNESS_TIER_FRESH
    return FreshnessAssessment(age_days=age_days, tier=tier, confidence=CONFIDENCE_BY_TIER[tier])
