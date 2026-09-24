from __future__ import annotations

import math
from decimal import Decimal, InvalidOperation
from typing import Any

ZERO = Decimal("0")
ONE = Decimal("1")
ONE_HALF = Decimal("0.5")
ONE_HUNDRED = Decimal("100")
BP_PER_DECIMAL = Decimal("10000")

TENOR_YEARS = {
    "1Y": Decimal("1"),
    "3Y": Decimal("3"),
    "5Y": Decimal("5"),
    "7Y": Decimal("7"),
    "10Y": Decimal("10"),
    "30Y": Decimal("30"),
}

_CREDIT_CURVE_BY_RATING = {
    "AAA": "AAA",
    "AA+": "AA+",
    "AA": "AA",
}


class DirtyNumericInputError(ValueError):
    """脏数值输入：非缺失、但无法解析为有限 Decimal 的值。

    决策评级等正式口径禁止把脏输入静默当 0；真缺失（None/NaN/空白占位）
    仍按既有缺失语义处理，两者语义必须可区分。
    """


# 序列化后的缺失占位符（"nan"/"none"/"null"/空白）按真缺失处理，与脏输入区分。
_MISSING_NUMERIC_TEXT = {"", "nan", "none", "null"}


def is_missing_numeric(value: Any) -> bool:
    """真缺失：None、空白/缺失占位字符串、float/Decimal NaN。"""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().lower() in _MISSING_NUMERIC_TEXT
    if isinstance(value, float):
        return math.isnan(value)
    if isinstance(value, Decimal):
        return value.is_nan()
    return False


def decimal_value(value: Any) -> Decimal:
    """真缺失 → ZERO（维持既有缺失聚合语义）；脏输入 → DirtyNumericInputError。"""
    if is_missing_numeric(value):
        return ZERO
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise DirtyNumericInputError(
            f"无法解析为 Decimal 的脏数值输入：{value!r}（{type(value).__name__}）"
        ) from exc
    if not result.is_finite():
        raise DirtyNumericInputError(f"非有限数值不得进入决策评级计算：{value!r}")
    return result


def normalize_accounting_basis(value: Any) -> str:
    text = str(value or "").strip().upper().replace(" ", "")
    if text in {"AC", "AMC", "AMORTIZEDCOST", "摊余成本"}:
        return "AC"
    if text in {"FVOCI", "OCI", "FAIRVALUETHROUGHOCI", "以公允价值计量且其变动计入其他综合收益"}:
        return "FVOCI"
    if text in {"FVTPL", "TPL", "TRADING", "FAIRVALUETHROUGHPNL", "以公允价值计量且其变动计入当期损益"}:
        return "FVTPL"
    return text or "UNCLASSIFIED"


def normalize_rating_bucket(value: Any) -> str | None:
    text = str(value or "").upper().replace(" ", "")
    if "AAA" in text:
        return "AAA"
    if "AA+" in text or "AA＋" in text:
        return "AA+"
    if "AA" in text:
        return "AA"
    return None


def interpolate_curve_rate_pct(curve: dict[str, Decimal] | None, years: Decimal) -> Decimal | None:
    points: list[tuple[Decimal, Decimal]] = []
    for tenor, tenor_years in TENOR_YEARS.items():
        value = (curve or {}).get(tenor)
        if value is not None:
            points.append((tenor_years, decimal_value(value)))
    if not points:
        return None
    points.sort(key=lambda item: item[0])
    if years <= points[0][0]:
        return points[0][1]
    if years >= points[-1][0]:
        return points[-1][1]
    for left, right in zip(points, points[1:], strict=False):
        left_years, left_rate = left
        right_years, right_rate = right
        if left_years <= years <= right_years:
            span = right_years - left_years
            if span == ZERO:
                return left_rate
            weight = (years - left_years) / span
            return left_rate + (right_rate - left_rate) * weight
    return points[-1][1]


