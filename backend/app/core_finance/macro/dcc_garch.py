"""DCC-GARCH 风格滚动相关观察载荷（无网络）。

从 toolkit/scripts/dcc_garch_cn.py 抽取 GARCH 标准化 + 滚动相关摘要。
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from app.core_finance.macro.helpers import dedupe_preserving_order as _dedupe
from app.core_finance.macro.helpers import normalize_price_inputs as _normalize_price_inputs

DCC_GARCH_RULE_VERSION = "rv_macro_dcc_garch_cn_v1"
DEFAULT_WINDOW = 60
ASSET_LABELS = {
    "hs300": "沪深300",
    "csi500": "中证500",
    "copper": "铜",
    "nanhua": "南华商品",
}


def garch_standardize(
    series: pd.Series,
    *,
    omega: float = 1e-6,
    alpha: float = 0.1,
    beta: float = 0.85,
) -> pd.Series:
    r = series.dropna().astype(float)
    if r.empty:
        return pd.Series(dtype=float)
    values = r.values
    n = len(values)
    sigma2 = np.empty(n)
    sigma2[0] = max(float(np.var(values)), 1e-8)
    for t in range(1, n):
        sigma2[t] = max(omega + alpha * values[t - 1] ** 2 + beta * sigma2[t - 1], 1e-10)
    return pd.Series(values / np.sqrt(sigma2), index=r.index, name=series.name)


def classify_warning(avg: float) -> str:
    if avg > 0.85:
        return "红色预警"
    if avg > 0.70:
        return "黄色预警"
    return "正常"


def compute_dcc_garch_payload(
    prices: Mapping[str, Sequence[tuple[date, float]]] | pd.DataFrame | None,
    *,
    report_date: date,
    window: int = DEFAULT_WINDOW,
    min_assets: int = 2,
    min_history: int = 120,
) -> dict[str, Any]:
    frame, warnings = _normalize_price_inputs(
        prices, report_date=report_date, missing_token="NO_DCC_GARCH_INPUTS"
    )
    if frame.shape[1] < min_assets:
        return _unavailable(report_date, warnings or ["DCC_GARCH_NEED_MULTI_ASSET"])

    usable = frame.dropna(how="any")
    if len(usable) < min_history:
        return _unavailable(
            report_date,
            _dedupe([*warnings, "DCC_GARCH_HISTORY_SHORT", f"DCC_GARCH_HISTORY_ROWS_{len(usable)}"]),
        )

    log_ret = np.log(usable / usable.shift(1)).dropna()
    if len(log_ret) < window // 2:
        return _unavailable(report_date, _dedupe([*warnings, "DCC_GARCH_RETURNS_SHORT"]))

    std_resid = pd.DataFrame({col: garch_standardize(log_ret[col]) for col in log_ret.columns}).dropna()
    if std_resid.shape[1] < min_assets or len(std_resid) < window // 2:
        return _unavailable(report_date, _dedupe([*warnings, "DCC_GARCH_STANDARDIZE_FAILED"]))

    cols = list(std_resid.columns)
    rolling = std_resid.rolling(window=window, min_periods=max(window // 2, 20)).corr()
    pair_avgs: list[float] = []
    pair_rows: list[dict[str, Any]] = []
    for i, a in enumerate(cols):
        for b in cols[i + 1 :]:
            # 单个配对提取失败必须显式可见：跳过的腿会偏移 avg_correlation，
            # 不能静默吞掉后仍标 complete。
            try:
                series = rolling.loc[(slice(None), a), b]
                series.index = series.index.droplevel(1)
            except KeyError:
                warnings.append(f"DCC_GARCH_PAIR_SKIPPED_{a.upper()}_{b.upper()}")
                continue
            latest = series.dropna()
            if latest.empty:
                warnings.append(f"DCC_GARCH_PAIR_SKIPPED_{a.upper()}_{b.upper()}")
                continue
            value = float(latest.iloc[-1])
            if not math.isfinite(value):
                warnings.append(f"DCC_GARCH_PAIR_SKIPPED_{a.upper()}_{b.upper()}")
                continue
            pair_avgs.append(value)
            pair_rows.append(
                {
                    "pair": f"{a}_{b}",
                    "label": f"{ASSET_LABELS.get(a, a)}/{ASSET_LABELS.get(b, b)}",
                    "corr": round(value, 4),
                }
            )

    if not pair_avgs:
        return _unavailable(report_date, _dedupe([*warnings, "DCC_GARCH_CORR_EMPTY"]))

    avg = float(np.mean(pair_avgs))
    warning = classify_warning(avg)
    data_status = "complete" if not warnings else "degraded"
    return {
        "report_date": report_date.isoformat(),
        "data_status": data_status,
        "rule_version": DCC_GARCH_RULE_VERSION,
        "observation_only": True,
        "formal_use_allowed": False,
        "avg_correlation": round(avg, 4),
        "warning_level": warning,
        "pair_correlations": sorted(pair_rows, key=lambda item: abs(item["corr"]), reverse=True)[:8],
        "asset_count": len(cols),
        "window": window,
        "headline": f"DCC相关：{warning} · 均值{avg:.2f}",
        "warnings": _dedupe(warnings),
    }


def _unavailable(report_date: date, warnings: list[str]) -> dict[str, Any]:
    return {
        "report_date": report_date.isoformat(),
        "data_status": "unavailable",
        "rule_version": DCC_GARCH_RULE_VERSION,
        "observation_only": True,
        "formal_use_allowed": False,
        "avg_correlation": None,
        "warning_level": "不可用",
        "pair_correlations": [],
        "asset_count": 0,
        "window": DEFAULT_WINDOW,
        "headline": "DCC相关数据不足",
        "warnings": _dedupe(warnings),
    }
