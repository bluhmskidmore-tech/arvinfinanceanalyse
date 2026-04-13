from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
import math
from typing import Any, Iterable, Sequence


@dataclass(slots=True, frozen=True)
class MacroBondCorrelation:
    """单个宏观指标与债券收益率的相关性。"""

    series_id: str
    series_name: str
    target_yield: str
    correlation_3m: float | None
    correlation_6m: float | None
    correlation_1y: float | None
    lead_lag_days: int
    direction: str
    sample_size: int | None = None
    winsorized: bool = False
    zscore_applied: bool = False
    lead_lag_confidence: float | None = None
    effective_observation_span_days: int | None = None


@dataclass(slots=True, frozen=True)
class MacroEnvironmentScore:
    """宏观环境综合评分。"""

    report_date: date
    rate_direction: str
    rate_direction_score: float
    liquidity_score: float
    growth_score: float
    inflation_score: float
    composite_score: float
    signal_description: str
    contributing_factors: list[dict[str, Any]]
    warnings: list[str]


RATE_INDICATORS = {
    "EMM00166466": ("中债国债到期收益率:10年", 1.0),
    "EMM00166462": ("中债国债到期收益率:5年", 0.8),
    "EMM00166458": ("中债国债到期收益率:1年", 0.6),
}
LIQUIDITY_INDICATORS = {
    "EMM00166252": ("SHIBOR:隔夜", 1.0),
    "EMM00166253": ("SHIBOR:1周", 0.8),
    "EMM00166216": ("银行间质押式回购加权利率", 0.9),
}
GROWTH_INDICATORS = {
    "EMM00008445": ("工业增加值:当月同比", 1.0),
    "EMM00619381": ("中国:GDP:现价:当季值", 0.8),
}
INFLATION_INDICATORS = {
    "EMM00072301": ("CPI:当月同比", 1.0),
}

SERIES_NAME_OVERRIDES = {
    **{series_id: series_name for series_id, (series_name, _weight) in RATE_INDICATORS.items()},
    **{series_id: series_name for series_id, (series_name, _weight) in LIQUIDITY_INDICATORS.items()},
    **{series_id: series_name for series_id, (series_name, _weight) in GROWTH_INDICATORS.items()},
    **{series_id: series_name for series_id, (series_name, _weight) in INFLATION_INDICATORS.items()},
}

ZERO_DECIMAL = Decimal("0")
EPSILON = 1e-12


def pearson_correlation(
    values_x: Sequence[float] | Sequence[int],
    values_y: Sequence[float] | Sequence[int],
) -> float | None:
    if len(values_x) != len(values_y) or len(values_x) < 2:
        return None

    x = [float(value) for value in values_x]
    y = [float(value) for value in values_y]
    mean_x = sum(x) / len(x)
    mean_y = sum(y) / len(y)

    covariance = sum((left - mean_x) * (right - mean_y) for left, right in zip(x, y, strict=True))
    variance_x = sum((value - mean_x) ** 2 for value in x)
    variance_y = sum((value - mean_y) ** 2 for value in y)
    if variance_x <= EPSILON or variance_y <= EPSILON:
        return None

    correlation = covariance / ((variance_x ** 0.5) * (variance_y ** 0.5))
    if abs(correlation - 1.0) <= EPSILON:
        return 1.0
    if abs(correlation + 1.0) <= EPSILON:
        return -1.0
    if correlation > 1:
        return 1.0
    if correlation < -1:
        return -1.0
    return correlation


