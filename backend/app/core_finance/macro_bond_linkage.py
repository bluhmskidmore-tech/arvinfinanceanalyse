from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Literal

ResearchViewStance = Literal["bullish", "neutral", "bearish", "conflicted"]
ResearchViewConfidence = Literal["high", "medium", "low"]
ResearchViewStatus = Literal["ready", "pending_signal"]
TransmissionAxisKey = Literal[
    "global_rates",
    "liquidity",
    "equity_bond_spread",
    "commodities_inflation",
    "mega_cap_equities",
]
TransmissionAxisStance = Literal["supportive", "neutral", "restrictive", "conflicted"]
TransmissionAxisStatus = Literal["ready", "pending_signal"]


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


@dataclass(slots=True, frozen=True)
class MacroBondResearchViewResult:
    key: Literal["duration", "curve", "credit", "instrument"]
    stance: ResearchViewStance
    confidence: ResearchViewConfidence
    summary: str
    affected_targets: list[str]
    evidence: list[str]
    status: ResearchViewStatus = "ready"


@dataclass(slots=True, frozen=True)
class MacroBondTransmissionAxisResult:
    axis_key: TransmissionAxisKey
    status: TransmissionAxisStatus
    stance: TransmissionAxisStance
    summary: str
    impacted_views: list[str]
    required_series_ids: list[str]
    warnings: list[str]


@dataclass(slots=True, frozen=True)
class EquityBondSpreadSignal:
    trade_date: date
    index_code: str
    index_close: float
    index_pct_change: float | None
    pe: float
    earnings_yield_pct: float
    bond_yield_pct: float
    spread_pct: float


@dataclass(slots=True, frozen=True)
class MegaCapEquitySignal:
    weight_trade_date: date
    index_code: str
    top10_weight_sum: float
    top5_weight_sum: float
    leading_constituents: list[str]
    index_pct_change: float | None


@dataclass(slots=True, frozen=True)
class EquityBondSpreadRule:
    stance: TransmissionAxisStance
    spread_min: float | None = None
    spread_max: float | None = None
    index_pct_change_min: float | None = None
    index_pct_change_max: float | None = None
    summary: str = ""


@dataclass(slots=True, frozen=True)
class MegaCapEquityRule:
    stance: TransmissionAxisStance
    concentration_min: float | None = None
    concentration_max: float | None = None
    index_pct_change_min: float | None = None
    index_pct_change_max: float | None = None
    summary: str = ""


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
ENVIRONMENT_SCORE_METHOD = "robust_environment_score_v1"
ENVIRONMENT_WINSORIZE_TAIL_FRACTION = 0.1
ENVIRONMENT_DISPERSION_FLOOR = 0.05

_DEFAULT_LOOKBACK_DAYS = 365
_SHORT_LOOKBACK_DAYS = 90
_WINDOW_3M_DAYS = 90
_WINDOW_6M_DAYS = 180
_WINDOW_1Y_DAYS = 365
_MAX_LEAD_LAG_DAYS = 30

EQUITY_BOND_SPREAD_RULES: tuple[EquityBondSpreadRule, ...] = (
    EquityBondSpreadRule(
        stance="restrictive",
        spread_min=4.0,
        index_pct_change_min=0.25,
        summary="Equity-bond spread remains wide and equities are rising, which restrains bond risk appetite.",
    ),
    EquityBondSpreadRule(
        stance="conflicted",
        spread_min=4.0,
        index_pct_change_max=-0.25,
        summary="Equity-bond spread is wide, but equities are falling, leaving the cross-asset message conflicted.",
    ),
    EquityBondSpreadRule(
        stance="supportive",
        spread_max=2.75,
        summary="Equity-bond spread has compressed enough to support a more constructive bond view.",
    ),
)

MEGA_CAP_EQUITY_RULES: tuple[MegaCapEquityRule, ...] = (
    MegaCapEquityRule(
        stance="restrictive",
        concentration_min=22.0,
        index_pct_change_min=0.5,
        summary="Mega-cap concentration is high and leadership is rising, which leans against adding bond beta aggressively.",
    ),
    MegaCapEquityRule(
        stance="supportive",
        concentration_min=22.0,
        index_pct_change_max=-0.5,
        summary="Mega-cap concentration is high but leadership is fading, which supports a more defensive equity backdrop for bonds.",
    ),
)


