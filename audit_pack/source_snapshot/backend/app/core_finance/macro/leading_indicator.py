"""
M10: 宏观经济领先指标（纯函数，自 V1 macro_analysis.leading_indicator 迁入）。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from app.core_finance.macro.helpers import to_decimal_safe as _d, to_rounded_float as _f

# 与 V1 config.M10_* 对齐
_M10_WEIGHTS = {
    "pmi": Decimal("0.20"),
    "m2_yoy": Decimal("0.15"),
    "social_financing_yoy": Decimal("0.15"),
    "term_spread": Decimal("0.20"),
    "credit_spread": Decimal("0.15"),
    "commodity": Decimal("0.15"),
}
_M10_LEI_THRESHOLDS = {
    "strong_expansion": 70,
    "moderate_expansion": 55,
    "neutral_high": 50,
    "neutral_low": 45,
    "moderate_contraction": 30,
}


def _monthly_series(wide_rows_desc: list[dict[str, Any]]) -> dict[str, list[Decimal]]:
    seen: set[tuple[int, int]] = set()
    monthly_pmi: list[Decimal] = []
    monthly_m2: list[Decimal] = []
    monthly_sf: list[Decimal] = []
    monthly_term: list[Decimal] = []
    monthly_credit: list[Decimal] = []
    monthly_oil: list[Decimal] = []
    for r in wide_rows_desc:
        d = r.get("trade_date") or r.get("biz_date")
        if not hasattr(d, "year"):
            continue
        key = (d.year, d.month)
        if key in seen:
            continue
        seen.add(key)
        monthly_pmi.append(_d(r.get("pmi")))
        monthly_m2.append(_d(r.get("m2_yoy")))
        monthly_sf.append(_d(r.get("social_financing_yoy")))
        monthly_term.append(_d(r.get("term_spread_10y_1y")))
        monthly_credit.append(_d(r.get("credit_spread_aaa_3y")))
        monthly_oil.append(_d(r.get("brent_oil")))
    return {
        "pmi": monthly_pmi,
        "m2": monthly_m2,
        "sf": monthly_sf,
        "term": monthly_term,
        "credit": monthly_credit,
        "oil": monthly_oil,
    }


def compute_leading_indicator(
    wide_rows_desc: list[dict[str, Any]],
    report_date: date,
) -> dict[str, Any]:
    if not wide_rows_desc:
        return {
            "report_date": report_date.isoformat(),
            "data_status": "unavailable",
            "lei_index": 50.0,
            "economic_state": "中性",
            "trend": "平稳",
            "pmi_score": None,
            "m2_score": None,
            "social_financing_score": None,
            "term_spread_score": None,
            "credit_spread_score": None,
            "commodity_score": None,
            "warnings": ["NO_MACRO_ROWS"],
        }

    today = wide_rows_desc[0]
    ms = _monthly_series(wide_rows_desc)
    monthly_pmi = ms["pmi"]
    monthly_m2 = ms["m2"]
    monthly_sf = ms["sf"]
    monthly_term = ms["term"]
    monthly_credit = ms["credit"]
    monthly_oil = ms["oil"]

    weights = _M10_WEIGHTS
    thresholds = _M10_LEI_THRESHOLDS

    pmi_val = _d(today.get("pmi"))
    if pmi_val:
        pmi_score = (pmi_val - Decimal("30")) / Decimal("0.4")
        pmi_score = max(Decimal("0"), min(Decimal("100"), pmi_score))
    else:
        pmi_score = Decimal("50")

    if len(monthly_m2) >= 2:
        m2_avg = sum(monthly_m2[1:]) / (len(monthly_m2) - 1)
        m2_cur = monthly_m2[0]
        if m2_avg and m2_cur:
            m2_score = Decimal("50") + (m2_cur - m2_avg) * Decimal("5")
            m2_score = max(Decimal("0"), min(Decimal("100"), m2_score))
        else:
            m2_score = Decimal("50")
    else:
        m2_score = Decimal("50")

    if len(monthly_sf) >= 2:
        sf_avg = sum(monthly_sf[1:]) / (len(monthly_sf) - 1)
        sf_cur = monthly_sf[0]
        if sf_avg and sf_cur:
            sf_score = Decimal("50") + (sf_cur - sf_avg) * Decimal("5")
            sf_score = max(Decimal("0"), min(Decimal("100"), sf_score))
        else:
            sf_score = Decimal("50")
    else:
        sf_score = Decimal("50")

    term_val = _d(today.get("term_spread_10y_1y"))
    term_score = Decimal("50") + term_val / Decimal("2")
    term_score = max(Decimal("0"), min(Decimal("100"), term_score))

    credit_val = _d(today.get("credit_spread_aaa_3y"))
    credit_score = Decimal("100") - credit_val
    credit_score = max(Decimal("0"), min(Decimal("100"), credit_score))

    if len(monthly_oil) >= 2 and monthly_oil[0]:
        oil_avg = sum(monthly_oil[1:]) / (len(monthly_oil) - 1)
        oil_cur = monthly_oil[0]
        if oil_avg and oil_cur:
            commodity_score = Decimal("50") + (oil_cur - oil_avg) / oil_avg * Decimal("500")
            commodity_score = max(Decimal("0"), min(Decimal("100"), commodity_score))
        else:
            commodity_score = Decimal("50")
    else:
        commodity_score = Decimal("50")

    lei = (
        pmi_score * weights["pmi"]
        + m2_score * weights["m2_yoy"]
        + sf_score * weights["social_financing_yoy"]
        + term_score * weights["term_spread"]
        + credit_score * weights["credit_spread"]
        + commodity_score * weights["commodity"]
    )
    lei = lei.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    fv = float(lei)
    if fv >= thresholds["strong_expansion"]:
        economic_state = "强劲扩张"
    elif fv >= thresholds["moderate_expansion"]:
        economic_state = "温和扩张"
    elif fv >= thresholds["neutral_high"]:
        economic_state = "中性"
    elif fv >= thresholds["neutral_low"]:
        economic_state = "中性"
    elif fv >= thresholds["moderate_contraction"]:
        economic_state = "温和收缩"
    else:
        economic_state = "显著收缩"

    if len(monthly_pmi) >= 2:
        pmi_prev = monthly_pmi[1]
        if pmi_val > pmi_prev:
            trend = "上升"
        elif pmi_val < pmi_prev:
            trend = "下降"
        else:
            trend = "平稳"
    else:
        trend = "平稳"

    warnings: list[str] = []
    if today.get("term_spread_10y_1y") is None:
        warnings.append("TERM_SPREAD_MISSING")
    if today.get("credit_spread_aaa_3y") is None:
        warnings.append("CREDIT_SPREAD_AAA_MISSING")

    return {
        "report_date": report_date.isoformat(),
        "data_status": "degraded" if warnings else "complete",
        "lei_index": _f(lei),
        "economic_state": economic_state,
        "trend": trend,
        "pmi_score": _f(pmi_score),
        "m2_score": _f(m2_score),
        "social_financing_score": _f(sf_score),
        "term_spread_score": _f(term_score),
        "credit_spread_score": _f(credit_score),
        "commodity_score": _f(commodity_score),
        "warnings": warnings,
    }
