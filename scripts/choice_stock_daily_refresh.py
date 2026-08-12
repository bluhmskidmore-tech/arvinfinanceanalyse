"""Operator CLI for the daily Choice-stock materialization refresh.

Runs the same refresh job body as the worker path (`run_choice_stock_refresh`),
so every run leaves the standard governance `cache_build_run` records that
`GET /ui/macro/toolkit/choice-stock/refresh-status` already exposes, and
optionally writes an atomic JSON receipt following the macro-toolkit
freshness-refresh receipt convention.

A successful refresh also recomputes the Livermore market-gate supplement
(``breadth_5d`` / ``limit_up_quality_ok``) from the newly landed rows, so the
/stock-analysis gate does not lag a day behind the stock data. That step is a
downstream analytical input and degrades to a receipt warning on failure.

It also rolls the ``livermore_position_snapshot`` proxy holding forward to the
newly landed trade date (see ``scripts/sync_livermore_position_snapshot.py``),
so the risk-exit ``position_risk`` input does not lag the market gate. That
step is likewise a downstream analytical input, retries briefly on DuckDB
writer contention, and degrades to a receipt warning on failure.
"""

from __future__ import annotations

import argparse
import functools
import json
import os
import socket
import sys
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Sequence, TypeVar

import duckdb

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.governance.settings import get_settings  # noqa: E402
from backend.app.network.source_bound_socks_proxy import (  # noqa: E402
    source_bound_socks_proxy,
)
from backend.app.services.livermore_gate_supplement_compute_service import (  # noqa: E402
    compute_and_materialize_gate_supplement,
)
from backend.app.services.macro_toolkit_service import (  # noqa: E402
    CHOICE_STOCK_REFRESH_JOB_NAME,
    build_choice_stock_refresh_permission_payload,
    choice_stock_refresh_status,
    default_choice_stock_refresh_as_of_date,
    latest_choice_stock_inflight_refresh,
)
from backend.app.tasks.choice_stock_refresh import run_choice_stock_refresh  # noqa: E402
from scripts.macro_toolkit_freshness_refresh import (  # noqa: E402
    RECEIPT_SCHEMA_VERSION,
    _resolve_commit_sha,
    _safe_error,
    _write_receipt_atomic,
)
from scripts.sync_livermore_position_snapshot import (  # noqa: E402
    sync_livermore_position_snapshot,
)

TASK_NAME = "run_choice_stock_refresh"
SOURCE_VERSION = "choice_stock_daily_refresh_v1"
SUCCESS_STATUSES = frozenset({"success", "dry_run", "skipped_non_trading_day"})
POSITION_SNAPSHOT_ROLLFORWARD_RETRY_ATTEMPTS = 10
POSITION_SNAPSHOT_ROLLFORWARD_RETRY_SLEEP_SECONDS = 15.0
_T = TypeVar("_T")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--dry-run", action="store_true", help="Report the plan without vendor or DuckDB writes.")
    modes.add_argument("--run-once", action="store_true", help="Run the refresh synchronously in this process.")
    parser.add_argument(
        "--as-of-date",
        help="Target trade date (YYYY-MM-DD). Defaults to today; weekends are skipped unless set explicitly.",
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
        help=(
            "For --run-once only: bind Choice traffic to a loopback SOCKS5 proxy and all other "
            "vendor sockets to this IPv4 source address (bypasses a TLS-breaking default route)."
        ),
    )
    parser.add_argument("--factor-max-stock-count", type=int)
    return parser


def _bind_source_address(original, source_ip: str):
    """Wrap a create_connection-style callable so unpinned calls egress from source_ip."""

    @functools.wraps(original)
    def source_bound_create_connection(address, *args, **kwargs):
        # create_connection(address, timeout, source_address, ...); only inject
        # when the caller did not pin a source address itself.
        if len(args) < 2 and kwargs.get("source_address") is None:
            kwargs["source_address"] = (source_ip, 0)
        return original(address, *args, **kwargs)

    return source_bound_create_connection


