from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from backend.app.repositories.governance_repo import CACHE_BUILD_RUN_STREAM, GovernanceRepository
from backend.app.repositories.job_state_repo import JobStateRepository

logger = logging.getLogger(__name__)

LEDGER_IMPORT_JOB_NAME = "ledger_import"
LEDGER_IMPORT_CACHE_KEY = "ledger_import"
LEDGER_IMPORT_TERMINAL_OUTBOX_STREAM = "ledger_import_terminal_outbox"
PUBLIC_FIELDS = (
    "run_id",
    "status",
    "trigger_mode",
    "file_name",
    "batch_id",
    "duplicate_of_batch_id",
    "queued_at",
    "started_at",
    "finished_at",
    "error_category",
    "error_message",
)


class LedgerImportRunNotFoundError(LookupError):
    pass


def normalize_ledger_import_file_name(file_name: str) -> str:
    return Path(str(file_name or "").replace("\\", "/")).name


def record_ledger_import_terminal_outbox(
    *,
    governance_dir: str | Path,
    run_id: str,
    file_name: str,
    status: str,
    outcome: str | None,
    batch_id: int | None,
    duplicate_of_batch_id: int | None,
    source_version: str,
    rule_version: str,
    error_category: str | None,
    error_message: str | None,
    governance_backend: str = "jsonl",
    governance_sql_dsn: str = "",
) -> dict[str, object]:
    now = datetime.now(UTC).isoformat()
    facts: dict[str, object] = {
        "run_id": run_id,
        "file_name": normalize_ledger_import_file_name(file_name),
        "status": status,
        "outcome": outcome,
        "batch_id": batch_id,
        "duplicate_of_batch_id": duplicate_of_batch_id,
        "source_version": source_version or None,
        "rule_version": rule_version or None,
        "error_category": error_category,
        "error_message": error_message,
        "finished_at": now,
        "created_at": now,
    }
    GovernanceRepository(
        base_dir=governance_dir,
        sql_dsn=governance_sql_dsn,
        backend_mode=governance_backend,
    ).append(LEDGER_IMPORT_TERMINAL_OUTBOX_STREAM, facts)
    return facts


def get_ledger_import_terminal_outbox(
    *,
    governance_dir: str | Path,
    run_id: str,
    governance_backend: str = "jsonl",
    governance_sql_dsn: str = "",
) -> dict[str, object]:
    rows = GovernanceRepository(
        base_dir=governance_dir,
        sql_dsn=governance_sql_dsn,
        backend_mode=governance_backend,
    ).read_all(LEDGER_IMPORT_TERMINAL_OUTBOX_STREAM)
    selected: dict[str, object] | None = None
    selected_priority = -1
    for row in rows:
        if row.get("run_id") != run_id:
            continue
        priority = _terminal_fact_priority(row)
        if priority >= selected_priority:
            selected = row
            selected_priority = priority
    if selected is not None:
        return selected
    raise LedgerImportRunNotFoundError(run_id)


def _terminal_fact_priority(record: dict[str, object]) -> int:
    if record.get("status") == "completed" and record.get("outcome") == "success":
        return 3
    if record.get("status") == "completed" and record.get("outcome") == "duplicate":
        return 2
    return 1


def record_ledger_import_transition(
    *,
    governance_dir: str | Path,
    governance_backend: str,
    governance_sql_dsn: str,
    job_state_dsn: str,
    run_id: str,
    status: str,
    file_name: str,
    outcome: str | None = None,
    batch_id: int | None = None,
    duplicate_of_batch_id: int | None = None,
    source_version: str = "",
    rule_version: str = "",
    error_category: str | None = None,
    error_message: str | None = None,
) -> dict[str, object]:
    if status not in {"queued", "running", "completed", "failed"}:
        raise ValueError(f"Unsupported Ledger import run status: {status}")
    if status == "completed" and outcome not in {"success", "duplicate"}:
        raise ValueError("Completed Ledger import run requires success or duplicate outcome.")

    now = datetime.now(UTC).isoformat()
    payload: dict[str, object] = {
        "run_id": str(run_id),
        "job_name": LEDGER_IMPORT_JOB_NAME,
        "cache_key": LEDGER_IMPORT_CACHE_KEY,
        "status": status,
        "trigger_mode": "api",
        "file_name": normalize_ledger_import_file_name(file_name),
        "outcome": outcome,
        "batch_id": batch_id,
        "duplicate_of_batch_id": duplicate_of_batch_id,
        "source_version": source_version or None,
        "rule_version": rule_version or None,
        "vendor_version": None,
        "error_category": error_category,
        "error_message": error_message,
        "failure_category": error_category,
        "failure_reason": error_message,
        "queued_at": now if status == "queued" else None,
        "started_at": now if status == "running" else None,
        "finished_at": now if status in {"completed", "failed"} else None,
        "created_at": now,
    }
    GovernanceRepository(
        base_dir=governance_dir,
        sql_dsn=governance_sql_dsn,
        backend_mode=governance_backend,
    ).append(CACHE_BUILD_RUN_STREAM, payload)
    _mirror_job_state(payload, job_state_dsn=job_state_dsn)
    return payload


