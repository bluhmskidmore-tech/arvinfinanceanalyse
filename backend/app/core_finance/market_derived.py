"""
市场数据派生指标（纯函数）。

利差公式与 V1 `market_data_daily_service._calculate_spreads` 锁定一致：百分数差 × 100 → BP。
信用利差默认值与 V1 `credit_spread_data_service._get_default_spread` 一致。
FTP 线性插值与 V1 `ftp_curve_service.get_ftp_rate` 一致（输入为已解析的曲线点）。
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any


def _pct_diff_bp(a: Any, b: Any) -> float | None:
    if a is None or b is None:
        return None
    try:
        return (float(a) - float(b)) * 100.0
    except (TypeError, ValueError):
        return None


def calculate_spreads(market_data: dict[str, Any]) -> dict[str, float | None]:
    """
    由市场收益率（百分数，如 2.55 表示 2.55%）计算各类利差，输出单位 BP。
    字段缺失时对应输出为 None。
    """
    d = market_data
    return {
        "ncd_treasury_spread_1y": _pct_diff_bp(d.get("ncd_aaa_1y"), d.get("treasury_1y")),
        "term_spread_10y_1y": _pct_diff_bp(d.get("treasury_10y"), d.get("treasury_1y")),
        "term_spread_10y_5y": _pct_diff_bp(d.get("treasury_10y"), d.get("treasury_5y")),
        "credit_spread_aaa_3y": _pct_diff_bp(d.get("credit_aaa_3y"), d.get("treasury_3y")),
        "cdb_treasury_spread_5y": _pct_diff_bp(d.get("cdb_5y"), d.get("treasury_5y")),
        "r007_dr007_spread": _pct_diff_bp(d.get("r007"), d.get("dr007")),
        "credit_spread_aa_plus_3y": _pct_diff_bp(d.get("credit_aa_plus_3y"), d.get("treasury_3y")),
        "credit_spread_aa_3y": _pct_diff_bp(d.get("credit_aa_3y"), d.get("treasury_3y")),
        "aa_aaa_spread_3y": _pct_diff_bp(d.get("credit_aa_3y"), d.get("credit_aaa_3y")),
        "china_us_spread_10y": _pct_diff_bp(d.get("treasury_10y"), d.get("us_treasury_10y")),
        "cdb_treasury_spread_10y": _pct_diff_bp(d.get("cdb_10y"), d.get("treasury_10y")),
    }


# 默认信用利差表，单位 BP（与 V1 credit_spread_data_service 一致）
DEFAULT_CREDIT_SPREADS: dict[tuple[str, str], Decimal] = {
    ("AAA", "1Y"): Decimal("25"),
    ("AAA", "3Y"): Decimal("35"),
    ("AAA", "5Y"): Decimal("45"),
    ("AA+", "1Y"): Decimal("45"),
    ("AA+", "3Y"): Decimal("60"),
    ("AA+", "5Y"): Decimal("75"),
    ("AA", "1Y"): Decimal("70"),
    ("AA", "3Y"): Decimal("90"),
    ("AA", "5Y"): Decimal("110"),
}


def _normalize_rating(rating: str) -> str:
    r = str(rating or "").strip().upper().replace(" ", "")
    if r in ("AA+", "AA-", "A+", "A-", "BBB+", "BBB-", "BB+", "BB-"):
        return r
    if len(r) >= 2 and r.startswith("AA") and r[2:3] in "+-":
        return r[:2] + r[2:3]
    return r


def _tenor_label_for_curve(years: float) -> str:
    """将剩余年数映射到曲线键 1Y / 3Y / 5Y（用于默认表与常见曲线）。"""
    if years <= 2.0:
        return "1Y"
    if years <= 4.0:
        return "3Y"
    return "5Y"


def _curve_bp_to_decimal(spread_bp: Any) -> Decimal:
    return Decimal(str(spread_bp)) / Decimal("10000")


def get_credit_spread(rating: str, tenor_years: float, curve: dict[str, Any] | None) -> Decimal:
    """
    信用利差（小数，= BP/10000）。

    优先级：curve 中该评级期限 → 曲线期限回退 3Y/5Y/1Y → DEFAULT_CREDIT_SPREADS → 0.008（80bp）。
    curve 的值为 BP（与 Wind / V1 缓存一致）。
    """
    r = _normalize_rating(rating)
    tenor_key = _tenor_label_for_curve(float(tenor_years))

    if curve:
        if tenor_key in curve and curve[tenor_key] is not None:
            return _curve_bp_to_decimal(curve[tenor_key])
        for fb in ("3Y", "5Y", "1Y"):
            if fb in curve and curve[fb] is not None:
                v = curve[fb]
                try:
                    if float(v) > 0:
                        return _curve_bp_to_decimal(v)
                except (TypeError, ValueError):
                    return _curve_bp_to_decimal(v)

    default_bp = DEFAULT_CREDIT_SPREADS.get((r, tenor_key))
    if default_bp is not None:
        return default_bp / Decimal("10000")

    for fb in ("3Y", "5Y", "1Y"):
        bp = DEFAULT_CREDIT_SPREADS.get((r, fb))
        if bp is not None:
            return bp / Decimal("10000")

    return Decimal("0.008")


def interpolate_ftp_rate(term_months: float, curve_points: list[tuple[float, float]]) -> float:
    """
    按期限（月）对 FTP 年化利率做线性插值。curve_points: [(months, rate), ...]，rate 为小数。
    点集按月份排序；单点则返回该点利率；空集返回 0.0。
    """
    if not curve_points:
        return 0.0
    pts = sorted(curve_points, key=lambda x: x[0])
    t = float(term_months)
    if t <= 0:
        return float(pts[0][1])

    tenors = [p[0] for p in pts]
    rates = [float(p[1]) for p in pts]

    if t <= tenors[0]:
        return rates[0]
    if t >= tenors[-1]:
        return rates[-1]

    for i in range(len(tenors) - 1):
        t0, t1 = tenors[i], tenors[i + 1]
        if t0 <= t <= t1:
            r0, r1 = rates[i], rates[i + 1]
            if t1 == t0:
                return r0
            w = (t - t0) / (t1 - t0)
            return r0 + (r1 - r0) * w

    return rates[-1]
