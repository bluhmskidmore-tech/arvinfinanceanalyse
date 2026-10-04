"""Drain the data-center request queue from the host scheduler, independently of HTTP."""

from __future__ import annotations

import argparse
import errno
import hashlib
import logging
import os
import socket
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import perf_counter
from typing import SupportsIndex, SupportsInt, TypedDict

from backend.app.governance.locks import acquire_lock, resolve_duckdb_writer_lock
from backend.app.governance.settings import get_settings
from backend.app.repositories.data_update_repo import latest_runs, save_run, verify_daily_balance_date
from backend.app.schemas.curve_recovery import normalize_curve_recovery_options
from backend.app.services.data_update_service import (
    ACTIVE_STATUSES,
    CHOICE_STOCK_PIT_WORKFLOW,
    QUEUE_LOCK,
    STEP_LABELS,
    WORKER_LOCK,
    input_preflight,
    publication_recovery_eligibility,
    utc_now,
)

logger = logging.getLogger(__name__)


class _RefreshCorrelationKwargs(TypedDict, total=False):
    data_update_run_id: str


class _SystemReadPublicationFailed(RuntimeError):
    def __init__(self, message: str, *, receipt: dict[str, object]) -> None:
        super().__init__(message)
        self.receipt = receipt


def _validate_balance_input_content(settings, report_date: str) -> None:
    """Parse only the target sources the upcoming snapshot batch will select."""
    from backend.app.core_finance.source_rules import describe_source_file
    from backend.app.repositories.governance_repo import GovernanceRepository
    from backend.app.repositories.object_store_repo import ObjectStoreRepository
    from backend.app.repositories.snapshot_row_parse import (
        parse_tyw_snapshot_rows_from_bytes,
        parse_zqtz_snapshot_rows_from_bytes,
    )
    from backend.app.repositories.source_manifest_repo import SourceManifestRepository
    from backend.app.services.ingest_service import _iter_data_input_scan_paths
    from backend.app.tasks.snapshot_materialize import SNAPSHOT_RULE_VERSION

    root = Path(settings.data_input_root).resolve()
    manifest = SourceManifestRepository(governance_repo=GovernanceRepository(base_dir=settings.governance_path))
    candidates: list[dict[str, object]] = []
    payloads: dict[str, bytes] = {}
    for path in _iter_data_input_scan_paths(root):
        metadata = describe_source_file(path.name)
        if metadata.source_family not in {"zqtz", "tyw"} or metadata.report_date != report_date:
            continue
        if not path.resolve().is_relative_to(root):
            raise ValueError("余额来源路径不在配置的输入目录内。")
        before = path.stat()
        payload = path.read_bytes()
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError("余额来源在内容检查时发生变化。")
        identity = str(path)
        payloads[identity] = payload
        candidates.append({
            "source_family": metadata.source_family, "report_date": metadata.report_date,
            "source_file": path.name, "file_path": identity,
            "source_version": f"sv_{hashlib.sha256(payload).hexdigest()[:12]}",
        })
    incremental = manifest.filter_incremental_rows(candidates)
    # Formal balance uses the new ingest batch when it contains any target-date
    # rows, even one family; otherwise its existing selector picks archived rows.
    # Other report dates cannot affect that decision and are never read here.
    selected = incremental or manifest.select_for_snapshot_materialization(
        source_families=["zqtz", "tyw"], report_date=report_date,
    )
    if not selected:
        raise ValueError("该报告日没有可用的余额内容来源。")
    store = ObjectStoreRepository(
        endpoint=str(getattr(settings, "minio_endpoint", "")),
        access_key=str(getattr(settings, "minio_access_key", "")),
        secret_key=str(getattr(settings, "minio_secret_key", "")),
        bucket=str(getattr(settings, "minio_bucket", "")),
        mode=str(getattr(settings, "object_store_mode", "local")),
        local_archive_path=str(settings.local_archive_path),
    )
    if not incremental and store.mode == "local":
        selected = [row for row in selected if store._resolve_archived_path(str(row["archived_path"])).is_file()]
        if not selected:
            raise ValueError("该报告日没有可读取的余额归档来源。")
    parsers = {"zqtz": parse_zqtz_snapshot_rows_from_bytes, "tyw": parse_tyw_snapshot_rows_from_bytes}
    for row in selected:
        payload = (payloads[str(row["file_path"])] if incremental
                   else store.read_archived_bytes(str(row["archived_path"])))
        parsers[str(row["source_family"])](
            file_bytes=payload, ingest_batch_id=str(row.get("ingest_batch_id") or "input-content-preflight"),
            source_version=str(row["source_version"]),
            source_file=str(row.get("source_file") or Path(str(row["archived_path"])).name),
            rule_version=SNAPSHOT_RULE_VERSION,
        )


