"""
单券四效应归因（自 MOSS-SYSTEM-V1 attribution_core.compute_bond_four_effects 迁入）。

依赖本包 bond_duration（原 bond_analytics.common），无全局 config / DB。
"""
from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Any, TypedDict

from backend.app.core_finance.field_normalization import ACCOUNTING_BASIS_AC
from backend.app.core_finance.rate_units import normalize_annual_rate_to_decimal

from .bond_duration import (
    estimate_convexity_bond,
    estimate_duration,
    infer_accounting_class,
    modified_duration_from_macaulay,
)
from .safe_decimal import safe_decimal

logger = logging.getLogger(__name__)

# 稳定的诊断码：归因链路入口（campisi.campisi_attribution / campisi_enhanced）按这些
# 常量统计"跑在退化分支上"的行数与市值占比，避免两个模块各写一份字符串字面量。
ACCRUED_INTEREST_MISSING_DIAGNOSTIC = "accrued_interest_missing"
ACCRUED_INTEREST_PARTIAL_DIAGNOSTIC = "accrued_interest_partial"
ACCRUED_INTEREST_EXCEEDS_CARRY_DIAGNOSTIC = "accrued_interest_exceeds_modeled_carry"
MATURITY_DATE_PARSE_FAILED_DIAGNOSTIC = "maturity_date_parse_failed"
MOD_DUR_FALLBACK_ZERO_DIAGNOSTIC = "mod_dur_fallback_zero"
# 这两个诊断都意味着 total_return 退化为「净价变动 + 票息估算」，selection_effect
# 因此吸收面值/市值差异；`has_accrued_interest is False` 与本集合等价。
CLEAN_PRICE_FALLBACK_DIAGNOSTICS = frozenset(
    {ACCRUED_INTEREST_MISSING_DIAGNOSTIC, ACCRUED_INTEREST_PARTIAL_DIAGNOSTIC}
)


def _get_bond_field(bond: Any, *keys: str, default: Any = 0):
    for k in keys:
        try:
            v = bond.get(k, None) if hasattr(bond, "get") and callable(bond.get) else getattr(bond, k, None)
        except (KeyError, AttributeError):
            v = None
        if v is None:
            continue
        try:
            import pandas as pd

            if pd.isna(v):
                continue
        except (TypeError, ValueError):
            logger.exception("_get_bond_field: pd.isna check failed for key=%r", k)
            pass
        return v
    return default


def _annual_rate_decimal(value: Any) -> Decimal:
    normalized = normalize_annual_rate_to_decimal(value)
    if normalized is None:
        return Decimal("0")
    return Decimal(str(normalized))


class BondFourEffects(TypedDict):
    """compute_bond_four_effects 的返回结构（仅类型声明，运行时仍为普通 dict）。"""

    income_return: Decimal
    treasury_effect: Decimal
    spread_effect: Decimal
    selection_effect: Decimal
    total_return: Decimal
    total_price_change: Decimal
    mod_duration: Decimal
    has_accrued_interest: bool
    diagnostics: list[str]


class BondSixEffects(BondFourEffects):
    """compute_bond_six_effects 的返回结构：四效应 + 二阶项。"""

    convexity_effect: Decimal
    cross_effect: Decimal
    reinvestment_effect: Decimal