def parallel_shift_decimal(
    curve_start: dict[str, Decimal] | None,
    curve_end: dict[str, Decimal] | None,
) -> Decimal | None:
    changes = []
    for tenor in TENOR_YEARS:
        if curve_start and curve_end and tenor in curve_start and tenor in curve_end:
            changes.append(decimal_value(curve_end[tenor]) - decimal_value(curve_start[tenor]))
    if not changes:
        return None
    return (sum(changes, ZERO) / Decimal(len(changes))) / ONE_HUNDRED


def tenor_shift_decimal(
    curve_start: dict[str, Decimal] | None,
    curve_end: dict[str, Decimal] | None,
    years: Decimal,
) -> Decimal | None:
    start_rate = interpolate_curve_rate_pct(curve_start, years)
    end_rate = interpolate_curve_rate_pct(curve_end, years)
    if start_rate is None or end_rate is None:
        return None
    return (end_rate - start_rate) / ONE_HUNDRED


def credit_spread_shift_decimal(
    *,
    rating: Any,
    years: Decimal,
    treasury_start: dict[str, Decimal] | None,
    treasury_end: dict[str, Decimal] | None,
    credit_start_by_rating: dict[str, dict[str, Decimal]],
    credit_end_by_rating: dict[str, dict[str, Decimal]],
) -> Decimal | None:
    bucket = normalize_rating_bucket(rating)
    if bucket not in _CREDIT_CURVE_BY_RATING:
        return None
    credit_start = credit_start_by_rating.get(bucket)
    credit_end = credit_end_by_rating.get(bucket)
    credit_rate_start = interpolate_curve_rate_pct(credit_start, years)
    credit_rate_end = interpolate_curve_rate_pct(credit_end, years)
    treasury_rate_start = interpolate_curve_rate_pct(treasury_start, years)
    treasury_rate_end = interpolate_curve_rate_pct(treasury_end, years)
    if None in {credit_rate_start, credit_rate_end, treasury_rate_start, treasury_rate_end}:
        return None
    start_spread_pct = credit_rate_start - treasury_rate_start
    end_spread_pct = credit_rate_end - treasury_rate_end
    return (end_spread_pct - start_spread_pct) / ONE_HUNDRED


def primary_driver(components: dict[str, Decimal]) -> str:
    ranked = [
        (key, abs(value))
        for key, value in components.items()
        if key not in {"residual_noise"} and abs(value) > ZERO
    ]
    if not ranked:
        return "none"
    ranked.sort(key=lambda item: item[1], reverse=True)
    return ranked[0][0]


