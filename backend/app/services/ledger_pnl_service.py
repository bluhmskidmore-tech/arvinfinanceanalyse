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

from calendar import monthrange
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from backend.app.core_finance.config.classification_rules import (
    LEDGER_PNL_ACCOUNT_PREFIXES,
)
from backend.app.core_finance.decimal_utils import fmt_money, to_decimal
from backend.app.core_finance.formal_financial_indicator_rules import (
    build_formal_financial_indicator_rule_checks,
)
from backend.app.core_finance.formal_financial_indicators import (
    build_formal_financial_indicator_contract,
)
from backend.app.core_finance.ledger_pnl_analysis import (
    build_ledger_pnl_account_detail,
    build_ledger_pnl_analysis,
)
from backend.app.schemas.ledger_pnl_analysis import (
    LedgerPnlAccountDetailEnvelope,
    LedgerPnlAnalysisEnvelope,
)
from backend.app.services.formal_result_runtime import build_result_envelope
from backend.app.services.product_category_source_service import (
    build_canonical_facts,
    discover_source_pairs,
)

CACHE_VERSION = "cv_ledger_pnl_v2"
RULE_VERSION = "rv_ledger_pnl_v2"
FINANCIAL_INDICATOR_CONTRACT_CACHE_VERSION = "cv_ledger_pnl_financial_indicator_contract_v1"
FINANCIAL_INDICATOR_RULE_CHECKS_CACHE_VERSION = "cv_ledger_pnl_financial_indicator_rule_checks_v1"
ANALYSIS_CACHE_VERSION = "cv_ledger_pnl_analysis_v1"
ANALYSIS_RULE_VERSION = "rv_ledger_pnl_analysis_v1"
ACCOUNT_DETAIL_CACHE_VERSION = "cv_ledger_pnl_account_detail_v1"
ACCOUNT_DETAIL_RULE_VERSION = "rv_ledger_pnl_account_detail_v1"
SUPPORTED_CURRENCIES = {"CNX", "CNY"}
DEFAULT_CURRENCY_BASIS = "CNX"
CURRENCY_BASIS_NOTE = "CNX=综本；CNY=人民币账"
LEDGER_PNL_TOTAL_ACCOUNT_PREFIXES = ("5",)


class LedgerPnlRequestError(ValueError):
    """A caller-correctable Ledger PnL request error."""


def _quality_for_evidence(evidence_rows: int | None) -> Literal["ok", "warning"]:
    return "ok" if evidence_rows and evidence_rows > 0 else "warning"


def _ledger_pnl_cache_key(
    result_kind: str,
    report_date: str | None = None,
    currency: str | None = None,
) -> str:
    parts = [result_kind]
    if report_date:
        parts.append(report_date)
    parts.append(_normalize_currency_basis(currency))
    return ":".join(parts)


def _normalize_currency_basis(currency: str | None) -> str:
    normalized = DEFAULT_CURRENCY_BASIS if currency is None else currency.strip().upper()
    if normalized not in SUPPORTED_CURRENCIES:
        raise LedgerPnlRequestError(
            f"Unsupported ledger currency basis: {currency!r}. Expected CNX or CNY."
        )
    return normalized


def _normalize_pnl_account_code(account_code: str) -> str:
    normalized = account_code.strip()
    if (
        len(normalized) > 32
        or len(normalized) < 2
        or not normalized.startswith("5")
        or not normalized[1:].isdigit()
    ):
        raise LedgerPnlRequestError(
            f"Invalid ledger PnL account_code: {account_code!r}. Expected ^5[0-9]+$ with max length 32."
        )
    return normalized


def _empty_ledger_next_drill(report_date: str | None = None, currency: str | None = None) -> list[dict[str, str]]:
    checks = [
        {
            "label": "核对总账报告日",
            "detail": "确认请求报告日是否存在于 /api/ledger-pnl/dates 返回列表。",
        },
        {
            "label": "核对总账源文件",
            "detail": "检查 product_category_source_dir 是否包含对应 YYYYMM 的总账对账工作簿。",
        },
    ]
    if currency:
        checks.append({
            "label": "核对币种筛选",
            "detail": f"当前币种筛选为 {currency}，请确认该报告日下是否存在对应币种分录。",
        })
    if report_date:
        checks.append({
            "label": "核对明细证据",
            "detail": f"补查 {report_date} 的 canonical 总账事实行，避免把无证据结果解释为真实 0。",
        })
    return checks


