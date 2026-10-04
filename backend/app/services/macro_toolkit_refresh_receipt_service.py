"""Read-only validation for the latest scheduled macro-toolkit refresh receipt."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

RECEIPT_SCHEMA_VERSION = 1
RECEIPT_TASK_NAME = "refresh_macro_toolkit_freshness"
EXPECTED_SOURCE_VERSION = "macro_toolkit_freshness_refresh_v4"
RUNNING_RECEIPT_STALE_AFTER_HOURS = 6.0
RUNNING_RECEIPT_STALE_AFTER_HOURS_ENV = "MOSS_MACRO_TOOLKIT_RUNNING_RECEIPT_STALE_HOURS"
REQUIRED_STEPS = frozenset(
    {
        "choice_policy_rate_7d",
        "choice_crisis_aa_5y",
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
        "EMM00166683",
    }
)
DEFAULT_MACRO_TOOLKIT_REFRESH_RECEIPT_PATH = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "logs"
    / "macro_toolkit_freshness_refresh_receipt.json"
)


@dataclass(frozen=True)
class MacroToolkitRefreshReceiptHealth:
    status: str
    ready: bool
    cache_fingerprint: str
    generated_at: str | None
    run_status: str | None
    source_version: str | None
    missing_fields: tuple[str, ...]
    warnings: tuple[str, ...]
    latest_observation_dates: dict[str, str]
    failure_category: str | None = None
    failure_message: str | None = None
    step_statuses: dict[str, dict[str, object]] = field(default_factory=dict)
    running_age_hours: float | None = None

    def as_payload(self) -> dict[str, object]:
        return {
            "status": self.status,
            "ready": self.ready,
            "fingerprint": self.cache_fingerprint,
            "generated_at": self.generated_at,
            "running_age_hours": self.running_age_hours,
            "run_status": self.run_status,
            "source_version": self.source_version,
            "missing_fields": list(self.missing_fields),
            "warnings": list(self.warnings),
            "latest_observation_dates": dict(self.latest_observation_dates),
            "failure_category": self.failure_category,
            "failure_message": self.failure_message,
            "step_statuses": {
                step_name: dict(summary)
                for step_name, summary in self.step_statuses.items()
            },
        }

    def analysis_warnings(self) -> list[str]:
        messages = list(self.warnings)
        if self.ready:
            return messages
        if self.status == "blocked" and self.failure_message:
            category = _failure_category_label(self.failure_category)
            reason = f"最近一次刷新未完成（{category}）"
        elif self.status == "abandoned":
            generated_at = self.generated_at or "未知时间"
            age_hours = self.running_age_hours if self.running_age_hours is not None else 0.0
            reason = f"最近一次定时宏观刷新自 {generated_at} 起未完成（已 {age_hours:.0f} 小时）"
        elif self.status == "missing":
            reason = "未找到最近一次定时宏观刷新回执"
        elif self.status == "invalid":
            reason = "最近一次定时宏观刷新回执无法读取"
        else:
            fields = "、".join(self.missing_fields)
            reason = f"刷新回执未通过完整性校验：{fields}"
        return [f"{reason}，方向性结论已关闭；原始指标仅作未验证证据。", *messages]

    def recovery_action(self) -> str:
        actions = {
            "scheduler_configuration_error": "先修复采集出口地址或调度配置，再重跑数据刷新并核验回执。",
            "external_dependency_pending": "先确认供应商权限及外部依赖就绪，再重跑数据刷新并核验回执。",
            "upstream_unavailable": "确认上游数据服务恢复后，重跑数据刷新并核验回执。",
        }
        return actions.get(
            self.failure_category or "",
            "检查数据刷新任务及失败回执，修复后重跑并确认必要步骤完成。",
        )


def load_macro_toolkit_refresh_receipt_health(
    receipt_path: Path = DEFAULT_MACRO_TOOLKIT_REFRESH_RECEIPT_PATH,
    *,
    now: datetime | None = None,
) -> MacroToolkitRefreshReceiptHealth:
    try:
        raw = receipt_path.read_bytes()
    except FileNotFoundError:
        return _health(status="missing", missing_fields=["receipt"])
    except OSError as exc:
        return _health(
            status="invalid",
            missing_fields=["receipt"],
            warnings=[f"receipt could not be read: {_safe_error(exc)}"],
        )

    content_fingerprint = hashlib.sha256(raw).hexdigest()
    try:
        receipt = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return _health(
            status="invalid",
            content_fingerprint=content_fingerprint,
            missing_fields=["receipt"],
            warnings=[f"receipt could not be read: {_safe_error(exc)}"],
        )
    if not isinstance(receipt, dict):
        return _health(
            status="invalid",
            content_fingerprint=content_fingerprint,
            missing_fields=["receipt"],
            warnings=["receipt must be a JSON object"],
        )

    missing_fields: list[str] = []
    warnings: list[str] = []
    if receipt.get("schema_version") != RECEIPT_SCHEMA_VERSION:
        _add_missing(missing_fields, "receipt.schema_version")
    generated_at = _string_or_none(receipt.get("generated_at"))
    generated_at_value = _parse_generated_at(receipt.get("generated_at"))
    if generated_at_value is None:
        _add_missing(missing_fields, "receipt.generated_at")
    if receipt.get("run_kind") != "scheduled":
        _add_missing(missing_fields, "receipt.run_kind")
    if receipt.get("invocation_mode") != "run_once":
        _add_missing(missing_fields, "receipt.invocation_mode")
    if receipt.get("task_name") != RECEIPT_TASK_NAME:
        _add_missing(missing_fields, "receipt.task_name")
    if receipt.get("source_version") != EXPECTED_SOURCE_VERSION:
        _add_missing(missing_fields, "receipt.source_version")
    run_status = receipt.get("status")
    if run_status not in {"success", "degraded"}:
        _add_missing(missing_fields, "receipt.status")
    if receipt.get("exit_code") != 0:
        _add_missing(missing_fields, "receipt.exit_code")
    running_age_hours: float | None = None
    abandoned_running = False
    if run_status == "running" and generated_at_value is not None:
        current_time = now or datetime.now(UTC)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=UTC)
        else:
            current_time = current_time.astimezone(UTC)
        running_age_hours = (current_time - generated_at_value).total_seconds() / 3600
        if running_age_hours > _running_receipt_stale_after_hours():
            abandoned_running = True
            _add_missing(missing_fields, "receipt.abandoned_running")

    receipt_warnings = receipt.get("warnings")
    if isinstance(receipt_warnings, list):
        warnings.extend(
            f"receipt: {warning}"
            for warning in receipt_warnings
            if isinstance(warning, str) and warning.strip()
        )

    latest_observation_dates: dict[str, str] = {}
    step_statuses: dict[str, dict[str, object]] = {}
    result = receipt.get("result")
    if not isinstance(result, dict):
        _add_missing(missing_fields, "receipt.result")
    else:
        step_statuses = _summarize_step_statuses(result)
        if result.get("status") != run_status:
            _add_missing(missing_fields, "receipt.result.status")
        steps_by_name = _steps_by_name(result, missing_fields)
        _validate_required_steps(steps_by_name, missing_fields)
        _validate_optional_cffex(steps_by_name, missing_fields, warnings)
        latest_observation_dates = _validate_latest_dates(result, missing_fields)

    result_payload = result if isinstance(result, dict) else {}
    failure_category = _first_nonempty_string(
        receipt.get("failure_category"),
        result_payload.get("failure_category"),
    )
    if failure_category is None and run_status == "failed":
        failure_category = "refresh_execution_failure"
    failure_message = _first_nonempty_string(
        _first_nonempty_string(
            receipt.get("failure_message"),
            receipt.get("failure_reason"),
        ),
        _first_nonempty_string(
            result_payload.get("failure_message"),
            result_payload.get("failure_reason"),
        ),
        _first_failed_step_reason(result_payload),
    )
    if failure_message is None and run_status == "failed":
        failure_message = "refresh failed without error details"

    status = "abandoned" if abandoned_running else "blocked" if missing_fields else "ready"
    if not missing_fields and (run_status == "degraded" or warnings):
        if run_status == "degraded" and not warnings:
            warnings.append("scheduled run reported degraded status")
        status = "ready_with_warning"
    return _health(
        status=status,
        content_fingerprint=content_fingerprint,
        generated_at=generated_at,
        running_age_hours=running_age_hours,
        run_status=_string_or_none(run_status),
        source_version=_string_or_none(receipt.get("source_version")),
        missing_fields=missing_fields,
        warnings=warnings,
        latest_observation_dates=latest_observation_dates,
        failure_category=failure_category,
        failure_message=failure_message,
        step_statuses=step_statuses,
    )


def _steps_by_name(
    result: dict[str, object],
    missing_fields: list[str],
) -> dict[str, dict[str, object]]:
    raw_steps = result.get("steps")
    if not isinstance(raw_steps, list):
        _add_missing(missing_fields, "receipt.result.steps")
        return {}
    return {
        str(step.get("step")): step
        for step in raw_steps
        if isinstance(step, dict) and step.get("step")
    }


def _validate_required_steps(
    steps_by_name: dict[str, dict[str, object]],
    missing_fields: list[str],
) -> None:
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


def _validate_optional_cffex(
    steps_by_name: dict[str, dict[str, object]],
    missing_fields: list[str],
    warnings: list[str],
) -> None:
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


def _validate_latest_dates(
    result: dict[str, object],
    missing_fields: list[str],
) -> dict[str, str]:
    latest_dates = result.get("latest_observation_dates")
    if not isinstance(latest_dates, dict):
        _add_missing(missing_fields, "receipt.result.latest_observation_dates")
        return {}
    normalized = {
        str(key): str(value).strip()
        for key, value in latest_dates.items()
        if value is not None and str(value).strip()
    }
    for key in sorted(CORE_LATEST_OBSERVATION_KEYS):
        if key not in normalized:
            _add_missing(
                missing_fields,
                f"receipt.result.latest_observation_dates.{key}",
            )
    return normalized


def _positive_row_count(step: dict[str, object]) -> bool:
    result = step.get("result")
    if not isinstance(result, dict) or "row_count" not in result:
        return False
    try:
        return int(result["row_count"]) > 0
    except (OverflowError, TypeError, ValueError):
        return False


def _summarize_step_statuses(
    result: dict[str, object],
) -> dict[str, dict[str, object]]:
    raw_steps = result.get("steps")
    if not isinstance(raw_steps, list):
        return {}
    summaries: dict[str, dict[str, object]] = {}
    for step in raw_steps:
        if not isinstance(step, dict):
            continue
        step_name = _nonempty_string(step.get("step"))
        if step_name is None:
            continue
        summary: dict[str, object] = {}
        status = step.get("status")
        if _has_summary_value(status):
            summary["status"] = status
        row_count = step.get("row_count")
        step_result = step.get("result")
        if row_count is None and isinstance(step_result, dict):
            row_count = step_result.get("row_count")
        if _has_summary_value(row_count):
            summary["row_count"] = row_count
        if isinstance(step_result, dict):
            # Preserve source-run evidence for read-only, dependency-local checks.
            # This does not alter the global receipt ready/blocked decision.
            for key in ("run_id", "covered_required_series", "failed_sources", "source_failures"):
                if key in step_result:
                    summary[key] = step_result[key]
        attempt_count = step.get("attempt_count")
        if _has_summary_value(attempt_count):
            summary["attempt_count"] = attempt_count
        reason = step.get("reason")
        if _has_summary_value(reason):
            summary["reason"] = reason
        summaries[step_name] = summary
    return summaries


def _first_failed_step_reason(result: dict[str, object]) -> str | None:
    raw_steps = result.get("steps")
    if not isinstance(raw_steps, list):
        return None
    for step in raw_steps:
        if not isinstance(step, dict):
            continue
        status = _nonempty_string(step.get("status"))
        if status is None or status.casefold() not in {"failed", "error"}:
            continue
        reason = _nonempty_string(step.get("reason"))
        if reason is not None:
            return reason
    return None


def _has_summary_value(value: object) -> bool:
    return value is not None and (not isinstance(value, str) or bool(value.strip()))


def _failure_category_label(category: str | None) -> str:
    labels = {
        "scheduler_configuration_error": "调度配置错误",
        "external_dependency_pending": "外部依赖未就绪",
        "upstream_unavailable": "上游暂不可用",
        "refresh_execution_failure": "刷新执行失败",
    }
    if category is None:
        return "未分类失败"
    return labels.get(category, category)


def _parse_generated_at(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _running_receipt_stale_after_hours() -> float:
    configured = os.getenv(RUNNING_RECEIPT_STALE_AFTER_HOURS_ENV)
    if configured is None:
        return RUNNING_RECEIPT_STALE_AFTER_HOURS
    try:
        threshold = float(configured)
    except ValueError:
        return RUNNING_RECEIPT_STALE_AFTER_HOURS
    return threshold if threshold >= 0 else RUNNING_RECEIPT_STALE_AFTER_HOURS


def _health(
    *,
    status: str,
    content_fingerprint: str | None = None,
    generated_at: str | None = None,
    run_status: str | None = None,
    source_version: str | None = None,
    missing_fields: list[str] | None = None,
    warnings: list[str] | None = None,
    latest_observation_dates: dict[str, str] | None = None,
    failure_category: str | None = None,
    failure_message: str | None = None,
    step_statuses: dict[str, dict[str, object]] | None = None,
    running_age_hours: float | None = None,
) -> MacroToolkitRefreshReceiptHealth:
    fingerprint = (
        f"{status}:{content_fingerprint}"
        if content_fingerprint is not None
        else status
    )
    return MacroToolkitRefreshReceiptHealth(
        status=status,
        ready=status in {"ready", "ready_with_warning"},
        cache_fingerprint=fingerprint,
        generated_at=generated_at,
        run_status=run_status,
        source_version=source_version,
        missing_fields=tuple(missing_fields or ()),
        warnings=tuple(warnings or ()),
        latest_observation_dates=dict(latest_observation_dates or {}),
        failure_category=failure_category,
        failure_message=failure_message,
        step_statuses={
            step_name: dict(summary)
            for step_name, summary in (step_statuses or {}).items()
        },
        running_age_hours=running_age_hours,
    )


def _add_missing(missing_fields: list[str], field: str) -> None:
    if field not in missing_fields:
        missing_fields.append(field)


def _safe_error(exc: BaseException) -> str:
    message = " ".join(str(exc).split()) or "no error details"
    return f"{type(exc).__name__}: {message[:300]}"


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _nonempty_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _first_nonempty_string(*values: object) -> str | None:
    for value in values:
        normalized = _nonempty_string(value)
        if normalized is not None:
            return normalized
    return None