@contextmanager
def _vendor_source_network(source_ip: str) -> Iterator[None]:
    """Route Choice through a source-bound SOCKS5 proxy and bind direct sockets to the same source IP."""
    import urllib3.util.connection as urllib3_connection

    keys = (
        "CHOICE_MACRO_SOCKS5_PROXY_HOST",
        "CHOICE_MACRO_SOCKS5_PROXY_PORT",
    )
    previous = {key: os.environ.get(key) for key in keys}
    original_create_connection = socket.create_connection
    # urllib3 (requests -> Tushare) ships its own create_connection and never
    # calls socket.create_connection, so both entry points must be bound.
    original_urllib3_create_connection = urllib3_connection.create_connection

    with source_bound_socks_proxy(source_ip=source_ip) as endpoint:
        os.environ[keys[0]] = endpoint.host
        os.environ[keys[1]] = str(endpoint.port)
        socket.create_connection = _bind_source_address(original_create_connection, source_ip)
        urllib3_connection.create_connection = _bind_source_address(
            original_urllib3_create_connection, source_ip
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


def _resolve_as_of_date(raw: str | None) -> tuple[str, bool]:
    """Return (as_of_date, weekend_skip). Explicit dates are never skipped."""
    text = str(raw or "").strip()
    if text:
        date.fromisoformat(text)
        return text, False
    today = date.today()
    return today.isoformat(), today.weekday() >= 5


def _receipt(
    *,
    run_kind: str,
    invocation_mode: str,
    status: str,
    exit_code: int | None,
    result: dict[str, object],
    warnings: list[str],
) -> dict[str, object]:
    commit_sha, commit_warning = _resolve_commit_sha()
    if commit_warning:
        warnings = [*warnings, commit_warning]
    return {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "run_kind": run_kind,
        "invocation_mode": invocation_mode,
        "task_name": TASK_NAME,
        "commit_sha": commit_sha,
        "source_version": SOURCE_VERSION,
        "status": status,
        "exit_code": exit_code,
        "result": result,
        "warnings": warnings,
    }


def _latest_refresh_record(governance_path: str) -> dict[str, object]:
    try:
        return choice_stock_refresh_status(governance_path)
    except Exception as exc:  # noqa: BLE001 - the receipt must survive a status read failure
        return {"status": "unknown", "error": _safe_error(exc)}


def _refresh_gate_supplement(
    *,
    duckdb_path: str,
    as_of_date: str,
) -> tuple[dict[str, object], str | None]:
    """Recompute the Livermore market-gate supplement from the just-landed stock data.

    Returns (result, warning). The gate supplement is a downstream analytical
    input, so a failure here degrades to a receipt warning instead of failing
    the Choice-stock refresh itself.
    """
    try:
        payload = compute_and_materialize_gate_supplement(
            duckdb_path=duckdb_path,
            as_of_date=date.fromisoformat(as_of_date),
        )
    except Exception as exc:  # noqa: BLE001 - the main chain must survive this step
        error = _safe_error(exc)
        return (
            {"status": "failed", "error": error},
            f"gate supplement refresh failed: {error}",
        )
    status = str(payload.get("status") or "unknown")
    if status != "completed":
        return payload, f"gate supplement refresh returned status={status}"
    return payload, None


def _is_duckdb_writer_contention(exc: BaseException) -> bool:
    message = str(exc).lower()
    return isinstance(exc, duckdb.Error) and (
        "already open" in message
        or "database is locked" in message
        or "could not set lock" in message
        or "conflicting lock" in message
        or "lock on file" in message
    )


def _call_with_duckdb_retry(
    fn: Callable[[], _T],
    *,
    label: str,
    attempts: int,
    sleep_seconds: float,
) -> _T:
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - retry only writer contention
            last_exc = exc
            if not _is_duckdb_writer_contention(exc) or attempt >= attempts:
                raise
            print(
                f"{label}: DuckDB writer contention attempt={attempt}/{attempts}; "
                f"retrying in {sleep_seconds:.0f}s: {exc}",
                file=sys.stderr,
            )
            time.sleep(sleep_seconds)
    assert last_exc is not None
    raise last_exc


def _refresh_position_snapshot(
    *,
    duckdb_path: str,
    as_of_date: str,
) -> tuple[dict[str, object], str | None]:
    """Roll the Livermore proxy position snapshot forward to the newly landed trade date.

    Returns (result, warning). This keeps the risk-exit ``position_risk`` input
    from lagging the market gate (see ``scripts/sync_livermore_position_snapshot.py``);
    it is a downstream analytical input, so a failure here degrades to a receipt
    warning instead of failing the Choice-stock refresh itself. Retries briefly
    on DuckDB writer-lock contention since the refresh job may still hold the
    write lock when this step starts.
    """
    try:
        payload = _call_with_duckdb_retry(
            lambda: sync_livermore_position_snapshot(
                duckdb_path=duckdb_path,
                target_as_of=as_of_date,
            ),
            label="position snapshot roll-forward",
            attempts=POSITION_SNAPSHOT_ROLLFORWARD_RETRY_ATTEMPTS,
            sleep_seconds=POSITION_SNAPSHOT_ROLLFORWARD_RETRY_SLEEP_SECONDS,
        )
    except Exception as exc:  # noqa: BLE001 - the main chain must survive this step
        error = _safe_error(exc)
        return (
            {"status": "failed", "error": error},
            f"position snapshot roll-forward failed: {error}",
        )
    status = str(payload.get("status") or "unknown")
    if status not in {"completed", "noop"}:
        return payload, f"position snapshot roll-forward returned status={status}"
    return payload, None


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.vendor_source_ip and not args.run_once:
        parser.error("--vendor-source-ip requires --run-once")

    settings = get_settings()
    duckdb_path = str(settings.duckdb_path)
    governance_path = str(settings.governance_path)
    as_of_date, weekend_skip = _resolve_as_of_date(args.as_of_date)
    invocation_mode = "dry_run" if args.dry_run else "run_once"
    warnings: list[str] = []

    if args.dry_run:
        result: dict[str, object] = {
            "status": "dry_run",
            "as_of_date": as_of_date,
            "weekend_skip": weekend_skip,
            "duckdb_latest_as_of": default_choice_stock_refresh_as_of_date(duckdb_path),
            "latest_refresh": _latest_refresh_record(governance_path),
            "would_run": {
                "refresh_history": True,
                "refresh_factors": True,
                "factor_max_stock_count": args.factor_max_stock_count,
                "theme_overlay_mode": "off",
            },
        }
    elif weekend_skip:
        result = {
            "status": "skipped_non_trading_day",
            "as_of_date": as_of_date,
            "reason": "as_of_date defaulted to a weekend day; pass --as-of-date to force a run",
        }
    else:
        inflight = latest_choice_stock_inflight_refresh(governance_path, as_of_date=as_of_date)
        if inflight is not None:
            result = {
                "status": "conflict",
                "as_of_date": as_of_date,
                "reason": f"Choice stock refresh already in progress for as_of_date={as_of_date}.",
                "inflight_run_id": str(inflight.get("run_id") or ""),
            }
        else:
            if args.run_kind == "scheduled" and args.receipt_path is not None:
                running_receipt = _receipt(
                    run_kind=args.run_kind,
                    invocation_mode=invocation_mode,
                    status="running",
                    exit_code=None,
                    result={"status": "running", "as_of_date": as_of_date},
                    warnings=[],
                )
                try:
                    _write_receipt_atomic(args.receipt_path, running_receipt)
                except Exception as exc:  # noqa: BLE001 - no writes may start without the guard
                    print(f"running receipt write failed: {_safe_error(exc)}", file=sys.stderr)
                    return 1

            run_id = f"{CHOICE_STOCK_REFRESH_JOB_NAME}:{as_of_date}:{uuid.uuid4().hex[:12]}"
            queued_at = datetime.now(UTC).isoformat()
            run_kwargs = {
                "duckdb_path": duckdb_path,
                "catalog_path": str(settings.choice_stock_catalog_file),
                "governance_path": governance_path,
                "archive_root": str(settings.local_archive_path),
                "run_id": run_id,
                "as_of_date": as_of_date,
                "queued_at": queued_at,
                "refresh_history": True,
                "refresh_factors": True,
                "factor_max_stock_count": args.factor_max_stock_count,
                "theme_overlay_mode": "off",
                "permission": build_choice_stock_refresh_permission_payload(),
            }
            try:
                if args.vendor_source_ip:
                    with _vendor_source_network(args.vendor_source_ip):
                        run_choice_stock_refresh(**run_kwargs)
                else:
                    run_choice_stock_refresh(**run_kwargs)
            except Exception as exc:  # noqa: BLE001 - failure must land in the receipt
                result = {
                    "status": "failed",
                    "as_of_date": as_of_date,
                    "run_id": run_id,
                    "error": _safe_error(exc),
                    "refresh": _latest_refresh_record(governance_path),
                }
            else:
                gate_supplement, gate_warning = _refresh_gate_supplement(
                    duckdb_path=duckdb_path,
                    as_of_date=as_of_date,
                )
                if gate_warning:
                    warnings.append(gate_warning)
                position_snapshot, position_warning = _refresh_position_snapshot(
                    duckdb_path=duckdb_path,
                    as_of_date=as_of_date,
                )
                if position_warning:
                    warnings.append(position_warning)
                result = {
                    "status": "success",
                    "as_of_date": as_of_date,
                    "run_id": run_id,
                    "refresh": _latest_refresh_record(governance_path),
                    "gate_supplement": gate_supplement,
                    "position_snapshot_rollforward": position_snapshot,
                }

    status = str(result.get("status") or "failed")
    exit_code = 0 if status in SUCCESS_STATUSES else 1
    print(json.dumps(result, ensure_ascii=False, default=str))
    if args.receipt_path is not None:
        receipt = _receipt(
            run_kind=args.run_kind,
            invocation_mode=invocation_mode,
            status=status,
            exit_code=exit_code,
            result=result,
            warnings=warnings,
        )
        try:
            _write_receipt_atomic(args.receipt_path, receipt)
        except Exception as exc:  # noqa: BLE001 - receipt durability is a hard CLI failure
            print(f"receipt write failed: {_safe_error(exc)}", file=sys.stderr)
            return 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
