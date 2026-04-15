"""
损益归因核心工具（自 MOSS-SYSTEM-V1 app.services.attribution_core 迁入 Phase A 子集）。

不含：get_ftp_rate（依赖全局配置）、compute_bond_four_effects（依赖 bond_analytics.common）、
log_attribution_result（可选）。
"""
from __future__ import annotations

import logging
from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .safe_decimal import safe_decimal

logger = logging.getLogger(__name__)

DEFAULT_RESIDUAL_THRESHOLD_WARN = Decimal("0.05")
DEFAULT_RESIDUAL_THRESHOLD_BAD = Decimal("0.15")

MIN_DURATION = Decimal("0.01")
MAX_DURATION = Decimal("30.0")
DEFAULT_DURATION = Decimal("3.0")


class DayCountConvention(str, Enum):
    ACT_365 = "ACT/365"
    ACT_360 = "ACT/360"
    ACT_ACT = "ACT/ACT"
    THIRTY_360 = "30/360"


class QualityFlag(str, Enum):
    OK = "OK"
    WARN = "WARN"
    BAD = "BAD"
    NA = "N/A"


@dataclass
class ReconciliationResult:
    explained_pnl: Decimal = Decimal("0")
    actual_pnl: Decimal = Decimal("0")
    residual: Decimal = Decimal("0")
    residual_ratio: Optional[Decimal] = None
    quality_flag: QualityFlag = QualityFlag.NA
    explained_breakdown: Dict[str, Decimal] = field(default_factory=dict)
    diagnostics: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "explained_pnl": float(self.explained_pnl),
            "actual_pnl": float(self.actual_pnl),
            "residual": float(self.residual),
            "residual_ratio": float(self.residual_ratio) if self.residual_ratio is not None else None,
            "quality_flag": self.quality_flag.value,
            "explained_breakdown": {k: float(v) for k, v in self.explained_breakdown.items()},
            "diagnostics": self.diagnostics,
        }


def calculate_reconciliation(
    explained_components: Dict[str, Decimal],
    actual_pnl: Decimal,
    threshold_warn: Decimal = DEFAULT_RESIDUAL_THRESHOLD_WARN,
    threshold_bad: Decimal = DEFAULT_RESIDUAL_THRESHOLD_BAD,
    context: str = "",
) -> ReconciliationResult:
    result = ReconciliationResult()
    result.explained_breakdown = explained_components.copy()
    result.actual_pnl = actual_pnl

    explained_pnl_sum = Decimal("0")
    for _key, value in explained_components.items():
        if not isinstance(value, Decimal):
            explained_pnl_sum += safe_decimal(value)
        else:
            explained_pnl_sum += value
    result.explained_pnl = explained_pnl_sum

    if not isinstance(actual_pnl, Decimal):
        actual_pnl = safe_decimal(actual_pnl)
    result.residual = actual_pnl - result.explained_pnl

    if actual_pnl != Decimal("0"):
        residual_abs = abs(result.residual)
        actual_pnl_abs = abs(actual_pnl)
        if not isinstance(residual_abs, Decimal):
            residual_abs = safe_decimal(residual_abs)
        if not isinstance(actual_pnl_abs, Decimal):
            actual_pnl_abs = safe_decimal(actual_pnl_abs)
        result.residual_ratio = residual_abs / actual_pnl_abs

        threshold_warn_dec = threshold_warn if isinstance(threshold_warn, Decimal) else safe_decimal(threshold_warn)
        threshold_bad_dec = threshold_bad if isinstance(threshold_bad, Decimal) else safe_decimal(threshold_bad)

        if result.residual_ratio < threshold_warn_dec:
            result.quality_flag = QualityFlag.OK
        elif result.residual_ratio < threshold_bad_dec:
            result.quality_flag = QualityFlag.WARN
            result.diagnostics.append(
                f"残差比例 {float(result.residual_ratio)*100:.2f}% 超过警告阈值 {float(threshold_warn)*100:.0f}%"
            )
            logger.warning(
                "[Reconciliation] %s: residual_ratio=%.2f%% (WARN)",
                context,
                float(result.residual_ratio) * 100,
            )
        else:
            result.quality_flag = QualityFlag.BAD
            result.diagnostics.append(
                f"残差比例 {float(result.residual_ratio)*100:.2f}% 超过错误阈值 {float(threshold_bad)*100:.0f}%"
            )
            logger.error(
                "[Reconciliation] %s: residual_ratio=%.2f%% (BAD)",
                context,
                float(result.residual_ratio) * 100,
            )
    else:
        if result.explained_pnl == Decimal("0"):
            result.quality_flag = QualityFlag.OK
            result.residual_ratio = Decimal("0")
        else:
            result.quality_flag = QualityFlag.WARN
            result.diagnostics.append("actual_pnl 为 0 但 explained_pnl 不为 0")

    return result


