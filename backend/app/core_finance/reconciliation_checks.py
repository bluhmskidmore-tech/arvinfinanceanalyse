"""
对账补充检查（纯函数，自 MOSS-V2 core_finance 迁入）：头寸 vs 总账、损益 vs 总账、完整性。

2026-07-19 审计 余额 M-4：
- 比较与差额计算改为 Decimal 口径（输入可为 Decimal / int / float / str）；
  输出展示值保持 float 以兼容既有 payload 序列化。
- 缺键 / None / 非有限值不再按 0 参与比较（避免双缺键 0 vs 0 假平），
  而是显式标记为 missing：该维度 breached=True，并在行内透出 missing_keys。
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Mapping


def _comparison_decimal(value: object) -> Decimal | None:
    """转换为参与对账比较的 Decimal；缺失/无法解析/NaN/Inf 返回 None（missing）。"""
    if value is None:
        return None
    if isinstance(value, Decimal):
        result = value
    else:
        try:
            result = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return None
    return result if result.is_finite() else None


def position_vs_ledger_diff(
    position_totals: Mapping[str, object],
    ledger_totals: Mapping[str, object],
    *,
    threshold_yuan: float | Decimal = 1.0,
) -> list[dict[str, Any]]:
    """
    比对维度：total_assets, total_liabilities, net_assets。
    任一侧缺键/缺值时该维度不参与数值比较：diff=None、breached=True，
    并在 missing_keys 中标注缺失侧（"position" / "ledger"）。
    """
    threshold = Decimal(str(threshold_yuan))
    dims = ("total_assets", "total_liabilities", "net_assets")
    rows = []
    for d in dims:
        pv = _comparison_decimal(position_totals.get(d))
        lv = _comparison_decimal(ledger_totals.get(d))
        missing_keys = [
            *(["position"] if pv is None else []),
            *(["ledger"] if lv is None else []),
        ]
        if missing_keys:
            rows.append(
                {
                    "dimension": d,
                    "position_value": None if pv is None else float(pv),
                    "ledger_value": None if lv is None else float(lv),
                    "diff": None,
                    "breached": True,
                    "missing_keys": missing_keys,
                }
            )
            continue
        # missing_keys 为空即两侧都已解析成功；assert 仅用于类型收窄，不改变行为。
        assert pv is not None and lv is not None
        diff = pv - lv
        rows.append(
            {
                "dimension": d,
                "position_value": float(pv),
                "ledger_value": float(lv),
                "diff": float(diff),
                "breached": abs(diff) >= threshold,
                "missing_keys": [],
            }
        )
    return rows


def pnl_vs_ledger_diff(
    pnl_total: object,
    ledger_pnl_total: object,
    *,
    threshold_yuan: float | Decimal = 1.0,
) -> dict[str, Any]:
    threshold = Decimal(str(threshold_yuan))
    pv = _comparison_decimal(pnl_total)
    lv = _comparison_decimal(ledger_pnl_total)
    missing_keys = [
        *(["pnl_total"] if pv is None else []),
        *(["ledger_pnl_total"] if lv is None else []),
    ]
    if missing_keys:
        return {
            "pnl_total": None if pv is None else float(pv),
            "ledger_pnl_total": None if lv is None else float(lv),
            "diff": None,
            "breached": True,
            "missing_keys": missing_keys,
        }
    # missing_keys 为空即两侧都已解析成功；assert 仅用于类型收窄，不改变行为。
    assert pv is not None and lv is not None
    diff = pv - lv
    return {
        "pnl_total": float(pv),
        "ledger_pnl_total": float(lv),
        "diff": float(diff),
        "breached": abs(diff) >= threshold,
        "missing_keys": [],
    }


def completeness_check(
    product_category_total: object,
    pnl_total: object,
    *,
    threshold_yuan: float | Decimal = 1.0,
) -> dict[str, Any]:
    threshold = Decimal(str(threshold_yuan))
    cv = _comparison_decimal(product_category_total)
    pv = _comparison_decimal(pnl_total)
    missing_keys = [
        *(["product_category_total"] if cv is None else []),
        *(["pnl_total"] if pv is None else []),
    ]
    if missing_keys:
        return {
            "product_category_total": None if cv is None else float(cv),
            "pnl_total": None if pv is None else float(pv),
            "diff": None,
            "breached": True,
            "missing_keys": missing_keys,
        }
    # missing_keys 为空即两侧都已解析成功；assert 仅用于类型收窄，不改变行为。
    assert cv is not None and pv is not None
    diff = cv - pv
    return {
        "product_category_total": float(cv),
        "pnl_total": float(pv),
        "diff": float(diff),
        "breached": abs(diff) >= threshold,
        "missing_keys": [],
    }
