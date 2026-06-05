from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from math import sqrt
from typing import Any, Iterable

from .helpers import (
    available_dates,
    build_curve_history,
    clamp,
    first_available_rate,
    get_curve_rate,
)

_TWENTY_ONE = 21
_TEN = 10
_ONE_HUNDRED = Decimal("100")


def _round(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _avg(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    return sum(values) / Decimal(len(values))


def _rate_change_bp(
    curves_by_date: dict[date, dict[str, dict[str, Decimal]]],
    dates: list[date],
    candidates: list[tuple[str, str]],
    lookback_index: int,
) -> Decimal | None:
    if len(dates) <= lookback_index:
        return None

    current_values = [
        rate
        for curve_id, tenor in candidates
        if (rate := get_curve_rate(curves_by_date, dates[0], curve_id, tenor)) is not None
    ]
    prior_values = [
        rate
        for curve_id, tenor in candidates
        if (rate := get_curve_rate(curves_by_date, dates[lookback_index], curve_id, tenor)) is not None
    ]
    current_avg = _avg(current_values)
    prior_avg = _avg(prior_values)
    if current_avg is None or prior_avg is None:
        return None
    return (current_avg - prior_avg) * _ONE_HUNDRED


def _stddev_bp(series: list[Decimal]) -> Decimal | None:
    if len(series) < 5:
        return None
    mean = sum(series) / Decimal(len(series))
    variance = sum((value - mean) ** 2 for value in series) / Decimal(len(series))
    return Decimal(str(sqrt(float(variance)))) * _ONE_HUNDRED


def _score_term_structure(slope_bp: Decimal | None) -> Decimal | None:
    if slope_bp is None:
        return None
    if slope_bp < Decimal("0"):
        return Decimal("-100")
    if slope_bp < Decimal("20"):
        return Decimal("-60")
    if slope_bp < Decimal("50"):
        return Decimal("-20") + (slope_bp - Decimal("20")) * Decimal("0.67")
    if slope_bp < Decimal("80"):
        return (slope_bp - Decimal("50")) * Decimal("1.67")
    return Decimal("100")


def _score_credit_environment(
    aaa_spread_bp: Decimal | None,
    aa_minus_aaa_bp: Decimal | None,
) -> Decimal | None:
    if aaa_spread_bp is None and aa_minus_aaa_bp is None:
        return None

    scores: list[Decimal] = []
    if aaa_spread_bp is not None:
        scores.append(clamp(Decimal("100") - aaa_spread_bp * Decimal("1.25"), Decimal("-100"), Decimal("100")))
    if aa_minus_aaa_bp is not None:
        scores.append(clamp(Decimal("100") - aa_minus_aaa_bp * Decimal("3"), Decimal("-100"), Decimal("100")))
    return _avg(scores)


def compute_monetary_policy_stance(
    curve_rows: Iterable[Any],
    *,
    report_date: date,
) -> dict[str, Any]:
    curves_by_date = build_curve_history(curve_rows, report_date=report_date)
    dates = available_dates(curves_by_date)
    if not dates:
        return {
            "report_date": report_date.isoformat(),
            "data_status": "unavailable",
            "stance_score": 0.0,
            "stance_label": "unavailable",
            "headline": "暂无市场曲线数据，无法进行货币政策立场分析。",
            "components": [],
            "key_metrics": {},
            "warnings": ["NO_MARKET_CURVES"],
        }

    current_date = dates[0]
    warnings: list[str] = []
    current_curves = curves_by_date[current_date]

    policy_curve_id, policy_tenor, policy_rate = first_available_rate(
        curves_by_date,
        current_date,
        [("CN_RRP", "7D"), ("CN_REPO", "7D"), ("CN_GC", "7D")],
    )
    if policy_rate is None:
        warnings.append("POLICY_RATE_7D_MISSING")

    _, _, dr007 = first_available_rate(curves_by_date, current_date, [("CN_DR", "7D")])
    if dr007 is None:
        warnings.append("DR007_MISSING")

    _, _, mlf_rate = first_available_rate(curves_by_date, current_date, [("CN_MLF", "1Y")])
    _, _, lpr_1y = first_available_rate(curves_by_date, current_date, [("CN_LPR", "1Y")])
    _, _, shibor_3m = first_available_rate(curves_by_date, current_date, [("CN_SHIBOR", "3M")])

    gov_1y = get_curve_rate(curves_by_date, current_date, "CN_GOVT", "1Y")
    gov_10y = get_curve_rate(curves_by_date, current_date, "CN_GOVT", "10Y")
    gov_slope_10y_1y_bp = None
    if gov_1y is not None and gov_10y is not None:
        gov_slope_10y_1y_bp = (gov_10y - gov_1y) * _ONE_HUNDRED
    else:
        warnings.append("GOVERNMENT_SLOPE_MISSING")

    aaa_spread_bp = None
    aa_minus_aaa_bp = None
    for tenor in ("3Y", "5Y", "1Y"):
        aaa_curve = get_curve_rate(curves_by_date, current_date, "CN_CREDIT_AAA", tenor)
        gov_curve = get_curve_rate(curves_by_date, current_date, "CN_GOVT", tenor)
        if aaa_curve is not None and gov_curve is not None:
            aaa_spread_bp = (aaa_curve - gov_curve) * _ONE_HUNDRED
            break
    if aaa_spread_bp is None:
        warnings.append("AAA_SPREAD_MISSING")

    for tenor in ("3Y", "5Y", "1Y"):
        aa_curve = get_curve_rate(curves_by_date, current_date, "CN_CREDIT_AA", tenor)
        aaa_curve = get_curve_rate(curves_by_date, current_date, "CN_CREDIT_AAA", tenor)
        if aa_curve is not None and aaa_curve is not None:
            aa_minus_aaa_bp = (aa_curve - aaa_curve) * _ONE_HUNDRED
            break

    policy_change_bp = _rate_change_bp(
        curves_by_date,
        dates,
        [("CN_MLF", "1Y"), ("CN_RRP", "7D"), ("CN_LPR", "1Y")],
        _TWENTY_ONE,
    )
    if policy_change_bp is None and len(dates) <= _TWENTY_ONE:
        warnings.append("POLICY_RATE_HISTORY_SHORT")

    dr_history = [
        rate
        for sample_date in dates[:_TEN]
        if (rate := get_curve_rate(curves_by_date, sample_date, "CN_DR", "7D")) is not None
    ]
    dr007_volatility_bp = _stddev_bp(dr_history)
    if dr007_volatility_bp is None and len(dr_history) < 5:
        warnings.append("DR007_HISTORY_SHORT")

    policy_rate_score = None
    if policy_change_bp is not None:
        policy_rate_score = clamp(-policy_change_bp * Decimal("4"), Decimal("-100"), Decimal("100"))

    liquidity_score = None
    if dr007 is not None and policy_rate is not None:
        liquidity_gap_bp = (dr007 - policy_rate) * _ONE_HUNDRED
        liquidity_score = clamp(-liquidity_gap_bp * Decimal("4"), Decimal("-100"), Decimal("100"))
    else:
        liquidity_gap_bp = None

    term_structure_score = _score_term_structure(gov_slope_10y_1y_bp)
    credit_environment_score = _score_credit_environment(aaa_spread_bp, aa_minus_aaa_bp)
    volatility_score = None
    if dr007_volatility_bp is not None:
        volatility_score = clamp(Decimal("100") - dr007_volatility_bp * Decimal("8"), Decimal("-100"), Decimal("100"))

    weighted_scores = [
        (policy_rate_score, Decimal("0.30")),
        (liquidity_score, Decimal("0.25")),
        (volatility_score, Decimal("0.15")),
        (term_structure_score, Decimal("0.15")),
        (credit_environment_score, Decimal("0.15")),
    ]
    available_components = [(score, weight) for score, weight in weighted_scores if score is not None]
    if not available_components:
        return {
            "report_date": report_date.isoformat(),
            "data_status": "unavailable",
            "stance_score": 0.0,
            "stance_label": "unavailable",
            "headline": "当前市场数据不足以计算货币政策立场得分。",
            "components": [],
            "key_metrics": {},
            "warnings": warnings or ["INSUFFICIENT_POLICY_INPUTS"],
        }

    total_weight = sum(weight for _, weight in available_components)
    stance_score = sum(score * weight for score, weight in available_components) / total_weight
    stance_score = stance_score.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    if stance_score >= Decimal("20"):
        stance_label = "accommodative"
        headline = "流动性环境仍偏宽松。"
    elif stance_score <= Decimal("-20"):
        stance_label = "tight"
        headline = "货币市场偏紧，宜保持谨慎。"
    else:
        stance_label = "neutral"
        headline = "政策与流动性条件整体均衡。"

    components = []
    if policy_rate_score is not None:
        components.append(
            {
                "key": "policy_rate",
                "label": "政策利率趋势",
                "score": _round(policy_rate_score),
                "detail": (
                    f"近 21 个交易日平均变动：{_round(policy_change_bp)} bp。"
                    if policy_change_bp is not None
                    else None
                ),
            }
        )
    if liquidity_score is not None:
        components.append(
            {
                "key": "liquidity",
                "label": "货币市场流动性",
                "score": _round(liquidity_score),
                "detail": (
                    f"DR007 与 {policy_curve_id or '政策利率'} {policy_tenor or ''} 利差：{_round(liquidity_gap_bp)} bp。"
                    if liquidity_gap_bp is not None
                    else None
                ),
            }
        )
    if volatility_score is not None:
        components.append(
            {
                "key": "volatility",
                "label": "资金面波动",
                "score": _round(volatility_score),
                "detail": f"近 10 个交易日 DR007 波动：{_round(dr007_volatility_bp)} bp。",
            }
        )
    if term_structure_score is not None:
        components.append(
            {
                "key": "term_structure",
                "label": "国债曲线形态",
                "score": _round(term_structure_score),
                "detail": f"10年-1年利差：{_round(gov_slope_10y_1y_bp)} bp。",
            }
        )
    if credit_environment_score is not None:
        components.append(
            {
                "key": "credit_environment",
                "label": "信用环境",
                "score": _round(credit_environment_score),
                "detail": (
                    f"AAA 利差 {_round(aaa_spread_bp)} bp；AA 相对 AAA {_round(aa_minus_aaa_bp)} bp。"
                    if aaa_spread_bp is not None and aa_minus_aaa_bp is not None
                    else None
                ),
            }
        )

    data_status = "complete"
    if warnings:
        data_status = "degraded"

    return {
        "report_date": report_date.isoformat(),
        "data_status": data_status,
        "stance_score": _round(stance_score),
        "stance_label": stance_label,
        "headline": headline,
        "components": components,
        "key_metrics": {
            "policy_rate_curve_id": policy_curve_id,
            "policy_rate_tenor": policy_tenor,
            "policy_rate_7d": _round(policy_rate) if policy_rate is not None else None,
            "dr007": _round(dr007) if dr007 is not None else None,
            "mlf_1y": _round(mlf_rate) if mlf_rate is not None else None,
            "lpr_1y": _round(lpr_1y) if lpr_1y is not None else None,
            "shibor_3m": _round(shibor_3m) if shibor_3m is not None else None,
            "gov_slope_10y_1y_bp": _round(gov_slope_10y_1y_bp) if gov_slope_10y_1y_bp is not None else None,
            "aaa_spread_bp": _round(aaa_spread_bp) if aaa_spread_bp is not None else None,
            "aa_minus_aaa_bp": _round(aa_minus_aaa_bp) if aa_minus_aaa_bp is not None else None,
            "policy_change_21d_bp": _round(policy_change_bp) if policy_change_bp is not None else None,
            "dr007_volatility_10d_bp": _round(dr007_volatility_bp) if dr007_volatility_bp is not None else None,
        },
        "warnings": warnings,
    }
