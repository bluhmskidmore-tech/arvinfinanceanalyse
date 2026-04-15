from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any, Iterable, Mapping

from app.core_finance.safe_decimal import safe_decimal

_PREFERRED_TENORS = ("3Y", "5Y", "1Y")


def _get_value(record: Any, *keys: str, default: Any = None) -> Any:
    for key in keys:
        if isinstance(record, Mapping) and key in record:
            value = record[key]
        else:
            value = getattr(record, key, None)
        if value is not None:
            return value
    return default


def _coerce_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip()[:10])
        except ValueError:
            return None
    if hasattr(value, "date"):
        try:
            return value.date()
        except Exception:
            return None
    return None


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
    available_dates = sorted(curves_by_date.keys(), reverse=True)
    if not available_dates:
        return {
            "report_date": report_date.isoformat(),
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

    current_date = available_dates[0]
    tenor, aaa_spread_bp = _resolve_spread(
        curves_by_date,
        current_date,
        credit_curve_id="CN_CREDIT_AAA",
        base_curve_id="CN_GOVT",
        tenors=_PREFERRED_TENORS,
    )
    if tenor is None or aaa_spread_bp is None:
        return {
            "report_date": report_date.isoformat(),
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

    _, aa_minus_aaa_bp = _resolve_aa_minus_aaa(
        curves_by_date,
        current_date,
        tenors=(tenor, *tuple(item for item in _PREFERRED_TENORS if item != tenor)),
    )
    weekly_change_bp = _change_vs_prior(
        available_dates,
        curves_by_date,
        lookback_index=5,
        tenor=tenor,
    )
    monthly_change_bp = _change_vs_prior(
        available_dates,
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

    return {
        "report_date": report_date.isoformat(),
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
        "warnings": [],
    }
