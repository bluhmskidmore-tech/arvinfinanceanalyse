from __future__ import annotations

import contextlib
import io
import os
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
from backend.app.core_finance.macro.toolkit.paths import OUTPUT_DIR
from backend.app.core_finance.macro.toolkit.runner import (
    PROJECT_ROOT,
    TOOLKIT_ROOT,
    get_toolkit_script,
    run_toolkit_script,
)
from backend.app.governance.locks import LockDefinition, acquire_lock
from backend.app.repositories.governance_repo import CACHE_BUILD_RUN_STREAM, GovernanceRepository
from backend.app.security.auth_context import AuthContext
from backend.app.services.cffex_member_rank_service import materialize_cffex_member_rank
from backend.app.tasks.choice_stock_materialize import (
    materialize_choice_stock_factor_snapshot,
    materialize_choice_stock_inputs,
)
from fastapi import BackgroundTasks

CHOICE_STOCK_REFRESH_JOB_NAME = "choice_stock_refresh"
CHOICE_STOCK_REFRESH_CACHE_KEY = "choice_stock.history_and_factor_snapshot"
CHOICE_STOCK_REFRESH_CACHE_VERSION = "choice_stock_refresh_v1"
CHOICE_STOCK_REFRESH_LOCK = "lock:choice_stock_refresh"
CHOICE_STOCK_REFRESH_RULE_VERSION = "rv_choice_stock_materialization_front_layer_v1"
_CHOICE_STOCK_REFRESH_IN_FLIGHT_STATUSES = {"queued", "running"}


@dataclass(frozen=True)
class MacroToolkitActionResult:
    payload: dict[str, object]
    quality_flag: str = "ok"
    fallback_mode: str = "none"
    as_of_date: str | None = None


class MacroToolkitConflictError(RuntimeError):
    pass


