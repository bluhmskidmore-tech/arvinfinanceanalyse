from __future__ import annotations

import csv
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from io import StringIO
from pathlib import Path
from typing import Any, NamedTuple
from uuid import uuid4

from backend.app.core_finance.qdb_gl_monthly_analysis import (
    build_qdb_gl_monthly_analysis_workbook,
    export_qdb_gl_monthly_analysis_workbook_xlsx_bytes,
    merge_all,
    parse_daily_avg,
    parse_general_ledger,
)
from backend.app.governance.locks import LockDefinition, acquire_lock
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    GovernanceRepository,
)
from backend.app.schemas.materialize import CacheBuildRunRecord
from backend.app.services.formal_result_runtime import (
    build_analytical_result_meta,
    build_formal_result_envelope,
)
from backend.app.services.qdb_gl_input_validation_service import (
    discover_qdb_gl_baseline_bindings,
    validate_qdb_gl_baseline_source,
)

RULE_VERSION = "rv_qdb_gl_monthly_analysis_v1"
CACHE_VERSION = "cv_qdb_gl_monthly_analysis_v1"
JOB_NAME = "qdb_gl_monthly_analysis"
LOCK_KEY = "lock:duckdb:qdb-gl-monthly-analysis"
CACHE_KEY = "qdb_gl_monthly_analysis.analytical"
FAILED_SOURCE_VERSION = "sv_qdb_gl_monthly_analysis_failed"
ADJUSTMENT_STREAM = "monthly_operating_analysis_adjustments"
REFRESH_LOCK_TIMEOUT_SECONDS = 30.0
QDB_SOURCE_TABLE_BY_KIND = {
    "average_balance": "qdb_gl_average_balance_workbook",
    "ledger_reconciliation": "qdb_gl_ledger_reconciliation_workbook",
}


class _ResolvedMonthPair(NamedTuple):
    avg_path: Path
    ledger_path: Path
    source_version: str
    tables_used: list[str]
    evidence_rows: int


def qdb_gl_monthly_analysis_dates_envelope(*, source_dir: str | Path) -> dict[str, object]:
    months = _discover_report_months(source_dir)
    meta = build_analytical_result_meta(
        trace_id="tr_qdb_gl_monthly_analysis_dates",
        result_kind="qdb-gl-monthly-analysis.dates",
        cache_version=CACHE_VERSION,
        source_version="__".join(months) if months else "sv_qdb_gl_monthly_analysis_empty",
        rule_version=RULE_VERSION,
    )
    return build_formal_result_envelope(result_meta=meta, result_payload={"report_months": months})


def qdb_gl_monthly_analysis_workbook_envelope(
    *,
    source_dir: str | Path,
    governance_dir: str | Path | None = None,
    report_month: str,
) -> dict[str, object]:
    workbook_payload, source_version, tables_used, evidence_rows, comparison_months = _rebuild_workbook_payload(
        source_dir=source_dir,
        governance_dir=governance_dir,
        report_month=report_month,
    )
    resolved_report_month = _require_matching_workbook_report_month(
        workbook_payload=workbook_payload,
        requested_report_month=report_month,
    )
    meta = build_analytical_result_meta(
        trace_id=f"tr_qdb_gl_monthly_analysis_workbook_{report_month}",
        result_kind="qdb-gl-monthly-analysis.workbook",
        cache_version=CACHE_VERSION,
        source_version=source_version,
        rule_version=RULE_VERSION,
        filters_applied=_monthly_analysis_filters(
            report_month=report_month,
            comparison_months=comparison_months,
        ),
        tables_used=tables_used,
        evidence_rows=evidence_rows,
        requested_report_date=report_month,
        resolved_report_date=resolved_report_month,
        date_basis="qdb_gl_monthly_analysis_report_month",
    )
    return build_formal_result_envelope(result_meta=meta, result_payload=workbook_payload)


def export_qdb_gl_monthly_analysis_workbook_xlsx(
    *,
    source_dir: str | Path,
    governance_dir: str | Path | None = None,
    report_month: str,
) -> tuple[str, bytes]:
    workbook_payload = qdb_gl_monthly_analysis_workbook_envelope(
        source_dir=source_dir,
        governance_dir=governance_dir,
        report_month=report_month,
    )["result"]
    return f"analysis_report_{report_month}.xlsx", export_qdb_gl_monthly_analysis_workbook_xlsx_bytes(workbook_payload)


