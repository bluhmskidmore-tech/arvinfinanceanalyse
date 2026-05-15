from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from typing import cast

EPS = 1e-12
FORMULA_VERSION = "rv_livermore_stock_candidates_bundle_v6"
DEFAULT_STOCK_CANDIDATE_POLICY = "default"
EXP3B_STOCK_CANDIDATE_POLICY = "exp3b"
MIN_HISTORY = 120
EMA_WINDOW = 10
MAX_RANKED = 6
MAX_BREAKOUT_EXTENSION_NORM = 0.35


@dataclass(frozen=True)
class StockCandidateSnapshot:
    stock_code: str
    stock_name: str
    sector_code: str
    sector_name: str
    sector_rank: object
    open_value: object
    high_value: object
    low_value: object
    close_value: object
    turnover_free: object
    limit_ratio: object
    one_word_board: bool = False
    closed_up_limit: bool = False
    close_history: Sequence[object] = ()
    turnover_history: Sequence[object] = ()


@dataclass(frozen=True)
class StockCandidateResult:
    payload: dict[str, object]


@dataclass(frozen=True)
class _StockCandidatePolicy:
    name: str
    active_market_states: frozenset[str]
    close_strength_min: float
    gap_norm_max: float
    abnormal_turnover_min: float
    abnormal_turnover_max: float
    close_strength_first: bool = False


_POLICY_BY_NAME: dict[str, _StockCandidatePolicy] = {
    DEFAULT_STOCK_CANDIDATE_POLICY: _StockCandidatePolicy(
        name=DEFAULT_STOCK_CANDIDATE_POLICY,
        active_market_states=frozenset({"WARM", "HOT", "OVERHEAT"}),
        close_strength_min=0.95,
        gap_norm_max=0.45,
        abnormal_turnover_min=1.0,
        abnormal_turnover_max=3.5,
    ),
    EXP3B_STOCK_CANDIDATE_POLICY: _StockCandidatePolicy(
        name=EXP3B_STOCK_CANDIDATE_POLICY,
        active_market_states=frozenset({"WARM", "HOT"}),
        close_strength_min=0.99,
        gap_norm_max=0.35,
        abnormal_turnover_min=1.2,
        abnormal_turnover_max=2.4,
        close_strength_first=True,
    ),
}
ACTIVE_MARKET_STATES = set(_POLICY_BY_NAME[DEFAULT_STOCK_CANDIDATE_POLICY].active_market_states)


def compute_stock_candidates(
    *,
    as_of_date: str,
    market_state: str,
    snapshots: list[StockCandidateSnapshot],
    include_universe: bool = False,
    policy_name: str = DEFAULT_STOCK_CANDIDATE_POLICY,
) -> StockCandidateResult:
    policy = _resolve_policy(policy_name)
    if market_state not in policy.active_market_states:
        return StockCandidateResult(
            payload=_build_payload(
                as_of_date=as_of_date,
                market_state=market_state,
                selection_policy=policy.name,
                input_stock_count=len(snapshots),
                excluded_stock_count=len(snapshots),
                insufficient_history_count=0,
                items=[],
                universe_items=[] if include_universe else None,
            )
        )

    items: list[dict[str, object]] = []
    excluded_stock_count = 0
    insufficient_history_count = 0
    for snapshot in snapshots:
        candidate = _candidate_row(snapshot, market_state=market_state, policy=policy)
        if candidate is None:
            excluded_stock_count += 1
            if _is_insufficient_history(snapshot):
                insufficient_history_count += 1
            continue
        items.append(candidate)

    ordered = sorted(
        items,
        key=_candidate_close_strength_first_sort_key if policy.close_strength_first else _candidate_sort_key,
    )
    universe_items = _universe_items(ordered) if include_universe else None
    truncated = ordered[:MAX_RANKED]
    ranked = [
        {
            "rank": index,
            **row,
        }
        for index, row in enumerate(truncated, start=1)
    ]
    return StockCandidateResult(
            payload=_build_payload(
                as_of_date=as_of_date,
                market_state=market_state,
                selection_policy=policy.name,
                input_stock_count=len(snapshots),
                excluded_stock_count=excluded_stock_count + max(0, len(ordered) - MAX_RANKED),
                insufficient_history_count=insufficient_history_count,
                items=ranked,
                universe_items=universe_items,
        )
    )


