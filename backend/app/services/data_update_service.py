"""Data-center controls. DuckDB is read-only; execution belongs to tasks."""

from __future__ import annotations

import re
import subprocess
import time
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

from backend.app.core_finance.source_rules import describe_source_file
from backend.app.governance.locks import LockDefinition, acquire_lock
from backend.app.repositories.data_update_repo import financial_dates, latest_runs, save_run
from backend.app.repositories.governance_repo import GovernanceRepository
from backend.app.repositories.source_manifest_repo import SourceManifestRepository
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
            Path(str(row["archived_path"])) for row in manifest if row.get("source_family") == family
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
            parsed = _parse_schtasks_csv(_run_schtasks_query(task_name, timeout=remaining))
            matching = [row for row in parsed if row.get("task_name") == task_name]
            if len(parsed) != 1 or len(matching) != 1:
                raise ValueError(f"targeted schtasks query did not return exactly {task_name}")
            tasks[task_name] = matching[0]
    except Exception:
        try:
            tasks = {row["task_name"]: row for row in _parse_schtasks_csv(_run_schtasks_query())}
        except Exception:
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
    task = next((row for row in snapshot["tasks"] if row["task_name"] == task_name), None)
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
) -> dict[str, object]:
    report_date = normalize_report_date(report_date)
    if workflow not in {"balance_daily", "core_financial"}:
        raise ValueError("不支持的更新范围。")
    with acquire_lock(QUEUE_LOCK, base_dir=settings.governance_path, timeout_seconds=1):
        runs = latest_runs(settings.governance_path)
        for run in runs:
            if run.get("idempotency_key") == idempotency_key and run.get("requested_by") == requested_by:
                if (
                    run.get("report_date") != report_date
                    or run.get("wait_for_inputs") != wait_for_inputs
                    or run.get("workflow", "core_financial") != workflow
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
                "submitted_at": utc_now(),
                "updated_at": utc_now(),
                "attempt": 0,
                "steps": [],
                "message": "已受理，后台将在五分钟内检查。",
                "preflight": preflight,
            },
        )


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
        "runs": [{key: value for key, value in run.items() if key != "idempotency_key"} for run in runs[:30]],
        "steps": [{"key": key, "label": label} for key, label in STEP_LABELS.items()],
    }
