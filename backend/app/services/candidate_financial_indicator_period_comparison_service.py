"""Read-only candidate comparison orchestration for the fixed Ledger PnL key metrics."""

from __future__ import annotations

import hashlib
import json
import logging
from calendar import monthrange
from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from backend.app.core_finance.finance_metric_engine import (
    AccountObservation,
    FinanceMetricDataContext,
    FinanceMetricResult,
    evaluate_finance_metrics,
    load_finance_metric_rules,
)
from backend.app.core_finance.finance_metric_period_comparison import (
    FinanceMetricNetInterestComponentBridge,
    build_finance_metric_period_comparisons,
    build_net_interest_component_bridge,
)
from backend.app.core_finance.finance_metric_xlsx import (
    LEDGER_HEADERS,
    FinanceMetricLedgerOnlySourceData,
    FinanceMetricXlsxError,
    parse_finance_metric_ledger_only_source,
    read_xlsx,
)
from backend.app.schemas.candidate_financial_indicator_period_comparison import (
    CandidateFinancialIndicatorPeriodComparisonEnvelope,
)
from backend.app.services.candidate_financial_indicator_service import (
    CandidateFinancialIndicatorRequestError,
    candidate_financial_indicator_envelope,
)

LEDGER_FILE_PREFIX = "总账对账"
DAILY_FILE_PREFIX = "日均"
REQUIRED_DAILY_SHEETS = ("年", "月", "微贷")
CONTRACT_VERSION = "candidate-financial-indicator-period-comparison-v2"
LOGGER = logging.getLogger(__name__)


class CandidateFinancialIndicatorPeriodComparisonRequestError(ValueError):
    """A caller-correctable period-comparison request error."""


def candidate_financial_indicator_period_comparison_envelope(
    *,
    source_dir: str,
    report_month: str,
) -> dict[str, Any]:
    report_date = _month_end(report_month)
    comparison_month = _previous_month(report_month)
    two_month_prior = _previous_month(comparison_month)
    months = (report_month, comparison_month, two_month_prior)
    root = Path(source_dir)
    rules = load_finance_metric_rules(rule_version="qdb-finance-2026-v1.0.1")

    source_periods = tuple(_load_ledger_only_period(root=root, report_month=month) for month in months)
    source_contracts = tuple(_source_period_contract(rules=rules, source=source) for source in source_periods)
    if any(item["lock_status"] == "locked_mismatch" for item in source_contracts):
        raise CandidateFinancialIndicatorPeriodComparisonRequestError(
            "A locked ledger source hash does not match the governed rule evidence."
        )
    quality_status: Literal["standard_candidate", "degraded_candidate"] = (
        "standard_candidate"
        if all(item["lock_status"] == "locked_match" for item in source_contracts)
        else "degraded_candidate"
    )
    evaluated = tuple(_evaluate_ledger_only(rules, source) for source in source_periods)
    rows = build_finance_metric_period_comparisons(
        report_month=report_month,
        current_metrics=evaluated[0],
        previous_metrics=evaluated[1],
        two_month_prior_metrics=evaluated[2],
        comparable_quality_status=quality_status,
    )
    net_interest_row = next(item for item in rows if item.metric_id == "income.interest.net")
    net_interest_component_bridge = _net_interest_component_bridge_contract(
        build_net_interest_component_bridge(
            report_month=report_month,
            current_metrics=evaluated[0],
            previous_metrics=evaluated[1],
            two_month_prior_metrics=evaluated[2],
            net_interest_row=net_interest_row,
            comparable_quality_status=quality_status,
        )
    )
    full_scope = _probe_previous_full_scope(
        root=root,
        comparison_month=comparison_month,
        rule_version=rules["metadata"]["rule_version"],
        rule_hash=rules["rule_hash"],
    )
    metrics = [_comparison_row_contract(row) for row in rows]
    comparable_count = sum(item["comparison_status"] == "comparable" for item in metrics)
    overall_status = (
        "available" if comparable_count == len(metrics) else "unavailable" if comparable_count == 0 else "partial"
    )
    payload = {
        "contract_version": CONTRACT_VERSION,
        "report_month": report_month,
        "report_date": report_date,
        "comparison_month": comparison_month,
        "two_month_prior": two_month_prior,
        "comparison_scope": "ledger_only_key_metrics",
        **full_scope,
        "overall_status": overall_status,
        "metric_status": "candidate",
        "formal_use_allowed": False,
        "certification_effect": "none",
        "driver_status": "unclear",
        "rule_version": rules["metadata"]["rule_version"],
        "rule_hash": rules["rule_hash"],
        "idempotency_key": _build_period_comparison_idempotency_key(
            contract_version=CONTRACT_VERSION,
            months=months,
            rule_hash=rules["rule_hash"],
            source_contracts=list(source_contracts),
            full_scope=full_scope,
            metrics=metrics,
            net_interest_component_bridge=net_interest_component_bridge,
        ),
        "source_periods": list(source_contracts),
        "net_interest_component_bridge": net_interest_component_bridge,
        "metrics": metrics,
    }
    return CandidateFinancialIndicatorPeriodComparisonEnvelope.model_validate(payload).model_dump(mode="json")


