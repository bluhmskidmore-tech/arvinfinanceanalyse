from __future__ import annotations

import argparse
import json
import os
import re
import socket
import sys
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.governance.settings import get_settings  # noqa: E402
from backend.app.network.source_bound_socks_proxy import (  # noqa: E402
    resolve_vendor_source_ip,
    source_bound_socks_proxy,
)
from backend.app.repositories.tushare_adapter import TUSHARE_TOKEN_ENV  # noqa: E402
from backend.app.tasks.stock_adjustment_factor_daily_refresh import (  # noqa: E402
    TASK_NAME,
    VENDOR_ENDPOINT,
    refresh_stock_adjustment_factors_for_trade_date,
)
from scripts.macro_toolkit_freshness_refresh import (  # noqa: E402
    RECEIPT_SCHEMA_VERSION,
    _resolve_commit_sha,
    _write_receipt_atomic,
)

SOURCE_VERSION = "stock_adjustment_factor_daily_refresh_v1"
SUCCESS_STATUSES = frozenset({"completed", "dry_run", "skipped_non_trading_day"})
_SENSITIVE_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(api[_-]?key|token|secret|password)\b\s*[:=]\s*([^\s,;]+)"
)
_SENSITIVE_WORD_RE = re.compile(r"(?i)\b(token|secret|password|apikey|api_key)\b")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--dry-run", action="store_true", help="Validate prerequisites without vendor writes.")
    modes.add_argument("--run-once", action="store_true", help="Run synchronously in the current process.")
    parser.add_argument(
        "--as-of-date",
        "--trade-date",
        dest="as_of_date",
        help="Target trade date (YYYY-MM-DD). Defaults to today.",
    )
    parser.add_argument("--db-path", "--duckdb-path", dest="duckdb_path", help="Override DuckDB path.")
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
            "For --run-once only: route vendor traffic through a source-bound SOCKS5 proxy and bind "
            "other vendor sockets to this IPv4 source address."
        ),
    )
    return parser


def _resolve_trade_date(raw: str | None) -> tuple[str, bool]:
    text = str(raw or "").strip()
    if text:
        if len(text) != 10:
            raise ValueError("--as-of-date must be a valid YYYY-MM-DD date")
        return date.fromisoformat(text).isoformat(), False
    today = date.today()
    return today.isoformat(), today.weekday() >= 5


def _mask_error(exc: BaseException, *, settings: object | None = None) -> str:
    text = str(exc).strip() or exc.__class__.__name__
    text = _SENSITIVE_ASSIGNMENT_RE.sub(lambda match: f"{match.group(1)}=***", text)
    env_token = str(os.getenv(TUSHARE_TOKEN_ENV, "") or "").strip()
    if env_token:
        text = text.replace(env_token, "***")
    settings_token = str(getattr(settings, "tushare_token", "") or "").strip() if settings is not None else ""
    if settings_token:
        text = text.replace(settings_token, "***")
    text = _SENSITIVE_WORD_RE.sub("***", text)
    return f"{type(exc).__name__}: {text}"[:300]


def _bind_source_address(original, source_ip: str):
    def source_bound_create_connection(address, *args, **kwargs):
        if len(args) < 2 and kwargs.get("source_address") is None:
            kwargs["source_address"] = (source_ip, 0)
        return original(address, *args, **kwargs)

    return source_bound_create_connection


