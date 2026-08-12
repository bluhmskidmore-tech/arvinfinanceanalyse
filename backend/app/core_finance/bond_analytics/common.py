"""Shared utilities for bond analytics calculations."""
from __future__ import annotations

import logging
from datetime import date
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

from backend.app.core_finance.config.classification_rules import infer_invest_type
from backend.app.core_finance.field_normalization import (
    ACCOUNTING_BASIS_AC,
    ACCOUNTING_BASIS_FVOCI,
    ACCOUNTING_BASIS_FVTPL,
    derive_accounting_basis_value,
)
from backend.app.core_finance.safe_decimal import safe_decimal as _core_safe_decimal

logger = logging.getLogger(__name__)

# --- Decimal helpers ---

# 身份哨兵：共享实现在任何回退分支都原样返回 ``default`` 对象，据此区分
# "转换失败回退 0" 与 "输入本就是 0"。取值仍为 Decimal("0")，即使将来共享实现
# 不再返回同一对象，也只会漏掉日志而不会改变返回值。
_CONVERSION_FALLBACK = Decimal("0")


def safe_decimal(value) -> Decimal:
    """Bond-analytics 侧入口，委托 ``core_finance.safe_decimal`` 取值。

    共享实现已覆盖 None / NaN / Infinity / numpy 标量 / 空串等全部缺省语义；
    本包历史上按 ERROR 级披露转换失败（共享实现按 warning 级），保留该级别。
    None 属于常规缺失输入，与历史行为一致地静默归 0。
    """
    if value is None:
        return Decimal("0")
    result = _core_safe_decimal(value, default=_CONVERSION_FALLBACK)
    if result is _CONVERSION_FALLBACK:
        logger.error("safe_decimal: failed to convert %r", type(value).__name__)
        return Decimal("0")
    return result


def decimal_to_str(value: Decimal) -> str:
    return (
        str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        if isinstance(value, Decimal)
        else str(value)
    )


# --- Asset classification ---

RATE_KEYWORDS = ("国债", "国开", "政金", "政策性", "地方政府", "央票", "treasury", "government", "policy")
CREDIT_KEYWORDS = (
    "企业债",
    "公司债",
    "信用债",
    "商业银行债",
    "次级债",
    "资产支持证券",
    "中票",
    "短融",
    "超短融",
    "PPN",
    "ABS",
    "corporate",
    "credit",
)
CDB_KEYWORDS = ("国开", "政策性", "政金", "cdb", "policy bank")


def classify_asset_class(sub_type: str) -> str:
    lower = (sub_type or "").lower()
    for kw in RATE_KEYWORDS:
        if kw in lower:
            return "rate"
    for kw in CREDIT_KEYWORDS:
        if kw in lower:
            return "credit"
    return "other"


def infer_curve_type(*surfaces: object) -> str:
    combined = " ".join(str(surface or "").lower() for surface in surfaces)
    if any(keyword in combined for keyword in CDB_KEYWORDS):
        return "cdb"
    return "treasury"


# --- Accounting classification ---

# Fallback patterns when ``infer_invest_type`` returns None (e.g. bare ``AC`` token).
# W-bond-2026-04-21: H/A/T labels delegate to canonical ``hat_mapping`` via
# ``infer_invest_type``; rows for 持有至到期 / 可供出售 were removed as redundant.
ACCOUNTING_RULES = [
    {"rule_id": "R002", "pattern": "摊余成本", "result": "AC"},
    {"rule_id": "R003", "pattern": "HTM", "result": "AC"},
    {"rule_id": "R004", "pattern": "AC", "result": "AC"},
    {"rule_id": "R011", "pattern": "其他债权", "result": "OCI"},
    {"rule_id": "R012", "pattern": "FVOCI", "result": "OCI"},
    {"rule_id": "R013", "pattern": "OCI", "result": "OCI"},
    {"rule_id": "R020", "pattern": "交易性", "result": "TPL"},
    {"rule_id": "R021", "pattern": "FVTPL", "result": "TPL"},
    {"rule_id": "R022", "pattern": "TPL", "result": "TPL"},
]

ACCOUNTING_BASIS_RISK_CLASS_RULE_IDS = {
    "AC": "R001",
    "OCI": "R010",
    "TPL": "R020",
}


