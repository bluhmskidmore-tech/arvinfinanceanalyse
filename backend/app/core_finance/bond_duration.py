"""
债券久期 / 会计推断（自 MOSS-SYSTEM-V1 bond_analytics/common.py 迁入，无 SQLAlchemy / Wind）。

与 attribution_core.estimate_modified_duration(maturity, report, coupon, ytm) 不同：
本模块提供 Macaulay 闭合公式 + Macaulay→修正久期转换（modified_duration_from_macaulay）。
"""
from __future__ import annotations

import logging
import math
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from backend.app.core_finance.config.classification_rules import infer_invest_type
from backend.app.core_finance.field_normalization import (
    ACCOUNTING_BASIS_AC,
    ACCOUNTING_BASIS_FVOCI,
    derive_accounting_basis_value,
)

logger = logging.getLogger(__name__)


def _coerce_date_like(value: object | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if hasattr(value, "to_pydatetime"):
        try:
            return value.to_pydatetime().date()
        except Exception:
            return None
    if hasattr(value, "date"):
        try:
            return value.date()
        except Exception:
            return None
    return None


def _estimate_duration_proxy_years(
    maturity_date: object | None,
    report_date: object,
    bond_code: str = "",
) -> float:
    code = str(bond_code or "").upper()
    if code.startswith("SA") or code.startswith("SCP"):
        return 0.25

    maturity = _coerce_date_like(maturity_date)
    report = _coerce_date_like(report_date)
    if maturity is None or report is None:
        return 3.0

    try:
        return max(0.0, (maturity - report).days / 365.0)
    except Exception:
        return 3.0


def compute_macaulay_duration(
    years_to_maturity: Decimal,
    coupon_rate: Decimal,
    ytm: Decimal,
    frequency: int = 1,
) -> Decimal:
    _ZERO = Decimal("0")
    _ONE = Decimal("1")
    _TWO = Decimal("2")
    _QUARTER = Decimal("0.25")
    _TINY = Decimal("0.0001")
    _FLOOR = Decimal("0.1")

    if years_to_maturity <= _ZERO:
        return _ZERO
    if years_to_maturity <= _QUARTER:
        return years_to_maturity

    if coupon_rate <= _ZERO:
        return years_to_maturity

    freq_d = Decimal(frequency)

    if ytm <= _TINY:
        if coupon_rate <= _ZERO:
            return years_to_maturity
        factor = _ONE - coupon_rate * years_to_maturity / (_TWO * (_ONE + coupon_rate * years_to_maturity))
        if factor < _FLOOR:
            factor = _FLOOR
        return (years_to_maturity * factor).quantize(Decimal("0.0001"))

    try:
        n_periods = int((years_to_maturity * freq_d).to_integral_value())
        if n_periods <= 0:
            n_periods = 1
        c_per = coupon_rate / freq_d
        y_per = ytm / freq_d

        one_plus_y = _ONE + y_per
        pow_n = one_plus_y ** n_periods  # int exponent — Decimal supports this

        term1 = one_plus_y / y_per

        numer = one_plus_y + n_periods * (c_per - y_per)
        denom = c_per * (pow_n - _ONE) + y_per

        if abs(denom) < Decimal("1E-12"):
            return years_to_maturity

        term2 = numer / denom
        mac_dur_years = (term1 - term2) / freq_d

        if mac_dur_years <= _ZERO or mac_dur_years > years_to_maturity:
            return years_to_maturity

        return mac_dur_years.quantize(Decimal("0.0001"))

    except (OverflowError, ZeroDivisionError, ValueError, InvalidOperation):
        return years_to_maturity


def _estimate_macaulay_duration_years(
    maturity_date: date,
    report_date: date,
    coupon_rate: Decimal,
    ytm: Decimal | None = None,
    coupon_frequency: int = 1,
) -> Decimal:
    remaining_days = (maturity_date - report_date).days
    if remaining_days <= 0:
        return Decimal("0")
    years_to_maturity = Decimal(str(remaining_days)) / Decimal("365")

    if ytm is not None and ytm > Decimal("0") and coupon_rate > Decimal("0"):
        return compute_macaulay_duration(
            years_to_maturity, coupon_rate, ytm, frequency=coupon_frequency
        )

    if coupon_rate > Decimal("0"):
        return compute_macaulay_duration(
            years_to_maturity, coupon_rate, coupon_rate, frequency=coupon_frequency
        )

    return years_to_maturity


def infer_accounting_class(asset_class: str | None) -> str:
    """Map accounting label to AC / OCI / TPL (legacy bond_duration buckets).

    W-bond-2026-04-21: delegates H/A/T to ``classification_rules.infer_invest_type``
    (caliber ``hat_mapping``), then ``derive_accounting_basis_value``. Preserves
    fallbacks for substrings not fully covered by the canonical matcher (e.g.
    ``摊余`` without ``摊余成本``, bare ``AC`` token).
    """
    if not asset_class:
        return "TPL"
    invest = infer_invest_type(None, None, str(asset_class))
    if invest is not None:
        basis = derive_accounting_basis_value(invest)  # type: ignore[arg-type]
        if basis == ACCOUNTING_BASIS_AC:
            return "AC"
        if basis == ACCOUNTING_BASIS_FVOCI:
            return "OCI"
        return "TPL"
    s = str(asset_class)
    if "债权投资" in s or "摊余" in s or ACCOUNTING_BASIS_AC in s:
        return "AC"
    if "出售" in s or "OCI" in s or "可供" in s:
        return "OCI"
    return "TPL"


def estimate_duration(
    maturity_date: date | None,
    report_date: date,
    coupon_rate: Decimal,
    bond_code: str = "",
    ytm: Decimal | None = None,
    wind_metrics: dict[str, Any] | None = None,
    coupon_frequency: int = 1,
) -> Decimal:
    code = str(bond_code or "").upper()
    if code.startswith("SA") or code.startswith("SCP"):
        return Decimal("0.25")

    if wind_metrics and bond_code in wind_metrics:
        wind_dur = wind_metrics[bond_code].get("duration")
        if wind_dur is not None and wind_dur > Decimal("0"):
            return wind_dur

    mat = _coerce_date_like(maturity_date)
    report = _coerce_date_like(report_date)
    if mat is not None and report is not None:
        return _estimate_macaulay_duration_years(
            mat, report, coupon_rate, ytm, coupon_frequency
        )

    logger.warning("Bond %s missing maturity_date, using proxy duration", bond_code)
    return Decimal(str(_estimate_duration_proxy_years(maturity_date, report_date, bond_code)))


def modified_duration_from_macaulay(
    duration: Decimal,
    ytm: Decimal,
    coupon_frequency: int = 1,
    wind_mod_dur: Decimal | None = None,
) -> Decimal:
    """Macaulay → 修正久期；与旧 common.estimate_modified_duration(duration, ytm, ...) 一致。"""
    if wind_mod_dur is not None and wind_mod_dur > Decimal("0"):
        return wind_mod_dur

    if ytm <= Decimal("-0.99"):
        return duration
    if ytm <= 0:
        return duration
    divisor = Decimal("1") + ytm / Decimal(str(coupon_frequency))
    if divisor <= 0:
        return duration
    return duration / divisor


def estimate_convexity_bond(
    duration: Decimal,
    ytm: Decimal,
    wind_convexity: Decimal | None = None,
    coupon_frequency: int = 2,
) -> Decimal:
    """与旧 common.estimate_convexity 公式一致（供后续迁移 quantitative 测试）。"""
    if wind_convexity is not None and wind_convexity > Decimal("0"):
        return wind_convexity

    if not coupon_frequency or coupon_frequency <= 0:
        coupon_frequency = 1
    n = Decimal(str(coupon_frequency))
    numerator = duration * duration + duration * (Decimal("1") + Decimal("1") / n)
    if ytm <= 0:
        return numerator * Decimal("1.1")
    denominator = (Decimal("1") + ytm / n) * (Decimal("1") + ytm / n)
    if denominator <= 0:
        return numerator
    return numerator / denominator