def compute_macro_bond_correlations(
    macro_series: dict[str, list[tuple[date, float]]],
    yield_series: dict[str, list[tuple[date, float]]],
    *,
    lookback_days: int = 365,
    alignment_mode: str = "conservative",
    winsorize_tail_fraction: float | None = None,
) -> list[MacroBondCorrelation]:
    """
    对每个宏观指标 vs 每条收益率曲线关键期限，计算滚动相关系数与领先滞后关系。

    纯 Python 实现，不依赖 numpy。
    """

    validated_tail_fraction = _validate_winsorize_tail_fraction(winsorize_tail_fraction)

    prepared_macro = {
        series_id: _series_to_map(points, lookback_days=lookback_days)
        for series_id, points in macro_series.items()
    }
    prepared_yields = {
        target_name: _series_to_map(points, lookback_days=lookback_days)
        for target_name, points in yield_series.items()
    }

    results: list[MacroBondCorrelation] = []
    for series_id in sorted(prepared_macro):
        macro_map = prepared_macro[series_id]
        if len(macro_map) < 2:
            continue
        series_name = SERIES_NAME_OVERRIDES.get(series_id, series_id)
        for target_name in sorted(prepared_yields):
            target_map = prepared_yields[target_name]
            if len(target_map) < 2:
                continue
            latest_date = _latest_alignment_date(
                macro_map,
                target_map,
                alignment_mode=alignment_mode,
            )
            correlation_3m = _window_correlation(
                macro_map,
                target_map,
                latest_date=latest_date,
                window_days=90,
                alignment_mode=alignment_mode,
                winsorize_tail_fraction=validated_tail_fraction,
            )
            correlation_6m = _window_correlation(
                macro_map,
                target_map,
                latest_date=latest_date,
                window_days=180,
                alignment_mode=alignment_mode,
                winsorize_tail_fraction=validated_tail_fraction,
            )
            correlation_1y = _window_correlation(
                macro_map,
                target_map,
                latest_date=latest_date,
                window_days=365,
                alignment_mode=alignment_mode,
                winsorize_tail_fraction=validated_tail_fraction,
            )
            lead_details = _best_lead_lag_details(
                macro_map,
                target_map,
                alignment_mode=alignment_mode,
                winsorize_tail_fraction=validated_tail_fraction,
            )
            lead_lag_days = int(lead_details["lag_days"])
            best_correlation = lead_details["correlation"]
            raw_sample = lead_details["sample_size"]
            sample_size = int(raw_sample) if raw_sample is not None and int(raw_sample) >= 2 else None
            lc_val = lead_details["confidence"]
            lead_lag_confidence = round(float(lc_val), 6) if lc_val is not None else None
            winsorized = validated_tail_fraction is not None
            zscore_applied = False
            effective_observation_span_days = _alignment_span_days(
                macro_map,
                target_map,
                latest_date=latest_date,
                window_days=365,
                alignment_mode=alignment_mode,
                lag_days=lead_lag_days,
            )
            direction = _direction_from_correlation(
                correlation_1y,
                correlation_6m,
                correlation_3m,
                best_correlation,
            )
            results.append(
                MacroBondCorrelation(
                    series_id=series_id,
                    series_name=series_name,
                    target_yield=target_name,
                    correlation_3m=correlation_3m,
                    correlation_6m=correlation_6m,
                    correlation_1y=correlation_1y,
                    lead_lag_days=lead_lag_days,
                    direction=direction,
                    sample_size=sample_size,
                    winsorized=winsorized,
                    zscore_applied=zscore_applied,
                    lead_lag_confidence=lead_lag_confidence,
                    effective_observation_span_days=effective_observation_span_days,
                )
            )
    return results


