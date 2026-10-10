"""Read-only candidate financial-indicator orchestration for Ledger PnL."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from calendar import monthrange
from collections.abc import Iterable, Mapping
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from backend.app.core_finance.finance_metric_engine import (
    AccountObservation,
    FinanceMetricAccountLineage,
    FinanceMetricDataContext,
    FinanceMetricLedgerBalanceRow,
    FinanceMetricManualLineage,
    FinanceMetricMetricLineage,
    FinanceMetricPeriod,
    FinanceMetricResult,
    FinanceMetricValidationEvidence,
    FinanceMetricValidationResult,
    build_finance_metric_idempotency_key,
    evaluate_finance_metrics,
    load_finance_metric_rules,
    validate_finance_metrics,
)
from backend.app.core_finance.finance_metric_source_impact import (
    build_finance_metric_source_impact,
)
from backend.app.core_finance.finance_metric_xlsx import (
    LEDGER_HEADERS,
    FinanceMetricSourceData,
    FinanceMetricXlsxError,
    PeriodEvidence,
    SourceIssue,
    parse_finance_metric_sources,
)
from backend.app.core_finance.formal_financial_indicators import (
    build_formal_financial_indicator_contract,
)
from backend.app.schemas.candidate_financial_indicators import (
    CandidateFinancialIndicatorEnvelope,
    CandidateFinancialIndicatorRevalidationReceipt,
    CandidateFinancialIndicatorRevalidationRequest,
    build_candidate_requirement_resolution_key,
    build_promotion_evidence_pack_key,
    build_promotion_readiness_evidence_key,
)

CACHE_VERSION = "cv_candidate_financial_indicators_v1"
LEDGER_FILE_PREFIX = "总账对账"
DAILY_FILE_PREFIX = "日均"
OUTPUT_TOTAL = 186
VALIDATION_TOTAL = 12
LOGGER = logging.getLogger(__name__)


class CandidateFinancialIndicatorRequestError(ValueError):
    """A caller-correctable candidate financial-indicator request error."""


class CandidateFinancialIndicatorConflictError(ValueError):
    """The requested base candidate or evidence pack is no longer current."""


def candidate_financial_indicator_envelope(
    *,
    source_dir: str,
    report_month: str,
    include_lineage: bool = False,
    metric_id: str | None = None,
    manual_overrides: Mapping[str, Decimal] | None = None,
) -> dict[str, Any]:
    rules = load_finance_metric_rules()
    known_metric_ids = _expanded_metric_ids(rules)
    if metric_id is not None and metric_id not in known_metric_ids:
        raise CandidateFinancialIndicatorRequestError(
            f"Unknown candidate financial metric_id: {metric_id!r}."
        )

    report_date = _month_end(report_month)
    root = Path(source_dir)
    ledger_path = root / f"{LEDGER_FILE_PREFIX}{report_month}.xlsx"
    daily_path = root / f"{DAILY_FILE_PREFIX}{report_month}.xlsx"
    existence = (ledger_path.is_file(), daily_path.is_file())
    if not all(existence):
        return _empty_envelope(
            rules=rules,
            report_month=report_month,
            report_date=report_date,
            ledger_path=ledger_path,
            daily_path=daily_path,
            include_lineage=include_lineage,
            metric_id=metric_id,
            status="no_data",
            parse_error=None,
        )

    try:
        source_data = parse_finance_metric_sources(
            ledger_path,
            daily_path,
            requested_month=report_month,
        )
    except FinanceMetricXlsxError as exc:
        return _empty_envelope(
            rules=rules,
            report_month=report_month,
            report_date=report_date,
            ledger_path=ledger_path,
            daily_path=daily_path,
            include_lineage=include_lineage,
            metric_id=metric_id,
            status="error",
            parse_error=exc,
        )

    context = _build_context(source_data)
    metrics = evaluate_finance_metrics(
        rules,
        context,
        manual_overrides=manual_overrides,
        include_lineage=include_lineage,
    )
    validation_evidence = _build_validation_evidence(source_data)
    validations = validate_finance_metrics(
        rules,
        context,
        metrics,
        validation_evidence,
    )
    idempotency_key = build_finance_metric_idempotency_key(
        ledger_sha256=source_data.ledger_sha256,
        daily_sha256=source_data.daily_sha256,
        rules=rules,
        manual_overrides=manual_overrides,
        references=None,
        analysis_requests=None,
        include_lineage=include_lineage,
        requested_metric_id=metric_id,
        report_month=report_month,
    )
    sources = _evaluated_sources(
        rules=rules,
        ledger_path=ledger_path,
        daily_path=daily_path,
        source_data=source_data,
    )
    source_alignment = _source_alignment(sources)
    calculation_status = _calculation_status(
        metrics=metrics,
        validations=validations,
        source_alignment=source_alignment,
        source_issues=source_data.issues,
    )
    gaps = _evaluated_gaps(
        metrics=metrics,
        validations=validations,
        sources=sources,
        source_issues=source_data.issues,
    )
    returned_metrics = (
        tuple(item for item in metrics if item.id == metric_id)
        if metric_id is not None
        else metrics
    )
    source_version = _source_version(
        report_month,
        source_data.ledger_sha256,
        source_data.daily_sha256,
        rules["rule_hash"],
    )
    metric_counts = _metric_counts(metrics)
    validation_counts = _validation_counts(validations)
    summary = {
        "metric_total": OUTPUT_TOTAL,
        "metric_evaluated": len(metrics),
        "metric_returned": len(returned_metrics),
        **metric_counts,
        "validation_total": VALIDATION_TOTAL,
        "validation_evaluated": len(validations),
        **validation_counts,
    }
    source_version_impact = None
    if not manual_overrides:
        source_version_impact = build_finance_metric_source_impact(
            report_month=report_month,
            rule_version=rules["metadata"]["rule_version"],
            ledger_sha256=source_data.ledger_sha256,
            daily_sha256=source_data.daily_sha256,
            metric_values={item.id: item.value for item in metrics},
        )
    payload = {
        "result_meta": _result_meta(
            report_month=report_month,
            report_date=report_date,
            source_version=source_version,
            rule_version=rules["metadata"]["rule_version"],
            idempotency_key=idempotency_key,
            calculation_status=calculation_status,
            include_lineage=include_lineage,
            metric_id=metric_id,
            tables_used=_tables_used(sources),
            evidence_rows=len(source_data.ledger) + len(source_data.averages),
        ),
        "result": {
            "report_month": report_month,
            "report_date": report_date,
            "currency": "CNX",
            "basis": "ledger",
            "metric_status": "candidate",
            "formal_use_allowed": False,
            "calculation_status": calculation_status,
            "source_alignment": source_alignment,
            "source_version": source_version,
            "rule_version": rules["metadata"]["rule_version"],
            "rule_hash": rules["rule_hash"],
            "idempotency_key": idempotency_key,
            "requested_metric_id": metric_id,
            "include_lineage": include_lineage,
            "source_version_impact": source_version_impact,
            "promotion_readiness": _promotion_readiness(
                report_month=report_month,
                report_date=report_date,
                rule_version=rules["metadata"]["rule_version"],
                rule_hash=rules["rule_hash"],
                source_version=source_version,
                candidate_idempotency_key=idempotency_key,
                source_alignment=source_alignment,
                sources=sources,
                metrics=metrics,
                validations=validations,
            ),
            "sources": sources,
            "summary": summary,
            "metrics": [_serialize_metric(item) for item in returned_metrics],
            "validations": [_serialize_validation(item) for item in validations],
            "gaps": gaps,
        },
    }
    return CandidateFinancialIndicatorEnvelope.model_validate(payload).model_dump(mode="json")


def revalidate_candidate_financial_indicators(
    *,
    source_dir: str,
    report_month: str,
    include_lineage: bool,
    metric_id: str | None,
    request: CandidateFinancialIndicatorRevalidationRequest,
) -> dict[str, Any]:
    base = candidate_financial_indicator_envelope(
        source_dir=source_dir,
        report_month=report_month,
        include_lineage=include_lineage,
        metric_id=metric_id,
    )
    base_result = base["result"]
    base_pack = base_result["promotion_readiness"]["evidence_pack"]
    if request.base_candidate_idempotency_key != base_result["idempotency_key"]:
        raise CandidateFinancialIndicatorConflictError(
            "base candidate idempotency key no longer matches the current calculation"
        )
    if request.base_evidence_pack_key != base_pack["evidence_pack_key"]:
        raise CandidateFinancialIndicatorConflictError(
            "base evidence pack key no longer matches the current calculation"
        )

    rules = load_finance_metric_rules()
    manual_metric_ids = {item["id"] for item in rules["manual_metrics"]}
    invalid_metric_ids = set(request.manual_overrides) - manual_metric_ids
    if invalid_metric_ids:
        joined = ", ".join(sorted(invalid_metric_ids))
        raise CandidateFinancialIndicatorRequestError(
            f"manual_overrides contains unknown or non-manual metric IDs: {joined}"
        )
    override_metric_ids = set(request.manual_overrides)
    if metric_id is not None and (
        metric_id not in manual_metric_ids or override_metric_ids != {metric_id}
    ):
        raise CandidateFinancialIndicatorRequestError(
            "a filtered revalidation requires exactly one override for the same manual metric_id"
        )
    if override_metric_ids and base_result["calculation_status"] in {
        "no_data",
        "error",
    }:
        raise CandidateFinancialIndicatorRequestError(
            "manual_overrides cannot be applied when the base calculation_status is "
            f"{base_result['calculation_status']}"
        )
    base_manual_requirement_metric_ids = {
        ref
        for requirement in base_pack["owner_requirements"]
        if requirement["category"] == "manual_input"
        for ref in requirement["evidence_refs"]
        if ref in manual_metric_ids
    }
    missing_requirement_ids = (
        override_metric_ids - base_manual_requirement_metric_ids
    )
    if missing_requirement_ids:
        joined = ", ".join(sorted(missing_requirement_ids))
        raise CandidateFinancialIndicatorRequestError(
            "manual_overrides has no matching base manual requirement: " + joined
        )

    override_values = {
        metric_id: Decimal(item.value_yi)
        for metric_id, item in request.manual_overrides.items()
    }
    result = candidate_financial_indicator_envelope(
        source_dir=source_dir,
        report_month=report_month,
        include_lineage=include_lineage,
        metric_id=metric_id,
        manual_overrides=override_values,
    )
    result_payload = result["result"]
    boundary_fields = (
        "report_month",
        "report_date",
        "rule_version",
        "rule_hash",
        "source_version",
    )
    changed_fields = [
        field
        for field in boundary_fields
        if result_payload[field] != base_result[field]
    ]
    if changed_fields:
        raise CandidateFinancialIndicatorConflictError(
            "candidate calculation changed during revalidation: "
            + ", ".join(changed_fields)
        )
    result_pack = result_payload["promotion_readiness"]["evidence_pack"]
    result_metrics = {
        item["metric_id"]: item for item in result_payload["metrics"]
    }
    resolutions: list[dict[str, Any]] = []
    for requirement in base_pack["owner_requirements"]:
        referenced_manual_id = (
            next(
                (
                    ref
                    for ref in requirement["evidence_refs"]
                    if ref in manual_metric_ids
                ),
                None,
            )
            if requirement["category"] == "manual_input"
            else None
        )
        override = (
            request.manual_overrides.get(referenced_manual_id)
            if referenced_manual_id is not None
            else None
        )
        status = "awaiting_owner_input"
        status_detail = "No revalidation input was submitted for this requirement."
        submitted_refs: list[str] = []
        validation_refs: list[str] = []
        if override is not None:
            submitted_refs = list(override.submitted_evidence_refs)
            metric = result_metrics.get(referenced_manual_id)
            calculation_available = result_payload["calculation_status"] not in {
                "error",
                "no_data",
            }
            metric_available = metric is not None and metric["status"] not in {
                "manual_default",
                "error",
            }
            if calculation_available and metric_available:
                status = "evidence_received"
                status_detail = (
                    "Submitted manual value was applied and the candidate recalculation is "
                    "available; evidence and approval have not been verified."
                )
                validation_refs = [
                    f"candidate_metric:{referenced_manual_id}:applied",
                    f"candidate_idempotency:{result_payload['idempotency_key']}",
                ]
            else:
                status = "validation_failed"
                status_detail = (
                    "Submitted manual value could not be verified against an available "
                    "candidate calculation."
                )
                validation_refs = [
                    f"candidate_calculation_status:{result_payload['calculation_status']}"
                ]
        resolutions.append(
            {
                "requirement_id": requirement["requirement_id"],
                "status": status,
                "status_detail": status_detail,
                "submitted_evidence_refs": submitted_refs,
                "validation_evidence_refs": validation_refs,
            }
        )

    resolution = {
        "contract_version": "candidate-promotion-resolution-v1",
        "resolution_key": "",
        "base_evidence_pack_key": request.base_evidence_pack_key,
        "result_evidence_pack_key": result_pack["evidence_pack_key"],
        "base_requirement_ids": [
            item["requirement_id"] for item in base_pack["owner_requirements"]
        ],
        "requirements": resolutions,
    }
    resolution["resolution_key"] = build_candidate_requirement_resolution_key(
        requirement_resolution=resolution
    )
    receipt = {
        "contract_version": "candidate-financial-indicator-revalidation-v1",
        "revalidation_effect": "none",
        "persisted": False,
        "formal_use_allowed": False,
        "base_candidate_idempotency_key": request.base_candidate_idempotency_key,
        "base_evidence_pack_key": request.base_evidence_pack_key,
        "manual_override_count": len(request.manual_overrides),
        "requirement_resolution": resolution,
        "result": result,
    }
    return CandidateFinancialIndicatorRevalidationReceipt.model_validate(
        receipt
    ).model_dump(mode="json")


def _build_context(source_data: FinanceMetricSourceData) -> FinanceMetricDataContext:
    amounts: dict[tuple[str, str, str, str], Decimal] = {}
    refs: dict[tuple[str, str, str, str], list[str]] = {}

    def add(
        key: tuple[str, str, str, str],
        amount: Decimal,
        evidence_ref: str,
    ) -> None:
        amounts[key] = amounts.get(key, Decimal(0)) + amount
        if evidence_ref:
            refs.setdefault(key, []).append(evidence_ref)

    for row in source_data.ledger:
        if row.currency != "CNX":
            continue
        ending_ref = dict(row.cell_refs).get(LEDGER_HEADERS[-1], "")
        evidence_ref = f"{row.sheet}!{ending_ref}" if ending_ref else ""
        if row.source == "main":
            levels = (
                ("l1", row.account_code[:3]),
                ("l2", row.account_code[:5]),
                ("l3", row.account_code[:7]),
                ("full", row.account_code),
            )
            for level, code in levels:
                add(("main", "point", level, code), row.ending, evidence_ref)
                add(("ledger", "cumulative", level, code), row.ending, evidence_ref)
        elif row.source == "microloan":
            code = row.account_code[:3]
            add(("microloan", "point", "l1", code), row.ending, evidence_ref)
            add(
                ("microloan_ledger", "cumulative", "l1", code),
                row.ending,
                evidence_ref,
            )

    for row in source_data.averages:
        if row.currency != "CNX":
            continue
        balance_ref = dict(row.cell_refs).get("balance", "")
        evidence_ref = f"{row.sheet}!{balance_ref}" if balance_ref else ""
        add(
            (row.source, row.basis, row.level, row.account_code),
            row.balance,
            evidence_ref,
        )

    observations = {
        key: AccountObservation(
            raw_yuan=amount,
            evidence_refs=tuple(dict.fromkeys(refs.get(key, ()))),
        )
        for key, amount in amounts.items()
    }
    return FinanceMetricDataContext(observations)


def _build_validation_evidence(
    source_data: FinanceMetricSourceData,
) -> FinanceMetricValidationEvidence:
    periods = tuple(
        FinanceMetricPeriod(id=item.evidence_id, start=item.start, end=item.end)
        for item in source_data.periods
    )
    ledger_rows = tuple(
        FinanceMetricLedgerBalanceRow(
            source=item.source,
            row=item.row,
            code=item.account_code,
            currency=item.currency,
            opening=item.opening,
            debit=item.debit,
            credit=item.credit,
            ending=item.ending,
        )
        for item in source_data.ledger
    )
    currencies = tuple(
        item.currency for item in (*source_data.ledger, *source_data.averages)
    )
    return FinanceMetricValidationEvidence(
        periods=periods,
        consumed_currencies=currencies,
        ledger_balance_rows=ledger_rows,
    )


def _expanded_metric_ids(rules: dict[str, Any]) -> tuple[str, ...]:
    metric_ids = [
        f"{rule['id']}::{basis}"
        for rule in rules["scale_rules"]
        for basis in rule["available_bases"]
    ]
    for section in ("direct_rules", "manual_metrics", "derived_rules"):
        metric_ids.extend(rule["id"] for rule in rules[section])
    if len(metric_ids) != OUTPUT_TOTAL or len(set(metric_ids)) != OUTPUT_TOTAL:
        raise RuntimeError("candidate rule pack must expand to 186 unique metric IDs")
    return tuple(metric_ids)


def _evaluated_sources(
    *,
    rules: dict[str, Any],
    ledger_path: Path,
    daily_path: Path,
    source_data: FinanceMetricSourceData,
) -> list[dict[str, Any]]:
    ledger_periods = tuple(
        item for item in source_data.periods if item.evidence_id == "ledger"
    )
    daily_periods = tuple(
        item for item in source_data.periods if item.evidence_id != "ledger"
    )
    return [
        _source_record(
            rules=rules,
            source_kind="ledger",
            path=ledger_path,
            exists=True,
            sha256=source_data.ledger_sha256,
            periods=ledger_periods,
        ),
        _source_record(
            rules=rules,
            source_kind="daily",
            path=daily_path,
            exists=True,
            sha256=source_data.daily_sha256,
            periods=daily_periods,
        ),
    ]


def _source_record(
    *,
    rules: dict[str, Any],
    source_kind: Literal["ledger", "daily"],
    path: Path,
    exists: bool,
    sha256: str | None,
    periods: Iterable[PeriodEvidence],
) -> dict[str, Any]:
    period_items = tuple(periods)
    locked_sha256 = _locked_sha256(rules, path.name)
    return {
        "source_kind": source_kind,
        "file_name": path.name,
        "exists": exists,
        "sha256": sha256,
        "locked_sha256": locked_sha256,
        "locked_hash_match": (
            sha256 == locked_sha256
            if sha256 is not None and locked_sha256 is not None
            else None
        ),
        "sheets": list(dict.fromkeys(item.sheet for item in period_items)),
        "periods": [
            {
                "evidence_id": item.evidence_id,
                "start": item.start,
                "end": item.end,
                "source_cell": f"{item.sheet}!{item.cell_ref}",
            }
            for item in period_items
        ],
    }


def _empty_envelope(
    *,
    rules: dict[str, Any],
    report_month: str,
    report_date: date,
    ledger_path: Path,
    daily_path: Path,
    include_lineage: bool,
    metric_id: str | None,
    status: Literal["no_data", "error"],
    parse_error: FinanceMetricXlsxError | None,
) -> dict[str, Any]:
    source_inputs = (("ledger", ledger_path), ("daily", daily_path))
    sources: list[dict[str, Any]] = []
    for source_kind, path in source_inputs:
        exists = path.is_file()
        sha256 = _sha256_path(path) if exists else None
        sources.append(
            _source_record(
                rules=rules,
                source_kind=source_kind,
                path=path,
                exists=exists,
                sha256=sha256,
                periods=(),
            )
        )
    state_key = _state_key(
        report_month=report_month,
        rule_hash=rules["rule_hash"],
        sources=sources,
        include_lineage=include_lineage,
        metric_id=metric_id,
        status=status,
    )
    source_version = _source_version(
        report_month,
        sources[0]["sha256"] or "missing",
        sources[1]["sha256"] or "missing",
        rules["rule_hash"],
    )
    gaps: list[dict[str, Any]] = []
    for source in sources:
        if not source["exists"]:
            gaps.append(
                {
                    "gap_id": f"source_missing.{source['source_kind']}",
                    "severity": "error",
                    "kind": "source_missing",
                    "title": f"缺少{source['source_kind']}源文件",
                    "detail": f"固定来源文件 {source['file_name']} 不存在，未执行候选指标计算。",
                    "metric_ids": [],
                }
            )
    if parse_error is not None:
        location = ", ".join(
            item
            for item in (
                f"sheet={parse_error.sheet}" if parse_error.sheet else "",
                f"cell={parse_error.cell}" if parse_error.cell else "",
            )
            if item
        )
        detail = f"源工作簿未通过结构安全解析（code={parse_error.code}"
        if location:
            detail += f", {location}"
        detail += "）。原始异常内容未向接口暴露。"
        gaps.append(
            {
                "gap_id": f"source_parse.{_slug(parse_error.code)}",
                "severity": "error",
                "kind": "source_parse",
                "title": "源工作簿解析失败",
                "detail": detail,
                "metric_ids": [],
            }
        )
    payload = {
        "result_meta": _result_meta(
            report_month=report_month,
            report_date=report_date,
            source_version=source_version,
            rule_version=rules["metadata"]["rule_version"],
            idempotency_key=state_key,
            calculation_status=status,
            include_lineage=include_lineage,
            metric_id=metric_id,
            tables_used=[],
            evidence_rows=0,
        ),
        "result": {
            "report_month": report_month,
            "report_date": report_date,
            "currency": "CNX",
            "basis": "ledger",
            "metric_status": "candidate",
            "formal_use_allowed": False,
            "calculation_status": status,
            "source_alignment": _source_alignment(sources),
            "source_version": source_version,
            "rule_version": rules["metadata"]["rule_version"],
            "rule_hash": rules["rule_hash"],
            "idempotency_key": state_key,
            "requested_metric_id": metric_id,
            "include_lineage": include_lineage,
            "promotion_readiness": _promotion_readiness(
                report_month=report_month,
                report_date=report_date,
                rule_version=rules["metadata"]["rule_version"],
                rule_hash=rules["rule_hash"],
                source_version=source_version,
                candidate_idempotency_key=state_key,
                source_alignment=_source_alignment(sources),
                sources=sources,
                metrics=(),
                validations=(),
            ),
            "sources": sources,
            "summary": {
                "metric_total": OUTPUT_TOTAL,
                "metric_evaluated": 0,
                "metric_returned": 0,
                "ok_count": 0,
                "warning_count": 0,
                "manual_default_count": 0,
                "error_count": 0,
                "validation_total": VALIDATION_TOTAL,
                "validation_evaluated": 0,
                "validation_passed": 0,
                "validation_warning_failed": 0,
                "validation_error_failed": 0,
            },
            "metrics": [],
            "validations": [],
            "gaps": gaps,
        },
    }
    return CandidateFinancialIndicatorEnvelope.model_validate(payload).model_dump(mode="json")


def _promotion_readiness(
    *,
    report_month: str,
    report_date: date,
    rule_version: str,
    rule_hash: str,
    source_version: str,
    candidate_idempotency_key: str,
    source_alignment: str,
    sources: list[dict[str, Any]],
    metrics: tuple[FinanceMetricResult, ...],
    validations: tuple[FinanceMetricValidationResult, ...],
) -> dict[str, Any]:
    def check(
        check_id: str,
        label: str,
        status: Literal["passed", "blocked", "not_evaluated"],
        summary: str,
        evidence_refs: list[str],
        action: str,
    ) -> dict[str, Any]:
        return {
            "check_id": check_id,
            "label": label,
            "status": status,
            "blocking": status != "passed",
            "summary": summary,
            "evidence_refs": evidence_refs,
            "action": action,
        }

    def owner_requirement(
        requirement_id: str,
        category: str,
        evidence_refs: list[str],
        required_evidence: list[str],
        action: str,
    ) -> dict[str, Any]:
        return {
            "requirement_id": requirement_id,
            "category": category,
            "status": "awaiting_owner_input",
            "submitted_value": None,
            "evidence_refs": evidence_refs,
            "required_evidence": required_evidence,
            "action": action,
        }

    checks = [
        check(
            "rule_asset",
            "规则资产与候选计算",
            "passed",
            f"已加载批准规则 {rule_version}（{rule_hash[:12]}…）。",
            [rule_version, rule_hash],
            "规则资产已通过；保持当前批准版本不变。",
        )
    ]

    missing_sources = [source["file_name"] for source in sources if not source["exists"]]
    period_validations = [item for item in validations if item.id.startswith("period.")]
    failed_period_validations = [item for item in period_validations if not item.passed]
    if missing_sources:
        source_status: Literal["passed", "blocked", "not_evaluated"] = "blocked"
        source_summary = f"缺少固定来源：{'、'.join(missing_sources)}。"
        source_action = "补齐当月固定总账与日均来源后重新计算。"
    elif failed_period_validations:
        source_status = "blocked"
        source_summary = "来源期间证据未通过全部期间控制。"
        source_action = "修复来源期间后重新执行六段期间校验。"
    elif (
        source_alignment == "matched"
        and len(period_validations) == 3
        and all(source["locked_hash_match"] is True for source in sources)
    ):
        source_status = "passed"
        source_summary = "总账与日均来源均匹配批准哈希，期间证据完整。"
        source_action = "来源证据已通过；保持锁定文件不变。"
    else:
        source_status = "blocked"
        source_summary = f"来源锁定状态为 {source_alignment}，不能进入正式登记评审。"
        source_action = "核对当前文件与批准样本；如需采纳新文件，创建新规则版本并重新审批。"
    source_refs = [
        f"{source['source_kind']}:{source['sha256'] or 'missing'}:{source['locked_sha256'] or 'unlocked'}"
        for source in sources
    ]
    source_refs.extend(item.id for item in failed_period_validations)
    checks.append(
        check(
            "source_evidence",
            "来源期间与锁定哈希",
            source_status,
            source_summary,
            source_refs,
            source_action,
        )
    )

    failed_validations = [item for item in validations if not item.passed]
    if not validations:
        validation_status = "not_evaluated"
        validation_summary = "12 项控制尚未执行。"
        validation_refs: list[str] = []
    elif failed_validations:
        validation_status = "blocked"
        validation_summary = f"{len(validations) - len(failed_validations)} / {len(validations)} 项控制通过。"
        validation_refs = [item.id for item in failed_validations]
    else:
        validation_status = "passed"
        validation_summary = f"{len(validations)} / {len(validations)} 项控制通过。"
        validation_refs = [item.id for item in validations]
    checks.append(
        check(
            "validation_controls",
            "控制校验",
            validation_status,
            validation_summary,
            validation_refs,
            "处置全部未通过控制并重新执行 12 项校验。",
        )
    )

    manual_metrics = [item.id for item in metrics if item.status == "manual_default"]
    if not metrics:
        manual_status = "not_evaluated"
        manual_summary = "手工调整项尚未评估。"
    elif manual_metrics:
        manual_status = "blocked"
        manual_summary = f"{len(manual_metrics)} 项仍使用默认值；即使为 0 也必须显式确认。"
    else:
        manual_status = "passed"
        manual_summary = "全部手工调整项均已显式提供。"
    checks.append(
        check(
            "manual_inputs",
            "手工调整输入",
            manual_status,
            manual_summary,
            manual_metrics,
            "提交带期间、证据、提交人与审批人的 19 项批准输入快照。",
        )
    )

    missing_account_validation = next(
        (item for item in validations if item.id == "rules.missing_accounts"),
        None,
    )
    if missing_account_validation is None:
        account_status = "not_evaluated"
        account_summary = "规则科目覆盖尚未评估。"
        account_refs: list[str] = []
    elif missing_account_validation.passed:
        account_status = "passed"
        account_summary = "规则引用科目均有来源记录或已批准的显式零证明。"
        account_refs = []
    else:
        account_status = "blocked"
        account_refs = list(missing_account_validation.sample)
        account_summary = f"{len(account_refs)} 个规则输入缺少来源或批准的零余额证明。"
    checks.append(
        check(
            "account_coverage",
            "规则科目覆盖",
            account_status,
            account_summary,
            account_refs,
            "补齐源文件记录，或登记期间匹配且审批完整的显式零余额证明。",
        )
    )

    try:
        formal_contract = build_formal_financial_indicator_contract(
            report_month=report_month
        )
    except Exception:
        LOGGER.exception(
            "candidate promotion readiness formal contract lookup failed",
            extra={"report_month": report_month},
        )
        formal_contract = None
    if formal_contract is None:
        formal_status = "unavailable"
        formal_metrics: list[dict[str, Any]] = []
        formal_passed = False
        remediation: dict[str, Any] = {}
        formal_sample_id = "formal-contract-registry-unavailable"
        formal_source_version = "source-version-unavailable"
        release_status = None
        formal_refs = ["formal-contract-registry-unavailable"]
    else:
        formal_status = str(formal_contract["sample_status"])
        formal_metrics = formal_contract.get("metrics") or []
        formal_passed = formal_status == "contract_fixture" and bool(formal_metrics)
        remediation = formal_contract.get("remediation") or {}
        formal_sample_id = str(formal_contract["sample_id"])
        formal_source_version = str(
            formal_contract.get("source_version") or "source-version-unavailable"
        )
        formal_refs = [
            formal_sample_id,
            formal_source_version,
        ]
        release_gate = formal_contract.get("release_gate") or {}
        release_status = str(release_gate.get("status") or "").strip() or None
        if release_status:
            formal_refs.append(f"release_gate:{release_status}")
        required_artifact = str(remediation.get("required_artifact") or "").strip()
        if required_artifact:
            formal_refs.append(required_artifact)
    checks.append(
        check(
            "formal_contract",
            "正式契约登记",
            "passed" if formal_passed else "blocked",
            (
                f"已登记 {len(formal_metrics)} 项冻结正式指标契约。"
                if formal_passed
                else (
                    # Human: caliber-formal_scenario_gate-justified -- formal_status
                    # is a frozen-contract availability label, not a basis gate.
                    "正式契约登记状态暂不可读取。"
                    if formal_status == "unavailable"
                    else f"{report_month} 正式财务指标冻结契约尚未登记。"
                )
            ),
            formal_refs,
            str(
                remediation.get("action_detail")
                or "回读正式契约并提交财务与数据治理负责人复核。"
            ),
        )
    )

    blocking_count = sum(item["blocking"] for item in checks)
    next_action = next(
        (item["action"] for item in checks if item["blocking"]),
        "候选技术门禁已通过；提交财务与数据治理负责人复核，正式使用仍保持关闭。",
    )
    readiness_contract_version = "promotion-readiness-v1"
    readiness_evidence_key = build_promotion_readiness_evidence_key(
        candidate_idempotency_key=candidate_idempotency_key,
        formal_contract_status=formal_status,
        checks=[
            {
                "check_id": item["check_id"],
                "status": item["status"],
                "evidence_refs": item["evidence_refs"],
            }
            for item in checks
        ],
    )
    owner_requirements: list[dict[str, Any]] = []
    if source_status != "passed":
        owner_requirements.append(
            owner_requirement(
                "source_evidence.1",
                "source_evidence",
                source_refs,
                [
                    "批准来源文件或新规则版本决定",
                    "来源期间与 SHA-256 复核记录",
                    "提交人与审批人",
                ],
                source_action,
            )
        )
    unresolved_validations = [
        item for item in failed_validations if item.id != "rules.missing_accounts"
    ]
    for index, item in enumerate(unresolved_validations, start=1):
        owner_requirements.append(
            owner_requirement(
                f"validation_control.{index}",
                "validation_control",
                [item.id],
                ["控制失败处置说明", "复核人和复核日期"],
                "处置控制失败并重新执行候选指标校验。",
            )
        )
    for index, metric_id in enumerate(manual_metrics, start=1):
        owner_requirements.append(
            owner_requirement(
                f"manual_input.{index}",
                "manual_input",
                [metric_id],
                ["期间匹配的实际值", "业务凭证", "提交人和审批人"],
                "提交显式手工输入；即使为 0 也必须提供批准证据。",
            )
        )
    for index, account_ref in enumerate(account_refs, start=1):
        owner_requirements.append(
            owner_requirement(
                f"account_coverage.{index}",
                "account_coverage",
                [account_ref],
                ["源文件科目记录或显式零余额证明", "期间和审批证据"],
                "补齐来源记录，或提交期间匹配的批准零余额证明。",
            )
        )
    if not formal_passed:
        owner_requirements.append(
            owner_requirement(
                "formal_contract.1",
                "formal_contract",
                formal_refs,
                ["正式财务指标 Excel 冻结样本", "样本 SHA-256 与契约登记记录"],
                str(
                    remediation.get("action_detail")
                    or "回读正式契约并提交财务与数据治理负责人复核。"
                ),
            )
        )
    owner_requirements.append(
        owner_requirement(
            "business_owner_approval.1",
            "business_owner_approval",
            [],
            ["负责人姓名与角色", "审批决定与日期", "签名或等效审批凭证"],
            "六项技术门禁通过后，仍须财务与数据治理负责人复核。",
        )
    )
    evidence_pack = {
        "contract_version": "candidate-promotion-evidence-v1",
        "evidence_pack_key": "",
        "report_month": report_month,
        "report_date": report_date,
        "rule_version": rule_version,
        "rule_hash": rule_hash,
        "source_version": source_version,
        "source_alignment": source_alignment,
        "candidate_idempotency_key": candidate_idempotency_key,
        "readiness_contract_version": readiness_contract_version,
        "readiness_evidence_key": readiness_evidence_key,
        "metric_status": "candidate",
        "formal_use_allowed": False,
        "owner_approval_required": True,
        "contains_metric_values": False,
        "contains_formal_values": False,
        "certification_effect": "none",
        "blocking_count": blocking_count,
        "check_total": len(checks),
        "formal_contract_status": formal_status,
        "formal_sample_id": formal_sample_id,
        "formal_source_version": formal_source_version,
        "formal_release_gate_status": release_status,
        "formal_metric_count": len(formal_metrics),
        "checks": checks,
        "owner_requirement_count": len(owner_requirements),
        "owner_requirements": owner_requirements,
        "outcome_status": "blocked" if blocking_count else "awaiting_owner_approval",
    }
    evidence_pack["evidence_pack_key"] = build_promotion_evidence_pack_key(
        evidence_pack=evidence_pack
    )
    return {
        "readiness_contract_version": readiness_contract_version,
        "readiness_evidence_key": readiness_evidence_key,
        "status": "blocked" if blocking_count else "review_required",
        "blocking_count": blocking_count,
        "check_total": len(checks),
        "candidate_idempotency_key": candidate_idempotency_key,
        "formal_contract_status": formal_status,
        "formal_use_allowed": False,
        "owner_approval_required": True,
        "next_action": next_action,
        "checks": checks,
        "evidence_pack": evidence_pack,
    }


def _calculation_status(
    *,
    metrics: tuple[FinanceMetricResult, ...],
    validations: tuple[FinanceMetricValidationResult, ...],
    source_alignment: str,
    source_issues: tuple[SourceIssue, ...],
) -> Literal["ready", "warning", "error"]:
    if any(item.status == "error" for item in metrics) or any(
        not item.passed and item.severity == "error" for item in validations
    ):
        return "error"
    if (
        any(item.status != "ok" for item in metrics)
        or any(not item.passed for item in validations)
        or source_alignment in {"mismatch", "not_applicable"}
        or source_issues
    ):
        return "warning"
    return "ready"


def _evaluated_gaps(
    *,
    metrics: tuple[FinanceMetricResult, ...],
    validations: tuple[FinanceMetricValidationResult, ...],
    sources: list[dict[str, Any]],
    source_issues: tuple[SourceIssue, ...],
) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    for source in sources:
        if source["locked_sha256"] is None:
            gaps.append(
                {
                    "gap_id": f"source_hash_unlocked.{source['source_kind']}",
                    "severity": "warning",
                    "kind": "source_hash",
                    "title": f"{source['source_kind']}来源尚未锁定样本",
                    "detail": "当前来源没有批准的 SHA-256 样本，候选结果不可判定为 ready。",
                    "metric_ids": [],
                }
            )
        elif source["locked_hash_match"] is False:
            gaps.append(
                {
                    "gap_id": f"source_hash.{source['source_kind']}",
                    "severity": "warning",
                    "kind": "source_hash",
                    "title": f"{source['source_kind']}来源与锁定样本不一致",
                    "detail": "本次按当前文件计算；该候选结果不可冒充锁定黄金样本。",
                    "metric_ids": [],
                }
            )

    manual_ids = [item.id for item in metrics if item.status == "manual_default"]
    if manual_ids:
        gaps.append(
            {
                "gap_id": "manual_input.required_defaults",
                "severity": "warning",
                "kind": "manual_input",
                "title": "人工调整项尚未录入",
                "detail": f"{len(manual_ids)} 项人工指标当前使用规则包默认值，正式使用前需补录并复核。",
                "metric_ids": manual_ids,
            }
        )

    missing_metric_ids = [
        item.id
        for item in metrics
        if any(reason.startswith("missing_account:") for reason in item.reasons)
    ]
    if missing_metric_ids:
        gaps.append(
            {
                "gap_id": "missing_account.rule_inputs",
                "severity": "warning",
                "kind": "missing_account",
                "title": "部分规则科目未在来源中观测到",
                "detail": "未观测科目按零参与候选计算，并在指标原因和血缘中显式标记。",
                "metric_ids": missing_metric_ids,
            }
        )

    error_metric_ids = [item.id for item in metrics if item.status == "error"]
    if error_metric_ids:
        gaps.append(
            {
                "gap_id": "calculation.metric_errors",
                "severity": "error",
                "kind": "calculation",
                "title": "候选指标存在不可用计算结果",
                "detail": "至少一个指标或其依赖不可用，结果已阻断。",
                "metric_ids": error_metric_ids,
            }
        )

    for validation in validations:
        if validation.passed:
            continue
        gaps.append(
            {
                "gap_id": f"validation.{validation.id}",
                "severity": validation.severity,
                "kind": "validation",
                "title": f"校验未通过：{validation.id}",
                "detail": validation.message,
                "metric_ids": [],
            }
        )

    for index, issue in enumerate(source_issues, start=1):
        evidence = ", ".join(
            (
                f"key={'/'.join(issue.key)}",
                f"rows={','.join(str(row) for row in issue.rows)}",
                f"cells={','.join(ref for ref in issue.cell_refs if ref)}",
            )
        ).rstrip(", ")
        gaps.append(
            {
                "gap_id": f"source_issue.{index}.{_slug(issue.code)}",
                "severity": issue.severity if issue.severity in {"error", "warning", "info"} else "warning",
                "kind": "validation",
                "title": f"来源证据提示：{issue.code}",
                "detail": f"{issue.message}（{evidence}）",
                "metric_ids": [],
            }
        )
    return gaps


def _serialize_metric(item: FinanceMetricResult) -> dict[str, Any]:
    return {
        "metric_id": item.id,
        "name": item.name,
        "category": item.category,
        "basis": item.basis,
        "unit": item.unit,
        "value": _decimal_text(item.value),
        "status": item.status,
        "reasons": list(item.reasons),
        "lineage": [_serialize_lineage(lineage) for lineage in (item.lineage or ())],
    }


def _serialize_lineage(item: Any) -> dict[str, Any]:
    if isinstance(item, FinanceMetricAccountLineage):
        return {
            "lineage_type": "account",
            "source": item.source,
            "basis": item.basis,
            "level": item.level,
            "code": item.code,
            "weight": _decimal_text(item.weight),
            "observed": item.observed,
            "raw_yuan": _decimal_text(item.raw_yuan),
            "contribution_yi": _decimal_text(item.contribution_yi),
            "evidence_refs": list(item.evidence_refs),
        }
    if isinstance(item, FinanceMetricMetricLineage):
        return {
            "lineage_type": "metric",
            "metric_id": item.metric_id,
            "weight": _decimal_text(item.weight),
            "metric_value_yi": _decimal_text(item.metric_value_yi),
            "contribution_yi": _decimal_text(item.contribution_yi),
            "dependency_status": item.dependency_status,
        }
    if isinstance(item, FinanceMetricManualLineage):
        return {
            "lineage_type": "manual",
            "supplied": item.supplied,
            "value_yi": _decimal_text(item.value_yi),
        }
    raise TypeError(f"Unsupported finance metric lineage type: {type(item).__name__}")


def _serialize_validation(item: FinanceMetricValidationResult) -> dict[str, Any]:
    return {
        "validation_id": item.id,
        "severity": item.severity,
        "passed": item.passed,
        "message": item.message,
        "delta_yi": _decimal_text(item.delta_yi),
        "sample": list(item.sample),
    }


def _metric_counts(metrics: tuple[FinanceMetricResult, ...]) -> dict[str, int]:
    return {
        "ok_count": sum(item.status == "ok" for item in metrics),
        "warning_count": sum(item.status == "warning" for item in metrics),
        "manual_default_count": sum(item.status == "manual_default" for item in metrics),
        "error_count": sum(item.status == "error" for item in metrics),
    }


def _validation_counts(
    validations: tuple[FinanceMetricValidationResult, ...],
) -> dict[str, int]:
    return {
        "validation_passed": sum(item.passed for item in validations),
        "validation_warning_failed": sum(
            not item.passed and item.severity == "warning" for item in validations
        ),
        "validation_error_failed": sum(
            not item.passed and item.severity == "error" for item in validations
        ),
    }


def _result_meta(
    *,
    report_month: str,
    report_date: date,
    source_version: str,
    rule_version: str,
    idempotency_key: str,
    calculation_status: str,
    include_lineage: bool,
    metric_id: str | None,
    tables_used: list[str],
    evidence_rows: int,
) -> dict[str, Any]:
    quality_flag = {
        "ready": "ok",
        "warning": "warning",
        "no_data": "warning",
        "error": "error",
    }[calculation_status]
    report_date_text = report_date.isoformat()
    return {
        "trace_id": f"tr_candidate_financial_indicators_{report_month}_{idempotency_key[:12]}",
        "basis": "ledger",
        "result_kind": "ledger_pnl.candidate_financial_indicators",
        "formal_use_allowed": False,
        "amount_currency_basis": "CNX",
        "amount_currency_basis_note": "候选规则固定使用综本 CNX 口径。",
        "source_version": source_version,
        "vendor_version": "vv_none",
        "rule_version": rule_version,
        "cache_version": CACHE_VERSION,
        "cache_key": idempotency_key,
        "quality_flag": quality_flag,
        "vendor_status": "ok",
        "fallback_mode": "none",
        "requested_report_date": report_month,
        "resolved_report_date": report_date_text,
        "scenario_flag": False,
        "as_of_date": report_date_text,
        "date_basis": "report_month_end",
        "fallback_date": None,
        "filters_applied": {
            "report_month": report_month,
            "include_lineage": include_lineage,
            "metric_id": metric_id,
        },
        "tables_used": tables_used,
        "evidence_rows": evidence_rows,
        "next_drill": [],
        "source_surface": None,
    }


def _locked_sha256(rules: dict[str, Any], file_name: str) -> str | None:
    for source in rules["metadata"].get("derived_from", []):
        if source.get("file") == file_name:
            value = source.get("sha256")
            return value if isinstance(value, str) else None
    return None


def _source_alignment(
    sources: list[dict[str, Any]],
) -> Literal["matched", "mismatch", "not_applicable", "incomplete"]:
    if not sources or any(not source["exists"] for source in sources):
        return "incomplete"
    comparisons = [
        source["locked_hash_match"]
        for source in sources
        if source["locked_sha256"] is not None
    ]
    if not comparisons:
        return "not_applicable"
    if any(match is False for match in comparisons):
        return "mismatch"
    return "matched"


def _tables_used(sources: list[dict[str, Any]]) -> list[str]:
    return list(
        dict.fromkeys(sheet for source in sources for sheet in source["sheets"])
    )


def _month_end(report_month: str) -> date:
    try:
        year = int(report_month[:4])
        month = int(report_month[4:])
        if len(report_month) != 6:
            raise ValueError
        return date(year, month, monthrange(year, month)[1])
    except (TypeError, ValueError) as exc:
        raise CandidateFinancialIndicatorRequestError(
            "Invalid report_month; expected a real YYYYMM month."
        ) from exc


def _decimal_text(value: Decimal | None) -> str | None:
    if value is None:
        return None
    if not value.is_finite():
        raise ValueError("finance metric response cannot serialize a non-finite Decimal")
    if value == 0:
        return "0"
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_version(
    report_month: str,
    ledger_hash: str,
    daily_hash: str,
    rule_hash: str,
) -> str:
    value = f"{report_month}:{ledger_hash}:{daily_hash}:{rule_hash}".encode()
    return f"sv_candidate_{hashlib.sha256(value).hexdigest()[:20]}"


def _state_key(
    *,
    report_month: str,
    rule_hash: str,
    sources: list[dict[str, Any]],
    include_lineage: bool,
    metric_id: str | None,
    status: str,
) -> str:
    payload = {
        "report_month": report_month,
        "rule_hash": rule_hash,
        "sources": [
            {
                "kind": source["source_kind"],
                "file_name": source["file_name"],
                "exists": source["exists"],
                "sha256": source["sha256"],
            }
            for source in sources
        ],
        "include_lineage": include_lineage,
        "metric_id": metric_id,
        "status": status,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9_.:-]+", "-", value.lower()).strip("-")
    return normalized or "unknown"
