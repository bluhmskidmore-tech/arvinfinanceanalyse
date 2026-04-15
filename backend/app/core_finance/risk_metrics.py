"""
风险集中度与压力情景（纯函数，自 V1 risk_analysis_service 口径迁入）。
"""

from __future__ import annotations

from typing import Any, Literal


def calc_hhi(
    positions: list[dict[str, Any]],
    *,
    group_by: Literal["issuer", "instrument"] = "issuer",
    weight_key: str = "market_value",
    group_key_issuer: str = "issuer_id",
    group_key_instrument: str = "instrument_id",
) -> float:
    """HHI = Σ share² × 10000，share 为市值占比（绝对值归一）。"""
    key = group_key_issuer if group_by == "issuer" else group_key_instrument
    totals: dict[str, float] = {}
    for p in positions:
        g = str(p.get(key) or p.get("instrument_id") or "UNKNOWN")
        w = abs(float(p.get(weight_key) or 0))
        totals[g] = totals.get(g, 0.0) + w
    total = sum(totals.values())
    if total <= 0:
        return 0.0
    return sum((v / total) ** 2 for v in totals.values()) * 10000.0


def credit_concentration_check(
    hhi: float,
    top_issuer_pct: float | None,
    top_industry_pct: float | None,
) -> dict[str, Any]:
    """阈值与 V1 迁移说明一致。"""
    level = "OK"
    if hhi > 2500:
        level = "CRITICAL"
    elif hhi > 1800:
        level = "WARNING"
    elif hhi > 1000:
        level = "MEDIUM"

    alerts: list[str] = []
    if top_issuer_pct is not None and top_issuer_pct > 10.0:
        alerts.append("issuer_concentration_gt_10pct")
        if level == "OK":
            level = "MEDIUM"
    if top_industry_pct is not None and top_industry_pct > 20.0:
        alerts.append("industry_concentration_gt_20pct")
        if level in ("OK", "MEDIUM"):
            level = "WARNING"

    return {
        "hhi": hhi,
        "level": level,
        "alerts": alerts,
        "top_issuer_pct": top_issuer_pct,
        "top_industry_pct": top_industry_pct,
    }


def weighted_avg_ytm(
    positions: list[dict[str, Any]],
    *,
    mv_key: str = "market_value",
    ytm_key: str = "yield_to_maturity",
) -> float:
    """市值加权 YTM；ytm 为小数（0.0255=2.55%）。"""
    num = 0.0
    den = 0.0
    for p in positions:
        mv = abs(float(p.get(mv_key) or 0))
        ytm = p.get(ytm_key)
        if ytm is None:
            continue
        y = float(ytm)
        num += mv * y
        den += mv
    return num / den if den > 0 else 0.0


def stress_test_pnl(dv01: float, scenarios_bp: list[int]) -> list[dict[str, Any]]:
    """PnL ≈ -DV01 × shock_bp（与迁移说明一致）。"""
    out = []
    for bp in scenarios_bp:
        out.append({"shock_bp": bp, "pnl": -float(dv01) * float(bp)})
    return out