def map_accounting_basis_to_risk_class(accounting_basis: str | None) -> str | None:
    normalized = str(accounting_basis or "").strip().upper()
    if normalized == ACCOUNTING_BASIS_AC:
        return "AC"
    if normalized in {ACCOUNTING_BASIS_FVOCI, "OCI"}:
        return "OCI"
    if normalized in {ACCOUNTING_BASIS_FVTPL, "TPL"}:
        return "TPL"
    return None


def map_accounting_class(asset_class: str) -> str:
    if not asset_class:
        return "other"
    invest = infer_invest_type(None, None, asset_class)
    if invest is not None:
        basis = derive_accounting_basis_value(invest)  # type: ignore[arg-type]
        if basis == ACCOUNTING_BASIS_AC:
            return "AC"
        if basis == ACCOUNTING_BASIS_FVOCI:
            return "OCI"
        return "TPL"
    upper = asset_class.upper()
    for rule in ACCOUNTING_RULES:
        if rule["pattern"].upper() in upper:
            return rule["result"]
    return "other"


def infer_accounting_class(asset_class: str) -> str:
    return map_accounting_class(asset_class)


def get_accounting_rule_trace(asset_class: str) -> tuple[str, str | None]:
    """Return (rule_id, representative_pattern) for the asset_class match.

    The Chinese-label *return values* below are output-side trace literals
    that name the matched canonical bucket; they are NOT input-side
    classifiers (those live in ``classification_rules.infer_invest_type``).
    Audit ``hat_mapping/accounting_class_substring`` flags them as a regex
    false positive — see W-final-2026-04-21 docstring on
    ``calibers.rules.hat_mapping``.
    Human: caliber-hat_mapping-justified (output trace literals, not filters).
    """
    if not asset_class:
        return "R999", None
    invest = infer_invest_type(None, None, asset_class)
    if invest == "H":
        return "R001", "持有至到期"
    if invest == "A":
        return "R010", "可供出售"
    if invest == "T":
        return "R020", "交易性"
    upper = asset_class.upper()
    for rule in ACCOUNTING_RULES:
        if rule["pattern"].upper() in upper:
            return rule["rule_id"], rule["pattern"]
    return "R999", None


# --- Duration estimation ---

YTM_PAR_FALLBACK_RULE_ID = "ytm_par_fallback_duration_v1"


def resolve_ytm_with_par_fallback(
    coupon_rate: Decimal,
    ytm: Decimal,
) -> tuple[Decimal, bool]:
    """解析久期/修正久期/凸性估计所用的生效 ytm；有票息缺 ytm 时用 par 假设。

    W-fi-2026-08 P1：有票息但 ytm 缺失/非正的债此前落入零息回退
    （Macaulay=剩余年限），10Y/3% 票息券回退值 10 年 vs par 口径 ≈8.79 年，
    久期与 DV01 被系统性高估。与 bond_duration._estimate_macaulay_duration_years
    的既有口径对齐：按 ytm=coupon_rate（par 假设）走 Macaulay。

    返回 ``(生效 ytm, 是否使用 par 回退)``。ytm>0 正常路径与零票息路径
    （零息债 Macaulay=剩余年限本就正确）行为不变。
    """
    if ytm > 0:
        return ytm, False
    if coupon_rate > 0:
        return coupon_rate, True
    return ytm, False


def compute_macaulay_duration(
    coupon_rate: Decimal,
    ytm: Decimal,
    years_to_maturity: Decimal,
    coupon_frequency: int = 1,
) -> Decimal:
    if years_to_maturity <= 0:
        return Decimal("0")
    if ytm <= 0:
        return years_to_maturity

    raw_periods = years_to_maturity * Decimal(str(coupon_frequency))
    full_periods = int(raw_periods)
    fractional_period = raw_periods - Decimal(str(full_periods))
    if full_periods > 0 and Decimal("0") < fractional_period <= Decimal("0.01"):
        n_periods = full_periods
        cashflow_years = Decimal(str(full_periods)) / Decimal(str(coupon_frequency))
    else:
        n_periods = int(raw_periods.to_integral_value(rounding=ROUND_CEILING))
        cashflow_years = years_to_maturity
    if n_periods <= 0:
        return years_to_maturity

    c = coupon_rate / coupon_frequency if coupon_frequency > 0 else coupon_rate
    y = ytm / coupon_frequency if coupon_frequency > 0 else ytm

    if y == 0:
        return years_to_maturity

    pv_sum = Decimal("0")
    price = Decimal("0")

    first_period_years = (
        cashflow_years
        - (Decimal(str(n_periods - 1)) / Decimal(str(coupon_frequency)))
    )
    first_period_number = first_period_years * Decimal(str(coupon_frequency))

    for t in range(1, n_periods + 1):
        payment_time_years = first_period_years + (
            Decimal(str(t - 1)) / Decimal(str(coupon_frequency))
        )
        period_number = first_period_number + Decimal(str(t - 1))
        discount = (Decimal("1") + y) ** period_number
        cf = c if t < n_periods else c + Decimal("1")
        pv = cf / discount
        pv_sum += payment_time_years * pv
        price += pv

    if price <= 0:
        return years_to_maturity

    return pv_sum / price


