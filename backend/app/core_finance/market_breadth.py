"""Formal market-breadth and limit-up-quality inputs for the Livermore market gate.

Definitions (per trade date ``d``, universe = landed all-A-share daily
observations with a non-null ``pctchange``):

- ``advancing_count``  = #{pctchange > 0}
- ``declining_count``  = #{pctchange < 0}
- ``limit_up_sealed_count`` = #{vendor limit-up flag says the board sealed}
- ``limit_up_broken_count`` = #{intraday high reached the derived limit-up
  price but the vendor flag does not say sealed}

Gate condition inputs derived here:

- ``breadth_5d(t)`` = sum over the 5 most recent landed trade dates ending
  exactly at ``t`` of ``(advancing_count - declining_count)``. Requires a
  complete 5-day window; otherwise the input is missing (``None``).
  Condition ``breadth_5d_positive`` passes when the value is > 0.
- ``limit_up_quality_ok(t)`` = ``sealed(t) > broken(t)``. When no stock touched
  limit-up at all (``sealed + broken == 0``) the signal is undefined and the
  input is missing (``None``).

Limit-up classification basis (mainstream A-share convention):

- Sealed boards come from the vendor yes/no limit flag, which is the
  authoritative point-in-time source. Choice ``HIGHLIMIT`` is such a flag, not
  a price.
- Broken boards ("炸板") are derived: ``prev_close = close / (1 + pctchange/100)``
  and ``limit_price = round_half_up(prev_close * (1 + ratio), 2)``. A row whose
  intraday high reached that price without the sealed flag broke its board.
- ``ratio`` follows the board the code belongs to; a main-board stock with an
  explicit daily ST flag is capped at 5%. When that flag is missing, the stock
  name remains a fallback and its ST cap is dropped when the row's own move is
  already wider than it, because name snapshots can lag 戴帽/摘帽.
- A row whose own ``pctchange`` sits outside its board band is not governed by
  that band (new listing with no first-day cap, board transfer, vendor error),
  so it is reported separately instead of being counted as a broken board.

Price comparison tolerance when classifying sealed/broken from OHLC vs the
exchange limit price: half of the minimum tick (0.01 / 2 = 0.005).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

BREADTH_WINDOW_DAYS = 5
# Half of the minimum A-share price tick (0.01), used when comparing
# high/close against the exchange limit-up price.
LIMIT_PRICE_TOLERANCE = 0.005

# Vendor limit flag literals (Choice HIGHLIMIT / LOWLIMIT).
LIMIT_FLAG_SEALED = "是"
LIMIT_FLAG_NOT_SEALED = "否"

LIMIT_RATIO_MAIN_BOARD = 0.10
LIMIT_RATIO_MAIN_BOARD_ST = 0.05
LIMIT_RATIO_GROWTH_BOARD = 0.20
LIMIT_RATIO_BEIJING = 0.30
# Slack in percentage points before a row's own move is judged to sit outside
# its board band; absorbs limit-price rounding at low prices.
LIMIT_BAND_TOLERANCE_PCT = 0.5

LIMIT_TOUCH_SEALED = "sealed"
LIMIT_TOUCH_BROKEN = "broken"
LIMIT_TOUCH_NO_TOUCH = "no_touch"
LIMIT_TOUCH_OUT_OF_BAND = "out_of_band"
LIMIT_TOUCH_UNCLASSIFIED = "unclassified"

_FLAG_SEALED = "sealed"
_FLAG_NOT_SEALED = "not_sealed"
_FLAG_ABSENT = "absent"
_FLAG_UNSUPPORTED = "unsupported"

_DERIVED_TOUCHED = "touched"
_DERIVED_NOT_TOUCHED = "not_touched"
_DERIVED_OUT_OF_BAND = "out_of_band"
_DERIVED_UNDERIVABLE = "underivable"


@dataclass(frozen=True)
class MarketBreadthDaily:
    """Aggregated all-market counts for one trade date."""

    trade_date: date
    advancing_count: int
    declining_count: int
    limit_up_sealed_count: int
    limit_up_broken_count: int


@dataclass(frozen=True)
class LimitUpObservation:
    """One stock's daily row as needed by the limit-up classification."""

    stock_code: str
    limit_flag: str | None = None
    pctchange: float | None = None
    close_value: float | None = None
    high_value: float | None = None
    stock_name: str | None = None
    is_st: bool | None = None
    listing_date: str | None = None


@dataclass(frozen=True)
class LimitUpDaySummary:
    """Counts and coverage evidence for one trade date's limit-up leg."""

    sealed_count: int
    broken_count: int
    no_touch_count: int
    out_of_band_count: int
    unclassified_count: int
    absent_flag_count: int
    sealed_without_derived_touch_count: int

    @property
    def evaluable(self) -> bool:
        """False when the vendor flag basis is absent for the whole day."""
        return (self.sealed_count + self.broken_count + self.no_touch_count) > 0


def is_st_name(stock_name: str | None) -> bool:
    """Special-treatment marker, which A-share vendors put at the name head.

    Matched inside the leading marker window only (``ST``/``*ST``/``SST``/
    ``S*ST``, optionally behind an ex-rights prefix) so a mid-name ``ST`` never
    silently halves a normal stock's band.
    """
    text = str(stock_name or "").upper().replace(" ", "")
    return "ST" in text[:4]


