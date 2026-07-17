from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import cast

EPS = 1e-12
FORMULA_VERSION = "rv_fresh_trend_watchlist_candidates_v1"
ACTIVE_MARKET_STATES = frozenset({"WARM", "HOT", "OVERHEAT"})
GROWTH_BOARD_PREFIXES = ("300", "301", "688", "002")
MIN_HISTORY_BARS = 121
MIN_AMOUNT_BARS = 21
MAX_RANKED = 20
MAX_CANDIDATES_PER_SECTOR = 3
MIN_RETURN_20D = 0.08
MAX_RETURN_20D = 0.90
MIN_RETURN_60D = 0.18
MAX_RETURN_60D = 1.60
MIN_RETURN_120D = 0.30
MAX_RETURN_120D = 3.20
MAX_CLOSE_TO_MA20 = 0.25
MAX_CLOSE_EXTENSION_FOR_PENALTY = 0.16
MIN_AMOUNT_RATIO = 0.70
MAX_AMOUNT_RATIO = 3.50
MAX_DAILY_RETURN = 0.095
MAX_LIMIT_UP_STREAK = 2
OLD_ECONOMY_SECTOR_KEYWORDS = (
    "bank",
    "broker",
    "finance",
    "real estate",
    "coal",
    "oil",
    "steel",
    "construction",
    "building",
    "utility",
    "transport",
    "retail",
    "textile",
    "home appliance",
    "银行",
    "非银",
    "房地产",
    "煤炭",
    "石油",
    "钢铁",
    "建筑",
    "公用",
    "交通",
    "商贸",
    "纺织",
    "家用电器",
)


@dataclass(frozen=True)
class FreshTrendWatchlistSnapshot:
    stock_code: str
    stock_name: str
    sector_code: str
    sector_name: str
    concepts: Sequence[object]
    close_value: object
    pctchange: object
    turn: object
    amplitude: object
    hlimitedays: object
    close_history: Sequence[object]
    amount_history: Sequence[object]


@dataclass(frozen=True)
class FreshTrendWatchlistResult:
    payload: dict[str, object]


def compute_fresh_trend_watchlist_candidates(
    *,
    as_of_date: str,
    market_state: str,
    snapshots: list[FreshTrendWatchlistSnapshot],
) -> FreshTrendWatchlistResult:
    raw_state = market_state.strip()
    if raw_state not in ACTIVE_MARKET_STATES:
        return FreshTrendWatchlistResult(
            payload=_build_payload(
                as_of_date=as_of_date,
                market_state=raw_state or market_state,
                input_stock_count=len(snapshots),
                excluded_stock_count=len(snapshots),
                insufficient_history_count=0,
                items=[],
            )
        )

    items_accum: list[dict[str, object]] = []
    excluded_stock_count = 0
    insufficient_history_count = 0
    for snapshot in snapshots:
        closes = _float_series(snapshot.close_history)
        amounts = _float_series(snapshot.amount_history)
        if (
            closes is None
            or amounts is None
            or len(closes) < MIN_HISTORY_BARS
            or len(amounts) < MIN_AMOUNT_BARS
        ):
            row = None
            insufficient_history = True
        else:
            row = _candidate_row(snapshot, closes, amounts)
            insufficient_history = False
        if row is None:
            excluded_stock_count += 1
            if insufficient_history:
                insufficient_history_count += 1
            continue
        items_accum.append(row)

    ordered = sorted(items_accum, key=lambda row: (-cast(float, row["score"]), cast(str, row["stock_code"])))
    capped = _limit_per_sector(ordered)
    truncated = capped[:MAX_RANKED]
    ranked = []
    for index, row in enumerate(truncated, start=1):
        enriched = dict(row)
        enriched["rank"] = index
        ranked.append(enriched)

    excluded_stock_count += max(0, len(ordered) - len(truncated))
    return FreshTrendWatchlistResult(
        payload=_build_payload(
            as_of_date=as_of_date,
            market_state=raw_state,
            input_stock_count=len(snapshots),
            excluded_stock_count=excluded_stock_count,
            insufficient_history_count=insufficient_history_count,
            items=ranked,
        )
    )


def _build_payload(
    *,
    as_of_date: str,
    market_state: str,
    input_stock_count: int,
    excluded_stock_count: int,
    insufficient_history_count: int,
    items: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "as_of_date": as_of_date,
        "formula_version": FORMULA_VERSION,
        "market_state": market_state,
        "input_stock_count": input_stock_count,
        "candidate_count": len(items),
        "excluded_stock_count": excluded_stock_count,
        "insufficient_history_count": insufficient_history_count,
        "observation_only": True,
        "items": items,
    }