def compute_decision_grade_row(
    row: dict[str, Any],
    *,
    treasury_start: dict[str, Decimal] | None,
    treasury_end: dict[str, Decimal] | None,
    credit_start_by_rating: dict[str, dict[str, Decimal]],
    credit_end_by_rating: dict[str, dict[str, Decimal]],
) -> dict[str, Any]:
    actual_pnl = decimal_value(row.get("actual_pnl"))
    carry = decimal_value(row.get("carry"))
    realized_trading = decimal_value(row.get("realized_trading"))
    manual_adjustment = decimal_value(row.get("manual_adjustment"))
    market_value = decimal_value(row.get("market_value"))
    modified_duration = decimal_value(row.get("modified_duration"))
    convexity = decimal_value(row.get("convexity"))
    spread_dv01 = decimal_value(row.get("spread_dv01"))
    # 0 是有效剩余期限（当日到期，取曲线短端）；仅在缺失时才回退 3Y 代理。
    years_raw = row.get("years_to_maturity")
    years_missing = years_raw is None
    years = Decimal("3") if years_missing else decimal_value(years_raw)
    include_market_effects_in_formal_pnl = bool(row.get("include_market_effects_in_formal_pnl", True))

    diagnostics: list[str] = []
    residual_reasons: list[str] = []
    if years_missing:
        # 期限点是 3Y 代理，利率水平/曲线形态/信用利差/凸性都可能错位，未解释余额
        # 因此不得计为选券能力；与 missing_analytics 等缺数据情形同调归入残差噪音。
        diagnostics.append("years_to_maturity_missing_fallback_3y")
        residual_reasons.append("missing_years_to_maturity")
        diagnostics.append("缺少剩余期限，曲线取点按 3Y 代理，未将剩余项计为能力。")
    dy_level = parallel_shift_decimal(treasury_start, treasury_end)
    dy_tenor = tenor_shift_decimal(treasury_start, treasury_end, years)

    rate_level_effect = ZERO
    curve_shape_effect = ZERO
    convexity_effect = ZERO
    if include_market_effects_in_formal_pnl and modified_duration != ZERO and market_value != ZERO:
        if dy_level is None or dy_tenor is None:
            residual_reasons.append("missing_treasury_curve")
            diagnostics.append("缺少国债曲线，利率水平/曲线形态影响进入残差噪音。")
        else:
            rate_level_effect = -modified_duration * market_value * dy_level
            curve_shape_effect = -modified_duration * market_value * (dy_tenor - dy_level)

    spread_shift = ZERO
    credit_spread_effect = ZERO
    if include_market_effects_in_formal_pnl and bool(row.get("is_credit")) and market_value != ZERO:
        computed_spread_shift = credit_spread_shift_decimal(
            rating=row.get("rating"),
            years=years,
            treasury_start=treasury_start,
            treasury_end=treasury_end,
            credit_start_by_rating=credit_start_by_rating,
            credit_end_by_rating=credit_end_by_rating,
        )
        if computed_spread_shift is None:
            residual_reasons.append("missing_credit_curve")
            diagnostics.append("缺少信用曲线或评级映射，信用利差影响进入残差噪音。")
        else:
            spread_shift = computed_spread_shift
            if spread_dv01 != ZERO:
                credit_spread_effect = -spread_dv01 * (spread_shift * BP_PER_DECIMAL)
            else:
                credit_spread_effect = -modified_duration * market_value * spread_shift

    if include_market_effects_in_formal_pnl and convexity != ZERO and market_value != ZERO:
        if dy_tenor is None:
            residual_reasons.append("missing_convexity_curve")
            diagnostics.append("缺少期限点收益率，凸性影响进入残差噪音。")
        else:
            convexity_shift = dy_tenor + spread_shift
            convexity_effect = ONE_HALF * convexity * market_value * convexity_shift * convexity_shift

    if bool(row.get("duplicate_position_key")) and bool(row.get("duplicate_position_key_is_ambiguous", True)):
        residual_reasons.append("duplicate_position_key")
        diagnostics.append("同一组合/成本中心/会计分类存在重复 key，未将剩余项计为能力。")
    if bool(row.get("missing_analytics")):
        residual_reasons.append("missing_bond_analytics")
        diagnostics.append("缺少债券久期/凸性等 analytics，未将剩余项计为能力。")

    fixed_components = (
        carry
        + rate_level_effect
        + curve_shape_effect
        + credit_spread_effect
        + convexity_effect
        + realized_trading
        + manual_adjustment
    )
    unexplained_balance = actual_pnl - fixed_components
    if residual_reasons:
        selection_proxy = ZERO
        residual_noise = unexplained_balance
    else:
        selection_proxy = unexplained_balance
        residual_noise = ZERO

    components = {
        "carry": carry,
        "rate_level_effect": rate_level_effect,
        "curve_shape_effect": curve_shape_effect,
        "credit_spread_effect": credit_spread_effect,
        "convexity_effect": convexity_effect,
        "realized_trading": realized_trading,
        "manual_adjustment": manual_adjustment,
        "selection_proxy": selection_proxy,
        "residual_noise": residual_noise,
    }
    return {
        "components": components,
        "actual_pnl": actual_pnl,
        # explained_pnl 仅累加真正可归因的固定因子；selection_proxy/residual_noise 是承接
        # 缺口的平衡项，若计入会使下游 explained_pnl≡actual_pnl，令闭合判定代数恒真（假门禁）。
        "explained_pnl": fixed_components,
        "residual_reasons": sorted(set(residual_reasons)),
        "diagnostics": diagnostics,
    }