def _load_ledger_only_period(
    *,
    root: Path,
    report_month: str,
) -> FinanceMetricLedgerOnlySourceData:
    ledger_path = root / f"{LEDGER_FILE_PREFIX}{report_month}.xlsx"
    if not ledger_path.is_file():
        raise CandidateFinancialIndicatorPeriodComparisonRequestError(
            f"Ledger source is unavailable for {report_month}."
        )
    try:
        source = parse_finance_metric_ledger_only_source(
            ledger_path,
            requested_month=report_month,
        )
    except FinanceMetricXlsxError as exc:
        raise CandidateFinancialIndicatorPeriodComparisonRequestError(
            f"Ledger source is not usable for {report_month}."
        ) from exc
    if source.issues:
        raise CandidateFinancialIndicatorPeriodComparisonRequestError(
            f"Ledger source quality controls failed for {report_month}."
        )
    return source


def _evaluate_ledger_only(
    rules: dict[str, Any],
    source: FinanceMetricLedgerOnlySourceData,
) -> tuple[FinanceMetricResult, ...]:
    amounts: dict[tuple[str, str, str, str], Decimal] = {}
    refs: dict[tuple[str, str, str, str], list[str]] = {}
    for row in source.ledger:
        if row.currency != "CNX":
            continue
        ending_ref = dict(row.cell_refs).get(LEDGER_HEADERS[-1], "")
        evidence_ref = f"{row.sheet}!{ending_ref}" if ending_ref else ""
        levels = (
            ("l1", row.account_code[:3]),
            ("l2", row.account_code[:5]),
            ("l3", row.account_code[:7]),
            ("full", row.account_code),
        )
        for level, code in levels:
            for key in (
                ("main", "point", level, code),
                ("ledger", "cumulative", level, code),
            ):
                amounts[key] = amounts.get(key, Decimal(0)) + row.ending
                if evidence_ref:
                    refs.setdefault(key, []).append(evidence_ref)
    context = FinanceMetricDataContext(
        {
            key: AccountObservation(
                raw_yuan=amount,
                evidence_refs=tuple(dict.fromkeys(refs.get(key, ()))),
            )
            for key, amount in amounts.items()
        }
    )
    return evaluate_finance_metrics(rules, context, include_lineage=False)


def _source_period_contract(
    *,
    rules: dict[str, Any],
    source: FinanceMetricLedgerOnlySourceData,
) -> dict[str, Any]:
    file_name = f"{LEDGER_FILE_PREFIX}{source.report_month}.xlsx"
    locked_sha256 = next(
        (item.get("sha256") for item in rules["metadata"].get("derived_from", ()) if item.get("file") == file_name),
        None,
    )
    lock_status = (
        "unlocked"
        if locked_sha256 is None
        else "locked_match"
        if locked_sha256 == source.ledger_sha256
        else "locked_mismatch"
    )
    return {
        "month": source.report_month,
        "report_date": source.report_date,
        "ledger_file_name": file_name,
        "ledger_sha256": source.ledger_sha256,
        "locked_sha256": locked_sha256,
        "lock_status": lock_status,
    }


