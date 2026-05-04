"""Balance analysis workbook builder - monolithic implementation.

REFACTORING NOTE (2026-04-17):
This 1576-line file contains 29 _build_* table functions with no clear separation.
Planned refactoring: split into modular structure under balance_workbook/ package:
  - _utils.py: shared utilities (group_rows, weighted_average, etc.) [DONE]
  - _cards.py: _build_cards
  - _bond_tables.py: bond_business_type, maturity_gap, issuer_concentration, etc.
  - _ifrs9_tables.py: ifrs9_classification, ifrs9_position_scope, ifrs9_source_family
  - _risk_tables.py: regulatory_limits, overdue_credit_quality, risk_alerts
  - _analysis_tables.py: campisi, cross_analysis, decision_items, event_calendar
  - builder.py: main entry point [DONE]

For now, this file remains intact to avoid breaking existing imports.
New code should import from balance_workbook package instead.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from backend.app.core_finance.balance_analysis import (
    BalanceCurrencyBasis,
    BalancePositionScope,
    FormalTywBalanceFactRow,
    FormalZqtzBalanceFactRow,
)
from backend.app.core_finance.interest_mode import classify_interest_rate_style

_ZERO = Decimal("0")
_MATURITY_BUCKETS = (
    ("已到期/逾期", None, Decimal("0")),
    ("3个月以内", Decimal("0"), Decimal("0.25")),
    ("3-6个月", Decimal("0.25"), Decimal("0.5")),
    ("6-12个月", Decimal("0.5"), Decimal("1")),
    ("1-2年", Decimal("1"), Decimal("2")),
    ("2-3年", Decimal("2"), Decimal("3")),
    ("3-5年", Decimal("3"), Decimal("5")),
    ("5-10年", Decimal("5"), Decimal("10")),
    ("10年以上", Decimal("10"), None),
)
_RATE_BUCKETS = (
    ("零息/无息", None, Decimal("0")),
    ("1.5%以下", Decimal("0"), Decimal("1.5")),
    ("1.5%-2.0%", Decimal("1.5"), Decimal("2.0")),
    ("2.0%-2.5%", Decimal("2.0"), Decimal("2.5")),
    ("2.5%-3.0%", Decimal("2.5"), Decimal("3.0")),
    ("3.0%-3.5%", Decimal("3.0"), Decimal("3.5")),
    ("3.5%-4.0%", Decimal("3.5"), Decimal("4.0")),
    ("4.0%以上", Decimal("4.0"), None),
)
_CAMPISI_POLICY_BOND = "政策性金融债"
_TEN_THOUSAND = Decimal("10000")
_LIQUIDITY_LAYER_ORDER = ("Level 1", "Level 2A", "Level 2B", "其他")
_LIQUIDITY_LEVEL1_BOND_TYPES = frozenset({"国债", "政策性金融债", "凭证式国债"})
_LIQUIDITY_HQLA_HAIRCUTS = {
    "Level 1": Decimal("1.00"),
    "Level 2A": Decimal("0.85"),
    "Level 2B": Decimal("0.75"),
    "其他": Decimal("0"),
}
_LIQUIDITY_HIGH_RATING = frozenset({"AAA", "AA+"})


def build_balance_analysis_workbook_payload(
    *,
    report_date: date,
    position_scope: BalancePositionScope,
    currency_basis: BalanceCurrencyBasis,
    zqtz_rows: list[FormalZqtzBalanceFactRow],
    tyw_rows: list[FormalTywBalanceFactRow],
    zqtz_currency_rows: list[FormalZqtzBalanceFactRow] | None = None,
) -> dict[str, Any]:
    zqtz_currency_rows = zqtz_currency_rows or zqtz_rows
    cards = _build_cards(zqtz_rows, tyw_rows)
    tables = [
        _build_bond_business_type_table(zqtz_rows),
        _build_maturity_gap_table(report_date, zqtz_rows, tyw_rows),
        _build_cashflow_calendar_table(report_date, zqtz_rows, tyw_rows),
        _build_issuer_concentration_table(zqtz_rows),
        _build_liquidity_layers_table(zqtz_rows),
        _build_regulatory_limits_table(report_date, zqtz_rows, tyw_rows),
        _build_overdue_credit_quality_detail_table(zqtz_rows),
        _build_overdue_credit_quality_rating_table(zqtz_rows),
        _build_vintage_analysis_table(zqtz_rows),
        _build_customer_attribute_analysis_table(zqtz_rows),
        _build_portfolio_comparison_table(zqtz_rows),
        _build_account_category_comparison_table(zqtz_rows),
        _build_ifrs9_classification_table(zqtz_rows, tyw_rows),
        _build_ifrs9_position_scope_table(zqtz_rows, tyw_rows),
        _build_ifrs9_source_family_table(zqtz_rows, tyw_rows),
        _build_rule_reference_table(),
        _build_issuance_business_type_table(zqtz_rows),
        _build_currency_split_table(zqtz_currency_rows),
        _build_rating_table(zqtz_rows),
        _build_rate_distribution_table(zqtz_rows, tyw_rows),
        _build_industry_table(zqtz_rows),
        _build_counterparty_type_table(tyw_rows),
        _build_campisi_table(zqtz_rows),
        _build_cross_analysis_table(zqtz_rows),
        _build_interest_mode_table(zqtz_rows),
        _build_decision_items_table(report_date, zqtz_rows, tyw_rows),
        _build_event_calendar_table(report_date, zqtz_rows, tyw_rows),
        _build_risk_alerts_table(report_date, zqtz_rows, tyw_rows),
    ]
    return {
        "report_date": report_date.isoformat(),
        "position_scope": position_scope,
        "currency_basis": currency_basis,
        "cards": cards,
        "tables": tables,
    }


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


def _regulatory_metric_status(current: Decimal | None, threshold: Decimal, *, lower_is_better: bool = True) -> str:
    if current is None:
        return "unknown"
    if lower_is_better:
        return "pass" if current <= threshold else "review"
    return "pass" if current >= threshold else "review"


def _build_regulatory_limits_table(
    report_date: date,
    zqtz_rows: list[FormalZqtzBalanceFactRow],
    tyw_rows: list[FormalTywBalanceFactRow],
) -> dict[str, Any]:
    bond_assets = [row for row in zqtz_rows if row.position_scope == "asset"]
    interbank_assets = [row for row in tyw_rows if row.position_scope == "asset"]
    interbank_liabilities = [row for row in tyw_rows if row.position_scope == "liability"]
    bond_asset_total = _sum_decimal(bond_assets, lambda row: row.face_value_amount)
    interbank_asset_total = _sum_decimal(interbank_assets, lambda row: row.principal_amount)
    interbank_liability_total = _sum_decimal(interbank_liabilities, lambda row: row.principal_amount)
    asset_denominator = bond_asset_total + interbank_asset_total

    issuer_groups = _group_rows(bond_assets, lambda row: row.issuer_name or "未分类")
    top1_share = _ZERO
    for entries in issuer_groups.values():
        balance_amount = _sum_decimal(entries, lambda row: row.face_value_amount)
        top1_share = max(top1_share, _safe_ratio(balance_amount, bond_asset_total))

    interbank_ratio = _safe_ratio(interbank_liability_total, asset_denominator) if asset_denominator > _ZERO else _ZERO

    usd_amount = _sum_decimal(
        [row for row in bond_assets if str(row.currency_code or "").upper() in {"USD", "美元"}],
        lambda row: row.face_value_amount,
    )
    usd_ratio = _safe_ratio(usd_amount, bond_asset_total) if bond_asset_total > _ZERO else _ZERO

    duration_weights: list[tuple[Decimal, Decimal]] = []
    for row in bond_assets:
        years = _remaining_years(report_date, row.maturity_date)
        duration_weights.append((row.face_value_amount, years))
    for row in interbank_assets:
        years = _remaining_years(report_date, row.maturity_date)
        duration_weights.append((row.principal_amount, years))
    duration_numerator = _ZERO
    duration_denominator = _ZERO
    for weight, years in duration_weights:
        duration_numerator += weight * years
        duration_denominator += weight
    duration_proxy = duration_numerator / duration_denominator if duration_denominator > _ZERO else None

    thresholds = {
        "top1_concentration": Decimal("0.15"),
        "interbank_liability_ratio": Decimal("0.25"),
        "usd_exposure_ratio": Decimal("0.05"),
        "portfolio_modified_duration": Decimal("5.0"),
    }

    rows = [
        {
            "metric_key": "top1_concentration",
            "metric_name": "最大单一发行人占比(债券资产)",
            "current_value": top1_share,
            "threshold_value": thresholds["top1_concentration"],
            "status": _regulatory_metric_status(top1_share, thresholds["top1_concentration"]),
            "calculation_note": "来自正式 fact 资产端按 issuer_name 分组后的最大 face_value 占比。",
        },
        {
            "metric_key": "interbank_liability_ratio",
            "metric_name": "同业负债 / (债券资产+同业资产)",
            "current_value": interbank_ratio,
            "threshold_value": thresholds["interbank_liability_ratio"],
            "status": _regulatory_metric_status(interbank_ratio, thresholds["interbank_liability_ratio"]),
            "calculation_note": "TYW 负债本金合计除以 ZQTZ 资产+TYW 资产面值合计；参考阈值表，非完整监管引擎。",
        },
        {
            "metric_key": "usd_exposure_ratio",
            "metric_name": "美元债券资产占比",
            "current_value": usd_ratio,
            "threshold_value": thresholds["usd_exposure_ratio"],
            "status": _regulatory_metric_status(usd_ratio, thresholds["usd_exposure_ratio"]),
            "calculation_note": "ZQTZ 资产端 USD 口径 face_value 合计 / 债券资产合计。",
        },
        {
            "metric_key": "portfolio_modified_duration",
            "metric_name": "组合剩余期限 proxy(年)",
            "current_value": duration_proxy,
            "threshold_value": thresholds["portfolio_modified_duration"],
            "status": _regulatory_metric_status(duration_proxy, thresholds["portfolio_modified_duration"]),
            "calculation_note": "以剩余年限加权的 proxy，不等同风险张量修正久期；无曲线与期权调整。",
        },
    ]

    return _table(
        "regulatory_limits",
        "监管参考阈值(初版)",
        [
            ("metric_key", "指标键"),
            ("metric_name", "指标名称"),
            ("current_value", "当前值"),
            ("threshold_value", "参考阈值"),
            ("status", "状态"),
            ("calculation_note", "口径说明"),
        ],
        rows,
    )


def _build_overdue_credit_quality_detail_table(zqtz_rows: list[FormalZqtzBalanceFactRow]) -> dict[str, Any]:
    asset_rows = [row for row in zqtz_rows if row.position_scope == "asset"]
    overdue_rows = [
        row
        for row in asset_rows
        if row.overdue_principal_days > 0 or row.overdue_interest_days > 0
    ]
    rows = []
    for row in sorted(overdue_rows, key=lambda r: (r.instrument_code, r.portfolio_name)):
        rows.append(
            {
                "instrument_code": row.instrument_code,
                "instrument_name": row.instrument_name,
                "bond_type": row.bond_type,
                "rating": row.rating,
                "overdue_principal_days": row.overdue_principal_days,
                "overdue_interest_days": row.overdue_interest_days,
                "balance_amount": _to_wanyuan(row.face_value_amount),
            }
        )
    return _table(
        "overdue_credit_quality",
        "逾期与信用质量(明细)",
        [
            ("instrument_code", "代码"),
            ("instrument_name", "名称"),
            ("bond_type", "业务种类"),
            ("rating", "评级"),
            ("overdue_principal_days", "本金逾期天数"),
            ("overdue_interest_days", "利息逾期天数"),
            ("balance_amount", "面值/余额"),
        ],
        rows,
    )


def _build_overdue_credit_quality_rating_table(zqtz_rows: list[FormalZqtzBalanceFactRow]) -> dict[str, Any]:
    asset_rows = [row for row in zqtz_rows if row.position_scope == "asset"]
    overdue_rows = [
        row
        for row in asset_rows
        if row.overdue_principal_days > 0 or row.overdue_interest_days > 0
    ]
    grouped = _group_rows(overdue_rows, lambda row: row.rating or "未评级/空")
    rows = []
    for rating_label, entries in sorted(grouped.items()):
        balance_amount = _sum_decimal(entries, lambda row: row.face_value_amount)
        rows.append(
            {
                "rating": rating_label,
                "row_count": len(entries),
                "balance_amount": _to_wanyuan(balance_amount),
                "weighted_rate_pct": _weighted_average(entries, lambda row: row.face_value_amount, lambda row: row.coupon_rate),
            }
        )
    return _table(
        "overdue_credit_quality_ratings",
        "逾期持仓评级汇总",
        [
            ("rating", "评级"),
            ("row_count", "笔数"),
            ("balance_amount", "面值/余额"),
            ("weighted_rate_pct", "加权利率(%)"),
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


def _build_currency_split_table(zqtz_rows: list[FormalZqtzBalanceFactRow]) -> dict[str, Any]:
    asset_rows = [row for row in zqtz_rows if row.position_scope == "asset"]
    total_balance = _sum_decimal(asset_rows, lambda row: row.face_value_amount)
    grouped = _group_rows(asset_rows, lambda row: row.currency_code or "未知币种")
    rows = []
    for currency_code, entries in sorted(grouped.items()):
        balance_amount = _sum_decimal(entries, lambda row: row.face_value_amount)
        rows.append(
            {
                "currency_code": currency_code,
                "count": len(entries),
                "balance_amount": _to_wanyuan(balance_amount),
                "share": _safe_ratio(balance_amount, total_balance),
                "weighted_rate_pct": _weighted_average(entries, lambda row: row.face_value_amount, lambda row: row.coupon_rate),
                "weighted_term_years": _weighted_average(entries, lambda row: row.face_value_amount, lambda row: _optional_remaining_years(row.report_date, row.maturity_date)),
                "amortized_cost_amount": _to_wanyuan(_sum_decimal(entries, lambda row: row.amortized_cost_amount)),
                "market_value_amount": _to_wanyuan(_sum_decimal(entries, lambda row: row.market_value_amount)),
                "floating_pnl_amount": _to_wanyuan(_sum_decimal(entries, lambda row: row.market_value_amount - row.amortized_cost_amount)),
                "fx_sensitivity_per_0_01": (
                    _to_wanyuan(balance_amount * Decimal("0.01")) if currency_code.upper() in {"USD", "美元"} else _ZERO
                ),
            }
        )
    return _table(
        "currency_split",
        "币种拆分分析",
        [
            ("currency_code", "币种"),
            ("count", "笔数"),
            ("balance_amount", "折算余额"),
            ("share", "占比"),
            ("weighted_rate_pct", "加权利率(%)"),
            ("weighted_term_years", "加权期限(年)"),
            ("amortized_cost_amount", "摊余成本"),
            ("market_value_amount", "公允价值"),
            ("floating_pnl_amount", "浮盈浮亏"),
            ("fx_sensitivity_per_0_01", "汇率敏感性"),
        ],
        rows,
    )


def _build_rating_table(zqtz_rows: list[FormalZqtzBalanceFactRow]) -> dict[str, Any]:
    asset_rows = [row for row in zqtz_rows if row.position_scope == "asset"]
    total_balance = _sum_decimal(asset_rows, lambda row: row.face_value_amount)
    grouped = _group_rows(asset_rows, lambda row: row.rating or "无评级(利率债等)")
    rows = []
    for rating, entries in sorted(grouped.items()):
        balance_amount = _sum_decimal(entries, lambda row: row.face_value_amount)
        rows.append(
            {
                "rating": rating,
                "count": len(entries),
                "balance_amount": _to_wanyuan(balance_amount),
                "share": _safe_ratio(balance_amount, total_balance),
                "weighted_rate_pct": _weighted_average(entries, lambda row: row.face_value_amount, lambda row: row.coupon_rate),
                "weighted_term_years": _weighted_average(entries, lambda row: row.face_value_amount, lambda row: _optional_remaining_years(row.report_date, row.maturity_date)),
            }
        )
    return _table(
        "rating_analysis",
        "信用评级分析",
        [
            ("rating", "评级"),
            ("count", "笔数"),
            ("balance_amount", "面值/余额"),
            ("share", "占比"),
            ("weighted_rate_pct", "加权利率(%)"),
            ("weighted_term_years", "加权期限(年)"),
        ],
        rows,
    )


def _build_rate_distribution_table(
    zqtz_rows: list[FormalZqtzBalanceFactRow],
    tyw_rows: list[FormalTywBalanceFactRow],
) -> dict[str, Any]:
    asset_bonds = [row for row in zqtz_rows if row.position_scope == "asset"]
    asset_interbank = [row for row in tyw_rows if row.position_scope == "asset"]
    liability_interbank = [row for row in tyw_rows if row.position_scope == "liability"]
    rows = []
    for label, lower, upper in _RATE_BUCKETS:
        bond_bucket = [row for row in asset_bonds if _match_bucket(_rate_value(row.coupon_rate), lower, upper)]
        asset_bucket = [row for row in asset_interbank if _match_bucket(_rate_value(row.funding_cost_rate), lower, upper)]
        liability_bucket = [row for row in liability_interbank if _match_bucket(_rate_value(row.funding_cost_rate), lower, upper)]
        rows.append(
            {
                "bucket": label,
                "bond_count": len(bond_bucket),
                "bond_amount": _to_wanyuan(_sum_decimal(bond_bucket, lambda row: row.face_value_amount)),
                "interbank_asset_count": len(asset_bucket),
                "interbank_asset_amount": _to_wanyuan(_sum_decimal(asset_bucket, lambda row: row.principal_amount)),
                "interbank_liability_count": len(liability_bucket),
                "interbank_liability_amount": _to_wanyuan(_sum_decimal(liability_bucket, lambda row: row.principal_amount)),
            }
        )
    return _table(
        "rate_distribution",
        "利率分布分析",
        [
            ("bucket", "利率区间"),
            ("bond_count", "债券笔数"),
            ("bond_amount", "债券面值"),
            ("interbank_asset_count", "同业资产笔数"),
            ("interbank_asset_amount", "同业资产金额"),
            ("interbank_liability_count", "同业负债笔数"),
            ("interbank_liability_amount", "同业负债金额"),
        ],
        rows,
    )


def _build_industry_table(zqtz_rows: list[FormalZqtzBalanceFactRow]) -> dict[str, Any]:
    asset_rows = [row for row in zqtz_rows if row.position_scope == "asset"]
    total_balance = _sum_decimal(asset_rows, lambda row: row.face_value_amount)
    grouped = _group_rows(asset_rows, lambda row: row.industry_name or "未分类")
    rows = []
    for industry_name, entries in sorted(grouped.items()):
        balance_amount = _sum_decimal(entries, lambda row: row.face_value_amount)
        rows.append(
            {
                "industry_name": industry_name,
                "count": len(entries),
                "balance_amount": _to_wanyuan(balance_amount),
                "share": _safe_ratio(balance_amount, total_balance),
                "weighted_rate_pct": _weighted_average(entries, lambda row: row.face_value_amount, lambda row: row.coupon_rate),
            }
        )
    return _table(
        "industry_distribution",
        "行业分布",
        [
            ("industry_name", "行业"),
            ("count", "笔数"),
            ("balance_amount", "面值/余额"),
            ("share", "占比"),
            ("weighted_rate_pct", "加权利率(%)"),
        ],
        rows,
    )


def _build_counterparty_type_table(tyw_rows: list[FormalTywBalanceFactRow]) -> dict[str, Any]:
    grouped = _group_rows(tyw_rows, lambda row: row.core_customer_type or row.counterparty_name or "未分类")
    rows = []
    for counterparty_type, entries in sorted(grouped.items()):
        asset_entries = [row for row in entries if row.position_scope == "asset"]
        liability_entries = [row for row in entries if row.position_scope == "liability"]
        asset_amount = _sum_decimal(asset_entries, lambda row: row.principal_amount)
        liability_amount = _sum_decimal(liability_entries, lambda row: row.principal_amount)
        rows.append(
            {
                "counterparty_type": counterparty_type,
                "asset_count": len(asset_entries),
                "asset_amount": _to_wanyuan(asset_amount),
                "asset_weighted_rate_pct": _weighted_average(asset_entries, lambda row: row.principal_amount, lambda row: row.funding_cost_rate),
                "liability_count": len(liability_entries),
                "liability_amount": _to_wanyuan(liability_amount),
                "liability_weighted_rate_pct": _weighted_average(liability_entries, lambda row: row.principal_amount, lambda row: row.funding_cost_rate),
                "net_position_amount": _to_wanyuan(asset_amount - liability_amount),
            }
        )
    return _table(
        "counterparty_types",
        "对手方类型",
        [
            ("counterparty_type", "对手方类型"),
            ("asset_count", "资产笔数"),
            ("asset_amount", "资产金额"),
            ("asset_weighted_rate_pct", "资产加权利率(%)"),
            ("liability_count", "负债笔数"),
            ("liability_amount", "负债金额"),
            ("liability_weighted_rate_pct", "负债加权利率(%)"),
            ("net_position_amount", "净头寸"),
        ],
        rows,
    )


def _build_campisi_table(zqtz_rows: list[FormalZqtzBalanceFactRow]) -> dict[str, Any]:
    asset_rows = [row for row in zqtz_rows if row.position_scope == "asset"]
    benchmark_rows = [row for row in asset_rows if row.bond_type == _CAMPISI_POLICY_BOND]
    benchmark_rate = _weighted_average(benchmark_rows, lambda row: row.face_value_amount, lambda row: row.coupon_rate) or _ZERO
    total_income = _sum_decimal(asset_rows, lambda row: row.face_value_amount * _rate_value(row.coupon_rate))
    grouped = _group_rows(asset_rows, lambda row: row.bond_type or "未分类")
    rows = []
    for bond_type, entries in sorted(grouped.items()):
        balance_amount = _sum_decimal(entries, lambda row: row.face_value_amount)
        coupon_income = _sum_decimal(entries, lambda row: row.face_value_amount * _rate_value(row.coupon_rate))
        spread_bp = _weighted_average(entries, lambda row: row.face_value_amount, lambda row: row.coupon_rate)
        spread_value = ((spread_bp or _ZERO) - benchmark_rate) * Decimal("100")
        spread_income = _sum_decimal(
            entries,
            lambda row: row.face_value_amount * (_rate_value(row.coupon_rate) - benchmark_rate),
        )
        rows.append(
            {
                "bond_type": bond_type,
                "balance_amount": _to_wanyuan(balance_amount),
                "weighted_rate_pct": _weighted_average(entries, lambda row: row.face_value_amount, lambda row: row.coupon_rate),
                "coupon_income_amount": _to_wanyuan(coupon_income),
                "duration_years": _weighted_average(entries, lambda row: row.face_value_amount, lambda row: _optional_remaining_years(row.report_date, row.maturity_date)),
                "spread_bp": spread_value,
                "spread_income_amount": _to_wanyuan(spread_income),
                "share_of_income": _safe_ratio(coupon_income, total_income),
                "price_return_amount": _to_wanyuan(_sum_decimal(entries, lambda row: row.market_value_amount - row.amortized_cost_amount)),
            }
        )
    return _table(
        "campisi_breakdown",
        "Campisi归因分析",
        [
            ("bond_type", "分析维度"),
            ("balance_amount", "余额"),
            ("weighted_rate_pct", "加权利率(%)"),
            ("coupon_income_amount", "票息收入贡献"),
            ("duration_years", "久期贡献(年)"),
            ("spread_bp", "利差(bp)"),
            ("spread_income_amount", "利差收入贡献"),
            ("share_of_income", "占总收入比重"),
            ("price_return_amount", "浮盈浮亏"),
        ],
        rows,
    )


def _build_cross_analysis_table(zqtz_rows: list[FormalZqtzBalanceFactRow]) -> dict[str, Any]:
    asset_rows = [row for row in zqtz_rows if row.position_scope == "asset"]
    grouped = _group_rows(asset_rows, lambda row: row.bond_type or "未分类")
    rows = []
    for bond_type, entries in sorted(grouped.items()):
        matrix: dict[str, Decimal] = {}
        total_amount = _ZERO
        for row in entries:
            key = row.asset_class or "未分类"
            matrix[key] = matrix.get(key, _ZERO) + _to_wanyuan(row.face_value_amount)
            total_amount += row.face_value_amount
        rows.append({"bond_type": bond_type, **matrix, "All": _to_wanyuan(total_amount)})
    return _table(
        "cross_analysis",
        "交叉分析",
        [("bond_type", "业务种类")],
        rows,
    )


def _build_interest_mode_table(zqtz_rows: list[FormalZqtzBalanceFactRow]) -> dict[str, Any]:
    asset_rows = [row for row in zqtz_rows if row.position_scope == "asset"]
    total_balance = _sum_decimal(asset_rows, lambda row: row.face_value_amount)
    grouped = _group_rows(asset_rows, lambda row: _normalize_interest_mode(row.interest_mode))
    rows = []
    for interest_mode, entries in sorted(grouped.items()):
        balance_amount = _sum_decimal(entries, lambda row: row.face_value_amount)
        rows.append(
            {
                "interest_mode": interest_mode,
                "count": len(entries),
                "balance_amount": _to_wanyuan(balance_amount),
                "share": _safe_ratio(balance_amount, total_balance),
                "weighted_rate_pct": _weighted_average(entries, lambda row: row.face_value_amount, lambda row: row.coupon_rate),
            }
        )
    return _table(
        "interest_modes",
        "计息方式",
        [
            ("interest_mode", "计息方式"),
            ("count", "笔数"),
            ("balance_amount", "面值/余额"),
            ("share", "占比"),
            ("weighted_rate_pct", "加权利率(%)"),
        ],
        rows,
    )


def _build_decision_items_table(
    report_date: date,
    zqtz_rows: list[FormalZqtzBalanceFactRow],
    tyw_rows: list[FormalTywBalanceFactRow],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    maturity_gap = _build_maturity_gap_table(report_date, zqtz_rows, tyw_rows)
    gap_rows = [row for row in maturity_gap["rows"] if _decimal_value(row.get("gap_amount")) != _ZERO]
    if gap_rows:
        largest_gap = max(gap_rows, key=lambda row: abs(_decimal_value(row.get("gap_amount"))))
        rows.append(
            {
                "title": f"Review {largest_gap['bucket']} gap positioning",
                "action_label": "Review gap",
                "severity": _severity_from_gap(_decimal_value(largest_gap.get("gap_amount"))),
                "reason": f"Bucket gap is {largest_gap['gap_amount']} wan yuan.",
                "source_section": "maturity_gap",
                "rule_id": "bal_wb_decision_gap_001",
                "rule_version": "v1",
            }
        )

    rating_table = _build_rating_table(zqtz_rows)
    if rating_table["rows"]:
        top_rating = max(rating_table["rows"], key=lambda row: _decimal_value(row.get("share")))
        top_share = _decimal_value(top_rating.get("share"))
        if top_share >= Decimal("0.60"):
            rows.append(
                {
                    "title": f"Check concentration in {top_rating['rating']}",
                    "action_label": "Review concentration",
                    "severity": "medium" if top_share < Decimal("0.75") else "high",
                    "reason": f"Top rating bucket share reached {top_share:.4f}.",
                    "source_section": "rating_analysis",
                    "rule_id": "bal_wb_decision_rating_001",
                    "rule_version": "v1",
                }
            )

    issuance_table = _build_issuance_business_type_table(zqtz_rows)
    if issuance_table["rows"]:
        leading_issue = max(
            issuance_table["rows"],
            key=lambda row: _decimal_value(row.get("balance_amount")),
        )
        rows.append(
            {
                "title": f"Monitor issuance book: {leading_issue['bond_type']}",
                "action_label": "Review issuance",
                "severity": "medium",
                "reason": f"Issuance bucket balance is {leading_issue['balance_amount']} wan yuan.",
                "source_section": "issuance_business_types",
                "rule_id": "bal_wb_decision_issuance_001",
                "rule_version": "v1",
            }
        )

    return _section(
        "decision_items",
        "决策事项",
        "decision_items",
        [
            ("title", "Title"),
            ("action_label", "Action"),
            ("severity", "Severity"),
            ("reason", "Reason"),
            ("source_section", "Source Section"),
            ("rule_id", "Rule Id"),
            ("rule_version", "Rule Version"),
        ],
        rows,
    )


def _build_event_calendar_table(
    report_date: date,
    zqtz_rows: list[FormalZqtzBalanceFactRow],
    tyw_rows: list[FormalTywBalanceFactRow],
) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    for row in zqtz_rows:
        if row.maturity_date is None or row.maturity_date < report_date:
            continue
        event_type = "issuance_maturity" if row.position_scope == "liability" else "bond_maturity"
        events.append(
            {
                "event_date": row.maturity_date.isoformat(),
                "event_type": event_type,
                "title": f"{row.instrument_code} maturity",
                "source": "internal_governed_schedule",
                "impact_hint": f"{row.position_scope} book / {row.bond_type or 'unknown bond type'}",
                "source_section": "maturity_gap",
            }
        )
    for row in tyw_rows:
        if row.maturity_date is None or row.maturity_date < report_date:
            continue
        event_type = "funding_rollover" if row.position_scope == "liability" else "asset_maturity"
        events.append(
            {
                "event_date": row.maturity_date.isoformat(),
                "event_type": event_type,
                "title": f"{row.position_id} maturity",
                "source": "internal_governed_schedule",
                "impact_hint": f"{row.position_scope} book / {row.product_type or 'unknown product'}",
                "source_section": "maturity_gap",
            }
        )

    events.sort(key=lambda item: (str(item["event_date"]), str(item["title"])))
    return _section(
        "event_calendar",
        "事件日历",
        "event_calendar",
        [
            ("event_date", "Event Date"),
            ("event_type", "Event Type"),
            ("title", "Title"),
            ("source", "Source"),
            ("impact_hint", "Impact Hint"),
            ("source_section", "Source Section"),
        ],
        events[:5],
    )


def _build_risk_alerts_table(
    report_date: date,
    zqtz_rows: list[FormalZqtzBalanceFactRow],
    tyw_rows: list[FormalTywBalanceFactRow],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    maturity_gap = _build_maturity_gap_table(report_date, zqtz_rows, tyw_rows)
    negative_gap_rows = [row for row in maturity_gap["rows"] if _decimal_value(row.get("gap_amount")) < _ZERO]
    if negative_gap_rows:
        tightest_gap = min(negative_gap_rows, key=lambda row: _decimal_value(row.get("gap_amount")))
        rows.append(
            {
                "title": f"Negative gap in {tightest_gap['bucket']}",
                "severity": "high",
                "reason": f"Gap dropped to {tightest_gap['gap_amount']} wan yuan.",
                "source_section": "maturity_gap",
                "rule_id": "bal_wb_risk_gap_001",
                "rule_version": "v1",
            }
        )

    issuance_total = _sum_decimal(
        [row for row in zqtz_rows if row.position_scope == "liability"],
        lambda row: row.face_value_amount,
    )
    if issuance_total > _ZERO:
        rows.append(
            {
                "title": "Issuance liabilities outstanding",
                "severity": "medium",
                "reason": f"Issuance book totals {_to_wanyuan(issuance_total)} wan yuan.",
                "source_section": "issuance_business_types",
                "rule_id": "bal_wb_risk_issuance_001",
                "rule_version": "v1",
            }
        )

    rating_table = _build_rating_table(zqtz_rows)
    if rating_table["rows"]:
        top_rating = max(rating_table["rows"], key=lambda row: _decimal_value(row.get("share")))
        top_share = _decimal_value(top_rating.get("share"))
        if top_share >= Decimal("0.60"):
            rows.append(
                {
                    "title": f"{top_rating['rating']} concentration watch",
                    "severity": "medium" if top_share < Decimal("0.75") else "high",
                    "reason": f"Top rating bucket share reached {top_share:.4f}.",
                    "source_section": "rating_analysis",
                    "rule_id": "bal_wb_risk_rating_001",
                    "rule_version": "v1",
                }
            )

    return _section(
        "risk_alerts",
        "风险预警",
        "risk_alerts",
        [
            ("title", "Title"),
            ("severity", "Severity"),
            ("reason", "Reason"),
            ("source_section", "Source Section"),
            ("rule_id", "Rule Id"),
            ("rule_version", "Rule Version"),
        ],
        rows,
    )


def _group_rows(rows: list[Any], key_fn) -> dict[str, list[Any]]:
    grouped: dict[str, list[Any]] = {}
    for row in rows:
        grouped.setdefault(str(key_fn(row) or "未分类"), []).append(row)
    return grouped


def _sum_decimal(rows: list[Any], value_fn) -> Decimal:
    return sum((Decimal(str(value_fn(row))) for row in rows), _ZERO)


def _weighted_average(rows: list[Any], weight_fn, value_fn) -> Decimal | None:
    numerator = _ZERO
    denominator = _ZERO
    for row in rows:
        value = value_fn(row)
        if value in (None, ""):
            continue
        weight = Decimal(str(weight_fn(row)))
        numerator += weight * Decimal(str(value))
        denominator += weight
    if denominator == _ZERO:
        return None
    return numerator / denominator


def _merged_weighted_average(specs: list[tuple[list[Any], Any, Any]]) -> Decimal | None:
    numerator = _ZERO
    denominator = _ZERO
    for rows, weight_fn, value_fn in specs:
        for row in rows:
            value = value_fn(row)
            if value in (None, ""):
                continue
            weight = Decimal(str(weight_fn(row)))
            numerator += weight * Decimal(str(value))
            denominator += weight
    if denominator == _ZERO:
        return None
    return numerator / denominator


def _remaining_years(report_date: date, maturity_date: date | None) -> Decimal:
    if maturity_date is None:
        return _ZERO
    return Decimal((maturity_date - report_date).days) / Decimal("365")


def _optional_remaining_years(report_date: date, maturity_date: date | None) -> Decimal | None:
    # Workbook 加权期限: calendar days / 365.25 (verified vs 2026-03-01 desktop reference).
    if maturity_date is None:
        return None
    if maturity_date < report_date:
        return None
    days = (maturity_date - report_date).days
    if days <= 0:
        return None
    return Decimal(days) / Decimal("365.25")


def _match_bucket(value: Decimal, lower: Decimal | None, upper: Decimal | None) -> bool:
    if lower is None:
        return value <= (upper or _ZERO)
    if upper is None:
        return value > lower
    return value > lower and value <= upper


def _safe_ratio(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator == _ZERO:
        return _ZERO
    return numerator / denominator


def _spread_bp(asset_rate_pct: Decimal | None, liability_rate_pct: Decimal | None) -> Decimal | None:
    if asset_rate_pct is None or liability_rate_pct is None:
        return None
    return (asset_rate_pct - liability_rate_pct) * Decimal("100")


def _rate_value(value: Decimal | None) -> Decimal:
    return Decimal(str(value)) if value is not None else _ZERO


def _normalize_interest_mode(value: str) -> str:
    style = classify_interest_rate_style(value)
    if style == "fixed":
        return "固定"
    if style == "floating":
        return "浮动"
    return "未分类"


def _to_wanyuan(value: Decimal) -> Decimal:
    return value / _TEN_THOUSAND


def _card(key: str, label: str, value: Decimal, note: str) -> dict[str, Any]:
    return {"key": key, "label": label, "value": value, "note": note}


def _section(
    key: str,
    title: str,
    section_kind: str,
    columns: list[tuple[str, str]],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "key": key,
        "title": title,
        "section_kind": section_kind,
        "columns": [{"key": column_key, "label": label} for column_key, label in columns],
        "rows": rows,
    }


def _table(key: str, title: str, columns: list[tuple[str, str]], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return _section(key, title, "table", columns, rows)


def _decimal_value(value: Any) -> Decimal:
    if value in (None, ""):
        return _ZERO
    return Decimal(str(value))


def _severity_from_gap(gap_value: Decimal) -> str:
    absolute_gap = abs(gap_value)
    if absolute_gap >= Decimal("20"):
        return "high"
    if absolute_gap >= Decimal("5"):
        return "medium"
    return "low"


def _month_ladder(report_date: date, months: int) -> list[str]:
    start_month_index = report_date.year * 12 + (report_date.month - 1)
    return [_month_key_from_index(start_month_index + offset) for offset in range(months)]


def _month_key(value: date | None) -> str:
    if value is None:
        return ""
    return f"{value.year:04d}-{value.month:02d}"


def _month_key_from_index(month_index: int) -> str:
    year = month_index // 12
    month = (month_index % 12) + 1
    return f"{year:04d}-{month:02d}"
