"""
M15: 宏观情景 → 组合影响（纯函数，自 V1 macro_analysis.macro_portfolio_impact 迁入）。

组合概况由服务层从 DuckDB 头寸 + 维度表构建；本模块只做久期桶汇总与情景冲击。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any


_M15_SCENARIOS: tuple[dict[str, Any], ...] = (
    {
        "name": "rate_cut",
        "name_cn": "降息宽松",
        "description": "央行降息25bp，经济下行压力加大，曲线牛陡",
        "probability": "30%",
        "curve_shifts_bp": {"1Y": -30, "3Y": -25, "5Y": -20, "7Y": -15, "10Y": -10},
        "credit_spread_shift_bp": -5,
    },
    {
        "name": "economic_recovery",
        "name_cn": "经济复苏",
        "description": "经济数据超预期回暖，宽信用传导顺畅，曲线熊平",
        "probability": "25%",
        "curve_shifts_bp": {"1Y": 5, "3Y": 10, "5Y": 15, "7Y": 20, "10Y": 25},
        "credit_spread_shift_bp": -10,
    },
    {
        "name": "stagflation",
        "name_cn": "类滞胀",
        "description": "通胀上行叠加经济走弱，债市整体承压",
        "probability": "15%",
        "curve_shifts_bp": {"1Y": 20, "3Y": 25, "5Y": 30, "7Y": 30, "10Y": 25},
        "credit_spread_shift_bp": 20,
    },
    {
        "name": "baseline",
        "name_cn": "基准情景",
        "description": "经济温和修复，政策维持中性偏松，利率窄幅震荡",
        "probability": "30%",
        "curve_shifts_bp": {"1Y": -5, "3Y": -3, "5Y": 0, "7Y": 2, "10Y": 5},
        "credit_spread_shift_bp": 0,
    },
)


def _d(v: Any) -> Decimal:
    if v is None:
        return Decimal("0")
    if isinstance(v, Decimal):
        return v
    return Decimal(str(v))


def _estimate_duration_simple(
    maturity_date: date | None,
    report_date: date,
    coupon_rate: Decimal | None,
) -> float:
    if not maturity_date or maturity_date <= report_date:
        return 0.0
    remaining_years = (maturity_date - report_date).days / 365.25
    cr = float(_d(coupon_rate))
    if remaining_years <= 0.5:
        return remaining_years
    if cr <= 0.001:
        return remaining_years
    discount_factor = 1 + cr / 2
    mod_dur = remaining_years * 0.85 / discount_factor
    return max(0.1, min(remaining_years, mod_dur))


def build_bond_portfolio_profile(
    positions: list[dict[str, Any]],
    report_date: date,
) -> dict[str, Any]:
    """
    positions: 每行含 market_value, maturity_date（date 或可转 date）, coupon_rate（可选）。
    仅统计 instrument_type 为 BOND 或未标注类型的正市值债券类（由调用方过滤）。
    """
    if not positions:
        return {"total_mv": 0.0, "buckets": {}, "weighted_duration": 0.0, "bond_count": 0}

    buckets_cfg = [
        ("0-1Y", 0, 1),
        ("1-3Y", 1, 3),
        ("3-5Y", 3, 5),
        ("5-7Y", 5, 7),
        ("7-10Y", 7, 10),
        ("10Y+", 10, 100),
    ]

    total_mv = Decimal("0")
    dur_weighted = Decimal("0")
    bucket_data: dict[str, dict[str, Any]] = {}
    for label, _lo, _hi in buckets_cfg:
        bucket_data[label] = {"mv": Decimal("0"), "dur_weighted_mv": Decimal("0"), "count": 0}

    for p in positions:
        mv = _d(p.get("market_value"))
        if mv == 0:
            continue
        mat_raw = p.get("maturity_date")
        if mat_raw is not None and hasattr(mat_raw, "date"):
            mat = mat_raw.date()
        elif isinstance(mat_raw, date):
            mat = mat_raw
        else:
            mat = None
        cr = p.get("coupon_rate")
        cr_d = _d(cr) if cr is not None else Decimal("0")
        dur = Decimal(str(_estimate_duration_simple(mat, report_date, cr_d)))
        total_mv += mv
        dur_weighted += mv * dur

        remaining = (mat - report_date).days / 365.25 if mat and mat > report_date else 0
        placed = False
        for label, lo, hi in buckets_cfg:
            if lo <= remaining < hi:
                bucket_data[label]["mv"] += mv
                bucket_data[label]["dur_weighted_mv"] += mv * dur
                bucket_data[label]["count"] += 1
                placed = True
                break
        if not placed:
            bucket_data["10Y+"]["mv"] += mv
            bucket_data["10Y+"]["dur_weighted_mv"] += mv * dur
            bucket_data["10Y+"]["count"] += 1

    weighted_dur = float(dur_weighted / total_mv) if total_mv else 0.0

    buckets_out: dict[str, Any] = {}
    for label in bucket_data:
        b = bucket_data[label]
        b_mv = float(b["mv"])
        b_dur = float(b["dur_weighted_mv"] / b["mv"]) if b["mv"] else 0.0
        buckets_out[label] = {
            "market_value": round(b_mv, 2),
            "pct": round(b_mv / float(total_mv) * 100, 2) if total_mv else 0.0,
            "avg_duration": round(b_dur, 2),
            "count": b["count"],
        }

    return {
        "total_mv": round(float(total_mv), 2),
        "weighted_duration": round(weighted_dur, 2),
        "bond_count": len(positions),
        "buckets": buckets_out,
    }


def compute_macro_portfolio_impact(
    portfolio_profile: dict[str, Any],
    current_curve: dict[str, float],
    report_date: date,
    *,
    scenarios: tuple[dict[str, Any], ...] | None = None,
) -> dict[str, Any]:
    """
    current_curve: 百分数收益率，键为 1Y/3Y/5Y/7Y/10Y。
    """
    scenarios_cfg = scenarios if scenarios is not None else _M15_SCENARIOS
    total_mv = portfolio_profile.get("total_mv") or 0
    if total_mv <= 0:
        return {
            "report_date": report_date.isoformat(),
            "data_status": "unavailable",
            "scenarios": [],
            "portfolio": portfolio_profile,
            "current_curve": current_curve,
            "warnings": ["NO_PORTFOLIO"],
        }

    scenarios_out: list[dict[str, Any]] = []
    tenor_to_bucket = {"1Y": "0-1Y", "3Y": "1-3Y", "5Y": "3-5Y", "7Y": "5-7Y", "10Y": "7-10Y"}
    profile_buckets = portfolio_profile.get("buckets") or {}

    for sc in scenarios_cfg:
        curve_shifts = sc["curve_shifts_bp"]
        credit_shift_bp = sc.get("credit_spread_shift_bp", 0)

        new_curve: dict[str, float] = {}
        for tenor, shift in curve_shifts.items():
            base = float(current_curve.get(tenor, 2.5))
            new_curve[tenor] = round(base + shift / 100.0, 4)

        total_delta = 0.0
        bucket_impacts: dict[str, Any] = {}

        for tenor, shift_bp in curve_shifts.items():
            bucket_label = tenor_to_bucket.get(tenor)
            if not bucket_label or bucket_label not in profile_buckets:
                continue
            b = profile_buckets[bucket_label]
            b_mv = b["market_value"]
            b_dur = b["avg_duration"]
            combined_shift = shift_bp + credit_shift_bp
            delta = -b_mv * b_dur * combined_shift / 10000.0
            total_delta += delta
            bucket_impacts[bucket_label] = {
                "delta_mv": round(delta, 2),
                "rate_shift_bp": shift_bp,
                "credit_shift_bp": credit_shift_bp,
            }

        remaining_mv = sum(
            profile_buckets[bl]["market_value"] for bl in profile_buckets if bl not in bucket_impacts
        )
        if remaining_mv > 0:
            avg_shift = sum(curve_shifts.values()) / len(curve_shifts) if curve_shifts else 0
            remaining_dur = portfolio_profile.get("weighted_duration") or 0.0
            delta_remaining = -remaining_mv * remaining_dur * (avg_shift + credit_shift_bp) / 10000.0
            total_delta += delta_remaining
            bucket_impacts["other"] = {"delta_mv": round(delta_remaining, 2)}

        pnl_pct = round(total_delta / total_mv * 100, 2) if total_mv else 0.0

        scenarios_out.append(
            {
                "name": sc["name"],
                "name_cn": sc["name_cn"],
                "description": sc["description"],
                "probability": sc.get("probability", "—"),
                "curve_shifts_bp": curve_shifts,
                "credit_spread_shift_bp": credit_shift_bp,
                "new_curve": new_curve,
                "total_pnl": round(total_delta, 2),
                "pnl_pct": pnl_pct,
                "bucket_impacts": bucket_impacts,
                "risk_level": "HIGH" if abs(pnl_pct) > 2 else ("MEDIUM" if abs(pnl_pct) > 0.5 else "LOW"),
            }
        )

    return {
        "report_date": report_date.isoformat(),
        "data_status": "complete",
        "current_curve": current_curve,
        "scenarios": scenarios_out,
        "portfolio": portfolio_profile,
        "warnings": [],
    }
