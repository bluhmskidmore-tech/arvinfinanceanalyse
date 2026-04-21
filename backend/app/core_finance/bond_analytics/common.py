"""Shared utilities for bond analytics calculations."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.app.core_finance.config.classification_rules import infer_invest_type
from backend.app.core_finance.field_normalization import (
    ACCOUNTING_BASIS_AC,
    ACCOUNTING_BASIS_FVOCI,
    derive_accounting_basis_value,
)

# --- Decimal helpers ---

def safe_decimal(value) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def decimal_to_str(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"))) if isinstance(value, Decimal) else str(value)


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

    n_periods = int(years_to_maturity * coupon_frequency)
    if n_periods <= 0:
        return years_to_maturity

    c = coupon_rate / coupon_frequency if coupon_frequency > 0 else coupon_rate
    y = ytm / coupon_frequency if coupon_frequency > 0 else ytm

    if y == 0:
        return years_to_maturity

    pv_sum = Decimal("0")
    price = Decimal("0")

    for t in range(1, n_periods + 1):
        discount = (Decimal("1") + y) ** t
        cf = c if t < n_periods else c + Decimal("1")
        pv = cf / discount
        pv_sum += Decimal(str(t)) / Decimal(str(coupon_frequency)) * pv
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
) -> Decimal:
    if not maturity_date or not report_date:
        return Decimal("3")

    remaining_days = (maturity_date - report_date).days
    if remaining_days <= 0:
        return Decimal("0")

    years = Decimal(str(remaining_days)) / Decimal("365")

    if coupon_rate > 0 and ytm > 0:
        return compute_macaulay_duration(coupon_rate, ytm, years, coupon_frequency=1)

    return years


def estimate_modified_duration(
    macaulay_duration: Decimal,
    ytm: Decimal,
    coupon_frequency: int = 1,
) -> Decimal:
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


def tenor_to_years(tenor: str) -> float:
    return TENOR_YEARS.get(tenor, 5.0)


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
    points = []
    for tenor, rate in curve.items():
        years = tenor_to_years(tenor)
        points.append((years, safe_decimal(rate)))
    return sorted(points, key=lambda x: x[0])


def interpolate_rate(points: list[tuple[float, Decimal]], target_years: float) -> Decimal:
    if not points:
        return Decimal("0")
    if target_years <= points[0][0]:
        return points[0][1]
    if target_years >= points[-1][0]:
        return points[-1][1]
    for i in range(len(points) - 1):
        y0, r0 = points[i]
        y1, r1 = points[i + 1]
        if y0 <= target_years <= y1:
            span = y1 - y0
            if span <= 0:
                return r0
            frac = Decimal(str((target_years - y0) / span))
            return r0 + frac * (r1 - r0)
    return points[-1][1]


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
    {"name": "steepening_50bp", "description": "陡峭化 50bp", "shocks": {"1Y": -25, "10Y": 25, "30Y": 50}},
    {"name": "flattening_50bp", "description": "平坦化 50bp", "shocks": {"1Y": 25, "10Y": -25, "30Y": -50}},
]