def build_macro_bond_research_output(
    macro_environment: MacroEnvironmentScore,
    correlations: Sequence[MacroBondCorrelation],
    *,
    equity_bond_spread_signal: EquityBondSpreadSignal | None = None,
    mega_cap_equity_signal: MegaCapEquitySignal | None = None,
) -> tuple[list[MacroBondResearchViewResult], list[MacroBondTransmissionAxisResult]]:
    ranked_correlations = sorted(correlations, key=_correlation_rank, reverse=True)
    axes = [
        _build_global_rates_axis(macro_environment),
        _build_liquidity_axis(macro_environment),
        _build_equity_bond_spread_axis(equity_bond_spread_signal),
        _build_commodities_inflation_axis(macro_environment),
        _build_mega_cap_equities_axis(mega_cap_equity_signal),
    ]
    axis_map = {axis.axis_key: axis for axis in axes}
    views = [
        _build_duration_view(macro_environment, axis_map, ranked_correlations),
        _build_curve_view(macro_environment, axis_map, ranked_correlations),
        _build_credit_view(macro_environment, axis_map, ranked_correlations),
        _build_instrument_view(macro_environment, axis_map, ranked_correlations),
    ]
    return views, axes


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
    lookback_days: int = _DEFAULT_LOOKBACK_DAYS,
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
            corr_3m, corr_6m, corr_1y = _compute_correlations(
                macro_map,
                target_map,
                latest_date=latest_date,
                alignment_mode=alignment_mode,
                winsorize_tail_fraction=validated_tail_fraction,
            )
            lead_lag_days, best_correlation, sample_size, lead_lag_confidence = _compute_lead_lag(
                macro_map,
                target_map,
                alignment_mode=alignment_mode,
                winsorize_tail_fraction=validated_tail_fraction,
            )
            effective_observation_span_days = _alignment_span_days(
                macro_map,
                target_map,
                latest_date=latest_date,
                window_days=_WINDOW_1Y_DAYS,
                alignment_mode=alignment_mode,
                lag_days=lead_lag_days,
            )
            direction = _direction_from_correlation(corr_1y, corr_6m, corr_3m, best_correlation)
            results.append(
                MacroBondCorrelation(
                    series_id=series_id,
                    series_name=series_name,
                    target_yield=target_name,
                    correlation_3m=corr_3m,
                    correlation_6m=corr_6m,
                    correlation_1y=corr_1y,
                    lead_lag_days=lead_lag_days,
                    direction=direction,
                    sample_size=sample_size,
                    winsorized=validated_tail_fraction is not None,
                    zscore_applied=False,
                    lead_lag_confidence=lead_lag_confidence,
                    effective_observation_span_days=effective_observation_span_days,
                )
            )
    return results


def _compute_correlations(
    macro_map: dict[date, float],
    target_map: dict[date, float],
    *,
    latest_date: date,
    alignment_mode: str,
    winsorize_tail_fraction: float | None,
) -> tuple[float | None, float | None, float | None]:
    """Return (corr_3m, corr_6m, corr_1y) for a macro/yield pair."""
    corr_3m = _window_correlation(
        macro_map=macro_map,
        target_map=target_map,
        latest_date=latest_date,
        alignment_mode=alignment_mode,
        winsorize_tail_fraction=winsorize_tail_fraction,
        window_days=_WINDOW_3M_DAYS,
    )
    corr_6m = _window_correlation(
        macro_map=macro_map,
        target_map=target_map,
        latest_date=latest_date,
        alignment_mode=alignment_mode,
        winsorize_tail_fraction=winsorize_tail_fraction,
        window_days=_WINDOW_6M_DAYS,
    )
    corr_1y = _window_correlation(
        macro_map=macro_map,
        target_map=target_map,
        latest_date=latest_date,
        alignment_mode=alignment_mode,
        winsorize_tail_fraction=winsorize_tail_fraction,
        window_days=_WINDOW_1Y_DAYS,
    )
    return corr_3m, corr_6m, corr_1y