def _probe_previous_full_scope(
    *,
    root: Path,
    comparison_month: str,
    rule_version: str,
    rule_hash: str,
) -> dict[str, Any]:
    ledger_path = root / f"{LEDGER_FILE_PREFIX}{comparison_month}.xlsx"
    daily_path = root / f"{DAILY_FILE_PREFIX}{comparison_month}.xlsx"
    missing_kind = "ledger" if not ledger_path.is_file() else "daily" if not daily_path.is_file() else None
    if missing_kind is not None:
        return _full_scope_unavailable(
            comparison_month=comparison_month,
            reason_code="missing_source_file",
            source_kind=missing_kind,
            detail="上期完整来源文件不齐，未用于全量跨期比较。",
        )
    try:
        workbook = read_xlsx(daily_path)
        missing_sheet = next(
            (name for name in REQUIRED_DAILY_SHEETS if name not in workbook.sheets),
            None,
        )
        if missing_sheet is not None:
            return _full_scope_unavailable(
                comparison_month=comparison_month,
                reason_code="missing_required_sheet",
                source_kind="daily",
                required_sheet=missing_sheet,
                detail="上期完整六期间重放缺少必需工作表，未用于全量跨期比较。",
            )
    except FinanceMetricXlsxError:
        return _full_scope_unavailable(
            comparison_month=comparison_month,
            reason_code="source_parse_error",
            source_kind="daily",
            detail="上期完整来源未通过受控结构校验，未用于全量跨期比较。",
        )
    try:
        replay = candidate_financial_indicator_envelope(
            source_dir=str(root),
            report_month=comparison_month,
            include_lineage=False,
            metric_id=None,
        )
    except CandidateFinancialIndicatorRequestError as exc:
        LOGGER.warning(
            "candidate full replay rejected",
            extra={
                "comparison_month": comparison_month,
                "error_type": type(exc).__name__,
            },
        )
        return _full_scope_unavailable(
            comparison_month=comparison_month,
            reason_code="source_evaluation_error",
            source_kind="daily",
            detail="上期完整来源重放未完成，未用于全量跨期比较。",
        )
    result = replay.get("result") if isinstance(replay, Mapping) else None
    summary = result.get("summary") if isinstance(result, Mapping) else None
    metrics = result.get("metrics") if isinstance(result, Mapping) else None
    replay_complete = (
        isinstance(summary, Mapping)
        and isinstance(metrics, list)
        and result.get("rule_version") == rule_version
        and result.get("rule_hash") == rule_hash
        and result.get("calculation_status") in {"ready", "warning"}
        and summary.get("metric_total") == 186
        and summary.get("metric_evaluated") == 186
        and summary.get("error_count") == 0
        and summary.get("validation_error_failed") == 0
        and len(metrics) == 186
    )
    if not replay_complete:
        return _full_scope_unavailable(
            comparison_month=comparison_month,
            reason_code="full_replay_incomplete",
            source_kind="daily",
            detail="上期完整来源未形成同规则的 186 项无错误重放，未用于全量跨期比较。",
        )
    return {
        "full_scope_status": "available",
        "full_scope_reason_code": "available",
        "full_scope_detail": "上期完整来源已通过同规则 186 项无错误重放校验。",
        "full_scope_gaps": [],
    }


