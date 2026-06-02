from __future__ import annotations

import math
from dataclasses import dataclass

PROVISIONAL_FORMULA_VERSION = "rv_livermore_sector_rank_provisional_v1"
MIN_RANKABLE_SECTORS = 3


@dataclass(frozen=True)
class SectorRankConstituent:
    stock_code: str
    sector_code: str
    sector_name: str
    pctchange: object
    turn: object
    amplitude: object


@dataclass(frozen=True)
class SectorRankResult:
    ready: bool
    payload: dict[str, object] | None
    rankable_sector_count: int
    excluded_constituent_count: int
    excluded_sector_count: int


@dataclass(frozen=True)
class _SectorAggregate:
    sector_code: str
    sector_name: str
    avg_pctchange: float
    avg_turn: float
    avg_amplitude: float
    constituent_count: int


def compute_sector_rank(
    *,
    as_of_date: str,
    rows: list[SectorRankConstituent],
) -> SectorRankResult:
    grouped: dict[tuple[str, str], list[tuple[float, float, float]]] = {}
    seen_sector_keys: set[tuple[str, str]] = set()
    excluded_constituents = 0

    for row in rows:
        sector_code = row.sector_code.strip()
        sector_name = row.sector_name.strip()
        has_sector = bool(sector_code and sector_name)
        if has_sector:
            seen_sector_keys.add((sector_code, sector_name))
        pctchange = _valid_float(row.pctchange)
        turn = _valid_float(row.turn)
        amplitude = _valid_float(row.amplitude)
        if not has_sector or pctchange is None or turn is None or amplitude is None:
            excluded_constituents += 1
            continue
        grouped.setdefault((sector_code, sector_name), []).append((pctchange, turn, amplitude))

    aggregates = [_aggregate_sector(key, values) for key, values in grouped.items() if values]
    excluded_sectors = len(seen_sector_keys - set(grouped))
    if len(aggregates) < MIN_RANKABLE_SECTORS:
        return SectorRankResult(
            ready=False,
            payload=None,
            rankable_sector_count=len(aggregates),
            excluded_constituent_count=excluded_constituents,
            excluded_sector_count=excluded_sectors,
        )

    score_by_sector = _score_aggregates(aggregates)
    ordered = sorted(
        aggregates,
        key=lambda row: (
            -score_by_sector[(row.sector_code, row.sector_name)],
            -row.avg_pctchange,
            -row.avg_turn,
            row.sector_code,
        ),
    )
    items = [
        {
            "rank": index,
            "sector_code": row.sector_code,
            "sector_name": row.sector_name,
            "score": round(score_by_sector[(row.sector_code, row.sector_name)], 6),
            "avg_pctchange": round(row.avg_pctchange, 6),
            "avg_turn": round(row.avg_turn, 6),
            "avg_amplitude": round(row.avg_amplitude, 6),
            "constituent_count": row.constituent_count,
        }
        for index, row in enumerate(ordered, start=1)
    ]
    return SectorRankResult(
        ready=True,
        payload={
            "as_of_date": as_of_date,
            "formula_version": PROVISIONAL_FORMULA_VERSION,
            "is_provisional": True,
            "sector_count": len(items),
            "excluded_constituent_count": excluded_constituents,
            "excluded_sector_count": excluded_sectors,
            "items": items,
        },
        rankable_sector_count=len(items),
        excluded_constituent_count=excluded_constituents,
        excluded_sector_count=excluded_sectors,
    )


def _aggregate_sector(
    key: tuple[str, str],
    values: list[tuple[float, float, float]],
) -> _SectorAggregate:
    sector_code, sector_name = key
    return _SectorAggregate(
        sector_code=sector_code,
        sector_name=sector_name,
        avg_pctchange=sum(row[0] for row in values) / len(values),
        avg_turn=sum(row[1] for row in values) / len(values),
        avg_amplitude=sum(row[2] for row in values) / len(values),
        constituent_count=len(values),
    )


def _score_aggregates(rows: list[_SectorAggregate]) -> dict[tuple[str, str], float]:
    pctchange_percentiles = _percentiles({(row.sector_code, row.sector_name): row.avg_pctchange for row in rows})
    turn_percentiles = _percentiles({(row.sector_code, row.sector_name): row.avg_turn for row in rows})
    amplitude_percentiles = _percentiles({(row.sector_code, row.sector_name): row.avg_amplitude for row in rows})
    return {
        (row.sector_code, row.sector_name): (
            0.5 * pctchange_percentiles[(row.sector_code, row.sector_name)]
            + 0.3 * turn_percentiles[(row.sector_code, row.sector_name)]
            + 0.2 * amplitude_percentiles[(row.sector_code, row.sector_name)]
        )
        for row in rows
    }


def _percentiles(values_by_key: dict[tuple[str, str], float]) -> dict[tuple[str, str], float]:
    ordered = sorted(values_by_key.items(), key=lambda item: (item[1], item[0]))
    if len(ordered) == 1:
        return {ordered[0][0]: 1.0}

    percentiles: dict[tuple[str, str], float] = {}
    index = 0
    denominator = len(ordered) - 1
    while index < len(ordered):
        value = ordered[index][1]
        end = index
        while end + 1 < len(ordered) and ordered[end + 1][1] == value:
            end += 1
        percentile = ((index + end) / 2) / denominator
        for position in range(index, end + 1):
            percentiles[ordered[position][0]] = percentile
        index = end + 1
    return percentiles


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