def _candidate_row(
    snapshot: StockCandidateSnapshot,
    *,
    market_state: str,
    policy: _StockCandidatePolicy,
) -> dict[str, object] | None:
    closes = _float_series(snapshot.close_history)
    turns = _float_series(snapshot.turnover_history)
    if closes is None or turns is None or len(closes) < MIN_HISTORY or len(turns) < MIN_HISTORY:
        return None

    sector_rank = _valid_int(snapshot.sector_rank)
    open_value = _valid_float(snapshot.open_value)
    high_value = _valid_float(snapshot.high_value)
    low_value = _valid_float(snapshot.low_value)
    close_value = _valid_float(snapshot.close_value)
    turnover_free = _valid_float(snapshot.turnover_free)
    limit_ratio = _valid_float(snapshot.limit_ratio)
    if (
        sector_rank is None
        or open_value is None
        or high_value is None
        or low_value is None
        or close_value is None
        or turnover_free is None
        or limit_ratio is None
    ):
        return None
    if sector_rank > 3:
        return None
    if limit_ratio <= 0:
        return None
    if snapshot.one_word_board or snapshot.closed_up_limit:
        return None

    breakout_level = max(closes[-56:-1])
    ema10 = _ema(closes, EMA_WINDOW)[-1]
    ma20 = _moving_average(closes, 20)
    ma60 = _moving_average(closes, 60)
    ma120 = _moving_average(closes, 120)
    close_strength = _close_strength(close=close_value, low=low_value, high=high_value)
    gap_norm = _gap_norm(open_value=open_value, prior_close=closes[-2], limit_ratio=limit_ratio)
    breakout_extension_norm = _breakout_extension_norm(
        close_value=close_value,
        breakout_level=breakout_level,
        limit_ratio=limit_ratio,
    )
    abnormal_turnover = _abnormal_turnover(turnover_free=turnover_free, turns=turns)

    signal = (
        close_value > breakout_level
        and ma20 > ma60 > ma120
        and close_strength >= policy.close_strength_min
        and gap_norm <= policy.gap_norm_max
        and _breakout_extension_allowed(
            market_state=market_state,
            breakout_extension_norm=breakout_extension_norm,
        )
        and policy.abnormal_turnover_min <= abnormal_turnover <= policy.abnormal_turnover_max
    )
    if not signal:
        return None

    return {
        "stock_code": snapshot.stock_code,
        "stock_name": snapshot.stock_name,
        "sector_code": snapshot.sector_code,
        "sector_name": snapshot.sector_name,
        "sector_rank": sector_rank,
        "close": round(close_value, 6),
        "breakout_level": round(breakout_level, 6),
        "ema10": round(ema10, 6),
        "ma20": round(ma20, 6),
        "ma60": round(ma60, 6),
        "ma120": round(ma120, 6),
        "close_strength": round(close_strength, 6),
        "gap_norm": round(gap_norm, 6),
        "breakout_extension_norm": round(breakout_extension_norm, 6),
        "abnormal_turnover": round(abnormal_turnover, 6),
        "selection_policy": policy.name,
    }


def _build_payload(
    *,
    as_of_date: str,
    market_state: str,
    selection_policy: str,
    input_stock_count: int,
    excluded_stock_count: int,
    insufficient_history_count: int,
    items: list[dict[str, object]],
    universe_items: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "as_of_date": as_of_date,
        "formula_version": FORMULA_VERSION,
        "market_state": market_state,
        "selection_policy": selection_policy,
        "input_stock_count": input_stock_count,
        "candidate_count": len(items),
        "excluded_stock_count": excluded_stock_count,
        "insufficient_history_count": insufficient_history_count,
        "items": items,
    }
    if universe_items is not None:
        payload["universe_items"] = universe_items
    return payload


def _universe_items(ordered: list[dict[str, object]]) -> list[dict[str, object]]:
    old_rank_by_code = {
        str(row["stock_code"]): index
        for index, row in enumerate(sorted(ordered, key=_candidate_old_sort_key), start=1)
    }
    return [
        {
            "new_rank": index,
            "old_rank": old_rank_by_code.get(str(row["stock_code"])),
            "eligible_before_truncation": True,
            "selected_new_top6": index <= MAX_RANKED,
            "selected_old_top6": (old_rank_by_code.get(str(row["stock_code"])) or 9999) <= MAX_RANKED,
            **row,
        }
        for index, row in enumerate(ordered, start=1)
    ]


def _is_insufficient_history(snapshot: StockCandidateSnapshot) -> bool:
    closes = _float_series(snapshot.close_history)
    turns = _float_series(snapshot.turnover_history)
    return closes is None or turns is None or len(closes) < MIN_HISTORY or len(turns) < MIN_HISTORY


def _moving_average(values: list[float], window: int) -> float:
    return sum(values[-window:]) / window


def _ema(values: list[float], window: int) -> list[float]:
    alpha = 2.0 / (window + 1.0)
    ema: list[float] = []
    for value in values:
        if not ema:
            ema.append(value)
        else:
            ema.append(alpha * value + (1.0 - alpha) * ema[-1])
    return ema


def _close_strength(*, close: float, low: float, high: float) -> float:
    return (close - low) / (high - low + EPS)


def _gap_norm(*, open_value: float, prior_close: float, limit_ratio: float) -> float:
    return ((open_value - prior_close) / prior_close) / limit_ratio


def _breakout_extension_norm(*, close_value: float, breakout_level: float, limit_ratio: float) -> float:
    return ((close_value - breakout_level) / (breakout_level + EPS)) / limit_ratio


def _breakout_extension_allowed(*, market_state: str, breakout_extension_norm: float) -> bool:
    if market_state != "OVERHEAT":
        return True
    return breakout_extension_norm <= MAX_BREAKOUT_EXTENSION_NORM


def _abnormal_turnover(*, turnover_free: float, turns: list[float]) -> float:
    median20 = statistics.median(turns[-21:-1])
    return math.log1p(turnover_free / (median20 + EPS))


def _candidate_sort_key(row: dict[str, object]) -> tuple[float, float, int, str]:
    return (
        -cast(float, row["abnormal_turnover"]),
        -cast(float, row["close_strength"]),
        cast(int, row["sector_rank"]),
        str(row["stock_code"]),
    )


def _candidate_close_strength_first_sort_key(row: dict[str, object]) -> tuple[float, float, int, str]:
    return (
        -cast(float, row["close_strength"]),
        -cast(float, row["abnormal_turnover"]),
        cast(int, row["sector_rank"]),
        str(row["stock_code"]),
    )


def _candidate_old_sort_key(row: dict[str, object]) -> tuple[int, float, float, str]:
    return (
        cast(int, row["sector_rank"]),
        -cast(float, row["abnormal_turnover"]),
        -cast(float, row["close_strength"]),
        str(row["stock_code"]),
    )


def _resolve_policy(policy_name: str) -> _StockCandidatePolicy:
    policy = _POLICY_BY_NAME.get(policy_name)
    if policy is None:
        supported = ", ".join(sorted(_POLICY_BY_NAME))
        raise ValueError(f"Unsupported stock candidate policy '{policy_name}'. Supported policies: {supported}.")
    return policy


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