def qdb_gl_monthly_analysis_scenario_envelope(
    *,
    source_dir: str | Path,
    governance_dir: str | Path | None = None,
    report_month: str,
    scenario_name: str,
    threshold_overrides: dict[str, int | float] | None = None,
) -> dict[str, object]:
    workbook_payload, source_version, tables_used, evidence_rows, comparison_months = _rebuild_workbook_payload(
        source_dir=source_dir,
        governance_dir=governance_dir,
        report_month=report_month,
        threshold_overrides=threshold_overrides,
    )
    resolved_report_month = _require_matching_workbook_report_month(
        workbook_payload=workbook_payload,
        requested_report_month=report_month,
    )
    applied_overrides = {key: value for key, value in (threshold_overrides or {}).items()}
    meta = build_analytical_result_meta(
        trace_id=f"tr_qdb_gl_monthly_analysis_scenario_{report_month}",
        result_kind="qdb-gl-monthly-analysis.scenario",
        cache_version=CACHE_VERSION,
        source_version=source_version,
        rule_version=RULE_VERSION,
        filters_applied=_monthly_analysis_filters(
            report_month=report_month,
            comparison_months=comparison_months,
        ),
        tables_used=tables_used,
        evidence_rows=evidence_rows,
        requested_report_date=report_month,
        resolved_report_date=resolved_report_month,
        date_basis="qdb_gl_monthly_analysis_report_month",
    )
    return build_formal_result_envelope(
        result_meta=meta,
        result_payload={
            **workbook_payload,
            "report_month": report_month,
            "scenario_name": scenario_name,
            "applied_overrides": applied_overrides,
        },
    )


def refresh_qdb_gl_monthly_analysis(
    *,
    source_dir: str | Path,
    governance_dir: str | Path,
    report_month: str,
    idempotency_key: str | None = None,
) -> dict[str, object]:
    normalized_idempotency_key = _normalize_idempotency_key(idempotency_key)
    repo = GovernanceRepository(base_dir=governance_dir)
    _require_month_pair_binding(source_dir, report_month)
    with acquire_lock(
        _refresh_trigger_lock(report_month=report_month),
        base_dir=governance_dir,
        timeout_seconds=REFRESH_LOCK_TIMEOUT_SECONDS,
    ):
        if normalized_idempotency_key is not None:
            existing_run = _latest_refresh_for_idempotency_key(
                repo,
                report_month=report_month,
                idempotency_key=normalized_idempotency_key,
            )
            if existing_run is not None:
                return _idempotent_refresh_response(existing_run)

        run_id = _build_run_id(report_month=report_month)
        try:
            workbook_payload, source_version, tables_used, evidence_rows, comparison_months = _rebuild_workbook_payload(
                source_dir=source_dir,
                governance_dir=governance_dir,
                report_month=report_month,
            )
            resolved_report_month = _require_matching_workbook_report_month(
                workbook_payload=workbook_payload,
                requested_report_month=report_month,
            )
        except Exception as exc:
            return _record_failed_refresh(
                repo=repo,
                run_id=run_id,
                report_month=report_month,
                idempotency_key=normalized_idempotency_key,
                exc=exc,
            )

        return _record_completed_refresh(
            repo=repo,
            run_id=run_id,
            report_month=report_month,
            resolved_report_month=resolved_report_month,
            source_version=source_version,
            workbook_payload=workbook_payload,
            tables_used=tables_used,
            evidence_rows=evidence_rows,
            comparison_months=comparison_months,
            idempotency_key=normalized_idempotency_key,
        )


def qdb_gl_monthly_analysis_refresh_status(
    *,
    governance_dir: str | Path,
    run_id: str,
) -> dict[str, object]:
    records = [
        record
        for record in GovernanceRepository(base_dir=governance_dir).read_all(CACHE_BUILD_RUN_STREAM)
        if str(record.get("job_name")) == JOB_NAME and str(record.get("run_id")) == run_id
    ]
    if not records:
        raise ValueError(f"Unknown qdb_gl_monthly_analysis run_id={run_id}")
    latest = records[-1]
    status = str(latest.get("status") or "")
    return {
        **latest,
        "trigger_mode": "async" if status in {"queued", "running"} else "terminal",
    }


