"""Formal market-breadth and limit-up-quality inputs for the Livermore market gate.

Definitions (per trade date ``d``, universe = landed all-A-share daily
observations with a non-null ``pctchange``):

- ``advancing_count``  = #{pctchange > 0}
- ``declining_count``  = #{pctchange < 0}
- ``limit_up_sealed_count`` = #{touched limit-up and closed at the limit price}
- ``limit_up_broken_count`` = #{touched limit-up intraday but closed below it}

Gate condition inputs derived here:

- ``breadth_5d(t)`` = sum over the 5 most recent landed trade dates ending
  exactly at ``t`` of ``(advancing_count - declining_count)``. Requires a
  complete 5-day window; otherwise the input is missing (``None``).
  Condition ``breadth_5d_positive`` passes when the value is > 0.
- ``limit_up_quality_ok(t)`` = ``sealed(t) > broken(t)``. When no stock touched
  limit-up at all (``sealed + broken == 0``) the signal is undefined and the
  input is missing (``None``).

Price comparison tolerance when classifying sealed/broken from OHLC vs the
exchange limit price: half of the minimum tick (0.01 / 2 = 0.005).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

BREADTH_WINDOW_DAYS = 5
# Half of the minimum A-share price tick (0.01), used when comparing
# high/close against the exchange limit-up price.
LIMIT_PRICE_TOLERANCE = 0.005


@dataclass(frozen=True)
class MarketBreadthDaily:
    """Aggregated all-market counts for one trade date."""

    trade_date: date
    advancing_count: int
    declining_count: int
    limit_up_sealed_count: int
    limit_up_broken_count: int


def compute_breadth_5d(rows: list[MarketBreadthDaily], *, as_of: date) -> float | None:
    """Sum of (advancers - decliners) over the 5 most recent trade dates ending at ``as_of``.

    Returns ``None`` (missing) when fewer than 5 landed trade dates are
    available up to ``as_of`` or when ``as_of`` itself is not landed.
    """
    ordered = sorted(
        (row for row in rows if row.trade_date <= as_of),
        key=lambda row: row.trade_date,
    )
    if len(ordered) < BREADTH_WINDOW_DAYS:
        return None
    window = ordered[-BREADTH_WINDOW_DAYS:]
    if window[-1].trade_date != as_of:
        return None
    return float(sum(row.advancing_count - row.declining_count for row in window))


def compute_limit_up_quality_ok(row: MarketBreadthDaily) -> bool | None:
    """Seal quality is positive when sealed limit-ups outnumber broken boards.

    Returns ``None`` (missing) when no stock touched limit-up on that day.
    """
    total = row.limit_up_sealed_count + row.limit_up_broken_count
    if total <= 0:
        return None
    return row.limit_up_sealed_count > row.limit_up_broken_count


def build_gate_supplement_values(rows: list[MarketBreadthDaily]) -> list[dict[str, object]]:
    """Per-date gate supplement inputs for every date with a complete 5-day window."""
    ordered = sorted(rows, key=lambda row: row.trade_date)
    by_date = {row.trade_date: row for row in ordered}
    values: list[dict[str, object]] = []
    for row in ordered:
        breadth = compute_breadth_5d(ordered, as_of=row.trade_date)
        if breadth is None:
            continue
        values.append(
            {
                "trade_date": row.trade_date,
                "breadth_5d": breadth,
                "limit_up_quality_ok": compute_limit_up_quality_ok(by_date[row.trade_date]),
            }
        )
    return values
