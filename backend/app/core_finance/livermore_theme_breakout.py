from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from typing import cast

EPS = 1e-12
FORMULA_VERSION = "rv_livermore_theme_breakout_real_concept_v3"
STRONG_PCTCHANGE_THRESHOLD = 5.0
MIN_STRONG_STOCK_COUNT = 3
MIN_LIMIT_STOCK_COUNT = 2
MIN_ADVANCE_RATIO = 0.55
MIN_AVG_PCTCHANGE = 3.0
MAX_ITEMS_PER_THEME = 8
MAX_THEMES = 30
MAX_REVIEW_ITEMS = 5


@dataclass(frozen=True)
class ThemeBreakoutSnapshot:
    stock_code: str
    stock_name: str
    sector_code: str
    sector_name: str
    sector_rank: object
    open_value: object
    high_value: object
    low_value: object
    close_value: object
    pctchange: object
    turn: object
    amplitude: object
    closed_up_limit: bool = False
    concept_code: str = ""
    concept_name: str = ""
    movement_event_count: int = 0
    latest_event_title: str = ""
    latest_event_time: str = ""


@dataclass(frozen=True)
class ThemeBreakoutResult:
    payload: dict[str, object]


@dataclass(frozen=True)
class _EvaluatedThemeRow:
    row: dict[str, object]
    passed: bool
    failed_gate_codes: tuple[str, ...]


@dataclass(frozen=True)
class _ThemeDefinition:
    key: str
    name: str
    parent_sector_codes: tuple[str, ...]
    parent_sector_names: tuple[str, ...]
    stock_name_keywords: tuple[str, ...]


_THEME_DEFINITIONS: tuple[_ThemeDefinition, ...] = (
    _ThemeDefinition(
        key="semiconductor_proxy",
        name="Semiconductor proxy",
        parent_sector_codes=("801080",),
        parent_sector_names=("electronic", "electronics", "dianzi", "电子"),
        stock_name_keywords=(
            "semiconductor",
            "chip",
            "micro",
            "wafer",
            "ic",
            "半导体",
            "芯",
            "晶圆",
            "集成",
            "微电子",
        ),
    ),
)


def compute_theme_breakout(
    *,
    as_of_date: str,
    snapshots: list[ThemeBreakoutSnapshot],
) -> ThemeBreakoutResult:
    evaluated_rows: list[_EvaluatedThemeRow] = []
    real_groups: dict[tuple[str, str], list[dict[str, object]]] = {}
    for snapshot in snapshots:
        concept_code = snapshot.concept_code.strip()
        concept_name = snapshot.concept_name.strip()
        if not (concept_code or concept_name):
            continue
        stock_row = _stock_row(None, snapshot)
        if stock_row is None:
            continue
        real_groups.setdefault((concept_code or concept_name, concept_name or concept_code), []).append(stock_row)

    if real_groups:
        for (concept_code, concept_name), stock_rows in real_groups.items():
            row = _evaluate_theme_row(
                as_of_date=as_of_date,
                theme_key=f"concept:{concept_code}",
                theme_name=concept_name,
                source_kind="real_concept",
                stock_rows=stock_rows,
            )
            if row is not None:
                evaluated_rows.append(row)
    else:
        for definition in _THEME_DEFINITIONS:
            candidates = [_stock_row(definition, snapshot) for snapshot in snapshots]
            stock_rows = [row for row in candidates if row is not None]
            if not stock_rows:
                continue

            row = _evaluate_theme_row(
                as_of_date=as_of_date,
                theme_key=definition.key,
                theme_name=definition.name,
                source_kind="proxy",
                stock_rows=stock_rows,
            )
            if row is not None:
                evaluated_rows.append(row)

    ordered = sorted([row.row for row in evaluated_rows if row.passed], key=_theme_sort_key)[:MAX_THEMES]
    ranked = [{"rank": index, **row} for index, row in enumerate(ordered, start=1)]
    review_items = [
        _review_row(row)
        for row in sorted((item for item in evaluated_rows if not item.passed), key=lambda item: _theme_sort_key(item.row))[
            :MAX_REVIEW_ITEMS
        ]
    ]
    return ThemeBreakoutResult(
        payload={
            "as_of_date": as_of_date,
            "formula_version": FORMULA_VERSION,
            "is_proxy": not real_groups,
            "theme_count": len(ranked),
            "items": ranked,
            "review_items": review_items,
        }
    )


