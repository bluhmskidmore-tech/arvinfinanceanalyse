"""Cadence-aware freshness age for homepage macro observation periods."""

from __future__ import annotations

import calendar
from datetime import date
from typing import Literal

HomeMacroCadence = Literal["monthly", "quarterly", "event"]


def home_macro_freshness_age_days(
    observation_date: date,
    reference_date: date,
    *,
    cadence: HomeMacroCadence,
) -> int:
    """Measure age from the represented period end, not a storage convention."""
    anchor = observation_date
    if cadence == "monthly":
        anchor = observation_date.replace(
            day=calendar.monthrange(observation_date.year, observation_date.month)[1]
        )
    return (reference_date - anchor).days
