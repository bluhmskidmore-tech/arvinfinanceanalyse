"""
单日 fact_attribution_daily 行分解（纯函数）。

与区间 Campisi 共用 bond_four_effects + 市场插值/利差变动逻辑（见 campisi.py）。
映射约定：
- carry_return ← income_return
- curve_return ← treasury_effect：固定剩余期限 T(prev) 上，期初→期末国债曲线的平移（benchmark_yield_change）
- spread_return ← spread_effect
- rolldown_return ← 在**期末**国债曲线上，因剩余期限从 T(prev) 滑向 T(report) 带来的基准收益率差 × (-MD×MV)；
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
    if hasattr(mat, "date"):
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
    carry = float(fx["income_return"])
    curve = float(fx["treasury_effect"])
    spread = float(fx["spread_effect"])
    mod_dur = fx["mod_duration"]
    mv_start_dec = safe_decimal(merged_position.get("market_value_start"))
    if infer_accounting_class(merged_position.get("asset_class_start")) == "AC":
        rolldown = 0.0
    elif not market_end or mat_d is None:
        rolldown = 0.0
    else:
        T_prev = _years_to_maturity(mat_d, prev_date)
        T_rep = _years_to_maturity(mat_d, report_date)
        if T_rep >= T_prev:
            rolldown = 0.0
        else:
            y_pe = interpolate_treasury_yield_pct(market_end, T_prev)
            y_re = interpolate_treasury_yield_pct(market_end, T_rep)
            bench_roll_dec = Decimal(str((y_re - y_pe) / 100.0))
            rolldown = float(-mod_dur * bench_roll_dec * mv_start_dec)
    fx_ret = float(fx_pnl or 0.0)
    if total_pnl is not None:
        total = float(total_pnl)
    else:
        total = float(fx["total_return"])
    residual = total - carry - rolldown - spread - curve - fx_ret
    return {
        "carry_return": carry,
        "rolldown_return": rolldown,
        "spread_return": spread,
        "curve_return": curve,
        "fx_return": fx_ret,
        "total_return": total,
        "residual_return": residual,
    }
