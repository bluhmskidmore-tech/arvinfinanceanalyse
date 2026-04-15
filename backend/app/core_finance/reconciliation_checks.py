"""
对账补充检查（纯函数，自 MOSS-V2 core_finance 迁入）：头寸 vs 总账、损益 vs 总账、完整性。
"""

from __future__ import annotations

from typing import Any


def position_vs_ledger_diff(
    position_totals: dict[str, float],
    ledger_totals: dict[str, float],
    *,
    threshold_yuan: float = 1.0,
) -> list[dict[str, Any]]:
    """
    比对维度：total_assets, total_liabilities, net_assets（键名可缺省按 0）
    """
    dims = ("total_assets", "total_liabilities", "net_assets")
    rows = []
    for d in dims:
        pv = float(position_totals.get(d) or 0)
        lv = float(ledger_totals.get(d) or 0)
        diff = pv - lv
        rows.append(
            {
                "dimension": d,
                "position_value": pv,
                "ledger_value": lv,
                "diff": diff,
                "breached": abs(diff) >= threshold_yuan,
            }
        )
    return rows


def pnl_vs_ledger_diff(
    pnl_total: float,
    ledger_pnl_total: float,
    *,
    threshold_yuan: float = 1.0,
) -> dict[str, Any]:
    diff = float(pnl_total) - float(ledger_pnl_total)
    return {
        "pnl_total": float(pnl_total),
        "ledger_pnl_total": float(ledger_pnl_total),
        "diff": diff,
        "breached": abs(diff) >= threshold_yuan,
    }


def completeness_check(
    product_category_total: float,
    pnl_total: float,
    *,
    threshold_yuan: float = 1.0,
) -> dict[str, Any]:
    diff = float(product_category_total) - float(pnl_total)
    return {
        "product_category_total": float(product_category_total),
        "pnl_total": float(pnl_total),
        "diff": diff,
        "breached": abs(diff) >= threshold_yuan,
    }
