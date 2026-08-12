"""DCC-GARCH 动态相关观察载荷（无网络）。

与 toolkit/scripts/dcc_garch_cn.py 同口径：每资产先做 GARCH(1,1) 过滤得到
标准化残差 ε_t，再按 DCC 递推估计动态条件相关
    Q_t = (1-α-β)·Q̄ + α·ε_{t-1}·ε'_{t-1} + β·Q_{t-1}
    R_t = diag(Q_t)^{-1/2}·Q_t·diag(Q_t)^{-1/2}
其中 Q̄ 取标准化残差的无条件二阶矩 E[εε']，Q_0 = Q̄。
平均相关系数 = 全部两两配对（上三角、不含对角线）等权平均。
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from backend.app.core_finance.macro.helpers import dedupe_preserving_order as _dedupe
from backend.app.core_finance.macro.helpers import normalize_price_inputs as _normalize_price_inputs

DCC_GARCH_RULE_VERSION = "rv_macro_dcc_garch_cn_v2"
# DCC 递推参数（尽调笔记"慢速调整"档，与 toolkit/scripts/dcc_garch_cn.py 逐字一致）
DCC_ALPHA = 0.05
DCC_BETA = 0.93
# window 仅用于历史充足性闸门与载荷兼容字段，不再是相关性计算窗口。
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


def _normalize_corr(q: np.ndarray) -> np.ndarray:
    """R_t = diag(Q_t)^{-1/2} · Q_t · diag(Q_t)^{-1/2}"""
    d = np.sqrt(np.clip(np.diag(q), 1e-12, None))
    r = q / np.outer(d, d)
    np.fill_diagonal(r, 1.0)
    return r


def _dcc_correlation_paths(
    std_resid: pd.DataFrame,
) -> tuple[dict[str, pd.Series], pd.Series, pd.DataFrame]:
    """DCC 递推条件相关（与脚本 compute_dcc 的递推段逐字一致，去掉打印）。

    返回 (pair_series, avg_series, latest_corr)：
    - pair_series: 上三角两两配对的条件相关时序
    - avg_series: 全配对等权平均（不含对角线）
    - latest_corr: 最新一期条件相关矩阵
    """
    cols = std_resid.columns.tolist()
    pairs = [(i, j) for i in range(len(cols)) for j in range(i + 1, len(cols))]

    eps = std_resid.values.astype(float)
    n_obs = len(eps)
    # Q̄ 用标准化残差的无条件二阶矩 E[εε']，与递推项 ε_{t-1}·ε'_{t-1} 同口径；
    # R_t 的对角归一化保证输出恒为合法相关系数。
    q_bar = eps.T @ eps / n_obs
    q_t = q_bar.copy()
    corr_path = np.empty((n_obs, len(cols), len(cols)))
    corr_path[0] = _normalize_corr(q_t)  # Q_0 = Q̄ 初始化
    for t in range(1, n_obs):
        e_prev = eps[t - 1]
        q_t = (1.0 - DCC_ALPHA - DCC_BETA) * q_bar + DCC_ALPHA * np.outer(e_prev, e_prev) + DCC_BETA * q_t
        corr_path[t] = _normalize_corr(q_t)

    pair_series: dict[str, pd.Series] = {}
    for i, j in pairs:
        key = f"{cols[i]}_{cols[j]}"
        pair_series[key] = pd.Series(corr_path[:, i, j], index=std_resid.index, name=key)

    pair_df = pd.DataFrame(pair_series)
    # 平均相关系数 = 全部两两配对（上三角）等权平均，不含对角线
    avg_series = pair_df.mean(axis=1)

    latest_corr = pd.DataFrame(corr_path[-1], index=cols, columns=cols)

    return pair_series, avg_series, latest_corr


def compute_dcc(
    log_ret: pd.DataFrame,
) -> tuple[dict[str, pd.Series], pd.Series, pd.DataFrame]:
    """与脚本 compute_dcc 同口径：GARCH(1,1) 标准化 → DCC 递推。"""
    std_resid = pd.DataFrame(
        {col: garch_standardize(log_ret[col]) for col in log_ret.columns}
    ).dropna()
    return _dcc_correlation_paths(std_resid)


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
    """DCC 递推观察卡载荷。

    相关性口径为真 DCC 递推（见模块 docstring），全样本递推而非滚动窗口；
    ``window`` 保留为历史充足性闸门与载荷兼容字段。
    """
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
    pair_series_map, _avg_series, _latest_corr = _dcc_correlation_paths(std_resid)
    pair_avgs: list[float] = []
    pair_rows: list[dict[str, Any]] = []
    for i, a in enumerate(cols):
        for b in cols[i + 1 :]:
            # 退化输入可能产出非有限相关值；跳过的腿会偏移 avg_correlation，
            # 必须显式警告，不能静默吞掉后仍标 complete。
            value = float(pair_series_map[f"{a}_{b}"].iloc[-1])
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
