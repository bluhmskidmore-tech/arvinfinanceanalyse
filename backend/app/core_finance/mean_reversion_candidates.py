from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import cast

EPS = 1e-12
FORMULA_VERSION = "rv_mean_reversion_candidates_v1"
ACTIVE_MARKET_STATES = frozenset({"OFF", "WARM"})
# 60 个交易日高点窗口需要「今日收盘价之前」一共 60 根；加上今日至少共 61 根。
MIN_HISTORY_BARS = 61
MAX_RANKED = 20


@dataclass(frozen=True)
class MeanReversionSnapshot:
    stock_code: str
    stock_name: str
    sector_code: str
    sector_name: str
    close_value: object
    low_value: object
    high_value: object
    volume: object
    close_history: Sequence[object]
    volume_history: Sequence[object]


@dataclass(frozen=True)
class MeanReversionResult:
    payload: dict[str, object]


def compute_mean_reversion_candidates(
    *,
    as_of_date: str,
    market_state: str,
    snapshots: list[MeanReversionSnapshot],
) -> MeanReversionResult:
    raw_state = market_state.strip()
    if raw_state not in ACTIVE_MARKET_STATES:
        return MeanReversionResult(
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
        row = _candidate_row(snapshot)
        if row is None:
            excluded_stock_count += 1
            if _is_insufficient_history(snapshot):
                insufficient_history_count += 1
            continue
        items_accum.append(row)

    ordered = sorted(
        items_accum,
        key=lambda r: (-cast(float, r["score"]), cast(str, r["stock_code"])),
    )
    truncated = ordered[:MAX_RANKED]
    ranked = []
    for index, row in enumerate(truncated, start=1):
        enriched = dict(cast(dict[str, object], row))
        enriched["rank"] = index
        ranked.append(enriched)

    return MeanReversionResult(
        payload=_build_payload(
            as_of_date=as_of_date,
            market_state=raw_state,
            input_stock_count=len(snapshots),
            excluded_stock_count=excluded_stock_count + max(0, len(ordered) - MAX_RANKED),
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
        "items": items,
    }


def _candidate_row(snapshot: MeanReversionSnapshot) -> dict[str, object] | None:
    closes = _float_series(snapshot.close_history)
    volumes = _float_series(snapshot.volume_history)
    if closes is None or volumes is None:
        return None
    if len(closes) < MIN_HISTORY_BARS or len(volumes) < MIN_HISTORY_BARS:
        return None
    if len(closes) != len(volumes):
        return None

    close_price = _valid_float(snapshot.close_value)
    low_price = _valid_float(snapshot.low_value)
    high_price = _valid_float(snapshot.high_value)
    volume = _valid_float(snapshot.volume)
    if close_price is None or low_price is None or high_price is None or volume is None:
        return None
    rng = high_price - low_price + EPS
    if rng <= EPS:
        return None

    max_20 = max(closes[-21:-1])
    max_60 = max(closes[-61:-1])
    drawdown_20d = _drawdown(close_price, max_20)
    drawdown_60d = _drawdown(close_price, max_60)

    distressed = drawdown_20d <= -0.15 or drawdown_60d <= -0.25
    if not distressed:
        return None

    ma5 = _mean_tail(closes, 5)
    ma10 = _mean_tail(closes, 10)
    if not (close_price > ma5 > ma10):
        return None

    vol_ma20 = sum(volumes[-21:-1]) / 20.0
    if vol_ma20 <= 0:
        return None
    vol_ratio = volume / vol_ma20
    if not (1.5 <= vol_ratio <= 5.0):
        return None

    close_strength = (close_price - low_price) / rng
    if close_strength < 0.60:
        return None

    prior_close = closes[-2]
    if prior_close <= 0:
        return None
    pct_change = (close_price - prior_close) / prior_close
    if pct_change >= 0.095:
        return None

    score = abs(drawdown_20d) * 0.4 + close_strength * 0.3 + min(vol_ratio / 3.0, 1.0) * 0.3

    return {
        "stock_code": snapshot.stock_code,
        "stock_name": snapshot.stock_name,
        "sector_code": snapshot.sector_code,
        "sector_name": snapshot.sector_name,
        "close": round(close_price, 6),
        "drawdown_20d": round(drawdown_20d, 6),
        "drawdown_60d": round(drawdown_60d, 6),
        "ma5": round(ma5, 6),
        "ma10": round(ma10, 6),
        "close_strength": round(close_strength, 6),
        "vol_ratio": round(vol_ratio, 6),
        "score": round(score, 6),
    }


def _drawdown(close_px: float, peak: float) -> float:
    if peak <= EPS:
        return 0.0
    return (close_px - peak) / peak


def _mean_tail(values: list[float], n: int) -> float:
    return sum(values[-n:]) / float(n)


def _is_insufficient_history(snapshot: MeanReversionSnapshot) -> bool:
    closes = _float_series(snapshot.close_history)
    volumes = _float_series(snapshot.volume_history)
    if closes is None or volumes is None:
        return True
    if len(closes) < MIN_HISTORY_BARS or len(volumes) < MIN_HISTORY_BARS:
        return True
    return False


def _float_series(values: Sequence[object]) -> list[float] | None:
    converted = [_valid_float(value) for value in values]
    if any(value is None for value in converted):
        return None
    return [float(cast(float, value)) for value in converted]


def _valid_float(value: object) -> float | None:
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
