"""V1 损益展示用投资类型 A/T/H 推导（与 MOSS-SYSTEM-V1 pnl_service._infer_invest_type 对齐）。

非正式风险/久期指标，仅用于 /pnl/data、yield-bench 与 V1 界面口径对齐。

W-migrate-hat-2026-04-21
------------------------
本模块原内嵌一份 H/A/T 推导逻辑，与 ``classification_rules.infer_invest_type``
属于同一规则的并行实现（caliber rule ``hat_mapping``，canonical
``backend.app.core_finance.config.classification_rules.infer_invest_type``）。
此次试迁把 ``infer_invest_type_v1`` 改为 canonical 的薄包装：

* 保留模块名 / 函数签名以兼容现有调用方（外部仍按 V1 名字 import）。
* 行为差异修正：原 v1 对 ``"Trading"`` 大小写敏感（漏匹配 ``"TRADING"``、
  ``"trading"``）；canonical 对 ``"TRADING"`` 不区分大小写。caliber 统一选择
  采用 canonical 行为（同一输入跨页面给出同一答案）。
* 入参 ``interest_income`` 类型从 ``float`` 转为 ``Decimal`` 适配 canonical。
"""

from __future__ import annotations

from decimal import Decimal

from backend.app.core_finance.config.classification_rules import infer_invest_type


def infer_invest_type_v1(
    portfolio: str | None,
    asset_type: str | None,
    asset_class: str | None = None,
    *,
    interest_income: float | None = None,
    is_nonstd: bool = False,
) -> str | None:
    """推导投资类型（A/T/H）。

    薄包装：直接 delegate 到 ``classification_rules.infer_invest_type``。
    保留 V1 风格的签名（``interest_income: float | None``）以兼容现有调用方；
    内部转 ``Decimal`` 调 canonical。
    """
    interest_income_decimal: Decimal | None = (
        Decimal(str(interest_income)) if interest_income is not None else None
    )
    return infer_invest_type(
        portfolio,
        asset_type,
        asset_class,
        interest_income=interest_income_decimal,
        is_nonstd=is_nonstd,
    )


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