def _load_facts_for_date(
    source_dir: str,
    report_date: date,
) -> tuple[list[Any], str]:
    """从 Excel 源加载指定日期的 CanonicalFactRow。"""
    pairs = discover_source_pairs(Path(source_dir))
    target_key = f"{report_date.year}{report_date.month:02d}"
    for pair in pairs:
        if pair.month_key == target_key:
            if pair.report_date != report_date:
                raise LedgerPnlRequestError(
                    f"Requested report_date {report_date.isoformat()} does not match "
                    f"source report_date {pair.report_date.isoformat()} for {target_key}."
                )
            facts = build_canonical_facts(pair)
            return facts, pair.source_version
    return [], "sv_ledger_pnl_empty"


def _load_previous_facts(
    source_dir: str,
    report_date: date,
) -> tuple[date | None, str | None, list[Any]]:
    pairs = [
        pair
        for pair in discover_source_pairs(Path(source_dir))
        if pair.report_date < report_date
    ]
    if not pairs:
        return None, None, []
    pair = max(pairs, key=lambda item: item.report_date)
    return pair.report_date, pair.source_version, build_canonical_facts(pair)


def _require_exact_month_end(report_date: date) -> None:
    expected_day = monthrange(report_date.year, report_date.month)[1]
    if report_date.day != expected_day:
        raise LedgerPnlRequestError(
            f"Requested report_date {report_date.isoformat()} must be an exact calendar month-end."
        )


def _serialize_analysis_money(value: Any) -> Any:
    if isinstance(value, Decimal):
        money = fmt_money(value)
        if Decimal(money["yi"]) == Decimal("0"):
            money["yi"] = "0.00"
        return money
    if isinstance(value, list):
        return [_serialize_analysis_money(item) for item in value]
    if isinstance(value, dict):
        return {
            key: _serialize_analysis_money(item)
            for key, item in value.items()
        }
    return value


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


def _supported_currency_facts(facts: list[Any]) -> list[Any]:
    return [row for row in facts if row.currency in SUPPORTED_CURRENCIES]


