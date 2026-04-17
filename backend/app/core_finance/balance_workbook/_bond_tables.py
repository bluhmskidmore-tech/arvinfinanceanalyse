"""Bond table builders for balance analysis workbook."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from backend.app.core_finance.balance_analysis import (
    FormalTywBalanceFactRow,
    FormalZqtzBalanceFactRow,
)
from backend.app.core_finance.balance_workbook._utils import (
    _ZERO,
    _MATURITY_BUCKETS,
    _LIQUIDITY_LAYER_ORDER,
    _LIQUIDITY_LEVEL1_BOND_TYPES,
    _LIQUIDITY_HQLA_HAIRCUTS,
    _LIQUIDITY_HIGH_RATING,
    _group_rows,
    _sum_decimal,
    _weighted_average,
    _merged_weighted_average,
    _remaining_years,
    _optional_remaining_years,
    _match_bucket,
    _safe_ratio,
    _spread_bp,
    _normalize_interest_mode,
    _to_wanyuan,
    _month_ladder,
    _month_key,
    _card,
    _table,
)


def _build_cards(
    zqtz_rows: list[FormalZqtzBalanceFactRow],
    tyw_rows: list[FormalTywBalanceFactRow],
) -> list[dict[str, Any]]:
    bond_assets = [row for row in zqtz_rows if row.position_scope == "asset"]
    issuance_rows = [row for row in zqtz_rows if row.position_scope == "liability"]
    interbank_assets = [row for row in tyw_rows if row.position_scope == "asset"]
    interbank_liabilities = [row for row in tyw_rows if row.position_scope == "liability"]
    bond_asset_total = _sum_decimal(bond_assets, lambda row: row.face_value_amount)
    interbank_asset_total = _sum_decimal(interbank_assets, lambda row: row.principal_amount)
    interbank_liability_total = _sum_decimal(interbank_liabilities, lambda row: row.principal_amount)
    issuance_total = _sum_decimal(issuance_rows, lambda row: row.face_value_amount)
    assets_total = bond_asset_total + interbank_asset_total
    net_position = assets_total - interbank_liability_total
    return [
        _card("bond_assets_excluding_issue", "债券资产(剔除发行类)", _to_wanyuan(bond_asset_total), "ZQTZ 资产端剔除发行类后余额(万元)"),
        _card("interbank_assets", "同业资产", _to_wanyuan(interbank_asset_total), "TYW 资产端余额(万元)"),
        _card("interbank_liabilities", "同业负债", _to_wanyuan(interbank_liability_total), "TYW 负债端余额(万元)"),
        _card("issuance_liabilities", "发行类负债", _to_wanyuan(issuance_total), "ZQTZ 发行类单独展示(万元)"),
        _card("net_position", "净头寸", _to_wanyuan(net_position), "资产端合计 - 同业负债(万元)"),
    ]


def _build_bond_business_type_table(zqtz_rows: list[FormalZqtzBalanceFactRow]) -> dict[str, Any]:
    asset_rows = [row for row in zqtz_rows if row.position_scope == "asset"]
    total_balance = _sum_decimal(asset_rows, lambda row: row.face_value_amount)
    grouped = _group_rows(asset_rows, lambda row: row.bond_type or "未分类")
    rows = []
    for bond_type, entries in sorted(grouped.items()):
        balance_amount = _sum_decimal(entries, lambda row: row.face_value_amount)
        rows.append(
            {
                "bond_type": bond_type,
                "count": len(entries),
                "balance_amount": _to_wanyuan(balance_amount),
                "share": _safe_ratio(balance_amount, total_balance),
                "weighted_rate_pct": _weighted_average(entries, lambda row: row.face_value_amount, lambda row: row.coupon_rate),
                "weighted_term_years": _weighted_average(entries, lambda row: row.face_value_amount, lambda row: _optional_remaining_years(row.report_date, row.maturity_date)),
                "amortized_cost_amount": _to_wanyuan(_sum_decimal(entries, lambda row: row.amortized_cost_amount)),
                "market_value_amount": _to_wanyuan(_sum_decimal(entries, lambda row: row.market_value_amount)),
                "floating_pnl_amount": _to_wanyuan(_sum_decimal(
                    entries,
                    lambda row: row.market_value_amount - row.amortized_cost_amount,
                )),
            }
        )
    return _table(
        "bond_business_types",
        "债券业务种类",
        [
            ("bond_type", "业务种类"),
            ("count", "笔数"),
            ("balance_amount", "面值/余额"),
            ("share", "占比"),
            ("weighted_rate_pct", "加权利率(%)"),
            ("weighted_term_years", "加权期限(年)"),
            ("amortized_cost_amount", "摊余成本"),
            ("market_value_amount", "公允价值"),
            ("floating_pnl_amount", "浮盈浮亏"),
        ],
        rows,
    )


def _build_maturity_gap_table(
    report_date: date,
    zqtz_rows: list[FormalZqtzBalanceFactRow],
    tyw_rows: list[FormalTywBalanceFactRow],
) -> dict[str, Any]:
    asset_bonds = [row for row in zqtz_rows if row.position_scope == "asset"]
    issuance_rows = [row for row in zqtz_rows if row.position_scope == "liability"]
    asset_interbank = [row for row in tyw_rows if row.position_scope == "asset"]
    liability_interbank = [row for row in tyw_rows if row.position_scope == "liability"]
    asset_total_all = _sum_decimal(asset_bonds, lambda row: row.face_value_amount) + _sum_decimal(
        asset_interbank, lambda row: row.principal_amount
    )
    liability_total_all = _sum_decimal(liability_interbank, lambda row: row.principal_amount)

    cumulative_gap = _ZERO
    rows = []
    for label, lower, upper in _MATURITY_BUCKETS:
        bucket_bonds = [row for row in asset_bonds if _match_bucket(_remaining_years(report_date, row.maturity_date), lower, upper)]
        bucket_issuance = [row for row in issuance_rows if _match_bucket(_remaining_years(report_date, row.maturity_date), lower, upper)]
        bucket_assets = [row for row in asset_interbank if _match_bucket(_remaining_years(report_date, row.maturity_date), lower, upper)]
        bucket_liabilities = [row for row in liability_interbank if _match_bucket(_remaining_years(report_date, row.maturity_date), lower, upper)]
        bond_asset_amount = _sum_decimal(bucket_bonds, lambda row: row.face_value_amount)
        issuance_amount = _sum_decimal(bucket_issuance, lambda row: row.face_value_amount)
        interbank_asset_amount = _sum_decimal(bucket_assets, lambda row: row.principal_amount)
        interbank_liability_amount = _sum_decimal(bucket_liabilities, lambda row: row.principal_amount)
        asset_total = bond_asset_amount + interbank_asset_amount
        full_scope_liability_amount = issuance_amount + interbank_liability_amount
        gap = asset_total - interbank_liability_amount
        full_scope_gap = asset_total - full_scope_liability_amount
        cumulative_gap += gap
        rows.append(
            {
                "bucket": label,
                "bond_assets_amount": _to_wanyuan(bond_asset_amount),
                "interbank_assets_amount": _to_wanyuan(interbank_asset_amount),
                "asset_total_amount": _to_wanyuan(asset_total),
                "issuance_amount": _to_wanyuan(issuance_amount),
                "interbank_liabilities_amount": _to_wanyuan(interbank_liability_amount),
                "full_scope_liability_amount": _to_wanyuan(full_scope_liability_amount),
                "gap_amount": _to_wanyuan(gap),
                "full_scope_gap_amount": _to_wanyuan(full_scope_gap),
                "cumulative_gap_amount": _to_wanyuan(cumulative_gap),
                "asset_share": _safe_ratio(asset_total, asset_total_all),
                "liability_share": _safe_ratio(interbank_liability_amount, liability_total_all),
                "asset_weighted_rate_pct": _merged_weighted_average(
                    [(bucket_bonds, lambda row: row.face_value_amount, lambda row: row.coupon_rate), (bucket_assets, lambda row: row.principal_amount, lambda row: row.funding_cost_rate)]
                ),
                "liability_weighted_rate_pct": _weighted_average(
                    bucket_liabilities, lambda row: row.principal_amount, lambda row: row.funding_cost_rate
                ),
                "spread_bp": _spread_bp(
                    _merged_weighted_average(
                        [(bucket_bonds, lambda row: row.face_value_amount, lambda row: row.coupon_rate), (bucket_assets, lambda row: row.principal_amount, lambda row: row.funding_cost_rate)]
                    ),
                    _weighted_average(bucket_liabilities, lambda row: row.principal_amount, lambda row: row.funding_cost_rate),
                ),
            }
        )
    return _table(
        "maturity_gap",
        "期限缺口分析",
        [
            ("bucket", "期限分类"),
            ("bond_assets_amount", "债券资产"),
            ("interbank_assets_amount", "同业资产"),
            ("asset_total_amount", "资产合计"),
            ("issuance_amount", "发行类"),
            ("interbank_liabilities_amount", "同业负债"),
            ("full_scope_liability_amount", "全口径负债"),
            ("gap_amount", "缺口"),
            ("full_scope_gap_amount", "全口径缺口"),
            ("cumulative_gap_amount", "累计缺口"),
            ("asset_share", "资产占比"),
            ("liability_share", "负债占比"),
            ("asset_weighted_rate_pct", "资产加权利率(%)"),
            ("liability_weighted_rate_pct", "负债加权利率(%)"),
            ("spread_bp", "利差(bp)"),
        ],
        rows,
    )


def _build_issuance_business_type_table(zqtz_rows: list[FormalZqtzBalanceFactRow]) -> dict[str, Any]:
    issuance_rows = [row for row in zqtz_rows if row.position_scope == "liability"]
    total_balance = _sum_decimal(issuance_rows, lambda row: row.face_value_amount)
    grouped = _group_rows(issuance_rows, lambda row: row.bond_type or "未分类")
    rows = []
    for bond_type, entries in sorted(grouped.items()):
        balance_amount = _sum_decimal(entries, lambda row: row.face_value_amount)
        rows.append(
            {
                "bond_type": bond_type,
                "count": len(entries),
                "balance_amount": _to_wanyuan(balance_amount),
                "share": _safe_ratio(balance_amount, total_balance),
                "weighted_rate_pct": _weighted_average(entries, lambda row: row.face_value_amount, lambda row: row.coupon_rate),
                "weighted_term_years": _weighted_average(entries, lambda row: row.face_value_amount, lambda row: _optional_remaining_years(row.report_date, row.maturity_date)),
                "interest_mode_fixed_count": sum(1 for row in entries if _normalize_interest_mode(row.interest_mode) == "固定"),
                "interest_mode_floating_count": sum(1 for row in entries if _normalize_interest_mode(row.interest_mode) == "浮动"),
            }
        )
    return _table(
        "issuance_business_types",
        "发行类分析",
        [
            ("bond_type", "业务种类"),
            ("count", "笔数"),
            ("balance_amount", "金额"),
            ("share", "占比"),
            ("weighted_rate_pct", "加权利率(%)"),
            ("weighted_term_years", "加权期限(年)"),
            ("interest_mode_fixed_count", "固定计息"),
            ("interest_mode_floating_count", "浮动计息"),
        ],
        rows,
    )


def _build_issuer_concentration_table(zqtz_rows: list[FormalZqtzBalanceFactRow]) -> dict[str, Any]:
    asset_rows = [row for row in zqtz_rows if row.position_scope == "asset"]
    total_balance = _sum_decimal(asset_rows, lambda row: row.face_value_amount)
    grouped = _group_rows(asset_rows, lambda row: row.issuer_name or "未分类")
    rows = []
    for issuer_name, entries in sorted(
        grouped.items(),
        key=lambda item: (
            -_sum_decimal(item[1], lambda row: row.face_value_amount),
            item[0],
        ),
    ):
        balance_amount = _sum_decimal(entries, lambda row: row.face_value_amount)
        rows.append(
            {
                "issuer_name": issuer_name,
                "count": len(entries),
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
        "issuer_concentration",
        "发行人集中度",
        [
            ("issuer_name", "发行人"),
            ("count", "笔数"),
            ("balance_amount", "面值/余额"),
            ("share_of_bond_assets", "占债券资产比"),
            ("weighted_rate_pct", "加权利率(%)"),
        ],
        rows,
    )


def _classify_liquidity_layer(row: FormalZqtzBalanceFactRow) -> str:
    bond_type = str(row.bond_type or "").strip()
    if bond_type in _LIQUIDITY_LEVEL1_BOND_TYPES:
        return "Level 1"
    if bond_type == "地方政府债":
        return "Level 2A"
    if bond_type == "同业存单":
        return "Level 2B"
    rating = str(row.rating or "").strip()
    if rating in _LIQUIDITY_HIGH_RATING:
        return "Level 2B"
    return "其他"


def _build_liquidity_layers_table(zqtz_rows: list[FormalZqtzBalanceFactRow]) -> dict[str, Any]:
    asset_rows = [row for row in zqtz_rows if row.position_scope == "asset"]
    total_balance = _sum_decimal(asset_rows, lambda row: row.face_value_amount)
    grouped: dict[str, list[FormalZqtzBalanceFactRow]] = {layer: [] for layer in _LIQUIDITY_LAYER_ORDER}
    for row in asset_rows:
        layer = _classify_liquidity_layer(row)
        grouped[layer].append(row)

    rows = []
    for layer in _LIQUIDITY_LAYER_ORDER:
        entries = grouped[layer]
        balance_amount = _sum_decimal(entries, lambda row: row.face_value_amount)
        haircut = _LIQUIDITY_HQLA_HAIRCUTS[layer]
        balance_wanyuan = _to_wanyuan(balance_amount)
        rows.append(
            {
                "liquidity_layer": layer,
                "row_count": len(entries),
                "balance_amount": balance_wanyuan,
                "share_of_bond_assets": _safe_ratio(balance_amount, total_balance),
                "weighted_rate_pct": _weighted_average(
                    entries,
                    lambda row: row.face_value_amount,
                    lambda row: row.coupon_rate,
                ),
                "hqla_haircut": haircut,
                "hqla_amount": balance_wanyuan * haircut,
            }
        )

    return _table(
        "liquidity_layers",
        "流动性分层(HQLA)",
        [
            ("liquidity_layer", "分层"),
            ("row_count", "笔数"),
            ("balance_amount", "面值/余额"),
            ("share_of_bond_assets", "占债券资产比"),
            ("weighted_rate_pct", "加权利率(%)"),
            ("hqla_haircut", "HQLA折扣"),
            ("hqla_amount", "HQLA金额"),
        ],
        rows,
    )


def _build_portfolio_comparison_table(zqtz_rows: list[FormalZqtzBalanceFactRow]) -> dict[str, Any]:
    asset_rows = [row for row in zqtz_rows if row.position_scope == "asset"]
    grouped = _group_rows(asset_rows, lambda row: row.portfolio_name or "未分类")
    rows = []
    for portfolio_name, entries in sorted(grouped.items()):
        balance_amount = _sum_decimal(entries, lambda row: row.face_value_amount)
        rows.append(
            {
                "portfolio_name": portfolio_name,
                "row_count": len(entries),
                "balance_amount": _to_wanyuan(balance_amount),
                "weighted_rate_pct": _weighted_average(entries, lambda row: row.face_value_amount, lambda row: row.coupon_rate),
                "weighted_term_years": _weighted_average(
                    entries,
                    lambda row: row.face_value_amount,
                    lambda row: _optional_remaining_years(row.report_date, row.maturity_date),
                ),
                "floating_pnl_amount": _to_wanyuan(
                    _sum_decimal(entries, lambda row: row.market_value_amount - row.amortized_cost_amount)
                ),
            }
        )
    return _table(
        "portfolio_comparison",
        "组合对比",
        [
            ("portfolio_name", "组合"),
            ("row_count", "笔数"),
            ("balance_amount", "面值/余额"),
            ("weighted_rate_pct", "加权利率(%)"),
            ("weighted_term_years", "加权期限(年)"),
            ("floating_pnl_amount", "浮盈浮亏"),
        ],
        rows,
    )


def _build_cashflow_calendar_table(
    report_date: date,
    zqtz_rows: list[FormalZqtzBalanceFactRow],
    tyw_rows: list[FormalTywBalanceFactRow],
) -> dict[str, Any]:
    asset_bonds = [row for row in zqtz_rows if row.position_scope == "asset" and row.maturity_date is not None and row.maturity_date >= report_date]
    issuance_rows = [row for row in zqtz_rows if row.position_scope == "liability" and row.maturity_date is not None and row.maturity_date >= report_date]
    interbank_assets = [row for row in tyw_rows if row.position_scope == "asset" and row.maturity_date is not None and row.maturity_date >= report_date]
    interbank_liabilities = [row for row in tyw_rows if row.position_scope == "liability" and row.maturity_date is not None and row.maturity_date >= report_date]

    cumulative_net_cashflow = _ZERO
    rows = []
    for month_key in _month_ladder(report_date, 12):
        month_bonds = [row for row in asset_bonds if _month_key(row.maturity_date) == month_key]
        month_interbank_assets = [row for row in interbank_assets if _month_key(row.maturity_date) == month_key]
        month_interbank_liabilities = [row for row in interbank_liabilities if _month_key(row.maturity_date) == month_key]
        month_issuance = [row for row in issuance_rows if _month_key(row.maturity_date) == month_key]

        bond_maturity_amount = _sum_decimal(month_bonds, lambda row: row.face_value_amount)
        interbank_asset_maturity_amount = _sum_decimal(month_interbank_assets, lambda row: row.principal_amount)
        interbank_liability_maturity_amount = _sum_decimal(month_interbank_liabilities, lambda row: row.principal_amount)
        issuance_maturity_amount = _sum_decimal(month_issuance, lambda row: row.face_value_amount)
        net_cashflow_amount = bond_maturity_amount + interbank_asset_maturity_amount - interbank_liability_maturity_amount - issuance_maturity_amount
        cumulative_net_cashflow += net_cashflow_amount

        rows.append(
            {
                "month": month_key,
                "bond_maturity_amount": _to_wanyuan(bond_maturity_amount),
                "bond_maturity_count": len(month_bonds),
                "interbank_asset_maturity_amount": _to_wanyuan(interbank_asset_maturity_amount),
                "interbank_asset_maturity_count": len(month_interbank_assets),
                "interbank_liability_maturity_amount": _to_wanyuan(interbank_liability_maturity_amount),
                "interbank_liability_maturity_count": len(month_interbank_liabilities),
                "issuance_maturity_amount": _to_wanyuan(issuance_maturity_amount),
                "issuance_maturity_count": len(month_issuance),
                "net_cashflow_amount": _to_wanyuan(net_cashflow_amount),
                "cumulative_net_cashflow_amount": _to_wanyuan(cumulative_net_cashflow),
            }
        )

    return _table(
        "cashflow_calendar",
        "Cashflow Calendar",
        [
            ("month", "Month"),
            ("bond_maturity_amount", "Bond Maturity Amount"),
            ("bond_maturity_count", "Bond Maturity Count"),
            ("interbank_asset_maturity_amount", "Interbank Asset Maturity Amount"),
            ("interbank_asset_maturity_count", "Interbank Asset Maturity Count"),
            ("interbank_liability_maturity_amount", "Interbank Liability Maturity Amount"),
            ("interbank_liability_maturity_count", "Interbank Liability Maturity Count"),
            ("issuance_maturity_amount", "Issuance Maturity Amount"),
            ("issuance_maturity_count", "Issuance Maturity Count"),
            ("net_cashflow_amount", "Net Cashflow Amount"),
            ("cumulative_net_cashflow_amount", "Cumulative Net Cashflow Amount"),
        ],
        rows,
    )


def _build_vintage_analysis_table(zqtz_rows: list[FormalZqtzBalanceFactRow]) -> dict[str, Any]:
    asset_rows = [row for row in zqtz_rows if row.position_scope == "asset" and row.value_date is not None]
    grouped = _group_rows(asset_rows, lambda row: str(row.value_date.year))
    rows = []
    for start_year in sorted(grouped.keys()):
        entries = grouped[start_year]
        balance_amount = _sum_decimal(entries, lambda row: row.face_value_amount)
        rows.append(
            {
                "start_year": start_year,
                "row_count": len(entries),
                "balance_amount": _to_wanyuan(balance_amount),
                "weighted_rate_pct": _weighted_average(entries, lambda row: row.face_value_amount, lambda row: row.coupon_rate),
                "weighted_term_years": _weighted_average(
                    entries,
                    lambda row: row.face_value_amount,
                    lambda row: _optional_remaining_years(row.report_date, row.maturity_date),
                ),
            }
        )
    return _table(
        "vintage_analysis",
        "起息年分桶(Vintage)",
        [
            ("start_year", "起息年"),
            ("row_count", "笔数"),
            ("balance_amount", "面值/余额"),
            ("weighted_rate_pct", "加权利率(%)"),
            ("weighted_term_years", "加权期限(年)"),
        ],
        rows,
    )


def _build_customer_attribute_analysis_table(zqtz_rows: list[FormalZqtzBalanceFactRow]) -> dict[str, Any]:
    asset_rows = [row for row in zqtz_rows if row.position_scope == "asset"]
    grouped = _group_rows(asset_rows, lambda row: row.customer_attribute or "未标注")
    rows = []
    for attr, entries in sorted(grouped.items()):
        balance_amount = _sum_decimal(entries, lambda row: row.face_value_amount)
        rows.append(
            {
                "customer_attribute": attr,
                "row_count": len(entries),
                "balance_amount": _to_wanyuan(balance_amount),
                "weighted_rate_pct": _weighted_average(entries, lambda row: row.face_value_amount, lambda row: row.coupon_rate),
                "weighted_term_years": _weighted_average(
                    entries,
                    lambda row: row.face_value_amount,
                    lambda row: _optional_remaining_years(row.report_date, row.maturity_date),
                ),
            }
        )
    return _table(
        "customer_attribute_analysis",
        "客户属性分布",
        [
            ("customer_attribute", "客户属性"),
            ("row_count", "笔数"),
            ("balance_amount", "面值/余额"),
            ("weighted_rate_pct", "加权利率(%)"),
            ("weighted_term_years", "加权期限(年)"),
        ],
        rows,
    )
