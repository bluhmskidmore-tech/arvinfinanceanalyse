from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import date
from decimal import Decimal
from typing import Any

from backend.app.core_finance.macro.helpers import coerce_date as _coerce_date
from backend.app.core_finance.macro.helpers import get_value as _get_value
from backend.app.core_finance.safe_decimal import safe_decimal

_PREFERRED_TENORS = ("3Y", "5Y", "1Y")

_OBSERVATION_FLAGS = {
    "observation_only": True,
    "formal_use_allowed": False,
}


def _build_curves(
    curve_rows: Iterable[Any],
    *,
    report_date: date,
) -> dict[date, dict[str, dict[str, Decimal]]]:
    curves: dict[date, dict[str, dict[str, Decimal]]] = defaultdict(lambda: defaultdict(dict))
    for row in curve_rows:
        row_date = _coerce_date(_get_value(row, "biz_date", "report_date"))
        if row_date is None or row_date > report_date:
            continue
        curve_id = str(_get_value(row, "curve_id", default=""))
        tenor = str(_get_value(row, "tenor", default=""))
        rate_value = _get_value(row, "rate_value")
        if not curve_id or not tenor or rate_value is None:
            continue
        curves[row_date][curve_id][tenor] = safe_decimal(rate_value)
    return curves


def _resolve_spread(
    curves_by_date: Mapping[date, Mapping[str, Mapping[str, Decimal]]],
    target_date: date,
    *,
    credit_curve_id: str,
    base_curve_id: str,
    tenors: tuple[str, ...],
) -> tuple[str | None, Decimal | None]:
    curves = curves_by_date.get(target_date, {})
    credit_curve = curves.get(credit_curve_id, {})
    base_curve = curves.get(base_curve_id, {})
    for tenor in tenors:
        credit_value = credit_curve.get(tenor)
        base_value = base_curve.get(tenor)
        if credit_value is None or base_value is None:
            continue
        return tenor, (credit_value - base_value) * Decimal("100")
    return None, None


def _resolve_aa_minus_aaa(
    curves_by_date: Mapping[date, Mapping[str, Mapping[str, Decimal]]],
    target_date: date,
    *,
    tenors: tuple[str, ...],
) -> tuple[str | None, Decimal | None]:
    curves = curves_by_date.get(target_date, {})
    aa_curve = curves.get("CN_CREDIT_AA", {})
    aaa_curve = curves.get("CN_CREDIT_AAA", {})
    for tenor in tenors:
        aa_value = aa_curve.get(tenor)
        aaa_value = aaa_curve.get(tenor)
        if aa_value is None or aaa_value is None:
            continue
        return tenor, (aa_value - aaa_value) * Decimal("100")
    return None, None


def _change_vs_prior(
    dates: list[date],
    curves_by_date: Mapping[date, Mapping[str, Mapping[str, Decimal]]],
    *,
    lookback_index: int,
    tenor: str,
) -> Decimal | None:
    if len(dates) <= lookback_index:
        return None
    current_tenor, current_spread = _resolve_spread(
        curves_by_date,
        dates[0],
        credit_curve_id="CN_CREDIT_AAA",
        base_curve_id="CN_GOVT",
        tenors=(tenor,),
    )
    if current_tenor is None or current_spread is None:
        return None
    _, prior_spread = _resolve_spread(
        curves_by_date,
        dates[lookback_index],
        credit_curve_id="CN_CREDIT_AAA",
        base_curve_id="CN_GOVT",
        tenors=(tenor,),
    )
    if prior_spread is None:
        return None
    return current_spread - prior_spread


