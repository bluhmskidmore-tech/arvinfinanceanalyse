"""
单券四效应归因（自 MOSS-SYSTEM-V1 attribution_core.compute_bond_four_effects 迁入）。

依赖本包 bond_duration（原 bond_analytics.common），无全局 config / DB。
"""
from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, TypedDict

from backend.app.core_finance.bond_analytics.common import (
    compute_macaulay_duration_and_convexity,
    resolve_ytm_with_par_fallback,
)
from backend.app.core_finance.field_normalization import ACCOUNTING_BASIS_AC
from backend.app.core_finance.interest_mode import classify_interest_payment_frequency
from backend.app.core_finance.rate_units import (
    NEGATIVE_YIELD_DIRTY_FLOOR,
    normalize_annual_rate_to_decimal,
)

from .bond_duration import (
    estimate_convexity_bond,
    estimate_duration,
    infer_accounting_class,
    modified_duration_from_macaulay,
)
from .decimal_utils import to_decimal_strict
from .safe_decimal import safe_decimal

logger = logging.getLogger(__name__)

# 稳定的诊断码：归因链路入口（campisi.campisi_attribution / campisi_enhanced）按这些
# 常量统计"跑在退化分支上"的行数与市值占比，避免两个模块各写一份字符串字面量。
ACCRUED_INTEREST_MISSING_DIAGNOSTIC = "accrued_interest_missing"
ACCRUED_INTEREST_PARTIAL_DIAGNOSTIC = "accrued_interest_partial"
ACCRUED_INTEREST_EXCEEDS_CARRY_DIAGNOSTIC = "accrued_interest_exceeds_modeled_carry"
MATURITY_DATE_PARSE_FAILED_DIAGNOSTIC = "maturity_date_parse_failed"
MOD_DUR_FALLBACK_ZERO_DIAGNOSTIC = "mod_dur_fallback_zero"
COUPON_RATE_START_PARSE_FAILED_DIAGNOSTIC = "coupon_rate_start_parse_failed"
FACE_VALUE_START_PARSE_FAILED_DIAGNOSTIC = "face_value_start_parse_failed"
MARKET_VALUE_START_PARSE_FAILED_DIAGNOSTIC = "market_value_start_parse_failed"
MARKET_VALUE_END_PARSE_FAILED_DIAGNOSTIC = "market_value_end_parse_failed"
# 「缺失」与「脏值」是两种事故：脏值有 *_PARSE_FAILED_*，缺失此前没有任何披露通道，
# 于是「按 0 代入」在下游与「观测到 0」完全不可区分。数值口径不变，只补标记。
COUPON_RATE_START_MISSING_DIAGNOSTIC = "coupon_rate_start_missing"
FACE_VALUE_START_MISSING_DIAGNOSTIC = "face_value_start_missing"
MARKET_VALUE_START_MISSING_DIAGNOSTIC = "market_value_start_missing"
MARKET_VALUE_END_MISSING_DIAGNOSTIC = "market_value_end_missing"
# 只在期初或只在期末存在的持仓：缺失一侧不是「市值 0」，两者之差也不是价格变动。
POSITION_START_ONLY_DIAGNOSTIC = "position_start_only"
POSITION_END_ONLY_DIAGNOSTIC = "position_end_only"
POSITION_PRINCIPAL_CHANGED_DIAGNOSTIC = "position_principal_changed"
POSITION_PRINCIPAL_UNAVAILABLE_DIAGNOSTIC = "position_principal_unavailable"
PRINCIPAL_EXCLUSION_DIAGNOSTICS = frozenset(
    {POSITION_PRINCIPAL_CHANGED_DIAGNOSTIC, POSITION_PRINCIPAL_UNAVAILABLE_DIAGNOSTIC}
)
SINGLE_SIDED_POSITION_DIAGNOSTICS = frozenset(
    {POSITION_START_ONLY_DIAGNOSTIC, POSITION_END_ONLY_DIAGNOSTIC}
)
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


_ACCOUNTING_CLASS_TOKENS = frozenset({"AC", "OCI", "TPL"})