def _normalize_idempotency_key(value: str | None) -> str | None:
    text = str(value or "").strip()
    return text or None


def _refresh_trigger_lock(*, report_month: str) -> LockDefinition:
    return LockDefinition(
        key=f"{LOCK_KEY}:{report_month}:trigger",
        ttl_seconds=30,
    )


def _require_month_pair_binding(source_dir: str | Path, report_month: str) -> None:
    if not _has_complete_month_pair_binding(_group_bindings(source_dir), report_month):
        raise ValueError(
            f"Missing QDB GL month pair for report_month={report_month}. "
            "Expected both ledger_reconciliation and average_balance source workbooks."
        )


def _latest_refresh_for_idempotency_key(
    repo: GovernanceRepository,
    *,
    report_month: str,
    idempotency_key: str,
) -> dict[str, object] | None:
    records = [
        record
        for record in repo.read_all(CACHE_BUILD_RUN_STREAM)
        if str(record.get("job_name")) == JOB_NAME
        and str(record.get("cache_key")) == CACHE_KEY
        and str(record.get("report_date")) == report_month
        and str(record.get("idempotency_key") or "").strip() == idempotency_key
    ]
    return records[-1] if records else None


def _idempotent_refresh_response(record: dict[str, object]) -> dict[str, object]:
    status = str(record.get("status") or "")
    return {
        **record,
        "job_name": JOB_NAME,
        "trigger_mode": "async" if status in {"queued", "running"} else "terminal",
        "cache_key": CACHE_KEY,
        "idempotency_replay": True,
    }


def _build_run_id(*, report_month: str) -> str:
    return f"{JOB_NAME}:{report_month}:{datetime.now(UTC).isoformat()}"


def _record_failed_refresh(
    *,
    repo: GovernanceRepository,
    run_id: str,
    report_month: str,
    idempotency_key: str | None,
    exc: Exception,
) -> dict[str, object]:
    error_message = _qdb_gl_monthly_analysis_build_error_message(
        report_month=report_month,
        exc=exc,
    )
    failed_record = CacheBuildRunRecord(
        run_id=run_id,
        job_name=JOB_NAME,
        status="failed",
        cache_key=CACHE_KEY,
        cache_version=CACHE_VERSION,
        lock=LOCK_KEY,
        source_version=FAILED_SOURCE_VERSION,
        vendor_version="vv_none",
        rule_version=RULE_VERSION,
        report_date=report_month,
        finished_at=datetime.now(UTC).isoformat(),
        error_message=error_message,
        failure_category="qdb_gl_monthly_analysis_build",
        failure_reason=type(exc).__name__,
    ).model_dump()
    failed_record["idempotency_key"] = idempotency_key
    repo.append(CACHE_BUILD_RUN_STREAM, failed_record)
    return {
        "status": "failed",
        "run_id": run_id,
        "job_name": JOB_NAME,
        "trigger_mode": "sync",
        "cache_key": CACHE_KEY,
        "report_month": report_month,
        "report_date": report_month,
        "source_version": FAILED_SOURCE_VERSION,
        "failure_category": failed_record["failure_category"],
        "failure_reason": failed_record["failure_reason"],
        "error_message": error_message,
        "idempotency_key": idempotency_key,
        "idempotency_replay": False,
    }


def _record_completed_refresh(
    *,
    repo: GovernanceRepository,
    run_id: str,
    report_month: str,
    resolved_report_month: str,
    source_version: str,
    workbook_payload: dict[str, Any],
    tables_used: list[str],
    evidence_rows: int,
    comparison_months: dict[str, dict[str, str]],
    idempotency_key: str | None,
) -> dict[str, object]:
    sheets = workbook_payload.get("sheets")
    sheet_count = len(sheets) if isinstance(sheets, list) else 0
    completed_record = CacheBuildRunRecord(
        run_id=run_id,
        job_name=JOB_NAME,
        status="completed",
        cache_key=CACHE_KEY,
        cache_version=CACHE_VERSION,
        lock=LOCK_KEY,
        source_version=source_version,
        vendor_version="vv_none",
        rule_version=RULE_VERSION,
        report_date=report_month,
        finished_at=datetime.now(UTC).isoformat(),
    ).model_dump()
    completed_record["idempotency_key"] = idempotency_key
    repo.append(CACHE_BUILD_RUN_STREAM, completed_record)
    return {
        "status": "completed",
        "run_id": run_id,
        "job_name": JOB_NAME,
        "trigger_mode": "sync",
        "cache_key": CACHE_KEY,
        "report_month": report_month,
        "report_date": report_month,
        "resolved_report_date": resolved_report_month,
        "source_version": source_version,
        "sheet_count": sheet_count,
        "tables_used": tables_used,
        "evidence_rows": evidence_rows,
        "comparison_months": comparison_months,
        "idempotency_key": idempotency_key,
        "idempotency_replay": False,
    }


