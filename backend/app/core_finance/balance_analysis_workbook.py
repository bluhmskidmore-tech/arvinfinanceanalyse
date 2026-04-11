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
_CAMPISI_TREASURY_TYPES = frozenset({"政策性金融债", "国债", "地方政府债", "凭证式国债"})
_TEN_THOUSAND = Decimal("10000")


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
        _build_issuance_business_type_table(zqtz_rows),
        _build_currency_split_table(zqtz_currency_rows),
        _build_rating_table(zqtz_rows),
        _build_rate_distribution_table(zqtz_rows, tyw_rows),
        _build_industry_table(zqtz_rows),
        _build_counterparty_type_table(tyw_rows),
        _build_campisi_table(zqtz_rows),
        _build_cross_analysis_table(zqtz_rows),
        _build_interest_mode_table(zqtz_rows),
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
                "weighted_term_years": _weighted_average(entries, lambda row: row.face_value_amount, lambda row: _remaining_years(row.report_date, row.maturity_date)),
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
        bucket_assets = [row for row in asset_interbank if _match_bucket(_remaining_years(report_date, row.maturity_date), lower, upper)]
        bucket_liabilities = [row for row in liability_interbank if _match_bucket(_remaining_years(report_date, row.maturity_date), lower, upper)]
        bond_asset_amount = _sum_decimal(bucket_bonds, lambda row: row.face_value_amount)
        interbank_asset_amount = _sum_decimal(bucket_assets, lambda row: row.principal_amount)
        interbank_liability_amount = _sum_decimal(bucket_liabilities, lambda row: row.principal_amount)
        asset_total = bond_asset_amount + interbank_asset_amount
        gap = asset_total - interbank_liability_amount
        cumulative_gap += gap
        rows.append(
            {
                "bucket": label,
                "bond_assets_amount": _to_wanyuan(bond_asset_amount),
                "interbank_assets_amount": _to_wanyuan(interbank_asset_amount),
                "asset_total_amount": _to_wanyuan(asset_total),
                "interbank_liabilities_amount": _to_wanyuan(interbank_liability_amount),
                "gap_amount": _to_wanyuan(gap),
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
            ("interbank_liabilities_amount", "同业负债"),
            ("gap_amount", "缺口"),
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
                "weighted_term_years": _weighted_average(entries, lambda row: row.face_value_amount, lambda row: _remaining_years(row.report_date, row.maturity_date)),
                "interest_mode_fixed_count": sum(1 for row in entries if _normalize_interest_mode(row.interest_mode) == "固定"),
                "interest_mode_floating_count": sum(1 for row in entries if _normalize_interest_mode(row.interest_mode) != "固定"),
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
                "weighted_term_years": _weighted_average(entries, lambda row: row.face_value_amount, lambda row: _remaining_years(row.report_date, row.maturity_date)),
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
                "weighted_term_years": _weighted_average(entries, lambda row: row.face_value_amount, lambda row: _remaining_years(row.report_date, row.maturity_date)),
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
    benchmark_rows = [row for row in asset_rows if row.bond_type in _CAMPISI_TREASURY_TYPES]
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
                "duration_years": _weighted_average(entries, lambda row: row.face_value_amount, lambda row: _remaining_years(row.report_date, row.maturity_date)),
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
    normalized = str(value or "").strip()
    return normalized or "未分类"


def _to_wanyuan(value: Decimal) -> Decimal:
    return value / _TEN_THOUSAND


def _card(key: str, label: str, value: Decimal, note: str) -> dict[str, Any]:
    return {"key": key, "label": label, "value": value, "note": note}


def _table(key: str, title: str, columns: list[tuple[str, str]], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "key": key,
        "title": title,
        "columns": [{"key": column_key, "label": label} for column_key, label in columns],
        "rows": rows,
    }
