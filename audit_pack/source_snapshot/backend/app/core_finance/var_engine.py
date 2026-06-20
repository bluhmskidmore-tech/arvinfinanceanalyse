"""参数法 VaR 引擎 — 基于 DV01 的利率风险 VaR 计算（自 MOSS-V2 core_finance 迁入）。

公式:
  daily_vol_bp = annual_vol_bp / sqrt(252)
  VaR = |DV01| × z_score × daily_vol_bp × sqrt(holding_period)

z_score: 95% = 1.645, 99% = 2.326
"""

from __future__ import annotations

import math
from decimal import Decimal

_Z_95 = Decimal("1.6449")
_Z_99 = Decimal("2.3263")
_TRADING_DAYS = Decimal("252")
_SQRT_252 = Decimal(str(math.sqrt(252)))
_SQRT_10 = Decimal(str(math.sqrt(10)))


def compute_position_var(
    *,
    dv01: Decimal | float,
    annual_yield_vol_bp: Decimal | float = Decimal("80"),
) -> dict[str, Decimal]:
    """单头寸参数法 VaR，返回 var_1d_95 / var_1d_99 / var_10d_99."""
    d = Decimal(str(dv01))
    vol = Decimal(str(annual_yield_vol_bp))
    daily_vol_bp = vol / _SQRT_252
    abs_dv01 = abs(d)

    var_1d_95 = abs_dv01 * _Z_95 * daily_vol_bp
    var_1d_99 = abs_dv01 * _Z_99 * daily_vol_bp
    var_10d_99 = var_1d_99 * _SQRT_10

    return {
        "var_1d_95": var_1d_95.quantize(Decimal("0.01")),
        "var_1d_99": var_1d_99.quantize(Decimal("0.01")),
        "var_10d_99": var_10d_99.quantize(Decimal("0.01")),
    }


def compute_portfolio_var(
    positions: list[dict],
    *,
    annual_yield_vol_bp: Decimal | float = Decimal("80"),
    dv01_key: str = "dv01",
) -> dict[str, Decimal]:
    """组合级参数法 VaR（假设完全相关，即简单加总 DV01）."""
    total_dv01 = sum((abs(Decimal(str(p.get(dv01_key) or 0))) for p in positions), Decimal("0"))
    return compute_position_var(dv01=total_dv01, annual_yield_vol_bp=annual_yield_vol_bp)
