"""
M13: 跨市场联动（纯函数，自 V1 macro_analysis.cross_market_linkage 迁入）。

输入为按日期降序对齐的宽表行，需含 treasury_10y；可选 vix、brent_oil、us_treasury_10y、usdcny（或 fx_usdcny）。
缺失序列时相应相关系数为 None，整体 data_status 可能为 degraded。
"""

from __future__ import annotations

import math
from datetime import date
from typing import Any

from app.core_finance.macro.helpers import to_float_safe as _d, pearson_corr as _pearson_corr


def _align(bond: list[float | None], other: list[float | None]) -> tuple[list[float], list[float]]:
    x, y = [], []
    for a, b in zip(bond, other):
        if a is not None and b is not None:
            x.append(a)
            y.append(b)
    return x, y


_M13_VIX_LEVELS = {
    "panic": 30,
    "elevated": 20,
    "normal": 15,
}


def analyze_cross_market_linkage(
    wide_rows_desc: list[dict[str, Any]],
    report_date: date,
) -> dict[str, Any]:
    if not wide_rows_desc:
        return {
            "report_date": report_date.isoformat(),
            "data_status": "unavailable",
            "linkages": {},
            "overall_risk": "LOW",
            "recommendation": "无足够市场数据",
            "warnings": ["NO_ROWS"],
        }

    bond_10y = [_d(r.get("treasury_10y")) for r in wide_rows_desc]
    if not any(v is not None for v in bond_10y):
        return {
            "report_date": report_date.isoformat(),
            "data_status": "unavailable",
            "linkages": {},
            "overall_risk": "LOW",
            "recommendation": "缺少国债收益率序列",
            "warnings": ["TREASURY_10Y_MISSING"],
        }

    vix_list = [_d(r.get("vix")) for r in wide_rows_desc]
    oil_list = [_d(r.get("brent_oil")) for r in wide_rows_desc]
    us10y_list = [_d(r.get("us_treasury_10y")) for r in wide_rows_desc]
    fx_list = [_d(r.get("usdcny") or r.get("fx_usdcny")) for r in wide_rows_desc]

    x_be, y_vix = _align(bond_10y, vix_list)
    x_bf, y_fx = _align(bond_10y, fx_list)
    x_bc, y_oil = _align(bond_10y, oil_list)
    x_bu, y_us = _align(bond_10y, us10y_list)

    bond_equity_corr = _pearson_corr(x_be, y_vix) if x_be else None
    bond_fx_corr = _pearson_corr(x_bf, y_fx) if x_bf else None
    bond_commodity_corr = _pearson_corr(x_bc, y_oil) if x_bc else None
    bond_us_corr = _pearson_corr(x_bu, y_us) if x_bu else None

    vix_today = _d(wide_rows_desc[0].get("vix"))
    vix_levels = _M13_VIX_LEVELS
    if vix_today is not None:
        if vix_today >= vix_levels["panic"]:
            vix_level = "恐慌"
        elif vix_today >= vix_levels["elevated"]:
            vix_level = "抬升"
        else:
            vix_level = "正常"
    else:
        vix_level = "未知"

    fx_today = _d(wide_rows_desc[0].get("usdcny") or wide_rows_desc[0].get("fx_usdcny"))
    if fx_today is not None and len(fx_list) >= 5:
        head = [f for f in fx_list[:5] if f is not None]
        if head:
            fx_ma = sum(head) / len(head)
            fx_trend = "贬值" if fx_today > fx_ma else "升值"
        else:
            fx_trend = "中性"
    else:
        fx_trend = "中性"

    oil_today = _d(wide_rows_desc[0].get("brent_oil"))
    oil_ma = None
    valid_oil = [o for o in oil_list if o is not None][:20]
    if valid_oil:
        oil_ma = sum(valid_oil) / len(valid_oil)
    if oil_today is not None and oil_ma is not None:
        oil_level = "偏高" if oil_today > oil_ma * 1.05 else ("偏低" if oil_today < oil_ma * 0.95 else "正常")
    else:
        oil_level = "正常"

    y10 = _d(wide_rows_desc[0].get("treasury_10y"))
    us10 = _d(wide_rows_desc[0].get("us_treasury_10y"))
    cn_us_spread = None
    if y10 is not None and us10 is not None:
        cn_us_spread = round((y10 - us10) * 100, 2)

    linkages = {
        "bond_equity": {
            "correlation": round(bond_equity_corr, 4) if bond_equity_corr is not None else None,
            "vix_level": vix_level,
        },
        "bond_fx": {
            "correlation": round(bond_fx_corr, 4) if bond_fx_corr is not None else None,
            "fx_trend": fx_trend,
        },
        "bond_commodity": {
            "correlation": round(bond_commodity_corr, 4) if bond_commodity_corr is not None else None,
            "oil_level": oil_level,
        },
        "bond_us": {
            "correlation": round(bond_us_corr, 4) if bond_us_corr is not None else None,
            "cn_us_spread": cn_us_spread,
        },
    }

    corrs = [c for c in [bond_equity_corr, bond_fx_corr, bond_commodity_corr, bond_us_corr] if c is not None]
    high_corr_count = sum(1 for c in corrs if abs(c) > 0.6)
    if high_corr_count >= 3 or vix_level == "恐慌":
        overall_risk = "HIGH"
        recommendation = "降低风险资产敞口，增配利率债与高流动性资产"
    elif high_corr_count >= 1 or vix_level == "抬升":
        overall_risk = "MEDIUM"
        recommendation = "关注跨市场传导，适度防御"
    else:
        overall_risk = "LOW"
        recommendation = "跨市场联动处于常态"

    warnings: list[str] = []
    if bond_equity_corr is None:
        warnings.append("BOND_EQUITY_CORR_UNAVAILABLE")
    if bond_fx_corr is None:
        warnings.append("BOND_FX_CORR_UNAVAILABLE")
    if bond_commodity_corr is None:
        warnings.append("BOND_COMMODITY_CORR_UNAVAILABLE")
    if bond_us_corr is None:
        warnings.append("BOND_US_CORR_UNAVAILABLE")

    if len(corrs) == 0:
        data_status = "degraded"
    elif len(warnings) >= 3:
        data_status = "degraded"
    else:
        data_status = "complete"

    return {
        "report_date": report_date.isoformat(),
        "data_status": data_status,
        "linkages": linkages,
        "overall_risk": overall_risk,
        "recommendation": recommendation,
        "bond_equity_corr": round(bond_equity_corr, 4) if bond_equity_corr is not None else None,
        "bond_fx_corr": round(bond_fx_corr, 4) if bond_fx_corr is not None else None,
        "bond_commodity_corr": round(bond_commodity_corr, 4) if bond_commodity_corr is not None else None,
        "bond_us_corr": round(bond_us_corr, 4) if bond_us_corr is not None else None,
        "warnings": warnings,
    }
