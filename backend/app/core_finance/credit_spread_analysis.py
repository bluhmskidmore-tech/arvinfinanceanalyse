from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from statistics import median
from typing import Any

from backend.app.core_finance.bond_analytics.common import (
    build_curve_points,
    build_full_curve,
    interpolate_rate,
    safe_decimal,
    tenor_to_years,
)
from backend.app.core_finance.decimal_utils import to_decimal_strict

ZERO = Decimal("0")
Q8 = Decimal("0.00000001")
# 历史分位的最小观测数披露阈值。与 macro/credit_spread_percentile.py 的
# MARKET_HISTORY_LT_60D 及 crisis_score 的 min_periods=60 同一口径：样本不足
# 时分位数照常出数，由服务层追加告警，不在计算端压制。
MIN_HISTORY_OBSERVATIONS = 60


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

    current_spread_bps: Decimal | None
    percentile_1y: Decimal | None
    percentile_3y: Decimal | None
    median_1y: Decimal | None
    median_3y: Decimal | None
    min_1y: Decimal | None
    max_1y: Decimal | None


def compute_bond_spreads(
    bond_rows: list[dict[str, Any]],
    treasury_curve: dict[str, Any],
) -> list[BondSpreadRow]:
    """
    对每只信用债（asset_class_std == "credit"）计算信用利差。

    `fact_formal_bond_analytics_daily.ytm` 当前以小数存储，国债曲线以百分比点位存储；
    这里统一转换为百分比后，再换算为 bps。
    """

    if not bond_rows or not treasury_curve:
        return []

    normalized_curve = _finite_curve_rates(treasury_curve)
    full_curve = build_full_curve(normalized_curve)
    if not full_curve:
        return []

    candidate_rows: list[tuple[dict[str, Any], Decimal]] = []
    for row in bond_rows:
        if (
            str(row.get("asset_class_std") or "").strip() != "credit"
            or not str(row.get("tenor_bucket") or "").strip()
            or row.get("ytm") is None
            or safe_decimal(row.get("market_value")) == ZERO
        ):
            continue
        normalized_ytm_pct = _normalize_ytm_to_pct(row.get("ytm"))
        if normalized_ytm_pct is None:
            continue
        candidate_rows.append((row, normalized_ytm_pct))
    total_credit_mv = sum((safe_decimal(row.get("market_value")) for row, _ in candidate_rows), ZERO)
    if total_credit_mv == ZERO:
        return []

    spread_rows: list[BondSpreadRow] = []
    for row, ytm_pct in candidate_rows:
        tenor_bucket = str(row.get("tenor_bucket") or "").strip()
        benchmark_yield = _resolve_actual_maturity_benchmark_yield(
            normalized_curve,
            row.get("years_to_maturity"),
        )
        if benchmark_yield is None:
            benchmark_yield = _resolve_benchmark_yield(full_curve, tenor_bucket)
        market_value = safe_decimal(row.get("market_value"))
        # Legacy in-memory inputs may omit face value; an observed zero is valid.
        face_value = market_value if row.get("face_value") is None else safe_decimal(row["face_value"])
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
                spread_dv01=_q8(face_value * spread_duration / Decimal("10000")),
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
    current_avg_spread: Decimal | None,
    historical_spreads: list[tuple[date, Decimal]],
) -> SpreadHistoricalContext:
    """给定当前加权平均利差与历史序列，计算近 1 年 / 3 年分位。"""

    if not historical_spreads:
        return SpreadHistoricalContext(
            current_spread_bps=_q8(current_avg_spread) if current_avg_spread is not None else None,
            percentile_1y=None,
            percentile_3y=None,
            median_1y=None,
            median_3y=None,
            min_1y=None,
            max_1y=None,
        )

    values_1y, values_3y = _history_windows(historical_spreads)

    return SpreadHistoricalContext(
        current_spread_bps=_q8(current_avg_spread) if current_avg_spread is not None else None,
        percentile_1y=_percentile(current_avg_spread, values_1y) if current_avg_spread is not None else None,
        percentile_3y=_percentile(current_avg_spread, values_3y) if current_avg_spread is not None else None,
        median_1y=_median(values_1y),
        median_3y=_median(values_3y),
        min_1y=min(values_1y) if values_1y else None,
        max_1y=max(values_1y) if values_1y else None,
    )


