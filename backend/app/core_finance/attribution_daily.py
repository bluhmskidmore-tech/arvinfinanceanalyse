"""
单日 fact_attribution_daily 行分解（纯函数）。

与区间 Campisi 共用 bond_four_effects + 市场插值/利差变动逻辑（见 campisi.py）。
映射约定：
- carry_return ← income_return；天数口径 num_days = (report_date - prev_date).days
  （不含头含尾；同日窗口下限 1 天），与区间 Campisi 一致
- curve_return ← treasury_effect：固定剩余期限 T(prev) 上，期初→期末国债曲线的平移（benchmark_yield_change）
- spread_return ← spread_effect
- rolldown_return ← 在**期末**国债曲线上取两点：锚点为报告日剩余期限 T(report)，
  滚动点为 T(report) − Δ（Δ = (report_date - prev_date).days / 365；
  Gate 1 Option A 时间锚，与 docs/calc_rules.md 桥接归因口径一致）；
  rolldown = +MD × (y(T(report)) − y(T(report)−Δ)) / 100 × MV_end，
  向上倾斜的曲线产生正的 rolldown 收益；
  与 curve_return 相加近似于债券沿曲线的总基准价格效应（AC 类为 0，与四效应一致）
- fx_return ← 来自 fact_pnl_daily.fx_pnl（若有）
- total_return ← fact_pnl_daily.total_pnl（正式闭合）
- residual_return ← total - carry - rolldown - spread - curve - fx
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from .bond_duration import infer_accounting_class
from .bond_four_effects import compute_bond_four_effects
from .campisi import (
    _coupon_freq,
    _years_to_maturity,
    benchmark_yield_change_decimal,
    credit_spread_change_decimal,
    infer_credit_rating_from_asset_class,
    interpolate_treasury_yield_pct,
)
from .field_normalization import ACCOUNTING_BASIS_AC
from .safe_decimal import safe_decimal


def compute_daily_attribution_row(
    merged_position: dict[str, Any],
    market_start: dict[str, Any] | None,
    market_end: dict[str, Any] | None,
    prev_date: date,
    report_date: date,
    *,
    total_pnl: float | None,
    fx_pnl: float | None = None,
) -> dict[str, float]:
    """
    merged_position: 与 campisi_attribution 单条相同，需含
    market_value_start/end, face_value_start, coupon_rate_start,
    yield_to_maturity_start, asset_class_start, maturity_date_start, bond_code。
    total_pnl: 当日 fact_pnl_daily.total_pnl；若 None 则用模型 total_return。
    """
    num_days = max((report_date - prev_date).days, 1)
    mat = merged_position.get("maturity_date_start")
    # None 先行排除与 hasattr 语义等价（hasattr(None, "date") 恒为 False），便于 mypy 收窄。
    if mat is not None and hasattr(mat, "date"):
        mat_d = mat.date()
    elif isinstance(mat, date):
        mat_d = mat
    else:
        mat_d = None
    years = _years_to_maturity(mat_d, prev_date)
    bench_dec = benchmark_yield_change_decimal(market_start, market_end, years)
    rating = infer_credit_rating_from_asset_class(merged_position.get("asset_class_start"))
    spread_dec = credit_spread_change_decimal(market_start, market_end, rating)
    cf = _coupon_freq(merged_position.get("asset_class_start"))
    bond = {
        "bond_code": merged_position.get("bond_code") or merged_position.get("instrument_id"),
        "market_value_start": merged_position.get("market_value_start"),
        "market_value_end": merged_position.get("market_value_end"),
        "face_value_start": merged_position.get("face_value_start"),
        "coupon_rate_start": merged_position.get("coupon_rate_start"),
        "yield_to_maturity_start": merged_position.get("yield_to_maturity_start"),
        "asset_class_start": merged_position.get("asset_class_start"),
        "maturity_date_start": mat_d,
        "accrued_interest_start": merged_position.get("accrued_interest_start"),
        "accrued_interest_end": merged_position.get("accrued_interest_end"),
    }
    fx = compute_bond_four_effects(
        bond, num_days, bench_dec, spread_dec, prev_date, coupon_frequency=cf
    )
    # Effects and residual are combined in the Decimal domain to avoid float
    # subtraction error in the residual identity; converted to float only at
    # the returned dict boundary (output contract stays float, per callers).
    carry_dec = fx["income_return"]
    curve_dec = fx["treasury_effect"]
    spread_ret_dec = fx["spread_effect"]
    _ZERO = Decimal("0")
    if infer_accounting_class(merged_position.get("asset_class_start")) == ACCOUNTING_BASIS_AC:
        rolldown_dec = _ZERO
    elif not market_end or mat_d is None:
        rolldown_dec = _ZERO
    else:
        period_days = max((report_date - prev_date).days, 0)
        current_years = _years_to_maturity(mat_d, report_date)
        if period_days <= 0 or current_years <= 0:
            rolldown_dec = _ZERO
        else:
            rolled_years = max(float(current_years) - (period_days / 365), 0.0)
            current_rate = interpolate_treasury_yield_pct(market_end, current_years)
            rolled_rate = interpolate_treasury_yield_pct(market_end, rolled_years)
            roll_fx = compute_bond_four_effects(
                bond,
                num_days,
                bench_dec,
                spread_dec,
                report_date,
                coupon_frequency=cf,
            )
            rate_delta = Decimal(str((current_rate - rolled_rate) / 100.0))
            rolldown_dec = (
                safe_decimal(roll_fx["mod_duration"])
                * rate_delta
                * safe_decimal(merged_position.get("market_value_end"))
            )
    fx_ret_dec = safe_decimal(fx_pnl)
    if total_pnl is not None:
        total_dec = safe_decimal(total_pnl)
    else:
        total_dec = fx["total_return"]
    residual_dec = total_dec - carry_dec - rolldown_dec - spread_ret_dec - curve_dec - fx_ret_dec
    return {
        "carry_return": float(carry_dec),
        "rolldown_return": float(rolldown_dec),
        "spread_return": float(spread_ret_dec),
        "curve_return": float(curve_dec),
        "fx_return": float(fx_ret_dec),
        "total_return": float(total_dec),
        "residual_return": float(residual_dec),
    }
