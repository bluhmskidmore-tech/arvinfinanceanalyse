"""风险平价影子权重观察载荷（无网络）。

从 toolkit/scripts/risk_parity_cn.py 抽取协方差 / 风险贡献求解；不做再平衡执行。

资产宇宙与风险预算以本模块为系统权威口径：系统数据源
（macro/toolkit/system_sources.py）只提供沪深300 / 中证500 / 铜 / 南华商品，
因此 BUDGET_MAP 是 4 资产；脚本侧含黄金、原油的 5 资产预算依赖 WindPy 研究数据，
两者的分叉是数据可得性决定的，不是同步遗漏（2026-09-18 审计裁定）。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from backend.app.core_finance.macro.helpers import dedupe_preserving_order as _dedupe
from backend.app.core_finance.macro.helpers import normalize_price_inputs as _normalize_price_inputs


def _minimize(*args: Any, **kwargs: Any) -> Any:
    # 延迟导入：scipy 冷导入约 300ms，不应挂在 API 路由导入链上。
    from scipy.optimize import minimize

    return minimize(*args, **kwargs)

RISK_PARITY_RULE_VERSION = "rv_macro_risk_parity_cn_v2"
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
# economic_cycle.compute_economic_cycle 输出的英文象限标识符 -> BUDGET_MAP 的中文键。
# 只映射该模块实际输出的取值（recovery/overheat/stagflation/recession），
# 避免传入英文标识符时静默落到 BUDGET_MAP 未命中分支的"衰退"回退。
_CLOCK_PHASE_EN_TO_CN = {
    "recovery": "复苏",
    "overheat": "过热",
    "stagflation": "滞胀",
    "recession": "衰退",
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
    weights, _ = solve_risk_parity_with_status(cov)
    return weights


def solve_risk_parity_with_status(cov: np.ndarray) -> tuple[np.ndarray, bool]:
    n = cov.shape[0]
    w0 = np.ones(n) / n

    def objective(w: np.ndarray) -> float:
        rc, sig = risk_contributions(w, cov)
        return float(np.sum((rc - sig / n) ** 2))

    result = _minimize(
        objective,
        w0,
        method="SLSQP",
        bounds=[(1e-6, 1.0)] * n,
        constraints=[{"type": "eq", "fun": lambda w: float(np.sum(w)) - 1.0}],
        options={"ftol": 1e-12, "maxiter": 2000},
    )
    return _normalized_weights(result.x), bool(result.success)


def solve_risk_budget(cov: np.ndarray, budget: Sequence[float]) -> np.ndarray:
    weights, _ = solve_risk_budget_with_status(cov, budget)
    return weights


def solve_risk_budget_with_status(
    cov: np.ndarray,
    budget: Sequence[float],
) -> tuple[np.ndarray, bool]:
    n = cov.shape[0]
    b = np.asarray(budget, dtype=float)
    b = b / b.sum()

    def objective(w: np.ndarray) -> float:
        rc, sig = risk_contributions(w, cov)
        if sig <= 0:
            return 1.0
        return float(np.sum((rc / sig - b) ** 2))

    result = _minimize(
        objective,
        b.copy(),
        method="SLSQP",
        bounds=[(1e-6, 1.0)] * n,
        constraints=[{"type": "eq", "fun": lambda w: float(np.sum(w)) - 1.0}],
        options={"ftol": 1e-12, "maxiter": 2000},
    )
    return _normalized_weights(result.x), bool(result.success)


def _normalized_weights(weights: np.ndarray) -> np.ndarray:
    w = np.asarray(weights, dtype=float)
    total = float(w.sum())
    if total > 0:
        return w / total
    return w


def _valid_risk_allocation(weights: np.ndarray, cov: np.ndarray, budget: Sequence[float]) -> bool:
    w = np.asarray(weights, dtype=float)
    target = np.asarray(budget, dtype=float)
    if w.shape != target.shape or not np.all(np.isfinite(w)) or np.any(w <= 0):
        return False
    roundoff = len(w) * np.finfo(float).eps
    if not np.isclose(w.sum(), 1.0, rtol=0.0, atol=roundoff):
        return False
    # Scale by asset variance before testing cancellation, so the tolerance is
    # dimensionless and does not reject small but valid portfolio volatility.
    scaled_cov = cov / float(np.max(np.diag(cov)))
    variance = float(w @ scaled_cov @ w)
    if not np.isfinite(variance) or variance <= roundoff:
        return False
    risk_shares = w * (scaled_cov @ w) / variance
    target = target / target.sum()
    # Shares are displayed to 0.01 percentage point: permit at most one display
    # quantum of target residual, independent of covariance/return units.
    return bool(
        np.all(np.isfinite(risk_shares))
        and np.allclose(risk_shares, target, rtol=0.0, atol=1e-4)
    )


def compute_risk_parity_payload(
    prices: Mapping[str, Sequence[tuple[date, float]]] | pd.DataFrame | None,
    *,
    report_date: date,
    clock_phase: str | None = None,
    min_history: int = 100,
) -> dict[str, Any]:
    frame, warnings = _normalize_price_inputs(
        prices, report_date=report_date, missing_token="NO_RISK_PARITY_INPUTS"
    )
    if frame.shape[1] < 2:
        return _unavailable(report_date, warnings or ["RISK_PARITY_NEED_MULTI_ASSET"])

    usable = frame.dropna(how="any")
    if len(usable) < min_history:
        return _unavailable(
            report_date,
            _dedupe([*warnings, "RISK_PARITY_HISTORY_SHORT", f"RISK_PARITY_HISTORY_ROWS_{len(usable)}"]),
        )

    cov, _log_ret, vol = calc_cov(usable)
    if not np.all(np.isfinite(cov)):
        return _unavailable(report_date, _dedupe([*warnings, "RISK_PARITY_COV_INVALID"]))
    # 任一常数资产的风险贡献恒为零，无法满足每个资产的正风险预算。
    # 仅检查总方差会放行“几乎全仓常数资产”的退化解。
    if np.any(np.diag(cov) <= 0):
        return _unavailable(report_date, _dedupe([*warnings, "RISK_PARITY_COV_DEGENERATE"]))

    columns = list(usable.columns)
    w_rp, rp_converged = solve_risk_parity_with_status(cov)
    if not rp_converged:
        warnings.append("RISK_PARITY_SOLVER_NOT_CONVERGED")
    if clock_phase in BUDGET_MAP:
        phase = clock_phase
    elif clock_phase in _CLOCK_PHASE_EN_TO_CN:
        phase = _CLOCK_PHASE_EN_TO_CN[clock_phase]
    else:
        phase = "衰退"
    if clock_phase is None:
        warnings.append("CLOCK_PHASE_MISSING_DEFAULT_RECESSION")
    elif clock_phase not in BUDGET_MAP and clock_phase not in _CLOCK_PHASE_EN_TO_CN:
        warnings.append(f"CLOCK_PHASE_FALLBACK:{clock_phase}->{phase}")
    budget = [BUDGET_MAP[phase].get(col, 1.0 / len(columns)) for col in columns]
    w_rb, rb_converged = solve_risk_budget_with_status(cov, budget)
    if not rb_converged:
        warnings.append("RISK_BUDGET_SOLVER_NOT_CONVERGED")
    if not _valid_risk_allocation(w_rp, cov, [1.0 / len(columns)] * len(columns)):
        return _unavailable(report_date, _dedupe([*warnings, "RISK_PARITY_SOLUTION_INVALID"]))
    if not _valid_risk_allocation(w_rb, cov, budget):
        return _unavailable(report_date, _dedupe([*warnings, "RISK_BUDGET_SOLUTION_INVALID"]))
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
