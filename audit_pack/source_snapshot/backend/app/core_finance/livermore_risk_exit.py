from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

FORMULA_VERSION = "rv_livermore_risk_exit_ema10_mvp_v1"
MVP_RULE_LABEL = "10EMA invalidation"
REQUIRED_INPUTS: tuple[str, ...] = ("positions", "entry_cost", "bars_since_entry", "close_history")
MIN_HISTORY = 10
EMA_WINDOW = 10


@dataclass(frozen=True)
class RiskExitSnapshot:
    stock_code: str
    stock_name: str
    entry_cost: object
    bars_since_entry: object
    close_history: Sequence[object] = ()


@dataclass(frozen=True)
class RiskExitResult:
    payload: dict[str, object]


def compute_risk_exit(
    *,
    as_of_date: str,
    snapshots: list[RiskExitSnapshot],
) -> RiskExitResult:
    items: list[dict[str, object]] = []
    excluded_position_count = 0
    insufficient_history_count = 0

    for snapshot in snapshots:
        validated = _validated_snapshot(snapshot)
        if validated is None:
            excluded_position_count += 1
            if _is_insufficient_history(snapshot):
                insufficient_history_count += 1
            continue
        row = _risk_exit_row(snapshot, validated)
        if row is None:
            continue
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
        }
    )


def _risk_exit_row(
    snapshot: RiskExitSnapshot,
    validated: tuple[float, int, list[float]],
) -> dict[str, object] | None:
    entry_cost, bars_since_entry, closes = validated
    ema10 = _ema(closes, EMA_WINDOW)
    latest_close = closes[-1]
    prior_close = closes[-2]
    latest_ema10 = ema10[-1]
    prior_ema10 = ema10[-2]
    if latest_close >= latest_ema10 or prior_close >= prior_ema10:
        return None

    return {
        "stock_code": snapshot.stock_code,
        "stock_name": snapshot.stock_name,
        "reason": "2d_below_ema10",
        "entry_cost": round(entry_cost, 6),
        "bars_since_entry": bars_since_entry,
        "latest_close": round(latest_close, 6),
        "latest_ema10": round(latest_ema10, 6),
        "prior_close": round(prior_close, 6),
        "prior_ema10": round(prior_ema10, 6),
    }


def _validated_snapshot(snapshot: RiskExitSnapshot) -> tuple[float, int, list[float]] | None:
    entry_cost = _valid_float(snapshot.entry_cost)
    bars_since_entry = _valid_int(snapshot.bars_since_entry)
    closes = _float_series(snapshot.close_history)
    if entry_cost is None or bars_since_entry is None or closes is None or len(closes) < MIN_HISTORY:
        return None
    return entry_cost, bars_since_entry, closes


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
    return closes is None or len(closes) < MIN_HISTORY


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