def get_days_in_month(year: int, month: int) -> int:
    _, days = monthrange(year, month)
    return days


def get_day_count_factor(
    report_date: date,
    convention: DayCountConvention = DayCountConvention.ACT_365,
    period_days: Optional[int] = None,
) -> Decimal:
    if period_days is None:
        period_days = get_days_in_month(report_date.year, report_date.month)

    period_days_dec = Decimal(str(period_days))

    if convention == DayCountConvention.ACT_365:
        return period_days_dec / Decimal("365")
    if convention == DayCountConvention.ACT_360:
        return period_days_dec / Decimal("360")
    if convention == DayCountConvention.ACT_ACT:
        import calendar

        days_in_year = 366 if calendar.isleap(report_date.year) else 365
        return period_days_dec / Decimal(str(days_in_year))
    if convention == DayCountConvention.THIRTY_360:
        return Decimal("30") / Decimal("360")
    return period_days_dec / Decimal("365")


def get_month_end_date(year: int, month: int) -> date:
    _, last_day = monthrange(year, month)
    return date(year, month, last_day)


def get_previous_month(report_date: date) -> date:
    if report_date.month == 1:
        return get_month_end_date(report_date.year - 1, 12)
    return get_month_end_date(report_date.year, report_date.month - 1)


def get_same_month_last_year(report_date: date) -> date:
    return get_month_end_date(report_date.year - 1, report_date.month)


def round_decimal(
    val: Decimal,
    precision: str = "0.0001",
    rounding: str = ROUND_HALF_UP,
) -> Decimal:
    return val.quantize(Decimal(precision), rounding=rounding)


def safe_divide(
    numerator: Decimal,
    denominator: Decimal,
    default: Decimal = Decimal("0"),
) -> Decimal:
    if denominator == Decimal("0"):
        return default
    return numerator / denominator


def estimate_modified_duration(
    maturity_date: Optional[date],
    report_date: date,
    coupon_rate: Decimal,
    ytm: Optional[Decimal] = None,
    coupon_frequency: int = 1,
) -> Decimal:
    if maturity_date is None:
        return DEFAULT_DURATION

    days_to_maturity = (maturity_date - report_date).days
    if days_to_maturity <= 0:
        return MIN_DURATION

    maturity_years = Decimal(str(days_to_maturity)) / Decimal("365")
    n = max(1, int(coupon_frequency))
    num_periods = max(1, int(round(float(maturity_years) * n)))

    coupon_decimal = coupon_rate if coupon_rate > Decimal("0") else Decimal("0")
    c_per_period = coupon_decimal / Decimal(str(n))

    if ytm is not None and ytm > Decimal("0.001"):
        ytm_decimal = ytm
    else:
        ytm_decimal = coupon_decimal if coupon_decimal > Decimal("0.001") else Decimal("0.01")
    y_per = ytm_decimal / Decimal(str(n))
    one_plus_y = Decimal("1") + y_per

    price = Decimal("0")
    pv_t = Decimal("0")
    for t in range(1, num_periods + 1):
        cf = c_per_period if t < num_periods else c_per_period + Decimal("1")
        discount = one_plus_y ** (-t)
        price += cf * discount
        pv_t += Decimal(str(t)) * cf * discount

    if price <= Decimal("0"):
        return max(MIN_DURATION, min(MAX_DURATION, maturity_years))

    macd_periods = pv_t / price
    macd_years = macd_periods / Decimal(str(n))
    modified_duration = macd_years / one_plus_y

    return max(MIN_DURATION, min(MAX_DURATION, modified_duration))