def compute_credit_spread_risk(
    curve_rows: Iterable[Any],
    *,
    report_date: date,
) -> dict[str, Any]:
    curves_by_date = _build_curves(curve_rows, report_date=report_date)
    all_dates = sorted(curves_by_date.keys(), reverse=True)
    if not all_dates:
        return {
            "report_date": report_date.isoformat(),
            "as_of_date": None,
            "data_status": "unavailable",
            **_OBSERVATION_FLAGS,
            "credit_spread_tenor": None,
            "aaa_spread_bp": None,
            "aa_minus_aaa_bp": None,
            "weekly_change_bp": None,
            "monthly_change_bp": None,
            "risk_score": 0,
            "risk_level": "UNAVAILABLE",
            "spread_regime": "unavailable",
            "alerts": [],
            "recommendation": "暂无信用利差数据。",
            "warnings": ["NO_CREDIT_CURVES"],
        }

    spread_dates: list[date] = []
    for sample_date in all_dates:
        _, sample_spread = _resolve_spread(
            curves_by_date,
            sample_date,
            credit_curve_id="CN_CREDIT_AAA",
            base_curve_id="CN_GOVT",
            tenors=_PREFERRED_TENORS,
        )
        if sample_spread is not None:
            spread_dates.append(sample_date)

    if not spread_dates:
        return {
            "report_date": report_date.isoformat(),
            "as_of_date": None,
            "data_status": "unavailable",
            **_OBSERVATION_FLAGS,
            "credit_spread_tenor": None,
            "aaa_spread_bp": None,
            "aa_minus_aaa_bp": None,
            "weekly_change_bp": None,
            "monthly_change_bp": None,
            "risk_score": 0,
            "risk_level": "UNAVAILABLE",
            "spread_regime": "unavailable",
            "alerts": [],
            "recommendation": "缺少 AAA 相对国债的利差节点。",
            "warnings": ["AAA_SPREAD_MISSING"],
        }

    current_date = spread_dates[0]
    tenor, aaa_spread_bp = _resolve_spread(
        curves_by_date,
        current_date,
        credit_curve_id="CN_CREDIT_AAA",
        base_curve_id="CN_GOVT",
        tenors=_PREFERRED_TENORS,
    )
    assert tenor is not None and aaa_spread_bp is not None

    tenor_dates = [
        sample_date
        for sample_date in spread_dates
        if _resolve_spread(
            curves_by_date,
            sample_date,
            credit_curve_id="CN_CREDIT_AAA",
            base_curve_id="CN_GOVT",
            tenors=(tenor,),
        )[1]
        is not None
    ]

    _, aa_minus_aaa_bp = _resolve_aa_minus_aaa(
        curves_by_date,
        current_date,
        tenors=(tenor,),
    )
    weekly_change_bp = _change_vs_prior(
        tenor_dates,
        curves_by_date,
        lookback_index=5,
        tenor=tenor,
    )
    monthly_change_bp = _change_vs_prior(
        tenor_dates,
        curves_by_date,
        lookback_index=21,
        tenor=tenor,
    )

    alerts: list[dict[str, str]] = []
    risk_score = 0

    if aaa_spread_bp >= Decimal("120"):
        alerts.append({"level": "CRITICAL", "message": "AAA 利差处于压力区间。"})
        risk_score += 40
    elif aaa_spread_bp >= Decimal("80"):
        alerts.append({"level": "WARNING", "message": "AAA 利差偏高。"})
        risk_score += 20

    if aa_minus_aaa_bp is not None:
        if aa_minus_aaa_bp >= Decimal("60"):
            alerts.append({"level": "CRITICAL", "message": "AA 相对 AAA 利差明显走阔。"})
            risk_score += 35
        elif aa_minus_aaa_bp >= Decimal("30"):
            alerts.append({"level": "WARNING", "message": "AA 相对 AAA 利差在走阔。"})
            risk_score += 15

    if weekly_change_bp is not None and abs(weekly_change_bp) >= Decimal("15"):
        alerts.append({"level": "WARNING", "message": "近一周 AAA 利差波动较大。"})
        risk_score += 10

    if monthly_change_bp is not None and abs(monthly_change_bp) >= Decimal("25"):
        alerts.append({"level": "WARNING", "message": "近一月 AAA 利差波动较大。"})
        risk_score += 15

    risk_score = min(100, max(0, risk_score))
    if risk_score >= 60:
        risk_level = "HIGH"
        recommendation = "优先高等级信用，压缩低等级利差敞口。"
    elif risk_score >= 30:
        risk_level = "MEDIUM"
        recommendation = "信用敞口宜有选择，密切关注利差走阔。"
    else:
        risk_level = "LOW"
        recommendation = "信用利差环境整体可控。"

    spread_regime = "neutral"
    if aaa_spread_bp >= Decimal("80") or (aa_minus_aaa_bp is not None and aa_minus_aaa_bp >= Decimal("30")):
        spread_regime = "wide"
    elif aaa_spread_bp <= Decimal("45") and (aa_minus_aaa_bp is None or aa_minus_aaa_bp <= Decimal("15")):
        spread_regime = "tight"

    warnings: list[str] = []
    if aa_minus_aaa_bp is None:
        warnings.append("AA_MINUS_AAA_UNAVAILABLE")
    if weekly_change_bp is None:
        warnings.append("WEEKLY_CHANGE_UNAVAILABLE")
    if monthly_change_bp is None:
        warnings.append("MONTHLY_CHANGE_UNAVAILABLE")

    return {
        "report_date": report_date.isoformat(),
        "as_of_date": current_date.isoformat(),
        "data_status": "degraded" if warnings else "complete",
        **_OBSERVATION_FLAGS,
        "credit_spread_tenor": tenor,
        "aaa_spread_bp": float(aaa_spread_bp),
        "aa_minus_aaa_bp": float(aa_minus_aaa_bp) if aa_minus_aaa_bp is not None else None,
        "weekly_change_bp": float(weekly_change_bp) if weekly_change_bp is not None else None,
        "monthly_change_bp": float(monthly_change_bp) if monthly_change_bp is not None else None,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "spread_regime": spread_regime,
        "alerts": alerts,
        "recommendation": recommendation,
        "warnings": warnings,
    }