@contextmanager
def _vendor_source_network(source_ip: str) -> Iterator[None]:
    import urllib3.util.connection as urllib3_connection

    keys = (
        "CHOICE_MACRO_SOCKS5_PROXY_HOST",
        "CHOICE_MACRO_SOCKS5_PROXY_PORT",
    )
    previous = {key: os.environ.get(key) for key in keys}
    original_create_connection = socket.create_connection
    original_urllib3_create_connection = urllib3_connection.create_connection
    with source_bound_socks_proxy(source_ip=source_ip) as endpoint:
        os.environ[keys[0]] = endpoint.host
        os.environ[keys[1]] = str(endpoint.port)
        socket.create_connection = _bind_source_address(original_create_connection, source_ip)
        urllib3_connection.create_connection = _bind_source_address(
            original_urllib3_create_connection,
            source_ip,
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


def _receipt(
    *,
    run_kind: str,
    invocation_mode: str,
    status: str,
    exit_code: int | None,
    result: dict[str, object],
    warnings: list[str] | None = None,
) -> dict[str, object]:
    commit_sha, commit_warning = _resolve_commit_sha()
    receipt_warnings = list(warnings or [])
    if commit_warning:
        receipt_warnings.append(commit_warning)
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
        "warnings": receipt_warnings,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.vendor_source_ip and not args.run_once:
        parser.error("--vendor-source-ip requires --run-once")
    if args.vendor_source_ip:
        try:
            args.vendor_source_ip = resolve_vendor_source_ip(args.vendor_source_ip)
        except ValueError as exc:
            parser.error(str(exc))

    settings = get_settings()
    try:
        trade_date, default_weekend = _resolve_trade_date(args.as_of_date)
    except ValueError as exc:
        parser.error(str(exc))
    duckdb_path = str(args.duckdb_path or settings.duckdb_path)
    invocation_mode = "dry_run" if args.dry_run else "run_once"
    warnings: list[str] = []

    if args.run_once and default_weekend and not args.as_of_date:
        result: dict[str, object] = {
            "status": "skipped_non_trading_day",
            "trade_date": trade_date,
            "reason": "trade_date defaulted to a weekend day; pass --as-of-date to force a run",
            "vendor_endpoint": VENDOR_ENDPOINT,
        }
    else:
        if args.run_once and args.run_kind == "scheduled" and args.receipt_path is not None:
            running_receipt = _receipt(
                run_kind=args.run_kind,
                invocation_mode=invocation_mode,
                status="running",
                exit_code=None,
                result={"status": "running", "trade_date": trade_date, "vendor_endpoint": VENDOR_ENDPOINT},
            )
            try:
                _write_receipt_atomic(args.receipt_path, running_receipt)
            except Exception as exc:
                print(f"running receipt write failed: {_mask_error(exc, settings=settings)}", file=sys.stderr)
                return 1
        try:
            if args.dry_run:
                result = refresh_stock_adjustment_factors_for_trade_date(
                    duckdb_path=duckdb_path,
                    trade_date=trade_date,
                    dry_run=True,
                )
            elif args.vendor_source_ip:
                with _vendor_source_network(args.vendor_source_ip):
                    result = refresh_stock_adjustment_factors_for_trade_date(
                        duckdb_path=duckdb_path,
                        trade_date=trade_date,
                    )
            else:
                result = refresh_stock_adjustment_factors_for_trade_date(
                    duckdb_path=duckdb_path,
                    trade_date=trade_date,
                )
        except Exception as exc:  # noqa: BLE001
            result = {
                "status": "failed",
                "trade_date": trade_date,
                "duckdb_path": duckdb_path,
                "error": _mask_error(exc, settings=settings),
                "vendor_endpoint": VENDOR_ENDPOINT,
            }

    exit_code = 0 if str(result.get("status") or "failed") in SUCCESS_STATUSES else 1
    print(json.dumps(result, ensure_ascii=False, default=str))
    if args.receipt_path is not None:
        try:
            _write_receipt_atomic(
                args.receipt_path,
                _receipt(
                    run_kind=args.run_kind,
                    invocation_mode=invocation_mode,
                    status=str(result.get("status") or "failed"),
                    exit_code=exit_code,
                    result=result,
                    warnings=warnings,
                ),
            )
        except Exception as exc:
            print(f"receipt write failed: {_mask_error(exc, settings=settings)}", file=sys.stderr)
            return 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