def _qdb_gl_monthly_analysis_build_error_message(
    *,
    report_month: str,
    exc: Exception,
) -> str:
    message = str(exc).strip()
    if report_month in message:
        return message
    if message:
        return f"QDB GL monthly analysis refresh failed for report_month={report_month}: {message}"
    return f"QDB GL monthly analysis refresh failed for report_month={report_month}."


def create_qdb_gl_monthly_analysis_manual_adjustment(
    *,
    governance_dir: str | Path,
    payload: dict[str, Any],
) -> dict[str, object]:
    adjustment_id = f"moa-{uuid4()}"
    record = {
        "adjustment_id": adjustment_id,
        "event_type": "created",
        "created_at": datetime.now(UTC).isoformat(),
        "stream": ADJUSTMENT_STREAM,
        **payload,
    }
    GovernanceRepository(base_dir=governance_dir).append(ADJUSTMENT_STREAM, record)
    return record


def list_qdb_gl_monthly_analysis_manual_adjustments(
    *,
    governance_dir: str | Path,
    report_month: str,
) -> dict[str, object]:
    events = [row for row in GovernanceRepository(base_dir=governance_dir).read_all(ADJUSTMENT_STREAM) if str(row.get("report_month")) == report_month]
    latest_by_id: dict[str, dict[str, object]] = {}
    for event in events:
        adjustment_id = str(event.get("adjustment_id") or "")
        existing = latest_by_id.get(adjustment_id)
        if existing is None or str(event.get("created_at") or "") >= str(existing.get("created_at") or ""):
            latest_by_id[adjustment_id] = event
    return {
        "report_month": report_month,
        "adjustment_count": len(latest_by_id),
        "adjustments": list(latest_by_id.values()),
        "events": sorted(events, key=lambda row: str(row.get("created_at") or ""), reverse=True),
    }


def update_qdb_gl_monthly_analysis_manual_adjustment(
    *,
    governance_dir: str | Path,
    adjustment_id: str,
    payload: dict[str, Any],
) -> dict[str, object]:
    current = _require_adjustment(governance_dir=governance_dir, adjustment_id=adjustment_id)
    record = {
        **current,
        **payload,
        "adjustment_id": adjustment_id,
        "event_type": "edited",
        "created_at": datetime.now(UTC).isoformat(),
        "stream": ADJUSTMENT_STREAM,
    }
    GovernanceRepository(base_dir=governance_dir).append(ADJUSTMENT_STREAM, record)
    return record


def revoke_qdb_gl_monthly_analysis_manual_adjustment(
    *,
    governance_dir: str | Path,
    adjustment_id: str,
) -> dict[str, object]:
    current = _require_adjustment(governance_dir=governance_dir, adjustment_id=adjustment_id)
    record = {
        **current,
        "adjustment_id": adjustment_id,
        "event_type": "revoked",
        "created_at": datetime.now(UTC).isoformat(),
        "approval_status": "rejected",
        "stream": ADJUSTMENT_STREAM,
    }
    GovernanceRepository(base_dir=governance_dir).append(ADJUSTMENT_STREAM, record)
    return record


def restore_qdb_gl_monthly_analysis_manual_adjustment(
    *,
    governance_dir: str | Path,
    adjustment_id: str,
) -> dict[str, object]:
    current = _require_adjustment(governance_dir=governance_dir, adjustment_id=adjustment_id)
    record = {
        **current,
        "adjustment_id": adjustment_id,
        "event_type": "restored",
        "created_at": datetime.now(UTC).isoformat(),
        "approval_status": "approved",
        "stream": ADJUSTMENT_STREAM,
    }
    GovernanceRepository(base_dir=governance_dir).append(ADJUSTMENT_STREAM, record)
    return record


