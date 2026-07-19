"""CTA 趋势跟踪观察载荷（无网络）。

从 toolkit/scripts/cta_trend_cn.py 抽取信号纯函数；输入为已加载价格序列。
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

CTA_TREND_RULE_VERSION = "rv_macro_cta_trend_cn_v1"
ASSET_LABELS = {
    "hs300": "沪深300",
    "csi500": "中证500",
    "copper": "铜",
    "nanhua": "南华商品",
}


def signal_ma_cross(price: pd.Series, short: int = 20, long: int = 60) -> pd.Series:
    ma_s = price.rolling(short).mean()
    ma_l = price.rolling(long).mean()
    sig = pd.Series(np.where(ma_s > ma_l, 1.0, -1.0), index=price.index)
    sig[ma_s.isna() | ma_l.isna()] = np.nan
    return sig


def signal_donchian(price: pd.Series, window: int = 20) -> pd.Series:
    high = price.rolling(window).max().shift(1)
    low = price.rolling(window).min().shift(1)
    sig = pd.Series(np.nan, index=price.index)
    sig[price > high] = 1.0
    sig[price < low] = -1.0
    return sig.ffill().fillna(0.0)


def signal_atr_position(
    price: pd.Series,
    atr_window: int = 14,
    target_vol: float = 0.01,
) -> pd.Series:
    daily_ret_std = np.log(price / price.shift(1)).rolling(atr_window).std()
    pos = (target_vol / daily_ret_std.replace(0, np.nan)).clip(0, 1.0)
    ma_sig = signal_ma_cross(price)
    return (pos * ma_sig.clip(0, 1)).fillna(0.0)


def compute_composite(price: pd.Series) -> pd.DataFrame:
    ma = signal_ma_cross(price)
    don = signal_donchian(price)
    atr = signal_atr_position(price)
    composite = np.tanh(ma * 0.4 + don * 0.3 + atr * 0.3)
    return pd.DataFrame(
        {
            "ma_signal": ma,
            "don_signal": don,
            "atr_position": atr,
            "composite": composite,
        }
    )


def trend_label(val: float) -> str:
    if val > 0.5:
        return "强多头"
    if val > 0.2:
        return "弱多头"
    if val > -0.2:
        return "震荡观望"
    if val > -0.5:
        return "弱空头"
    return "强空头"


def compute_cta_trend_payload(
    prices: Mapping[str, Sequence[tuple[date, float]]] | pd.DataFrame | None,
    *,
    report_date: date,
    min_history: int = 80,
) -> dict[str, Any]:
    frame, warnings = _normalize_prices(prices, report_date=report_date)
    if frame.empty:
        return _unavailable(report_date, warnings or ["NO_CTA_TREND_INPUTS"])

    asset_rows: list[dict[str, Any]] = []
    composites: list[float] = []
    for column in frame.columns:
        series = frame[column].dropna()
        if len(series) < min_history:
            warnings.append(f"{column.upper()}_HISTORY_SHORT")
            continue
        signals = compute_composite(series)
        latest = signals["composite"].dropna()
        if latest.empty:
            warnings.append(f"{column.upper()}_SIGNAL_EMPTY")
            continue
        value = float(latest.iloc[-1])
        composites.append(value)
        asset_rows.append(
            {
                "asset": column,
                "label": ASSET_LABELS.get(column, column),
                "composite": round(value, 4),
                "trend_label": trend_label(value),
                "as_of": latest.index[-1].date().isoformat(),
            }
        )

    if not asset_rows:
        return _unavailable(report_date, _dedupe([*warnings, "CTA_TREND_SIGNAL_INSUFFICIENT"]))

    avg = float(np.mean(composites))
    data_status = "complete" if not warnings else "degraded"
    bullish = sum(1 for row in asset_rows if row["composite"] > 0.2)
    bearish = sum(1 for row in asset_rows if row["composite"] < -0.2)
    return {
        "report_date": report_date.isoformat(),
        "data_status": data_status,
        "rule_version": CTA_TREND_RULE_VERSION,
        "observation_only": True,
        "formal_use_allowed": False,
        "avg_composite": round(avg, 4),
        "trend_label": trend_label(avg),
        "bullish_count": bullish,
        "bearish_count": bearish,
        "asset_signals": asset_rows,
        "headline": f"CTA趋势：{trend_label(avg)} · 均值{avg:+.2f}",
        "warnings": _dedupe(warnings),
    }


def _normalize_prices(
    prices: Mapping[str, Sequence[tuple[date, float]]] | pd.DataFrame | None,
    *,
    report_date: date,
) -> tuple[pd.DataFrame, list[str]]:
    warnings: list[str] = []
    if prices is None:
        return pd.DataFrame(), ["NO_CTA_TREND_INPUTS"]
    if isinstance(prices, pd.DataFrame):
        frame = prices.copy()
    else:
        columns: dict[str, pd.Series] = {}
        for key, points in prices.items():
            series = _to_series(points)
            if series.empty:
                warnings.append(f"{str(key).upper()}_MISSING")
                continue
            columns[str(key)] = series
        frame = pd.DataFrame(columns) if columns else pd.DataFrame()
    if frame.empty:
        return frame, warnings or ["NO_CTA_TREND_INPUTS"]
    if not isinstance(frame.index, pd.DatetimeIndex):
        frame.index = pd.to_datetime(frame.index)
    frame = frame.sort_index()
    frame = frame[frame.index.date <= report_date]
    for column in frame.columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.dropna(how="all"), warnings


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
    return pd.Series({ts: value for ts, value in rows}, dtype="float64").sort_index()


def _unavailable(report_date: date, warnings: list[str]) -> dict[str, Any]:
    return {
        "report_date": report_date.isoformat(),
        "data_status": "unavailable",
        "rule_version": CTA_TREND_RULE_VERSION,
        "observation_only": True,
        "formal_use_allowed": False,
        "avg_composite": None,
        "trend_label": "不可用",
        "bullish_count": 0,
        "bearish_count": 0,
        "asset_signals": [],
        "headline": "CTA趋势数据不足",
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