def _compute_lead_lag(
    macro_map: dict[date, float],
    target_map: dict[date, float],
    *,
    alignment_mode: str,
    winsorize_tail_fraction: float | None,
) -> tuple[int, float | None, int | None, float | None]:
    """Return (lead_lag_days, best_correlation, sample_size, lead_lag_confidence)."""
    lead_details = _best_lead_lag_details(
        macro_map,
        target_map,
        alignment_mode=alignment_mode,
        winsorize_tail_fraction=winsorize_tail_fraction,
    )
    lag_value = lead_details["lag_days"]
    lead_lag_days = int(lag_value) if lag_value is not None else 0
    raw_best_correlation = lead_details["correlation"]
    best_correlation = float(raw_best_correlation) if raw_best_correlation is not None else None
    raw_sample = lead_details["sample_size"]
    sample_size = int(raw_sample) if raw_sample is not None and raw_sample >= 2 else None
    lc_val = lead_details["confidence"]
    lead_lag_confidence = round(float(lc_val), 6) if lc_val is not None else None
    return lead_lag_days, best_correlation, sample_size, lead_lag_confidence


def compute_macro_environment_score(
    macro_latest: dict[str, tuple[date, float]],
    macro_history: dict[str, list[tuple[date, float]]],
    *,
    lookback_days: int = _SHORT_LOOKBACK_DAYS,
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
    if validated_tail_fraction is None:
        raise ValueError("winsorize_tail_fraction must be provided")
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
                "scoring_method": ENVIRONMENT_SCORE_METHOD,
                "observation_count": 1,
                "winsorized": False,
                "normalized_signal": round(float(latest_value) - 2.0, 6),
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
    values = [float(value) for _point_date, value in window_points]
    winsorized_values, winsorized = _maybe_winsorize_environment_values(values)
    start_date, start_value = window_points[0]
    end_date, _end_value = window_points[-1]
    start_metric = winsorized_values[0]
    latest_metric = winsorized_values[-1]
    delta = float(latest_metric - start_metric)
    normalized_signal = _normalize_signal(
        delta,
        dispersion=max(_population_std(winsorized_values), ENVIRONMENT_DISPERSION_FLOOR),
    )
    score = _bounded_score(normalized_signal)
    return {
        "category": "rate",
        "series_id": series_id,
        "series_name": series_name,
        "window_start": start_date.isoformat(),
        "window_end": end_date.isoformat(),
        "start_value": start_metric,
        "latest_value": latest_metric,
        "delta": delta,
        "score": score,
        "weight": weight,
        "scoring_method": ENVIRONMENT_SCORE_METHOD,
        "observation_count": len(window_points),
        "winsorized": winsorized,
        "normalized_signal": round(normalized_signal, 6),
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
    winsorized_values, winsorized = _maybe_winsorize_environment_values(values)
    recent_count = min(5, max(1, len(values) // 3))
    baseline = winsorized_values[:-recent_count]
    recent = winsorized_values[-recent_count:]
    if len(baseline) < 2:
        return None
    baseline_mean = _mean(baseline)
    recent_mean = _mean(recent)
    baseline_std = max(_population_std(baseline), ENVIRONMENT_DISPERSION_FLOOR)
    normalized_signal = _normalize_signal(
        recent_mean - baseline_mean,
        dispersion=baseline_std,
    )
    score = -_bounded_score(normalized_signal)
    return {
        "category": "liquidity",
        "series_id": series_id,
        "series_name": series_name,
        "baseline_mean": baseline_mean,
        "baseline_std": baseline_std,
        "recent_mean": recent_mean,
        "score": score,
        "weight": weight,
        "scoring_method": ENVIRONMENT_SCORE_METHOD,
        "observation_count": len(points),
        "winsorized": winsorized,
        "normalized_signal": round(normalized_signal, 6),
    }


def _score_latest_delta(
    series_id: str,
    series_name: str,
    weight: float,
    points: list[tuple[date, float]],
) -> dict[str, Any] | None:
    values = [float(value) for _point_date, value in points]
    winsorized_values, winsorized = _maybe_winsorize_environment_values(values)
    previous_date, _previous_value = points[-2]
    latest_date, _latest_value = points[-1]
    previous_metric = winsorized_values[-2]
    latest_metric = winsorized_values[-1]
    delta = float(latest_metric - previous_metric)
    delta_history = [
        winsorized_values[index] - winsorized_values[index - 1]
        for index in range(1, len(winsorized_values))
    ]
    dispersion = max(
        _population_std(delta_history) if len(delta_history) > 1 else 0.0,
        ENVIRONMENT_DISPERSION_FLOOR,
    )
    normalized_signal = _normalize_signal(delta, dispersion=dispersion)
    score = _bounded_score(normalized_signal)
    return {
        "category": "growth",
        "series_id": series_id,
        "series_name": series_name,
        "previous_date": previous_date.isoformat(),
        "report_date": latest_date.isoformat(),
        "previous_value": previous_metric,
        "latest_value": latest_metric,
        "delta": delta,
        "score": score,
        "weight": weight,
        "scoring_method": ENVIRONMENT_SCORE_METHOD,
        "observation_count": len(points),
        "winsorized": winsorized,
        "normalized_signal": round(normalized_signal, 6),
    }


def _maybe_winsorize_environment_values(values: Sequence[float]) -> tuple[list[float], bool]:
    prepared = [float(value) for value in values]
    if len(prepared) < 4:
        return prepared, False
    return _winsorize_values(
        prepared,
        tail_fraction=ENVIRONMENT_WINSORIZE_TAIL_FRACTION,
    ), True


def _normalize_signal(delta: float, *, dispersion: float) -> float:
    if abs(delta) <= EPSILON:
        return 0.0
    return delta / max(float(dispersion), ENVIRONMENT_DISPERSION_FLOOR)


def _bounded_score(signal: float) -> float:
    if abs(signal) <= EPSILON:
        return 0.0
    return round(math.tanh(signal / 2.0), 6)


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def _population_std(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean_value = _mean(values)
    variance = sum((value - mean_value) ** 2 for value in values) / len(values)
    return variance ** 0.5


def _build_global_rates_axis(
    macro_environment: MacroEnvironmentScore,
) -> MacroBondTransmissionAxisResult:
    stance = _axis_stance_from_score(macro_environment.rate_direction_score, reverse=True)
    if stance == "supportive":
        summary = "Rate direction signals are easing and support adding duration risk."
    elif stance == "restrictive":
        summary = "Rate direction signals are tightening and argue for tighter duration risk budgets."
    else:
        summary = "Rate direction is mixed and does not justify a strong duration call."
    return MacroBondTransmissionAxisResult(
        axis_key="global_rates",
        status="ready",
        stance=stance,
        summary=summary,
        impacted_views=["duration", "curve", "instrument"],
        required_series_ids=list(RATE_INDICATORS),
        warnings=[],
    )


def _build_liquidity_axis(
    macro_environment: MacroEnvironmentScore,
) -> MacroBondTransmissionAxisResult:
    stance = _axis_stance_from_score(macro_environment.liquidity_score)
    if stance == "supportive":
        summary = "Funding conditions are supportive and favor rates, NCD carry, and high-grade credit."
    elif stance == "restrictive":
        summary = "Funding conditions are restrictive and argue against extending risk through NCD or credit."
    else:
        summary = "Liquidity conditions are balanced and warrant neutral implementation."
    return MacroBondTransmissionAxisResult(
        axis_key="liquidity",
        status="ready",
        stance=stance,
        summary=summary,
        impacted_views=["duration", "curve", "credit", "instrument"],
        required_series_ids=list(LIQUIDITY_INDICATORS),
        warnings=[],
    )


def _build_commodities_inflation_axis(
    macro_environment: MacroEnvironmentScore,
) -> MacroBondTransmissionAxisResult:
    inflation_stance = _axis_stance_from_score(macro_environment.inflation_score)
    growth_stance = _axis_stance_from_score(macro_environment.growth_score, neutral_threshold=0.2)
    stance = _merge_axis_stances(inflation_stance, growth_stance)
    if stance == "supportive":
        summary = "Inflation pressure is subdued enough to support rates and high-grade spread carry."
    elif stance == "restrictive":
        summary = "Inflation and growth pressure argue against aggressive duration or spread compression calls."
    elif stance == "conflicted":
        summary = "Growth and inflation signals conflict, so commodity-linked inflation pressure is inconclusive."
    else:
        summary = "Commodity and inflation signals are neutral for current bond research views."
    return MacroBondTransmissionAxisResult(
        axis_key="commodities_inflation",
        status="ready",
        stance=stance,
        summary=summary,
        impacted_views=["duration", "credit", "instrument"],
        required_series_ids=list(INFLATION_INDICATORS) + list(GROWTH_INDICATORS),
        warnings=[],
    )


def _build_equity_bond_spread_axis(
    signal: EquityBondSpreadSignal | None,
) -> MacroBondTransmissionAxisResult:
    if signal is None:
        return _build_pending_axis(
            axis_key="equity_bond_spread",
            summary="Pending governed equity spread proxy; do not infer from unrelated signals.",
            impacted_views=["duration", "credit"],
            required_series_ids=["tushare.index.000300.SH.daily", "tushare.index.000300.SH.dailybasic"],
            warnings=["missing governed proxy series"],
        )

    matched_rule = _match_equity_bond_spread_rule(signal)
    stance: TransmissionAxisStance = matched_rule.stance if matched_rule is not None else "neutral"
    pct_change = signal.index_pct_change
    move_text = f"{pct_change:.2f}%" if pct_change is not None else "n/a"
    context = (
        f"CSI300 equity-bond spread is {signal.spread_pct:.2f}ppt "
        f"(earnings yield {signal.earnings_yield_pct:.2f}% - CN10Y {signal.bond_yield_pct:.2f}%), "
        f"with CSI300 move {move_text} on {signal.trade_date.isoformat()}."
    )
    summary = f"{matched_rule.summary} {context}" if matched_rule is not None else context
    return MacroBondTransmissionAxisResult(
        axis_key="equity_bond_spread",
        status="ready",
        stance=stance,
        summary=summary,
        impacted_views=["duration", "credit", "instrument"],
        required_series_ids=["tushare.index.000300.SH.daily", "tushare.index.000300.SH.dailybasic"],
        warnings=[],
    )


def _build_mega_cap_equities_axis(
    signal: MegaCapEquitySignal | None,
) -> MacroBondTransmissionAxisResult:
    if signal is None:
        return _build_pending_axis(
            axis_key="mega_cap_equities",
            summary="Pending governed mega-cap equity leadership proxy; do not infer from unrelated signals.",
            impacted_views=["credit", "instrument"],
            required_series_ids=["tushare.index.000300.SH.weight"],
            warnings=["missing governed proxy series"],
        )

    matched_rule = _match_mega_cap_equity_rule(signal)
    stance: TransmissionAxisStance = matched_rule.stance if matched_rule is not None else "neutral"
    leaders = ", ".join(signal.leading_constituents[:3]) or "n/a"
    move_text = f"{signal.index_pct_change:.2f}%" if signal.index_pct_change is not None else "n/a"
    context = (
        f"CSI300 top10 weight concentration is {signal.top10_weight_sum:.2f}% "
        f"(top5 {signal.top5_weight_sum:.2f}%) on {signal.weight_trade_date.isoformat()}, with latest index move {move_text}; "
        f"leaders include {leaders}."
    )
    summary = f"{matched_rule.summary} {context}" if matched_rule is not None else context
    return MacroBondTransmissionAxisResult(
        axis_key="mega_cap_equities",
        status="ready",
        stance=stance,
        summary=summary,
        impacted_views=["credit", "instrument"],
        required_series_ids=["tushare.index.000300.SH.weight"],
        warnings=[],
    )


def _build_pending_axis(
    *,
    axis_key: Literal["equity_bond_spread", "mega_cap_equities"],
    summary: str,
    impacted_views: list[str],
    required_series_ids: list[str],
    warnings: list[str],
) -> MacroBondTransmissionAxisResult:
    return MacroBondTransmissionAxisResult(
        axis_key=axis_key,
        status="pending_signal",
        stance="neutral",
        summary=summary,
        impacted_views=impacted_views,
        required_series_ids=required_series_ids,
        warnings=warnings,
    )


def _match_equity_bond_spread_rule(signal: EquityBondSpreadSignal) -> EquityBondSpreadRule | None:
    for rule in EQUITY_BOND_SPREAD_RULES:
        if rule.spread_min is not None and signal.spread_pct < rule.spread_min:
            continue
        if rule.spread_max is not None and signal.spread_pct > rule.spread_max:
            continue
        if rule.index_pct_change_min is not None:
            if signal.index_pct_change is None or signal.index_pct_change < rule.index_pct_change_min:
                continue
        if rule.index_pct_change_max is not None:
            if signal.index_pct_change is None or signal.index_pct_change > rule.index_pct_change_max:
                continue
        return rule
    return None


def _match_mega_cap_equity_rule(signal: MegaCapEquitySignal) -> MegaCapEquityRule | None:
    for rule in MEGA_CAP_EQUITY_RULES:
        if rule.concentration_min is not None and signal.top10_weight_sum < rule.concentration_min:
            continue
        if rule.concentration_max is not None and signal.top10_weight_sum > rule.concentration_max:
            continue
        if rule.index_pct_change_min is not None:
            if signal.index_pct_change is None or signal.index_pct_change < rule.index_pct_change_min:
                continue
        if rule.index_pct_change_max is not None:
            if signal.index_pct_change is None or signal.index_pct_change > rule.index_pct_change_max:
                continue
        return rule
    return None


def _build_duration_view(
    macro_environment: MacroEnvironmentScore,
    axis_map: dict[TransmissionAxisKey, MacroBondTransmissionAxisResult],
    correlations: Sequence[MacroBondCorrelation],
) -> MacroBondResearchViewResult:
    global_axis = axis_map["global_rates"]
    liquidity_axis = axis_map["liquidity"]
    inflation_axis = axis_map["commodities_inflation"]
    equity_axis = axis_map["equity_bond_spread"]
    stance: ResearchViewStance
    if global_axis.stance == "supportive" and inflation_axis.stance != "restrictive":
        stance = "bullish"
    elif global_axis.stance == "restrictive" and liquidity_axis.stance != "supportive":
        stance = "bearish"
    elif global_axis.stance != inflation_axis.stance and "neutral" not in {
        global_axis.stance,
        inflation_axis.stance,
    }:
        stance = "conflicted"
    else:
        stance = "neutral"
    base_stance = stance

    if equity_axis.status == "ready":
        if stance == "bullish" and equity_axis.stance == "restrictive":
            stance = "conflicted"
        elif stance == "neutral" and equity_axis.stance == "supportive":
            stance = "bullish"

    if (
        stance == "bullish"
        and base_stance == "neutral"
        and equity_axis.status == "ready"
        and equity_axis.stance == "supportive"
    ):
        summary = "Backend research supports longer duration because the equity-bond spread axis is supportive."
    elif stance == "bullish":
        summary = "Backend research supports longer duration across rates, NCD, and high-grade credit."
    elif stance == "bearish":
        summary = "Backend research favors keeping duration tight across rates, NCD, and high-grade credit."
    elif stance == "conflicted" and equity_axis.status == "ready" and equity_axis.stance == "restrictive":
        summary = "Duration inputs conflict: rates are supportive, but the equity-bond spread axis is restrictive."
    elif stance == "conflicted":
        summary = "Duration inputs conflict across rate direction and inflation pressure; keep duration balanced."
    else:
        summary = "Duration inputs are mixed, so keep the duration stance neutral."
    evidence = [
        f"global_rates: {global_axis.summary}",
        f"liquidity: {liquidity_axis.summary}",
    ]
    if equity_axis.status == "ready":
        evidence.append(f"equity-bond: {equity_axis.summary}")
    top_duration = _find_top_correlation(correlations, {"treasury", "cdb"})
    if top_duration is not None:
        evidence.append(_format_correlation_evidence(top_duration))
    return MacroBondResearchViewResult(
        key="duration",
        stance=stance,
        confidence=_confidence_from_values(
            abs(macro_environment.rate_direction_score),
            abs(macro_environment.liquidity_score),
            _correlation_rank(top_duration),
        ),
        summary=summary,
        affected_targets=["rates", "ncd", "high_grade_credit"],
        evidence=evidence,
    )


def _build_curve_view(
    macro_environment: MacroEnvironmentScore,
    axis_map: dict[TransmissionAxisKey, MacroBondTransmissionAxisResult],
    correlations: Sequence[MacroBondCorrelation],
) -> MacroBondResearchViewResult:
    global_axis = axis_map["global_rates"]
    liquidity_axis = axis_map["liquidity"]
    stance: ResearchViewStance
    if global_axis.stance == "supportive" and liquidity_axis.stance == "supportive":
        stance = "bullish"
    elif global_axis.stance == "restrictive" or liquidity_axis.stance == "restrictive":
        stance = "bearish"
    elif global_axis.stance == "neutral" and liquidity_axis.stance == "neutral":
        stance = "neutral"
    else:
        stance = "conflicted"

    summary = {
        "bullish": "Curve conditions favor owning front-end rates and NCD carry rather than flattening defensively.",
        "bearish": "Curve conditions argue for staying defensive on rates and NCD curve exposure.",
        "conflicted": "Curve inputs disagree across duration and liquidity; avoid a large curve tilt.",
        "neutral": "Curve inputs are balanced and do not support a strong rates or NCD curve tilt.",
    }[stance]
    evidence = [
        f"global_rates: {global_axis.summary}",
        f"liquidity: {liquidity_axis.summary}",
    ]
    top_curve = _find_top_correlation(correlations, {"treasury", "cdb"})
    if top_curve is not None:
        evidence.append(_format_correlation_evidence(top_curve))
    return MacroBondResearchViewResult(
        key="curve",
        stance=stance,
        confidence=_confidence_from_values(
            abs(macro_environment.rate_direction_score),
            abs(macro_environment.liquidity_score),
            _correlation_rank(top_curve),
        ),
        summary=summary,
        affected_targets=["rates", "ncd"],
        evidence=evidence,
    )


def _build_credit_view(
    macro_environment: MacroEnvironmentScore,
    axis_map: dict[TransmissionAxisKey, MacroBondTransmissionAxisResult],
    correlations: Sequence[MacroBondCorrelation],
) -> MacroBondResearchViewResult:
    liquidity_axis = axis_map["liquidity"]
    inflation_axis = axis_map["commodities_inflation"]
    equity_axis = axis_map["equity_bond_spread"]
    mega_cap_axis = axis_map["mega_cap_equities"]
    stance: ResearchViewStance
    if (
        equity_axis.status == "ready"
        and equity_axis.stance == "restrictive"
        and mega_cap_axis.status == "ready"
        and mega_cap_axis.stance == "restrictive"
    ):
        stance = "bearish"
    elif liquidity_axis.stance == "supportive" and inflation_axis.stance != "restrictive":
        stance = "bullish"
    elif liquidity_axis.stance == "restrictive" or inflation_axis.stance == "restrictive":
        stance = "bearish"
    elif liquidity_axis.stance == "neutral" and inflation_axis.stance == "neutral":
        stance = "neutral"
    else:
        stance = "conflicted"

    if (
        stance == "bearish"
        and equity_axis.status == "ready"
        and equity_axis.stance == "restrictive"
        and mega_cap_axis.status == "ready"
        and mega_cap_axis.stance == "restrictive"
    ):
        summary = "High-grade credit should stay defensive because both equity-bond spread and mega-cap leadership are restrictive."
    elif stance == "bullish":
        summary = "High-grade credit is supported, but the tranche remains limited to high-grade spread risk only."
    elif stance == "bearish":
        summary = "High-grade credit should stay defensive while liquidity or inflation pressure remains restrictive."
    elif stance == "conflicted":
        summary = "High-grade credit inputs conflict; keep spread exposure selective and high quality only."
    else:
        summary = "High-grade credit inputs are balanced, so keep spread exposure neutral."
    evidence = [
        f"liquidity: {liquidity_axis.summary}",
        f"commodities_inflation: {inflation_axis.summary}",
    ]
    if equity_axis.status == "ready":
        evidence.append(f"equity-bond: {equity_axis.summary}")
    if mega_cap_axis.status == "ready":
        evidence.append(f"mega-cap: {mega_cap_axis.summary}")
    top_credit = _find_top_correlation(correlations, {"credit_spread", "aaa_credit"})
    if top_credit is not None:
        evidence.append(_format_correlation_evidence(top_credit))
    return MacroBondResearchViewResult(
        key="credit",
        stance=stance,
        confidence=_confidence_from_values(
            abs(macro_environment.liquidity_score),
            abs(macro_environment.inflation_score),
            _correlation_rank(top_credit),
        ),
        summary=summary,
        affected_targets=["high_grade_credit"],
        evidence=evidence,
    )


def _build_instrument_view(
    macro_environment: MacroEnvironmentScore,
    axis_map: dict[TransmissionAxisKey, MacroBondTransmissionAxisResult],
    correlations: Sequence[MacroBondCorrelation],
) -> MacroBondResearchViewResult:
    global_axis = axis_map["global_rates"]
    liquidity_axis = axis_map["liquidity"]
    inflation_axis = axis_map["commodities_inflation"]
    equity_axis = axis_map["equity_bond_spread"]
    mega_cap_axis = axis_map["mega_cap_equities"]
    considered_axes = [
        global_axis,
        liquidity_axis,
        inflation_axis,
        *(axis for axis in (equity_axis, mega_cap_axis) if axis.status == "ready"),
    ]
    supportive_count = sum(axis.stance == "supportive" for axis in considered_axes)
    restrictive_count = sum(axis.stance == "restrictive" for axis in considered_axes)
    stance: ResearchViewStance
    if supportive_count >= 2 and restrictive_count == 0:
        stance = "bullish"
    elif restrictive_count >= 2 and supportive_count == 0:
        stance = "bearish"
    elif supportive_count and restrictive_count:
        stance = "conflicted"
    else:
        stance = "neutral"

    summary = {
        "bullish": "Prefer rates first, then NCD carry, with high-grade credit as a controlled extension.",
        "bearish": "Keep implementation defensive across rates, NCD, and high-grade credit until pressure eases.",
        "conflicted": "Instrument preferences are mixed; keep allocations balanced across rates, NCD, and high-grade credit.",
        "neutral": "No strong instrument tilt is supported across rates, NCD, and high-grade credit.",
    }[stance]
    evidence = [
        f"global_rates: {global_axis.summary}",
        f"liquidity: {liquidity_axis.summary}",
        f"commodities_inflation: {inflation_axis.summary}",
    ]
    if equity_axis.status == "ready":
        evidence.append(f"equity-bond: {equity_axis.summary}")
    if mega_cap_axis.status == "ready":
        evidence.append(f"mega-cap: {mega_cap_axis.summary}")
    top_instrument = _find_top_correlation(correlations, {"treasury", "cdb", "credit_spread", "aaa_credit"})
    if top_instrument is not None:
        evidence.append(_format_correlation_evidence(top_instrument))
    return MacroBondResearchViewResult(
        key="instrument",
        stance=stance,
        confidence=_confidence_from_values(
            abs(macro_environment.rate_direction_score),
            abs(macro_environment.liquidity_score),
            abs(macro_environment.inflation_score),
            _correlation_rank(top_instrument),
        ),
        summary=summary,
        affected_targets=["rates", "ncd", "high_grade_credit"],
        evidence=evidence,
    )


def _axis_stance_from_score(
    score: float,
    *,
    neutral_threshold: float = 0.1,
    reverse: bool = False,
) -> Literal["supportive", "neutral", "restrictive"]:
    if score >= neutral_threshold:
        return "supportive" if not reverse else "restrictive"
    if score <= -neutral_threshold:
        return "restrictive" if not reverse else "supportive"
    return "neutral"


def _merge_axis_stances(
    primary: Literal["supportive", "neutral", "restrictive"],
    secondary: Literal["supportive", "neutral", "restrictive"],
) -> TransmissionAxisStance:
    if primary == secondary:
        return primary
    if "neutral" in {primary, secondary}:
        return secondary if primary == "neutral" else primary
    return "conflicted"


def _confidence_from_values(*values: float) -> ResearchViewConfidence:
    strongest = max((float(value) for value in values), default=0.0)
    if strongest >= 0.65:
        return "high"
    if strongest >= 0.25:
        return "medium"
    return "low"


def _find_top_correlation(
    correlations: Sequence[MacroBondCorrelation],
    target_families: set[str],
) -> MacroBondCorrelation | None:
    for correlation in correlations:
        family, _tenor = _split_target_identity(correlation.target_yield)
        if family in target_families:
            return correlation
    return None


def _format_correlation_evidence(correlation: MacroBondCorrelation) -> str:
    family, tenor = _split_target_identity(correlation.target_yield)
    target_label = family if tenor is None else f"{family} {tenor}"
    strength = _correlation_rank(correlation)
    return (
        f"Top supported correlation: {correlation.series_name} vs {target_label} "
        f"(strength {round(strength, 3)}, lead_lag_days {correlation.lead_lag_days})."
    )


def _split_target_identity(target_yield: str) -> tuple[str, str | None]:
    family, separator, tenor = str(target_yield).rpartition("_")
    if not separator:
        return str(target_yield), None
    return family, tenor or None


def _correlation_rank(correlation: MacroBondCorrelation | None) -> float:
    if correlation is None:
        return 0.0
    candidates = (
        correlation.correlation_1y,
        correlation.correlation_6m,
        correlation.correlation_3m,
    )
    strengths = [abs(float(value)) for value in candidates if value is not None]
    return max(strengths, default=0.0)
