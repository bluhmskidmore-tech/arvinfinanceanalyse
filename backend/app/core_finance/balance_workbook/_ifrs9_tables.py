"""IFRS9 table builders for balance analysis workbook."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from backend.app.core_finance.balance_analysis import (
    FormalTywBalanceFactRow,
    FormalZqtzBalanceFactRow,
)
from backend.app.core_finance.balance_workbook._utils import (
    _ZERO,
    _group_rows,
    _sum_decimal,
    _weighted_average,
    _safe_ratio,
    _to_wanyuan,
    _decimal_value,
    _table,
)


def _build_ifrs9_classification_table(
    zqtz_rows: list[FormalZqtzBalanceFactRow],
    tyw_rows: list[FormalTywBalanceFactRow],
) -> dict[str, Any]:
    grouped: dict[tuple[str, str, str, str], dict[str, Decimal | int]] = {}

    for row in zqtz_rows:
        key = ("zqtz", row.position_scope, row.invest_type_std, row.accounting_basis)
        bucket = grouped.setdefault(key, {"row_count": 0, "balance_amount": _ZERO})
        bucket["row_count"] = int(bucket["row_count"]) + 1
        bucket["balance_amount"] = _decimal_value(bucket["balance_amount"]) + row.face_value_amount

    for row in tyw_rows:
        key = ("tyw", row.position_scope, row.invest_type_std, row.accounting_basis)
        bucket = grouped.setdefault(key, {"row_count": 0, "balance_amount": _ZERO})
        bucket["row_count"] = int(bucket["row_count"]) + 1
        bucket["balance_amount"] = _decimal_value(bucket["balance_amount"]) + row.principal_amount

    grand_total = _ZERO
    for values in grouped.values():
        grand_total += _decimal_value(values["balance_amount"])

    rows = []
    for (source_family, position_scope, invest_type_std, accounting_basis), values in sorted(grouped.items()):
        balance_amount = _decimal_value(values["balance_amount"])
        rows.append(
            {
                "source_family": source_family,
                "position_scope": position_scope,
                "invest_type_std": invest_type_std,
                "accounting_basis": accounting_basis,
                "row_count": int(values["row_count"]),
                "balance_amount": _to_wanyuan(balance_amount),
                "share_of_total": _safe_ratio(balance_amount, grand_total),
            }
        )

    return _table(
        "ifrs9_classification",
        "IFRS9 分类",
        [
            ("source_family", "来源"),
            ("position_scope", "范围"),
            ("invest_type_std", "投资分类"),
            ("accounting_basis", "会计计量"),
            ("row_count", "笔数"),
            ("balance_amount", "面值/金额"),
            ("share_of_total", "占合计比"),
        ],
        rows,
    )


def _build_ifrs9_position_scope_table(
    zqtz_rows: list[FormalZqtzBalanceFactRow],
    tyw_rows: list[FormalTywBalanceFactRow],
) -> dict[str, Any]:
    buckets: dict[str, dict[str, Decimal | int]] = {}
    grand_total = _ZERO

    for row in zqtz_rows:
        key = str(row.position_scope)
        bucket = buckets.setdefault(key, {"row_count": 0, "balance_amount": _ZERO})
        bucket["row_count"] = int(bucket["row_count"]) + 1
        bucket["balance_amount"] = _decimal_value(bucket["balance_amount"]) + row.face_value_amount
        grand_total += row.face_value_amount

    for row in tyw_rows:
        key = str(row.position_scope)
        bucket = buckets.setdefault(key, {"row_count": 0, "balance_amount": _ZERO})
        bucket["row_count"] = int(bucket["row_count"]) + 1
        bucket["balance_amount"] = _decimal_value(bucket["balance_amount"]) + row.principal_amount
        grand_total += row.principal_amount

    rows = []
    for position_scope in sorted(buckets.keys()):
        values = buckets[position_scope]
        balance_amount = _decimal_value(values["balance_amount"])
        rows.append(
            {
                "position_scope": position_scope,
                "row_count": int(values["row_count"]),
                "balance_amount": _to_wanyuan(balance_amount),
                "share_of_total": _safe_ratio(balance_amount, grand_total),
            }
        )

    return _table(
        "ifrs9_position_scope",
        "IFRS9 资产负债分层",
        [
            ("position_scope", "范围"),
            ("row_count", "笔数"),
            ("balance_amount", "面值/金额"),
            ("share_of_total", "占合计比"),
        ],
        rows,
    )


def _build_ifrs9_source_family_table(
    zqtz_rows: list[FormalZqtzBalanceFactRow],
    tyw_rows: list[FormalTywBalanceFactRow],
) -> dict[str, Any]:
    buckets: dict[str, dict[str, Decimal | int]] = {"zqtz": {"row_count": 0, "balance_amount": _ZERO}, "tyw": {"row_count": 0, "balance_amount": _ZERO}}
    grand_total = _ZERO

    for row in zqtz_rows:
        bucket = buckets["zqtz"]
        bucket["row_count"] = int(bucket["row_count"]) + 1
        bucket["balance_amount"] = _decimal_value(bucket["balance_amount"]) + row.face_value_amount
        grand_total += row.face_value_amount

    for row in tyw_rows:
        bucket = buckets["tyw"]
        bucket["row_count"] = int(bucket["row_count"]) + 1
        bucket["balance_amount"] = _decimal_value(bucket["balance_amount"]) + row.principal_amount
        grand_total += row.principal_amount

    rows = []
    for source_family in ("zqtz", "tyw"):
        values = buckets[source_family]
        balance_amount = _decimal_value(values["balance_amount"])
        rows.append(
            {
                "source_family": source_family,
                "row_count": int(values["row_count"]),
                "balance_amount": _to_wanyuan(balance_amount),
                "share_of_total": _safe_ratio(balance_amount, grand_total),
            }
        )

    return _table(
        "ifrs9_source_family",
        "IFRS9 来源分层",
        [
            ("source_family", "来源"),
            ("row_count", "笔数"),
            ("balance_amount", "面值/金额"),
            ("share_of_total", "占合计比"),
        ],
        rows,
    )


def _build_account_category_comparison_table(
    zqtz_rows: list[FormalZqtzBalanceFactRow],
) -> dict[str, Any]:
    asset_rows = [row for row in zqtz_rows if row.position_scope == "asset"]
    total_balance = _sum_decimal(asset_rows, lambda row: row.face_value_amount)
    grouped = _group_rows(asset_rows, lambda row: row.account_category or "未分类")
    rows = []
    for account_category, entries in sorted(
        grouped.items(),
        key=lambda item: (
            -_sum_decimal(item[1], lambda row: row.face_value_amount),
            item[0],
        ),
    ):
        balance_amount = _sum_decimal(entries, lambda row: row.face_value_amount)
        rows.append(
            {
                "account_category": account_category,
                "row_count": len(entries),
                "balance_amount": _to_wanyuan(balance_amount),
                "share_of_bond_assets": _safe_ratio(balance_amount, total_balance),
                "weighted_rate_pct": _weighted_average(
                    entries,
                    lambda row: row.face_value_amount,
                    lambda row: row.coupon_rate,
                ),
            }
        )

    return _table(
        "account_category_comparison",
        "账户类别对比",
        [
            ("account_category", "账户类别"),
            ("row_count", "笔数"),
            ("balance_amount", "面值/余额"),
            ("share_of_bond_assets", "占债券资产比"),
            ("weighted_rate_pct", "加权利率(%)"),
        ],
        rows,
    )


def _build_rule_reference_table() -> dict[str, Any]:
    rows = [
        {
            "rule_id": "bal_scope_issuance_exclusion",
            "rule_name": "发行类剔除",
            "summary": "资产端默认剔除发行类，负债端单独保留发行类语义行。",
            "source_doc": "docs/calc_rules.md",
            "source_section": "12.2 zqtz formal fact 规则",
        },
        {
            "rule_id": "bal_formal_fact_boundary",
            "rule_name": "正式事实输入边界",
            "summary": "workbook 只消费 formal fact，不直读 snapshot 或 preview。",
            "source_doc": "docs/data_contracts.md",
            "source_section": "4.3 fact_formal_zqtz_balance_daily / 4.4 fact_formal_tyw_balance_daily",
        },
        {
            "rule_id": "bal_fx_projection_order",
            "rule_name": "汇率换算顺序",
            "summary": "CNY 口径必须先逐日 FX，再进入逐日 formal amount。",
            "source_doc": "docs/calc_rules.md",
            "source_section": "12.4 月均与汇率顺序",
        },
        {
            "rule_id": "bal_workbook_supported_sections",
            "rule_name": "已支持 workbook section 边界",
            "summary": "只有当前 governed workbook 已支持的 section 可以宣称已落地。",
            "source_doc": "docs/BALANCE_ANALYSIS_SPEC_FOR_CODEX.md",
            "source_section": "13 当前 governed workbook 已支持的 section keys",
        },
    ]
    return _table(
        "rule_reference",
        "规则引用",
        [
            ("rule_id", "Rule ID"),
            ("rule_name", "规则名称"),
            ("summary", "规则摘要"),
            ("source_doc", "来源文档"),
            ("source_section", "来源章节"),
        ],
        rows,
    )
