"""风险平价影子权重观察载荷（无网络）。

从 toolkit/scripts/risk_parity_cn.py 抽取协方差 / 风险贡献求解；不做再平衡执行。
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import minimize

RISK_PARITY_RULE_VERSION = "rv_macro_risk_parity_cn_v1"
ASSET_LABELS = {
    "hs300": "沪深300",
    "csi500": "中证500",
    "copper": "铜",
    "nanhua": "南华商品",
}
BUDGET_MAP = {
    "复苏": {"hs300": 0.35, "csi500": 0.25, "copper": 0.20, "nanhua": 0.20},
    "过热": {"hs300": 0.25, "csi500": 0.15, "copper": 0.25, "nanhua": 0.35},
    "滞胀": {"hs300": 0.15, "csi500": 0.10, "copper": 0.30, "nanhua": 0.45},
    "衰退": {"hs300": 0.30, "csi500": 0.20, "copper": 0.20, "nanhua": 0.30},
}


def calc_cov(prices: pd.DataFrame) -> tuple[np.ndarray, pd.DataFrame, np.ndarray]:
    log_ret = np.log(prices / prices.shift(1)).dropna()
    cov = log_ret.cov().values * 252
    vol = np.sqrt(np.diag(cov))
    return cov, log_ret, vol


def risk_contributions(weights: np.ndarray, cov: np.ndarray) -> tuple[np.ndarray, float]:
    w = np.asarray(weights, dtype=float)
    sig = float(np.sqrt(w @ cov @ w))
    if sig <= 0:
        return np.zeros_like(w), 0.0
    mrc = cov @ w / sig
    return w * mrc, sig


def solve_risk_parity(cov: np.ndarray) -> np.ndarray:
    n = cov.shape[0]
    w0 = np.ones(n) / n

    def objective(w: np.ndarray) -> float:
        rc, sig = risk_contributions(w, cov)
        return float(np.sum((rc - sig / n) ** 2))

    result = minimize(
        objective,
        w0,
        method="SLSQP",
        bounds=[(1e-6, 1.0)] * n,
        constraints=[{"type": "eq", "fun": lambda w: float(np.sum(w)) - 1.0}],
        options={"ftol": 1e-12, "maxiter": 2000},
    )
    return result.x


def solve_risk_budget(cov: np.ndarray, budget: Sequence[float]) -> np.ndarray:
    n = cov.shape[0]
    b = np.asarray(budget, dtype=float)
    b = b / b.sum()

    def objective(w: np.ndarray) -> float:
        rc, sig = risk_contributions(w, cov)
        if sig <= 0:
            return 1.0
        return float(np.sum((rc / sig - b) ** 2))

    result = minimize(
        objective,
        b.copy(),
        method="SLSQP",
        bounds=[(1e-6, 1.0)] * n,
        constraints=[{"type": "eq", "fun": lambda w: float(np.sum(w)) - 1.0}],
        options={"ftol": 1e-12, "maxiter": 2000},
    )
    return result.x


def compute_risk_parity_payload(
    prices: Mapping[str, Sequence[tuple[date, float]]] | pd.DataFrame | None,
    *,
    report_date: date,
    clock_phase: str | None = None,
    min_history: int = 100,
) -> dict[str, Any]:
    frame, warnings = _normalize_prices(prices, report_date=report_date)
    if frame.shape[1] < 2:
        return _unavailable(report_date, warnings or ["RISK_PARITY_NEED_MULTI_ASSET"])

    usable = frame.dropna(how="any")
    if len(usable) < min_history:
        return _unavailable(
            report_date,
            _dedupe([*warnings, "RISK_PARITY_HISTORY_SHORT", f"rows={len(usable)}"]),
        )

    cov, _log_ret, vol = calc_cov(usable)
    if not np.all(np.isfinite(cov)):
        return _unavailable(report_date, _dedupe([*warnings, "RISK_PARITY_COV_INVALID"]))

    columns = list(usable.columns)
    w_rp = solve_risk_parity(cov)
    phase = clock_phase if clock_phase in BUDGET_MAP else "衰退"
    if clock_phase and clock_phase not in BUDGET_MAP:
        warnings.append(f"CLOCK_PHASE_FALLBACK:{clock_phase}->{phase}")
    budget = [BUDGET_MAP[phase].get(col, 1.0 / len(columns)) for col in columns]
    w_rb = solve_risk_budget(cov, budget)
    rc_rp, sig_rp = risk_contributions(w_rp, cov)
    rc_rb, sig_rb = risk_contributions(w_rb, cov)

    weights = []
    for i, col in enumerate(columns):
        weights.append(
            {
                "asset": col,
                "label": ASSET_LABELS.get(col, col),
                "rp_weight_pct": round(float(w_rp[i]) * 100, 2),
                "rb_weight_pct": round(float(w_rb[i]) * 100, 2),
                "ann_vol_pct": round(float(vol[i]) * 100, 2),
                "rp_risk_contrib_pct": round(float(rc_rp[i] / sig_rp * 100), 2) if sig_rp else None,
            }
        )

    top = max(weights, key=lambda item: item["rp_weight_pct"])
    data_status = "complete" if not warnings else "degraded"
    return {
        "report_date": report_date.isoformat(),
        "data_status": data_status,
        "rule_version": RISK_PARITY_RULE_VERSION,
        "observation_only": True,
        "formal_use_allowed": False,
        "shadow": True,
        "clock_phase": phase,
        "portfolio_vol_rp_pct": round(float(sig_rp) * 100, 2),
        "portfolio_vol_rb_pct": round(float(sig_rb) * 100, 2),
        "weights": weights,
        "top_asset": top["label"],
        "top_weight_pct": top["rp_weight_pct"],
        "headline": f"风险平价影子：{phase} · 组合波动{sig_rp * 100:.1f}%",
        "warnings": _dedupe(warnings),
    }


def _normalize_prices(
    prices: Mapping[str, Sequence[tuple[date, float]]] | pd.DataFrame | None,
    *,
    report_date: date,
) -> tuple[pd.DataFrame, list[str]]:
    warnings: list[str] = []
    if prices is None:
        return pd.DataFrame(), ["NO_RISK_PARITY_INPUTS"]
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
        return frame, warnings or ["NO_RISK_PARITY_INPUTS"]
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
        "rule_version": RISK_PARITY_RULE_VERSION,
        "observation_only": True,
        "formal_use_allowed": False,
        "shadow": True,
        "clock_phase": None,
        "portfolio_vol_rp_pct": None,
        "portfolio_vol_rb_pct": None,
        "weights": [],
        "top_asset": None,
        "top_weight_pct": None,
        "headline": "风险平价影子数据不足",
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
