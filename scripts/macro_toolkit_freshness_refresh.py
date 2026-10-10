"""Operator CLI for macro-toolkit price/commodity freshness refresh."""

from __future__ import annotations

import argparse
import functools
import json
import os
import re
import socket
import subprocess
import sys
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.network.source_bound_socks_proxy import (  # noqa: E402
    source_bound_socks_proxy,
)
from backend.app.tasks.macro_toolkit_freshness_refresh import (  # noqa: E402
    SOURCE_VERSION,
    refresh_macro_toolkit_freshness,
    refresh_macro_toolkit_freshness_actor,
)

RECEIPT_SCHEMA_VERSION = 1
SUCCESS_STATUSES = frozenset({"success", "degraded", "dry_run", "queued"})
FAILURE_CATEGORIES = frozenset(
    {
        "scheduler_configuration_error",
        "external_dependency_pending",
        "upstream_unavailable",
        "refresh_execution_failure",
    }
)

_SENSITIVE_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(api[_-]?key|access[_-]?token|refresh[_-]?token|token|secret|password|passwd|pwd)\b"
    r"(\s*[:=]\s*|\s+)([^\s,;]+)"
)
_AUTH_CREDENTIAL_RE = re.compile(r"(?i)\b(bearer|basic)\s+[^\s,;]+")
_URL_USERINFO_RE = re.compile(r"(?i)(\b[a-z][a-z0-9+.-]*://[^:/\s]+:)[^@\s]+(@)")
_SENSITIVE_ENV_NAME_RE = re.compile(
    r"(?i)(?:^|_)(?:token|secret|password|passwd|api_key|apikey|credential)(?:$|_)"
)

_CHOICE_ACCESS_MARKERS = (
    "insufficient access",
    "insufficient user access",
    "user access",
    "permission",
    "permission denied",
    "access denied",
    "not entitled",
    "entitlement",
    "no permission",
    "unauthorized",
    "forbidden",
    "10001012",
    "权限不足",
    "无权限",
)
_UPSTREAM_UNAVAILABLE_MARKERS = (
    "connection",
    "connecterror",
    "connect timeout",
    "connecttimeout",
    "timed out",
    "timeout",
    "network",
    "proxy fail",
    "remote disconnected",
    "service unavailable",
    "temporary failure",
    "temporarily unavailable",
    "connection reset",
    "http 408",
    "http 429",
    "http 500",
    "http 502",
    "http 503",
    "http 504",
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--dry-run", action="store_true", help="Plan steps without vendor writes.")
    modes.add_argument("--enqueue", action="store_true", help="Enqueue the canonical Dramatiq actor.")
    modes.add_argument("--run-once", action="store_true", help="Run synchronously in the current environment.")
    parser.add_argument(
        "--skip-cffex",
        action="store_true",
        help="Skip CFFEX; still run commodity, headlines, and NCD.",
    )
    parser.add_argument("--receipt-path", type=Path, help="Atomically write a JSON run receipt.")
    parser.add_argument(
        "--run-kind",
        choices=("manual", "shadow", "scheduled"),
        default="manual",
        help="Classify the caller for receipt validation (default: manual).",
    )
    parser.add_argument(
        "--vendor-source-ip",
        "--choice-source-ip",
        dest="vendor_source_ip",
        help=(
            "For --run-once only, bind Tushare/public HTTP and Choice vendor traffic "
            "to this IPv4 address. --choice-source-ip remains as a compatibility alias."
        ),
    )
    return parser


def _safe_error(exc: BaseException) -> str:
    message = " ".join(str(exc).split()) or "no error details"
    message = _AUTH_CREDENTIAL_RE.sub(lambda match: f"{match.group(1)} ***", message)
    message = _SENSITIVE_ASSIGNMENT_RE.sub(
        lambda match: f"{match.group(1)}{match.group(2)}***",
        message,
    )
    message = _URL_USERINFO_RE.sub(r"\1***\2", message)
    for name, value in os.environ.items():
        normalized_value = str(value or "")
        if (
            _SENSITIVE_ENV_NAME_RE.search(name)
            and len(normalized_value) >= 6
        ):
            message = message.replace(normalized_value, "***")
    return f"{type(exc).__name__}: {message[:300]}"


def _failure_text(value: object) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, default=str, sort_keys=True).casefold()
    except (TypeError, ValueError):
        return str(value).casefold()


def _contains_upstream_failure(value: object) -> bool:
    text = _failure_text(value)
    return any(marker in text for marker in _UPSTREAM_UNAVAILABLE_MARKERS)


def _choice_access_is_pending(result: dict[str, object]) -> bool:
    steps = result.get("steps")
    if not isinstance(steps, list):
        return False
    for step in steps:
        if not isinstance(step, dict):
            continue
        if str(step.get("step") or "") != "choice_policy_rate_7d":
            continue
        if str(step.get("status") or "").casefold() != "failed":
            continue
        text = _failure_text(step)
        if any(marker in text for marker in _CHOICE_ACCESS_MARKERS):
            return True
    return False