def compute_macro_environment_score(
    macro_latest: dict[str, tuple[date, float]],
    macro_history: dict[str, list[tuple[date, float]]],
    *,
    lookback_days: int = 90,
) -> MacroEnvironmentScore:
    warnings: list[str] = []
    contributing_factors: list[dict[str, Any]] = []
    report_date = _resolve_report_date(macro_latest, macro_history)

    rate_direction_score = _weighted_direction_score(
        indicator_config=RATE_INDICATORS,
        macro_history=macro_history,
        report_date=report_date,
        lookback_days=lookback_days,
        warnings=warnings,
        contributing_factors=contributing_factors,
    )
    liquidity_score = _weighted_liquidity_score(
        indicator_config=LIQUIDITY_INDICATORS,
        macro_history=macro_history,
        warnings=warnings,
        contributing_factors=contributing_factors,
    )
    growth_score = _weighted_latest_delta_score(
        indicator_config=GROWTH_INDICATORS,
        macro_history=macro_history,
        warnings=warnings,
        contributing_factors=contributing_factors,
    )
    inflation_score = _weighted_inflation_score(
        indicator_config=INFLATION_INDICATORS,
        macro_latest=macro_latest,
        warnings=warnings,
        contributing_factors=contributing_factors,
    )
    composite_score = (
        0.4 * rate_direction_score
        + 0.3 * liquidity_score
        + 0.2 * growth_score
        + 0.1 * inflation_score
    )
    if rate_direction_score > 0.2:
        rate_direction = "rising"
    elif rate_direction_score < -0.2:
        rate_direction = "falling"
    else:
        rate_direction = "neutral"

    if composite_score > 0.3:
        signal_description = "宏观环境偏紧，利率上行压力，建议缩短久期"
    elif composite_score < -0.3:
        signal_description = "宏观环境偏松，利率下行空间，可适度拉长久期"
    else:
        signal_description = "宏观环境中性，维持当前久期配置"

    return MacroEnvironmentScore(
        report_date=report_date,
        rate_direction=rate_direction,
        rate_direction_score=round(rate_direction_score, 4),
        liquidity_score=round(liquidity_score, 4),
        growth_score=round(growth_score, 4),
        inflation_score=round(inflation_score, 4),
        composite_score=round(composite_score, 4),
        signal_description=signal_description,
        contributing_factors=contributing_factors,
        warnings=warnings,
    )


def estimate_macro_impact_on_portfolio(
    macro_environment: MacroEnvironmentScore,
    portfolio_dv01: Decimal,
    portfolio_cs01: Decimal,
    portfolio_market_value: Decimal,
) -> dict[str, Any]:
    rate_change_bps = Decimal(str(round(macro_environment.rate_direction_score * 30, 4)))
    spread_change_bps = Decimal(str(round(-macro_environment.liquidity_score * 20, 4)))
    rate_pnl_impact = -(portfolio_dv01 * rate_change_bps)
    spread_pnl_impact = -(portfolio_cs01 * spread_change_bps)
    total_estimated_impact = rate_pnl_impact + spread_pnl_impact
    impact_ratio = (
        total_estimated_impact / portfolio_market_value
        if portfolio_market_value != ZERO_DECIMAL
        else ZERO_DECIMAL
    )
    return {
        "estimated_rate_change_bps": rate_change_bps,
        "estimated_spread_widening_bps": spread_change_bps,
        "estimated_rate_pnl_impact": rate_pnl_impact,
        "estimated_spread_pnl_impact": spread_pnl_impact,
        "total_estimated_impact": total_estimated_impact,
        "impact_ratio_to_market_value": impact_ratio,
    }


def _series_to_map(
    points: Iterable[tuple[date, float]],
    *,
    lookback_days: int,
) -> dict[date, float]:
    ordered = sorted(points, key=lambda item: item[0])
    if not ordered:
        return {}
    latest_date = ordered[-1][0]
    start_date = latest_date - timedelta(days=max(lookback_days - 1, 0))
    return {
        point_date: float(value)
        for point_date, value in ordered
        if point_date >= start_date
    }


def _latest_common_date(
    macro_map: dict[date, float],
    target_map: dict[date, float],
) -> date:
    common_dates = sorted(set(macro_map) & set(target_map))
    if common_dates:
        return common_dates[-1]
    return max(max(macro_map), max(target_map))


def _latest_alignment_date(
    macro_map: dict[date, float],
    target_map: dict[date, float],
    *,
    alignment_mode: str,
) -> date:
    if alignment_mode == "market_timing" and target_map:
        return max(target_map)
    return _latest_common_date(macro_map, target_map)


