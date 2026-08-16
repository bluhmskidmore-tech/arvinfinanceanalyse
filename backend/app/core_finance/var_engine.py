"""DORMANT: 无生产调用方，接线前必须补黄金测试（见 PRD v0.3 B3/FI-P2-09）。

参数法 VaR 引擎 — 基于 DV01 的单因子平行利率冲击 VaR。

公式:
  daily_vol_bp = annual_vol_bp / sqrt(252)
  单头寸 VaR = |DV01| × z_score × daily_vol_bp × sqrt(holding_period)
  组合 VaR = |Σ signed_DV01_i| × z_score × daily_vol_bp × sqrt(holding_period)

z_score: 95% = 1.6449, 99% = 2.3263
单位: DV01 为货币金额/1bp，波动率为年化收益率波动率（bp），VaR 输出为货币金额。
"""

from __future__ import annotations

import math
from decimal import ROUND_HALF_UP, Decimal

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
    """单头寸 VaR；DV01 单位为货币/1bp，波动率为年化收益率波动率（bp），结果为货币金额."""
    d = Decimal(str(dv01))
    vol = Decimal(str(annual_yield_vol_bp))
    if not vol.is_finite() or vol < 0:
        raise ValueError("annual_yield_vol_bp must be finite and >= 0")
    if any(not z_score.is_finite() or z_score <= 0 for z_score in (_Z_95, _Z_99)):
        raise ValueError("z_score must be finite and > 0")

    daily_vol_bp = vol / _SQRT_252
    abs_dv01 = abs(d)

    var_1d_95 = abs_dv01 * _Z_95 * daily_vol_bp
    var_1d_99 = abs_dv01 * _Z_99 * daily_vol_bp
    var_10d_99 = var_1d_99 * _SQRT_10

    # 显式 ROUND_HALF_UP，与全库舍入口径一致（2026-08 审计 SHR-01）。
    return {
        "var_1d_95": var_1d_95.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "var_1d_99": var_1d_99.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "var_10d_99": var_10d_99.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
    }


def compute_portfolio_var(
    positions: list[dict],
    *,
    annual_yield_vol_bp: Decimal | float = Decimal("80"),
    dv01_key: str = "dv01",
) -> dict[str, Decimal]:
    """组合 VaR；单一平行因子下先对 signed DV01 净额，再取绝对值计算."""
    total_dv01 = abs(sum((Decimal(str(p.get(dv01_key) or 0)) for p in positions), Decimal("0")))
    return compute_position_var(dv01=total_dv01, annual_yield_vol_bp=annual_yield_vol_bp)