def _returned_failure_evidence(result: dict[str, object]) -> dict[str, object]:
    evidence = {
        key: result[key]
        for key in ("failure_message", "failure_reason", "error_message", "errors")
        if key in result
    }
    steps = result.get("steps")
    if isinstance(steps, list):
        evidence["failed_steps"] = [
            step
            for step in steps
            if isinstance(step, dict)
            and str(step.get("status") or "").casefold() == "failed"
        ]
    return evidence


def _display_failure(value: object) -> str:
    if isinstance(value, str):
        text = " ".join(value.split())
    else:
        try:
            text = json.dumps(value, ensure_ascii=False, default=str, sort_keys=True)
        except (TypeError, ValueError):
            text = str(value)
        text = " ".join(text.split())
    return text[:500]


def _returned_failure_message(result: dict[str, object]) -> str:
    for key in ("failure_message", "failure_reason", "error_message"):
        message = _display_failure(result.get(key))
        if message and message != "null":
            return message

    steps = result.get("steps")
    if isinstance(steps, list):
        failed_steps = [
            step
            for step in steps
            if isinstance(step, dict)
            and str(step.get("status") or "").casefold() == "failed"
        ]
        for step in failed_steps:
            step_result = step.get("result")
            if not isinstance(step_result, dict):
                continue
            for key in ("errors", "error_message"):
                detail = _display_failure(step_result.get(key))
                if detail and detail not in {"null", "{}", "[]"}:
                    step_name = str(step.get("step") or "refresh")
                    return f"{step_name}: {detail}"[:500]
        for step in failed_steps:
            reason = _display_failure(step.get("reason"))
            if reason and reason != "null":
                return reason

    raw_status = str(result.get("status") or "missing")
    return f"refresh returned non-success status: {raw_status}"


def _classify_returned_failure(result: dict[str, object]) -> str:
    existing = str(result.get("failure_category") or "")
    if existing in FAILURE_CATEGORIES:
        return existing
    if _choice_access_is_pending(result):
        return "external_dependency_pending"
    if _contains_upstream_failure(_returned_failure_evidence(result)):
        return "upstream_unavailable"
    return "refresh_execution_failure"


def _classify_execution_exception(exc: Exception, *, stage: str) -> str:
    if stage == "proxy_setup" and isinstance(exc, (OSError, ValueError)):
        return "scheduler_configuration_error"
    error_text = _safe_error(exc).casefold()
    if "choice" in error_text and any(
        marker in error_text for marker in _CHOICE_ACCESS_MARKERS
    ):
        return "external_dependency_pending"
    if isinstance(exc, (ConnectionError, TimeoutError)) or _contains_upstream_failure(exc):
        return "upstream_unavailable"
    return "refresh_execution_failure"


def _terminal_failure_result(
    *,
    category: str,
    reason: str,
) -> dict[str, object]:
    return {
        "status": "failed",
        "source_version": SOURCE_VERSION,
        "steps": [],
        "latest_observation_dates": {},
        "failure_category": category,
        "failure_message": reason,
        "failure_reason": reason,
    }


def _normalize_failed_result(result: dict[str, object]) -> dict[str, object]:
    normalized = dict(result)
    failure_category = _classify_returned_failure(normalized)
    failure_message = _returned_failure_message(normalized)
    normalized["status"] = "failed"
    normalized["source_version"] = str(
        normalized.get("source_version") or SOURCE_VERSION
    )
    if not isinstance(normalized.get("steps"), list):
        normalized["steps"] = []
    if not isinstance(normalized.get("latest_observation_dates"), dict):
        normalized["latest_observation_dates"] = {}
    normalized["failure_category"] = failure_category
    normalized["failure_message"] = failure_message
    normalized.setdefault("failure_reason", failure_message)
    return normalized


def _resolve_commit_sha() -> tuple[str | None, str | None]:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"commit SHA unavailable: {_safe_error(exc)}"
    commit_sha = completed.stdout.strip()
    if completed.returncode != 0 or not commit_sha:
        return None, f"commit SHA unavailable: git exited with code {completed.returncode}"
    return commit_sha, None