def _candidate_row(
    snapshot: FreshTrendWatchlistSnapshot,
    closes: list[float],
    amounts: list[float],
) -> dict[str, object] | None:
    if _is_st_name(snapshot.stock_name):
        return None
    if not _is_growth_board(snapshot.stock_code):
        return None
    if _is_old_economy_sector(snapshot.sector_name):
        return None

    close_price = _valid_float(snapshot.close_value)
    if close_price is None or close_price <= EPS:
        return None

    ma20 = _mean_tail(closes, 20)
    ma60 = _mean_tail(closes, 60)
    ma120 = _mean_tail(closes, 120)
    if not (close_price > ma20 > ma60 > ma120):
        return None

    return_20d = _window_return(close_price, closes, 20)
    return_60d = _window_return(close_price, closes, 60)
    return_120d = _window_return(close_price, closes, 120)
    if not (MIN_RETURN_20D <= return_20d <= MAX_RETURN_20D):
        return None
    if not (MIN_RETURN_60D <= return_60d <= MAX_RETURN_60D):
        return None
    if not (MIN_RETURN_120D <= return_120d <= MAX_RETURN_120D):
        return None

    close_to_ma20 = close_price / ma20 - 1.0
    if close_to_ma20 <= 0 or close_to_ma20 > MAX_CLOSE_TO_MA20:
        return None

    prior_close = closes[-2] if len(closes) >= 2 else 0.0
    if prior_close <= EPS:
        return None
    daily_return = close_price / prior_close - 1.0
    if daily_return >= MAX_DAILY_RETURN:
        return None

    previous_amounts = amounts[-21:-1]
    amount_ma20 = sum(previous_amounts) / 20.0
    amount_today = amounts[-1]
    if amount_ma20 <= EPS or amount_today <= EPS:
        return None
    amount_ratio = amount_today / amount_ma20
    if not (MIN_AMOUNT_RATIO <= amount_ratio <= MAX_AMOUNT_RATIO):
        return None

    hlimitedays = _valid_float(snapshot.hlimitedays)
    if hlimitedays is not None and hlimitedays > MAX_LIMIT_UP_STREAK:
        return None

    pctchange = _valid_float(snapshot.pctchange)
    turn = _valid_float(snapshot.turn)
    amplitude = _valid_float(snapshot.amplitude)
    score = (
        return_20d * 0.40
        + return_60d * 0.28
        + return_120d * 0.14
        + min(amount_ratio, 2.5) * 0.08
        + min((turn or 0.0) / 10.0, 1.0) * 0.06
        + _board_bonus(snapshot.stock_code)
        - max(close_to_ma20 - MAX_CLOSE_EXTENSION_FOR_PENALTY, 0.0) * 0.30
    )

    return {
        "stock_code": snapshot.stock_code,
        "stock_name": snapshot.stock_name,
        "sector_code": snapshot.sector_code,
        "sector_name": snapshot.sector_name,
        "concepts": _clean_concepts(snapshot.concepts),
        "close": round(close_price, 6),
        "ma20": round(ma20, 6),
        "ma60": round(ma60, 6),
        "ma120": round(ma120, 6),
        "return_20d": round(return_20d, 6),
        "return_60d": round(return_60d, 6),
        "return_120d": round(return_120d, 6),
        "close_to_ma20": round(close_to_ma20, 6),
        "amount_ratio": round(amount_ratio, 6),
        "pctchange": round(pctchange, 6) if pctchange is not None else None,
        "turn": round(turn, 6) if turn is not None else None,
        "amplitude": round(amplitude, 6) if amplitude is not None else None,
        "hlimitedays": int(hlimitedays) if hlimitedays is not None else None,
        "score": round(score, 6),
    }


def _limit_per_sector(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    counts: dict[str, int] = {}
    kept: list[dict[str, object]] = []
    for row in rows:
        key = str(row.get("sector_code") or row.get("sector_name") or "")
        count = counts.get(key, 0)
        if count >= MAX_CANDIDATES_PER_SECTOR:
            continue
        counts[key] = count + 1
        kept.append(row)
    return kept


def _window_return(close_price: float, closes: list[float], window: int) -> float:
    start = closes[-window - 1]
    if start <= EPS:
        return 0.0
    return close_price / start - 1.0


def _mean_tail(values: list[float], n: int) -> float:
    return sum(values[-n:]) / float(n)


def _is_growth_board(stock_code: str) -> bool:
    normalized = stock_code.strip().upper()
    return normalized.startswith(GROWTH_BOARD_PREFIXES)


def _board_bonus(stock_code: str) -> float:
    normalized = stock_code.strip().upper()
    if normalized.startswith(("300", "301", "688")):
        return 0.10
    if normalized.startswith("002"):
        return 0.04
    return 0.0


def _is_old_economy_sector(sector_name: str) -> bool:
    normalized = sector_name.strip().lower()
    return any(keyword in normalized for keyword in OLD_ECONOMY_SECTOR_KEYWORDS)


def _is_st_name(stock_name: str) -> bool:
    normalized = stock_name.strip().upper()
    return normalized.startswith("ST") or normalized.startswith("*ST")


def _clean_concepts(values: Sequence[object]) -> list[str]:
    concepts: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        concepts.append(text)
        seen.add(text)
    return concepts


def _float_series(values: Sequence[object]) -> list[float] | None:
    if type(values) is list:
        for value in values:
            if type(value) is not float or not math.isfinite(value):
                break
        else:
            return cast(list[float], values)

    converted = [_valid_float(value) for value in values]
    if any(value is None for value in converted):
        return None
    return [float(cast(float, value)) for value in converted]


def _valid_float(value: object) -> float | None:
    if type(value) is float:
        return value if math.isfinite(value) else None
    if type(value) is int:
        try:
            return float(value)
        except OverflowError:
            return None
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number if math.isfinite(number) else None