def _build_period_comparison_idempotency_key(
    *,
    contract_version: str,
    months: tuple[str, str, str],
    rule_hash: str,
    source_contracts: list[dict[str, Any]],
    full_scope: dict[str, Any],
    metrics: list[dict[str, Any]],
    net_interest_component_bridge: dict[str, Any],
) -> str:
    canonical_payload = {
        "contract_version": contract_version,
        "months": months,
        "rule_hash": rule_hash,
        "source_contracts": source_contracts,
        "full_scope": full_scope,
        "metrics": metrics,
        "net_interest_component_bridge": net_interest_component_bridge,
    }
    return hashlib.sha256(
        json.dumps(
            canonical_payload,
            default=_period_comparison_json_default,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _period_comparison_json_default(value: Any) -> str:
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(f"unsupported period-comparison evidence type: {type(value).__name__}")


def _full_scope_unavailable(
    *,
    comparison_month: str,
    reason_code: Literal[
        "missing_source_file",
        "missing_required_sheet",
        "source_parse_error",
        "full_replay_incomplete",
        "source_evaluation_error",
    ],
    source_kind: Literal["ledger", "daily"],
    detail: str,
    required_sheet: str | None = None,
) -> dict[str, Any]:
    gap: dict[str, Any] = {
        "reason_code": reason_code,
        "source_kind": source_kind,
        "month": comparison_month,
    }
    if required_sheet is not None:
        gap["required_sheet"] = required_sheet
    return {
        "full_scope_status": "unavailable",
        "full_scope_reason_code": reason_code,
        "full_scope_detail": detail,
        "full_scope_gaps": [gap],
    }


def _comparison_row_contract(row: Any) -> dict[str, Any]:
    return {
        "metric_id": row.metric_id,
        "metric_name": row.metric_name,
        "basis": row.basis,
        "method": row.method,
        "unit": row.unit,
        "comparison_status": row.comparison_status,
        "current_metric_status": row.current_metric_status,
        "previous_metric_status": row.previous_metric_status,
        "two_month_prior_metric_status": row.two_month_prior_metric_status,
        "current_value_yi": _decimal_text(row.current_value_yi),
        "previous_value_yi": _decimal_text(row.previous_value_yi),
        "current_source_value_yi": _decimal_text(row.current_source_value_yi),
        "previous_source_value_yi": _decimal_text(row.previous_source_value_yi),
        "two_month_prior_source_value_yi": _decimal_text(row.two_month_prior_source_value_yi),
        "delta_yi": _decimal_text(row.delta_yi),
        "change_rate": _decimal_text(row.change_rate),
        "rate_reason": row.rate_reason,
        "reasons": list(row.reasons),
        "driver_status": row.driver_status,
        "quality_status": row.quality_status,
    }


def _net_interest_component_bridge_contract(
    bridge: FinanceMetricNetInterestComponentBridge,
) -> dict[str, Any]:
    return {
        "analysis_kind": bridge.analysis_kind,
        "status": bridge.status,
        "metric_id": bridge.metric_id,
        "basis": bridge.basis,
        "method": bridge.method,
        "unit": bridge.unit,
        "quality_status": bridge.quality_status,
        "foot_status": bridge.foot_status,
        "net_delta_yi": _decimal_text(bridge.net_delta_yi),
        "component_contribution_total_yi": _decimal_text(bridge.component_contribution_total_yi),
        "reconciliation_delta_yi": _decimal_text(bridge.reconciliation_delta_yi),
        "reasons": list(bridge.reasons),
        "components": [
            {
                "metric_id": item.metric_id,
                "metric_name": item.metric_name,
                "formula_weight": item.formula_weight,
                "current_metric_status": item.current_metric_status,
                "previous_metric_status": item.previous_metric_status,
                "two_month_prior_metric_status": (item.two_month_prior_metric_status),
                "current_value_yi": _decimal_text(item.current_value_yi),
                "previous_value_yi": _decimal_text(item.previous_value_yi),
                "current_source_value_yi": _decimal_text(item.current_source_value_yi),
                "previous_source_value_yi": _decimal_text(item.previous_source_value_yi),
                "two_month_prior_source_value_yi": _decimal_text(item.two_month_prior_source_value_yi),
                "component_delta_yi": _decimal_text(item.component_delta_yi),
                "contribution_to_net_delta_yi": _decimal_text(item.contribution_to_net_delta_yi),
                "reasons": list(item.reasons),
            }
            for item in bridge.components
        ],
    }


def _decimal_text(value: Decimal | None) -> str | None:
    if value is None:
        return None
    if not value.is_finite():
        raise ValueError("period-comparison value must be finite")
    return "0" if value == 0 else format(value, "f")


def _month_end(report_month: str) -> date:
    try:
        if len(report_month) != 6 or not report_month.isdigit():
            raise ValueError
        year = int(report_month[:4])
        month = int(report_month[4:])
        return date(year, month, monthrange(year, month)[1])
    except (TypeError, ValueError) as exc:
        raise CandidateFinancialIndicatorPeriodComparisonRequestError(
            "Invalid report_month; expected a real YYYYMM month."
        ) from exc


def _previous_month(report_month: str) -> str:
    year = int(report_month[:4])
    month = int(report_month[4:])
    return f"{year - 1:04d}12" if month == 1 else f"{year:04d}{month - 1:02d}"
