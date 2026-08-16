from __future__ import annotations

import base64
import binascii
import logging
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, cast

from backend.app.governance.settings import get_settings
from backend.app.repositories.task_write_guard import repository_task_write_scope
from backend.app.services.ledger_import_run_service import (
    get_ledger_import_terminal_outbox,
    normalize_ledger_import_file_name,
    record_ledger_import_terminal_outbox,
    record_ledger_import_transition,
)
from backend.app.services.ledger_import_service import MAX_LEDGER_IMPORT_BYTES, LedgerImportService
from backend.app.tasks.broker import register_actor_once

MAX_LEDGER_IMPORT_BASE64_CHARS = 4 * ((MAX_LEDGER_IMPORT_BYTES + 2) // 3)
MAX_LEDGER_IMPORT_MANUAL_RETRIES = 3
LEDGER_IMPORT_RETRY_DELAY_MS = 15_000
TERMINAL_OUTBOX_WRITE_ATTEMPTS = 3
logger = logging.getLogger(__name__)


class TerminalDelivery(StrEnum):
    DELIVERED = "delivered"
    SPOOLED = "spooled"
    DELIVERY_FAILED = "delivery_failed"


def _run_ledger_import_terminal_reconciliation(
    *,
    run_id: str,
    governance_dir: str,
    retry_attempt: int = 0,
    file_name: str | None = None,
    status: str | None = None,
    outcome: str | None = None,
    batch_id: int | None = None,
    duplicate_of_batch_id: int | None = None,
    source_version: str = "",
    rule_version: str = "",
    error_category: str | None = None,
    error_message: str | None = None,
    finished_at: str | None = None,
) -> dict[str, object]:
    settings = get_settings()
    try:
        if status is None:
            facts = get_ledger_import_terminal_outbox(
                governance_dir=governance_dir,
                governance_backend=settings.governance_backend,
                governance_sql_dsn=settings.governance_sql_dsn,
                run_id=run_id,
            )
        else:
            facts = {
                "file_name": normalize_ledger_import_file_name(file_name or ""),
                "status": status,
                "outcome": outcome,
                "batch_id": batch_id,
                "duplicate_of_batch_id": duplicate_of_batch_id,
                "source_version": source_version,
                "rule_version": rule_version,
                "error_category": error_category,
                "error_message": error_message,
                "finished_at": finished_at,
            }
        record_ledger_import_transition(
            governance_dir=governance_dir,
            governance_backend=settings.governance_backend,
            governance_sql_dsn=settings.governance_sql_dsn,
            job_state_dsn=settings.job_state_dsn,
            run_id=run_id,
            file_name=str(facts.get("file_name") or ""),
            status=str(facts["status"]),
            outcome=str(facts.get("outcome") or "") or None,
            batch_id=cast(int | None, facts.get("batch_id")),
            duplicate_of_batch_id=cast(int | None, facts.get("duplicate_of_batch_id")),
            source_version=str(facts.get("source_version") or ""),
            rule_version=str(facts.get("rule_version") or ""),
            error_category=str(facts.get("error_category") or "") or None,
            error_message=str(facts.get("error_message") or "") or None,
        )
        return _safe_task_payload(run_id=run_id, status="reconciled")
    except Exception as exc:  # noqa: BLE001  # 终态对账兜底：任何治理后端异常都必须进入重试/outbox 路径，已 error 日志
        logger.error(
            "Ledger import terminal reconciliation attempt failed run_id=%s error_type=%s.",
            run_id,
            type(exc).__name__,
        )
        if retry_attempt < MAX_LEDGER_IMPORT_MANUAL_RETRIES:
            try:
                reconcile_ledger_import_terminal.send_with_options(
                    kwargs={
                        "run_id": run_id,
                        "governance_dir": governance_dir,
                        "retry_attempt": retry_attempt + 1,
                        "file_name": file_name,
                        "status": status,
                        "outcome": outcome,
                        "batch_id": batch_id,
                        "duplicate_of_batch_id": duplicate_of_batch_id,
                        "source_version": source_version,
                        "rule_version": rule_version,
                        "error_category": error_category,
                        "error_message": error_message,
                        "finished_at": finished_at,
                    },
                    delay=LEDGER_IMPORT_RETRY_DELAY_MS,
                )
                return _safe_task_payload(run_id=run_id, status="retrying")
            except Exception as enqueue_exc:  # noqa: BLE001  # broker 入队异常面无界；失败降级为本地 outbox spool，已 error 日志
                logger.error(
                    "Ledger import terminal reconciliation enqueue failed run_id=%s error_type=%s.",
                    run_id,
                    type(enqueue_exc).__name__,
                )
        if status is not None:
            for attempt in range(TERMINAL_OUTBOX_WRITE_ATTEMPTS):
                try:
                    record_ledger_import_terminal_outbox(
                        governance_dir=governance_dir,
                        governance_backend=settings.governance_backend,
                        governance_sql_dsn=settings.governance_sql_dsn,
                        run_id=run_id,
                        file_name=file_name or "",
                        status=status,
                        outcome=outcome,
                        batch_id=batch_id,
                        duplicate_of_batch_id=duplicate_of_batch_id,
                        source_version=source_version,
                        rule_version=rule_version,
                        error_category=error_category,
                        error_message=error_message,
                    )
                    logger.error("Ledger import reconciliation pending local recovery run_id=%s.", run_id)
                    return _safe_task_payload(run_id=run_id, status="pending_reconciliation")
                except Exception as spool_exc:  # noqa: BLE001  # outbox spool 落盘兜底：重试用尽后显式返回 delivery_failed，已 error 日志
                    logger.error(
                        "Ledger import reconciliation local spool failed run_id=%s attempt=%s error_type=%s.",
                        run_id,
                        attempt + 1,
                        type(spool_exc).__name__,
                    )
            logger.error("Ledger import reconciliation delivery failed run_id=%s.", run_id)
            return _safe_task_payload(run_id=run_id, status="delivery_failed")
        return _safe_task_payload(run_id=run_id, status="pending_reconciliation")


def _run_ledger_import(
    *,
    file_name: str,
    content_base64: str,
    duckdb_path: str,
    run_id: str,
    governance_dir: str | None = None,
    retry_attempt: int = 0,
) -> dict[str, object]:
    settings = get_settings()
    normalized_file_name = normalize_ledger_import_file_name(file_name)
    resolved_governance_dir = str(governance_dir or settings.governance_path)
    retry_kwargs = {
        "file_name": normalized_file_name,
        "content_base64": content_base64,
        "duckdb_path": duckdb_path,
        "run_id": run_id,
        "governance_dir": resolved_governance_dir,
        "retry_attempt": retry_attempt + 1,
    }
    try:
        record_ledger_import_transition(
            governance_dir=resolved_governance_dir,
            governance_backend=settings.governance_backend,
            governance_sql_dsn=settings.governance_sql_dsn,
            job_state_dsn=settings.job_state_dsn,
            run_id=run_id,
            file_name=normalized_file_name,
            status="running",
        )
    except Exception as exc:  # noqa: BLE001  # 治理后端（jsonl/sql）写入异常面无界；失败走 _retry_or_fail 终态机，已 error 日志
        logger.error(
            "Ledger import running transition failed run_id=%s error_type=%s.",
            run_id,
            type(exc).__name__,
        )
        return _retry_or_fail(
            retry_attempt=retry_attempt,
            retry_kwargs=retry_kwargs,
            run_id=run_id,
            file_name=normalized_file_name,
            governance_dir=resolved_governance_dir,
            error_category="processing_failed",
        )

    try:
        if len(content_base64) > MAX_LEDGER_IMPORT_BASE64_CHARS:
            raise ValueError("Ledger import payload is too large.")
        try:
            content = base64.b64decode(content_base64.encode("ascii"), validate=True)
        except (binascii.Error, UnicodeEncodeError) as exc:
            raise ValueError("Ledger import content must be valid base64 ASCII.") from exc
        if len(content) > MAX_LEDGER_IMPORT_BYTES:
            raise ValueError("Ledger import payload is too large.")
        with repository_task_write_scope(__name__):
            payload = cast(
                dict[str, Any],
                LedgerImportService(duckdb_path).import_file(
                    file_name=normalized_file_name,
                    content=content,
                ),
            )
        payload["data"]["run_id"] = run_id
        payload["trace"]["run_id"] = run_id
    except ValueError as exc:
        logger.error(
            "Ledger import file rejected run_id=%s error_type=%s.",
            run_id,
            type(exc).__name__,
        )
        delivered = _persist_terminal_and_enqueue(
            run_id=run_id,
            file_name=normalized_file_name,
            governance_dir=resolved_governance_dir,
            status="failed",
            outcome=None,
            batch_id=None,
            duplicate_of_batch_id=None,
            source_version="",
            rule_version="",
            error_category="invalid_file",
            error_message="Ledger import file is invalid.",
        )
        return _safe_task_payload(
            run_id=run_id,
            status=_terminal_delivery_status(delivered, terminal_status="failed"),
        )
    except Exception as exc:  # noqa: BLE001  # 导入处理兜底：ValueError 已单独窄化，其余异常必须落终态并重试，已 error 日志
        logger.error(
            "Ledger import processing attempt failed run_id=%s error_type=%s.",
            run_id,
            type(exc).__name__,
        )
        return _retry_or_fail(
            retry_attempt=retry_attempt,
            retry_kwargs=retry_kwargs,
            run_id=run_id,
            file_name=normalized_file_name,
            governance_dir=resolved_governance_dir,
            error_category="processing_failed",
        )

    duplicate = payload["data"].get("status") == "duplicate"
    delivered = _persist_terminal_and_enqueue(
        run_id=run_id,
        file_name=normalized_file_name,
        governance_dir=resolved_governance_dir,
        status="completed",
        outcome="duplicate" if duplicate else "success",
        batch_id=int(payload["data"]["batch_id"]),
        duplicate_of_batch_id=(
            int(payload["trace"]["duplicate_of_batch_id"])
            if payload["trace"].get("duplicate_of_batch_id") is not None
            else None
        ),
        source_version=str(payload["data"].get("source_version") or ""),
        rule_version=str(payload["data"].get("rule_version") or ""),
        error_category=None,
        error_message=None,
    )
    return (
        payload
        if delivered is TerminalDelivery.DELIVERED
        else _safe_task_payload(
            run_id=run_id,
            status=_terminal_delivery_status(delivered, terminal_status="completed"),
        )
    )


def _retry_or_fail(
    *,
    retry_attempt: int,
    retry_kwargs: dict[str, object],
    run_id: str,
    file_name: str,
    governance_dir: str,
    error_category: str,
) -> dict[str, object]:
    if retry_attempt < MAX_LEDGER_IMPORT_MANUAL_RETRIES:
        try:
            run_ledger_import.send_with_options(
                kwargs=retry_kwargs,
                delay=LEDGER_IMPORT_RETRY_DELAY_MS,
            )
            return _safe_task_payload(run_id=run_id, status="retrying")
        except Exception as exc:  # noqa: BLE001  # broker 入队异常面无界；重试入队失败后直接落 failed 终态，已 error 日志
            logger.error(
                "Ledger import manual retry enqueue failed run_id=%s error_type=%s.",
                run_id,
                type(exc).__name__,
            )
    delivered = _persist_terminal_and_enqueue(
        run_id=run_id,
        file_name=file_name,
        governance_dir=governance_dir,
        status="failed",
        outcome=None,
        batch_id=None,
        duplicate_of_batch_id=None,
        source_version="",
        rule_version="",
        error_category=error_category,
        error_message="Ledger import processing failed.",
    )
    return _safe_task_payload(
        run_id=run_id,
        status=_terminal_delivery_status(delivered, terminal_status="failed"),
    )


def _persist_terminal_and_enqueue(
    *,
    run_id: str,
    file_name: str,
    governance_dir: str,
    status: str,
    outcome: str | None,
    batch_id: int | None,
    duplicate_of_batch_id: int | None,
    source_version: str,
    rule_version: str,
    error_category: str | None,
    error_message: str | None,
) -> TerminalDelivery:
    settings = get_settings()
    finished_at = datetime.now(UTC).isoformat()
    try:
        record_ledger_import_transition(
            governance_dir=governance_dir,
            governance_backend=settings.governance_backend,
            governance_sql_dsn=settings.governance_sql_dsn,
            job_state_dsn=settings.job_state_dsn,
            run_id=run_id,
            file_name=file_name,
            status=status,
            outcome=outcome,
            batch_id=batch_id,
            duplicate_of_batch_id=duplicate_of_batch_id,
            source_version=source_version,
            rule_version=rule_version,
            error_category=error_category,
            error_message=error_message,
        )
        return TerminalDelivery.DELIVERED
    except Exception as exc:  # noqa: BLE001  # 终态主写失败必须降级到 safe enqueue/outbox，actor 不允许崩溃丢终态，已 error 日志
        logger.error(
            "Ledger import terminal primary write failed run_id=%s error_type=%s.",
            run_id,
            type(exc).__name__,
        )

    safe_facts = {
        "run_id": run_id,
        "governance_dir": governance_dir,
        "retry_attempt": 0,
        "file_name": normalize_ledger_import_file_name(file_name),
        "status": status,
        "outcome": outcome,
        "batch_id": batch_id,
        "duplicate_of_batch_id": duplicate_of_batch_id,
        "source_version": source_version,
        "rule_version": rule_version,
        "error_category": error_category,
        "error_message": error_message,
        "finished_at": finished_at,
    }
    last_spool_error_type = "Unknown"
    for attempt in range(TERMINAL_OUTBOX_WRITE_ATTEMPTS):
        try:
            reconcile_ledger_import_terminal.send(**safe_facts)
            return TerminalDelivery.DELIVERED
        except Exception as exc:  # noqa: BLE001  # safe enqueue 兜底：失败继续尝试本地 outbox spool，已 error 日志
            last_spool_error_type = type(exc).__name__
            logger.error(
                "Ledger import safe terminal enqueue failed run_id=%s attempt=%s error_type=%s.",
                run_id,
                attempt + 1,
                type(exc).__name__,
            )

    for attempt in range(TERMINAL_OUTBOX_WRITE_ATTEMPTS):
        try:
            record_ledger_import_terminal_outbox(
                governance_dir=governance_dir,
                governance_backend=settings.governance_backend,
                governance_sql_dsn=settings.governance_sql_dsn,
                run_id=run_id,
                file_name=file_name,
                status=status,
                outcome=outcome,
                batch_id=batch_id,
                duplicate_of_batch_id=duplicate_of_batch_id,
                source_version=source_version,
                rule_version=rule_version,
                error_category=error_category,
                error_message=error_message,
            )
            logger.warning("event=ledger_import_terminal_spooled run_id=%s.", run_id)
            return TerminalDelivery.SPOOLED
        except Exception as exc:  # noqa: BLE001  # 最后一级 spool 兜底：失败显式返回 DELIVERY_FAILED，已 error 日志
            last_spool_error_type = type(exc).__name__
            logger.error(
                "Ledger import local terminal spool write failed run_id=%s attempt=%s error_type=%s.",
                run_id,
                attempt + 1,
                type(exc).__name__,
            )
    logger.error(
        "event=ledger_import_terminal_delivery_failed run_id=%s attempts=%s error_type=%s.",
        run_id,
        TERMINAL_OUTBOX_WRITE_ATTEMPTS,
        last_spool_error_type,
    )
    return TerminalDelivery.DELIVERY_FAILED


def _terminal_delivery_status(delivery: TerminalDelivery, *, terminal_status: str) -> str:
    if delivery is TerminalDelivery.DELIVERED:
        return terminal_status
    if delivery is TerminalDelivery.SPOOLED:
        return "terminal_pending"
    return "delivery_failed"


def _safe_task_payload(*, run_id: str, status: str) -> dict[str, object]:
    return {
        "data": {"run_id": run_id, "status": status},
        "trace": {"run_id": run_id},
    }


reconcile_ledger_import_terminal = register_actor_once(
    "reconcile_ledger_import_terminal",
    _run_ledger_import_terminal_reconciliation,
    max_retries=0,
)
run_ledger_import = register_actor_once(
    "run_ledger_import",
    _run_ledger_import,
    max_retries=0,
)