def resolve_limit_ratio(
    stock_code: str | None,
    *,
    stock_name: str | None = None,
    is_st: bool | None = None,
    pctchange: float | None = None,
) -> float | None:
    """Daily price-limit ratio for a stock, or ``None`` when the code is unusable.

    Board caps take precedence over the ST cap: ChiNext/STAR ST rows keep the
    20% board cap, only main-board ST rows drop to 5%.

    A non-null daily ``is_st`` flag is authoritative. The name heuristic and
    wider-move self-calibration are used only when the daily flag is missing.
    """
    code = _numeric_stock_code(stock_code)
    if not code:
        return None
    if code[:3] in {"688", "689"}:
        return LIMIT_RATIO_GROWTH_BOARD
    if code[:2] == "30":
        return LIMIT_RATIO_GROWTH_BOARD
    if code[:1] in {"4", "8"} or code[:2] == "92":
        return LIMIT_RATIO_BEIJING
    resolved_is_st = is_st if is_st is not None else is_st_name(stock_name)
    if not resolved_is_st:
        return LIMIT_RATIO_MAIN_BOARD
    if is_st is None and pctchange is not None and abs(float(pctchange)) > _band_upper_bound_pct(
        LIMIT_RATIO_MAIN_BOARD_ST
    ):
        return LIMIT_RATIO_MAIN_BOARD
    return LIMIT_RATIO_MAIN_BOARD_ST


def derive_previous_close(close_value: float | None, pctchange: float | None) -> float | None:
    """Previous close implied by the close and its percentage change."""
    if close_value is None or pctchange is None:
        return None
    factor = 1.0 + float(pctchange) / 100.0
    if factor <= 0:
        return None
    return float(close_value) / factor


def derive_limit_up_price(previous_close: float, ratio: float) -> float:
    """Exchange limit-up price: previous close lifted by ``ratio``, rounded half-up to a tick."""
    raw = Decimal(str(previous_close)) * (Decimal("1") + Decimal(str(ratio)))
    return float(raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def classify_limit_touch(observation: LimitUpObservation) -> str:
    """Classify one stock-day against its limit-up board.

    The vendor flag decides sealed boards; everything else is decided by the
    derived limit price.
    """
    flag_state = _flag_state(observation.limit_flag)
    if flag_state == _FLAG_UNSUPPORTED:
        return LIMIT_TOUCH_UNCLASSIFIED
    if flag_state == _FLAG_SEALED:
        return LIMIT_TOUCH_SEALED
    derived = _derived_touch_state(observation)
    if derived == _DERIVED_TOUCHED:
        return LIMIT_TOUCH_BROKEN
    if derived == _DERIVED_NOT_TOUCHED:
        return LIMIT_TOUCH_NO_TOUCH
    if derived == _DERIVED_OUT_OF_BAND:
        return LIMIT_TOUCH_OUT_OF_BAND
    return LIMIT_TOUCH_UNCLASSIFIED


def summarize_limit_up_day(observations: Iterable[LimitUpObservation]) -> LimitUpDaySummary:
    """Aggregate one trade date's limit-up classification with coverage evidence."""
    sealed = broken = no_touch = out_of_band = unclassified = 0
    absent_flag = 0
    sealed_without_derived_touch = 0
    for observation in observations:
        if _flag_state(observation.limit_flag) == _FLAG_ABSENT:
            absent_flag += 1
        outcome = classify_limit_touch(observation)
        if outcome == LIMIT_TOUCH_SEALED:
            sealed += 1
            if _derived_touch_state(observation) != _DERIVED_TOUCHED:
                sealed_without_derived_touch += 1
        elif outcome == LIMIT_TOUCH_BROKEN:
            broken += 1
        elif outcome == LIMIT_TOUCH_NO_TOUCH:
            no_touch += 1
        elif outcome == LIMIT_TOUCH_OUT_OF_BAND:
            out_of_band += 1
        else:
            unclassified += 1
    return LimitUpDaySummary(
        sealed_count=sealed,
        broken_count=broken,
        no_touch_count=no_touch,
        out_of_band_count=out_of_band,
        unclassified_count=unclassified,
        absent_flag_count=absent_flag,
        sealed_without_derived_touch_count=sealed_without_derived_touch,
    )


def _numeric_stock_code(stock_code: str | None) -> str:
    text = str(stock_code or "").strip().upper()
    if not text:
        return ""
    for part in text.split("."):
        digits = "".join(character for character in part if character.isdigit())
        if len(digits) >= 6:
            return digits
    return ""


def _flag_state(limit_flag: str | None) -> str:
    value = str(limit_flag or "").strip()
    if value == LIMIT_FLAG_SEALED:
        return _FLAG_SEALED
    if value == LIMIT_FLAG_NOT_SEALED:
        return _FLAG_NOT_SEALED
    if not value:
        return _FLAG_ABSENT
    # Legacy landings put Tushare stk_limit prices in the same column; the
    # yes/no flag semantics do not apply to those rows.
    return _FLAG_UNSUPPORTED


def _band_upper_bound_pct(ratio: float) -> float:
    return ratio * 100.0 + LIMIT_BAND_TOLERANCE_PCT


def _derived_touch_state(observation: LimitUpObservation) -> str:
    ratio = resolve_limit_ratio(
        observation.stock_code,
        stock_name=observation.stock_name,
        is_st=observation.is_st,
        pctchange=observation.pctchange,
    )
    if ratio is None or observation.high_value is None or observation.pctchange is None:
        return _DERIVED_UNDERIVABLE
    if abs(float(observation.pctchange)) > _band_upper_bound_pct(ratio):
        return _DERIVED_OUT_OF_BAND
    previous_close = derive_previous_close(observation.close_value, observation.pctchange)
    if previous_close is None or previous_close <= 0:
        return _DERIVED_UNDERIVABLE
    limit_price = derive_limit_up_price(previous_close, ratio)
    if float(observation.high_value) >= limit_price - LIMIT_PRICE_TOLERANCE:
        return _DERIVED_TOUCHED
    return _DERIVED_NOT_TOUCHED


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
