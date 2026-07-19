"""中国版美林时钟（连续三维动量 + 资产偏好）纯函数。

从 toolkit/scripts/merrill_clock_cn.py 抽取；不访问 Wind/网络。
输入为已加载的宽表行、DataFrame 或 alias 序列点。
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

MERRILL_CLOCK_RULE_VERSION = "rv_macro_merrill_clock_cn_v1"

# 与脚本 GROWTH_INDICATORS / INFLATION / LIQUIDITY 列名对齐
GROWTH_WEIGHTS: dict[str, float] = {
    "pmi": 0.30,
    "industrial_va": 0.25,
    "pmi_new_orders": 0.25,
    "electricity": 0.10,
    "freight": 0.10,
}

# 系统宽表字段 → 脚本列名（仅映射实际可经 wide_rows / series 加载的别名）
_WIDE_TO_SCRIPT_COLUMNS: dict[str, str] = {
    "pmi": "pmi",
    "industrial_yoy": "industrial_va",
    "industrial_va": "industrial_va",
    "pmi_new_orders": "pmi_new_orders",
    "electricity": "electricity",
    "freight": "freight",
    "cpi_yoy": "cpi_yoy",
    "ppi_yoy": "ppi_yoy",
    "m2_yoy": "m2_yoy",
    "social_financing_yoy": "social_financing",
    "social_financing": "social_financing",
}

_SYSTEM_GROWTH_COLUMNS = ("pmi", "industrial_va")
_SYSTEM_INFLATION_COLUMNS = ("cpi_yoy", "ppi_yoy")
_SYSTEM_LIQUIDITY_COLUMNS = ("m2_yoy", "social_financing")
_OPTIONAL_GROWTH_COLUMNS = ("pmi_new_orders", "electricity", "freight")


def compute_momentum(
    series: pd.Series,
    short_window: int = 3,
    long_window: int = 12,
) -> pd.Series:
    """短期均值 vs 长期均值，经 tanh 压缩到 [-1, +1]。"""
    short_ma = series.rolling(short_window, min_periods=1).mean()
    long_ma = series.rolling(long_window, min_periods=3).mean()
    long_std = series.rolling(long_window, min_periods=3).std()
    long_std = long_std.replace(0, np.nan)
    raw = (short_ma - long_ma) / long_std
    return np.tanh(raw)


def compute_growth_momentum(df: pd.DataFrame) -> pd.Series:
    """合成增长动量（多指标加权，权重按可用列归一化）。"""
    momentums: dict[str, pd.Series] = {}
    for name, weight in GROWTH_WEIGHTS.items():
        if name in df.columns:
            momentums[name] = compute_momentum(df[name]) * weight
    if not momentums:
        return pd.Series(dtype=float)
    result = pd.DataFrame(momentums).sum(axis=1)
    total_weight = sum(GROWTH_WEIGHTS[key] for key in momentums)
    if total_weight > 0:
        result = result / total_weight
    return result


def compute_inflation_momentum(df: pd.DataFrame) -> pd.Series:
    """合成通胀动量: CPI×0.4 + PPI×0.6（仅一侧可用时退化为单侧）。"""
    cpi_m = compute_momentum(df["cpi_yoy"]) if "cpi_yoy" in df.columns else None
    ppi_m = compute_momentum(df["ppi_yoy"]) if "ppi_yoy" in df.columns else None
    if cpi_m is not None and ppi_m is not None:
        return 0.4 * cpi_m + 0.6 * ppi_m
    if cpi_m is not None:
        return cpi_m
    if ppi_m is not None:
        return ppi_m
    return pd.Series(dtype=float)


def compute_liquidity_momentum(df: pd.DataFrame) -> pd.Series:
    """流动性动量: M2 与社融增速动量均值。"""
    m2_m = compute_momentum(df["m2_yoy"]) if "m2_yoy" in df.columns else None
    sf_m = compute_momentum(df["social_financing"]) if "social_financing" in df.columns else None
    if m2_m is not None and sf_m is not None:
        return 0.5 * m2_m + 0.5 * sf_m
    if m2_m is not None:
        return m2_m
    if sf_m is not None:
        return sf_m
    return pd.Series(dtype=float)


def compute_asset_scores(growth: float, inflation: float, liquidity: float) -> dict[str, float]:
    """三维动量 → 各资产偏好得分 [-1, +1]。"""
    scores: dict[str, float] = {}
    inflation_penalty = -0.3 * max(0.0, inflation - 0.5)
    scores["股票"] = 0.45 * growth + 0.15 * inflation + inflation_penalty + 0.40 * liquidity
    scores["债券"] = -0.35 * growth - 0.35 * inflation + 0.30 * liquidity
    scores["商品"] = 0.40 * growth + 0.50 * inflation + 0.10 * liquidity
    scores["现金"] = -0.30 * growth + 0.30 * inflation - 0.40 * liquidity
    scores["黄金"] = -0.25 * growth + 0.40 * inflation + 0.35 * liquidity
    for key, value in scores.items():
        scores[key] = float(np.tanh(value))
    return scores


def get_regime_label(growth: float, inflation: float) -> str:
    """传统四象限标签（观察用，非交易信号）。"""
    if growth > 0 and inflation <= 0:
        return "复苏"
    if growth > 0 and inflation > 0:
        return "过热"
    if growth <= 0 and inflation > 0:
        return "滞胀"
    return "衰退"


def compute_merrill_clock_payload(
    series_or_frame: (
        Mapping[str, Sequence[tuple[date, float]]]
        | pd.DataFrame
        | Sequence[Mapping[str, Any]]
        | None
    ),
    *,
    report_date: date,
) -> dict[str, Any]:
    """从已加载序列/宽表计算美林时钟观察载荷（无网络）。"""
    frame, warnings = _normalize_to_script_frame(series_or_frame, report_date=report_date)
    if frame.empty:
        return _unavailable_payload(report_date, warnings or ["NO_MERRILL_CLOCK_INPUTS"])

    growth_m = compute_growth_momentum(frame)
    inflation_m = compute_inflation_momentum(frame)
    liquidity_m = compute_liquidity_momentum(frame)
    result = pd.DataFrame(
        {
            "growth_momentum": growth_m,
            "inflation_momentum": inflation_m,
            "liquidity_momentum": liquidity_m,
        }
    ).dropna(how="all")
    # 至少需要增长与通胀动量才能定象限；流动性可缺省为 0 并降级
    if result.empty or result["growth_momentum"].dropna().empty or result["inflation_momentum"].dropna().empty:
        return _unavailable_payload(
            report_date,
            _dedupe([*warnings, "MERRILL_CLOCK_MOMENTUM_INSUFFICIENT"]),
        )

    usable = result.dropna(subset=["growth_momentum", "inflation_momentum"])
    if usable.empty:
        return _unavailable_payload(
            report_date,
            _dedupe([*warnings, "MERRILL_CLOCK_MOMENTUM_INSUFFICIENT"]),
        )

    latest_index = usable.index[-1]
    latest = usable.loc[latest_index]
    growth = float(latest["growth_momentum"])
    inflation = float(latest["inflation_momentum"])
    liquidity_raw = latest.get("liquidity_momentum")
    if liquidity_raw is None or (isinstance(liquidity_raw, float) and math.isnan(liquidity_raw)) or pd.isna(
        liquidity_raw
    ):
        liquidity = 0.0
        warnings.append("LIQUIDITY_MOMENTUM_DEFAULT_ZERO")
    else:
        liquidity = float(liquidity_raw)

    regime = get_regime_label(growth, inflation)
    asset_scores = compute_asset_scores(growth, inflation, liquidity)
    ranked = sorted(asset_scores.items(), key=lambda item: item[1], reverse=True)
    top_asset, top_score = ranked[0]
    point_date = latest_index.date() if hasattr(latest_index, "date") else report_date

    # 可选增长代理（新订单/发电/货运）未接入系统源时仅提示，不单独把状态打成 degraded
    blocking = [item for item in warnings if not str(item).endswith("_UNAVAILABLE")]
    data_status = "complete" if not blocking else "degraded"
    return {
        "report_date": point_date.isoformat() if hasattr(point_date, "isoformat") else str(point_date)[:10],
        "requested_report_date": report_date.isoformat(),
        "data_status": data_status,
        "rule_version": MERRILL_CLOCK_RULE_VERSION,
        "growth_momentum": round(growth, 4),
        "inflation_momentum": round(inflation, 4),
        "liquidity_momentum": round(liquidity, 4),
        "regime_label": regime,
        "asset_scores": {key: round(value, 4) for key, value in asset_scores.items()},
        "top_asset": top_asset,
        "top_asset_score": round(float(top_score), 4),
        "headline": f"美林时钟：{regime} · 偏好{top_asset}",
        "warnings": _dedupe(warnings),
    }


def _normalize_to_script_frame(
    series_or_frame: (
        Mapping[str, Sequence[tuple[date, float]]]
        | pd.DataFrame
        | Sequence[Mapping[str, Any]]
        | None
    ),
    *,
    report_date: date,
) -> tuple[pd.DataFrame, list[str]]:
    warnings: list[str] = []
    if series_or_frame is None:
        return pd.DataFrame(), ["NO_MERRILL_CLOCK_INPUTS"]

    if isinstance(series_or_frame, pd.DataFrame):
        frame = _dataframe_to_script_columns(series_or_frame)
    elif isinstance(series_or_frame, Mapping):
        # Mapping → alias/series_data；宽表行列表走 Sequence 分支
        frame = _series_data_to_frame(series_or_frame)
    else:
        frame = _wide_rows_to_frame(list(series_or_frame))  # type: ignore[arg-type]

    if frame.empty:
        return frame, ["NO_MERRILL_CLOCK_INPUTS"]

    if not isinstance(frame.index, pd.DatetimeIndex):
        frame = frame.copy()
        frame.index = pd.to_datetime(frame.index)
    frame = frame.sort_index()
    frame = frame[frame.index.date <= report_date]
    if frame.empty:
        return frame, ["NO_MERRILL_CLOCK_INPUTS"]

    for column in frame.columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    warnings.extend(_missing_input_warnings(frame))
    return frame.dropna(how="all"), warnings


def _dataframe_to_script_columns(frame: pd.DataFrame) -> pd.DataFrame:
    renamed: dict[str, pd.Series] = {}
    for column in frame.columns:
        key = str(column)
        script_name = _WIDE_TO_SCRIPT_COLUMNS.get(key, key)
        if script_name in GROWTH_WEIGHTS or script_name in {
            "cpi_yoy",
            "ppi_yoy",
            "m2_yoy",
            "social_financing",
        }:
            renamed[script_name] = frame[column]
    if not renamed:
        return pd.DataFrame()
    out = pd.DataFrame(renamed)
    if not isinstance(out.index, pd.DatetimeIndex):
        out.index = pd.to_datetime(out.index)
    return out.sort_index()


def _series_data_to_frame(
    series_data: Mapping[str, Sequence[tuple[date, float]]],
) -> pd.DataFrame:
    columns: dict[str, pd.Series] = {}
    for key, points in series_data.items():
        script_name = _WIDE_TO_SCRIPT_COLUMNS.get(str(key), str(key))
        series = _to_series(points)
        if series.empty:
            continue
        columns[script_name] = series
    if not columns:
        return pd.DataFrame()
    return pd.DataFrame(columns).sort_index()


def _wide_rows_to_frame(wide_rows: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    if not wide_rows:
        return pd.DataFrame()
    records: list[dict[str, Any]] = []
    for row in wide_rows:
        row_date = row.get("trade_date") or row.get("biz_date") or row.get("date")
        if row_date is None:
            continue
        if hasattr(row_date, "isoformat") and not isinstance(row_date, str):
            ts = pd.Timestamp(row_date)
        else:
            ts = pd.Timestamp(str(row_date)[:10])
        record: dict[str, Any] = {"_date": ts}
        for field, script_name in _WIDE_TO_SCRIPT_COLUMNS.items():
            if field in row and row[field] is not None:
                try:
                    value = float(row[field])  # type: ignore[arg-type]
                except (TypeError, ValueError):
                    continue
                if math.isfinite(value):
                    record[script_name] = value
        if len(record) > 1:
            records.append(record)
    if not records:
        return pd.DataFrame()
    frame = pd.DataFrame(records).set_index("_date").sort_index()
    # 月度采样：每月保留最后一条（宽表可能是日频 ffill）
    month_keys = frame.index.to_period("M")
    return frame.groupby(month_keys, sort=True).tail(1)


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
    return pd.Series({point_date: value for point_date, value in rows}, dtype="float64").sort_index()


def _missing_input_warnings(frame: pd.DataFrame) -> list[str]:
    warnings: list[str] = []
    for column in _SYSTEM_GROWTH_COLUMNS:
        if column not in frame.columns or frame[column].dropna().empty:
            warnings.append(f"{column.upper()}_MISSING")
    for column in _OPTIONAL_GROWTH_COLUMNS:
        if column not in frame.columns or frame[column].dropna().empty:
            warnings.append(f"{column.upper()}_UNAVAILABLE")
    for column in _SYSTEM_INFLATION_COLUMNS:
        if column not in frame.columns or frame[column].dropna().empty:
            warnings.append(f"{column.upper()}_MISSING")
    for column in _SYSTEM_LIQUIDITY_COLUMNS:
        if column not in frame.columns or frame[column].dropna().empty:
            warnings.append(f"{column.upper()}_MISSING")
    return warnings


def _unavailable_payload(report_date: date, warnings: list[str]) -> dict[str, Any]:
    return {
        "report_date": report_date.isoformat(),
        "requested_report_date": report_date.isoformat(),
        "data_status": "unavailable",
        "rule_version": MERRILL_CLOCK_RULE_VERSION,
        "growth_momentum": None,
        "inflation_momentum": None,
        "liquidity_momentum": None,
        "regime_label": "不可用",
        "asset_scores": {},
        "top_asset": None,
        "top_asset_score": None,
        "headline": "美林时钟数据不足",
        "warnings": _dedupe(warnings),
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