def export_qdb_gl_monthly_analysis_manual_adjustments_csv(
    *,
    governance_dir: str | Path,
    report_month: str,
) -> tuple[str, str]:
    payload = list_qdb_gl_monthly_analysis_manual_adjustments(
        governance_dir=governance_dir,
        report_month=report_month,
    )
    output = StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["adjustment_id", "event_type", "created_at", "report_month", "adjustment_class", "operator", "approval_status", "target", "value"],
        lineterminator="\n",
    )
    writer.writeheader()
    for event in payload["events"]:
        writer.writerow(
            {
                "adjustment_id": event.get("adjustment_id"),
                "event_type": event.get("event_type"),
                "created_at": event.get("created_at"),
                "report_month": event.get("report_month"),
                "adjustment_class": event.get("adjustment_class"),
                "operator": event.get("operator"),
                "approval_status": event.get("approval_status"),
                "target": str(event.get("target")),
                "value": event.get("value"),
            }
        )
    return f"monthly-operating-analysis-audit-{report_month}.csv", output.getvalue()


def _require_adjustment(*, governance_dir: str | Path, adjustment_id: str) -> dict[str, object]:
    events = GovernanceRepository(base_dir=governance_dir).read_all(ADJUSTMENT_STREAM)
    matching = [row for row in events if str(row.get("adjustment_id")) == adjustment_id]
    if not matching:
        raise ValueError(f"Unknown monthly_operating_analysis adjustment_id={adjustment_id}")
    matching.sort(key=lambda row: str(row.get("created_at") or ""))
    return matching[-1]


def _discover_report_months(source_dir: str | Path) -> list[str]:
    grouped = _group_bindings(source_dir)
    return sorted(month for month, kinds in grouped.items() if {"ledger_reconciliation", "average_balance"} <= set(kinds))


def _resolve_valid_month_pair(source_dir: str | Path, report_month: str) -> _ResolvedMonthPair:
    grouped = _group_bindings(source_dir)
    month_bindings = grouped.get(report_month)
    if not month_bindings or "average_balance" not in month_bindings or "ledger_reconciliation" not in month_bindings:
        raise ValueError(f"Missing canonical QDB GL month pair for report_month={report_month}.")

    avg_binding = month_bindings["average_balance"]
    ledger_binding = month_bindings["ledger_reconciliation"]
    avg_evidence = validate_qdb_gl_baseline_source(avg_binding.path)
    ledger_evidence = validate_qdb_gl_baseline_source(ledger_binding.path)
    if not avg_evidence.admissible or not ledger_evidence.admissible:
        raise ValueError(f"QDB GL month pair failed input-contract validation for report_month={report_month}.")
    evidences = [avg_evidence, ledger_evidence]
    source_version = "__".join(sorted([evidence.source_version for evidence in evidences]))
    tables_used = _tables_used_from_qdb_evidence(evidences)
    if set(tables_used) != set(QDB_SOURCE_TABLE_BY_KIND.values()):
        raise ValueError(f"QDB GL month pair source evidence is incomplete for report_month={report_month}.")
    return _ResolvedMonthPair(
        avg_path=avg_binding.path,
        ledger_path=ledger_binding.path,
        source_version=source_version,
        tables_used=tables_used,
        evidence_rows=len(evidences),
    )


def _tables_used_from_qdb_evidence(evidences: list[Any]) -> list[str]:
    return sorted(
        {
            table_name
            for evidence in evidences
            if (table_name := QDB_SOURCE_TABLE_BY_KIND.get(str(evidence.source_kind))) is not None
        }
    )


def _require_matching_workbook_report_month(
    *,
    workbook_payload: dict[str, Any],
    requested_report_month: str,
) -> str:
    resolved_report_month = str(workbook_payload.get("report_month") or "").strip()
    if resolved_report_month != requested_report_month:
        returned = resolved_report_month or "<missing>"
        raise ValueError(
            "QDB GL monthly analysis workbook report_month mismatch: "
            f"requested {requested_report_month}, rebuilt {returned}."
        )
    return resolved_report_month


