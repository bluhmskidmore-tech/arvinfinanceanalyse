"""Drain the data-center request queue from the host scheduler, independently of HTTP."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from time import perf_counter

from backend.app.governance.locks import acquire_lock
from backend.app.governance.settings import get_settings
from backend.app.repositories.data_update_repo import latest_runs, save_run, verify_daily_balance_date
from backend.app.services.data_update_service import (
    ACTIVE_STATUSES,
    QUEUE_LOCK,
    STEP_LABELS,
    WORKER_LOCK,
    input_preflight,
    utc_now,
)

logger = logging.getLogger(__name__)


def _execute_core(
    settings,
    report_date: str,
    on_progress,
) -> dict[str, object]:
    from backend.app.services.pnl_source_service import load_latest_pnl_refresh_input
    from scripts.run_global_data_refresh import run_global_data_refresh

    # Parse the required PnL input before any balance/FX writes. Optional non-standard
    # families retain the canonical parser's existing rules.
    inputs = load_latest_pnl_refresh_input(
        governance_dir=settings.governance_path,
        data_root=settings.data_input_root,
        report_date=report_date,
    )
    if inputs.report_date != report_date or not inputs.fi_rows:
        raise ValueError("该报告日的固收损益文件没有可用记录。")
    return run_global_data_refresh(
        report_date=report_date,
        on_progress=on_progress,
    )


def _error_text(exc: Exception) -> str:
    return " ".join(str(exc).split())[:400] or exc.__class__.__name__


def _execute_balance(settings, report_date: str, on_progress) -> dict[str, object]:
    from backend.app.tasks.formal_balance_pipeline import run_formal_balance_pipeline_sync

    balance_step = "daily_balance_and_risk"
    on_progress({"current_step": balance_step, "steps": []})
    balance_started_at = utc_now()
    balance_started = perf_counter()
    try:
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
    on_progress({"current_step": None, "steps": steps})
    return balance_result


def _transient(exc: Exception) -> bool:
    # Only transient I/O/lock failures are retried. Formula, schema, and validation
    # failures stay terminal; never repeatedly rewrite finance facts on a bad input.
    return isinstance(exc, (TimeoutError, ConnectionError))


def _has_started_steps(run: dict[str, object]) -> bool:
    steps = run.get("steps")
    return bool(run.get("current_step")) or (isinstance(steps, list) and any(isinstance(step, dict) for step in steps))


def drain_updates(settings=None) -> int:
    """Drain governed update requests. A previous running attempt requires manual review."""
    settings = settings or get_settings()
    failures = 0
    worker_lock_acquired = False
    try:
        with acquire_lock(WORKER_LOCK, base_dir=settings.governance_path, timeout_seconds=0.1):
            worker_lock_acquired = True
            for snapshot in reversed(latest_runs(settings.governance_path)):
                if snapshot.get("status") not in ACTIVE_STATUSES:
                    continue
                with acquire_lock(QUEUE_LOCK, base_dir=settings.governance_path, timeout_seconds=1):
                    run = next(
                        row for row in latest_runs(settings.governance_path) if row["run_id"] == snapshot["run_id"]
                    )
                    if run["status"] not in ACTIVE_STATUSES:
                        continue
                    if run["status"] == "running":
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
                    if run["status"] == "retrying" and _has_started_steps(run):
                        save_run(
                            settings.governance_path,
                            {
                                **run,
                                "status": "failed",
                                "retry_after": None,
                                "updated_at": utc_now(),
                                "message": "上次执行已开始更新步骤，需人工复核结果，不自动重试。",
                            },
                        )
                        failures += 1
                        continue
                    if run.get("retry_after") and str(run["retry_after"]) > utc_now():
                        continue
                    try:
                        preflight = input_preflight(
                            settings,
                            str(run["report_date"]),
                            str(run.get("workflow", "core_financial")),
                        )
                    except Exception as exc:
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
                    attempt_value = run.get("attempt", 0)
                    if not isinstance(attempt_value, (int, float, str, bytes, bytearray)):
                        raise TypeError("无效的更新尝试次数。")
                    attempt = int(attempt_value) + 1
                    run = {
                        **run,
                        "status": "running",
                        "attempt": attempt,
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
                    receipt_steps = receipt.get("steps", [])
                    if not isinstance(receipt_steps, Iterable):
                        raise TypeError("无效的更新步骤回执。")
                    for item in receipt_steps:
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
                        if item["name"] == "daily_balance_and_risk" and isinstance(item.get("result"), dict):
                            step["result"] = dict(item["result"])
                        steps.append(step)
                    current_run.update(
                        steps=steps,
                        current_step=receipt.get("current_step"),
                        updated_at=utc_now(),
                    )
                    global_run_id = receipt.get("run_id")
                    if isinstance(global_run_id, str) and global_run_id:
                        current_run["global_run_id"] = global_run_id
                    save_run(settings.governance_path, current_run)

                try:
                    if run.get("workflow") == "balance_daily":
                        result = _execute_balance(settings, str(run["report_date"]), progress)
                    else:
                        result = _execute_core(settings, str(run["report_date"]), progress)
                    if result.get("status") != "completed":
                        raise ValueError("刷新链路未返回完整成功回执。")
                    run.update(
                        status="completed",
                        finished_at=utc_now(),
                        updated_at=utc_now(),
                        current_step=None,
                        message="更新完成，必需结果表已通过该报告日核验。",
                    )
                except Exception as exc:
                    started_steps = _has_started_steps(run)
                    retry = not started_steps and _transient(exc) and attempt < 3
                    run.update(
                        status="retrying" if retry else "failed",
                        updated_at=utc_now(),
                        current_step=None,
                        message=f"更新未完成：{_error_text(exc)}"
                        + (" 已开始更新步骤，需人工复核，不自动重试。" if started_steps else ""),
                        retry_after=(datetime.now(UTC) + timedelta(minutes=10)).isoformat() if retry else None,
                    )
                    failures += 1
                save_run(settings.governance_path, run)
    except TimeoutError:
        if not worker_lock_acquired:
            # Another drain owns the queue. Its receipt is authoritative.
            return 0
        raise
    return 1 if failures else 0


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()
    return drain_updates()


if __name__ == "__main__":
    raise SystemExit(main())
