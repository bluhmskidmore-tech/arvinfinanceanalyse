"""Read-only candidate comparison orchestration for the fixed Ledger PnL key metrics."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from calendar import monthrange
from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from backend.app.core_finance.finance_metric_component_detail import (
    FinanceMetricComponentDetail,
    FinanceMetricComponentDetailDefinition,
    FinanceMetricComponentParentSummary,
    build_finance_metric_component_detail,
)
from backend.app.core_finance.finance_metric_engine import (
    AccountObservation,
    FinanceMetricDataContext,
    FinanceMetricResult,
    evaluate_finance_metrics,
    load_finance_metric_rules,
)
from backend.app.core_finance.finance_metric_period_comparison import (
    NET_INTEREST_COMPONENT_DEFINITIONS,
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
from backend.app.schemas.candidate_financial_indicator_component_detail import (
    CandidateFinancialIndicatorComponentDetailEnvelope,
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
COMPONENT_DETAIL_CONTRACT_VERSION = (
    "candidate-financial-indicator-component-detail-v1"
)
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


def candidate_financial_indicator_component_detail_envelope(
    *,
    source_dir: str,
    report_month: str,
    metric_id: str,
    parent_idempotency_key: str,
) -> dict[str, Any]:
    """Return lazy exact-account evidence for one visible net-interest component."""

    definitions = {
        item.metric_id: item for item in NET_INTEREST_COMPONENT_DEFINITIONS
    }
    if metric_id not in definitions:
        raise CandidateFinancialIndicatorPeriodComparisonRequestError(
            "metric_id is outside the fixed net-interest component contract."
        )
    if re.fullmatch(r"[0-9a-f]{64}", parent_idempotency_key) is None:
        raise CandidateFinancialIndicatorPeriodComparisonRequestError(
            "parent_idempotency_key must be a lowercase SHA-256 value."
        )
    parent_payload = candidate_financial_indicator_period_comparison_envelope(
        source_dir=source_dir,
        report_month=report_month,
    )
    visible_parent_key = str(parent_payload["idempotency_key"])
    definition = definitions[metric_id]
    if parent_idempotency_key != visible_parent_key:
        stale_payload = _component_detail_base_payload(
            parent_payload=parent_payload,
            definition=definition,
            status="stale_parent",
            quality_status="not_evaluable",
            foot_status="not_evaluable",
            reasons=["parent_idempotency_key_mismatch"],
        )
        stale_payload.update(_empty_component_detail_values())
        stale_payload["idempotency_key"] = _build_component_detail_idempotency_key(
            payload=stale_payload,
            requested_parent_idempotency_key=parent_idempotency_key,
        )
        return CandidateFinancialIndicatorComponentDetailEnvelope.model_validate(
            stale_payload
        ).model_dump(mode="json")

    parent_bridge = parent_payload["net_interest_component_bridge"]
    if (
        parent_bridge["status"] != "available"
        or parent_bridge["foot_status"] != "passed"
    ):
        unavailable_payload = _component_detail_base_payload(
            parent_payload=parent_payload,
            definition=definition,
            status="not_evaluable",
            quality_status="not_evaluable",
            foot_status="not_evaluable",
            reasons=["parent_bridge_not_evaluable"],
        )
        unavailable_payload.update(_empty_component_detail_values())
        unavailable_payload["idempotency_key"] = _build_component_detail_idempotency_key(
            payload=unavailable_payload,
            requested_parent_idempotency_key=parent_idempotency_key,
        )
        return CandidateFinancialIndicatorComponentDetailEnvelope.model_validate(
            unavailable_payload
        ).model_dump(mode="json")

    parent_component = next(
        item
        for item in parent_bridge["components"]
        if item["metric_id"] == metric_id
    )
    parent_values = (
        parent_component["current_value_yi"],
        parent_component["previous_value_yi"],
        parent_component["component_delta_yi"],
        parent_component["contribution_to_net_delta_yi"],
    )
    if any(value is None for value in parent_values):
        unavailable_payload = _component_detail_base_payload(
            parent_payload=parent_payload,
            definition=definition,
            status="not_evaluable",
            quality_status="not_evaluable",
            foot_status="not_evaluable",
            reasons=["parent_component_not_evaluable"],
        )
        unavailable_payload.update(_empty_component_detail_values())
        unavailable_payload["idempotency_key"] = _build_component_detail_idempotency_key(
            payload=unavailable_payload,
            requested_parent_idempotency_key=parent_idempotency_key,
        )
        return CandidateFinancialIndicatorComponentDetailEnvelope.model_validate(
            unavailable_payload
        ).model_dump(mode="json")

    root = Path(source_dir)
    months = (
        str(parent_payload["report_month"]),
        str(parent_payload["comparison_month"]),
        str(parent_payload["two_month_prior"]),
    )
    rules = load_finance_metric_rules(rule_version="qdb-finance-2026-v1.0.1")
    sources = tuple(
        _load_ledger_only_period(root=root, report_month=month) for month in months
    )
    source_contracts = tuple(
        _source_period_contract(rules=rules, source=source) for source in sources
    )
    parent_sources = tuple(parent_payload["source_periods"])
    if any(
        source_contract["month"] != parent_source["month"]
        or source_contract["ledger_sha256"] != parent_source["ledger_sha256"]
        or source_contract["lock_status"] != parent_source["lock_status"]
        for source_contract, parent_source in zip(
            source_contracts,
            parent_sources,
            strict=True,
        )
    ):
        raise CandidateFinancialIndicatorPeriodComparisonRequestError(
            "Component detail source evidence does not match the visible parent."
        )
    direct_rule = next(
        item for item in rules["direct_rules"] if item["id"] == metric_id
    )
    detail = build_finance_metric_component_detail(
        report_month=report_month,
        definition=FinanceMetricComponentDetailDefinition(
            metric_id=definition.metric_id,
            metric_name=definition.metric_name,
            formula_weight=definition.formula_weight,
        ),
        direct_rule=direct_rule,
        source_periods=sources,  # type: ignore[arg-type]
        source_contracts=source_contracts,
        parent=FinanceMetricComponentParentSummary(
            current_value_yi=Decimal(str(parent_values[0])),
            previous_value_yi=Decimal(str(parent_values[1])),
            component_delta_yi=Decimal(str(parent_values[2])),
            contribution_to_net_delta_yi=Decimal(str(parent_values[3])),
        ),
    )
    payload = _component_detail_contract(
        parent_payload=parent_payload,
        detail=detail,
    )
    payload["idempotency_key"] = _build_component_detail_idempotency_key(
        payload=payload,
        requested_parent_idempotency_key=parent_idempotency_key,
    )
    return CandidateFinancialIndicatorComponentDetailEnvelope.model_validate(
        payload
    ).model_dump(mode="json")


def _component_detail_base_payload(
    *,
    parent_payload: Mapping[str, Any],
    definition: Any,
    status: Literal["available", "not_evaluable", "stale_parent"],
    quality_status: Literal[
        "standard_candidate",
        "degraded_candidate",
        "not_evaluable",
    ],
    foot_status: Literal["passed", "failed", "not_evaluable"],
    reasons: list[str],
) -> dict[str, Any]:
    return {
        "contract_version": COMPONENT_DETAIL_CONTRACT_VERSION,
        "analysis_kind": "accounting_component_account_detail",
        "report_month": parent_payload["report_month"],
        "report_date": parent_payload["report_date"],
        "comparison_month": parent_payload["comparison_month"],
        "two_month_prior": parent_payload["two_month_prior"],
        "metric_id": definition.metric_id,
        "metric_name": definition.metric_name,
        "formula_weight": definition.formula_weight,
        "currency": "CNX",
        "basis": "calendar_month_from_cumulative",
        "method": "finance_metric_account_contribution",
        "unit": "亿元",
        "status": status,
        "quality_status": quality_status,
        "foot_status": foot_status,
        "formal_use_allowed": False,
        "certification_effect": "none",
        "driver_status": "unclear",
        "rule_version": parent_payload["rule_version"],
        "rule_hash": parent_payload["rule_hash"],
        "parent_idempotency_key": parent_payload["idempotency_key"],
        "source_periods": parent_payload["source_periods"],
        "reasons": reasons,
    }


def _empty_component_detail_values() -> dict[str, Any]:
    return {
        "parent_current_value_yi": None,
        "parent_previous_value_yi": None,
        "parent_component_delta_yi": None,
        "parent_contribution_to_net_delta_yi": None,
        "account_current_total_yi": None,
        "account_previous_total_yi": None,
        "account_component_delta_total_yi": None,
        "account_contribution_total_yi": None,
        "current_reconciliation_yi": None,
        "previous_reconciliation_yi": None,
        "component_delta_reconciliation_yi": None,
        "contribution_reconciliation_yi": None,
        "rows": [],
    }


def _component_detail_contract(
    *,
    parent_payload: Mapping[str, Any],
    detail: FinanceMetricComponentDetail,
) -> dict[str, Any]:
    payload = _component_detail_base_payload(
        parent_payload=parent_payload,
        definition=detail,
        status=detail.status,
        quality_status=detail.quality_status,
        foot_status=detail.foot_status,
        reasons=list(detail.reasons),
    )
    payload.update(
        {
            "parent_current_value_yi": _decimal_text(detail.parent.current_value_yi),
            "parent_previous_value_yi": _decimal_text(
                detail.parent.previous_value_yi
            ),
            "parent_component_delta_yi": _decimal_text(
                detail.parent.component_delta_yi
            ),
            "parent_contribution_to_net_delta_yi": _decimal_text(
                detail.parent.contribution_to_net_delta_yi
            ),
            "account_current_total_yi": _decimal_text(
                detail.account_current_total_yi
            ),
            "account_previous_total_yi": _decimal_text(
                detail.account_previous_total_yi
            ),
            "account_component_delta_total_yi": _decimal_text(
                detail.account_component_delta_total_yi
            ),
            "account_contribution_total_yi": _decimal_text(
                detail.account_contribution_total_yi
            ),
            "current_reconciliation_yi": _decimal_text(
                detail.current_reconciliation_yi
            ),
            "previous_reconciliation_yi": _decimal_text(
                detail.previous_reconciliation_yi
            ),
            "component_delta_reconciliation_yi": _decimal_text(
                detail.component_delta_reconciliation_yi
            ),
            "contribution_reconciliation_yi": _decimal_text(
                detail.contribution_reconciliation_yi
            ),
            "rows": [_component_detail_row_contract(row) for row in detail.rows],
        }
    )
    return payload


def _component_detail_row_contract(row: Any) -> dict[str, Any]:
    return {
        "row_status": row.row_status,
        "account_code": row.account_code,
        "account_name": row.account_name,
        "currency": row.currency,
        "effective_component_weight": _decimal_text(
            row.effective_component_weight
        ),
        "effective_net_weight": _decimal_text(row.effective_net_weight),
        "matched_terms": [
            {
                "source": item.source,
                "level": item.level,
                "code": item.code,
                "weight": _decimal_text(item.weight),
            }
            for item in row.matched_terms
        ],
        "current_ending_yuan": _decimal_text(row.current_ending_yuan),
        "previous_ending_yuan": _decimal_text(row.previous_ending_yuan),
        "two_month_prior_ending_yuan": _decimal_text(
            row.two_month_prior_ending_yuan
        ),
        "current_value_yi": _decimal_text(row.current_value_yi),
        "previous_value_yi": _decimal_text(row.previous_value_yi),
        "component_delta_yi": _decimal_text(row.component_delta_yi),
        "contribution_to_net_delta_yi": _decimal_text(
            row.contribution_to_net_delta_yi
        ),
        "source_evidence": [
            {
                "month": item.month,
                "report_date": item.report_date,
                "ledger_file_name": item.ledger_file_name,
                "ledger_sha256": item.ledger_sha256,
                "locked_sha256": item.locked_sha256,
                "lock_status": item.lock_status,
                "sheet": item.sheet,
                "row": item.row,
                "account_code_cell": item.account_code_cell,
                "ending_cell": item.ending_cell,
                "ending_yuan": _decimal_text(item.ending_yuan),
            }
            for item in row.source_evidence
        ],
    }


def _build_component_detail_idempotency_key(
    *,
    payload: Mapping[str, Any],
    requested_parent_idempotency_key: str,
) -> str:
    material = {
        "payload": {
            key: value for key, value in payload.items() if key != "idempotency_key"
        },
        "requested_parent_idempotency_key": requested_parent_idempotency_key,
    }
    canonical = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_period_comparison_json_default,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


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