def estimate_duration(
    maturity_date: date | None,
    report_date: date | None,
    coupon_rate: Decimal = Decimal("0"),
    ytm: Decimal = Decimal("0"),
    bond_code: str = "",
    coupon_frequency: int = 1,
) -> Decimal:
    if not maturity_date or not report_date:
        return Decimal("3")

    remaining_days = (maturity_date - report_date).days
    if remaining_days <= 0:
        return Decimal("0")

    years = Decimal(str(remaining_days)) / Decimal("365")

    effective_ytm, _par_fallback_used = resolve_ytm_with_par_fallback(coupon_rate, ytm)
    if coupon_rate > 0 and effective_ytm > 0:
        return compute_macaulay_duration(
            coupon_rate,
            effective_ytm,
            years,
            coupon_frequency=coupon_frequency,
        )

    return years


def estimate_modified_duration(
    macaulay_duration: Decimal,
    ytm: Decimal,
    coupon_frequency: int = 1,
) -> Decimal:
    """Macaulay → 修正久期；``ytm`` 应传久期估计实际使用的生效 ytm。

    par 假设路径（estimate_duration 对有票息缺 ytm 的债按 ytm=coupon 计算）
    的调用方需传入该生效 ytm（见 ``resolve_ytm_with_par_fallback``），否则
    ytm<=0 时保持既有语义：不折算、原样返回 Macaulay。
    """
    if ytm <= 0 or coupon_frequency <= 0:
        return macaulay_duration
    return macaulay_duration / (Decimal("1") + ytm / Decimal(str(coupon_frequency)))


def estimate_convexity(
    duration: Decimal,
    ytm: Decimal,
    coupon_frequency: int = 2,
) -> Decimal:
    if ytm <= 0:
        return duration * duration
    y = ytm / Decimal(str(coupon_frequency)) if coupon_frequency > 0 else ytm
    return (duration * (duration + Decimal("1"))) / ((Decimal("1") + y) ** 2)


# --- Curve utilities ---

TENOR_YEARS: dict[str, float] = {
    "1M": 1 / 12, "3M": 0.25, "6M": 0.5, "9M": 0.75,
    "1Y": 1.0, "2Y": 2.0, "3Y": 3.0, "4Y": 4.0, "5Y": 5.0, "6Y": 6.0,
    "7Y": 7.0, "10Y": 10.0, "15Y": 15.0, "20Y": 20.0, "30Y": 30.0,
}


def tenor_to_years_or_none(tenor: str) -> float | None:
    """已知期限词表精确查询；未知标签返回 ``None`` 由调用方决定跳过或报错。"""
    return TENOR_YEARS.get(tenor)


def tenor_to_years(tenor: str) -> float:
    years = TENOR_YEARS.get(tenor)
    if years is None:
        # 未知标签绝不静默映射为 5.0 年：假 5Y 节点会与真实 5Y 重复（三次样条
        # h=0 除零）并污染全部插值结果（2026-08 审计 FI-05）。
        raise ValueError(f"Unknown curve tenor label: {tenor!r}")
    return years


def get_tenor_bucket(years_to_maturity: float) -> str:
    if years_to_maturity <= 0.5:
        return "6M"
    if years_to_maturity <= 1.5:
        return "1Y"
    if years_to_maturity <= 2.5:
        return "2Y"
    if years_to_maturity <= 4.0:
        return "3Y"
    if years_to_maturity <= 6.0:
        return "5Y"
    if years_to_maturity <= 8.5:
        return "7Y"
    if years_to_maturity <= 12.5:
        return "10Y"
    if years_to_maturity <= 25.0:
        return "20Y"
    return "30Y"