def compute_bond_four_effects(
    bond: dict[str, Any],
    num_days: int,
    benchmark_yield_change: Decimal,
    spread_change: Decimal,
    report_date: date,
    coupon_frequency: int = 2,
) -> BondFourEffects:
    """
    单券四效应：income / treasury / spread / selection + total_return。

    AC 类：利率/利差/选券归零，total_return = income_return。

    total_return 计算口径（标准 Campisi 全价基准）：
      若 bond 提供 accrued_interest_start / accrued_interest_end（应计利息），
      则 total_return = 全价变动 + 期内实付票息估算。
      实付票息 ≈ income_return - (ai_end - ai_start)，以覆盖跨付息日 AI 重置；
      无付息窗口时该项≈0，退化为全价变动。
      否则退化为 total_price_change + income_return（净价变动 + 票息估算），
      此时 selection_effect 会系统性吸收面值/市值差异（折溢价债券误差约 5-10%）。
    """
    coupon = _annual_rate_decimal(_get_bond_field(bond, "coupon_rate_start", "coupon_rate"))
    face = safe_decimal(_get_bond_field(bond, "face_value_start", "face_value"))
    mv_start = safe_decimal(_get_bond_field(bond, "market_value_start"))
    mv_end = safe_decimal(_get_bond_field(bond, "market_value_end"))
    bond_code = str(_get_bond_field(bond, "bond_code", default=""))
    asset_class = _get_bond_field(bond, "asset_class_start", "asset_class", default="")
    ytm_raw = _get_bond_field(bond, "yield_to_maturity_start", "yield_to_maturity")
    ytm = _annual_rate_decimal(ytm_raw) if ytm_raw is not None else None

    # 应计利息（全价基准）
    ai_start_raw = _get_bond_field(bond, "accrued_interest_start", "accrued_interest", default=None)
    ai_end_raw = _get_bond_field(bond, "accrued_interest_end", default=None)
    _ai_partial = (ai_start_raw is None) != (ai_end_raw is None)  # 只有一端有值
    has_accrued = ai_start_raw is not None and ai_end_raw is not None
    ai_start = safe_decimal(ai_start_raw) if has_accrued else Decimal("0")
    ai_end = safe_decimal(ai_end_raw) if has_accrued else Decimal("0")

    mat = _get_bond_field(bond, "maturity_date_start", "maturity_date")
    _mat_parse_failed = False
    if mat is not None and hasattr(mat, "date"):
        mat_date = mat.date()
    elif mat is not None:
        try:
            if hasattr(mat, "year"):
                mat_date = date(mat.year, mat.month, mat.day) if hasattr(mat, "day") else date(mat.year, mat.month, 1)
            else:
                _mat_parse_failed = True
                logger.warning(
                    "compute_bond_four_effects: maturity_date parse failed for bond %s, skipping duration calc",
                    bond_code,
                )
                mat_date = None
        except (ValueError, TypeError, AttributeError):
            _mat_parse_failed = True
            logger.warning(
                "compute_bond_four_effects: maturity_date parse failed for bond %s, skipping duration calc",
                bond_code,
            )
            mat_date = None
    else:
        mat_date = None

    income_return = coupon * face * Decimal(str(num_days)) / Decimal("365")

    if mat_date is None:
        mod_dur = Decimal("0")
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
        # modified_duration_from_macaulay returns duration unchanged when ytm <= 0,
        # so passing 0 is safe and avoids the arbitrary 0.01 proxy.
        ytm_for_mod = ytm if ytm and ytm > Decimal("0") else coupon if coupon > Decimal("0") else Decimal("0")
        mod_dur = modified_duration_from_macaulay(
            duration=macaulay,
            ytm=ytm_for_mod,
            coupon_frequency=coupon_frequency,
            wind_mod_dur=None,
        )

    treasury_effect = -mod_dur * benchmark_yield_change * mv_start
    spread_effect = -mod_dur * spread_change * mv_start

    total_price_change = mv_end - mv_start
    # 全价基准（标准 Campisi）：全价变动不含期内实付票息，跨付息日必须加回。
    # coupon_cash ≈ income_return - ΔAI；无付息时 ΔAI≈income，coupon_cash≈0。
    if has_accrued:
        dirty_change = (mv_end + ai_end) - (mv_start + ai_start)
        coupon_cash = income_return - (ai_end - ai_start)
        # Keep the clean-price + income identity; a negative inferred coupon
        # is surfaced as a diagnostic below instead of being clamped away.
        total_return = dirty_change + coupon_cash
    else:
        total_return = total_price_change + income_return
    selection_effect = total_return - income_return - treasury_effect - spread_effect

    ac_class = infer_accounting_class(asset_class)
    if ac_class == ACCOUNTING_BASIS_AC:
        treasury_effect = Decimal("0")
        spread_effect = Decimal("0")
        selection_effect = Decimal("0")
        total_return = income_return

    diagnostics: list[str] = []
    if _mat_parse_failed:
        diagnostics.append(MATURITY_DATE_PARSE_FAILED_DIAGNOSTIC)
    if mat_date is None:
        diagnostics.append(MOD_DUR_FALLBACK_ZERO_DIAGNOSTIC)
    log_id = bond_code or str(
        _get_bond_field(bond, "instrument_code", "instrument_id", default="") or "UNKNOWN"
    )
    if _ai_partial:
        diagnostics.append(ACCRUED_INTEREST_PARTIAL_DIAGNOSTIC)
        logger.warning(
            "bond %s: only one side of accrued_interest present "
            "(start=%r, end=%r), falling back to clean-price basis; "
            "selection_effect absorbs the par/market difference on this row",
            log_id, ai_start_raw, ai_end_raw,
        )
    elif not has_accrued:
        diagnostics.append(ACCRUED_INTEREST_MISSING_DIAGNOSTIC)
        logger.warning(
            "bond %s: accrued_interest missing on both sides, falling back to clean-price basis; "
            "selection_effect absorbs the par/market difference on this row",
            log_id,
        )
    elif coupon_cash < Decimal("0"):
        diagnostics.append(ACCRUED_INTEREST_EXCEEDS_CARRY_DIAGNOSTIC)
        logger.warning(
            "bond %s: accrued-interest delta %s exceeds modeled carry %s; "
            "retaining clean-price + income identity (inferred coupon_cash=%s)",
            log_id,
            ai_end - ai_start,
            income_return,
            coupon_cash,
        )

    return {
        "income_return": income_return,
        "treasury_effect": treasury_effect,
        "spread_effect": spread_effect,
        "selection_effect": selection_effect,
        "total_return": total_return,
        "total_price_change": total_price_change,
        "mod_duration": mod_dur,
        "has_accrued_interest": has_accrued,
        "diagnostics": diagnostics,
    }


def compute_bond_six_effects(
    bond: dict[str, Any],
    num_days: int,
    benchmark_yield_change: Decimal,
    spread_change: Decimal,
    report_date: date,
    coupon_frequency: int = 2,
) -> BondSixEffects:
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
            "has_accrued_interest": fx["has_accrued_interest"],
            "diagnostics": list(fx["diagnostics"]),
        }

    coupon = _annual_rate_decimal(_get_bond_field(bond, "coupon_rate_start", "coupon_rate"))
    ytm_raw = _get_bond_field(bond, "yield_to_maturity_start", "yield_to_maturity")
    ytm = _annual_rate_decimal(ytm_raw) if ytm_raw is not None else None
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
        except (ValueError, TypeError, AttributeError):
            logger.exception("compute_bond_convexity_standalone: date coercion failed for maturity_date")
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
        # modified_duration_from_macaulay returns duration unchanged when ytm <= 0,
        # so passing 0 is safe and avoids the arbitrary 0.01 proxy.
        ytm_for_mod = ytm if ytm and ytm > Decimal("0") else coupon if coupon > Decimal("0") else Decimal("0")
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
        "has_accrued_interest": fx["has_accrued_interest"],
        "diagnostics": list(fx["diagnostics"]),
    }