def _monthly_analysis_filters(
    *,
    report_month: str,
    comparison_months: dict[str, dict[str, str]],
) -> dict[str, object]:
    return {
        "report_month": report_month,
        "comparison_months": comparison_months,
    }


def _group_bindings(source_dir: str | Path) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for binding in discover_qdb_gl_baseline_bindings(source_dir):
        grouped.setdefault(binding.report_month, {})[binding.source_kind] = binding
    return grouped


def _rebuild_workbook_payload(
    *,
    source_dir: str | Path,
    governance_dir: str | Path | None,
    report_month: str,
    threshold_overrides: dict[str, int | float] | None = None,
) -> tuple[dict[str, Any], str, list[str], int, dict[str, dict[str, str]]]:
    resolved_pair = _resolve_valid_month_pair(source_dir, report_month)
    merged_data = merge_all(
        parse_general_ledger(resolved_pair.ledger_path),
        parse_daily_avg(resolved_pair.avg_path),
    )
    (
        comparison_data,
        comparison_source_versions,
        comparison_tables_used,
        comparison_evidence_rows,
        comparison_months,
    ) = _load_comparison_merged_data(
        source_dir=source_dir,
        report_month=report_month,
    )
    active_adjustments = _load_active_adjustments(
        governance_dir=governance_dir,
        report_month=report_month,
    )
    _apply_mapping_adjustments(merged_data, active_adjustments)
    workbook_payload = build_qdb_gl_monthly_analysis_workbook(
        report_month=report_month,
        merged_data=merged_data,
        threshold_overrides=threshold_overrides,
        comparison_data=comparison_data,
    )
    _apply_analysis_adjustments(workbook_payload, active_adjustments)
    all_source_versions = [resolved_pair.source_version, *comparison_source_versions]
    return (
        workbook_payload,
        "__".join(sorted(all_source_versions)),
        sorted({*resolved_pair.tables_used, *comparison_tables_used}),
        resolved_pair.evidence_rows + comparison_evidence_rows,
        comparison_months,
    )


def _load_comparison_merged_data(
    *,
    source_dir: str | Path,
    report_month: str,
) -> tuple[dict[str, dict[str, Any]], list[str], list[str], int, dict[str, dict[str, str]]]:
    comparison_months = {
        "prior_month": _shift_report_month(report_month, -1),
        "two_months_ago": _shift_report_month(report_month, -2),
        "prior_year": _shift_report_month(report_month, -12),
    }
    grouped = _group_bindings(source_dir)
    comparison_data: dict[str, dict[str, Any]] = {}
    source_versions: list[str] = []
    tables_used: list[str] = []
    evidence_rows = 0
    month_statuses: dict[str, dict[str, str]] = {}
    for comparison_key, comparison_month in comparison_months.items():
        if comparison_month is None:
            month_statuses[comparison_key] = {"report_month": "", "status": "missing"}
            continue
        try:
            resolved_pair = _resolve_valid_month_pair(source_dir, comparison_month)
        except ValueError:
            status = "invalid" if _has_complete_month_pair_binding(grouped, comparison_month) else "missing"
            month_statuses[comparison_key] = {"report_month": comparison_month, "status": status}
            continue
        comparison_data[comparison_key] = merge_all(
            parse_general_ledger(resolved_pair.ledger_path),
            parse_daily_avg(resolved_pair.avg_path),
        )
        source_versions.append(f"{comparison_key}:{comparison_month}:{resolved_pair.source_version}")
        tables_used.extend(resolved_pair.tables_used)
        evidence_rows += resolved_pair.evidence_rows
        month_statuses[comparison_key] = {"report_month": comparison_month, "status": "loaded"}
    return comparison_data, source_versions, sorted(set(tables_used)), evidence_rows, month_statuses


def _has_complete_month_pair_binding(grouped: dict[str, dict[str, Any]], report_month: str) -> bool:
    month_bindings = grouped.get(report_month) or {}
    return {"average_balance", "ledger_reconciliation"} <= set(month_bindings)


def _shift_report_month(report_month: str, month_delta: int) -> str | None:
    if len(report_month) != 6 or not report_month.isdigit():
        return None
    year = int(report_month[:4])
    month = int(report_month[4:])
    if month < 1 or month > 12:
        return None
    month_index = year * 12 + month - 1 + month_delta
    shifted_year = month_index // 12
    shifted_month = month_index % 12 + 1
    return f"{shifted_year:04d}{shifted_month:02d}"