def run_macro_toolkit_script(
    *,
    name: str,
    argv: list[str],
    timeout_seconds: int,
) -> dict[str, object]:
    script = get_toolkit_script(name)
    env = os.environ.copy()
    existing_python_path = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(TOOLKIT_ROOT), str(PROJECT_ROOT), existing_python_path) if part
    )
    try:
        completed = subprocess.run(
            [sys.executable, str(script.path), *argv],
            cwd=str(TOOLKIT_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "timeout",
            "script": _script_payload(script.name, script.filename, script.group, script.default_data_sources, script.optional_dependencies, script.notes, script.path),
            "exit_code": None,
            "stdout": _tail_text(exc.stdout),
            "stderr": _tail_text(exc.stderr),
            "output_files": _output_files(),
            "message": f"script exceeded {timeout_seconds}s timeout",
        }
    except OSError as exc:
        stdout_text, stderr_text, exit_code = _run_toolkit_script_inline(script.name, argv)
        return {
            "status": "completed" if exit_code == 0 else "failed",
            "script": _script_payload(script.name, script.filename, script.group, script.default_data_sources, script.optional_dependencies, script.notes, script.path),
            "exit_code": exit_code,
            "stdout": _tail_text(stdout_text),
            "stderr": _tail_text(f"{stderr_text}\nsubprocess fallback: {exc}".strip()),
            "output_files": _output_files(),
        }

    return {
        "status": "completed" if completed.returncode == 0 else "failed",
        "script": _script_payload(script.name, script.filename, script.group, script.default_data_sources, script.optional_dependencies, script.notes, script.path),
        "exit_code": completed.returncode,
        "stdout": _tail_text(completed.stdout),
        "stderr": _tail_text(completed.stderr),
        "output_files": _output_files(),
    }


def refresh_cffex_member_rank(
    *,
    duckdb_path: str | Path,
    trade_date: str | None,
    contracts: tuple[str, ...],
    sources: tuple[str, ...],
) -> MacroToolkitActionResult:
    payload = materialize_cffex_member_rank(
        duckdb_path=duckdb_path,
        trade_date=trade_date,
        contracts=contracts,
        sources=sources,
    )
    return MacroToolkitActionResult(
        payload=payload,
        quality_flag="ok" if int(payload.get("row_count") or 0) > 0 else "warning",
        fallback_mode="none",
        as_of_date=_optional_text(payload.get("trade_date")),
    )


def queue_choice_stock_refresh(
    *,
    background_tasks: BackgroundTasks,
    duckdb_path: str,
    catalog_path: str,
    governance_path: str,
    as_of_date: str,
    refresh_history: bool,
    refresh_factors: bool,
    factor_max_stock_count: int | None,
    permission: dict[str, object],
) -> MacroToolkitActionResult:
    try:
        with acquire_lock(
            _choice_stock_refresh_trigger_lock(as_of_date=as_of_date),
            base_dir=governance_path,
            timeout_seconds=0.1,
        ):
            existing = latest_choice_stock_inflight_refresh(governance_path, as_of_date=as_of_date)
            if existing is not None:
                raise MacroToolkitConflictError(
                    f"Choice stock refresh already in progress for as_of_date={as_of_date}."
                )

            queued_at = datetime.now(UTC).isoformat()
            run_id = f"{CHOICE_STOCK_REFRESH_JOB_NAME}:{as_of_date}:{uuid.uuid4().hex[:12]}"
            queued_payload = build_choice_stock_refresh_run_payload(
                run_id=run_id,
                status="queued",
                as_of_date=as_of_date,
                queued_at=queued_at,
                refresh_history=refresh_history,
                refresh_factors=refresh_factors,
                factor_max_stock_count=factor_max_stock_count,
                permission=permission,
            )
            append_choice_stock_refresh_run(governance_path, queued_payload)
            background_tasks.add_task(
                _run_choice_stock_refresh_job,
                duckdb_path=duckdb_path,
                catalog_path=catalog_path,
                governance_path=governance_path,
                run_id=run_id,
                as_of_date=as_of_date,
                queued_at=queued_at,
                refresh_history=refresh_history,
                refresh_factors=refresh_factors,
                factor_max_stock_count=factor_max_stock_count,
                permission=permission,
            )
    except TimeoutError as exc:
        raise MacroToolkitConflictError(
            f"Choice stock refresh already in progress for as_of_date={as_of_date}."
        ) from exc

    return MacroToolkitActionResult(
        payload=queued_payload,
        quality_flag="ok",
        fallback_mode="none",
        as_of_date=as_of_date,
    )


def append_choice_stock_refresh_run(governance_path: str | Path, payload: dict[str, object]) -> None:
    GovernanceRepository(base_dir=governance_path).append(CACHE_BUILD_RUN_STREAM, payload)


def build_choice_stock_refresh_run_payload(
    *,
    run_id: str,
    status: str,
    as_of_date: str,
    queued_at: str | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
    refresh_history: bool = True,
    refresh_factors: bool = True,
    factor_max_stock_count: int | None = None,
    history_row_count: int | None = None,
    factor_row_count: int | None = None,
    source_version: object | None = None,
    vendor_version: object | None = None,
    error_message: str | None = None,
    failure_category: str | None = None,
    failure_reason: str | None = None,
    permission: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "run_id": run_id,
        "job_name": CHOICE_STOCK_REFRESH_JOB_NAME,
        "status": status,
        "cache_key": CHOICE_STOCK_REFRESH_CACHE_KEY,
        "cache_version": CHOICE_STOCK_REFRESH_CACHE_VERSION,
        "lock": CHOICE_STOCK_REFRESH_LOCK,
        "source_version": _optional_text(source_version),
        "vendor_version": _optional_text(vendor_version),
        "rule_version": CHOICE_STOCK_REFRESH_RULE_VERSION,
        "report_date": as_of_date,
        "queued_at": queued_at,
        "started_at": started_at,
        "finished_at": finished_at,
        "error_message": error_message,
        "failure_category": failure_category,
        "failure_reason": failure_reason,
        "created_at": datetime.now(UTC).isoformat(),
        "refresh_history": refresh_history,
        "refresh_factors": refresh_factors,
        "factor_max_stock_count": factor_max_stock_count,
        "history_row_count": history_row_count,
        "factor_row_count": factor_row_count,
        "permission": permission or build_choice_stock_refresh_permission_payload(),
        "trigger_mode": _choice_stock_refresh_trigger_mode(status),
    }


def choice_stock_refresh_status(
    governance_path: str | Path,
    *,
    run_id: str = "",
) -> dict[str, object]:
    run_id_text = str(run_id or "").strip()
    records = _choice_stock_refresh_records(governance_path)
    if run_id_text:
        matching = [record for record in records if str(record.get("run_id") or "") == run_id_text]
        if not matching:
            raise ValueError(f"Choice stock refresh run not found: {run_id_text}")
        return _normalize_choice_stock_refresh_record(matching[-1])
    if not records:
        return {
            "status": "idle",
            "run_id": None,
            "job_name": CHOICE_STOCK_REFRESH_JOB_NAME,
            "cache_key": CHOICE_STOCK_REFRESH_CACHE_KEY,
            "trigger_mode": "idle",
            "permission": build_choice_stock_refresh_permission_payload(),
        }
    return _normalize_choice_stock_refresh_record(records[-1])


def choice_stock_refresh_overview(
    duckdb_path: str | Path,
    governance_path: str | Path,
    *,
    permission: dict[str, object] | None = None,
    reference_date: str | None = None,
) -> dict[str, object]:
    return {
        "permission": permission or build_choice_stock_refresh_permission_payload(),
        "refresh": choice_stock_refresh_status(governance_path),
        "daily_observation": _choice_stock_daily_observation_status(duckdb_path, reference_date=reference_date),
        "factor_snapshot": _choice_stock_factor_snapshot_status(duckdb_path, reference_date=reference_date),
        "default_factor_max_stock_count": None,
    }


def latest_choice_stock_inflight_refresh(
    governance_path: str | Path,
    *,
    as_of_date: str,
) -> dict[str, object] | None:
    by_run_id: dict[str, dict[str, object]] = {}
    for record in _choice_stock_refresh_records(governance_path):
        if str(record.get("report_date") or "") != as_of_date:
            continue
        by_run_id[str(record.get("run_id") or "")] = record
    for record in reversed(list(by_run_id.values())):
        if str(record.get("status") or "") in _CHOICE_STOCK_REFRESH_IN_FLIGHT_STATUSES:
            return record
    return None


def build_choice_stock_refresh_permission_payload(auth: AuthContext | None = None) -> dict[str, object]:
    return {
        "mode": "scoped_refresh",
        "allowed": True,
        "user_id": auth.user_id if auth else None,
        "role": auth.role if auth else None,
        "identity_source": auth.identity_source if auth else None,
        "resource": "macro_toolkit.choice_stock",
        "actions": ["history", "factor_snapshot"],
    }


def default_choice_stock_refresh_as_of_date(duckdb_path: str | Path) -> str:
    path = Path(duckdb_path)
    if path.exists():
        try:
            conn = duckdb.connect(str(path), read_only=True)
            try:
                if _duckdb_table_exists(conn, "choice_stock_daily_observation"):
                    row = conn.execute("select max(trade_date) from choice_stock_daily_observation").fetchone()
                    if row and row[0] is not None:
                        return str(row[0])[:10]
            finally:
                conn.close()
        except duckdb.Error:
            pass
    return date.today().isoformat()


def _run_choice_stock_refresh_job(
    *,
    duckdb_path: str,
    catalog_path: str,
    governance_path: str,
    run_id: str,
    as_of_date: str,
    queued_at: str,
    refresh_history: bool,
    refresh_factors: bool,
    factor_max_stock_count: int | None,
    permission: dict[str, object],
) -> None:
    started_at = datetime.now(UTC).isoformat()
    append_choice_stock_refresh_run(
        governance_path,
        build_choice_stock_refresh_run_payload(
            run_id=run_id,
            status="running",
            as_of_date=as_of_date,
            queued_at=queued_at,
            started_at=started_at,
            refresh_history=refresh_history,
            refresh_factors=refresh_factors,
            factor_max_stock_count=factor_max_stock_count,
            permission=permission,
        ),
    )
    history_result: dict[str, object] | None = None
    factor_result: dict[str, object] | None = None
    try:
        if refresh_history:
            history_result = materialize_choice_stock_inputs(
                as_of_date=as_of_date,
                duckdb_path=duckdb_path,
                catalog_path=catalog_path,
            )
        if refresh_factors:
            factor_result = materialize_choice_stock_factor_snapshot(
                as_of_date=as_of_date,
                duckdb_path=duckdb_path,
                max_stock_count=factor_max_stock_count,
            )
        append_choice_stock_refresh_run(
            governance_path,
            build_choice_stock_refresh_run_payload(
                run_id=run_id,
                status="completed",
                as_of_date=as_of_date,
                queued_at=queued_at,
                started_at=started_at,
                finished_at=datetime.now(UTC).isoformat(),
                refresh_history=refresh_history,
                refresh_factors=refresh_factors,
                factor_max_stock_count=factor_max_stock_count,
                history_row_count=_result_row_count(history_result),
                factor_row_count=_result_row_count(factor_result),
                source_version=_latest_result_field("source_version", factor_result, history_result),
                vendor_version=_latest_result_field("vendor_version", factor_result, history_result),
                permission=permission,
            ),
        )
    except Exception as exc:
        append_choice_stock_refresh_run(
            governance_path,
            build_choice_stock_refresh_run_payload(
                run_id=run_id,
                status="failed",
                as_of_date=as_of_date,
                queued_at=queued_at,
                started_at=started_at,
                finished_at=datetime.now(UTC).isoformat(),
                refresh_history=refresh_history,
                refresh_factors=refresh_factors,
                factor_max_stock_count=factor_max_stock_count,
                history_row_count=_result_row_count(history_result),
                factor_row_count=_result_row_count(factor_result),
                source_version=_latest_result_field("source_version", factor_result, history_result),
                vendor_version=_latest_result_field("vendor_version", factor_result, history_result),
                error_message=f"{type(exc).__name__}: {exc}",
                failure_category=type(exc).__name__,
                failure_reason=str(exc),
                permission=permission,
            ),
        )


def _run_toolkit_script_inline(name: str, argv: list[str]) -> tuple[str, str, int]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            run_toolkit_script(name, argv)
    except Exception as exc:  # pragma: no cover - returned to UI as script stderr
        stderr.write(f"\ninline runner failed: {exc}")
        return stdout.getvalue(), stderr.getvalue(), 1
    return stdout.getvalue(), stderr.getvalue(), 0


def _script_payload(
    name: str,
    filename: str,
    group: str,
    default_data_sources: tuple[str, ...],
    optional_dependencies: tuple[str, ...],
    notes: str,
    path: Path,
) -> dict[str, object]:
    return {
        "name": name,
        "filename": filename,
        "group": group,
        "default_data_sources": list(default_data_sources),
        "optional_dependencies": list(optional_dependencies),
        "notes": notes,
        "path": str(path.relative_to(TOOLKIT_ROOT)),
        "available": path.exists(),
    }


def _output_files() -> list[dict[str, object]]:
    if not OUTPUT_DIR.exists():
        return []
    files: list[dict[str, object]] = []
    for path in sorted(OUTPUT_DIR.glob("*")):
        if not path.is_file():
            continue
        stat = path.stat()
        files.append(
            {
                "name": path.name,
                "path": str(path),
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
            }
        )
    return files


def _tail_text(value: str | bytes | None, limit: int = 12000) -> str:
    if value is None:
        return ""
    text = value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value
    return text[-limit:]


def _choice_stock_refresh_records(governance_path: str | Path) -> list[dict[str, object]]:
    try:
        rows = GovernanceRepository(base_dir=governance_path).read_all(CACHE_BUILD_RUN_STREAM)
    except Exception:
        return []
    return [
        row
        for row in rows
        if str(row.get("job_name") or "") == CHOICE_STOCK_REFRESH_JOB_NAME
        and str(row.get("cache_key") or "") == CHOICE_STOCK_REFRESH_CACHE_KEY
    ]


def _choice_stock_refresh_trigger_lock(*, as_of_date: str) -> LockDefinition:
    return LockDefinition(
        key=f"{CHOICE_STOCK_REFRESH_LOCK}:{as_of_date}:trigger",
        ttl_seconds=30,
    )


def _normalize_choice_stock_refresh_record(record: dict[str, object]) -> dict[str, object]:
    normalized = dict(record)
    normalized["trigger_mode"] = _choice_stock_refresh_trigger_mode(str(normalized.get("status") or ""))
    normalized.setdefault("permission", build_choice_stock_refresh_permission_payload())
    return normalized


def _choice_stock_refresh_trigger_mode(status: str) -> str:
    normalized = str(status or "").strip()
    if normalized in _CHOICE_STOCK_REFRESH_IN_FLIGHT_STATUSES:
        return "async"
    if normalized:
        return "terminal"
    return "idle"


def _choice_stock_daily_observation_status(
    duckdb_path: str | Path,
    *,
    reference_date: str | None = None,
) -> dict[str, object]:
    path = Path(duckdb_path)
    if not path.exists():
        return _choice_stock_table_status("missing_database", reference_date=reference_date)
    try:
        conn = duckdb.connect(str(path), read_only=True)
    except duckdb.Error:
        return _choice_stock_table_status("unreadable_database", reference_date=reference_date)
    try:
        if not _duckdb_table_exists(conn, "choice_stock_daily_observation"):
            return _choice_stock_table_status("missing_table", reference_date=reference_date)
        row = conn.execute(
            """
            select
              count(*) as row_count,
              count(distinct stock_code) as stock_count,
              count(distinct trade_date) as trade_date_count,
              max(trade_date) as latest_trade_date
            from choice_stock_daily_observation
            """
        ).fetchone()
    except duckdb.Error:
        return _choice_stock_table_status("unreadable_table", reference_date=reference_date)
    finally:
        conn.close()
    row_count = _int_or_zero(row[0] if row else 0)
    latest_trade_date = str(row[3])[:10] if row and row[3] is not None else None
    return {
        "materialized": row_count > 0,
        "status": "ok" if row_count > 0 else "empty_table",
        "row_count": row_count,
        "stock_count": _int_or_zero(row[1] if row else 0),
        "trade_date_count": _int_or_zero(row[2] if row else 0),
        "latest_trade_date": latest_trade_date,
        **_choice_stock_table_freshness(latest_trade_date, reference_date),
    }


def _choice_stock_factor_snapshot_status(
    duckdb_path: str | Path,
    *,
    reference_date: str | None = None,
) -> dict[str, object]:
    path = Path(duckdb_path)
    if not path.exists():
        return _choice_stock_table_status("missing_database", reference_date=reference_date)
    try:
        conn = duckdb.connect(str(path), read_only=True)
    except duckdb.Error:
        return _choice_stock_table_status("unreadable_database", reference_date=reference_date)
    try:
        if not _duckdb_table_exists(conn, "choice_stock_factor_snapshot"):
            return _choice_stock_table_status("missing_table", reference_date=reference_date)
        row = conn.execute(
            """
            select
              count(*) as row_count,
              count(distinct stock_code) as stock_count,
              max(as_of_date) as as_of_date
            from choice_stock_factor_snapshot
            """
        ).fetchone()
    except duckdb.Error:
        return _choice_stock_table_status("unreadable_table", reference_date=reference_date)
    finally:
        conn.close()
    row_count = _int_or_zero(row[0] if row else 0)
    as_of_date = str(row[2])[:10] if row and row[2] is not None else None
    return {
        "materialized": row_count > 0,
        "status": "ok" if row_count > 0 else "empty_table",
        "row_count": row_count,
        "stock_count": _int_or_zero(row[1] if row else 0),
        "as_of_date": as_of_date,
        **_choice_stock_table_freshness(as_of_date, reference_date),
    }


def _choice_stock_table_status(status: str, *, reference_date: str | None = None) -> dict[str, object]:
    return {
        "materialized": False,
        "status": status,
        "row_count": 0,
        "stock_count": 0,
        **_choice_stock_table_freshness(None, reference_date),
    }


def _choice_stock_table_freshness(data_date: str | None, reference_date: str | None) -> dict[str, object]:
    if not data_date:
        return {
            "freshness_status": "missing",
            "reference_date": reference_date,
            "stale_days": None,
            "fallback_mode": "missing",
            "fallback_date": None,
        }
    if not reference_date:
        return {
            "freshness_status": "unknown",
            "reference_date": None,
            "stale_days": None,
            "fallback_mode": "unknown",
            "fallback_date": None,
        }
    try:
        data_day = date.fromisoformat(data_date[:10])
        reference_day = date.fromisoformat(reference_date[:10])
    except ValueError:
        return {
            "freshness_status": "unknown",
            "reference_date": reference_date,
            "stale_days": None,
            "fallback_mode": "unknown",
            "fallback_date": None,
        }
    raw_stale_days = (reference_day - data_day).days
    stale_days = max(raw_stale_days, 0)
    if raw_stale_days <= 1:
        status = "current"
    elif raw_stale_days <= 7:
        status = "lagging"
    else:
        status = "stale"
    fallback_mode = "none" if status == "current" else "latest_available"
    return {
        "freshness_status": status,
        "reference_date": reference_day.isoformat(),
        "stale_days": stale_days,
        "fallback_mode": fallback_mode,
        "fallback_date": data_day.isoformat() if fallback_mode == "latest_available" else None,
    }


def _result_row_count(result: dict[str, object] | None) -> int | None:
    if not result:
        return None
    value = result.get("row_count")
    return None if value is None else int(value)


def _latest_result_field(field_name: str, *results: dict[str, object] | None) -> object | None:
    for result in results:
        if result and result.get(field_name):
            return result[field_name]
    return None


def _optional_text(value: object | None) -> str | None:
    text = str(value or "").strip()
    return text or None


def _int_or_zero(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _duckdb_table_exists(conn: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    try:
        row = conn.execute(
            """
            select count(*)
            from information_schema.tables
            where lower(table_name) = lower(?)
            """,
            [table_name],
        ).fetchone()
    except duckdb.Error:
        return False
    return bool(row and row[0])