def _stock_row(
    definition: _ThemeDefinition | None,
    snapshot: ThemeBreakoutSnapshot,
) -> dict[str, object] | None:
    if definition is not None and not _matches_theme(definition, snapshot):
        return None

    sector_rank = _valid_int(snapshot.sector_rank)
    pctchange = _valid_float(snapshot.pctchange)
    turn = _valid_float(snapshot.turn)
    amplitude = _valid_float(snapshot.amplitude)
    open_value = _valid_float(snapshot.open_value)
    high_value = _valid_float(snapshot.high_value)
    low_value = _valid_float(snapshot.low_value)
    close_value = _valid_float(snapshot.close_value)
    if (
        sector_rank is None
        or pctchange is None
        or turn is None
        or amplitude is None
        or open_value is None
        or high_value is None
        or low_value is None
        or close_value is None
    ):
        return None

    strong = pctchange >= STRONG_PCTCHANGE_THRESHOLD
    if not strong and not snapshot.closed_up_limit:
        return None

    close_strength = _close_strength(close=close_value, low=low_value, high=high_value)
    return {
        "stock_code": snapshot.stock_code,
        "stock_name": snapshot.stock_name,
        "sector_code": snapshot.sector_code,
        "sector_name": snapshot.sector_name,
        "sector_rank": sector_rank,
        "open": round(open_value, 6),
        "high": round(high_value, 6),
        "low": round(low_value, 6),
        "close": round(close_value, 6),
        "pctchange": round(pctchange, 6),
        "turn": round(turn, 6),
        "amplitude": round(amplitude, 6),
        "close_strength": round(close_strength, 6),
        "closed_up_limit": bool(snapshot.closed_up_limit),
        "strong": strong,
        "concept_code": snapshot.concept_code,
        "concept_name": snapshot.concept_name,
        "movement_event_count": max(0, int(snapshot.movement_event_count)),
        "latest_event_title": snapshot.latest_event_title,
        "latest_event_time": snapshot.latest_event_time,
    }


def _evaluate_theme_row(
    *,
    as_of_date: str,
    theme_key: str,
    theme_name: str,
    source_kind: str,
    stock_rows: list[dict[str, object]],
) -> _EvaluatedThemeRow | None:
    member_count = len(stock_rows)
    advance_count = sum(1 for row in stock_rows if cast(float, row["pctchange"]) > 0)
    strong_stock_count = sum(1 for row in stock_rows if cast(bool, row["strong"]))
    limit_stock_count = sum(1 for row in stock_rows if cast(bool, row["closed_up_limit"]))
    advance_ratio = advance_count / member_count if member_count else 0.0
    avg_pctchange = _average(row["pctchange"] for row in stock_rows)
    avg_turn = _average(row["turn"] for row in stock_rows)
    avg_amplitude = _average(row["amplitude"] for row in stock_rows)
    parent_sector_rank = min(cast(int, row["sector_rank"]) for row in stock_rows)
    movement_event_count = sum(cast(int, row["movement_event_count"]) for row in stock_rows)
    movement_rows = [
        row
        for row in stock_rows
        if cast(int, row["movement_event_count"]) > 0 and str(row["latest_event_time"])
    ]
    latest_event = max(movement_rows, key=lambda row: str(row["latest_event_time"])) if movement_rows else None

    has_cluster_strength = (
        strong_stock_count >= MIN_STRONG_STOCK_COUNT
        or limit_stock_count >= MIN_LIMIT_STOCK_COUNT
        or (movement_event_count > 0 and strong_stock_count >= 2)
    )
    has_breadth = advance_ratio >= MIN_ADVANCE_RATIO or avg_pctchange >= MIN_AVG_PCTCHANGE
    ordered_items = sorted(stock_rows, key=_stock_sort_key)[:MAX_ITEMS_PER_THEME]
    leader_codes = ", ".join(str(row["stock_code"]) for row in ordered_items[:3])
    failed_gate_codes: list[str] = []
    if not has_cluster_strength:
        failed_gate_codes.append("insufficient_cluster_strength")
    if not has_breadth:
        failed_gate_codes.append("insufficient_breadth")

    row = {
        "as_of_date": as_of_date,
        "theme_key": theme_key,
        "theme_name": theme_name,
        "source_kind": source_kind,
        "parent_sector_code": str(ordered_items[0]["sector_code"]),
        "parent_sector_name": str(ordered_items[0]["sector_name"]),
        "parent_sector_rank": parent_sector_rank,
        "member_count": member_count,
        "advance_count": advance_count,
        "advance_ratio": round(advance_ratio, 6),
        "strong_stock_count": strong_stock_count,
        "limit_stock_count": limit_stock_count,
        "avg_pctchange": round(avg_pctchange, 6),
        "avg_turn": round(avg_turn, 6),
        "avg_amplitude": round(avg_amplitude, 6),
        "movement_event_count": movement_event_count,
        "latest_event_title": "" if latest_event is None else str(latest_event["latest_event_title"]),
        "latest_event_time": "" if latest_event is None else str(latest_event["latest_event_time"]),
        "observation_only": True,
        "reason": _theme_reason(
            source_kind=source_kind,
            strong_stock_count=strong_stock_count,
            limit_stock_count=limit_stock_count,
            movement_event_count=movement_event_count,
            parent_sector_rank=parent_sector_rank,
            leader_codes=leader_codes,
        ),
        "items": ordered_items,
    }
    return _EvaluatedThemeRow(
        row=row,
        passed=not failed_gate_codes,
        failed_gate_codes=tuple(failed_gate_codes),
    )


