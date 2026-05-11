from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import date
from typing import Any

import pandas as pd

CRISIS_SCORE_RULE_VERSION = "rv_macro_crisis_score_cn_v1"
CRISIS_SCORE_WEIGHTS: dict[str, float] = {
    "equity_vol": 0.25,
    "credit_spread": 0.25,
    "fx_vol": 0.15,
    "commodity_vol": 0.15,
    "liquidity_stress": 0.20,
}

_INDICATOR_LABELS = {
    "equity_vol": "HS300 realized volatility",
    "credit_spread": "AA 5Y - treasury 5Y",
    "fx_vol": "USD/CNY realized volatility",
    "commodity_vol": "Nanhua commodity realized volatility",
    "liquidity_stress": "DR007 - 7D reverse repo",
}


def compute_crisis_score_payload(
    series_data: dict[str, Sequence[tuple[date, float]]],
    *,
    report_date: date,
    vol_window: int = 20,
    z_window: int = 120,
    min_z_observations: int = 60,
    weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    resolved_weights = weights or CRISIS_SCORE_WEIGHTS
    indicators = compute_crisis_indicators(series_data, vol_window=vol_window)
    indicators = indicators[indicators.index.date <= report_date]
    if indicators.empty:
        return _unavailable_payload(report_date, ["NO_CRISIS_SCORE_INPUTS"])

    score_frame = compute_crisis_score(
        indicators,
        z_window=z_window,
        min_z_observations=min_z_observations,
        weights=resolved_weights,
    )
    score_frame = score_frame[score_frame.index.date <= report_date]
    if score_frame.empty or score_frame["crisis_score"].dropna().empty:
        return _unavailable_payload(report_date, ["CRISIS_SCORE_HISTORY_SHORT"])

    latest_index = score_frame["crisis_score"].dropna().index[-1]
    latest = score_frame.loc[latest_index]
    score = float(latest["crisis_score"])
    regime, recommendation = classify_crisis_score(score)
    component_details = _component_details(latest, indicators, latest_index, resolved_weights)
    warnings = _component_warnings(series_data, component_details)
    data_status = "complete" if len(component_details) == len(resolved_weights) and not warnings else "degraded"
    scores = score_frame["crisis_score"].dropna()
    percentile = float((scores <= score).mean() * 100) if len(scores) else None

    return {
        "report_date": latest_index.date().isoformat(),
        "requested_report_date": report_date.isoformat(),
        "data_status": data_status,
        "rule_version": CRISIS_SCORE_RULE_VERSION,
        "crisis_score": round(score, 4),
        "regime": regime,
        "recommendation": recommendation,
        "headline": f"Crisis Score {score:.2f}: {regime}",
        "percentile": round(percentile, 2) if percentile is not None else None,
        "available_component_count": len(component_details),
        "component_count": len(resolved_weights),
        "components": component_details,
        "weights": resolved_weights,
        "warnings": warnings,
    }


def compute_crisis_indicators(
    series_data: dict[str, Sequence[tuple[date, float]]],
    *,
    vol_window: int = 20,
) -> pd.DataFrame:
    indicators = pd.DataFrame()

    hs300 = _to_series(series_data.get("hs300"))
    if not hs300.empty:
        indicators["equity_vol"] = _realized_volatility(hs300, vol_window)

    credit_spread = _to_series(series_data.get("credit_spread"))
    if credit_spread.empty:
        aa_5y = _to_series(series_data.get("aa_5y"))
        gov_5y = _to_series(series_data.get("gov_5y"))
        if not aa_5y.empty and not gov_5y.empty:
            aligned = pd.concat({"aa_5y": aa_5y, "gov_5y": gov_5y}, axis=1).sort_index().ffill()
            credit_spread = aligned["aa_5y"] - aligned["gov_5y"]
    if not credit_spread.empty:
        indicators["credit_spread"] = credit_spread

    usdcny = _to_series(series_data.get("usdcny"))
    if not usdcny.empty:
        indicators["fx_vol"] = _realized_volatility(usdcny, vol_window)

    nanhua = _to_series(series_data.get("nanhua"))
    if not nanhua.empty:
        indicators["commodity_vol"] = _realized_volatility(nanhua, vol_window)

    dr007 = _to_series(series_data.get("dr007"))
    reverse_repo = _to_series(series_data.get("reverse_repo_7d"))
    if not dr007.empty and not reverse_repo.empty:
        aligned = pd.concat({"dr007": dr007, "reverse_repo": reverse_repo}, axis=1).sort_index().ffill()
        indicators["liquidity_stress"] = aligned["dr007"] - aligned["reverse_repo"]

    if indicators.empty:
        return indicators
    return indicators.sort_index().dropna(how="all")


def compute_crisis_score(
    indicators: pd.DataFrame,
    *,
    z_window: int = 120,
    min_z_observations: int = 60,
    weights: dict[str, float] | None = None,
) -> pd.DataFrame:
    resolved_weights = weights or CRISIS_SCORE_WEIGHTS
    z_scores = pd.DataFrame(index=indicators.index)

    for column in indicators.columns:
        if column not in resolved_weights:
            continue
        rolling_mean = indicators[column].rolling(z_window, min_periods=min_z_observations).mean()
        rolling_std = indicators[column].rolling(z_window, min_periods=min_z_observations).std()
        rolling_std = rolling_std.mask(rolling_std == 0)
        z_scores[f"{column}_z"] = (indicators[column] - rolling_mean) / rolling_std

    z_scores = z_scores.dropna(how="all")
    if z_scores.empty:
        return pd.DataFrame(columns=["crisis_score"], index=z_scores.index)

    score = pd.Series(0.0, index=z_scores.index)
    total_weight = 0.0
    for column in indicators.columns:
        z_column = f"{column}_z"
        if z_column not in z_scores.columns or column not in resolved_weights:
            continue
        score += resolved_weights[column] * z_scores[z_column].fillna(0.0)
        total_weight += resolved_weights[column]

    if total_weight > 0:
        score = score / total_weight
    return pd.DataFrame({"crisis_score": score}, index=z_scores.index).join(z_scores)


def classify_crisis_score(score: float) -> tuple[str, str]:
    if score < 0:
        return "宽松", "可适当加仓，风险偏好环境"
    if score < 1:
        return "正常", "维持当前配置"
    if score < 2:
        return "警惕", "降低风险敞口，增加对冲"
    if score < 3:
        return "高风险", "大幅降仓，启动 CTA 保护"
    return "危机", "最低仓位，全面防御，买入期权对冲"


def _to_series(points: Sequence[tuple[date, float]] | None) -> pd.Series:
    if not points:
        return pd.Series(dtype="float64")
    rows = [
        (pd.Timestamp(point_date), float(value))
        for point_date, value in points
        if point_date is not None and value is not None and math.isfinite(float(value))
    ]
    if not rows:
        return pd.Series(dtype="float64")
    series = pd.Series({point_date: value for point_date, value in rows}, dtype="float64")
    return series.sort_index()


def _realized_volatility(series: pd.Series, window: int) -> pd.Series:
    clean = series.astype("float64").where(series.astype("float64") > 0)
    ratio = (clean / clean.shift(1)).where(lambda values: values > 0)
    log_return = ratio.apply(lambda value: math.log(float(value)) if pd.notna(value) else float("nan"))
    return log_return.rolling(window).std() * math.sqrt(252) * 100


def _component_details(
    latest: pd.Series,
    indicators: pd.DataFrame,
    latest_index: pd.Timestamp,
    weights: dict[str, float],
) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for indicator, weight in weights.items():
        z_value = latest.get(f"{indicator}_z")
        if z_value is None or pd.isna(z_value):
            continue
        raw_value = indicators.get(indicator)
        latest_raw = raw_value.loc[latest_index] if raw_value is not None and latest_index in raw_value.index else None
        details.append(
            {
                "key": indicator,
                "label": _INDICATOR_LABELS.get(indicator, indicator),
                "raw_value": round(float(latest_raw), 4) if latest_raw is not None and pd.notna(latest_raw) else None,
                "z_score": round(float(z_value), 4),
                "weight": weight,
            }
        )
    return details


def _component_warnings(
    series_data: dict[str, Sequence[tuple[date, float]]],
    component_details: list[dict[str, Any]],
) -> list[str]:
    available_components = {str(item["key"]) for item in component_details}
    warnings: list[str] = []
    required_inputs = {
        "equity_vol": ("hs300",),
        "credit_spread": ("aa_5y", "gov_5y"),
        "fx_vol": ("usdcny",),
        "commodity_vol": ("nanhua",),
        "liquidity_stress": ("dr007", "reverse_repo_7d"),
    }
    for component, inputs in required_inputs.items():
        if component not in available_components:
            warnings.append(f"{component.upper()}_UNAVAILABLE")
        for input_key in inputs:
            if not series_data.get(input_key):
                warnings.append(f"{input_key.upper()}_MISSING")
    return _dedupe(warnings)


def _unavailable_payload(report_date: date, warnings: list[str]) -> dict[str, Any]:
    return {
        "report_date": report_date.isoformat(),
        "requested_report_date": report_date.isoformat(),
        "data_status": "unavailable",
        "rule_version": CRISIS_SCORE_RULE_VERSION,
        "crisis_score": None,
        "regime": "不可用",
        "recommendation": "补齐 Crisis Score 所需历史序列后再判断",
        "headline": "Crisis Score 数据不足",
        "percentile": None,
        "available_component_count": 0,
        "component_count": len(CRISIS_SCORE_WEIGHTS),
        "components": [],
        "weights": CRISIS_SCORE_WEIGHTS,
        "warnings": warnings,
    }


def _dedupe(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out
