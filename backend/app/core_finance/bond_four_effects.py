"""
单券四效应归因（自 MOSS-SYSTEM-V1 attribution_core.compute_bond_four_effects 迁入）。

依赖本包 bond_duration（原 bond_analytics.common），无全局 config / DB。
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Dict

from backend.app.core_finance.field_normalization import ACCOUNTING_BASIS_AC

from .bond_duration import (
    estimate_convexity_bond,
    estimate_duration,
    infer_accounting_class,
    modified_duration_from_macaulay,
)
from .safe_decimal import safe_decimal


def _get_bond_field(bond: Any, *keys: str, default: Any = 0):
    for k in keys:
        try:
            v = bond.get(k, None) if hasattr(bond, "get") and callable(getattr(bond, "get")) else getattr(bond, k, None)
        except (KeyError, AttributeError):
            v = None
        if v is None:
            continue
        try:
            import pandas as pd

            if pd.isna(v):
                continue
        except Exception:
            pass
        return v
    return default


def compute_bond_four_effects(
    bond: Dict[str, Any],
    num_days: int,
    benchmark_yield_change: Decimal,
    spread_change: Decimal,
    report_date: date,
    coupon_frequency: int = 2,
) -> Dict[str, Decimal]:
    """
    单券四效应：income / treasury / spread / selection + total_return。

    AC 类：利率/利差/选券归零，total_return = income_return。

    total_return 计算口径（标准 Campisi 全价基准）：
      若 bond 提供 accrued_interest_start / accrued_interest_end（应计利息），
      则 total_return = (mv_end + ai_end) - (mv_start + ai_start)，即全价变动。
      否则退化为 total_price_change + income_return（净价变动 + 票息估算），
      此时 selection_effect 会系统性吸收面值/市值差异（折溢价债券误差约 5-10%）。
    """
    coupon = safe_decimal(_get_bond_field(bond, "coupon_rate_start", "coupon_rate"))
    face = safe_decimal(_get_bond_field(bond, "face_value_start", "face_value"))
    mv_start = safe_decimal(_get_bond_field(bond, "market_value_start"))
    mv_end = safe_decimal(_get_bond_field(bond, "market_value_end"))
    bond_code = str(_get_bond_field(bond, "bond_code", default=""))
    asset_class = _get_bond_field(bond, "asset_class_start", "asset_class", default="")
    ytm_raw = _get_bond_field(bond, "yield_to_maturity_start", "yield_to_maturity")
    ytm = safe_decimal(ytm_raw) if ytm_raw is not None else None

    # 应计利息（全价基准）
    ai_start_raw = _get_bond_field(bond, "accrued_interest_start", "accrued_interest", default=None)
    ai_end_raw = _get_bond_field(bond, "accrued_interest_end", default=None)
    has_accrued = ai_start_raw is not None and ai_end_raw is not None
    ai_start = safe_decimal(ai_start_raw) if has_accrued else Decimal("0")
    ai_end = safe_decimal(ai_end_raw) if has_accrued else Decimal("0")

    mat = _get_bond_field(bond, "maturity_date_start", "maturity_date")
    if mat is not None and hasattr(mat, "date"):
        mat_date = mat.date()
    elif mat is not None:
        try:
            if hasattr(mat, "year"):
                mat_date = date(mat.year, mat.month, mat.day) if hasattr(mat, "day") else date(mat.year, mat.month, 1)
            else:
                mat_date = date.today()
        except Exception:
            mat_date = None
    else:
        mat_date = None

    income_return = coupon * face * Decimal(str(num_days)) / Decimal("365")

    if mat_date is None:
        mod_dur = Decimal("0.01")
    else:
        macaulay = estimate_duration(
            maturity_date=mat_date,
            report_date=report_date,
            coupon_rate=coupon,
            bond_code=bond_code,
            ytm=ytm,
            wind_metrics=None,
            coupon_frequency=coupon_frequency,
        )
        ytm_for_mod = ytm if ytm and ytm > Decimal("0") else coupon if coupon > Decimal("0") else Decimal("0.01")
        mod_dur = modified_duration_from_macaulay(
            duration=macaulay,
            ytm=ytm_for_mod,
            coupon_frequency=coupon_frequency,
            wind_mod_dur=None,
        )

    treasury_effect = -mod_dur * benchmark_yield_change * mv_start
    spread_effect = -mod_dur * spread_change * mv_start

    total_price_change = mv_end - mv_start
    # 全价基准（标准 Campisi）：若有应计利息则用全价变动，否则退化为净价+票息估算
    if has_accrued:
        total_return = (mv_end + ai_end) - (mv_start + ai_start)
    else:
        total_return = total_price_change + income_return
    selection_effect = total_return - income_return - treasury_effect - spread_effect

    ac_class = infer_accounting_class(asset_class)
    if ac_class == ACCOUNTING_BASIS_AC:
        treasury_effect = Decimal("0")
        spread_effect = Decimal("0")
        selection_effect = Decimal("0")
        total_return = income_return

    return {
        "income_return": income_return,
        "treasury_effect": treasury_effect,
        "spread_effect": spread_effect,
        "selection_effect": selection_effect,
        "total_return": total_return,
        "total_price_change": total_price_change,
        "mod_duration": mod_dur,
    }


def compute_bond_six_effects(
    bond: Dict[str, Any],
    num_days: int,
    benchmark_yield_change: Decimal,
    spread_change: Decimal,
    report_date: date,
    coupon_frequency: int = 2,
) -> Dict[str, Decimal]:
    """
    六效应（票息 / 利率 / 利差 / 凸性 / 交叉 / 再投资 + 选券残差）。

    在线性项（利率、利差）之外，用二阶项分解：
    - convexity_effect ≈ 0.5 * C * (dy² + ds²) * MV
    - cross_effect ≈ C * dy * ds * MV（与 (dy+ds)² 展开一致）
    - reinvestment_effect：占位 0（与 V1 enhanced 文档一致，可后续接短端利率）

    选券残差 = total_return - 上述各项之和，吸收更高阶与模型误差。
    AC 类与四效应一致：仅票息，余者为 0。
    """
    fx = compute_bond_four_effects(
        bond,
        num_days,
        benchmark_yield_change,
        spread_change,
        report_date,
        coupon_frequency=coupon_frequency,
    )
    asset_class = _get_bond_field(bond, "asset_class_start", "asset_class", default="")
    if infer_accounting_class(asset_class) == ACCOUNTING_BASIS_AC:
        return {
            "income_return": fx["income_return"],
            "treasury_effect": Decimal("0"),
            "spread_effect": Decimal("0"),
            "convexity_effect": Decimal("0"),
            "cross_effect": Decimal("0"),
            "reinvestment_effect": Decimal("0"),
            "selection_effect": Decimal("0"),
            "total_return": fx["total_return"],
            "total_price_change": fx["total_price_change"],
            "mod_duration": fx["mod_duration"],
        }

    coupon = safe_decimal(_get_bond_field(bond, "coupon_rate_start", "coupon_rate"))
    ytm_raw = _get_bond_field(bond, "yield_to_maturity_start", "yield_to_maturity")
    ytm = safe_decimal(ytm_raw) if ytm_raw is not None else None
    mv_start = safe_decimal(_get_bond_field(bond, "market_value_start"))
    mat = _get_bond_field(bond, "maturity_date_start", "maturity_date")
    if mat is not None and hasattr(mat, "date"):
        mat_date = mat.date()
    elif mat is not None:
        try:
            if hasattr(mat, "year"):
                mat_date = date(mat.year, mat.month, mat.day) if hasattr(mat, "day") else date(mat.year, mat.month, 1)
            else:
                mat_date = None
        except Exception:
            mat_date = None
    else:
        mat_date = None

    bond_code = str(_get_bond_field(bond, "bond_code", default=""))
    dy = benchmark_yield_change
    ds = spread_change

    if mat_date is None:
        convexity = Decimal("0")
    else:
        macaulay = estimate_duration(
            maturity_date=mat_date,
            report_date=report_date,
            coupon_rate=coupon,
            bond_code=bond_code,
            ytm=ytm,
            wind_metrics=None,
            coupon_frequency=coupon_frequency,
        )
        ytm_for_mod = ytm if ytm and ytm > Decimal("0") else coupon if coupon > Decimal("0") else Decimal("0.01")
        convexity = estimate_convexity_bond(macaulay, ytm_for_mod, wind_convexity=None, coupon_frequency=coupon_frequency)

    convexity_effect = Decimal("0.5") * convexity * (dy * dy + ds * ds) * mv_start
    cross_effect = convexity * dy * ds * mv_start
    reinvestment_effect = Decimal("0")

    total_return = fx["total_return"]
    income = fx["income_return"]
    treas = fx["treasury_effect"]
    spread = fx["spread_effect"]
    selection_effect = (
        total_return - income - treas - spread - convexity_effect - cross_effect - reinvestment_effect
    )

    return {
        "income_return": income,
        "treasury_effect": treas,
        "spread_effect": spread,
        "convexity_effect": convexity_effect,
        "cross_effect": cross_effect,
        "reinvestment_effect": reinvestment_effect,
        "selection_effect": selection_effect,
        "total_return": total_return,
        "total_price_change": fx["total_price_change"],
        "mod_duration": fx["mod_duration"],
    }