def summarize_spread_coverage(
    bond_rows: list[dict[str, Any]],
    spread_rows: list[BondSpreadRow],
) -> dict[str, Any]:
    """信用持仓规模独立于可计算利差样本；YTM 缺失和无效按同一校验披露。"""
    credit_rows = [row for row in bond_rows if str(row.get("asset_class_std") or "").strip() == "credit"]
    missing_ytm_rows = [row for row in credit_rows if _normalize_ytm_to_pct(row.get("ytm")) is None]
    if not credit_rows:
        coverage_status = "empty"
    elif not spread_rows:
        coverage_status = "unavailable"
    elif len(spread_rows) < len(credit_rows):
        coverage_status = "partial"
    else:
        coverage_status = "complete"
    return {
        "credit_bond_count": len(credit_rows),
        "total_credit_market_value": _q8(sum((safe_decimal(row.get("market_value")) for row in credit_rows), ZERO)),
        "spread_bond_count": len(spread_rows),
        "spread_market_value": _q8(sum((row.market_value for row in spread_rows), ZERO)),
        "missing_ytm_count": len(missing_ytm_rows),
        "missing_ytm_market_value": _q8(sum((safe_decimal(row.get("market_value")) for row in missing_ytm_rows), ZERO)),
        "spread_coverage_status": coverage_status,
    }


def spread_history_observation_counts(
    historical_spreads: list[tuple[date, Decimal]],
) -> tuple[int, int]:
    """近 1 年 / 3 年窗口内的有效观测数（与 compute_spread_historical_context 同一窗口与剔除规则）。"""

    if not historical_spreads:
        return 0, 0
    values_1y, values_3y = _history_windows(historical_spreads)
    return len(values_1y), len(values_3y)


def curve_has_usable_tenors(treasury_curve: dict[str, Any]) -> bool:
    """曲线是否含至少一个收益率有效且可识别期限的节点。

    全部为未知期限标签时 build_full_curve 返回空，compute_bond_spreads 随之 fail-closed
    返回空列表；服务层用本函数把这种"曲线在但不可用"与"无信用债持仓"区分开。
    """

    if not treasury_curve:
        return False
    normalized = _finite_curve_rates(treasury_curve)
    return bool(build_curve_points(normalized))


def _finite_curve_rates(treasury_curve: dict[str, Any]) -> dict[str, Decimal]:
    """剔除缺失、非法和非有限收益率，保留真实零值与负利率。"""

    normalized: dict[str, Decimal] = {}
    for key, value in treasury_curve.items():
        try:
            normalized[str(key)] = to_decimal_strict(value)
        except (InvalidOperation, TypeError, ValueError):
            continue
    return normalized


def _history_windows(
    historical_spreads: list[tuple[date, Decimal]],
) -> tuple[list[Decimal], list[Decimal]]:
    anchor_date = max(point_date for point_date, _value in historical_spreads)
    values_1y = _window_values(historical_spreads, anchor_date=anchor_date, days=365)
    values_3y = _window_values(historical_spreads, anchor_date=anchor_date, days=365 * 3)
    return values_1y, values_3y


def _resolve_benchmark_yield(curve: dict[str, Decimal], tenor_bucket: str) -> Decimal:
    benchmark = curve.get(tenor_bucket)
    if benchmark is not None:
        return safe_decimal(benchmark)
    points = build_curve_points(curve)
    return interpolate_rate(points, tenor_to_years(tenor_bucket))


def _resolve_actual_maturity_benchmark_yield(
    curve: dict[str, Decimal],
    years_to_maturity: Any,
) -> Decimal | None:
    target_years = safe_decimal(years_to_maturity)
    if target_years <= ZERO:
        return None

    points = build_curve_points(curve)
    if not points:
        return None
    target = float(target_years)
    if target <= points[0][0]:
        return points[0][1]
    if target >= points[-1][0]:
        return points[-1][1]

    for (left_years, left_rate), (right_years, right_rate) in zip(
        points,
        points[1:],
        strict=False,
    ):
        if target <= right_years:
            interval = Decimal(str(right_years - left_years))
            elapsed = Decimal(str(target - left_years))
            return left_rate + (right_rate - left_rate) * elapsed / interval
    return points[-1][1]


def _normalize_ytm_to_pct(value: Any) -> Decimal | None:
    """`fact_formal_bond_analytics_daily.ytm` 为小数口径（0.0182 = 1.82%），显式 ×100。

    |ytm| > 0.2（即年收益率绝对值 > 20%）视为脏数据返回 None、调用方跳过该券。
    此前的 `<1 则 ×100` 启发式在百分数误存时会输出千 bp 级错误利差
    （2026-07-19 审计固收 H-1）。
    """
    try:
        ytm = to_decimal_strict(value)
    except (InvalidOperation, TypeError, ValueError):
        return None
    if ytm == ZERO:
        return ZERO
    if abs(ytm) > Decimal("0.2"):
        return None
    return ytm * Decimal("100")


def _window_values(
    historical_spreads: list[tuple[date, Decimal]],
    *,
    anchor_date: date,
    days: int,
) -> list[Decimal]:
    cutoff = anchor_date - timedelta(days=days)
    values: list[Decimal] = []
    for point_date, value in historical_spreads:
        if point_date < cutoff:
            continue
        try:
            values.append(to_decimal_strict(value))
        except (InvalidOperation, TypeError, ValueError):
            continue
    return values


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
