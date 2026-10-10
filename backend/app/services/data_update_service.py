"""Data-center controls. DuckDB is read-only; execution belongs to tasks."""

from __future__ import annotations

import csv
import hashlib
import re
import subprocess
import time
from datetime import UTC, date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import duckdb
from backend.app.core_finance.source_rules import describe_source_file
from backend.app.governance.locks import LockDefinition, acquire_lock
from backend.app.repositories.data_update_repo import financial_dates, latest_runs, save_run
from backend.app.repositories.financial_result_publication_repo import canonical_json_bytes
from backend.app.repositories.governance_repo import GovernanceRepository
from backend.app.repositories.object_store_repo import resolve_local_archive_path
from backend.app.repositories.source_manifest_repo import SourceManifestRepository
from backend.app.schemas.curve_recovery import normalize_curve_recovery_options
from backend.app.services.data_health_service import (
    _SCHTASKS_TIMEOUT_SECONDS,
    _parse_schtasks_csv,
    _run_schtasks_query,
)
from backend.app.services.ingest_service import _iter_data_input_scan_paths

QUEUE_TASK_NAME = "MOSS-DataUpdateQueue"
MARKET_TASK_NAME = "MOSS-DailyDataRefresh"
QUEUE_LOCK = LockDefinition(key="lock:data-update-requests", ttl_seconds=60)
WORKER_LOCK = LockDefinition(key="lock:data-update-worker", ttl_seconds=21600)
ACTIVE_STATUSES = frozenset({"queued", "waiting_inputs", "running", "retrying"})
CHOICE_STOCK_PIT_WORKFLOW = "choice_stock_pit_history"
TASK_LABELS = {
    QUEUE_TASK_NAME: "财务更新与文件检查",
    MARKET_TASK_NAME: "每日市场数据",
    "MOSS-SupplyFreshnessSentry": "市场数据时效检查",
    "MOSS-BalanceMovementFreshness": "余额变动检查",
    "MOSS-MonthlyWalkForward": "月度策略验证",
}
STEP_LABELS = {
    "daily_balance_and_risk": "余额、持仓与风险更新",
    "formal_balance": "余额与汇率",
    "bond_analytics": "债券分析",
    "risk_tensor": "风险张量",
    "formal_pnl": "正式损益",
    "product_category_pnl": "产品损益",
    "accounting_asset_movement": "余额变动",
    "source_preview": "来源摘要",
    "verify": "结果日期核验",
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def normalize_report_date(value: str) -> str:
    normalized = date.fromisoformat(value).isoformat()
    if normalized != value:
        raise ValueError("报告日期必须使用 YYYY-MM-DD 格式。")
    return normalized


def _explicit_file_date(name: str, report_date: str, granularity: str | None) -> bool:
    # The legacy source parser falls back to today's date for an undated name.
    # Automated updates must not turn that fallback into evidence of file arrival.
    if granularity == "month" and re.search(r"FI损益\d{6}(?:\(\d+\))?\.xls$", name, re.IGNORECASE):
        return True
    for pattern in (r"(?<!\d)(\d{4})(\d{2})(\d{2})(?!\d)", r"(?<!\d)(\d{4})[.\-](\d{1,2})[.\-](\d{1,2})(?!\d)"):
        for match in re.finditer(pattern, name):
            try:
                if date(*(int(part) for part in match.groups())).isoformat() == report_date:
                    return True
            except ValueError:
                continue
    return False


def input_preflight(settings, report_date: str, workflow: str = "core_financial") -> dict[str, object]:
    """Check file arrival only. Formal parsers and FX validation still run in tasks."""
    report_date = normalize_report_date(report_date)
    families = {"zqtz": "债券余额文件", "tyw": "同业余额文件", "pnl": "固收损益文件"}
    if workflow == "balance_daily":
        families.pop("pnl")
    elif workflow != "core_financial":
        raise ValueError("不支持的更新范围。")
    direct: dict[str, list[Path]] = {key: [] for key in families}
    for path in _iter_data_input_scan_paths(Path(settings.data_input_root)):
        metadata = describe_source_file(path.name)
        if (
            metadata.report_date == report_date
            and metadata.source_family in direct
            and _explicit_file_date(path.name, report_date, metadata.report_granularity)
        ):
            direct[metadata.source_family].append(path)
    manifest = SourceManifestRepository(
        governance_repo=GovernanceRepository(base_dir=settings.governance_path)
    ).select_for_snapshot_materialization(source_families=list(families), report_date=report_date)
    checks: list[dict[str, object]] = []
    for family, label in families.items():
        paths = direct[family] or [
            resolve_local_archive_path(str(row["archived_path"]), settings.local_archive_path)
            for row in manifest if row.get("source_family") == family
        ]
        present = [path for path in paths if path.is_file()]
        settled = bool(present) and all(
            path.stat().st_size > 0 and time.time() - path.stat().st_mtime >= 60 for path in present
        )
        checks.append(
            {
                "key": family,
                "label": label,
                "status": "ready" if settled else "waiting",
                "files": [path.name for path in present],
                "detail": "文件已到齐，执行时校验内容。"
                if settled
                else ("文件正在写入，请等待一分钟。" if present else "尚未找到该报告日的文件。"),
            }
        )
    fx_path = str(
        getattr(settings, "fx_official_source_path", "") or getattr(settings, "fx_mid_csv_path", "") or ""
    ).strip()
    fx_ready = not fx_path or Path(fx_path).is_file()
    checks.append(
        {
            "key": "fx",
            "label": "汇率来源",
            "status": "ready" if fx_ready else "waiting",
            "files": [Path(fx_path).name] if fx_path and fx_ready else [],
            "detail": "执行时按既有来源校验报告日汇率。" if fx_ready else "已配置的汇率文件不存在。",
        }
    )
    return {
        "report_date": report_date,
        "workflow": workflow,
        "ready": all(row["status"] == "ready" for row in checks),
        "input_directory": str(settings.data_input_root),
        "checks": checks,
    }


def scheduled_updates() -> dict[str, object]:
    try:
        tasks: dict[str, dict[str, str]] = {}
        targeted_deadline = time.monotonic() + _SCHTASKS_TIMEOUT_SECONDS
        for task_name in TASK_LABELS:
            remaining = targeted_deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("targeted schtasks query budget exhausted")
            parsed = _parse_schtasks_csv(
                _run_schtasks_query(task_name, timeout=remaining)
            )
            matching = [row for row in parsed if row.get("task_name") == task_name]
            if len(parsed) != 1 or len(matching) != 1:
                raise ValueError(f"targeted schtasks query did not return exactly {task_name}")
            tasks[task_name] = matching[0]
    except (OSError, ValueError, csv.Error, subprocess.SubprocessError):
        try:
            tasks = {row["task_name"]: row for row in _parse_schtasks_csv(_run_schtasks_query())}
        except (OSError, ValueError, csv.Error, subprocess.SubprocessError):
            return {"status": "error", "detail": "无法读取本机计划任务，请检查运行环境或查询权限。", "tasks": []}
    rows = []
    for name, label in TASK_LABELS.items():
        task = tasks.get(name)
        if task is None:
            rows.append(
                {
                    "task_name": name,
                    "label": label,
                    "status": "missing",
                    "last_run_time": None,
                    "next_run_time": None,
                    "last_result": None,
                }
            )
            continue
        state = task["schtasks_status"].casefold()
        if state in {"disabled", "禁用", "已禁用"}:
            status = "disabled"
        elif state in {"running", "正在运行", "运行中"}:
            status = "running"
        elif task["last_result"] in {"267011", "0x41303"}:
            status = "never_run"
        elif task["last_result"] == "0":
            status = "ready"
        else:
            status = "warning"
        rows.append({**task, "label": label, "status": status})
    return {"status": "available", "detail": "计划任务的执行结果与数据日期分别核验。", "tasks": rows}


def require_scheduler(task_name: str) -> None:
    snapshot = scheduled_updates()
    tasks = snapshot["tasks"]
    if not isinstance(tasks, list):
        raise RuntimeError("Invalid scheduled task snapshot.")
    task = next((row for row in tasks if row["task_name"] == task_name), None)
    if task is None or task["status"] in {"missing", "disabled"}:
        raise RuntimeError("后台任务尚未启用，当前无法接收更新请求。")


def request_core_update(
    settings,
    *,
    report_date: str,
    wait_for_inputs: bool,
    requested_by: str,
    idempotency_key: str,
    workflow: str = "core_financial",
    use_existing_fx_only: bool = False,
    expected_fx_source_version: str | None = None,
    use_existing_curves_only: bool = False,
    expected_curve_snapshots: list[dict[str, str]] | None = None,
    recovery_of_run_id: str | None = None,
) -> dict[str, object]:
    report_date = normalize_report_date(report_date)
    if workflow not in {"balance_daily", "core_financial"}:
        raise ValueError("不支持的更新范围。")
    if type(use_existing_fx_only) is not bool:
        raise ValueError("现有汇率恢复模式必须是布尔值。")
    if expected_fx_source_version is not None and (
        not isinstance(expected_fx_source_version, str) or not expected_fx_source_version.strip()
    ):
        raise ValueError("预期汇率来源版本必须是非空字符串。")
    if recovery_of_run_id is not None and (not isinstance(recovery_of_run_id, str) or not recovery_of_run_id.strip()):
        raise ValueError("恢复来源请求编号必须是非空字符串。")
    expected_fx_source_version = expected_fx_source_version.strip() if expected_fx_source_version is not None else None
    recovery_of_run_id = recovery_of_run_id.strip() if recovery_of_run_id is not None else None
    expected_curve_snapshots = normalize_curve_recovery_options(
        use_existing_curves_only=use_existing_curves_only,
        expected_curve_snapshots=expected_curve_snapshots,
    )
    if use_existing_fx_only:
        if workflow != "core_financial":
            raise ValueError("现有汇率恢复模式仅支持完整财务更新。")
        if expected_fx_source_version is None:
            raise ValueError("现有汇率恢复模式必须指定汇率来源版本。")
    elif expected_fx_source_version is not None:
        raise ValueError("普通更新不能携带预期汇率来源版本。")
    if use_existing_curves_only and workflow != "core_financial":
        raise ValueError("现有曲线恢复模式仅支持完整财务更新。")
    recovery_mode = use_existing_fx_only or use_existing_curves_only
    if recovery_mode and recovery_of_run_id is None:
        raise ValueError("恢复模式必须指定原失败请求。")
    if not recovery_mode and recovery_of_run_id is not None:
        raise ValueError("普通更新不能携带恢复来源请求编号。")
    with acquire_lock(QUEUE_LOCK, base_dir=settings.governance_path, timeout_seconds=1):
        runs = latest_runs(settings.governance_path)
        if recovery_of_run_id is not None:
            recovery_run = next(
                (run for run in runs if run.get("run_id") == recovery_of_run_id),
                None,
            )
            if (
                recovery_run is None
                or recovery_run.get("report_date") != report_date
                or recovery_run.get("workflow", "core_financial") != "core_financial"
                or recovery_run.get("status") != "failed"
            ):
                raise ValueError("恢复来源必须是同一报告日已失败的完整财务更新请求。")
        for run in runs:
            if run.get("idempotency_key") == idempotency_key and run.get("requested_by") == requested_by:
                if (
                    run.get("report_date") != report_date
                    or run.get("wait_for_inputs") != wait_for_inputs
                    or run.get("workflow", "core_financial") != workflow
                    or run.get("use_existing_fx_only", False) is not use_existing_fx_only
                    or run.get("expected_fx_source_version") != expected_fx_source_version
                    or run.get("use_existing_curves_only", False) is not use_existing_curves_only
                    or run.get("expected_curve_snapshots") != expected_curve_snapshots
                    or run.get("recovery_of_run_id") != recovery_of_run_id
                ):
                    raise ValueError("同一请求编号不能用于不同更新参数。")
                return run
        existing = next(
            (
                run
                for run in runs
                if run.get("report_date") == report_date
                and run.get("workflow", "core_financial") == workflow
                and run.get("status") in ACTIVE_STATUSES
            ),
            None,
        )
        if existing:
            if (
                existing.get("use_existing_fx_only", False) is not use_existing_fx_only
                or existing.get("expected_fx_source_version") != expected_fx_source_version
                or existing.get("use_existing_curves_only", False) is not use_existing_curves_only
                or existing.get("expected_curve_snapshots") != expected_curve_snapshots
                or existing.get("recovery_of_run_id") != recovery_of_run_id
            ):
                raise ValueError("同一报告日已有不同恢复参数的更新请求。")
            return existing
        require_scheduler(QUEUE_TASK_NAME)
        preflight = input_preflight(settings, report_date, workflow)
        if not preflight["ready"] and not wait_for_inputs:
            raise ValueError("该报告日的文件尚未到齐，可选择“资料齐全后自动更新”。")
        return save_run(
            settings.governance_path,
            {
                "run_id": f"data_update_{uuid4().hex}",
                "report_date": report_date,
                "workflow": workflow,
                "status": "queued" if preflight["ready"] else "waiting_inputs",
                "requested_by": requested_by,
                "idempotency_key": idempotency_key,
                "wait_for_inputs": wait_for_inputs,
                "use_existing_fx_only": use_existing_fx_only,
                "expected_fx_source_version": expected_fx_source_version,
                "use_existing_curves_only": use_existing_curves_only,
                "expected_curve_snapshots": expected_curve_snapshots,
                "recovery_of_run_id": recovery_of_run_id,
                "submitted_at": utc_now(),
                "updated_at": utc_now(),
                "attempt": 0,
                "steps": [],
                "message": "已受理，后台将在五分钟内检查。",
                "preflight": preflight,
            },
        )


def _choice_stock_pit_path(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("历史股票恢复需要明确的本机绝对文件路径。")
    path = Path(value.strip())
    if not path.is_absolute() or str(path).startswith(("\\\\", "//")):
        raise ValueError("历史股票恢复仅接受本机绝对文件路径。")
    resolved = str(path.resolve())
    if resolved.startswith(("\\\\", "//")):
        raise ValueError("历史股票恢复不接受网络文件路径。")
    return resolved


def _choice_stock_pit_sha256(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("历史股票恢复需要有效的 SHA256 摘要。")
    return value


def _choice_stock_pit_same_file(first: str, second: str) -> bool:
    if first == second:
        return True
    try:
        return Path(first).samefile(second)
    except FileNotFoundError:
        # Preserve the existing missing-source/backup validation and message.
        return False


def choice_stock_pit_preflight(
    settings, *, report_date: str, source_duckdb_path: str, expected_source_sha256: str,
) -> dict[str, object]:
    """Preview the existing exact PIT importer; the operational DB remains read-only."""
    from backend.app.tasks.choice_stock_pit_import import import_choice_stock_pit_snapshot

    report_date = normalize_report_date(report_date)
    source_path = _choice_stock_pit_path(source_duckdb_path)
    target_path = str(Path(settings.duckdb_path).resolve())
    if _choice_stock_pit_same_file(source_path, target_path):
        raise ValueError("历史股票来源与目标数据库必须不同。")
    source_sha256 = _choice_stock_pit_sha256(expected_source_sha256)
    try:
        with TemporaryDirectory(prefix="moss-choice-pit-preflight-") as temporary_dir:
            result = import_choice_stock_pit_snapshot(
                target_path,
                source_duckdb_path=source_path,
                as_of_date=report_date,
                expected_source_sha256=source_sha256,
                receipt_path=Path(temporary_dir) / "preflight.json",
                apply_changes=False,
            )
    except (OSError, ValueError, RuntimeError, duckdb.Error) as exc:
        raise RuntimeError("历史股票来源预检未通过，请核对日期、来源摘要及现有目标范围。") from exc
    return {
        "ready": True,
        "workflow": CHOICE_STOCK_PIT_WORKFLOW,
        "report_date": report_date,
        "target_duckdb_path": target_path,
        "source_duckdb_path": source_path,
        **{key: result[key] for key in (
            "plan_sha256", "source_sha256", "source_stock_code_count", "source_lineage",
            "insert_counts", "identical_counts", "audit_insert_count", "audit_identical_count",
            "target_missing_request_items_before", "write_scope", "duckdb_written",
        )},
    }


def request_choice_stock_pit_update(
    settings, *, report_date: str, source_duckdb_path: str, expected_source_sha256: str,
    expected_plan_sha256: str, target_backup_path: str, requested_by: str, idempotency_key: str,
) -> dict[str, object]:
    """Persist an exact reviewed PIT request; execution remains in the queue worker."""
    if not requested_by or not requested_by.strip() or not idempotency_key or not idempotency_key.strip():
        raise ValueError("历史股票恢复需要操作人和请求编号。")
    parameters = {
        "report_date": normalize_report_date(report_date),
        "workflow": CHOICE_STOCK_PIT_WORKFLOW,
        "target_duckdb_path": str(Path(settings.duckdb_path).resolve()),
        "source_duckdb_path": _choice_stock_pit_path(source_duckdb_path),
        "expected_source_sha256": _choice_stock_pit_sha256(expected_source_sha256),
        "expected_plan_sha256": _choice_stock_pit_sha256(expected_plan_sha256),
        "target_backup_path": _choice_stock_pit_path(target_backup_path),
    }
    paths = [parameters["source_duckdb_path"], parameters["target_duckdb_path"], parameters["target_backup_path"]]
    if any(_choice_stock_pit_same_file(first, second) for index, first in enumerate(paths) for second in paths[index + 1:]):
        raise ValueError("历史股票来源、目标与备份必须是不同文件。")
    require_scheduler(QUEUE_TASK_NAME)
    with acquire_lock(QUEUE_LOCK, base_dir=settings.governance_path, timeout_seconds=1):
        runs = latest_runs(settings.governance_path)
        for run in runs:
            if run.get("requested_by") == requested_by and run.get("idempotency_key") == idempotency_key:
                if any(run.get(key) != value for key, value in parameters.items()):
                    raise ValueError("同一请求编号不能用于不同历史股票恢复参数。")
                return run
        existing = next((run for run in runs if (
            run.get("workflow") == CHOICE_STOCK_PIT_WORKFLOW
            and run.get("report_date") == parameters["report_date"]
            and run.get("status") in ACTIVE_STATUSES
        )), None)
        if existing:
            if any(existing.get(key) != value for key, value in parameters.items()):
                raise ValueError("同一报告日已有不同历史股票恢复参数的更新请求。")
            return existing
        if not Path(parameters["target_backup_path"]).is_file():
            raise ValueError("历史股票恢复备份文件不存在。")
        preflight = choice_stock_pit_preflight(
            settings, report_date=parameters["report_date"],
            source_duckdb_path=parameters["source_duckdb_path"],
            expected_source_sha256=parameters["expected_source_sha256"],
        )
        if preflight["plan_sha256"] != parameters["expected_plan_sha256"]:
            raise ValueError("历史股票恢复计划已变化，请重新预检并核对摘要。")
        timestamp = utc_now()
        return save_run(settings.governance_path, {
            **parameters,
            "run_id": f"data_update_{uuid4().hex}",
            "status": "queued",
            "requested_by": requested_by,
            "idempotency_key": idempotency_key,
            "wait_for_inputs": False,
            "submitted_at": timestamp,
            "updated_at": timestamp,
            "attempt": 0,
            "steps": [],
            "message": "历史股票来源恢复已受理，须由受控维护主机执行；执行前将再次核对来源、计划与备份。",
            "preflight": preflight,
        })


def cancel_update(settings, run_id: str, *, cancelled_by: str = "") -> dict[str, object]:
    with acquire_lock(QUEUE_LOCK, base_dir=settings.governance_path, timeout_seconds=1):
        run = next((row for row in latest_runs(settings.governance_path) if row["run_id"] == run_id), None)
        if run is None:
            raise LookupError("未找到该更新请求。")
        if run["status"] not in {"queued", "waiting_inputs", "retrying"}:
            raise ValueError("仅可取消尚未开始执行的更新请求。")
        return save_run(
            settings.governance_path,
            {
                **run,
                "status": "cancelled",
                "updated_at": utc_now(),
                "cancelled_by": cancelled_by,
                "message": "已取消等待，不再自动执行。",
            },
        )


def publication_recovery_eligibility(run: dict[str, object]) -> dict[str, object]:
    """Expose eligibility from persisted evidence; the writer revalidates sources."""
    receipt = run.get("failure_receipt")
    failed_step = receipt.get("failed_step") if isinstance(receipt, dict) else None
    result = {"available": False, "reason": None, "failed_step": failed_step}
    if run.get("status") != "failed" or run.get("workflow") != "core_financial":
        return {**result, "reason": "仅支持已失败的完整财务更新发布恢复。"}
    if run.get("recovery_mode") == "publication_only":
        return {**result, "reason": "请从原始财务请求恢复发布。"}
    if failed_step not in {"publish", "system_read_publish"}:
        return {**result, "reason": "该失败阶段不支持仅恢复发布。"}
    if not isinstance(receipt, dict) or (
        not run.get("global_run_id")
        or receipt.get("run_id") != run.get("global_run_id")
        or receipt.get("report_date") != run.get("report_date")
    ):
        return {**result, "reason": "原始请求缺少一致的报告日期和财务完成回执。"}
    # Keep this bounded list aligned with the existing strict publication contract.
    required = (
        "formal_balance", "bond_analytics", "risk_tensor", "formal_pnl",
        "product_category_pnl", "accounting_asset_movement", "source_preview", "verify",
        "pnl_by_business_page_prepare",
    ) + (("publish",) if failed_step == "system_read_publish" else ())
    steps = receipt.get("steps")
    if not isinstance(steps, list) or len(steps) != len(required) + 1:
        return {**result, "reason": "原始请求缺少完整有序的财务完成回执。"}
    for step, name in zip(steps[:-1], required, strict=True):
        if not isinstance(step, dict) or step.get("name") != name or step.get("status") != "completed":
            return {**result, "reason": "原始请求缺少完整有序的财务完成回执。"}
        value = step.get("result")
        if not isinstance(value, dict) or value.get("status") != "completed" or (
            value.get("report_date") and value.get("report_date") != run.get("report_date")
        ):
            return {**result, "reason": "财务步骤结果不完整或报告日期不一致。"}
    tail = steps[-1]
    if not isinstance(tail, dict) or tail.get("name") != failed_step or tail.get("status") != "failed":
        return {**result, "reason": "发布失败回执与请求不一致。"}
    if failed_step == "system_read_publish":
        pnl = steps[-2]["result"]
        if not pnl.get("generation") or not pnl.get("manifest_sha256"):
            return {**result, "reason": "缺少已完成损益发布的代次和摘要。"}
    else:
        versions = steps[-2]["result"].get("dependency_versions")
        if not isinstance(versions, dict) or not versions:
            return {**result, "reason": "缺少发布前已完成结果的来源版本。"}
    return {**result, "available": True}


def request_publication_recovery(
    settings, run_id: str, *, requested_by: str, idempotency_key: str,
) -> dict[str, object]:
    """Queue only publication, preserving the original immutable business receipt."""
    with acquire_lock(QUEUE_LOCK, base_dir=settings.governance_path, timeout_seconds=1):
        runs = latest_runs(settings.governance_path)
        original = next((run for run in runs if run.get("run_id") == run_id), None)
        if original is None:
            raise LookupError("未找到该更新请求。")
        if original.get("recovery_mode") == "publication_only":
            raise ValueError("请从原始财务请求恢复发布。")
        for run in runs:
            if run.get("idempotency_key") == idempotency_key and run.get("requested_by") == requested_by:
                if run.get("recovery_mode") != "publication_only" or run.get("recovery_of_run_id") != run_id:
                    raise ValueError("同一请求编号不能用于不同更新参数。")
                return run
        eligibility = publication_recovery_eligibility(original)
        if not eligibility["available"]:
            raise ValueError(str(eligibility["reason"]))
        if not bool(getattr(settings, "financial_publication_enabled", False)) or not bool(
            getattr(settings, "system_read_publication_enabled", False)
        ):
            raise ValueError("完整只读发布机制尚未启用，不能恢复发布。")
        # A snapshot is a system-wide cut: even a different report date can replace
        # dependencies. Never accept recovery alongside another active update.
        active = [run for run in runs if run.get("status") in ACTIVE_STATUSES]
        existing = next((run for run in active if run.get("recovery_mode") == "publication_only"
                         and run.get("recovery_of_run_id") == run_id), None)
        if existing is not None:
            return existing
        if active:
            raise ValueError("已有活跃财务更新，请待其结束后恢复发布。")
        require_scheduler(QUEUE_TASK_NAME)
        receipt = original["failure_receipt"]
        return save_run(settings.governance_path, {
            "run_id": f"data_update_{uuid4().hex}", "report_date": original["report_date"],
            "workflow": "core_financial", "status": "queued", "requested_by": requested_by,
            "idempotency_key": idempotency_key, "recovery_mode": "publication_only",
            "recovery_of_run_id": run_id,
            "expected_failure_receipt_sha256": hashlib.sha256(canonical_json_bytes(receipt)).hexdigest(),
            "global_run_id": original["global_run_id"], "wait_for_inputs": False,
            "submitted_at": utc_now(), "updated_at": utc_now(), "attempt": 0, "steps": [],
            "message": "已受理仅恢复发布，后台将重新核验来源与已完成结果。",
        })


def start_market_update() -> dict[str, object]:
    require_scheduler(MARKET_TASK_NAME)
    # Fixed task name; no command, path, or vendor parameter is accepted from HTTP.
    subprocess.run(["schtasks", "/Run", "/TN", MARKET_TASK_NAME], capture_output=True, check=True, timeout=15)
    return {"status": "accepted", "message": "已请求启动市场更新，请在计划任务中查看运行结果。"}


def update_overview(settings) -> dict[str, object]:
    runs = latest_runs(settings.governance_path)
    return {
        "checked_at": utc_now(),
        "input_directory": str(settings.data_input_root),
        "schedule": scheduled_updates(),
        "financial_dates": financial_dates(settings.duckdb_path),
        "runs": [
            {**{key: value for key, value in run.items() if key != "idempotency_key"},
             "publication_recovery": publication_recovery_eligibility(run)}
            for run in runs[:30]
        ],
        "steps": [{"key": key, "label": label} for key, label in STEP_LABELS.items()],
    }
