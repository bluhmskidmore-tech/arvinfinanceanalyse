from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable

from .helpers import available_dates, build_curve_history, get_curve_rate

_ONE_HUNDRED = Decimal("100")


def _round(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def compute_rate_turning_point(
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
            "direction": "unavailable",
            "conviction": "LOW",
            "headline": "暂无市场曲线数据，无法进行利率拐点分析。",
            "recommended_duration_stance": None,
            "current_10y": None,
            "current_slope_10y_1y_bp": None,
            "change_5d_bp": None,
            "change_20d_bp": None,
            "percentile_1y": None,
            "signals": [],
            "interpretation": "利率拐点分析需要 10 年期国债曲线历史。",
            "warnings": ["NO_GOVERNMENT_CURVE_HISTORY"],
        }

    history_10y = [
        (sample_date, rate)
        for sample_date in dates
        if (rate := get_curve_rate(curves_by_date, sample_date, "CN_GOVT", "10Y")) is not None
    ]
    history_slope = [
        (sample_date, (ten_year - one_year) * _ONE_HUNDRED)
        for sample_date in dates
        if (ten_year := get_curve_rate(curves_by_date, sample_date, "CN_GOVT", "10Y")) is not None
        and (one_year := get_curve_rate(curves_by_date, sample_date, "CN_GOVT", "1Y")) is not None
    ]

    if len(history_10y) < 10 or len(history_slope) < 10:
        current_10y = history_10y[0][1] if history_10y else None
        current_slope = history_slope[0][1] if history_slope else None
        return {
            "report_date": report_date.isoformat(),
            "data_status": "unavailable",
            "direction": "unavailable",
            "conviction": "LOW",
            "headline": "国债曲线历史不足，无法识别利率拐点。",
            "recommended_duration_stance": None,
            "current_10y": _round(current_10y),
            "current_slope_10y_1y_bp": _round(current_slope),
            "change_5d_bp": None,
            "change_20d_bp": None,
            "percentile_1y": None,
            "signals": [],
            "interpretation": "至少需要 10 个观测点才能判定拐点类型。",
            "warnings": ["TURNING_POINT_HISTORY_SHORT"],
        }

    current_10y = history_10y[0][1]
    current_slope = history_slope[0][1]
    change_5d_bp = (history_10y[0][1] - history_10y[5][1]) * _ONE_HUNDRED if len(history_10y) > 5 else None
    change_20d_bp = (history_10y[0][1] - history_10y[20][1]) * _ONE_HUNDRED if len(history_10y) > 20 else None
    slope_change_20d_bp = (
        history_slope[0][1] - history_slope[20][1] if len(history_slope) > 20 else None
    )

    prior_levels = [rate for _, rate in history_10y[1:252]]
    percentile_1y = None
    if prior_levels:
        below = sum(1 for rate in prior_levels if rate < current_10y)
        percentile_1y = Decimal(below) / Decimal(len(prior_levels)) * _ONE_HUNDRED

    bottom_signals = 0
    top_signals = 0
    signals: list[dict[str, str]] = []

    if percentile_1y is not None and percentile_1y <= Decimal("20"):
        bottom_signals += 1
        signals.append({"key": "level", "value": "收益率处于历史区间偏低分位。"})
    elif percentile_1y is not None and percentile_1y >= Decimal("80"):
        top_signals += 1
        signals.append({"key": "level", "value": "收益率处于历史区间偏高分位。"})

    if change_5d_bp is not None and change_5d_bp >= Decimal("5"):
        bottom_signals += 1
        signals.append({"key": "five_day_move", "value": "近五个交易日 10 年期收益率反弹。"})
    elif change_5d_bp is not None and change_5d_bp <= Decimal("-5"):
        top_signals += 1
        signals.append({"key": "five_day_move", "value": "近五个交易日 10 年期收益率回落。"})

    if slope_change_20d_bp is not None and slope_change_20d_bp >= Decimal("10"):
        bottom_signals += 1
        signals.append({"key": "slope", "value": "中期窗口内曲线斜率走陡。"})
    elif slope_change_20d_bp is not None and slope_change_20d_bp <= Decimal("-10"):
        top_signals += 1
        signals.append({"key": "slope", "value": "中期窗口内曲线斜率走平。"})

    if bottom_signals >= 2 and bottom_signals > top_signals:
        direction = "bottoming"
        recommended_duration_stance = "shorten"
        interpretation = "低收益率环境叠加近期反弹，利率更接近筑底阶段。"
        headline = "宏观利率更接近收益率底部而非新一轮上行。"
    elif top_signals >= 2 and top_signals > bottom_signals:
        direction = "topping"
        recommended_duration_stance = "extend"
        interpretation = "高收益率环境叠加回撤，利率更接近筑顶过程。"
        headline = "宏观利率更接近收益率顶部而非持续抛售。"
    else:
        direction = "range"
        recommended_duration_stance = "neutral"
        interpretation = "当前水平与近期走势尚不足以给出明确拐点信号。"
        headline = "利率仍以区间震荡为主，缺乏高置信度拐点判断。"

    conviction_score = max(bottom_signals, top_signals)
    conviction = "LOW"
    if conviction_score >= 3:
        conviction = "HIGH"
    elif conviction_score >= 2:
        conviction = "MEDIUM"

    return {
        "report_date": report_date.isoformat(),
        "data_status": "complete",
        "direction": direction,
        "conviction": conviction,
        "headline": headline,
        "recommended_duration_stance": recommended_duration_stance,
        "current_10y": _round(current_10y),
        "current_slope_10y_1y_bp": _round(current_slope),
        "change_5d_bp": _round(change_5d_bp),
        "change_20d_bp": _round(change_20d_bp),
        "percentile_1y": _round(percentile_1y),
        "signals": signals,
        "interpretation": interpretation,
        "warnings": [],
    }