def _load_active_adjustments(
    *,
    governance_dir: str | Path | None,
    report_month: str,
) -> list[dict[str, Any]]:
    if governance_dir is None:
        return []
    payload = list_qdb_gl_monthly_analysis_manual_adjustments(
        governance_dir=governance_dir,
        report_month=report_month,
    )
    return [
        adjustment
        for adjustment in payload["adjustments"]
        if str(adjustment.get("approval_status") or "") == "approved"
    ]


def _apply_mapping_adjustments(
    merged_data: dict[str, Any],
    adjustments: list[dict[str, Any]],
) -> None:
    for adjustment in adjustments:
        if str(adjustment.get("adjustment_class") or "") != "mapping_adjustment":
            continue
        target = adjustment.get("target")
        if not isinstance(target, dict):
            continue
        field = str(target.get("field") or "")
        account_code = str(target.get("account_code") or "")
        if not field or not account_code:
            continue
        for rows in merged_data.values():
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                if not _row_matches_code(row, account_code):
                    continue
                _apply_mapping_field_structured(row, field, adjustment.get("value"))


def _row_matches_code(row: dict[str, Any], account_code: str) -> bool:
    for value in row.values():
        text = str(value or "").strip()
        if text == account_code:
            return True
    return False


def _apply_mapping_field_structured(row: dict[str, Any], field: str, value: Any) -> None:
    field_map = {
        "industry_name": ["行业名称"],
        "category_name": ["名称"],
        "account_name": ["科目名称", "名称"],
    }
    for candidate_key in field_map.get(field, []):
        if candidate_key in row:
            row[candidate_key] = value
            return


def _apply_analysis_adjustments(
    workbook_payload: dict[str, Any],
    adjustments: list[dict[str, Any]],
) -> None:
    sheets = workbook_payload.get("sheets")
    if not isinstance(sheets, list):
        return
    sheets_by_key = {
        str(sheet.get("key") or ""): sheet
        for sheet in sheets
        if isinstance(sheet, dict)
    }
    for adjustment in adjustments:
        if str(adjustment.get("adjustment_class") or "") != "analysis_adjustment":
            continue
        target = adjustment.get("target")
        if not isinstance(target, dict):
            continue
        section_key = str(target.get("section_key") or "")
        row_key = str(target.get("row_key") or "")
        metric_key = str(target.get("metric_key") or "")
        sheet = sheets_by_key.get(section_key)
        if not section_key or not row_key or not metric_key or not isinstance(sheet, dict):
            continue
        rows = sheet.get("rows")
        columns = sheet.get("columns")
        if not isinstance(rows, list) or not isinstance(columns, list) or not columns:
            continue
        row = next(
            (
                candidate
                for candidate in rows
                if isinstance(candidate, dict)
                and str(candidate.get(columns[0]) or "") == row_key
            ),
            None,
        )
        if row is None:
            continue
        column_name = _resolve_metric_column_name(section_key=section_key, metric_key=metric_key, columns=columns)
        if column_name is None:
            continue
        row[column_name] = _apply_adjustment_operator(
            existing=row.get(column_name),
            operator=str(adjustment.get("operator") or "OVERRIDE"),
            value=adjustment.get("value"),
        )


def _resolve_metric_column_name(
    *,
    section_key: str,
    metric_key: str,
    columns: list[Any],
) -> Any | None:
    column_index_map = {
        ("overview", "value"): 1,
        ("alerts", "alert_level"): 2,
    }
    direct_match = next((column for column in columns if str(column) == metric_key), None)
    if direct_match is not None:
        return direct_match
    column_index = column_index_map.get((section_key, metric_key))
    if column_index is None or column_index >= len(columns):
        return None
    return columns[column_index]


def _apply_adjustment_operator(*, existing: Any, operator: str, value: Any) -> Any:
    if operator == "OVERRIDE":
        return value
    existing_number = _coerce_decimal(existing)
    value_number = _coerce_decimal(value)
    if existing_number is None or value_number is None:
        return value
    if operator == "DELTA":
        result = existing_number + value_number
        return int(result) if result == result.to_integral_value() else float(result)
    if operator == "ADD" and existing in (None, ""):
        return value
    return value


def _coerce_decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