def build_curve_points(curve: dict[str, Decimal]) -> list[tuple[float, Decimal]]:
    # 未知期限标签跳过并告警（不发明节点）；按 years 去重以保证 x 严格递增，
    # 防止三次样条 h=0 除零（2026-08 审计 FI-05）。
    points: dict[float, Decimal] = {}
    skipped: list[str] = []
    for tenor, rate in curve.items():
        years = tenor_to_years_or_none(tenor)
        if years is None:
            skipped.append(str(tenor))
            continue
        points[years] = safe_decimal(rate)
    if skipped:
        logger.warning(
            "build_curve_points skipped unknown tenor labels %s (kept %d of %d nodes)",
            sorted(skipped),
            len(points),
            len(curve),
        )
    return sorted(points.items(), key=lambda x: x[0])


def interpolate_rate(points: list[tuple[float, Decimal]], target_years: float) -> Decimal:
    """Interpolate a rate from sorted (years, rate) points.

    Delegates to ``curve_engine`` cubic spline when ≥ 3 points are available;
    falls back to piecewise linear otherwise.  Signature unchanged.
    """
    from backend.app.core_finance.curve_engine.curve_types import (
        CurvePoint,
        FittedCurve,
        InterpolationMethod,
    )
    from backend.app.core_finance.curve_engine.interpolation import (
        build_cubic_spline as _build_spline,
    )
    from backend.app.core_finance.curve_engine.interpolation import (
        interpolate as _engine_interpolate,
    )

    if not points:
        return Decimal("0")

    curve_points = tuple(CurvePoint(years=y, rate=r) for y, r in sorted(points, key=lambda p: p[0]))
    if len(curve_points) >= 3:
        fitted = _build_spline(list(curve_points))
    else:
        fitted = FittedCurve(method=InterpolationMethod.LINEAR, points=curve_points)
    return _engine_interpolate(fitted, target_years)


def build_full_curve(raw_curve: dict[str, Decimal]) -> dict[str, Decimal]:
    if not raw_curve:
        return {}
    points = build_curve_points(raw_curve)
    all_tenors = ["3M", "6M", "9M", "1Y", "2Y", "3Y", "4Y", "5Y", "6Y", "7Y", "10Y", "20Y", "30Y"]
    full: dict[str, Decimal] = {}
    for tenor in all_tenors:
        if tenor in raw_curve:
            full[tenor] = raw_curve[tenor]
        else:
            full[tenor] = interpolate_rate(points, tenor_to_years(tenor))
    return full


# --- Period resolution ---

def resolve_period(report_date: date, period_type: str) -> tuple[date, date]:
    if period_type == "YTD":
        return date(report_date.year, 1, 1), report_date
    if period_type == "TTM":
        start = date(report_date.year - 1, report_date.month, report_date.day)
        return start, report_date
    # MoM default
    first_of_month = report_date.replace(day=1)
    return first_of_month, report_date


# --- Standard scenarios ---

STANDARD_SCENARIOS: list[dict] = [
    {"name": "parallel_up_25bp", "description": "平行上移 25bp", "shocks": {"all": 25}},
    {"name": "parallel_up_50bp", "description": "平行上移 50bp", "shocks": {"all": 50}},
    {"name": "parallel_up_100bp", "description": "平行上移 100bp", "shocks": {"all": 100}},
    {"name": "parallel_down_25bp", "description": "平行下移 25bp", "shocks": {"all": -25}},
    {"name": "parallel_down_50bp", "description": "平行下移 50bp", "shocks": {"all": -50}},
    # 陡峭化/平坦化需覆盖 get_tenor_bucket 的全部桶，否则中间期限桶冲击为 0、
    # 情景损益被低估。非锚点桶按 1Y/10Y/30Y 锚点线性插值（取整 bp），
    # 端点外（6M）沿用最近锚点（1Y）值。
    # 口径说明（2026-07 经确认并存，勿擅自统一）：krd.py 的 STANDARD_KRD_SCENARIOS
    # 同名情景为 1Y∓25bp / 30Y±25bp 驼峰形，与此处 30Y±50bp 线性版本是两套已知口径。
    {
        "name": "steepening_50bp",
        "description": "陡峭化 50bp",
        "shocks": {
            "6M": -25, "1Y": -25, "2Y": -19, "3Y": -14, "5Y": -3,
            "7Y": 8, "10Y": 25, "20Y": 38, "30Y": 50,
        },
    },
    {
        "name": "flattening_50bp",
        "description": "平坦化 50bp",
        "shocks": {
            "6M": 25, "1Y": 25, "2Y": 19, "3Y": 14, "5Y": 3,
            "7Y": -8, "10Y": -25, "20Y": -38, "30Y": -50,
        },
    },
]