def resolve_accounting_class(bond: Any) -> str:
    """解析该券的会计分类（AC / OCI / TPL）。

    优先取仓库层算好的权威字段 ``accounting_class``；只有在它缺失时才回退到
    从标签串推断。上游 ``positions_merged`` 的 ``asset_class_start`` 是
    ``asset_class_std`` + 评级（如 ``credit AAA``），不含会计口径信息，单靠它
    推断会把全部持仓判成 TPL。
    """
    explicit = str(_get_bond_field(bond, "accounting_class", default="") or "").strip().upper()
    if explicit in _ACCOUNTING_CLASS_TOKENS:
        return explicit
    return infer_accounting_class(
        _get_bond_field(bond, "asset_class_start", "asset_class", default="")
    )


def _annual_rate_decimal(value: Any, *, negative_floor: float | None = None) -> Decimal:
    normalized = normalize_annual_rate_to_decimal(value, negative_floor=negative_floor)
    if normalized is None:
        return Decimal("0")
    return Decimal(str(normalized))


def _ytm_decimal(value: Any) -> Decimal | None:
    """保留观测零；缺失或脏值返回 None，由久期入口使用 par 代理。"""
    normalized = normalize_annual_rate_to_decimal(
        value, negative_floor=NEGATIVE_YIELD_DIRTY_FLOOR
    )
    return Decimal(str(normalized)) if normalized is not None else None


# 与 campisi_decision_grade.is_missing_numeric 对齐：真缺失不记解析失败。
_MISSING_NUMERIC_TEXT = frozenset({"", "nan", "none", "null"})


