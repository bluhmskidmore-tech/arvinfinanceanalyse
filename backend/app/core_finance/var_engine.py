"""参数法 VaR 引擎 — 基于 DV01 的利率风险 VaR 计算（自 MOSS-V2 core_finance 迁入）。

公式:
  daily_vol_bp = annual_vol_bp / sqrt(252)
  VaR = |DV01| × z_score × daily_vol_bp × sqrt(holding_period)

z_score: 95% = 1.645, 99% = 2.326
"""

from __future__ import annotations

import math

_Z_95 = 1.6449
_Z_99 = 2.3263
_TRADING_DAYS = 252


def compute_position_var(
    *,
    dv01: float,
    annual_yield_vol_bp: float = 80.0,
) -> dict[str, float]:
    """单头寸参数法 VaR，返回 var_1d_95 / var_1d_99 / var_10d_99."""
    daily_vol_bp = annual_yield_vol_bp / math.sqrt(_TRADING_DAYS)
    abs_dv01 = abs(dv01)

    var_1d_95 = abs_dv01 * _Z_95 * daily_vol_bp
    var_1d_99 = abs_dv01 * _Z_99 * daily_vol_bp
    var_10d_99 = var_1d_99 * math.sqrt(10)

    return {
        "var_1d_95": round(var_1d_95, 2),
        "var_1d_99": round(var_1d_99, 2),
        "var_10d_99": round(var_10d_99, 2),
    }


def compute_portfolio_var(
    positions: list[dict],
    *,
    annual_yield_vol_bp: float = 80.0,
    dv01_key: str = "dv01",
) -> dict[str, float]:
    """组合级参数法 VaR（假设完全相关，即简单加总 DV01）."""
    total_dv01 = sum(abs(p.get(dv01_key) or 0.0) for p in positions)
    return compute_position_var(dv01=total_dv01, annual_yield_vol_bp=annual_yield_vol_bp)
