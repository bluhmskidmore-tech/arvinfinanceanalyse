"""Service-owned orchestration for the macro vendor refresh workflow."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    GovernanceRepository,
)

CHOICE_MACRO_REFRESH_JOB_NAME = "choice_macro_refresh"
CHOICE_MACRO_REFRESH_CACHE_KEY = "choice_macro.latest"
CHOICE_MACRO_REFRESH_RULE_VERSION = "rv_choice_macro_async_v1"
CHOICE_MACRO_REFRESH_QUEUE_POLL_WINDOW_SECONDS = 120 * 3
CHOICE_MACRO_REFRESH_QUEUE_GRACE_SECONDS = 60
CHOICE_MACRO_REFRESH_TASK_TIME_LIMIT_MS = 3_600_000
CHOICE_MACRO_REFRESH_TASK_TIME_LIMIT_SECONDS = CHOICE_MACRO_REFRESH_TASK_TIME_LIMIT_MS // 1_000
CHOICE_MACRO_REFRESH_TASK_GRACE_SECONDS = 60


class MacroVendorQueueError(RuntimeError):
    """The governed refresh run could not be submitted to the worker queue."""


class _LazyChoiceMacroTask:
    """Resolve Choice macro actors only when a refresh is executed."""

    def __init__(self, task_name: str) -> None:
        self._task_name = task_name

    def _resolve(self) -> Any:
        from backend.app.tasks import choice_macro as choice_macro_tasks

        return getattr(choice_macro_tasks, self._task_name)

    def send(self, *args: object, **kwargs: object) -> object:
        return self._resolve().send(*args, **kwargs)

    def __call__(self, *args: object, **kwargs: object) -> object:
        return self._resolve()(*args, **kwargs)

    def __getattr__(self, name: str) -> object:
        return getattr(self._resolve(), name)


refresh_choice_macro_snapshot = _LazyChoiceMacroTask("refresh_choice_macro_snapshot")
refresh_public_cross_asset_headlines = _LazyChoiceMacroTask("refresh_public_cross_asset_headlines")
refresh_tushare_ncd_shibor_proxy = _LazyChoiceMacroTask("refresh_tushare_ncd_shibor_proxy")
run_choice_macro_refresh_task = _LazyChoiceMacroTask("run_choice_macro_refresh_workflow")


def queue_choice_macro_refresh(
    *,
    duckdb_path: str | Path,
    governance_path: str | Path,
    backfill_days: int,
    refresh_task: object = run_choice_macro_refresh_task,
) -> dict[str, object]:
    """Record a governed queued run and dispatch the write workflow to a worker."""

    queued_at_value = datetime.now(UTC)
    queued_at = queued_at_value.isoformat()
    status_deadline_at = (
        queued_at_value
        + timedelta(
            seconds=(
                CHOICE_MACRO_REFRESH_QUEUE_POLL_WINDOW_SECONDS
                + CHOICE_MACRO_REFRESH_QUEUE_GRACE_SECONDS
            )
        )
    ).isoformat()
    run_id = f"{CHOICE_MACRO_REFRESH_JOB_NAME}:{queued_at}:{uuid4().hex[:12]}"
    queued_payload: dict[str, object] = {
        "run_id": run_id,
        "job_name": CHOICE_MACRO_REFRESH_JOB_NAME,
        "status": "queued",
        "trigger_mode": "async",
        "cache_key": CHOICE_MACRO_REFRESH_CACHE_KEY,
        "rule_version": CHOICE_MACRO_REFRESH_RULE_VERSION,
        "source_version": "sv_pending",
        "vendor_version": "vv_pending",
        "backfill_days": backfill_days,
        "queued_at": queued_at,
        "status_deadline_at": status_deadline_at,
    }
    repo = GovernanceRepository(base_dir=governance_path)
    try:
        repo.append(CACHE_BUILD_RUN_STREAM, queued_payload)
    except Exception as exc:
        raise MacroVendorQueueError("Choice macro refresh queue registration failed.") from exc

    try:
        refresh_task.send(  # type: ignore[attr-defined]
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_path),
            run_id=run_id,
            backfill_days=backfill_days,
            queued_at=queued_at,
            status_deadline_at=status_deadline_at,
        )
    except Exception as exc:
        failed_payload = {
            **queued_payload,
            "status": "failed",
            "trigger_mode": "terminal",
            "finished_at": datetime.now(UTC).isoformat(),
            "error_message": str(exc),
            "failure_category": "queue_dispatch_failure",
            "failure_reason": type(exc).__name__,
        }
        try:
            repo.append(CACHE_BUILD_RUN_STREAM, failed_payload)
        except Exception as record_exc:
            raise MacroVendorQueueError(
                "Choice macro refresh queue dispatch failed and its terminal state could not be recorded."
            ) from record_exc
        raise MacroVendorQueueError("Choice macro refresh queue dispatch failed.") from exc
    return queued_payload


def run_choice_macro_refresh(
    *,
    backfill_days: int,
    choice_refresh_task: object = refresh_choice_macro_snapshot,
    public_refresh_task: object = refresh_public_cross_asset_headlines,
    tushare_ncd_shibor_refresh_task: object = refresh_tushare_ncd_shibor_proxy,
) -> tuple[dict[str, object], bool]:
    choice_refresh = getattr(choice_refresh_task, "fn", choice_refresh_task)
    try:
        choice_payload = choice_refresh(backfill_days=backfill_days)  # type: ignore[operator]
    except RuntimeError as exc:
        choice_payload = _choice_macro_refresh_failure_payload(exc)

    public_payload = _run_refresh_task(
        public_refresh_task,
        failure_label="public_cross_asset",
    )
    tushare_ncd_shibor_payload = None
    if str(choice_payload.get("status") or "") == "failed":
        tushare_ncd_shibor_payload = _run_refresh_task(
            tushare_ncd_shibor_refresh_task,
            failure_label="tushare_ncd_shibor",
        )

    refresh_succeeded = _refresh_payload_succeeded(
        choice_payload,
        public_payload,
        tushare_ncd_shibor_payload,
    )
    payload = _merge_choice_and_public_refresh_payloads(
        choice_payload,
        public_payload,
        tushare_ncd_shibor_payload,
    )
    return payload, refresh_succeeded


def _choice_macro_refresh_failure_payload(exc: RuntimeError) -> dict[str, object]:
    error_text = str(exc) or exc.__class__.__name__
    return {
        "status": "failed",
        "error_message": error_text,
        "warnings": [f"Choice macro refresh failed: {error_text}"],
    }


def _run_refresh_task(task: object, *, failure_label: str) -> dict[str, object]:
    try:
        refresh = getattr(task, "fn", task)
        return refresh()  # type: ignore[operator]
    except RuntimeError as exc:
        error_text = str(exc)
        return {
            "status": "failed",
            "error_message": error_text,
            "warnings": [f"{failure_label} refresh failed: {error_text}"],
        }


def _refresh_payload_succeeded(*payloads: dict[str, object] | None) -> bool:
    return any(
        str(payload.get("status") or "") in {"completed", "partial", "degraded"}
        for payload in payloads
        if payload
    )


def _format_refresh_warning(item: object) -> str:
    if isinstance(item, dict):
        code = str(item.get("code") or "").strip()
        message = str(item.get("message") or "").strip()
        if code and message:
            return f"{code}: {message}"
        return code or message
    return str(item).strip()


def _merge_choice_and_public_refresh_payloads(
    choice_payload: dict[str, object],
    public_payload: dict[str, object],
    tushare_ncd_shibor_payload: dict[str, object] | None = None,
) -> dict[str, object]:
    warnings: list[str] = []
    backup_payloads = [public_payload]
    if tushare_ncd_shibor_payload is not None:
        backup_payloads.append(tushare_ncd_shibor_payload)
    for payload in (choice_payload, *backup_payloads):
        payload_warnings = payload.get("warnings")
        if isinstance(payload_warnings, list):
            warnings.extend(
                text for text in (_format_refresh_warning(item) for item in payload_warnings) if text
            )

    result = {
        **choice_payload,
        "choice_macro": choice_payload,
        "public_cross_asset": public_payload,
        "warnings": warnings,
    }
    if tushare_ncd_shibor_payload is not None:
        result["tushare_ncd_shibor"] = tushare_ncd_shibor_payload
    if str(choice_payload.get("status") or "") == "failed":
        backup_succeeded = _refresh_payload_succeeded(*backup_payloads)
        result["status"] = "partial" if backup_succeeded else "failed"
        if backup_succeeded and not result.get("run_id"):
            result["run_id"] = next(
                (
                    payload.get("run_id")
                    for payload in backup_payloads
                    if str(payload.get("status") or "") == "completed" and payload.get("run_id")
                ),
                None,
            )
    return result