def _alignment_span_days(
    macro_map: dict[date, float],
    target_map: dict[date, float],
    *,
    latest_date: date,
    window_days: int,
    alignment_mode: str,
    lag_days: int,
) -> int | None:
    start_date = latest_date - timedelta(days=max(window_days - 1, 0))
    aligned_pairs = _align_series_pairs(
        macro_map,
        target_map,
        alignment_mode=alignment_mode,
        lag_days=lag_days,
        start_date=start_date,
        end_date=latest_date,
    )
    if len(aligned_pairs) < 2:
        return None
    dates = [pair[0] for pair in aligned_pairs]
    return (max(dates) - min(dates)).days + 1


def _window_correlation(
    macro_map: dict[date, float],
    target_map: dict[date, float],
    *,
    latest_date: date,
    window_days: int,
    alignment_mode: str = "conservative",
    winsorize_tail_fraction: float | None = None,
) -> float | None:
    start_date = latest_date - timedelta(days=max(window_days - 1, 0))
    aligned_pairs = _align_series_pairs(
        macro_map,
        target_map,
        alignment_mode=alignment_mode,
        start_date=start_date,
        end_date=latest_date,
    )
    if len(aligned_pairs) < 2:
        return None
    macro_values = _prepare_series_values(
        [macro_value for _current_date, macro_value, _target_value in aligned_pairs],
        winsorize_tail_fraction=winsorize_tail_fraction,
    )
    target_values = _prepare_series_values(
        [target_value for _current_date, _macro_value, target_value in aligned_pairs],
        winsorize_tail_fraction=winsorize_tail_fraction,
    )
    correlation = pearson_correlation(macro_values, target_values)
    return round(correlation, 6) if correlation is not None else None


