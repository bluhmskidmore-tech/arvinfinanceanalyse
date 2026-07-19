"""
M10: 宏观经济领先指标（纯函数，自 V1 macro_analysis.leading_indicator 迁入）。
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.core_finance.macro.helpers import to_decimal_or_none as _dn
from app.core_finance.macro.helpers import to_decimal_safe as _d
from app.core_finance.macro.helpers import to_rounded_float as _f

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


def _monthly_series(wide_rows_desc: list[dict[str, Any]]) -> dict[str, list[Decimal | None]]:
    # 缺失月保留为 None（而非 to_decimal_safe 的 0），由调用方在求均值时跳过，
    # 避免缺失月把均值人为拉向 0（审计 宏观 M-1）。
    seen: set[tuple[int, int]] = set()
    monthly_pmi: list[Decimal | None] = []
    monthly_m2: list[Decimal | None] = []
    monthly_sf: list[Decimal | None] = []
    monthly_term: list[Decimal | None] = []
    monthly_credit: list[Decimal | None] = []
    monthly_oil: list[Decimal | None] = []
    for r in wide_rows_desc:
        d = r.get("trade_date") or r.get("biz_date")
        if not hasattr(d, "year"):
            continue
        key = (d.year, d.month)
        if key in seen:
            continue
        seen.add(key)
        monthly_pmi.append(_dn(r.get("pmi")))
        monthly_m2.append(_dn(r.get("m2_yoy")))
        monthly_sf.append(_dn(r.get("social_financing_yoy")))
        monthly_term.append(_dn(r.get("term_spread_10y_1y")))
        monthly_credit.append(_dn(r.get("credit_spread_aaa_3y")))
        monthly_oil.append(_dn(r.get("brent_oil")))
    return {
        "pmi": monthly_pmi,
        "m2": monthly_m2,
        "sf": monthly_sf,
        "term": monthly_term,
        "credit": monthly_credit,
        "oil": monthly_oil,
    }


def _history_mean(values: list[Decimal | None]) -> tuple[Decimal | None, int, int]:
    """只对可用月求均值（缺失月跳过）；返回 (均值, 有效样本数, 总月数)。"""
    total = len(values)
    available = [v for v in values if v is not None]
    if not available:
        return None, 0, total
    return sum(available) / len(available), len(available), total


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
            "history_samples": {
                "m2_yoy": {"used": 0, "total": 0},
                "social_financing_yoy": {"used": 0, "total": 0},
                "commodity": {"used": 0, "total": 0},
            },
            "warnings": ["NO_MACRO_ROWS"],
        }

    today = wide_rows_desc[0]
    ms = _monthly_series(wide_rows_desc)
    monthly_pmi = ms["pmi"]
    monthly_m2 = ms["m2"]
    monthly_sf = ms["sf"]
    monthly_oil = ms["oil"]

    weights = _M10_WEIGHTS
    thresholds = _M10_LEI_THRESHOLDS

    pmi_val = _d(today.get("pmi"))
    if today.get("pmi") is not None:
        pmi_score = (pmi_val - Decimal("30")) / Decimal("0.4")
        pmi_score = max(Decimal("0"), min(Decimal("100"), pmi_score))
    else:
        pmi_score = Decimal("50")

    # 均值只对可用月计算（缺失月为 None 时跳过，不再被 0 污染）；有效样本数随结果披露。
    m2_cur = monthly_m2[0] if monthly_m2 else None
    m2_avg, m2_used, m2_total = _history_mean(monthly_m2[1:])
    if m2_avg and m2_cur:
        m2_score = Decimal("50") + (m2_cur - m2_avg) * Decimal("5")
        m2_score = max(Decimal("0"), min(Decimal("100"), m2_score))
    else:
        m2_score = Decimal("50")

    sf_cur = monthly_sf[0] if monthly_sf else None
    sf_avg, sf_used, sf_total = _history_mean(monthly_sf[1:])
    if sf_avg and sf_cur:
        sf_score = Decimal("50") + (sf_cur - sf_avg) * Decimal("5")
        sf_score = max(Decimal("0"), min(Decimal("100"), sf_score))
    else:
        sf_score = Decimal("50")

    term_val = _dn(today.get("term_spread_10y_1y"))
    if term_val is not None:
        term_score = Decimal("50") + term_val / Decimal("2")
        term_score = max(Decimal("0"), min(Decimal("100"), term_score))
    else:
        term_score = None

    credit_val = _dn(today.get("credit_spread_aaa_3y"))
    if credit_val is not None:
        credit_score = Decimal("100") - credit_val
        credit_score = max(Decimal("0"), min(Decimal("100"), credit_score))
    else:
        credit_score = None

    oil_cur = monthly_oil[0] if monthly_oil else None
    oil_avg, oil_used, oil_total = _history_mean(monthly_oil[1:])
    if oil_avg and oil_cur:
        commodity_score = Decimal("50") + (oil_cur - oil_avg) / oil_avg * Decimal("500")
        commodity_score = max(Decimal("0"), min(Decimal("100"), commodity_score))
    else:
        commodity_score = Decimal("50")

    # 分项缺失（term_score / credit_score 为 None）时不参与加权，剩余分项按权重重归一，
    # 避免缺数据被 to_decimal_safe 的 0 默认值污染评分（详见审计问题 1）。
    component_scores: dict[str, Decimal | None] = {
        "pmi": pmi_score,
        "m2_yoy": m2_score,
        "social_financing_yoy": sf_score,
        "term_spread": term_score,
        "credit_spread": credit_score,
        "commodity": commodity_score,
    }
    available_weight = sum(
        weights[name] for name, score in component_scores.items() if score is not None
    )
    if available_weight > 0:
        lei = sum(
            score * weights[name] for name, score in component_scores.items() if score is not None
        ) / available_weight
        lei = lei.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    else:
        lei = None

    if lei is not None:
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
    else:
        economic_state = "数据不足"

    if len(monthly_pmi) >= 2:
        pmi_prev = monthly_pmi[1]
        if today.get("pmi") is None or pmi_prev is None:
            trend = "平稳"
        elif pmi_val > pmi_prev:
            trend = "上升"
        elif pmi_val < pmi_prev:
            trend = "下降"
        else:
            trend = "平稳"
    else:
        trend = "平稳"

    warnings: list[str] = []
    if term_val is None:
        warnings.append("TERM_SPREAD_MISSING")
    if credit_val is None:
        warnings.append("CREDIT_SPREAD_AAA_MISSING")
    if m2_used < m2_total:
        warnings.append("M2_HISTORY_MISSING_MONTHS")
    if sf_used < sf_total:
        warnings.append("SOCIAL_FINANCING_HISTORY_MISSING_MONTHS")
    if oil_used < oil_total:
        warnings.append("COMMODITY_HISTORY_MISSING_MONTHS")
    if lei is None:
        warnings.append("LEI_ALL_COMPONENTS_MISSING")

    return {
        "report_date": report_date.isoformat(),
        "data_status": "degraded" if warnings else "complete",
        "lei_index": _f(lei) if lei is not None else None,
        "economic_state": economic_state,
        "trend": trend,
        "pmi_score": _f(pmi_score),
        "m2_score": _f(m2_score),
        "social_financing_score": _f(sf_score),
        "term_spread_score": _f(term_score) if term_score is not None else None,
        "credit_spread_score": _f(credit_score) if credit_score is not None else None,
        "commodity_score": _f(commodity_score),
        "history_samples": {
            "m2_yoy": {"used": m2_used, "total": m2_total},
            "social_financing_yoy": {"used": sf_used, "total": sf_total},
            "commodity": {"used": oil_used, "total": oil_total},
        },
        "warnings": warnings,
    }
