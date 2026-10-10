"""Execute one reviewed PIT request through the existing scoped importer."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from time import perf_counter

from backend.app.services.data_update_service import CHOICE_STOCK_PIT_WORKFLOW, utc_now
from backend.app.tasks import choice_stock_pit_import as importer

STEP_NAME = "choice_stock_pit_import"


class ChoiceStockPitExecutionFailed(RuntimeError):
    def __init__(self, *, receipt: dict[str, object]) -> None:
        super().__init__("历史股票来源导入未完成，请核对任务回执。")
        self.receipt = receipt


def _request_parameters(settings, run: dict[str, object]) -> dict[str, str]:
    if run.get("workflow") != CHOICE_STOCK_PIT_WORKFLOW:
        raise ValueError("单日股票 PIT 任务不能执行其他工作流。")
    run_id = run.get("run_id")
    if not isinstance(run_id, str) or not re.fullmatch(r"data_update_[0-9a-f]{32}", run_id):
        raise ValueError("历史股票请求编号无效。")
    report_date = run.get("report_date")
    if not isinstance(report_date, str) or datetime.strptime(report_date, "%Y-%m-%d").date().isoformat() != report_date:
        raise ValueError("历史股票请求必须指定一个完整报告日。")
    parameters = {"run_id": run_id, "report_date": report_date}
    for key in ("source_duckdb_path", "target_duckdb_path", "target_backup_path"):
        value = run.get(key)
        if not isinstance(value, str) or not Path(value).is_absolute():
            raise ValueError("历史股票请求必须使用本机绝对路径。")
        parameters[key] = str(Path(value).resolve())
    if parameters["target_duckdb_path"] != str(Path(settings.duckdb_path).resolve()):
        raise ValueError("历史股票请求的目标数据库与当前配置不一致。")
    if len({parameters[key] for key in ("source_duckdb_path", "target_duckdb_path", "target_backup_path")}) != 3:
        raise ValueError("历史股票来源、目标和备份必须是不同文件。")
    for key in ("expected_source_sha256", "expected_plan_sha256"):
        value = run.get(key)
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
            raise ValueError("历史股票请求缺少有效的来源或计划摘要。")
        parameters[key] = value
    if (
        run.get("recovery_mode") is not None
        or run.get("use_existing_fx_only", False) is not False
        or run.get("use_existing_curves_only", False) is not False
        or any(run.get(key) is not None for key in (
            "expected_fx_source_version", "expected_curve_snapshots", "recovery_of_run_id",
        ))
    ):
        raise ValueError("股票 PIT 请求不能携带财务或发布恢复参数。")
    return parameters


def task_receipt_path(settings, run: dict[str, object]) -> Path:
    parameters = _request_parameters(settings, run)
    attempt = run.get("attempt")
    if type(attempt) is not int or attempt < 1:
        raise ValueError("历史股票任务缺少有效的执行次数。")
    return (
        Path(settings.governance_path).resolve() / "data_update_tasks"
        / CHOICE_STOCK_PIT_WORKFLOW / parameters["run_id"] / f"attempt_{attempt}.json"
    )


def _completed_result(
    parameters: dict[str, str], run: dict[str, object], result: dict[str, object],
) -> None:
    expected = {
        "schema": importer.IMPORT_SCHEMA, "status": "completed",
        "as_of_date": parameters["report_date"],
        "duckdb_path": parameters["target_duckdb_path"],
        "source_duckdb_path": parameters["source_duckdb_path"],
        "source_sha256": parameters["expected_source_sha256"],
        "plan_sha256": parameters["expected_plan_sha256"],
        "backup_path": parameters["target_backup_path"],
    }
    if any(result.get(key) != value for key, value in expected.items()):
        raise ValueError("历史股票任务完成回执与请求不一致。")
    started_at = run.get("started_at")
    if not isinstance(started_at, str) or not isinstance(result.get("started_at"), str):
        raise ValueError("历史股票任务完成回执缺少执行时间。")
    if datetime.fromisoformat(str(result["started_at"])) < datetime.fromisoformat(started_at):
        raise ValueError("历史股票任务回执早于本次执行。")
    validation = result.get("post_write_validation")
    if not isinstance(validation, dict) or validation.get("coverage_full") is not True:
        raise ValueError("历史股票任务完成回执缺少范围核验。")
    scope = result.get("write_scope")
    if not isinstance(scope, dict) or (
        scope.get("tables") != [spec.table for spec in importer.PIT_SPECS]
        or scope.get("field_keys") != [spec.field_key for spec in importer.PIT_SPECS]
        or scope.get("choice_stock_daily_observation") != "no_write"
        or scope.get("choice_stock_materialize_run") != "no_write"
    ):
        raise ValueError("历史股票任务完成回执的写入范围不一致。")
    if result.get("backup_sha256") != result.get("target_sha256_before") or not re.fullmatch(
        r"[0-9a-f]{64}", str(result.get("backup_sha256") or ""),
    ):
        raise ValueError("历史股票任务回执缺少同字节备份证据。")


def _read_task_receipt(path: Path) -> tuple[dict[str, object], str]:
    payload = path.read_bytes()
    result = json.loads(payload)
    if not isinstance(result, dict):
        raise ValueError("历史股票任务回执格式无效。")
    return result, hashlib.sha256(payload).hexdigest()


def recover_choice_stock_pit_result(settings, run: dict[str, object]) -> dict[str, object]:
    """Recover only a completed receipt belonging to this request and attempt."""
    parameters = _request_parameters(settings, run)
    path = task_receipt_path(settings, run)
    if run.get("task_receipt_path") != str(path):
        raise ValueError("历史股票请求未保存本次任务回执路径。")
    result, digest = _read_task_receipt(path)
    _completed_result(parameters, run, result)
    return {
        **result, "data_update_run_id": parameters["run_id"], "attempt": run["attempt"],
        "task_receipt_path": str(path), "task_receipt_sha256": digest,
    }


def execute_choice_stock_pit_history(settings, run: dict[str, object], on_progress) -> dict[str, object]:
    parameters = _request_parameters(settings, run)
    path = task_receipt_path(settings, run)
    if run.get("task_receipt_path") != str(path):
        raise ValueError("历史股票请求未保存本次任务回执路径。")
    if path.exists():
        raise ValueError("本次股票 PIT 任务回执已存在，不能覆盖重跑。")
    started_at = utc_now()
    started = perf_counter()
    step: dict[str, object] = {
        "name": STEP_NAME, "status": "running", "started_at": started_at,
        "result": {"task_receipt_path": str(path), "data_update_run_id": parameters["run_id"],
                   "attempt": run["attempt"]},
    }
    on_progress({"steps": [step], "current_step": STEP_NAME})
    try:
        result = importer.import_choice_stock_pit_snapshot(
            parameters["target_duckdb_path"],
            source_duckdb_path=parameters["source_duckdb_path"],
            as_of_date=parameters["report_date"],
            expected_source_sha256=parameters["expected_source_sha256"],
            receipt_path=path, apply_changes=True,
            expected_plan_sha256=parameters["expected_plan_sha256"],
            target_backup_path=parameters["target_backup_path"],
        )
        _completed_result(parameters, run, result)
        durable_result, digest = _read_task_receipt(path)
        if durable_result != result:
            raise ValueError("历史股票任务持久回执与返回结果不一致。")
        correlated = {
            **result, "data_update_run_id": parameters["run_id"], "attempt": run["attempt"],
            "task_receipt_path": str(path), "task_receipt_sha256": digest,
        }
        step.update(status="completed", finished_at=utc_now(),
                    elapsed_seconds=round(perf_counter() - started, 3), result=correlated)
        on_progress({"steps": [step], "current_step": None})
        return correlated
    except Exception as exc:  # noqa: BLE001 - Persist exact task evidence without automatically replaying a possibly committed import.
        evidence: dict[str, object] = {
            "task_receipt_path": str(path), "data_update_run_id": parameters["run_id"],
            "attempt": run["attempt"], "commit_state": "unverified", "error_type": type(exc).__name__,
        }
        try:
            task_result, digest = _read_task_receipt(path)
            evidence["task_receipt_sha256"] = digest
            evidence["task_status"] = task_result.get("status")
            # A failed importer receipt lacks request hashes; retain it for
            # reconciliation, never treat its no_changes flag as retry authority.
        except (OSError, ValueError):
            pass
        step.update(status="failed", finished_at=utc_now(),
                    elapsed_seconds=round(perf_counter() - started, 3), result=evidence,
                    error_message=f"历史股票导入失败（异常类型：{type(exc).__name__}）。")
        receipt = {"status": "failed", "failed_step": STEP_NAME,
                   "steps": [step], **evidence}
        on_progress({"steps": [step], "current_step": None})
        raise ChoiceStockPitExecutionFailed(receipt=receipt) from exc