def _theme_reason(
    *,
    source_kind: str,
    strong_stock_count: int,
    limit_stock_count: int,
    movement_event_count: int,
    parent_sector_rank: int,
    leader_codes: str,
) -> str:
    if source_kind == "real_concept":
        return (
            f"Observation-only real concept cluster: {strong_stock_count} strong rows, "
            f"{limit_stock_count} limit-up rows, {movement_event_count} movement events, "
            f"parent sector rank {parent_sector_rank}, leaders {leader_codes}."
        )
    return (
        f"Observation-only proxy cluster: {strong_stock_count} strong rows, "
        f"{limit_stock_count} limit-up rows, parent sector rank {parent_sector_rank}, "
        f"leaders {leader_codes}."
    )


def _review_row(evaluated: _EvaluatedThemeRow) -> dict[str, object]:
    failed_gate_codes = list(evaluated.failed_gate_codes)
    return {
        **evaluated.row,
        "failed_gates": failed_gate_codes,
        "failed_gate_codes": failed_gate_codes,
        "reason": (
            f"Observation-only near-miss: failed gates {', '.join(failed_gate_codes)}. "
            f"{evaluated.row['reason']}"
        ),
    }


def _matches_theme(definition: _ThemeDefinition, snapshot: ThemeBreakoutSnapshot) -> bool:
    sector_code = str(snapshot.sector_code).strip()
    sector_name = str(snapshot.sector_name).strip().lower()
    stock_name = str(snapshot.stock_name).strip().lower()
    in_parent_sector = sector_code in definition.parent_sector_codes or any(
        name in sector_name for name in definition.parent_sector_names
    )
    if not in_parent_sector:
        return False
    return any(keyword.lower() in stock_name for keyword in definition.stock_name_keywords)


def _theme_sort_key(row: dict[str, object]) -> tuple[int, int, int, float, float, int, str]:
    return (
        -cast(int, row["limit_stock_count"]),
        -cast(int, row["movement_event_count"]),
        -cast(int, row["strong_stock_count"]),
        -cast(float, row["avg_pctchange"]),
        -cast(float, row["avg_turn"]),
        cast(int, row["parent_sector_rank"]),
        str(row["theme_key"]),
    )


def _stock_sort_key(row: dict[str, object]) -> tuple[int, float, float, float, str]:
    return (
        0 if cast(bool, row["closed_up_limit"]) else 1,
        -cast(float, row["pctchange"]),
        -cast(float, row["turn"]),
        -cast(float, row["close_strength"]),
        str(row["stock_code"]),
    )


def _average(values: Iterable[object]) -> float:
    numbers = [cast(float, value) for value in values]
    if not numbers:
        return 0.0
    return sum(numbers) / len(numbers)


def _close_strength(*, close: float, low: float, high: float) -> float:
    return (close - low) / (high - low + EPS)


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