def _is_absent_numeric(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip().lower() in _MISSING_NUMERIC_TEXT:
        return True
    if isinstance(value, float) and value != value:
        return True
    if isinstance(value, Decimal) and value.is_nan():
        return True
    return False


def _present_value_parse_failed(value: Any) -> bool:
    """字段存在但无法转为有限 Decimal 时为 True；缺失/占位不记解析失败。"""
    if _is_absent_numeric(value):
        return False
    try:
        to_decimal_strict(value)
    except (TypeError, ValueError, InvalidOperation, ArithmeticError):
        return True
    return False


def _safe_decimal_with_parse_flag(value: Any) -> tuple[Decimal, bool]:
    """数值行为与 safe_decimal 一致；仅对存在但不可解析的脏值打标。"""
    return safe_decimal(value), _present_value_parse_failed(value)


def _annual_rate_with_parse_flag(value: Any) -> tuple[Decimal, bool]:
    """数值行为与 _annual_rate_decimal 一致；仅对存在但不可解析的脏值打标。"""
    return _annual_rate_decimal(value), _present_value_parse_failed(value)


def _side_declared_present(bond: Any, key: str) -> bool:
    """该期末是否真的持有这条持仓。

    只有上游显式写入 ``False`` 才算「这一侧不存在」。缺字段视为「未声明」，
    保持既有口径：``attribution_daily`` 等调用方不产生该标记，行为不变。
    """
    return _get_bond_field(bond, key, default=None) is not False


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
    coupon_raw = _get_bond_field(bond, "coupon_rate_start", "coupon_rate", default=None)
    coupon, coupon_parse_failed = _annual_rate_with_parse_flag(coupon_raw)
    face_raw = _get_bond_field(bond, "face_value_start", "face_value", default=None)
    face, face_parse_failed = _safe_decimal_with_parse_flag(face_raw)
    mv_start_raw = _get_bond_field(bond, "market_value_start", default=None)
    mv_start, mv_start_parse_failed = _safe_decimal_with_parse_flag(mv_start_raw)
    mv_end_raw = _get_bond_field(bond, "market_value_end", default=None)
    mv_end, mv_end_parse_failed = _safe_decimal_with_parse_flag(mv_end_raw)
    start_present = _side_declared_present(bond, "start_present")
    end_present = _side_declared_present(bond, "end_present")
    single_sided = start_present != end_present
    principal_diagnostic = None
    # Snapshot merging supplies both principal endpoints. Legacy daily inputs
    # do not: an absent key is not an assertion that ending principal is zero.
    if not single_sided and "face_value_end" in bond:
        # CNY-equivalent face values change with FX even when native principal
        # is unchanged. Keep CNY face for income; compare native evidence only.
        native_basis = "face_value_native_start" in bond or "face_value_native_end" in bond
        start_face_raw = bond.get("face_value_native_start") if native_basis else face_raw
        end_face_raw = bond.get("face_value_native_end") if native_basis else bond.get("face_value_end")
        if (_is_absent_numeric(start_face_raw) or _is_absent_numeric(end_face_raw)
                or _present_value_parse_failed(start_face_raw) or _present_value_parse_failed(end_face_raw)):
            principal_diagnostic = POSITION_PRINCIPAL_UNAVAILABLE_DIAGNOSTIC
        elif to_decimal_strict(start_face_raw) != to_decimal_strict(end_face_raw):
            principal_diagnostic = POSITION_PRINCIPAL_CHANGED_DIAGNOSTIC
    bond_code = str(_get_bond_field(bond, "bond_code", default=""))
    ytm_raw = _get_bond_field(bond, "yield_to_maturity_start", "yield_to_maturity", default=None)
    ytm = _ytm_decimal(ytm_raw)

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
        if classify_interest_payment_frequency(bond.get("interest_mode_start")) == "bullet":
            effective_ytm, _ = resolve_ytm_with_par_fallback(coupon, ytm)
            macaulay, _ = compute_macaulay_duration_and_convexity(
                coupon_rate=coupon, ytm=effective_ytm,
                years_to_maturity=Decimal((mat_date - report_date).days) / Decimal("365"),
                coupon_frequency=coupon_frequency, single_cashflow_at_maturity=True,
                report_date=report_date, maturity_date=mat_date,
            )
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
        # 修正久期的除数必须用 Macaulay 实际采用的生效 ytm：estimate_duration 对有票息
        # 缺 ytm 的债走 par 假设（ytm=coupon），这里取同一来源，不再各自维护一份回退逻辑。
        ytm_for_mod, _par_fallback_used = resolve_ytm_with_par_fallback(
            coupon,
            ytm,
        )
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

    ac_class = resolve_accounting_class(bond)
    if ac_class == ACCOUNTING_BASIS_AC:
        treasury_effect = Decimal("0")
        spread_effect = Decimal("0")
        selection_effect = Decimal("0")
        total_return = income_return

    if single_sided or principal_diagnostic:
        # 单边或本金发生变化的持仓不能由两端市值推断收益；双端本金缺失也不能
        # 证明持仓未变。没有交易现金流时只保留排除诊断，Campisi 汇总据此剔除
        # 相关行。这里的 0 是排除占位，不是观测到的收益。
        income_return = Decimal("0")
        treasury_effect = Decimal("0")
        spread_effect = Decimal("0")
        selection_effect = Decimal("0")
        total_return = Decimal("0")
        total_price_change = Decimal("0")

    diagnostics: list[str] = []
    if principal_diagnostic:
        diagnostics.append(principal_diagnostic)
    log_id = bond_code or str(
        _get_bond_field(bond, "instrument_code", "instrument_id", default="") or "UNKNOWN"
    )
    _parse_failed_fields = (
        (coupon_parse_failed, COUPON_RATE_START_PARSE_FAILED_DIAGNOSTIC, "coupon_rate_start"),
        (face_parse_failed, FACE_VALUE_START_PARSE_FAILED_DIAGNOSTIC, "face_value_start"),
        (mv_start_parse_failed, MARKET_VALUE_START_PARSE_FAILED_DIAGNOSTIC, "market_value_start"),
        (mv_end_parse_failed, MARKET_VALUE_END_PARSE_FAILED_DIAGNOSTIC, "market_value_end"),
    )
    for failed, code, field_name in _parse_failed_fields:
        if not failed:
            continue
        diagnostics.append(code)
        logger.warning(
            "compute_bond_four_effects: %s parse failed for bond %s, treating as 0",
            field_name,
            log_id,
        )
    if single_sided:
        diagnostics.append(
            POSITION_START_ONLY_DIAGNOSTIC if start_present else POSITION_END_ONLY_DIAGNOSTIC
        )
        logger.warning(
            "bond %s: position exists on the %s side only; all four effects and total_return "
            "are 0 on this row because a one-sided holding is a position change, not a price "
            "move. Trade-level attribution for this row is undefined.",
            log_id,
            "start" if start_present else "end",
        )
    # 单边行的 market_value 缺失已由单边码解释，不再重复报缺失码；
    # 票息/面值缺失与单边无关，两种情形都必须披露。
    _missing_fields = (
        (coupon_raw, COUPON_RATE_START_MISSING_DIAGNOSTIC, "coupon_rate_start", True),
        (face_raw, FACE_VALUE_START_MISSING_DIAGNOSTIC, "face_value_start", True),
        (mv_start_raw, MARKET_VALUE_START_MISSING_DIAGNOSTIC, "market_value_start", not single_sided),
        (mv_end_raw, MARKET_VALUE_END_MISSING_DIAGNOSTIC, "market_value_end", not single_sided),
    )
    for raw, code, field_name, reportable in _missing_fields:
        if not reportable or not _is_absent_numeric(raw):
            continue
        diagnostics.append(code)
        logger.warning(
            "compute_bond_four_effects: %s is missing for bond %s, substituting 0; "
            "the resulting 0 is an input gap, not an observed value",
            field_name,
            log_id,
        )
    if _mat_parse_failed:
        diagnostics.append(MATURITY_DATE_PARSE_FAILED_DIAGNOSTIC)
    if mat_date is None:
        diagnostics.append(MOD_DUR_FALLBACK_ZERO_DIAGNOSTIC)
    if single_sided or principal_diagnostic:
        accrued_disclosure = (
            "excluded from attribution; all effects and total_return are 0 placeholders"
        )
    elif ac_class == ACCOUNTING_BASIS_AC:
        accrued_disclosure = "AC attribution uses modeled coupon only; selection_effect is 0"
    else:
        accrued_disclosure = (
            "falling back to clean-price basis; "
            "selection_effect absorbs the par/market difference on this row"
        )
    if _ai_partial:
        diagnostics.append(ACCRUED_INTEREST_PARTIAL_DIAGNOSTIC)
        logger.warning(
            "bond %s: only one side of accrued_interest present "
            "(start=%r, end=%r); %s",
            log_id, ai_start_raw, ai_end_raw, accrued_disclosure,
        )
    elif not has_accrued:
        diagnostics.append(ACCRUED_INTEREST_MISSING_DIAGNOSTIC)
        logger.warning(
            "bond %s: accrued_interest missing on both sides; %s",
            log_id, accrued_disclosure,
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
    if resolve_accounting_class(bond) == ACCOUNTING_BASIS_AC or (SINGLE_SIDED_POSITION_DIAGNOSTICS | PRINCIPAL_EXCLUSION_DIAGNOSTICS).intersection(
        fx["diagnostics"]
    ):
        # 排除持仓的二阶项同样以 mv_start 为基数，不归零就会让选券残差重新
        # 吸收 -(convexity + cross)，四效应侧的 fail-closed 归零白做。
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

    coupon, _ = _annual_rate_with_parse_flag(
        _get_bond_field(bond, "coupon_rate_start", "coupon_rate", default=None)
    )
    ytm_raw = _get_bond_field(bond, "yield_to_maturity_start", "yield_to_maturity", default=None)
    ytm = _ytm_decimal(ytm_raw)
    mv_start, _ = _safe_decimal_with_parse_flag(
        _get_bond_field(bond, "market_value_start", default=None)
    )
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
        # 凸性的贴现 ytm 与 estimate_duration 实际采用的生效 ytm 同源（缺 ytm 走 par 假设）。
        ytm_for_mod, _par_fallback_used = resolve_ytm_with_par_fallback(
            coupon,
            ytm,
        )
        # W-fi-2026-08 P4：传现金流入参，凸性走标准现金流二阶导而非久期型近似。
        # years_to_maturity 与 estimate_duration 内部同式（ACT/365F，剩余天数/365）。
        remaining_days = (mat_date - report_date).days
        years_to_maturity = (
            Decimal(str(remaining_days)) / Decimal("365")
            if remaining_days > 0
            else Decimal("0")
        )
        if classify_interest_payment_frequency(bond.get("interest_mode_start")) == "bullet":
            _, convexity = compute_macaulay_duration_and_convexity(
                coupon_rate=coupon, ytm=ytm_for_mod, years_to_maturity=years_to_maturity,
                coupon_frequency=coupon_frequency, single_cashflow_at_maturity=True,
                report_date=report_date, maturity_date=mat_date,
            )
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
            convexity = estimate_convexity_bond(
                macaulay,
                ytm_for_mod,
                wind_convexity=None,
                coupon_frequency=coupon_frequency,
                coupon_rate=coupon,
                years_to_maturity=years_to_maturity,
                report_date=report_date,
                maturity_date=mat_date,
            )

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
