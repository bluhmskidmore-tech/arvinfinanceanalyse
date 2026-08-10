"""Operator CLI for macro-toolkit price/commodity freshness refresh."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Sequence

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
        "--choice-source-ip",
        help="For --run-once only, bind Choice vendor traffic to this IPv4 address.",
    )
    return parser


def _safe_error(exc: BaseException) -> str:
    message = " ".join(str(exc).split()) or "no error details"
    return f"{type(exc).__name__}: {message[:300]}"


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
    keys = (
        "CHOICE_MACRO_SOCKS5_PROXY_HOST",
        "CHOICE_MACRO_SOCKS5_PROXY_PORT",
    )
    previous = {key: os.environ.get(key) for key in keys}
    with source_bound_socks_proxy(source_ip=source_ip) as endpoint:
        os.environ[keys[0]] = endpoint.host
        os.environ[keys[1]] = str(endpoint.port)
        try:
            yield
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.choice_source_ip and not args.run_once:
        parser.error("--choice-source-ip requires --run-once")
    include_cffex = not args.skip_cffex
    if args.dry_run:
        invocation_mode = "dry_run"
        result = refresh_macro_toolkit_freshness(dry_run=True, include_cffex=include_cffex)
    elif args.enqueue:
        invocation_mode = "enqueue"
        message = refresh_macro_toolkit_freshness_actor.send(include_cffex=include_cffex)
        result = {
            "status": "queued",
            "actor": refresh_macro_toolkit_freshness_actor.actor_name,
            "message_id": message.message_id,
        }
    else:
        invocation_mode = "run_once"
        if args.choice_source_ip:
            with _choice_source_proxy_environment(args.choice_source_ip):
                result = refresh_macro_toolkit_freshness_actor.fn(include_cffex=include_cffex)
        else:
            result = refresh_macro_toolkit_freshness_actor.fn(include_cffex=include_cffex)
    status = str(result.get("status") or "failed")
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
        try:
            _write_receipt_atomic(args.receipt_path, receipt)
        except Exception as exc:  # noqa: BLE001 - receipt durability is a hard CLI failure
            print(f"receipt write failed: {_safe_error(exc)}", file=sys.stderr)
            return 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
