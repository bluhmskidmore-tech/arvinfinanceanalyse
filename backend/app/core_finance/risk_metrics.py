"""
风险集中度与压力情景（纯函数，自 V1 risk_analysis_service 口径迁入）。
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

ZERO = Decimal("0")
_TEN_THOUSAND = Decimal("10000")
_HUNDRED = Decimal("100")
_TEN = Decimal("10")
_TWENTY = Decimal("20")


def calc_hhi(
    positions: list[dict[str, Any]],
    *,
    group_by: Literal["issuer", "instrument"] = "issuer",
    weight_key: str = "market_value",
    group_key_issuer: str = "issuer_id",
    group_key_instrument: str = "instrument_id",
) -> Decimal:
    """HHI = Σ share² × 10000，share 为市值占比（绝对值归一）。"""
    key = group_key_issuer if group_by == "issuer" else group_key_instrument
    totals: dict[str, Decimal] = {}
    for p in positions:
        g = str(p.get(key) or p.get("instrument_id") or "UNKNOWN")
        w = abs(Decimal(str(p.get(weight_key) or 0)))
        totals[g] = totals.get(g, ZERO) + w
    total = sum(totals.values())
    if total <= ZERO:
        return ZERO
    return sum((v / total) ** 2 for v in totals.values()) * _TEN_THOUSAND


def credit_concentration_check(
    hhi: Decimal,
    top_issuer_pct: Decimal | None,
    top_industry_pct: Decimal | None,
) -> dict[str, Any]:
    """阈值与 V1 迁移说明一致。"""
    level = "OK"
    if hhi > Decimal("2500"):
        level = "CRITICAL"
    elif hhi > Decimal("1800"):
        level = "WARNING"
    elif hhi > Decimal("1000"):
        level = "MEDIUM"

    alerts: list[str] = []
    if top_issuer_pct is not None and top_issuer_pct > _TEN:
        alerts.append("issuer_concentration_gt_10pct")
        if level == "OK":
            level = "MEDIUM"
    if top_industry_pct is not None and top_industry_pct > _TWENTY:
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
) -> Decimal:
    """市值加权 YTM；ytm 为小数（0.0255=2.55%）。"""
    num = ZERO
    den = ZERO
    for p in positions:
        mv = abs(Decimal(str(p.get(mv_key) or 0)))
        ytm = p.get(ytm_key)
        if ytm is None:
            continue
        y = Decimal(str(ytm))
        num += mv * y
        den += mv
    return num / den if den > ZERO else ZERO


def stress_test_pnl(dv01: Decimal | float, scenarios_bp: list[int]) -> list[dict[str, Any]]:
    """PnL ≈ -DV01 × shock_bp（与迁移说明一致）。"""
    d = Decimal(str(dv01))
    out = []
    for bp in scenarios_bp:
        out.append({"shock_bp": bp, "pnl": -d * Decimal(str(bp))})
    return out
