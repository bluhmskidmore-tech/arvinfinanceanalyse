"""Analysis table builders for balance analysis workbook."""
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
    _RATE_BUCKETS,
    _CAMPISI_POLICY_BOND,
    _group_rows,
    _sum_decimal,
    _weighted_average,
    _optional_remaining_years,
    _match_bucket,
    _safe_ratio,
    _rate_value,
    _normalize_interest_mode,
    _to_wanyuan,
    _decimal_value,
    _severity_from_gap,
    _section,
    _table,
)
from backend.app.core_finance.balance_workbook._bond_tables import (
    _build_maturity_gap_table,
    _build_issuance_business_type_table,
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
    total_income = _sum_decimal(asset_rows, lambda row: row.face_value_amount * _rate_value(row.coupon_rate) / Decimal("100"))
    grouped = _group_rows(asset_rows, lambda row: row.bond_type or "未分类")
    rows = []
    for bond_type, entries in sorted(grouped.items()):
        balance_amount = _sum_decimal(entries, lambda row: row.face_value_amount)
        coupon_income = _sum_decimal(entries, lambda row: row.face_value_amount * _rate_value(row.coupon_rate) / Decimal("100"))
        spread_bp = _weighted_average(entries, lambda row: row.face_value_amount, lambda row: row.coupon_rate)
        spread_value = ((spread_bp or _ZERO) - benchmark_rate) * Decimal("100")
        spread_income = _sum_decimal(
            entries,
            lambda row: row.face_value_amount * (((_rate_value(row.coupon_rate) - benchmark_rate) / Decimal("100"))),
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
