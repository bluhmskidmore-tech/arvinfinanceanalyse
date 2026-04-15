"""V1 损益展示用投资类型 A/T/H 推导（与 MOSS-SYSTEM-V1 pnl_service._infer_invest_type 一致）。

非正式风险/久期指标，仅用于 /pnl/data、yield-bench 与 V1 界面口径对齐。
"""

from __future__ import annotations


def infer_invest_type_v1(
    portfolio: str | None,
    asset_type: str | None,
    asset_class: str | None = None,
    *,
    interest_income: float | None = None,
    is_nonstd: bool = False,
) -> str | None:
    """
    推导投资类型（A/T/H）。
    非标：有利息收入 -> H，无（含 0 与负）-> T。标准债：先 asset_type 再 portfolio（与 V1 循环顺序一致），再 asset_class。
    """
    if is_nonstd and interest_income is not None:
        return "H" if interest_income > 0 else "T"
    for v in (asset_type, portfolio):
        if not v:
            continue
        s = str(v).strip().upper()
        if s in ("A", "T", "H"):
            return s
        if s and s[-1] in ("A", "T", "H"):
            return s[-1]
    if asset_class:
        ac = str(asset_class).strip()
        if "可供出售" in ac or "AFS" in ac.upper():
            return "A"
        if "交易" in ac or "Trading" in ac:
            return "T"
        if "持有至到期" in ac or "HTM" in ac.upper():
            return "H"
    return None


def apply_v1_invest_type_to_fi_yield_row(row: dict) -> None:
    """就地更新单行 dict：仅当 source 为 FI 时用 V1 规则覆盖 invest_type / asset_type。"""
    if (row.get("source") or "") != "FI":
        return
    ac = row.get("asset_class")
    dim_asset_type = row.get("asset_type") or row.get("invest_type")
    pl = str(row.get("portfolio_label") or "").strip() or None
    pb = str(row.get("portfolio") or "").strip() or None
    inferred = infer_invest_type_v1(
        pl,
        str(dim_asset_type).strip() if dim_asset_type is not None else None,
        str(ac).strip() if ac is not None and str(ac).strip() else None,
        interest_income=None,
        is_nonstd=False,
    )
    if inferred is None and pb is not None:
        inferred = infer_invest_type_v1(
            pb,
            str(dim_asset_type).strip() if dim_asset_type is not None else None,
            str(ac).strip() if ac is not None and str(ac).strip() else None,
            interest_income=None,
            is_nonstd=False,
        )
    if inferred is not None:
        row["invest_type"] = inferred
        row["asset_type"] = inferred
