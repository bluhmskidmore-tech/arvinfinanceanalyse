from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from statistics import median
from typing import Any

from backend.app.core_finance.bond_analytics.common import (
    build_curve_points,
    build_full_curve,
    interpolate_rate,
    safe_decimal,
    tenor_to_years,
)

ZERO = Decimal("0")
Q8 = Decimal("0.00000001")


@dataclass(slots=True, frozen=True)
class BondSpreadRow:
    """单只债券的信用利差计算结果。"""

    instrument_code: str
    instrument_name: str
    rating: str
    tenor_bucket: str
    ytm: Decimal
    benchmark_yield: Decimal
    credit_spread: Decimal
    spread_duration: Decimal
    spread_dv01: Decimal
    market_value: Decimal
    weight: Decimal


@dataclass(slots=True, frozen=True)
class SpreadTermStructurePoint:
    """利差期限结构上的一个点。"""

    tenor_bucket: str
    avg_spread_bps: Decimal
    min_spread_bps: Decimal
    max_spread_bps: Decimal
    bond_count: int
    total_market_value: Decimal


@dataclass(slots=True, frozen=True)
class SpreadHistoricalContext:
    """当前利差在历史中的分位数。"""

    current_spread_bps: Decimal
    percentile_1y: Decimal | None
    percentile_3y: Decimal | None
    median_1y: Decimal | None
    median_3y: Decimal | None
    min_1y: Decimal | None
    max_1y: Decimal | None


def compute_bond_spreads(
    bond_rows: list[dict[str, Any]],
    treasury_curve: dict[str, Decimal],
) -> list[BondSpreadRow]:
    """
    对每只信用债（asset_class_std == "credit"）计算信用利差。

    `fact_formal_bond_analytics_daily.ytm` 当前以小数存储，国债曲线以百分比点位存储；
    这里统一转换为百分比后，再换算为 bps。
    """

    if not bond_rows or not treasury_curve:
        return []

    full_curve = build_full_curve({str(key): safe_decimal(value) for key, value in treasury_curve.items()})
    if not full_curve:
        return []

    candidate_rows = [
        row
        for row in bond_rows
        if str(row.get("asset_class_std") or "").strip() == "credit"
        and str(row.get("tenor_bucket") or "").strip()
        and row.get("ytm") is not None
        and safe_decimal(row.get("market_value")) != ZERO
    ]
    total_credit_mv = sum((safe_decimal(row.get("market_value")) for row in candidate_rows), ZERO)
    if total_credit_mv == ZERO:
        return []

    spread_rows: list[BondSpreadRow] = []
    for row in candidate_rows:
        tenor_bucket = str(row.get("tenor_bucket") or "").strip()
        benchmark_yield = _resolve_benchmark_yield(full_curve, tenor_bucket)
        ytm_pct = _normalize_ytm_to_pct(row.get("ytm"))
        market_value = safe_decimal(row.get("market_value"))
        spread_duration = safe_decimal(row.get("modified_duration"))
        credit_spread = (ytm_pct - benchmark_yield) * Decimal("100")
        spread_rows.append(
            BondSpreadRow(
                instrument_code=str(row.get("instrument_code") or ""),
                instrument_name=str(row.get("instrument_name") or ""),
                rating=str(row.get("rating") or ""),
                tenor_bucket=tenor_bucket,
                ytm=_q8(ytm_pct),
                benchmark_yield=_q8(benchmark_yield),
                credit_spread=_q8(credit_spread),
                spread_duration=_q8(spread_duration),
                spread_dv01=_q8(market_value * spread_duration / Decimal("10000")),
                market_value=_q8(market_value),
                weight=_q8(market_value / total_credit_mv),
            )
        )
    return spread_rows


def build_spread_term_structure(
    spread_rows: list[BondSpreadRow],
) -> list[SpreadTermStructurePoint]:
    """按 tenor_bucket 聚合信用利差期限结构。"""

    grouped: dict[str, list[BondSpreadRow]] = {}
    for row in spread_rows:
        grouped.setdefault(row.tenor_bucket, []).append(row)

    points: list[SpreadTermStructurePoint] = []
    for tenor_bucket, rows in grouped.items():
        total_market_value = sum((row.market_value for row in rows), ZERO)
        if total_market_value == ZERO:
            avg_spread = ZERO
        else:
            avg_spread = sum((row.credit_spread * row.market_value for row in rows), ZERO) / total_market_value
        spreads = [row.credit_spread for row in rows]
        points.append(
            SpreadTermStructurePoint(
                tenor_bucket=tenor_bucket,
                avg_spread_bps=_q8(avg_spread),
                min_spread_bps=min(spreads) if spreads else ZERO,
                max_spread_bps=max(spreads) if spreads else ZERO,
                bond_count=len(rows),
                total_market_value=_q8(total_market_value),
            )
        )
    return sorted(points, key=lambda point: tenor_to_years(point.tenor_bucket))


def compute_spread_historical_context(
    current_avg_spread: Decimal,
    historical_spreads: list[tuple[date, Decimal]],
) -> SpreadHistoricalContext:
    """给定当前加权平均利差与历史序列，计算近 1 年 / 3 年分位。"""

    if not historical_spreads:
        return SpreadHistoricalContext(
            current_spread_bps=_q8(current_avg_spread),
            percentile_1y=None,
            percentile_3y=None,
            median_1y=None,
            median_3y=None,
            min_1y=None,
            max_1y=None,
        )

    anchor_date = max(point_date for point_date, _value in historical_spreads)
    values_1y = _window_values(historical_spreads, anchor_date=anchor_date, days=365)
    values_3y = _window_values(historical_spreads, anchor_date=anchor_date, days=365 * 3)

    return SpreadHistoricalContext(
        current_spread_bps=_q8(current_avg_spread),
        percentile_1y=_percentile(current_avg_spread, values_1y),
        percentile_3y=_percentile(current_avg_spread, values_3y),
        median_1y=_median(values_1y),
        median_3y=_median(values_3y),
        min_1y=min(values_1y) if values_1y else None,
        max_1y=max(values_1y) if values_1y else None,
    )


def _resolve_benchmark_yield(curve: dict[str, Decimal], tenor_bucket: str) -> Decimal:
    benchmark = curve.get(tenor_bucket)
    if benchmark is not None:
        return safe_decimal(benchmark)
    points = build_curve_points(curve)
    return interpolate_rate(points, tenor_to_years(tenor_bucket))


def _normalize_ytm_to_pct(value: Any) -> Decimal:
    ytm = safe_decimal(value)
    if ytm == ZERO:
        return ZERO
    return ytm * Decimal("100") if abs(ytm) < Decimal("1") else ytm


def _window_values(
    historical_spreads: list[tuple[date, Decimal]],
    *,
    anchor_date: date,
    days: int,
) -> list[Decimal]:
    cutoff = anchor_date - timedelta(days=days)
    return [safe_decimal(value) for point_date, value in historical_spreads if point_date >= cutoff]


def _percentile(current_value: Decimal, values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    count = sum(1 for value in values if value <= current_value)
    return _q8(Decimal(count) / Decimal(len(values)) * Decimal("100"))


def _median(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    return safe_decimal(median(values))


def _q8(value: Decimal) -> Decimal:
    return safe_decimal(value).quantize(Q8, rounding=ROUND_HALF_UP)
