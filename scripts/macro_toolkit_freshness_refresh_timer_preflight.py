"""Fail-closed preflight for the macro-toolkit freshness external timer."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHECKLIST = ROOT / "docs/templates/macro_toolkit_freshness_refresh_go_live_checklist.md"
DEFAULT_PACKET = ROOT / "docs/templates/macro_toolkit_freshness_refresh_timer_enablement_packet.md"
DEFAULT_EVIDENCE = ROOT / "docs/handoff/2026-07-20-macro-toolkit-freshness-timer-preflight-status.md"
DEFAULT_RECEIPT = ROOT / "data/logs/macro_toolkit_freshness_refresh_receipt.json"
DEFAULT_TASK_NAME = "MOSS-MacroToolkitFreshness"
RECEIPT_TASK_NAME = "refresh_macro_toolkit_freshness"
EXPECTED_SOURCE_VERSION = "macro_toolkit_freshness_refresh_v3"
RECEIPT_SCHEMA_VERSION = 1
REQUIRED_STEPS = frozenset(
    {
        "choice_policy_rate_7d",
        "commodity_daily_ingest",
        "public_cross_asset_headlines",
        "tushare_ncd_shibor",
    }
)
CORE_LATEST_OBSERVATION_KEYS = frozenset(
    {
        "fact_commodity_futures_daily",
        "CA.CSI300",
        "CA.CSI500",
        "CA.COPPER",
        "NHCI.NH",
        "NCD.SHIBOR.1M",
        "NCD.SHIBOR.3M",
        "NCD.SHIBOR.6M",
        "NCD.SHIBOR.9M",
        "NCD.SHIBOR.1Y",
        "EMM00088132",
    }
)
STAGES = frozenset({"pre-enable", "post-enable", "all"})

_FIELDS = {
    "owner": ("checklist", "Owner:"),
    "rollback": ("checklist", "Rollback:"),
    "timer_host": ("packet", "Timer host:"),
    "write_window": ("packet", "Write window:"),
    "log_path": ("packet", "Log path:"),
}
_UNSAFE_PACKET_MARKERS = (
    "schtasks /create",
    "crontab ",
    "register-scheduledtask",
    "new-scheduledtask",
)


def _value(text: str, label: str) -> str | None:
    for line in text.splitlines():
        if line.strip().lower().startswith(label.lower()):
            value = line.split(":", 1)[1].strip()
            if value and "<" not in value and ">" not in value and value.lower() not in {"tbd", "pending"}:
                return value
    return None


def _safe_error(exc: BaseException) -> str:
    message = " ".join(str(exc).split()) or "no error details"
    return f"{type(exc).__name__}: {message[:300]}"


def _add_missing(missing_fields: list[str], field: str) -> None:
    if field not in missing_fields:
        missing_fields.append(field)


def _positive_row_count(step: dict[str, object]) -> bool:
    result = step.get("result")
    if not isinstance(result, dict) or "row_count" not in result:
        return False
    try:
        return int(result["row_count"]) > 0
    except (TypeError, ValueError):
        return False


def _valid_generated_at(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _validate_receipt(
    receipt_path: Path,
    *,
    missing_fields: list[str],
    warnings: list[str],
) -> str:
    if not receipt_path.is_file():
        _add_missing(missing_fields, "receipt")
        return "missing"
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _add_missing(missing_fields, "receipt")
        warnings.append(f"receipt could not be read: {_safe_error(exc)}")
        return "invalid"
    if not isinstance(receipt, dict):
        _add_missing(missing_fields, "receipt")
        warnings.append("receipt must be a JSON object")
        return "invalid"

    receipt_missing_before = len(missing_fields)
    receipt_warnings_before = len(warnings)
    if receipt.get("schema_version") != RECEIPT_SCHEMA_VERSION:
        _add_missing(missing_fields, "receipt.schema_version")
    if not _valid_generated_at(receipt.get("generated_at")):
        _add_missing(missing_fields, "receipt.generated_at")
    if receipt.get("run_kind") != "scheduled":
        _add_missing(missing_fields, "receipt.run_kind")
    if receipt.get("invocation_mode") != "run_once":
        _add_missing(missing_fields, "receipt.invocation_mode")
    if receipt.get("task_name") != RECEIPT_TASK_NAME:
        _add_missing(missing_fields, "receipt.task_name")
    if receipt.get("source_version") != EXPECTED_SOURCE_VERSION:
        _add_missing(missing_fields, "receipt.source_version")
    status = receipt.get("status")
    if status not in {"success", "degraded"}:
        _add_missing(missing_fields, "receipt.status")
    if receipt.get("exit_code") != 0:
        _add_missing(missing_fields, "receipt.exit_code")

    receipt_warnings = receipt.get("warnings")
    if isinstance(receipt_warnings, list):
        warnings.extend(
            f"receipt: {warning}"
            for warning in receipt_warnings
            if isinstance(warning, str) and warning.strip()
        )

    result = receipt.get("result")
    if not isinstance(result, dict):
        _add_missing(missing_fields, "receipt.result")
    else:
        if result.get("status") != status:
            _add_missing(missing_fields, "receipt.result.status")
        raw_steps = result.get("steps")
        if not isinstance(raw_steps, list):
            _add_missing(missing_fields, "receipt.result.steps")
            steps_by_name: dict[str, dict[str, object]] = {}
        else:
            steps_by_name = {
                str(step.get("step")): step
                for step in raw_steps
                if isinstance(step, dict) and step.get("step")
            }
        for step_name in sorted(REQUIRED_STEPS):
            step = steps_by_name.get(step_name)
            prefix = f"receipt.result.steps.{step_name}"
            if step is None:
                _add_missing(missing_fields, prefix)
                continue
            if step.get("status") != "success":
                _add_missing(missing_fields, f"{prefix}.status")
            elif not _positive_row_count(step):
                _add_missing(missing_fields, f"{prefix}.row_count")

        cffex = steps_by_name.get("cffex_member_rank")
        if cffex is None:
            warnings.append("CFFEX optional step is missing from the receipt")
        elif cffex.get("status") == "success":
            if not _positive_row_count(cffex):
                _add_missing(
                    missing_fields,
                    "receipt.result.steps.cffex_member_rank.row_count",
                )
        elif cffex.get("status") in {"degraded", "skipped"}:
            warnings.append(
                f"CFFEX optional step reported {cffex.get('status')}; required steps remain valid"
            )
        else:
            _add_missing(
                missing_fields,
                "receipt.result.steps.cffex_member_rank.status",
            )

        latest_dates = result.get("latest_observation_dates")
        if not isinstance(latest_dates, dict):
            _add_missing(
                missing_fields,
                "receipt.result.latest_observation_dates",
            )
        else:
            for key in sorted(CORE_LATEST_OBSERVATION_KEYS):
                value = latest_dates.get(key)
                if value is None or not str(value).strip():
                    _add_missing(
                        missing_fields,
                        f"receipt.result.latest_observation_dates.{key}",
                    )

    if len(missing_fields) > receipt_missing_before:
        return "blocked"
    if status == "degraded" and len(warnings) == receipt_warnings_before:
        warnings.append("scheduled run reported degraded status")
    return "ready_with_warning" if len(warnings) > receipt_warnings_before else "ready"


def _probe_windows_scheduler(task_name: str) -> dict[str, object]:
    if sys.platform != "win32":
        return {"probe_error": "Windows Task Scheduler is unavailable on this platform"}
    escaped_task_name = task_name.replace("'", "''")
    command = (
        "$ErrorActionPreference = 'Stop'; "
        f"$task = Get-ScheduledTask -TaskName '{escaped_task_name}' -ErrorAction Stop; "
        "$info = $task | Get-ScheduledTaskInfo -ErrorAction Stop; "
        "[pscustomobject]@{"
        "TaskName = [string]$task.TaskName; "
        "Enabled = [bool]$task.Settings.Enabled; "
        "State = [string]$task.State; "
        "LastRunTime = $info.LastRunTime.ToString('o'); "
        "LastTaskResult = [int64]$info.LastTaskResult"
        "} | ConvertTo-Json -Compress"
    )
    try:
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                command,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"probe_error": _safe_error(exc)}
    if completed.returncode != 0:
        return {
            "probe_error": (
                f"PowerShell scheduler probe exited with code {completed.returncode}"
            )
        }
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return {"probe_error": f"invalid scheduler JSON: {_safe_error(exc)}"}
    if not isinstance(payload, dict):
        return {"probe_error": "scheduler probe returned a non-object JSON value"}
    return payload


def _scheduler_value(
    scheduler: dict[str, object],
    pascal_name: str,
    snake_name: str,
) -> object:
    return scheduler.get(pascal_name, scheduler.get(snake_name))


def _validate_scheduler(
    task_name: str,
    *,
    scheduler_probe: Callable[[str], dict[str, object]],
    missing_fields: list[str],
    warnings: list[str],
) -> str:
    scheduler_missing_before = len(missing_fields)
    try:
        scheduler = scheduler_probe(task_name)
    except Exception as exc:  # noqa: BLE001 - injected/host probe must fail closed
        _add_missing(missing_fields, "scheduler.probe")
        warnings.append(f"scheduler probe failed: {_safe_error(exc)}")
        return "blocked"
    if not isinstance(scheduler, dict):
        _add_missing(missing_fields, "scheduler.probe")
        warnings.append("scheduler probe returned an invalid result")
        return "blocked"
    probe_error = scheduler.get("probe_error")
    if probe_error:
        _add_missing(missing_fields, "scheduler.probe")
        warnings.append(f"scheduler probe failed: {probe_error}")
        return "blocked"

    actual_name = _scheduler_value(scheduler, "TaskName", "task_name")
    if not isinstance(actual_name, str) or actual_name.casefold() != task_name.casefold():
        _add_missing(missing_fields, "scheduler.task_name")

    enabled = _scheduler_value(scheduler, "Enabled", "enabled")
    state = _scheduler_value(scheduler, "State", "state")
    enabled_value = enabled is True or (
        isinstance(enabled, str) and enabled.casefold() == "true"
    )
    if not enabled_value or (
        isinstance(state, str) and state.casefold() == "disabled"
    ):
        _add_missing(missing_fields, "scheduler.enabled")

    last_run_time = _scheduler_value(scheduler, "LastRunTime", "last_run_time")
    try:
        parsed_last_run = (
            last_run_time
            if isinstance(last_run_time, datetime)
            else datetime.fromisoformat(str(last_run_time).replace("Z", "+00:00"))
        )
    except (TypeError, ValueError):
        parsed_last_run = None
    if parsed_last_run is None or parsed_last_run.year <= 1999:
        _add_missing(missing_fields, "scheduler.last_run_time")

    last_task_result = _scheduler_value(
        scheduler,
        "LastTaskResult",
        "last_task_result",
    )
    try:
        result_code = int(last_task_result)
    except (TypeError, ValueError):
        result_code = None
    if result_code != 0:
        _add_missing(missing_fields, "scheduler.last_task_result")

    return "blocked" if len(missing_fields) > scheduler_missing_before else "ready"


def run_preflight(
    *,
    checklist_path: Path,
    packet_path: Path,
    evidence_path: Path,
    stage: str = "pre-enable",
    receipt_path: Path | None = None,
    task_name: str = DEFAULT_TASK_NAME,
    scheduler_probe: Callable[[str], dict[str, object]] | None = None,
) -> dict[str, object]:
    if stage not in STAGES:
        raise ValueError(f"unsupported preflight stage: {stage}")
    paths = {"checklist": checklist_path, "packet": packet_path, "evidence": evidence_path}
    missing_files = [name for name, path in paths.items() if not path.is_file()]
    texts = {name: path.read_text(encoding="utf-8") if path.is_file() else "" for name, path in paths.items()}
    packet_lower = texts["packet"].lower()
    packet_safe = not any(marker in packet_lower for marker in _UNSAFE_PACKET_MARKERS)
    repo_status = "repo-complete" if not missing_files and packet_safe else "repo-incomplete"
    missing_fields = [field for field, (document, label) in _FIELDS.items() if _value(texts[document], label) is None]
    warnings: list[str] = []
    receipt_status = "not_checked"
    scheduler_status = "not_checked"
    if stage in {"post-enable", "all"}:
        resolved_receipt = receipt_path or DEFAULT_RECEIPT
        receipt_status = _validate_receipt(
            resolved_receipt,
            missing_fields=missing_fields,
            warnings=warnings,
        )
        scheduler_status = _validate_scheduler(
            task_name,
            scheduler_probe=scheduler_probe or _probe_windows_scheduler,
            missing_fields=missing_fields,
            warnings=warnings,
        )
    if repo_status != "repo-complete" or missing_fields:
        ops_status = "blocked"
    elif receipt_status == "ready_with_warning" or warnings:
        ops_status = "ready_with_warning"
    else:
        ops_status = "ready"
    return {
        "repo_status": repo_status,
        "ops_status": ops_status,
        "missing_files": missing_files,
        "missing_fields": missing_fields,
        "packet_safe": packet_safe,
        "stage": stage,
        "warnings": warnings,
        "receipt_status": receipt_status,
        "scheduler_status": scheduler_status,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checklist", type=Path, default=DEFAULT_CHECKLIST)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--receipt-path", type=Path, default=DEFAULT_RECEIPT)
    parser.add_argument(
        "--stage",
        choices=tuple(sorted(STAGES)),
        default="pre-enable",
    )
    parser.add_argument("--task-name", default=DEFAULT_TASK_NAME)
    args = parser.parse_args(argv)
    result = run_preflight(
        checklist_path=args.checklist,
        packet_path=args.packet,
        evidence_path=args.evidence,
        stage=args.stage,
        receipt_path=args.receipt_path,
        task_name=args.task_name,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ops_status"] in {"ready", "ready_with_warning"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
