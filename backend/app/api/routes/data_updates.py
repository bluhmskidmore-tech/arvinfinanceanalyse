"""Bounded controls for existing update workflows; never accepts arbitrary scripts."""

from __future__ import annotations

from pathlib import PureWindowsPath
from typing import Annotated, Literal

from backend.app.api.routes.data_health import _ensure_data_health_read_allowed
from backend.app.governance.settings import get_settings
from backend.app.schemas.data_updates import CoreDataUpdateRequest
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
from backend.app.services import data_update_service as service
from fastapi import APIRouter, Depends, Header, HTTPException, Query

router = APIRouter(prefix="/api/data-updates", tags=["data-updates"])
CORE_RESOURCES = (
    "balance_analysis",
    "bond_analytics",
    "formal_pnl",
    "product_category_pnl",
    "accounting_asset_movement",
    "source_preview.source_foundation",
)
BALANCE_RESOURCES = ("balance_analysis", "bond_analytics")
MARKET_PERMISSIONS = (
    ("macro_toolkit.choice_stock", "refresh"),
    ("macro_toolkit.source_backfill", "refresh"),
    ("macro_toolkit.commodity_futures", "refresh"),
    ("macro_toolkit.cffex_member_rank", "refresh"),
    ("macro_vendor.choice_series", "refresh"),
    ("market_data.livermore_gate_supplement", "refresh"),
    ("macro_toolkit.script", "execute"),
    ("choice_news.data", "import"),
)

_PUBLIC_RUN_FIELDS = frozenset(
    {
        "run_id",
        "report_date",
        "workflow",
        "status",
        "submitted_at",
        "updated_at",
        "finished_at",
        "attempt",
        "current_step",
        "global_run_id",
        "retry_after",
    }
)
_PUBLIC_STEP_FIELDS = frozenset({"key", "label", "status", "started_at", "finished_at", "elapsed_seconds"})
_PUBLIC_FAILURE_FIELDS = frozenset({"status", "failed_step", "business_body_status"})
_PUBLIC_STATUS_MESSAGES = {
    "queued": "已受理，等待后台检查。",
    "waiting_inputs": "等待该报告日的源文件到齐。",
    "running": "正在校验源文件并执行更新。",
    "retrying": "更新遇到暂时故障，等待重试。",
    "completed": "更新完成，必需结果表已通过该报告日核验。",
    "failed": "更新未完成，请查看步骤状态并人工复核。",
    "cancelled": "已取消等待，不再自动执行。",
}
_PUBLIC_PREFLIGHT_LABELS = {
    "zqtz": "债券余额文件",
    "tyw": "同业余额文件",
    "pnl": "固收损益文件",
    "fx": "汇率来源",
}


def _public_check_detail(key: str, status: str, *, has_files: bool) -> str:
    if key == "fx":
        return "执行时按既有来源校验报告日汇率。" if status == "ready" else "已配置的汇率文件不存在。"
    if status == "ready":
        return "文件已到齐，执行时校验内容。"
    return "文件正在写入，请等待一分钟。" if has_files else "尚未找到该报告日的文件。"


def _public_preflight(run: dict[str, object], input_directory: str) -> dict[str, object] | None:
    preflight = run.get("preflight")
    if not isinstance(preflight, dict):
        return None
    checks = []
    raw_checks = preflight.get("checks")
    for check in raw_checks if isinstance(raw_checks, list) else []:
        if not isinstance(check, dict) or check.get("key") not in _PUBLIC_PREFLIGHT_LABELS:
            continue
        key = str(check["key"])
        status = "ready" if check.get("status") == "ready" else "waiting"
        raw_files = check.get("files")
        files = (
            [PureWindowsPath(value).name for value in raw_files if isinstance(value, str)]
            if isinstance(raw_files, list)
            else []
        )
        checks.append(
            {
                "key": key,
                "label": _PUBLIC_PREFLIGHT_LABELS[key],
                "status": status,
                "files": files,
                "detail": _public_check_detail(key, status, has_files=bool(files)),
            }
        )
    return {
        "workflow": run.get("workflow", "core_financial"),
        "report_date": run.get("report_date"),
        "ready": preflight.get("ready") is True,
        "input_directory": input_directory,
        "checks": checks,
    }