def _write_receipt_atomic(path: Path, receipt: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            json.dump(receipt, handle, ensure_ascii=False, default=str, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary_path.replace(path)
    except Exception:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise


@contextmanager
def _choice_source_proxy_environment(source_ip: str) -> Iterator[None]:
    """Bind all macro vendor traffic to one egress while retaining the legacy helper name."""
    import urllib3.util.connection as urllib3_connection

    keys = (
        "CHOICE_MACRO_SOCKS5_PROXY_HOST",
        "CHOICE_MACRO_SOCKS5_PROXY_PORT",
    )
    previous = {key: os.environ.get(key) for key in keys}
    original_create_connection = socket.create_connection
    original_urllib3_create_connection = urllib3_connection.create_connection

    def bind_source_address(original):
        @functools.wraps(original)
        def source_bound_create_connection(address, *args, **kwargs):
            if len(args) >= 2:
                if args[1] is None:
                    args = (args[0], (source_ip, 0), *args[2:])
            elif kwargs.get("source_address") is None:
                kwargs["source_address"] = (source_ip, 0)
            return original(address, *args, **kwargs)

        return source_bound_create_connection

    with source_bound_socks_proxy(source_ip=source_ip) as endpoint:
        os.environ[keys[0]] = endpoint.host
        os.environ[keys[1]] = str(endpoint.port)
        socket.create_connection = bind_source_address(original_create_connection)
        urllib3_connection.create_connection = bind_source_address(
            original_urllib3_create_connection
        )
        try:
            yield
        finally:
            socket.create_connection = original_create_connection
            urllib3_connection.create_connection = original_urllib3_create_connection
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.vendor_source_ip and not args.run_once:
        parser.error("--vendor-source-ip/--choice-source-ip requires --run-once")
    include_cffex = not args.skip_cffex
    if args.dry_run:
        invocation_mode = "dry_run"
    elif args.enqueue:
        invocation_mode = "enqueue"
    else:
        invocation_mode = "run_once"
    if args.run_once and args.run_kind == "scheduled" and args.receipt_path is not None:
        running_result: dict[str, object] = {
            "status": "running",
            "source_version": SOURCE_VERSION,
            "steps": [],
            "latest_observation_dates": {},
        }
        running_receipt: dict[str, object] = {
            "schema_version": RECEIPT_SCHEMA_VERSION,
            "generated_at": datetime.now(UTC).isoformat(),
            "run_kind": "scheduled",
            "invocation_mode": "run_once",
            "task_name": str(refresh_macro_toolkit_freshness_actor.actor_name),
            "commit_sha": None,
            "source_version": SOURCE_VERSION,
            "status": "running",
            "exit_code": None,
            "result": running_result,
            "warnings": [],
        }
        try:
            _write_receipt_atomic(args.receipt_path, running_receipt)
        except Exception as exc:  # noqa: BLE001 - no writes may start without the guard
            print(f"running receipt write failed: {_safe_error(exc)}", file=sys.stderr)
            return 1
    execution_stage = "refresh_execution"
    try:
        if args.dry_run:
            result = refresh_macro_toolkit_freshness(
                dry_run=True,
                include_cffex=include_cffex,
            )
        elif args.enqueue:
            message = refresh_macro_toolkit_freshness_actor.send(
                include_cffex=include_cffex,
            )
            result = {
                "status": "queued",
                "actor": refresh_macro_toolkit_freshness_actor.actor_name,
                "message_id": message.message_id,
            }
        elif args.vendor_source_ip:
            execution_stage = "proxy_setup"
            with _choice_source_proxy_environment(args.vendor_source_ip):
                execution_stage = "refresh_execution"
                result = refresh_macro_toolkit_freshness_actor.fn(include_cffex=include_cffex)
        else:
            result = refresh_macro_toolkit_freshness_actor.fn(include_cffex=include_cffex)
    except Exception as exc:  # noqa: BLE001 - every execution failure needs a terminal receipt
        result = _terminal_failure_result(
            category=_classify_execution_exception(exc, stage=execution_stage),
            reason=_safe_error(exc),
        )
    if not isinstance(result, dict):
        result = _terminal_failure_result(
            category="refresh_execution_failure",
            reason=f"invalid result type: {type(result).__name__}",
        )
    status = str(result.get("status") or "failed")
    if status not in SUCCESS_STATUSES:
        result = _normalize_failed_result(result)
        status = "failed"
    exit_code = 0 if status in SUCCESS_STATUSES else 1
    print(json.dumps(result, ensure_ascii=False, default=str))
    if args.receipt_path is not None:
        commit_sha, commit_warning = _resolve_commit_sha()
        warnings = [commit_warning] if commit_warning else []
        receipt: dict[str, object] = {
            "schema_version": RECEIPT_SCHEMA_VERSION,
            "generated_at": datetime.now(UTC).isoformat(),
            "run_kind": args.run_kind,
            "invocation_mode": invocation_mode,
            "task_name": str(refresh_macro_toolkit_freshness_actor.actor_name),
            "commit_sha": commit_sha,
            "source_version": str(result.get("source_version") or SOURCE_VERSION),
            "status": status,
            "exit_code": exit_code,
            "result": result,
            "warnings": warnings,
        }
        if status == "failed":
            receipt["failure_category"] = str(result["failure_category"])
            if result.get("failure_message") is not None:
                receipt["failure_message"] = str(result["failure_message"])
            if result.get("failure_reason") is not None:
                receipt["failure_reason"] = str(result["failure_reason"])
        try:
            _write_receipt_atomic(args.receipt_path, receipt)
        except Exception as exc:  # noqa: BLE001 - receipt durability is a hard CLI failure
            print(f"receipt write failed: {_safe_error(exc)}", file=sys.stderr)
            return 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