def estimate_convexity(duration: Decimal) -> Decimal:
    return duration * duration * Decimal("0.01")


def interpolate_yield_curve(
    yield_curve: Dict[int, Decimal],
    target_tenor: float,
) -> Decimal:
    if not yield_curve:
        return Decimal("0")

    tenors = sorted(yield_curve.keys())
    target = Decimal(str(target_tenor))

    if target <= Decimal(str(tenors[0])):
        return yield_curve[tenors[0]]
    if target >= Decimal(str(tenors[-1])):
        return yield_curve[tenors[-1]]

    for i in range(len(tenors) - 1):
        t1, t2 = tenors[i], tenors[i + 1]
        if Decimal(str(t1)) <= target <= Decimal(str(t2)):
            y1, y2 = yield_curve[t1], yield_curve[t2]
            return y1 + (y2 - y1) * (target - Decimal(str(t1))) / Decimal(str(t2 - t1))

    return Decimal("0")


TENOR_BUCKETS = [
    ("ON", 0.0, 0.01),
    ("7D", 0.01, 0.02),
    ("1M", 0.02, 0.12),
    ("3M", 0.12, 0.30),
    ("6M", 0.30, 0.75),
    ("1Y", 0.75, 1.5),
    ("2Y", 1.5, 2.5),
    ("3Y", 2.5, 4.0),
    ("5Y", 4.0, 6.0),
    ("7Y", 6.0, 8.5),
    ("10Y", 8.5, 12.5),
    ("15Y", 12.5, 17.5),
    ("20Y", 17.5, 25.0),
    ("30Y", 25.0, 100.0),
]


def get_tenor_bucket(maturity_years: float) -> str:
    for label, min_years, max_years in TENOR_BUCKETS:
        if min_years <= maturity_years < max_years:
            return label
    return "30Y"


def get_adjacent_tenor_buckets(maturity_years: float) -> Tuple[str, str, float]:
    key_tenors = [1, 2, 3, 5, 7, 10, 15, 20, 30]

    if maturity_years <= key_tenors[0]:
        return "1Y", "1Y", 0.0
    if maturity_years >= key_tenors[-1]:
        return "30Y", "30Y", 1.0

    for i in range(len(key_tenors) - 1):
        t1, t2 = key_tenors[i], key_tenors[i + 1]
        if t1 <= maturity_years <= t2:
            weight = (maturity_years - t1) / (t2 - t1)
            return f"{t1}Y", f"{t2}Y", weight

    return "10Y", "10Y", 0.5


class PnLScope(str, Enum):
    TOTAL_PNL = "total_pnl"
    INTEREST_ONLY = "interest_only"
    FV_CHANGE_ONLY = "fv_change_only"
    REALIZED_ONLY = "realized_only"
    UNREALIZED_ONLY = "unrealized_only"


def validate_pnl_scope(
    interest_income: Decimal,
    fair_value_change: Decimal,
    capital_gain: Decimal,
    total_pnl: Decimal,
    tolerance: Decimal = Decimal("0.01"),
) -> Tuple[bool, str]:
    calculated_total = interest_income + fair_value_change + capital_gain
    diff = abs(total_pnl - calculated_total)

    if diff <= tolerance:
        return True, "口径一致"
    pct = safe_divide(diff, abs(total_pnl), Decimal("0")) * 100
    return False, f"口径不一致: 差异 {float(diff):.2f} 元 ({float(pct):.2f}%)"