def _execute_core(
    settings,
    report_date: str,
    on_progress,
    *,
    data_update_run_id: str | None = None,
    use_existing_fx_only: bool = False,
    expected_fx_source_version: str | None = None,
    use_existing_curves_only: bool = False,
    expected_curve_snapshots: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    from backend.app.services.pnl_source_service import load_latest_pnl_refresh_input
    from scripts.run_global_data_refresh import run_global_data_refresh

    _validate_balance_input_content(settings, report_date)
    # Parse the required PnL input before any balance/FX writes. Optional non-standard
    # families retain the canonical parser's existing rules.
    inputs = load_latest_pnl_refresh_input(
        governance_dir=settings.governance_path,
        data_root=settings.data_input_root,
        report_date=report_date,
        archive_root=settings.local_archive_path,
    )
    if inputs.report_date != report_date or not inputs.fi_rows:
        raise ValueError("该报告日的固收损益文件没有可用记录。")
    inferred_run_id = getattr(on_progress, "data_update_run_id", None)
    raw_correlated_run_id = (
        data_update_run_id
        if isinstance(data_update_run_id, str)
        else inferred_run_id if isinstance(inferred_run_id, str) else None
    )
    correlated_run_id = str(raw_correlated_run_id or "").strip()
    correlation_kwargs: _RefreshCorrelationKwargs = (
        {"data_update_run_id": correlated_run_id} if correlated_run_id else {}
    )
    if use_existing_fx_only and use_existing_curves_only:
        return run_global_data_refresh(
            report_date=report_date,
            on_progress=on_progress,
            use_existing_fx_only=True,
            expected_fx_source_version=expected_fx_source_version,
            use_existing_curves_only=True,
            expected_curve_snapshots=expected_curve_snapshots,
            **correlation_kwargs,
        )
    if use_existing_fx_only:
        return run_global_data_refresh(
            report_date=report_date,
            on_progress=on_progress,
            use_existing_fx_only=True,
            expected_fx_source_version=expected_fx_source_version,
            **correlation_kwargs,
        )
    if use_existing_curves_only:
        return run_global_data_refresh(
            report_date=report_date,
            on_progress=on_progress,
            use_existing_curves_only=True,
            expected_curve_snapshots=expected_curve_snapshots,
            **correlation_kwargs,
        )
    return run_global_data_refresh(
        report_date=report_date,
        on_progress=on_progress,
        **correlation_kwargs,
    )


def _error_text(exc: BaseException) -> str:
    # Exceptions may contain provider credentials, SQL or private source paths.
    return f"更新步骤失败（异常类型：{type(exc).__name__}）。"


def _receipt_count(value: object) -> int:
    if not isinstance(value, (str, bytes, bytearray, SupportsInt, SupportsIndex)):
        raise TypeError("更新回执计数必须可转换为整数。")
    return int(value)


def _receipt_steps(value: object) -> list[dict[str, object]]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise TypeError("更新回执步骤必须为记录列表。")
    return [dict(item) for item in value]


def _recovery_parameters(
    run: dict[str, object],
) -> tuple[bool, str | None, bool, list[dict[str, str]] | None]:
    use_existing_fx_only = run.get("use_existing_fx_only", False)
    if type(use_existing_fx_only) is not bool:
        raise ValueError("持久化请求中的现有汇率恢复模式不是布尔值。")
    expected_fx_source_version = run.get("expected_fx_source_version")
    if expected_fx_source_version is not None and (
        not isinstance(expected_fx_source_version, str) or not expected_fx_source_version.strip()
    ):
        raise ValueError("持久化请求中的预期汇率来源版本无效。")
    normalized_version = expected_fx_source_version.strip() if expected_fx_source_version is not None else None
    raw_use_existing_curves_only = run.get("use_existing_curves_only", False)
    if type(raw_use_existing_curves_only) is not bool:
        raise TypeError("持久化请求中的现有曲线恢复模式不是布尔值。")
    use_existing_curves_only = bool(raw_use_existing_curves_only)
    expected_curve_snapshots = normalize_curve_recovery_options(
        use_existing_curves_only=use_existing_curves_only,
        expected_curve_snapshots=run.get("expected_curve_snapshots"),
    )
    recovery_of_run_id = run.get("recovery_of_run_id")
    if recovery_of_run_id is not None and (not isinstance(recovery_of_run_id, str) or not recovery_of_run_id.strip()):
        raise ValueError("持久化请求中的恢复来源请求编号无效。")
    normalized_recovery_run_id = recovery_of_run_id.strip() if recovery_of_run_id is not None else None
    recovery_mode = use_existing_fx_only or use_existing_curves_only
    if recovery_mode and run.get("workflow", "core_financial") != "core_financial":
        raise ValueError("恢复模式仅支持完整财务更新。")
    if use_existing_fx_only and normalized_version is None:
        raise ValueError("现有汇率恢复请求缺少预期汇率来源版本。")
    if not use_existing_fx_only and normalized_version is not None:
        raise ValueError("普通更新请求不能携带预期汇率来源版本。")
    if recovery_mode and normalized_recovery_run_id is None:
        raise ValueError("恢复请求缺少原失败请求。")
    if not recovery_mode and normalized_recovery_run_id is not None:
        raise ValueError("普通更新请求不能携带恢复来源请求编号。")
    return use_existing_fx_only, normalized_version, use_existing_curves_only, expected_curve_snapshots


def _execute_balance(settings, report_date: str, on_progress) -> dict[str, object]:
    from backend.app.tasks.formal_balance_pipeline import run_formal_balance_pipeline_sync

    balance_step = "daily_balance_and_risk"
    on_progress({"current_step": balance_step, "steps": []})
    balance_started_at = utc_now()
    balance_started = perf_counter()
    try:
        _validate_balance_input_content(settings, report_date)
        result = run_formal_balance_pipeline_sync(
            report_date=report_date,
            include_analytics=True,
            data_root=str(settings.data_input_root),
            duckdb_path=str(settings.duckdb_path),
            governance_dir=str(settings.governance_path),
            archive_dir=str(settings.local_archive_path),
        )
        if result.get("status") != "completed":
            raise ValueError("余额与风险更新未返回完整成功回执。")
    except Exception as exc:
        on_progress(
            {
                "current_step": None,
                "steps": [
                    {
                        "name": balance_step,
                        "status": "failed",
                        "started_at": balance_started_at,
                        "finished_at": utc_now(),
                        "elapsed_seconds": round(perf_counter() - balance_started, 3),
                        "error_message": _error_text(exc),
                    }
                ],
            }
        )
        raise
    pipeline_result = dict(result)
    balance_result: dict[str, object] = {
        "status": "completed",
        "report_date": report_date,
        "pipeline": pipeline_result,
    }
    steps = [
        {
            "name": balance_step,
            "status": "completed",
            "started_at": balance_started_at,
            "finished_at": utc_now(),
            "elapsed_seconds": round(perf_counter() - balance_started, 3),
            "result": balance_result,
        }
    ]
    on_progress({"current_step": "verify", "steps": steps})
    verify_started_at = utc_now()
    verify_started = perf_counter()
    try:
        verify_daily_balance_date(settings.duckdb_path, report_date)
    except Exception as exc:
        on_progress(
            {
                "current_step": None,
                "steps": [
                    *steps,
                    {
                        "name": "verify",
                        "status": "failed",
                        "started_at": verify_started_at,
                        "finished_at": utc_now(),
                        "elapsed_seconds": round(perf_counter() - verify_started, 3),
                        "error_message": _error_text(exc),
                    },
                ],
            }
        )
        raise
    steps = [
        *steps,
        {
            "name": "verify",
            "status": "completed",
            "started_at": verify_started_at,
            "finished_at": utc_now(),
            "elapsed_seconds": round(perf_counter() - verify_started, 3),
        },
    ]
    if not bool(getattr(settings, "system_read_publication_enabled", False)):
        on_progress({"current_step": None, "steps": steps})
        return balance_result
    on_progress({"current_step": "source_preview", "steps": steps})
    preview_started_at = utc_now()
    preview_started = perf_counter()
    try:
        from backend.app.tasks.source_preview_refresh import _refresh_source_preview_cache

        preview_result = _refresh_source_preview_cache(
            duckdb_path=str(settings.duckdb_path),
            governance_dir=str(settings.governance_path),
            data_root=str(settings.data_input_root),
            from_existing_manifests=True,
        )
        if preview_result.get("status") != "completed":
            raise ValueError("来源预览未返回完整成功回执。")
    except Exception as exc:
        failed_steps = [
            *steps,
            {
                "name": "source_preview",
                "status": "failed",
                "started_at": preview_started_at,
                "finished_at": utc_now(),
                "elapsed_seconds": round(perf_counter() - preview_started, 3),
                "error_message": _error_text(exc),
            },
        ]
        on_progress(
            {
                "current_step": None,
                "steps": failed_steps,
            }
        )
        raise _SystemReadPublicationFailed(
            f"余额结果完成后的来源预览依赖失败：{_error_text(exc)}",
            receipt={
                "status": "failed",
                "failed_step": "source_preview",
                "business_body_status": "completed",
                "steps": failed_steps,
            },
        ) from exc
    pipeline_result["source_preview"] = dict(preview_result)
    on_progress(
        {
            "current_step": None,
            "steps": [
                *steps,
                {
                    "name": "source_preview",
                    "status": "completed",
                    "started_at": preview_started_at,
                    "finished_at": utc_now(),
                    "elapsed_seconds": round(perf_counter() - preview_started, 3),
                    "result": dict(preview_result),
                },
            ],
        }
    )
    return balance_result


def _transient(exc: BaseException) -> bool:
    # Only transient I/O/lock failures are retried. Formula, schema, and validation
    # failures stay terminal; never repeatedly rewrite finance facts on a bad input.
    return isinstance(exc, (TimeoutError, ConnectionError))


def _blocks_completed_work_replay(receipt: object) -> bool:
    if not isinstance(receipt, dict):
        return False
    # Publication is reached only after the business steps complete. Unlike the
    # balance preview dependency, its receipt has no business_body_status field.
    return receipt.get("failed_step") in {"publish", "system_read_publish"} or (
        receipt.get("failed_step") == "source_preview"
        and receipt.get("business_body_status") == "completed"
    )


def _recover_pending_pnl_by_business_precompute(
    settings,
    *,
    include_pending_dirty: bool = True,
) -> int:
    """Dispatch durable dirty read-model work without requiring another HTTP request."""
    from backend.app.repositories.pnl_repo import PnlRepository
    from backend.app.services.pnl_by_business_page_lifecycle import (
        recover_pending_pnl_by_business_page_rebuilds,
    )
    from backend.app.services.pnl_service import (
        recover_pending_pnl_by_business_adjustment_handoffs,
        recover_pending_pnl_by_business_precompute,
    )

    failures = 0
    pending_work = []
    if include_pending_dirty:
        try:
            pending_work = PnlRepository(str(settings.duckdb_path)).list_pending_pnl_by_business_precompute()
        except (OSError, RuntimeError) as exc:
            logger.warning(
                "failed to read durable pnl_by_business precompute state: %s",
                type(exc).__name__,
            )
            pending_work = []
            failures += 1
        for pending in pending_work:
            try:
                recover_pending_pnl_by_business_precompute(
                    settings,
                    pending=dict(pending),
                )
            except Exception as exc:  # noqa: BLE001 - A failed year dispatch must be counted without blocking other durable years.
                logger.warning(
                    "failed to recover pnl_by_business precompute year=%s revision=%s: %s",
                    pending.get("year"),
                    pending.get("dependency_revision"),
                    type(exc).__name__,
                )
                failures += 1
    try:
        recover_pending_pnl_by_business_adjustment_handoffs(settings)
    except Exception as exc:  # noqa: BLE001 - Handoff callback failure must not prevent independent page-intent recovery.
        logger.warning(
            "failed to recover pnl_by_business adjustment handoffs: %s",
            type(exc).__name__,
        )
        failures += 1
    try:
        page_recovery = recover_pending_pnl_by_business_page_rebuilds(settings)
        page_failures = _receipt_count(page_recovery.get("failed_count") or 0)
        if page_failures:
            logger.warning(
                "pnl_by_business page recovery completed with %s failed intent(s)",
                page_failures,
            )
            failures += page_failures
    except Exception as exc:  # noqa: BLE001 - Page dispatch failures must produce a nonzero host-drain receipt.
        logger.warning(
            "failed to recover pnl_by_business page rebuilds: %s",
            type(exc).__name__,
        )
        failures += 1
    return failures


def _has_started_steps(run: dict[str, object]) -> bool:
    steps = run.get("steps")
    receipt = run.get("failure_receipt")
    return (
        bool(run.get("current_step"))
        or (isinstance(steps, list) and any(isinstance(step, dict) for step in steps))
        or (isinstance(receipt, dict) and (
            bool(receipt.get("current_step"))
            or bool(receipt.get("failed_step"))
            or bool(receipt.get("steps"))
        ))
    )


def drain_updates(settings=None, *, run_id: str | None = None) -> int:
    from backend.app.repositories.system_read_publication_repo import (
        active_system_read_scope,
    )

    with active_system_read_scope():
        if run_id is not None:
            return _drain_choice_stock_pit_update(settings or get_settings(), run_id)
        return _drain_updates_active(settings)


def _require_pit_maintenance() -> None:
    from scripts.dev_runtime_control import require_owner

    require_owner(
        Path(__file__).resolve().parents[3],
        os.environ.get("MOSS_DATA_UPDATE_PIT_MAINTENANCE_OWNER_TOKEN"),
    )
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        # Windows can take about two seconds to deliver a localhost refusal.
        # Keep a finite wait long enough to obtain that evidence, not an early
        # WSAEWOULDBLOCK result from an already closed API port.
        probe.settimeout(5)
        # Only an explicit connection refusal proves the local API is absent;
        # a timeout or another network error is not drain evidence.
        status = probe.connect_ex(("127.0.0.1", 7888))
        if status not in {errno.ECONNREFUSED, getattr(errno, "WSAECONNREFUSED", 10061)}:
            raise RuntimeError("股票 PIT 导入前必须由维护主机排空运行中的 API。")


def _drain_choice_stock_pit_update(settings, run_id: str) -> int:
    """A controlled host may drain exactly one reviewed PIT request."""
    from backend.app.tasks.data_update_choice_stock_pit import (
        STEP_NAME,
        _request_parameters,
        execute_choice_stock_pit_history,
        recover_choice_stock_pit_result,
        task_receipt_path,
    )

    try:
        with acquire_lock(WORKER_LOCK, base_dir=settings.governance_path, timeout_seconds=0.1):
            _require_pit_maintenance()
            with acquire_lock(QUEUE_LOCK, base_dir=settings.governance_path, timeout_seconds=1):
                run = next((row for row in latest_runs(settings.governance_path) if row["run_id"] == run_id), None)
                if run is None or run.get("workflow") != CHOICE_STOCK_PIT_WORKFLOW:
                    return 1
                if run.get("status") == "completed":
                    return 0
                if run.get("status") not in ACTIVE_STATUSES:
                    return 1
                try:
                    _request_parameters(settings, run)
                    if run["status"] == "running":
                        result = recover_choice_stock_pit_result(settings, run)
                        save_run(settings.governance_path, {
                            **run, "status": "completed", "current_step": None,
                            "finished_at": utc_now(), "updated_at": utc_now(),
                            "steps": [{"key": STEP_NAME, "label": "单日股票 PIT 来源导入",
                                       "status": "completed", "result": result}],
                            "choice_stock_pit_result": result,
                            "message": "单日股票 PIT 导入完成，已核对本次任务的提交回执。",
                        })
                        return 0
                    # This leaf never retries automatically: a missing terminal
                    # receipt cannot exclude a commit before process interruption.
                    if run["status"] == "retrying":
                        raise ValueError("股票 PIT 导入不能自动重跑，请核对原任务回执。")
                    attempt = run.get("attempt", 0)
                    if type(attempt) is not int or attempt < 0:
                        raise ValueError("股票 PIT 请求执行次数无效。")
                    run = {
                        **run, "status": "running", "attempt": attempt + 1,
                        "started_at": utc_now(), "updated_at": utc_now(),
                        "steps": [], "current_step": None, "retry_after": None,
                        "message": "正在复核单日股票 PIT 来源、计划和独立备份。",
                    }
                    run["task_receipt_path"] = str(task_receipt_path(settings, run))
                except (OSError, TypeError, ValueError, RuntimeError) as exc:
                    save_run(settings.governance_path, {
                        **run, "status": "failed", "updated_at": utc_now(),
                        "current_step": None, "retry_after": None,
                        "failure_receipt": {
                            "status": "failed", "failed_step": STEP_NAME,
                            "data_update_run_id": run_id,
                            "task_receipt_path": run.get("task_receipt_path"),
                            "commit_state": "unverified", "error_type": type(exc).__name__,
                        },
                        "message": "单日股票 PIT 请求或中断回执未通过核验，请检查后重新预检。",
                    })
                    return 1
                save_run(settings.governance_path, run)

            def progress(receipt: dict[str, object]) -> None:
                run.update(
                    steps=[{
                        "key": step["name"], "label": "单日股票 PIT 来源导入",
                        **{key: step[key] for key in (
                            "status", "started_at", "finished_at", "elapsed_seconds", "error_message", "result",
                        ) if key in step},
                    } for step in _receipt_steps(receipt.get("steps"))],
                    current_step=receipt.get("current_step"), updated_at=utc_now(),
                )
                save_run(settings.governance_path, run)

            try:
                _require_pit_maintenance()
                result = execute_choice_stock_pit_history(settings, run, progress)
                run.update(
                    status="completed", current_step=None, finished_at=utc_now(), updated_at=utc_now(),
                    choice_stock_pit_result=result,
                    message="单日股票 PIT 来源恢复完成，三个原生来源及写入边界已核验。",
                )
            except Exception as exc:  # noqa: BLE001 - All leaf failures must persist a terminal receipt and never replay finance or a possibly committed import.
                receipt = getattr(exc, "receipt", None)
                run.update(
                    status="failed", current_step=None, updated_at=utc_now(), retry_after=None,
                    failure_receipt=receipt if isinstance(receipt, dict) else {
                        "status": "failed", "failed_step": STEP_NAME,
                        "data_update_run_id": run_id, "task_receipt_path": run["task_receipt_path"],
                        "commit_state": "unverified", "error_type": type(exc).__name__,
                    },
                    message=f"单日股票 PIT 恢复未完成：{_error_text(exc)}请核对任务回执后重新预检。",
                )
                save_run(settings.governance_path, run)
                return 1
            save_run(settings.governance_path, run)
            return 0
    except (OSError, RuntimeError, TimeoutError, ValueError) as exc:
        logger.warning("controlled PIT drain unavailable: %s", type(exc).__name__)
        return 1


def _recover_publication_only(settings, original: dict[str, object]) -> dict[str, object]:
    """Reuse exact completion receipts and publishers, never materialization."""
    from backend.app.repositories.financial_result_publication_repo import (
        canonical_json_bytes,
        read_publication_pointer,
        validate_sealed_financial_generation,
    )
    from backend.app.repositories.governance_repo import GovernanceRepository
    from backend.app.tasks import system_read_publication as system
    from backend.app.tasks.financial_result_publication import publish_financial_result
    from backend.app.tasks.pnl_by_business_page_publication import (
        FINANCIAL_PUBLICATION_API_VERSION,
        FINANCIAL_PUBLICATION_SCHEMA_VERSION,
        build_pnl_by_business_financial_publication_plan,
    )
    from scripts.run_global_data_refresh import REQUIRED_DATE_TABLES

    report_date = str(original["report_date"])
    original_id = str(original["run_id"])
    committed = system.recover_committed_system_read_publication(
        settings, data_update_run_id=original_id, report_date=report_date, workflow="core_financial",
    )
    if committed is not None:
        return committed
    if not bool(getattr(settings, "system_read_publication_enabled", False)) or not bool(
        getattr(settings, "financial_publication_enabled", False)
    ):
        raise ValueError("完整只读发布机制尚未启用，不能恢复发布。")
    receipt = original["failure_receipt"]
    assert isinstance(receipt, dict)
    steps = tuple(dict(step) for step in _receipt_steps(receipt.get("steps"))[:-1])
    if receipt["failed_step"] == "publish":
        # Validate *all* original financial lineage before even the PnL pointer
        # can change. Use the same source verifier as the final system publisher.
        import duckdb

        source_path = Path(settings.duckdb_path).resolve()
        writer_lock = resolve_duckdb_writer_lock(source_path, ttl_seconds=7200)
        with acquire_lock(writer_lock, base_dir=source_path.parent):
            refs = system._collect_lineage_references(steps)
            frozen = system._freeze_result_lineage(
                GovernanceRepository(base_dir=settings.governance_path),
                lineage_references=refs, report_date=report_date,
            )
            manifests = system._read_source_preview_manifest_rows(settings, governance_path=Path(settings.governance_path))
            with duckdb.connect(str(source_path), read_only=True) as conn:
                system._source_cut_snapshot(
                    conn, table_specs=system._required_table_specs(REQUIRED_DATE_TABLES, report_date=report_date),
                    governance_streams=frozen, lineage_references=refs, report_date=report_date,
                    source_manifest_rows=manifests, source_preview_archive_root=getattr(settings, "local_archive_path", None),
                )
            root = Path(settings.financial_publication_root)
            pointer = read_publication_pointer(root, require_valid=True)
            previous = str(pointer["generation"]) if pointer is not None else None
            plan = build_pnl_by_business_financial_publication_plan(
                settings, report_date=report_date, run_id=str(original["global_run_id"]),
                expected_previous_generation=previous, step_receipts=steps,
            )
            prepared_result = steps[-1]["result"]
            assert isinstance(prepared_result, dict)
            prepared_versions = prepared_result.get("dependency_versions")
            if not isinstance(prepared_versions, dict) or not prepared_versions or any(
                plan.dependency_versions.get(key) != str(value) for key, value in prepared_versions.items()
            ):
                raise ValueError("已完成财务结果的来源版本已变化，请重新核对后安排更新。")
            if pointer is not None and previous == plan.generation:
                existing = validate_sealed_financial_generation(
                    root, generation=plan.generation, reader_api_version=FINANCIAL_PUBLICATION_API_VERSION,
                    reader_schema_version=FINANCIAL_PUBLICATION_SCHEMA_VERSION,
                    expected_manifest_sha256=str(pointer["manifest_sha256"]),
                )
                expected_results = {
                    str(step["name"]): {"status": "completed", "result_sha256": hashlib.sha256(canonical_json_bytes(step["result"])).hexdigest()}
                    for step in steps
                }
                sealed = existing.manifest.get("sealed_payload")
                if not isinstance(sealed, dict) or sealed.get("step_results") != expected_results:
                    raise ValueError("已提交损益发布与原始财务完成回执不一致。")
                pnl_result = {"status": "completed", "generation": existing.generation,
                              "manifest_sha256": existing.manifest_sha256, "recovered_after_commit": True}
            else:
                publication = publish_financial_result(
                    source_duckdb_path=source_path, publication_root=root, plan=plan, writer_lock_already_held=True,
                )
                pnl_result = {"status": "completed", "generation": publication.generation,
                              "manifest_sha256": publication.manifest_sha256,
                              "recovered_after_commit": publication.recovered_after_commit}
            steps = (*steps, {"name": "publish", "status": "completed", "result": pnl_result})
    stored_pnl_result = steps[-1]["result"]
    assert isinstance(stored_pnl_result, dict)
    publication = system.publish_system_read_generation(
        settings, report_date=report_date, data_update_run_id=original_id,
        global_run_id=str(original["global_run_id"]), step_receipts=steps,
        pnl_generation=str(stored_pnl_result["generation"]), pnl_manifest_sha256=str(stored_pnl_result["manifest_sha256"]),
        required_date_tables=REQUIRED_DATE_TABLES,
    )
    return {"status": "completed", "generation": publication.generation,
            "manifest_sha256": publication.manifest_sha256,
            "recovered_after_commit": publication.recovered_after_commit,
            "data_update_run_id": original_id, "global_run_id": original["global_run_id"]}


def _drain_publication_recovery(settings, snapshot: dict[str, object]) -> int:
    from backend.app.repositories.financial_result_publication_repo import canonical_json_bytes

    run = snapshot
    try:
        with acquire_lock(QUEUE_LOCK, base_dir=settings.governance_path, timeout_seconds=1):
            runs = latest_runs(settings.governance_path)
            run = next(item for item in runs if item["run_id"] == snapshot["run_id"])
            if run.get("status") not in ACTIVE_STATUSES:
                return 0
            original = next((item for item in runs if item["run_id"] == run.get("recovery_of_run_id")), None)
            completed_before_receipt = original is not None and original.get("status") == "completed" and (
                original.get("publication_recovered_by_run_id") == run["run_id"]
            )
            if original is None or (not completed_before_receipt and not publication_recovery_eligibility(original)["available"]):
                raise ValueError("原始财务完成回执已变化或不具备恢复条件。")
            digest = hashlib.sha256(canonical_json_bytes(original["failure_receipt"])).hexdigest()
            if digest != run.get("expected_failure_receipt_sha256") or original.get("report_date") != run.get("report_date"):
                raise ValueError("原始财务完成回执已变化，停止恢复发布。")
            if any(item.get("status") in ACTIVE_STATUSES and item["run_id"] != run["run_id"] for item in runs):
                raise ValueError("已有其他活跃财务请求，停止恢复发布。")
            run = {**run, "status": "running", "current_step": "system_read_publish",
                   "attempt": _receipt_count(run.get("attempt")) + 1, "updated_at": utc_now(),
                   "message": "正在核验已完成结果并恢复发布。"}
            save_run(settings.governance_path, run)
        result = _recover_publication_only(settings, original)
        with acquire_lock(QUEUE_LOCK, base_dir=settings.governance_path, timeout_seconds=1):
            finished = utc_now()
            recovery_step: dict[str, object] = {"key": "system_read_publish", "label": "系统只读快照发布",
                             "status": "completed", "result": result}
            original_steps = [dict(step) for step in _receipt_steps(original.get("steps"))
                              if step.get("key") != "system_read_publish"]
            for step in original_steps:
                if step.get("key") == "publish":
                    step.update(status="completed", error_message=None)
            original_steps.append(recovery_step)
            save_run(settings.governance_path, {**original, "status": "completed", "current_step": None,
                "steps": original_steps,
                "updated_at": finished, "finished_at": finished, "system_read_publication": result,
                "publication_recovered_by_run_id": run["run_id"],
                "message": "已核验恢复发布，财务计算未重复执行。"})
            save_run(settings.governance_path, {**run, "status": "completed", "current_step": None,
                "steps": [recovery_step], "system_read_publication": result, "updated_at": finished,
                "finished_at": finished, "message": "发布已恢复，财务计算未重复执行。"})
        return 0
    except Exception as exc:  # noqa: BLE001 - publication recovery must persist a failed receipt without financial retry
        message = "发布恢复未完成，来源或结果版本可能已变化，请核对原始完成回执和发布条件。"
        save_run(settings.governance_path, {**run, "status": "failed", "current_step": None,
            "updated_at": utc_now(), "retry_after": None, "message": message,
            "steps": [{"key": "system_read_publish", "label": "系统只读快照发布", "status": "failed",
                       "error_message": _error_text(exc)}]})
        return 1


def _drain_updates_active(settings=None) -> int:
    settings = settings or get_settings()
    failures = 0
    worker_lock_acquired = False
    try:
        with acquire_lock(WORKER_LOCK, base_dir=settings.governance_path, timeout_seconds=0.1):
            worker_lock_acquired = True
            for snapshot in reversed(latest_runs(settings.governance_path)):
                if snapshot.get("status") not in ACTIVE_STATUSES:
                    continue
                if snapshot.get("workflow") == CHOICE_STOCK_PIT_WORKFLOW:
                    # PIT writes require the host's maintenance lease and an
                    # explicit request id. Never consume them in the scheduler.
                    continue
                if snapshot.get("recovery_mode") == "publication_only":
                    failures += _drain_publication_recovery(settings, snapshot)
                    continue
                with acquire_lock(QUEUE_LOCK, base_dir=settings.governance_path, timeout_seconds=1):
                    run = next(
                        row for row in latest_runs(settings.governance_path) if row["run_id"] == snapshot["run_id"]
                    )
                    if run["status"] not in ACTIVE_STATUSES:
                        continue
                    # Acquiring the worker lock proves the old worker is no longer
                    # executing. Interrupted runs require an explicit, auditable rerun.
                    if run["status"] == "running":
                        recovered_publication = None
                        try:
                            from backend.app.tasks.system_read_publication import (
                                recover_committed_system_read_publication,
                            )

                            recovered_publication = recover_committed_system_read_publication(
                                settings,
                                data_update_run_id=str(run["run_id"]),
                                report_date=str(run["report_date"]),
                                workflow=str(run.get("workflow", "core_financial")),
                            )
                        except (OSError, RuntimeError, ValueError) as exc:
                            logger.warning(
                                "failed to inspect committed system read publication for interrupted run: %s",
                                type(exc).__name__,
                            )
                        if recovered_publication is not None:
                            recovered_steps = _receipt_steps(run.get("steps"))
                            if not any(
                                str(step.get("key") or "") == "system_read_publish"
                                for step in recovered_steps
                                if isinstance(step, dict)
                            ):
                                recovered_steps.append(
                                    {
                                        "key": "system_read_publish",
                                        "label": "系统只读快照发布",
                                        "status": "completed",
                                        "result": recovered_publication,
                                    }
                                )
                            recovered_run = {
                                **run,
                                "status": "completed",
                                "steps": recovered_steps,
                                "system_read_publication": recovered_publication,
                                "finished_at": utc_now(),
                                "updated_at": utc_now(),
                                "current_step": None,
                                "message": "更新已完成，系统只读快照提交回执已恢复。",
                            }
                            recovered_global_run_id = recovered_publication.get(
                                "global_run_id"
                            )
                            if (
                                isinstance(recovered_global_run_id, str)
                                and recovered_global_run_id
                            ):
                                recovered_run["global_run_id"] = recovered_global_run_id
                            save_run(
                                settings.governance_path,
                                recovered_run,
                            )
                            continue
                        save_run(
                            settings.governance_path,
                            {
                                **run,
                                "status": "failed",
                                "updated_at": utc_now(),
                                "message": "上次执行中断，结果未完成核验。请检查后重新提交该报告日。",
                            },
                        )
                        failures += 1
                        continue
                    if run["status"] == "retrying" and (
                        _has_started_steps(run)
                        or _blocks_completed_work_replay(run.get("failure_receipt"))
                    ):
                        save_run(
                            settings.governance_path,
                            {
                                **run,
                                "status": "failed",
                                "updated_at": utc_now(),
                                "current_step": None,
                                "retry_after": None,
                                "message": "上次执行已开始更新步骤，已停止自动重跑。请人工复核完成结果及失败回执。",
                            },
                        )
                        failures += 1
                        continue
                    try:
                        (
                            use_existing_fx_only,
                            expected_fx_source_version,
                            use_existing_curves_only,
                            expected_curve_snapshots,
                        ) = _recovery_parameters(run)
                    except (TypeError, ValueError) as exc:
                        save_run(
                            settings.governance_path,
                            {
                                **run,
                                "status": "failed",
                                "updated_at": utc_now(),
                                "message": f"更新请求参数无效：{_error_text(exc)}",
                            },
                        )
                        failures += 1
                        continue
                    if run.get("retry_after") and str(run["retry_after"]) > utc_now():
                        continue
                    try:
                        preflight = input_preflight(
                            settings, str(run["report_date"]), str(run.get("workflow", "core_financial"))
                        )
                    except (OSError, RuntimeError, ValueError) as exc:
                        save_run(
                            settings.governance_path,
                            {
                                **run,
                                "status": "failed",
                                "updated_at": utc_now(),
                                "message": f"文件检查失败：{_error_text(exc)}",
                            },
                        )
                        failures += 1
                        continue
                    if not preflight["ready"]:
                        waiting = bool(run.get("wait_for_inputs"))
                        status = "waiting_inputs" if waiting else "failed"
                        if run.get("status") != status or run.get("preflight") != preflight:
                            save_run(
                                settings.governance_path,
                                {
                                    **run,
                                    "status": status,
                                    "preflight": preflight,
                                    "updated_at": utc_now(),
                                    "message": "等待该报告日的源文件到齐。"
                                    if waiting
                                    else "文件在受理后发生变化，未开始更新。请重新检查。",
                                },
                            )
                        failures += int(not waiting)
                        continue
                    run = {
                        **run,
                        "status": "running",
                        "use_existing_fx_only": use_existing_fx_only,
                        "expected_fx_source_version": expected_fx_source_version,
                        "use_existing_curves_only": use_existing_curves_only,
                        "expected_curve_snapshots": expected_curve_snapshots,
                        "attempt": _receipt_count(run.get("attempt", 0)) + 1,
                        "started_at": utc_now(),
                        "updated_at": utc_now(),
                        "preflight": preflight,
                        "steps": [],
                        "current_step": None,
                        "message": "正在校验源文件并执行更新。",
                    }
                    save_run(settings.governance_path, run)

                def progress(receipt: dict[str, object], current_run=run) -> None:
                    steps = []
                    for item in _receipt_steps(receipt.get("steps")):
                        step = {
                            "key": item["name"],
                            "label": STEP_LABELS.get(str(item["name"]), "更新步骤"),
                            "status": item["status"],
                            "error_message": item.get("error_message"),
                            **{
                                key: item[key]
                                for key in ("started_at", "finished_at", "elapsed_seconds")
                                if key in item
                            },
                        }
                        if item["name"] in {
                            "daily_balance_and_risk",
                            "pnl_by_business_page_prepare",
                            "publish",
                            "system_read_publish",
                        }:
                            for key in ("error_type", "failure_category", "resource_limits"):
                                if key in item:
                                    step[key] = item[key]
                            step_result = item.get("result")
                            if isinstance(step_result, dict):
                                step["result"] = dict(step_result)
                        steps.append(step)
                    current_run.update(steps=steps, current_step=receipt.get("current_step"), updated_at=utc_now())
                    global_run_id = receipt.get("run_id")
                    if isinstance(global_run_id, str) and global_run_id:
                        current_run["global_run_id"] = global_run_id
                    save_run(settings.governance_path, current_run)

                progress.data_update_run_id = str(run["run_id"])  # type: ignore[attr-defined]

                try:
                    if run.get("workflow") == "balance_daily":
                        result = _execute_balance(settings, str(run["report_date"]), progress)
                    elif use_existing_fx_only and use_existing_curves_only:
                        result = _execute_core(
                            settings,
                            str(run["report_date"]),
                            progress,
                            use_existing_fx_only=True,
                            expected_fx_source_version=expected_fx_source_version,
                            use_existing_curves_only=True,
                            expected_curve_snapshots=expected_curve_snapshots,
                        )
                    elif use_existing_fx_only:
                        result = _execute_core(
                            settings,
                            str(run["report_date"]),
                            progress,
                            use_existing_fx_only=True,
                            expected_fx_source_version=expected_fx_source_version,
                        )
                    elif use_existing_curves_only:
                        result = _execute_core(
                            settings,
                            str(run["report_date"]),
                            progress,
                            use_existing_curves_only=True,
                            expected_curve_snapshots=expected_curve_snapshots,
                        )
                    else:
                        result = _execute_core(
                            settings,
                            str(run["report_date"]),
                            progress,
                        )
                    if result.get("status") != "completed":
                        raise ValueError("刷新链路未返回完整成功回执。")
                    publish_balance_snapshot = run.get("workflow") == "balance_daily" and bool(
                        getattr(settings, "system_read_publication_enabled", False)
                    )
                    if publish_balance_snapshot:
                        from backend.app.tasks.system_read_publication import (
                            publish_qualified_balance_daily_system_read_generation,
                        )

                        publish_started_at = utc_now()
                        publish_started = perf_counter()
                        run.update(
                            current_step="system_read_publish",
                            updated_at=utc_now(),
                            message="余额结果已核验，正在提交系统完整只读快照。",
                        )
                        save_run(settings.governance_path, run)
                        writer_receipt = {
                            "status": "completed",
                            "run_id": str(run["run_id"]),
                            "workflow": "balance_daily",
                            "report_date": str(run["report_date"]),
                            "pipeline": result.get("pipeline"),
                        }
                        try:
                            publication = publish_qualified_balance_daily_system_read_generation(
                                settings,
                                data_update_run_id=str(run["run_id"]),
                                report_date=str(run["report_date"]),
                                writer_receipt=writer_receipt,
                            )
                        except Exception as exc:
                            failed_step = {
                                "key": "system_read_publish",
                                "label": STEP_LABELS.get(
                                    "system_read_publish", "系统只读快照发布"
                                ),
                                "status": "failed",
                                "started_at": publish_started_at,
                                "finished_at": utc_now(),
                                "elapsed_seconds": round(
                                    perf_counter() - publish_started, 3
                                ),
                                "error_message": _error_text(exc),
                            }
                            run["steps"] = [*_receipt_steps(run.get("steps")), failed_step]
                            receipt: dict[str, object] = {
                                "status": "failed",
                                "failed_step": "system_read_publish",
                                "steps": _receipt_steps(run["steps"]),
                            }
                            raise _SystemReadPublicationFailed(
                                "系统完整只读快照发布失败。",
                                receipt=receipt,
                            ) from exc
                        publication_result = {
                            "status": "completed",
                            "generation": publication.generation,
                            "manifest_sha256": publication.manifest_sha256,
                            "writer_run_id": str(run["run_id"]),
                        }
                        run["steps"] = [
                            *_receipt_steps(run.get("steps")),
                            {
                                "key": "system_read_publish",
                                "label": STEP_LABELS.get(
                                    "system_read_publish", "系统只读快照发布"
                                ),
                                "status": "completed",
                                "started_at": publish_started_at,
                                "finished_at": utc_now(),
                                "elapsed_seconds": round(
                                    perf_counter() - publish_started, 3
                                ),
                                "result": publication_result,
                            },
                        ]
                        run["system_read_publication"] = publication_result
                    run.update(
                        status="completed",
                        finished_at=utc_now(),
                        updated_at=utc_now(),
                        current_step=None,
                        message="更新完成，必需结果表已通过该报告日核验。",
                    )
                except Exception as exc:  # noqa: BLE001 - Arbitrary finance executors require a terminal/retry receipt and completed-work replay protection.
                    cause = exc.__cause__ or exc
                    failure_receipt = getattr(exc, "receipt", None)
                    retry = (
                        not _has_started_steps({**run, "failure_receipt": failure_receipt})
                        and not _blocks_completed_work_replay(failure_receipt)
                        and _transient(cause)
                        and _receipt_count(run["attempt"]) < 3
                    )
                    run.update(
                        status="retrying" if retry else "failed",
                        updated_at=utc_now(),
                        current_step=None,
                        message=f"更新未完成：{_error_text(cause)}"
                        + (" 已开始更新步骤，需人工复核，不自动重试。"
                           if _has_started_steps({**run, "failure_receipt": failure_receipt}) else ""),
                        retry_after=(datetime.now(UTC) + timedelta(minutes=10)).isoformat() if retry else None,
                    )
                    if isinstance(failure_receipt, dict):
                        run["failure_receipt"] = dict(failure_receipt)
                    failures += 1
                save_run(settings.governance_path, run)
            failures += _recover_pending_pnl_by_business_precompute(settings)
    except TimeoutError:
        if not worker_lock_acquired:
            # Another drain owns the queue. Its receipt is authoritative.
            return 0
        raise
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", help="single PIT request id selected by the controlled maintenance host")
    args = parser.parse_args()
    return drain_updates(run_id=args.run_id)


if __name__ == "__main__":
    raise SystemExit(main())
