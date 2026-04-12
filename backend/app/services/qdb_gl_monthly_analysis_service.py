from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from datetime import datetime, timezone
from uuid import uuid4
import csv
from io import StringIO

from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    GovernanceRepository,
)
from backend.app.schemas.materialize import CacheBuildRunRecord
from backend.app.core_finance.qdb_gl_monthly_analysis import (
    build_qdb_gl_monthly_analysis_workbook,
    export_qdb_gl_monthly_analysis_workbook_xlsx_bytes,
    merge_all,
    parse_daily_avg,
    parse_general_ledger,
)
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
ADJUSTMENT_STREAM = "monthly_operating_analysis_adjustments"


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
    workbook_payload, source_version = _rebuild_workbook_payload(
        source_dir=source_dir,
        governance_dir=governance_dir,
        report_month=report_month,
    )
    meta = build_analytical_result_meta(
        trace_id=f"tr_qdb_gl_monthly_analysis_workbook_{report_month}",
        result_kind="qdb-gl-monthly-analysis.workbook",
        cache_version=CACHE_VERSION,
        source_version=source_version,
        rule_version=RULE_VERSION,
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
    workbook_payload, source_version = _rebuild_workbook_payload(
        source_dir=source_dir,
        governance_dir=governance_dir,
        report_month=report_month,
        threshold_overrides=threshold_overrides,
    )
    applied_overrides = {key: value for key, value in (threshold_overrides or {}).items()}
    meta = build_analytical_result_meta(
        trace_id=f"tr_qdb_gl_monthly_analysis_scenario_{report_month}",
        result_kind="qdb-gl-monthly-analysis.scenario",
        cache_version=CACHE_VERSION,
        source_version=source_version,
        rule_version=RULE_VERSION,
        scenario_flag=True,
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
) -> dict[str, object]:
    _resolve_valid_month_pair(source_dir, report_month)
    run_id = f"{JOB_NAME}:{report_month}"
    repo = GovernanceRepository(base_dir=governance_dir)
    repo.append(
        CACHE_BUILD_RUN_STREAM,
        CacheBuildRunRecord(
            run_id=run_id,
            job_name=JOB_NAME,
            status="completed",
            cache_key="qdb_gl_monthly_analysis.analytical",
            cache_version=CACHE_VERSION,
            lock=LOCK_KEY,
            source_version=report_month,
            vendor_version="vv_none",
            rule_version=RULE_VERSION,
        ).model_dump(),
    )
    return {
        "status": "completed",
        "run_id": run_id,
        "job_name": JOB_NAME,
        "trigger_mode": "sync",
        "cache_key": "qdb_gl_monthly_analysis.analytical",
        "report_month": report_month,
    }


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
    return {
        **latest,
        "trigger_mode": "terminal" if str(latest.get("status")) == "completed" else "async",
    }


def create_qdb_gl_monthly_analysis_manual_adjustment(
    *,
    governance_dir: str | Path,
    payload: dict[str, Any],
) -> dict[str, object]:
    adjustment_id = f"moa-{uuid4()}"
    record = {
        "adjustment_id": adjustment_id,
        "event_type": "created",
        "created_at": datetime.now(timezone.utc).isoformat(),
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
        "created_at": datetime.now(timezone.utc).isoformat(),
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
        "created_at": datetime.now(timezone.utc).isoformat(),
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
        "created_at": datetime.now(timezone.utc).isoformat(),
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


def _resolve_valid_month_pair(source_dir: str | Path, report_month: str) -> tuple[Path, Path, str]:
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
    source_version = "__".join(sorted([avg_evidence.source_version, ledger_evidence.source_version]))
    return avg_binding.path, ledger_binding.path, source_version


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
) -> tuple[dict[str, Any], str]:
    avg_path, ledger_path, source_version = _resolve_valid_month_pair(source_dir, report_month)
    merged_data = merge_all(parse_general_ledger(ledger_path), parse_daily_avg(avg_path))
    active_adjustments = _load_active_adjustments(
        governance_dir=governance_dir,
        report_month=report_month,
    )
    _apply_mapping_adjustments(merged_data, active_adjustments)
    workbook_payload = build_qdb_gl_monthly_analysis_workbook(
        report_month=report_month,
        merged_data=merged_data,
        threshold_overrides=threshold_overrides,
    )
    _apply_analysis_adjustments(workbook_payload, active_adjustments)
    return workbook_payload, source_version


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
                _apply_mapping_field(row, field, adjustment.get("value"))


def _apply_mapping_field(row: dict[str, Any], field: str, value: Any) -> None:
    field_map = {
        "industry_name": ["琛屼笟鍚嶇О"],
        "category_name": ["鍚嶇О"],
        "account_name": ["绉戠洰鍚嶇О", "鍚嶇О"],
    }
    for candidate_key in field_map.get(field, []):
        if candidate_key in row:
            row[candidate_key] = value
            return


def _row_matches_code(row: dict[str, Any], account_code: str) -> bool:
    for value in row.values():
        text = str(value or "").strip()
        if text == account_code:
            return True
    return False


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
