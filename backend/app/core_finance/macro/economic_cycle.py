"""
M14: 经济周期定位（纯函数，自 V1 macro_analysis.economic_cycle 迁入）。

输入为按日降序的宽表行（含 pmi、cpi_yoy、ppi_yoy、m2_yoy、social_financing_yoy、term_spread_10y_1y 等），
由服务层从 DuckDB 宏观表 + 曲线拼接。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any


def _d(v: Any) -> Decimal:
    if v is None:
        return Decimal("0")
    if isinstance(v, Decimal):
        return v
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal("0")


def _f(d: Decimal) -> float:
    return float(d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _monthly_sample(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[int, int]] = set()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = r.get("trade_date") or r.get("biz_date")
        if not d:
            continue
        if hasattr(d, "year"):
            key = (d.year, d.month)
        else:
            continue
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def _momentum(series: list[Decimal], window: int = 3) -> str | None:
    valid = [s for s in series if s is not None]
    if len(valid) < window + 1:
        return None
    recent_avg = sum(valid[:window]) / window
    prev_slice = valid[window : window * 2]
    if not prev_slice:
        return None
    prev_avg = sum(prev_slice) / len(prev_slice)
    if recent_avg > prev_avg:
        return "up"
    if recent_avg < prev_avg:
        return "down"
    return "flat"


def compute_economic_cycle(
    wide_rows_desc: list[dict[str, Any]],
    report_date: date,
) -> dict[str, Any]:
    """
    wide_rows_desc: 按交易日期降序；首条为报告日或最近可用日。
    """
    if not wide_rows_desc:
        return {
            "report_date": report_date.isoformat(),
            "data_status": "unavailable",
            "cycle_phase": "unknown",
            "cycle_phase_cn": "数据不足",
            "growth_score": None,
            "inflation_score": None,
            "growth_momentum": None,
            "inflation_momentum": None,
            "strategy": {},
            "indicators": {},
            "phase_scores": {},
            "history": [],
            "warnings": ["NO_MACRO_ROWS"],
        }

    monthly = _monthly_sample(wide_rows_desc)
    today = wide_rows_desc[0]

    pmi_series = [_d(m.get("pmi")) for m in monthly]
    cpi_series = [_d(m.get("cpi_yoy")) for m in monthly]
    ppi_series = [_d(m.get("ppi_yoy")) for m in monthly]
    m2_series = [_d(m.get("m2_yoy")) for m in monthly]
    sf_series = [_d(m.get("social_financing_yoy")) for m in monthly]

    pmi_val = _d(today.get("pmi"))
    pmi_above_50 = pmi_val > Decimal("50") if pmi_val else False
    growth_mom = _momentum(pmi_series)
    m2_mom = _momentum(m2_series)
    sf_mom = _momentum(sf_series)

    growth_score = Decimal("0")
    if pmi_above_50:
        growth_score += Decimal("30")
    if growth_mom == "up":
        growth_score += Decimal("25")
    elif growth_mom == "flat":
        growth_score += Decimal("10")
    if m2_mom == "up":
        growth_score += Decimal("15")
    if sf_mom == "up":
        growth_score += Decimal("15")

    term_spread = _d(today.get("term_spread_10y_1y"))
    if term_spread > Decimal("50"):
        growth_score += Decimal("15")
    elif term_spread > Decimal("20"):
        growth_score += Decimal("5")

    growth_score = max(Decimal("0"), min(Decimal("100"), growth_score))

    cpi_val = _d(today.get("cpi_yoy"))
    ppi_val = _d(today.get("ppi_yoy"))
    inflation_mom = _momentum(cpi_series)
    ppi_mom = _momentum(ppi_series)

    inflation_score = Decimal("0")
    if cpi_val > Decimal("3"):
        inflation_score += Decimal("40")
    elif cpi_val > Decimal("2"):
        inflation_score += Decimal("25")
    elif cpi_val > Decimal("1"):
        inflation_score += Decimal("10")

    if ppi_val > Decimal("2"):
        inflation_score += Decimal("20")
    elif ppi_val > Decimal("0"):
        inflation_score += Decimal("10")

    if inflation_mom == "up":
        inflation_score += Decimal("20")
    elif inflation_mom == "flat":
        inflation_score += Decimal("5")
    if ppi_mom == "up":
        inflation_score += Decimal("20")

    inflation_score = max(Decimal("0"), min(Decimal("100"), inflation_score))

    g_high = growth_score >= Decimal("50")
    i_high = inflation_score >= Decimal("50")

    if g_high and not i_high:
        cycle_phase = "recovery"
        cycle_phase_cn = "复苏"
    elif g_high and i_high:
        cycle_phase = "expansion"
        cycle_phase_cn = "过热"
    elif not g_high and i_high:
        cycle_phase = "stagflation"
        cycle_phase_cn = "滞胀"
    else:
        cycle_phase = "recession"
        cycle_phase_cn = "衰退"

    strategies = {
        "recovery": {
            "duration_advice": "适度拉长久期至 4-6 年",
            "credit_advice": "逐步增配信用债，利差有收窄空间",
            "sector_advice": "超配利率债和中高等级信用债",
            "risk_note": "经济改善但通胀温和，债市仍有配置价值",
            "recommended_duration": "4-6Y",
        },
        "expansion": {
            "duration_advice": "缩短久期至 2-3 年，防范利率上行风险",
            "credit_advice": "信用利差处于低位，信用性价比下降",
            "sector_advice": "减配长久期利率债，增配浮息债和短融",
            "risk_note": "通胀上行叠加经济过热，利率面临上行压力",
            "recommended_duration": "2-3Y",
        },
        "stagflation": {
            "duration_advice": "缩短久期至 1-2 年，防御为主",
            "credit_advice": "谨慎信用下沉，关注违约风险",
            "sector_advice": "现金类资产、超短融为首选",
            "risk_note": "滞胀环境对债券最为不利，严控久期和信用风险",
            "recommended_duration": "1-2Y",
        },
        "recession": {
            "duration_advice": "大幅拉长久期至 7-10 年，捕捉利率下行",
            "credit_advice": "利差可能走阔，优选高等级信用债",
            "sector_advice": "超配长久期国债和政金债",
            "risk_note": "经济下行+通胀走低，利率债牛市主线",
            "recommended_duration": "7-10Y",
        },
    }
    strategy = strategies.get(cycle_phase, strategies["recession"])

    history: list[dict[str, Any]] = []
    for m in monthly[:6]:
        m_pmi = _d(m.get("pmi"))
        m_cpi = _d(m.get("cpi_yoy"))
        g = m_pmi > Decimal("50")
        i_flag = m_cpi > Decimal("2")
        if g and not i_flag:
            ph = "复苏"
        elif g and i_flag:
            ph = "过热"
        elif not g and i_flag:
            ph = "滞胀"
        else:
            ph = "衰退"
        md = m.get("trade_date") or m.get("biz_date")
        history.append(
            {
                "month": md.strftime("%Y-%m") if hasattr(md, "strftime") else str(md),
                "phase": ph,
                "pmi": _f(m_pmi) if m.get("pmi") is not None else None,
                "cpi": _f(m_cpi) if m.get("cpi_yoy") is not None else None,
            }
        )

    warnings: list[str] = []
    if len(monthly) < 3:
        warnings.append("MACRO_MONTHLY_SAMPLE_SHORT")

    return {
        "report_date": report_date.isoformat(),
        "data_status": "complete" if not warnings else "degraded",
        "cycle_phase": cycle_phase,
        "cycle_phase_cn": cycle_phase_cn,
        "growth_score": _f(growth_score),
        "inflation_score": _f(inflation_score),
        "growth_momentum": growth_mom or "flat",
        "inflation_momentum": inflation_mom or "flat",
        "strategy": strategy,
        "indicators": {
            "pmi": _f(pmi_val) if today.get("pmi") is not None else None,
            "cpi_yoy": _f(cpi_val) if today.get("cpi_yoy") is not None else None,
            "ppi_yoy": _f(ppi_val) if today.get("ppi_yoy") is not None else None,
            "m2_yoy": _f(_d(today.get("m2_yoy"))) if today.get("m2_yoy") is not None else None,
            "social_financing_yoy": _f(_d(today.get("social_financing_yoy")))
            if today.get("social_financing_yoy") is not None
            else None,
            "term_spread_10y_1y": _f(term_spread) if today.get("term_spread_10y_1y") is not None else None,
        },
        "phase_scores": {
            "recovery": _f(max(Decimal("0"), growth_score - inflation_score + Decimal("50"))),
            "expansion": _f(min(growth_score, inflation_score)),
            "stagflation": _f(max(Decimal("0"), inflation_score - growth_score + Decimal("50"))),
            "recession": _f(max(Decimal("0"), Decimal("100") - growth_score - inflation_score + Decimal("50"))),
        },
        "history": history,
        "warnings": warnings,
    }