def get_ledger_import_run_status(
    *,
    governance_dir: str | Path,
    governance_backend: str,
    governance_sql_dsn: str,
    run_id: str,
) -> dict[str, object]:
    records = GovernanceRepository(
        base_dir=governance_dir,
        sql_dsn=governance_sql_dsn,
        backend_mode=governance_backend,
    ).read_all(CACHE_BUILD_RUN_STREAM)
    matching = [
        row
        for row in records
        if row.get("run_id") == run_id
        and row.get("job_name") == LEDGER_IMPORT_JOB_NAME
        and row.get("cache_key") == LEDGER_IMPORT_CACHE_KEY
    ]
    reduced = _reduce_transitions(matching)
    if reduced is None:
        raise LedgerImportRunNotFoundError(run_id)

    public = dict(reduced)
    public["status"] = _public_status(reduced)
    return {field: public[field] for field in PUBLIC_FIELDS if public.get(field) is not None}


def _reduce_transitions(records: list[dict[str, object]]) -> dict[str, object] | None:
    current: dict[str, object] | None = None
    for record in records:
        if current is not None and not _may_supersede(current, record):
            continue
        merged = dict(current or {})
        merged.update({key: value for key, value in record.items() if value is not None})
        next_status = record.get("status")
        if next_status != "failed":
            merged.pop("error_category", None)
            merged.pop("error_message", None)
        if next_status in {"queued", "running"}:
            merged.pop("finished_at", None)
        if next_status == "completed" and record.get("outcome") == "success":
            merged.pop("duplicate_of_batch_id", None)
        current = merged
    return current


def _may_supersede(current: dict[str, object], candidate: dict[str, object]) -> bool:
    current_status = str(current.get("status") or "")
    current_outcome = str(current.get("outcome") or "")
    next_status = str(candidate.get("status") or "")
    next_outcome = str(candidate.get("outcome") or "")
    if current_status == "completed" and current_outcome == "success":
        return False
    if current_status == "completed" and current_outcome == "duplicate":
        return next_status == "completed" and next_outcome == "success"
    if next_status == "queued" and current_status:
        return False
    return True


def _public_status(record: dict[str, object]) -> str:
    status = str(record.get("status") or "")
    if status == "completed":
        return "duplicate" if record.get("outcome") == "duplicate" else "succeeded"
    return status


def _mirror_job_state(payload: dict[str, object], *, job_state_dsn: str) -> None:
    if not str(job_state_dsn or "").strip():
        return
    try:
        JobStateRepository(job_state_dsn).record_transition(
            run_id=str(payload["run_id"]),
            job_name=LEDGER_IMPORT_JOB_NAME,
            cache_key=LEDGER_IMPORT_CACHE_KEY,
            status=str(payload["status"]),
            report_date=None,
            source_version=str(payload.get("source_version") or ""),
            vendor_version="",
            rule_version=str(payload.get("rule_version") or "") or None,
            error_message=str(payload.get("error_message") or "") or None,
            queued_at=str(payload.get("queued_at") or "") or None,
            started_at=str(payload.get("started_at") or "") or None,
            finished_at=str(payload.get("finished_at") or "") or None,
        )
    except Exception as exc:
        logger.warning(
            "Ledger import JobState mirror failed error_type=%s.",
            type(exc).__name__,
        )
