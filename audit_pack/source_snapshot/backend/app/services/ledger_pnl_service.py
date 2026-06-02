"""
Ledger 口径损益汇总服务 — 按科目前缀聚合 monthly_pnl / ending_balance。

数据源：product_category_source_service 解析的 CanonicalFactRow（来自总账对账 Excel）。
用途：对账快照（reconciliation）、dashboard KPI、负债分析 NIM 计算。

口径说明：
- 514/516/517 = 利息收入 + 公允价值变动 + 投资收益（核心损益三科目）
- 5* = 全量损益科目（用于 completeness check）
- 1* = 资产科目，2* = 负债科目
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from backend.app.core_finance.config.classification_rules import (
    LEDGER_ASSET_ACCOUNT_PREFIXES,
    LEDGER_LIABILITY_ACCOUNT_PREFIXES,
    LEDGER_PNL_ACCOUNT_PREFIXES,
)
from backend.app.core_finance.decimal_utils import fmt_money, to_decimal
from backend.app.services.formal_result_runtime import build_result_envelope
from backend.app.services.product_category_source_service import (
    discover_source_pairs,
    build_canonical_facts,
)

CACHE_VERSION = "cv_ledger_pnl_v1"
RULE_VERSION = "rv_ledger_pnl_v1"


def _load_facts_for_date(
    source_dir: str,
    report_date: date,
) -> tuple[list[Any], str]:
    """从 Excel 源加载指定日期的 CanonicalFactRow。"""
    pairs = discover_source_pairs(Path(source_dir))
    target_key = f"{report_date.year}{report_date.month:02d}"
    for pair in pairs:
        if pair.month_key == target_key:
            facts = build_canonical_facts(pair)
            return facts, pair.source_version
    return [], "sv_ledger_pnl_empty"


def _sum_by_prefixes(
    facts: list[Any],
    prefixes: tuple[str, ...],
    field: str,
    currency: str | None = None,
) -> Decimal:
    """按科目前缀聚合指定字段（ending_balance / monthly_pnl / daily_avg_balance）。"""
    total = Decimal("0")
    for row in facts:
        if currency and row.currency != currency:
            continue
        code = row.account_code.strip()
        matched = any(code.startswith(p) for p in prefixes)
        if matched:
            total += to_decimal(getattr(row, field, None))
    return total


def get_available_dates(source_dir: str) -> dict[str, Any]:
    """获取可用的报告日期列表。"""
    pairs = discover_source_pairs(Path(source_dir))
    dates = sorted({p.report_date.isoformat() for p in pairs}, reverse=True)
    return {"dates": dates}


def get_ledger_pnl_by_date(
    source_dir: str,
    report_date: date,
    currency: str | None = None,
) -> dict[str, Any]:
    """获取指定日期的 Ledger 科目级明细 + 汇总。"""
    facts, source_version = _load_facts_for_date(source_dir, report_date)
    if not facts:
        return {
            "report_date": report_date.isoformat(),
            "items": [],
            "summary": {
                "total_pnl_cnx": fmt_money(Decimal("0")),
                "total_pnl_cny": fmt_money(Decimal("0")),
                "total_pnl": fmt_money(Decimal("0")),
                "count": 0,
            },
        }

    filtered = facts
    if currency:
        filtered = [f for f in facts if f.currency == currency]

    total_pnl_cnx = Decimal("0")
    total_pnl_cny = Decimal("0")
    items: list[dict[str, Any]] = []

    for row in filtered:
        pnl = to_decimal(row.monthly_pnl)
        if row.currency == "CNX":
            total_pnl_cnx += pnl
        elif row.currency == "CNY":
            total_pnl_cny += pnl

        items.append({
            "account_code": row.account_code,
            "account_name": row.account_name,
            "currency": row.currency,
            "beginning_balance": fmt_money(to_decimal(row.beginning_balance)),
            "ending_balance": fmt_money(to_decimal(row.ending_balance)),
            "monthly_pnl": fmt_money(pnl),
            "daily_avg_balance": fmt_money(to_decimal(row.daily_avg_balance)),
            "days_in_period": row.days_in_period,
        })

    items.sort(key=lambda x: abs(to_decimal(x["monthly_pnl"]["yuan"])), reverse=True)

    return {
        "report_date": report_date.isoformat(),
        "items": items,
        "summary": {
            "total_pnl_cnx": fmt_money(total_pnl_cnx),
            "total_pnl_cny": fmt_money(total_pnl_cny),
            "total_pnl": fmt_money(total_pnl_cnx + total_pnl_cny),
            "count": len(items),
        },
    }


def get_ledger_pnl_summary(
    source_dir: str,
    report_date: date,
    currency: str | None = None,
) -> dict[str, Any]:
    """
    Ledger 口径汇总 — 对账核心接口。

    返回：
    - 按前缀聚合的资产/负债/净资产（ending_balance）
    - 核心损益（514/516/517 monthly_pnl）
    - 全量损益（5* monthly_pnl，用于 completeness check）
    - 按币种/按科目的明细汇总
    """
    facts, source_version = _load_facts_for_date(source_dir, report_date)
    if not facts:
        return _empty_summary(report_date, source_version)

    filtered = facts
    if currency:
        filtered = [f for f in facts if f.currency == currency]

    ledger_assets = _sum_by_prefixes(filtered, LEDGER_ASSET_ACCOUNT_PREFIXES, "ending_balance")
    ledger_liabilities = _sum_by_prefixes(filtered, LEDGER_LIABILITY_ACCOUNT_PREFIXES, "ending_balance")
    ledger_net = ledger_assets - ledger_liabilities

    pnl_core = _sum_by_prefixes(filtered, LEDGER_PNL_ACCOUNT_PREFIXES, "monthly_pnl")
    pnl_all = _sum_by_prefixes(filtered, ("5",), "monthly_pnl")

    # 按币种汇总
    by_currency: dict[str, Decimal] = {}
    by_account: dict[str, dict[str, Any]] = {}
    for row in filtered:
        pnl = to_decimal(row.monthly_pnl)
        curr = row.currency
        by_currency[curr] = by_currency.get(curr, Decimal("0")) + pnl

        code = row.account_code
        if code not in by_account:
            by_account[code] = {
                "account_code": code,
                "account_name": row.account_name,
                "total_pnl": Decimal("0"),
                "count": 0,
            }
        by_account[code]["total_pnl"] += pnl
        by_account[code]["count"] += 1

    return {
        "report_date": report_date.isoformat(),
        "source_version": source_version,
        "ledger_total_assets": fmt_money(ledger_assets),
        "ledger_total_liabilities": fmt_money(ledger_liabilities),
        "ledger_net_assets": fmt_money(ledger_net),
        "ledger_monthly_pnl_core": fmt_money(pnl_core),
        "ledger_monthly_pnl_all": fmt_money(pnl_all),
        "by_currency": [
            {"currency": k, "total_pnl": fmt_money(v)}
            for k, v in sorted(by_currency.items())
        ],
        "by_account": [
            {
                "account_code": v["account_code"],
                "account_name": v["account_name"],
                "total_pnl": fmt_money(v["total_pnl"]),
                "count": v["count"],
            }
            for v in sorted(
                by_account.values(),
                key=lambda x: abs(x["total_pnl"]),
                reverse=True,
            )
        ],
    }


def _empty_summary(report_date: date, source_version: str) -> dict[str, Any]:
    zero = fmt_money(Decimal("0"))
    return {
        "report_date": report_date.isoformat(),
        "source_version": source_version,
        "ledger_total_assets": zero,
        "ledger_total_liabilities": zero,
        "ledger_net_assets": zero,
        "ledger_monthly_pnl_core": zero,
        "ledger_monthly_pnl_all": zero,
        "by_currency": [],
        "by_account": [],
    }


def ledger_pnl_dates_envelope(source_dir: str) -> dict[str, Any]:
    return build_result_envelope(
        basis="formal",
        trace_id="tr_ledger_pnl_dates",
        result_kind="ledger_pnl.dates",
        cache_version=CACHE_VERSION,
        source_version="sv_ledger_pnl_dates",
        rule_version=RULE_VERSION,
        quality_flag="ok",
        vendor_version="vv_none",
        result_payload=get_available_dates(source_dir),
    )


def ledger_pnl_data_envelope(
    source_dir: str,
    report_date: str,
    currency: str | None = None,
) -> dict[str, Any]:
    from datetime import datetime
    rd = datetime.strptime(report_date.strip(), "%Y-%m-%d").date()
    payload = get_ledger_pnl_by_date(source_dir, rd, currency)
    return build_result_envelope(
        basis="formal",
        trace_id="tr_ledger_pnl_data",
        result_kind="ledger_pnl.data",
        cache_version=CACHE_VERSION,
        source_version="sv_ledger_pnl_data",
        rule_version=RULE_VERSION,
        quality_flag="ok",
        vendor_version="vv_none",
        result_payload=payload,
    )


def ledger_pnl_summary_envelope(
    source_dir: str,
    report_date: str,
    currency: str | None = None,
) -> dict[str, Any]:
    from datetime import datetime
    rd = datetime.strptime(report_date.strip(), "%Y-%m-%d").date()
    payload = get_ledger_pnl_summary(source_dir, rd, currency)
    return build_result_envelope(
        basis="formal",
        trace_id="tr_ledger_pnl_summary",
        result_kind="ledger_pnl.summary",
        cache_version=CACHE_VERSION,
        source_version=payload.get("source_version", "sv_ledger_pnl_summary"),
        rule_version=RULE_VERSION,
        quality_flag="ok",
        vendor_version="vv_none",
        result_payload=payload,
    )