def _pnl_total_facts(facts: list[Any]) -> list[Any]:
    return [
        row for row in facts
        if str(row.account_code).strip().startswith(LEDGER_PNL_TOTAL_ACCOUNT_PREFIXES)
    ]


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
    currency_basis = _normalize_currency_basis(currency)
    facts, source_version = _load_facts_for_date(source_dir, report_date)
    if not facts:
        return {
            "data_status": "no_data",
            "report_date": report_date.isoformat(),
            "source_version": source_version,
            "items": [],
            "summary": {
                "total_pnl_cnx": fmt_money(Decimal("0")),
                "total_pnl_cny": fmt_money(Decimal("0")),
                "total_pnl": fmt_money(Decimal("0")),
                "count": 0,
            },
        }

    filtered = [
        row for row in _supported_currency_facts(facts)
        if row.currency == currency_basis
    ]
    total_pnl = _sum_by_prefixes(
        filtered,
        LEDGER_PNL_TOTAL_ACCOUNT_PREFIXES,
        "monthly_pnl",
    )
    total_pnl_cnx = total_pnl if currency_basis == "CNX" else Decimal("0")
    total_pnl_cny = total_pnl if currency_basis == "CNY" else Decimal("0")
    items: list[dict[str, Any]] = []

    for row in filtered:
        pnl = to_decimal(row.monthly_pnl)
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
        "data_status": "ready" if items else "no_data",
        "report_date": report_date.isoformat(),
        "source_version": source_version,
        "items": items,
        "summary": {
            "total_pnl_cnx": fmt_money(total_pnl_cnx),
            "total_pnl_cny": fmt_money(total_pnl_cny),
            "total_pnl": fmt_money(total_pnl),
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
    currency_basis = _normalize_currency_basis(currency)
    facts, source_version = _load_facts_for_date(source_dir, report_date)
    if not facts:
        return _empty_summary(report_date, source_version)

    filtered = [
        row for row in _supported_currency_facts(facts)
        if row.currency == currency_basis
    ]
    if not filtered:
        return _empty_summary(report_date, source_version)

    ledger_assets = _sum_by_prefixes(filtered, ("1",), "ending_balance")
    ledger_liabilities = abs(_sum_by_prefixes(filtered, ("2",), "ending_balance"))
    ledger_net = ledger_assets - ledger_liabilities

    pnl_core = _sum_by_prefixes(filtered, LEDGER_PNL_ACCOUNT_PREFIXES, "monthly_pnl")
    pnl_all = _sum_by_prefixes(filtered, LEDGER_PNL_TOTAL_ACCOUNT_PREFIXES, "monthly_pnl")
    pnl_filtered = _pnl_total_facts(filtered)

    # 按币种汇总
    by_currency: dict[str, Decimal] = {}
    by_account: dict[str, dict[str, Any]] = {}
    for row in pnl_filtered:
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
        "data_status": "ready",
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
        "data_status": "no_data",
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
    payload = get_available_dates(source_dir)
    evidence_rows = len(payload.get("dates", []))
    return build_result_envelope(
        basis="ledger",
        trace_id="tr_ledger_pnl_dates",
        result_kind="ledger_pnl.dates",
        cache_version=CACHE_VERSION,
        source_version="sv_ledger_pnl_dates",
        rule_version=RULE_VERSION,
        quality_flag=_quality_for_evidence(evidence_rows),
        vendor_version="vv_none",
        result_payload=payload,
        tables_used=[
            "qdb_gl_ledger_reconciliation_workbook",
            "qdb_gl_average_balance_workbook",
        ],
        evidence_rows=evidence_rows,
        next_drill=[] if evidence_rows > 0 else _empty_ledger_next_drill(),
    )


def ledger_pnl_data_envelope(
    source_dir: str,
    report_date: str,
    currency: str | None = None,
) -> dict[str, Any]:
    from datetime import datetime
    currency_basis = _normalize_currency_basis(currency)
    rd = datetime.strptime(report_date.strip(), "%Y-%m-%d").date()
    payload = get_ledger_pnl_by_date(source_dir, rd, currency_basis)
    items = payload.get("items")
    evidence_rows = len(items) if isinstance(items, list) else None
    return build_result_envelope(
        basis="ledger",
        trace_id="tr_ledger_pnl_data",
        result_kind="ledger_pnl.data",
        cache_version=CACHE_VERSION,
        cache_key=_ledger_pnl_cache_key(
            "ledger_pnl.data",
            payload["report_date"],
            currency_basis,
        ),
        source_version=payload.get("source_version", "sv_ledger_pnl_data"),
        rule_version=RULE_VERSION,
        quality_flag=_quality_for_evidence(evidence_rows),
        vendor_version="vv_none",
        result_payload=payload,
        requested_report_date=report_date.strip(),
        resolved_report_date=payload["report_date"],
        as_of_date=payload["report_date"],
        date_basis="ledger_report_date",
        filters_applied={
            "report_date": payload["report_date"],
            "currency": currency_basis,
            "currency_basis": currency_basis,
            "currency_basis_note": CURRENCY_BASIS_NOTE,
        },
        tables_used=[
            "qdb_gl_ledger_reconciliation_workbook",
            "qdb_gl_average_balance_workbook",
        ],
        evidence_rows=evidence_rows,
        next_drill=[] if evidence_rows and evidence_rows > 0 else _empty_ledger_next_drill(
            payload["report_date"],
            currency_basis,
        ),
    )


def ledger_pnl_summary_envelope(
    source_dir: str,
    report_date: str,
    currency: str | None = None,
) -> dict[str, Any]:
    from datetime import datetime
    currency_basis = _normalize_currency_basis(currency)
    rd = datetime.strptime(report_date.strip(), "%Y-%m-%d").date()
    payload = get_ledger_pnl_summary(source_dir, rd, currency_basis)
    by_account = payload.get("by_account")
    evidence_rows = (
        sum(int(item.get("count") or 0) for item in by_account if isinstance(item, dict))
        if isinstance(by_account, list)
        else None
    )
    return build_result_envelope(
        basis="ledger",
        trace_id="tr_ledger_pnl_summary",
        result_kind="ledger_pnl.summary",
        cache_version=CACHE_VERSION,
        cache_key=_ledger_pnl_cache_key(
            "ledger_pnl.summary",
            payload["report_date"],
            currency_basis,
        ),
        source_version=payload.get("source_version", "sv_ledger_pnl_summary"),
        rule_version=RULE_VERSION,
        quality_flag=_quality_for_evidence(evidence_rows),
        vendor_version="vv_none",
        result_payload=payload,
        requested_report_date=report_date.strip(),
        resolved_report_date=payload["report_date"],
        as_of_date=payload["report_date"],
        date_basis="ledger_report_date",
        filters_applied={
            "report_date": payload["report_date"],
            "currency": currency_basis,
            "currency_basis": currency_basis,
            "currency_basis_note": CURRENCY_BASIS_NOTE,
        },
        tables_used=[
            "qdb_gl_ledger_reconciliation_workbook",
            "qdb_gl_average_balance_workbook",
        ],
        evidence_rows=evidence_rows,
        next_drill=[] if evidence_rows and evidence_rows > 0 else _empty_ledger_next_drill(
            payload["report_date"],
            currency_basis,
        ),
    )


def ledger_pnl_analysis_envelope(
    source_dir: str,
    report_date: str,
    currency: str | None = None,
) -> dict[str, Any]:
    from datetime import datetime

    currency_basis = _normalize_currency_basis(currency)
    rd = datetime.strptime(report_date.strip(), "%Y-%m-%d").date()
    _require_exact_month_end(rd)
    current_facts, source_version = _load_facts_for_date(source_dir, rd)
    previous_date, previous_source_version, previous_facts = _load_previous_facts(
        source_dir,
        rd,
    )
    raw_payload = build_ledger_pnl_analysis(
        report_date=rd,
        source_version=source_version,
        currency_basis=currency_basis,
        current_facts=current_facts,
        previous_report_date=previous_date,
        previous_source_version=previous_source_version,
        previous_facts=previous_facts,
    )
    payload = _serialize_analysis_money(raw_payload)
    evidence_rows = sum(
        1
        for row in current_facts
        if row.currency == currency_basis
        and str(row.account_code).strip().startswith(LEDGER_PNL_TOTAL_ACCOUNT_PREFIXES)
    )
    envelope = build_result_envelope(
        basis="ledger",
        trace_id="tr_ledger_pnl_analysis",
        result_kind="ledger_pnl.analysis",
        cache_version=ANALYSIS_CACHE_VERSION,
        cache_key=_ledger_pnl_cache_key(
            "ledger_pnl.analysis",
            rd.isoformat(),
            currency_basis,
        ),
        source_version=source_version,
        rule_version=ANALYSIS_RULE_VERSION,
        quality_flag=_quality_for_evidence(evidence_rows),
        vendor_version="vv_none",
        result_payload=payload,
        requested_report_date=report_date.strip(),
        resolved_report_date=rd.isoformat(),
        as_of_date=rd.isoformat(),
        date_basis="ledger_report_date",
        filters_applied={
            "report_date": rd.isoformat(),
            "currency": currency_basis,
            "currency_basis": currency_basis,
            "currency_basis_note": CURRENCY_BASIS_NOTE,
        },
        tables_used=[
            "qdb_gl_ledger_reconciliation_workbook",
            "qdb_gl_average_balance_workbook",
        ],
        evidence_rows=evidence_rows,
        next_drill=[] if evidence_rows > 0 else _empty_ledger_next_drill(
            rd.isoformat(),
            currency_basis,
        ),
    )
    return LedgerPnlAnalysisEnvelope.model_validate(envelope).model_dump(mode="json")


def ledger_pnl_account_detail_envelope(
    source_dir: str,
    report_date: str,
    account_code: str,
    currency: str | None = None,
) -> dict[str, Any]:
    from datetime import datetime

    currency_basis = _normalize_currency_basis(currency)
    normalized_account_code = _normalize_pnl_account_code(account_code)
    rd = datetime.strptime(report_date.strip(), "%Y-%m-%d").date()
    _require_exact_month_end(rd)
    current_facts, source_version = _load_facts_for_date(source_dir, rd)
    previous_date, previous_source_version, previous_facts = _load_previous_facts(
        source_dir,
        rd,
    )
    raw_payload = build_ledger_pnl_account_detail(
        report_date=rd,
        source_version=source_version,
        account_code=normalized_account_code,
        currency_basis=currency_basis,
        current_facts=current_facts,
        previous_report_date=previous_date,
        previous_source_version=previous_source_version,
        previous_facts=previous_facts,
    )
    payload = _serialize_analysis_money(raw_payload)
    current_evidence_rows = int(
        raw_payload["period_comparison"]["current_evidence_rows"]
    )
    envelope = build_result_envelope(
        basis="ledger",
        trace_id="tr_ledger_pnl_account_detail",
        result_kind="ledger_pnl.account_detail",
        cache_version=ACCOUNT_DETAIL_CACHE_VERSION,
        cache_key=(
            f"ledger_pnl.account_detail:{rd.isoformat()}:"
            f"{currency_basis}:{normalized_account_code}"
        ),
        source_version=source_version,
        rule_version=ACCOUNT_DETAIL_RULE_VERSION,
        quality_flag=_quality_for_evidence(current_evidence_rows),
        vendor_version="vv_none",
        result_payload=payload,
        requested_report_date=report_date.strip(),
        resolved_report_date=rd.isoformat(),
        as_of_date=rd.isoformat(),
        date_basis="ledger_report_date",
        filters_applied={
            "report_date": rd.isoformat(),
            "account_code": normalized_account_code,
            "currency": currency_basis,
            "currency_basis": currency_basis,
            "currency_basis_note": CURRENCY_BASIS_NOTE,
        },
        tables_used=[
            "qdb_gl_ledger_reconciliation_workbook",
            "qdb_gl_average_balance_workbook",
        ],
        evidence_rows=current_evidence_rows,
        next_drill=(
            []
            if current_evidence_rows > 0
            else _empty_ledger_next_drill(rd.isoformat(), currency_basis)
        ),
    )
    return LedgerPnlAccountDetailEnvelope.model_validate(envelope).model_dump(mode="json")


def ledger_pnl_formal_financial_indicator_contract_envelope(
    *,
    report_month: str,
) -> dict[str, Any]:
    payload = build_formal_financial_indicator_contract(report_month=report_month)
    return build_result_envelope(
        basis="ledger",
        trace_id=f"tr_ledger_pnl_financial_indicator_contract_{report_month}",
        result_kind="ledger_pnl.formal_financial_indicator_source_contract",
        cache_version=FINANCIAL_INDICATOR_CONTRACT_CACHE_VERSION,
        source_version=str(payload["source_version"]),
        rule_version=str(payload["rule_version"]),
        quality_flag="warning",
        vendor_version="vv_none",
        result_payload=payload,
        requested_report_date=report_month,
        resolved_report_date=str(payload["report_date"]),
        as_of_date=str(payload["report_date"]),
        date_basis="report_month_end",
        evidence_rows=len(payload["metrics"]),
    )


def ledger_pnl_formal_indicator_rule_checks_envelope(
    *,
    report_month: str,
) -> dict[str, Any]:
    payload = build_formal_financial_indicator_rule_checks(report_month=report_month)
    evidence_rows = int(payload.get("summary", {}).get("total_checks") or 0)
    return build_result_envelope(
        basis="ledger",
        trace_id=f"tr_ledger_pnl_financial_indicator_rule_checks_{report_month}",
        result_kind="ledger_pnl.formal_financial_indicator_rule_checks",
        cache_version=FINANCIAL_INDICATOR_RULE_CHECKS_CACHE_VERSION,
        source_version=str(payload["source_version"]),
        rule_version=str(payload["rule_version"]),
        quality_flag=_quality_for_evidence(evidence_rows),
        vendor_version="vv_none",
        result_payload=payload,
        requested_report_date=report_month,
        resolved_report_date=str(payload["report_date"]),
        as_of_date=str(payload["report_date"]),
        date_basis="report_month_end",
        evidence_rows=evidence_rows,
    )
