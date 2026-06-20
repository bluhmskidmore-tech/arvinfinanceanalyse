from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

FORMULA_VERSION = "rv_livermore_risk_exit_ema10_volume_v2"
MVP_RULE_LABEL = "10EMA invalidation + volume confirmation"
REQUIRED_INPUTS: tuple[str, ...] = (
    "positions",
    "entry_cost",
    "bars_since_entry",
    "close_history",
    "volume_history",
)
MIN_HISTORY = 21
EMA_WINDOW = 10
VOLUME_MA_WINDOW = 20
VOLUME_CONFIRMATION_RATIO = 1.3


@dataclass(frozen=True)
class RiskExitSnapshot:
    stock_code: str
    stock_name: str
    entry_cost: object
    bars_since_entry: object
    close_history: Sequence[object] = ()
    volume_history: Sequence[object] = ()


@dataclass(frozen=True)
class RiskExitResult:
    payload: dict[str, object]


def compute_risk_exit(
    *,
    as_of_date: str,
    snapshots: list[RiskExitSnapshot],
) -> RiskExitResult:
    items: list[dict[str, object]] = []
    watch_items: list[dict[str, object]] = []
    excluded_position_count = 0
    insufficient_history_count = 0

    for snapshot in snapshots:
        validated = _validated_snapshot(snapshot)
        if validated is None:
            excluded_position_count += 1
            if _is_insufficient_history(snapshot):
                insufficient_history_count += 1
            continue
        watch_item = _watch_item(snapshot, validated)
        watch_items.append(watch_item)
        row = _risk_exit_row(watch_item)
        if row is not None:
            items.append(row)

    return RiskExitResult(
        payload={
            "as_of_date": as_of_date,
            "formula_version": FORMULA_VERSION,
            "position_count": len(snapshots),
            "signal_count": len(items),
            "excluded_position_count": excluded_position_count,
            "insufficient_history_count": insufficient_history_count,
            "items": items,
            "watch_items": watch_items,
        }
    )


def _watch_item(
    snapshot: RiskExitSnapshot,
    validated: tuple[float, int, list[float], list[float]],
) -> dict[str, object]:
    entry_cost, bars_since_entry, closes, volumes = validated
    ema10 = _ema(closes, EMA_WINDOW)
    latest_close = closes[-1]
    prior_close = closes[-2]
    latest_ema10 = ema10[-1]
    prior_ema10 = ema10[-2]
    latest_volume = volumes[-1]
    volume_ma20 = sum(volumes[-(VOLUME_MA_WINDOW + 1) : -1]) / float(VOLUME_MA_WINDOW)
    volume_ratio = latest_volume / volume_ma20 if volume_ma20 > 0 else 0.0
    price_below_ema = latest_close < latest_ema10 and prior_close < prior_ema10
    volume_confirmed = volume_ratio >= VOLUME_CONFIRMATION_RATIO
    triggered = price_below_ema and volume_confirmed

    return {
        "stock_code": snapshot.stock_code,
        "stock_name": snapshot.stock_name,
        "entry_cost": round(entry_cost, 6),
        "bars_since_entry": bars_since_entry,
        "latest_close": round(latest_close, 6),
        "latest_ema10": round(latest_ema10, 6),
        "prior_close": round(prior_close, 6),
        "prior_ema10": round(prior_ema10, 6),
        "latest_volume": round(latest_volume, 6),
        "volume_ma20": round(volume_ma20, 6),
        "volume_ratio": round(volume_ratio, 6),
        "price_below_ema": price_below_ema,
        "volume_confirmed": volume_confirmed,
        "exit_watch_price": round(latest_ema10, 6),
        "triggered": triggered,
    }


def _risk_exit_row(watch_item: dict[str, object]) -> dict[str, object] | None:
    if not bool(watch_item["triggered"]):
        return None

    return {
        "stock_code": watch_item["stock_code"],
        "stock_name": watch_item["stock_name"],
        "reason": "2d_below_ema10_with_volume",
        "entry_cost": watch_item["entry_cost"],
        "bars_since_entry": watch_item["bars_since_entry"],
        "latest_close": watch_item["latest_close"],
        "latest_ema10": watch_item["latest_ema10"],
        "prior_close": watch_item["prior_close"],
        "prior_ema10": watch_item["prior_ema10"],
        "volume_ratio": watch_item["volume_ratio"],
    }


def _validated_snapshot(
    snapshot: RiskExitSnapshot,
) -> tuple[float, int, list[float], list[float]] | None:
    entry_cost = _valid_float(snapshot.entry_cost)
    bars_since_entry = _valid_int(snapshot.bars_since_entry)
    closes = _float_series(snapshot.close_history)
    volumes = _float_series(snapshot.volume_history)
    if (
        entry_cost is None
        or bars_since_entry is None
        or closes is None
        or volumes is None
        or len(closes) < MIN_HISTORY
        or len(volumes) < MIN_HISTORY
        or len(closes) != len(volumes)
    ):
        return None
    return entry_cost, bars_since_entry, closes, volumes


def _ema(values: list[float], window: int) -> list[float]:
    alpha = 2.0 / (window + 1.0)
    ema: list[float] = []
    for value in values:
        if not ema:
            ema.append(value)
        else:
            ema.append(alpha * value + (1.0 - alpha) * ema[-1])
    return ema


def _is_insufficient_history(snapshot: RiskExitSnapshot) -> bool:
    closes = _float_series(snapshot.close_history)
    volumes = _float_series(snapshot.volume_history)
    return (
        closes is None
        or volumes is None
        or len(closes) < MIN_HISTORY
        or len(volumes) < MIN_HISTORY
    )


def _float_series(values: Sequence[object]) -> list[float] | None:
    converted = [_valid_float(value) for value in values]
    if any(value is None for value in converted):
        return None
    return [float(value) for value in converted if value is not None]


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


def _valid_int(value: object) -> int | None:
    number = _valid_float(value)
    return None if number is None else int(number)
