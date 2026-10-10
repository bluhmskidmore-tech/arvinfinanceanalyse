"""
M14: 经济周期定位（纯函数，自 V1 macro_analysis.economic_cycle 迁入）。

输入为按日降序的宽表行（含 pmi、cpi_yoy、ppi_yoy、m2_yoy、social_financing_yoy、term_spread_10y_1y 等），
由服务层从 DuckDB 宏观表 + 曲线拼接。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from backend.app.core_finance.macro.helpers import to_decimal_safe as _d
from backend.app.core_finance.macro.helpers import to_rounded_float as _f


def _optional_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    return _d(value)


# fail-closed 最小输入门槛（审计 H-1）：核心输入（PMI/CPI）在报告日不可得、
# 或月度样本不足时，不产出象限与久期建议，对齐 merrill_clock 的 fail-closed。
# 下限取 4：动量窗口（近 _MOMENTUM_WINDOW 个日历月 vs 前一窗口至少 1 个月）
# 至少需要 4 个月度样本；恰好 3 个月时动量全部不可算，只能退化为 0 分并把
# 结果伪装成 complete（H-1 残余缺口）。
_MIN_MONTHLY_SAMPLE = 4

_MOMENTUM_WINDOW = 3


def _missing_input_warnings(
    monthly: list[dict[str, Any]],
    today: dict[str, Any],
) -> list[str]:
    warnings: list[str] = []
    missing_checks = (
        ("pmi", "PMI_MISSING"),
        ("cpi_yoy", "CPI_YOY_MISSING"),
        ("ppi_yoy", "PPI_YOY_MISSING"),
        ("m2_yoy", "M2_YOY_MISSING"),
        ("social_financing_yoy", "SOCIAL_FINANCING_YOY_MISSING"),
    )
    for field, warning_code in missing_checks:
        if any(row.get(field) is None for row in monthly):
            warnings.append(warning_code)
    if today.get("term_spread_10y_1y") is None:
        warnings.append("TERM_SPREAD_10Y_1Y_MISSING")
    if len(monthly) < _MIN_MONTHLY_SAMPLE:
        warnings.append("MACRO_MONTHLY_SAMPLE_SHORT")
    return warnings


def _unknown_payload(
    report_date: date,
    warnings: list[str],
    *,
    indicators: dict[str, Any] | None = None,
) -> dict[str, Any]:
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
        "indicators": indicators or {},
        "phase_scores": {},
        "history": [],
        "warnings": warnings,
    }


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


def _month_ordinal(row: dict[str, Any]) -> int:
    d = row.get("trade_date") or row.get("biz_date")
    return d.year * 12 + d.month


def _slot_aligned_series(
    monthly: list[dict[str, Any]],
    field: str,
    depth: int = _MOMENTUM_WINDOW * 2,
) -> list[Decimal | None]:
    """按日历月槽位对齐的取值序列（审计 M-1）。

    槽位 i 对应最近月度样本往前第 i 个日历月；缺月或缺值的槽位保持 None，
    不得用更早月份跨槽拼接，避免动量比较窗口跨度不对称。
    """
    slots: list[Decimal | None] = [None] * depth
    if not monthly:
        return slots
    anchor = _month_ordinal(monthly[0])
    for row in monthly:
        offset = anchor - _month_ordinal(row)
        if 0 <= offset < depth:
            slots[offset] = _optional_decimal(row.get(field))
    return slots


def _momentum(series: list[Decimal | None], window: int = _MOMENTUM_WINDOW) -> str | None:
    """槽位对齐动量：近 window 个日历月均值 vs 前一 window 个日历月窗口均值。

    series 必须是 _slot_aligned_series 产出的槽位序列。近窗要求槽位齐全
    （缺月/缺值不得混入更早月份）；对照窗仅在其日历槽位内取可用值（至少
    1 个）。数据不足返回 None，由调用方按"动量不可计算"降级处理。
    """
    recent_values = [s for s in series[:window] if s is not None]
    if len(recent_values) < window:
        return None
    prev_values = [s for s in series[window : window * 2] if s is not None]
    if not prev_values:
        return None
    recent_avg = sum(recent_values) / window
    prev_avg = sum(prev_values) / len(prev_values)
    if recent_avg > prev_avg:
        return "up"
    if recent_avg < prev_avg:
        return "down"
    return "flat"


def _bounded_score(value: Decimal) -> Decimal:
    return max(Decimal("0"), min(Decimal("100"), value))


def compute_economic_cycle(
    wide_rows_desc: list[dict[str, Any]],
    report_date: date,
) -> dict[str, Any]:
    """
    wide_rows_desc: 按交易日期降序；首条为报告日或最近可用日。
    """
    if not wide_rows_desc:
        return _unknown_payload(report_date, ["NO_MACRO_ROWS"])

    monthly = _monthly_sample(wide_rows_desc)
    today = wide_rows_desc[0]

    pmi_series = _slot_aligned_series(monthly, "pmi")
    cpi_series = _slot_aligned_series(monthly, "cpi_yoy")
    ppi_series = _slot_aligned_series(monthly, "ppi_yoy")
    m2_series = _slot_aligned_series(monthly, "m2_yoy")
    sf_series = _slot_aligned_series(monthly, "social_financing_yoy")

    pmi_val = _optional_decimal(today.get("pmi"))
    cpi_today = _optional_decimal(today.get("cpi_yoy"))

    # fail-closed 门槛：缺失分项在评分中等价于 0 分并会把结果推向"衰退 +
    # 大幅拉长久期"，因此核心输入（PMI/CPI）报告日不可得或月度样本不足时，
    # 直接返回 unknown 且不给策略建议，而不是带 degraded 输出激进方向。
    gate_reasons: list[str] = []
    if pmi_val is None:
        gate_reasons.append("PMI_CORE_INPUT_MISSING")
    if cpi_today is None:
        gate_reasons.append("CPI_YOY_CORE_INPUT_MISSING")
    if len(monthly) < _MIN_MONTHLY_SAMPLE:
        gate_reasons.append("MACRO_MONTHLY_SAMPLE_SHORT")
    if gate_reasons:
        observed = {
            "pmi": _f(pmi_val) if pmi_val is not None else None,
            "cpi_yoy": _f(cpi_today) if cpi_today is not None else None,
        }
        term_observed = _optional_decimal(today.get("term_spread_10y_1y"))
        if term_observed is not None:
            observed["term_spread_10y_1y"] = _f(term_observed)
        gate_warnings = list(
            dict.fromkeys(
                [
                    *gate_reasons,
                    *_missing_input_warnings(monthly, today),
                ]
            )
        )
        return _unknown_payload(report_date, gate_warnings, indicators=observed)

    pmi_above_50 = pmi_val is not None and pmi_val > Decimal("50")
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

    term_spread = _optional_decimal(today.get("term_spread_10y_1y"))
    if term_spread is not None:
        if term_spread > Decimal("50"):
            growth_score += Decimal("15")
        elif term_spread > Decimal("20"):
            growth_score += Decimal("5")

    growth_score = max(Decimal("0"), min(Decimal("100"), growth_score))

    cpi_val = _optional_decimal(today.get("cpi_yoy"))
    ppi_val = _optional_decimal(today.get("ppi_yoy"))
    inflation_mom = _momentum(cpi_series)
    ppi_mom = _momentum(ppi_series)

    inflation_score = Decimal("0")
    if cpi_val is not None:
        if cpi_val > Decimal("3"):
            inflation_score += Decimal("40")
        elif cpi_val > Decimal("2"):
            inflation_score += Decimal("25")
        elif cpi_val > Decimal("1"):
            inflation_score += Decimal("10")

    if ppi_val is not None:
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
        # 标识符使用 overheat：与 gate_macro_overlay 的 expansion（宏观向好、
        # 不设仓位上限）同名反义，避免下游按字面 expansion 混接（审计 M-2）。
        cycle_phase = "overheat"
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
        "overheat": {
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
        m_pmi = _optional_decimal(m.get("pmi"))
        m_cpi = _optional_decimal(m.get("cpi_yoy"))
        g = m_pmi is not None and m_pmi > Decimal("50")
        i_flag = m_cpi is not None and m_cpi > Decimal("2")
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

    # 动量不可计算（缺月/缺值导致窗口不完整）时该分项计 0 分，属于降级
    # 而非完整结果：追加专属 warning 使 data_status=degraded，且输出层不得
    # 把 None 伪装成 "flat"（审计 H-1 残余缺口）。
    momentum_checks = (
        (growth_mom, "PMI_MOMENTUM_UNAVAILABLE"),
        (m2_mom, "M2_YOY_MOMENTUM_UNAVAILABLE"),
        (sf_mom, "SOCIAL_FINANCING_YOY_MOMENTUM_UNAVAILABLE"),
        (inflation_mom, "CPI_YOY_MOMENTUM_UNAVAILABLE"),
        (ppi_mom, "PPI_YOY_MOMENTUM_UNAVAILABLE"),
    )
    momentum_warnings = [code for mom, code in momentum_checks if mom is None]
    warnings = _missing_input_warnings(monthly, today) + momentum_warnings
    m2_val = _optional_decimal(today.get("m2_yoy"))
    sf_val = _optional_decimal(today.get("social_financing_yoy"))

    return {
        "report_date": report_date.isoformat(),
        "data_status": "complete" if not warnings else "degraded",
        "cycle_phase": cycle_phase,
        "cycle_phase_cn": cycle_phase_cn,
        "growth_score": _f(growth_score),
        "inflation_score": _f(inflation_score),
        "growth_momentum": growth_mom,
        "inflation_momentum": inflation_mom,
        "strategy": strategy,
        "indicators": {
            "pmi": _f(pmi_val) if pmi_val is not None else None,
            "cpi_yoy": _f(cpi_val) if cpi_val is not None else None,
            "ppi_yoy": _f(ppi_val) if ppi_val is not None else None,
            "m2_yoy": _f(m2_val) if m2_val is not None else None,
            "social_financing_yoy": _f(sf_val) if sf_val is not None else None,
            "term_spread_10y_1y": _f(term_spread) if term_spread is not None else None,
        },
        "phase_scores": {
            # 表观量纲统一为 [0,100]：上限 clip 防止不对称样本（如 growth=100、
            # inflation=0 时 recovery 原式=150）溢出（审计 M-4，纯载荷卫生）。
            "recovery": _f(_bounded_score(growth_score - inflation_score + Decimal("50"))),
            "overheat": _f(_bounded_score(min(growth_score, inflation_score))),
            "stagflation": _f(_bounded_score(inflation_score - growth_score + Decimal("50"))),
            "recession": _f(_bounded_score(Decimal("100") - growth_score - inflation_score + Decimal("50"))),
        },
        "history": history,
        "warnings": warnings,
    }