def _public_run(run: dict[str, object], *, input_directory: str) -> dict[str, object]:
    public = {key: value for key, value in run.items() if key in _PUBLIC_RUN_FIELDS}
    public["message"] = _PUBLIC_STATUS_MESSAGES.get(str(run.get("status")), "更新状态待核验。")
    preflight = _public_preflight(run, input_directory)
    if preflight is not None:
        public["preflight"] = preflight
    steps = run.get("steps")
    public["steps"] = (
        [
            {
                **{key: value for key, value in step.items() if key in _PUBLIC_STEP_FIELDS},
                **({"error_message": "该步骤未完成，请检查后台回执。"} if step.get("status") == "failed" else {}),
            }
            for step in steps
            if isinstance(step, dict)
        ]
        if isinstance(steps, list)
        else []
    )
    failure_receipt = run.get("failure_receipt")
    if isinstance(failure_receipt, dict):
        public["failure_receipt"] = {
            key: value for key, value in failure_receipt.items() if key in _PUBLIC_FAILURE_FIELDS
        }
    return public


def _authorize(auth: AuthContext, *, market: bool = False, workflow: str = "core_financial") -> None:
    resources = BALANCE_RESOURCES if workflow == "balance_daily" else CORE_RESOURCES
    permissions = MARKET_PERMISSIONS if market else tuple((resource, "refresh") for resource in resources)
    try:
        for resource, action in permissions:
            ensure_user_allowed(auth=auth, settings=get_settings(), resource=resource, action=action)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail="当前用户没有该更新链路的操作权限。") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="暂时无法核验更新权限，请稍后重试。") from exc


@router.get("")
def overview(auth: Annotated[AuthContext, Depends(get_auth_context)]) -> dict[str, object]:
    _ensure_data_health_read_allowed(auth)
    settings = get_settings()
    payload = service.update_overview(settings)
    permissions = {}
    for key, market in (("core", False), ("balance", False), ("market", True)):
        try:
            _authorize(auth, market=market, workflow="balance_daily" if key == "balance" else "core_financial")
            permissions[key] = True
        except HTTPException:
            permissions[key] = False
    runs = payload.get("runs")
    if isinstance(runs, list):
        payload["runs"] = [
            _public_run(run, input_directory=str(settings.data_input_root)) for run in runs if isinstance(run, dict)
        ]
    return {**payload, "permissions": permissions}


@router.get("/preflight")
def preflight(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: str = Query(pattern=r"^\d{4}-\d{2}-\d{2}$"),
    workflow: Literal["balance_daily", "core_financial"] = "core_financial",
) -> dict[str, object]:
    _ensure_data_health_read_allowed(auth)
    settings = get_settings()
    try:
        result = service.input_preflight(settings, report_date, workflow)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="报告日期无效。") from exc
    public = _public_preflight(
        {"report_date": report_date, "workflow": workflow, "preflight": result},
        str(settings.data_input_root),
    )
    if public is None:
        raise HTTPException(status_code=503, detail="暂时无法读取文件检查结果。")
    return public


@router.post("/core", status_code=202)
def request_core(
    body: CoreDataUpdateRequest,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)],
) -> dict[str, object]:
    _authorize(auth, workflow=body.workflow)
    settings = get_settings()
    try:
        return _public_run(
            service.request_core_update(
                settings,
                report_date=body.report_date.isoformat(),
                wait_for_inputs=body.wait_for_inputs,
                requested_by=auth.user_id,
                idempotency_key=idempotency_key,
                workflow=body.workflow,
            ),
            input_directory=str(settings.data_input_root),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="请求参数冲突，或该报告日的文件尚未到齐。") from exc
    except (RuntimeError, TimeoutError) as exc:
        raise HTTPException(status_code=503, detail="暂时无法受理更新请求，请检查后台任务状态后重试。") from exc


@router.post("/runs/{run_id}/cancel")
def cancel(run_id: str, auth: Annotated[AuthContext, Depends(get_auth_context)]) -> dict[str, object]:
    _ensure_data_health_read_allowed(auth)
    runs = service.latest_runs(get_settings().governance_path)
    run = next((item for item in runs if item["run_id"] == run_id), None)
    if run is None:
        raise HTTPException(status_code=404, detail="未找到该更新请求。")
    _authorize(auth, workflow=str(run.get("workflow", "core_financial")))
    settings = get_settings()
    try:
        return _public_run(
            service.cancel_update(settings, run_id, cancelled_by=auth.user_id),
            input_directory=str(settings.data_input_root),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="未找到该更新请求。") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="仅可取消尚未开始执行的更新请求。") from exc


@router.post("/market", status_code=202)
def request_market(auth: Annotated[AuthContext, Depends(get_auth_context)]) -> dict[str, object]:
    _authorize(auth, market=True)
    try:
        return service.start_market_update()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="市场更新未能启动，请检查计划任务状态后重试。") from exc