def _align_series_pairs(
    macro_map: dict[date, float],
    target_map: dict[date, float],
    *,
    alignment_mode: str,
    lag_days: int = 0,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[tuple[date, float, float]]:
    if alignment_mode not in {"conservative", "market_timing"}:
        raise ValueError(f"Unsupported alignment mode: {alignment_mode}")
    if not macro_map or not target_map:
        return []

    if alignment_mode == "conservative":
        aligned_pairs: list[tuple[date, float, float]] = []
        for macro_date in sorted(macro_map):
            target_date = macro_date + timedelta(days=lag_days)
            if target_date not in target_map:
                continue
            if start_date is not None and macro_date < start_date:
                continue
            if end_date is not None and macro_date > end_date:
                continue
            aligned_pairs.append((macro_date, macro_map[macro_date], target_map[target_date]))
        return aligned_pairs

    ordered_macro_dates = sorted(macro_map)
    macro_index = 0
    last_macro_date: date | None = None
    last_macro_value: float | None = None
    aligned_pairs = []
    for target_date in sorted(target_map):
        if start_date is not None and target_date < start_date:
            continue
        if end_date is not None and target_date > end_date:
            continue
        effective_macro_date = target_date - timedelta(days=lag_days)
        while macro_index < len(ordered_macro_dates) and ordered_macro_dates[macro_index] <= effective_macro_date:
            last_macro_date = ordered_macro_dates[macro_index]
            last_macro_value = macro_map[last_macro_date]
            macro_index += 1
        if last_macro_date is None or last_macro_value is None:
            continue
        aligned_pairs.append((target_date, last_macro_value, target_map[target_date]))
    return aligned_pairs


def _prepare_series_values(
    values: Sequence[float],
    *,
    winsorize_tail_fraction: float | None,
) -> list[float]:
    prepared = [float(value) for value in values]
    if winsorize_tail_fraction is not None and winsorize_tail_fraction > 0:
        prepared = _winsorize_values(prepared, tail_fraction=winsorize_tail_fraction)
    return prepared


def _validate_winsorize_tail_fraction(
    winsorize_tail_fraction: float | None,
) -> float | None:
    if winsorize_tail_fraction is None:
        return None
    tail_fraction = float(winsorize_tail_fraction)
    if not math.isfinite(tail_fraction) or tail_fraction <= 0 or tail_fraction >= 0.5:
        raise ValueError("winsorize_tail_fraction must be finite and satisfy 0 < tail_fraction < 0.5")
    return tail_fraction


def _winsorize_values(
    values: Sequence[float],
    *,
    tail_fraction: float,
) -> list[float]:
    validated_tail_fraction = _validate_winsorize_tail_fraction(tail_fraction)
    if len(values) < 2:
        return [float(value) for value in values]
    ordered = sorted(float(value) for value in values)
    lower_bound = _quantile(ordered, validated_tail_fraction)
    upper_bound = _quantile(ordered, 1 - validated_tail_fraction)
    return [
        min(max(float(value), lower_bound), upper_bound)
        for value in values
    ]


def _quantile(values: Sequence[float], quantile: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return float(values[0])
    bounded_quantile = min(max(float(quantile), 0.0), 1.0)
    position = bounded_quantile * (len(values) - 1)
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(values) - 1)
    weight = position - lower_index
    lower_value = float(values[lower_index])
    upper_value = float(values[upper_index])
    return lower_value + (upper_value - lower_value) * weight


def _best_lead_lag_details(
    macro_map: dict[date, float],
    target_map: dict[date, float],
    *,
    alignment_mode: str = "conservative",
    winsorize_tail_fraction: float | None = None,
    max_lag_days: int = 30,
) -> dict[str, float | int | None]:
    candidates: list[dict[str, float | int]] = []
    best_candidate: dict[str, float | int] | None = None
    best_abs = -1.0
    for lag_days in range(-max_lag_days, max_lag_days + 1):
        aligned_pairs = _align_series_pairs(
            macro_map,
            target_map,
            alignment_mode=alignment_mode,
            lag_days=lag_days,
        )
        if len(aligned_pairs) < 2:
            continue
        macro_values = _prepare_series_values(
            [macro_value for _current_date, macro_value, _target_value in aligned_pairs],
            winsorize_tail_fraction=winsorize_tail_fraction,
        )
        target_values = _prepare_series_values(
            [target_value for _current_date, _macro_value, target_value in aligned_pairs],
            winsorize_tail_fraction=winsorize_tail_fraction,
        )
        correlation = pearson_correlation(macro_values, target_values)
        if correlation is None:
            continue
        candidate = {
            "lag_days": lag_days,
            "correlation": correlation,
            "sample_size": len(aligned_pairs),
        }
        candidates.append(candidate)
        correlation_abs = abs(correlation)
        if correlation_abs > best_abs or (
            abs(correlation_abs - best_abs) <= EPSILON
            and best_candidate is not None
            and abs(lag_days) < abs(int(best_candidate["lag_days"]))
        ):
            best_candidate = candidate
            best_abs = correlation_abs
        elif best_candidate is None:
            best_candidate = candidate
            best_abs = correlation_abs

    if best_candidate is None:
        return {
            "lag_days": 0,
            "correlation": None,
            "sample_size": 0,
            "confidence": None,
        }

    runner_up_abs = max(
        (
            abs(float(candidate["correlation"]))
            for candidate in candidates
            if int(candidate["lag_days"]) != int(best_candidate["lag_days"])
        ),
        default=None,
    )
    confidence = _lead_lag_confidence(
        best_abs=abs(float(best_candidate["correlation"])),
        runner_up_abs=runner_up_abs,
        sample_size=int(best_candidate["sample_size"]),
    )
    return {
        "lag_days": int(best_candidate["lag_days"]),
        "correlation": round(float(best_candidate["correlation"]), 6),
        "sample_size": int(best_candidate["sample_size"]),
        "confidence": confidence,
    }


def _lead_lag_confidence(
    *,
    best_abs: float,
    runner_up_abs: float | None,
    sample_size: int,
) -> float:
    if sample_size < 2 or best_abs <= EPSILON:
        return 0.0
    sample_factor = min(sample_size / 45.0, 1.0)
    gap = best_abs if runner_up_abs is None else max(best_abs - runner_up_abs, 0.0)
    uniqueness_factor = min(gap / 0.15, 1.0)
    confidence = best_abs * sample_factor * (0.5 + 0.5 * uniqueness_factor)
    return round(max(0.0, min(confidence, 1.0)), 6)


def _direction_from_correlation(*candidates: float | None) -> str:
    for candidate in candidates:
        if candidate is None:
            continue
        if candidate >= 0.2:
            return "positive"
        if candidate <= -0.2:
            return "negative"
    return "neutral"


def _resolve_report_date(
    macro_latest: dict[str, tuple[date, float]],
    macro_history: dict[str, list[tuple[date, float]]],
) -> date:
    latest_dates = [value[0] for value in macro_latest.values()]
    if latest_dates:
        return max(latest_dates)
    history_dates = [
        point_date
        for points in macro_history.values()
        for point_date, _value in points
    ]
    if history_dates:
        return max(history_dates)
    return date.today()


def _weighted_direction_score(
    *,
    indicator_config: dict[str, tuple[str, float]],
    macro_history: dict[str, list[tuple[date, float]]],
    report_date: date,
    lookback_days: int,
    warnings: list[str],
    contributing_factors: list[dict[str, Any]],
) -> float:
    return _weighted_score(
        indicator_config=indicator_config,
        scoring_fn=lambda series_id, series_name, weight, points: _score_rate_direction(
            series_id=series_id,
            series_name=series_name,
            weight=weight,
            points=points,
            report_date=report_date,
            lookback_days=lookback_days,
        ),
        macro_history=macro_history,
        warnings=warnings,
        contributing_factors=contributing_factors,
    )


def _weighted_liquidity_score(
    *,
    indicator_config: dict[str, tuple[str, float]],
    macro_history: dict[str, list[tuple[date, float]]],
    warnings: list[str],
    contributing_factors: list[dict[str, Any]],
) -> float:
    return _weighted_score(
        indicator_config=indicator_config,
        scoring_fn=_score_liquidity,
        macro_history=macro_history,
        warnings=warnings,
        contributing_factors=contributing_factors,
    )


def _weighted_latest_delta_score(
    *,
    indicator_config: dict[str, tuple[str, float]],
    macro_history: dict[str, list[tuple[date, float]]],
    warnings: list[str],
    contributing_factors: list[dict[str, Any]],
) -> float:
    return _weighted_score(
        indicator_config=indicator_config,
        scoring_fn=_score_latest_delta,
        macro_history=macro_history,
        warnings=warnings,
        contributing_factors=contributing_factors,
    )


def _weighted_inflation_score(
    *,
    indicator_config: dict[str, tuple[str, float]],
    macro_latest: dict[str, tuple[date, float]],
    warnings: list[str],
    contributing_factors: list[dict[str, Any]],
) -> float:
    total_weight = 0.0
    weighted_score = 0.0
    for series_id, (series_name, weight) in indicator_config.items():
        latest = macro_latest.get(series_id)
        if latest is None:
            warnings.append(f"Inflation indicator missing latest point: {series_name}")
            continue
        latest_date, latest_value = latest
        if latest_value > 3:
            score = 1.0
        elif latest_value < 1:
            score = -1.0
        else:
            score = 0.0
        total_weight += weight
        weighted_score += weight * score
        contributing_factors.append(
            {
                "category": "inflation",
                "series_id": series_id,
                "series_name": series_name,
                "report_date": latest_date.isoformat(),
                "latest_value": latest_value,
                "score": score,
                "weight": weight,
            }
        )
    if total_weight <= EPSILON:
        warnings.append("Inflation score defaulted to 0 due to missing indicators.")
        return 0.0
    return weighted_score / total_weight


def _weighted_score(
    *,
    indicator_config: dict[str, tuple[str, float]],
    scoring_fn,
    macro_history: dict[str, list[tuple[date, float]]],
    warnings: list[str],
    contributing_factors: list[dict[str, Any]],
) -> float:
    total_weight = 0.0
    weighted_score = 0.0
    for series_id, (series_name, weight) in indicator_config.items():
        points = sorted(macro_history.get(series_id, []), key=lambda item: item[0])
        if len(points) < 2:
            warnings.append(f"Indicator history too short: {series_name}")
            continue
        factor = scoring_fn(series_id, series_name, weight, points)
        if factor is None:
            warnings.append(f"Indicator score unavailable: {series_name}")
            continue
        total_weight += weight
        weighted_score += weight * float(factor["score"])
        contributing_factors.append(factor)
    if total_weight <= EPSILON:
        return 0.0
    return weighted_score / total_weight


def _score_rate_direction(
    series_id: str,
    series_name: str,
    weight: float,
    points: list[tuple[date, float]],
    *,
    report_date: date,
    lookback_days: int,
) -> dict[str, Any] | None:
    window_start = report_date - timedelta(days=max(lookback_days - 1, 0))
    window_points = [(point_date, value) for point_date, value in points if point_date >= window_start]
    if len(window_points) < 2:
        return None
    start_date, start_value = window_points[0]
    end_date, end_value = window_points[-1]
    delta = float(end_value - start_value)
    if delta >= 0.20:
        score = 1.0
    elif delta <= -0.20:
        score = -1.0
    else:
        score = 0.0
    return {
        "category": "rate",
        "series_id": series_id,
        "series_name": series_name,
        "window_start": start_date.isoformat(),
        "window_end": end_date.isoformat(),
        "start_value": start_value,
        "latest_value": end_value,
        "delta": delta,
        "score": score,
        "weight": weight,
    }


def _score_liquidity(
    series_id: str,
    series_name: str,
    weight: float,
    points: list[tuple[date, float]],
) -> dict[str, Any] | None:
    values = [float(value) for _point_date, value in points]
    if len(values) < 3:
        return None
    recent_count = min(5, max(1, len(values) // 3))
    baseline = values[:-recent_count]
    recent = values[-recent_count:]
    if len(baseline) < 2:
        return None
    baseline_mean = _mean(baseline)
    recent_mean = _mean(recent)
    baseline_std = _population_std(baseline)
    upper_bound = baseline_mean + baseline_std
    lower_bound = baseline_mean - baseline_std
    if recent_mean > upper_bound:
        score = -1.0
    elif recent_mean < lower_bound:
        score = 1.0
    else:
        score = 0.0
    return {
        "category": "liquidity",
        "series_id": series_id,
        "series_name": series_name,
        "baseline_mean": baseline_mean,
        "baseline_std": baseline_std,
        "recent_mean": recent_mean,
        "score": score,
        "weight": weight,
    }


def _score_latest_delta(
    series_id: str,
    series_name: str,
    weight: float,
    points: list[tuple[date, float]],
) -> dict[str, Any] | None:
    previous_date, previous_value = points[-2]
    latest_date, latest_value = points[-1]
    delta = float(latest_value - previous_value)
    if delta > 0:
        score = 1.0
    elif delta < 0:
        score = -1.0
    else:
        score = 0.0
    return {
        "category": "growth",
        "series_id": series_id,
        "series_name": series_name,
        "previous_date": previous_date.isoformat(),
        "report_date": latest_date.isoformat(),
        "previous_value": previous_value,
        "latest_value": latest_value,
        "delta": delta,
        "score": score,
        "weight": weight,
    }


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def _population_std(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean_value = _mean(values)
    variance = sum((value - mean_value) ** 2 for value in values) / len(values)
    return variance ** 0.5
