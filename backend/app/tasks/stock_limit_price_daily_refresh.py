"""Safe single-date refresh CLI for numeric A-share limit prices.

The CLI defaults to a read-only dry run.  Only ``--run-once`` enables the
Tushare call and the task-layer DuckDB write.  Daily writes use the landed
``choice_stock_daily_observation`` stock domain and fail closed before any
delete/insert when the vendor response misses a required stock.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import sys
import uuid
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path

from backend.app.governance.settings import get_settings
from backend.app.network.source_bound_socks_proxy import (
    resolve_vendor_source_ip,
    source_bound_socks_proxy,
)
from backend.app.repositories.tushare_adapter import TUSHARE_TOKEN_ENV
from backend.app.tasks.stock_limit_price_ingest import (
    ingest_stock_limit_prices,
    safe_error_message,
)

TASK_NAME = "stock_limit_price_daily_refresh"
SOURCE_VERSION = "stock_limit_price_daily_refresh_v1"
VENDOR_ENDPOINT = "tushare.pro.stk_limit"
RECEIPT_SCHEMA_VERSION = "stock_limit_price_daily_refresh_receipt_v1"
SUCCESS_STATUSES = frozenset({"completed", "completed_with_warnings", "dry_run"})
DEFAULT_RECEIPT_DIR = Path("data/logs")
_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,119}$")
_DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_SENSITIVE_ASSIGNMENT_RE = re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\b\s*[:=]\s*([^\s,;]+)")


def refresh_stock_limit_prices_for_trade_date(
    *,
    duckdb_path: str | Path,
    trade_date: str | date,
    dry_run: bool = True,
    client: object | None = None,
    run_id: str | None = None,
) -> dict[str, object]:
    """Refresh one date with exact observation-domain coverage enforcement."""
    normalized_date = _normalize_as_of_date(str(trade_date))
    effective_run_id = _normalize_run_id(run_id, trade_date=normalized_date)
    return ingest_stock_limit_prices(
        duckdb_path=duckdb_path,
        start_date=normalized_date,
        end_date=normalized_date,
        client=client,
        dry_run=dry_run,
        run_id=effective_run_id,
        require_observation_coverage=True,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Call Tushare and write through the task layer. Omit for dry-run.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Explicitly select the default read-only mode.",
    )
    parser.add_argument(
        "--as-of-date",
        help="Target trade date in exact YYYY-MM-DD form. Defaults to today.",
    )
    parser.add_argument(
        "--duckdb-path",
        "--db-path",
        dest="duckdb_path",
        help="Override the configured DuckDB path.",
    )
    parser.add_argument(
        "--source-ip",
        help="For --run-once only, bind vendor traffic to this IPv4 address or 'auto'.",
    )
    parser.add_argument(
        "--receipt-dir",
        type=Path,
        default=DEFAULT_RECEIPT_DIR,
        help="Directory for the atomic JSON receipt (default: data/logs).",
    )
    parser.add_argument("--run-id", help="Stable idempotency and receipt identifier.")
    return parser


def _normalize_as_of_date(raw: str | None) -> str:
    text = str(raw or "").strip()
    if not text:
        return date.today().isoformat()
    if not _DATE_RE.fullmatch(text):
        raise ValueError("--as-of-date must be a valid YYYY-MM-DD date")
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise ValueError("--as-of-date must be a valid YYYY-MM-DD date") from exc


def _normalize_run_id(raw: str | None, *, trade_date: str) -> str:
    text = str(raw or "").strip()
    if not text:
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        return f"stock_limit_price_daily:{trade_date}:{timestamp}:{uuid.uuid4().hex[:8]}"
    if not _RUN_ID_RE.fullmatch(text):
        raise ValueError("--run-id must be 1-120 characters using letters, digits, dot, underscore, colon, or hyphen")
    return text


def _bind_source_address(original, source_ip: str):
    def source_bound_create_connection(address, *args, **kwargs):
        if len(args) < 2 and kwargs.get("source_address") is None:
            kwargs["source_address"] = (source_ip, 0)
        return original(address, *args, **kwargs)

    return source_bound_create_connection


@contextmanager
def _vendor_source_network(source_ip: str) -> Iterator[None]:
    """Bind both direct urllib3 sockets and the local SOCKS fallback."""
    import urllib3.util.connection as urllib3_connection

    proxy_keys = ("CHOICE_MACRO_SOCKS5_PROXY_HOST", "CHOICE_MACRO_SOCKS5_PROXY_PORT")
    previous_env = {key: os.environ.get(key) for key in proxy_keys}
    original_socket_create_connection = socket.create_connection
    original_urllib3_create_connection = urllib3_connection.create_connection
    with source_bound_socks_proxy(source_ip=source_ip) as endpoint:
        os.environ[proxy_keys[0]] = endpoint.host
        os.environ[proxy_keys[1]] = str(endpoint.port)
        socket.create_connection = _bind_source_address(
            original_socket_create_connection,
            source_ip,
        )
        urllib3_connection.create_connection = _bind_source_address(
            original_urllib3_create_connection,
            source_ip,
        )
        try:
            yield
        finally:
            socket.create_connection = original_socket_create_connection
            urllib3_connection.create_connection = original_urllib3_create_connection
            for key, value in previous_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


def _configured_tokens(settings: object) -> list[str]:
    return [
        token
        for token in (
            str(os.getenv(TUSHARE_TOKEN_ENV, "") or "").strip(),
            str(getattr(settings, "tushare_token", "") or "").strip(),
        )
        if token
    ]


def _redact_text(value: object, *, tokens: list[str]) -> str:
    text = str(value)
    text = _SENSITIVE_ASSIGNMENT_RE.sub(
        lambda match: f"{match.group(1)}=***",
        text,
    )
    for token in tokens:
        text = text.replace(token, "***")
    return text


def _redact_payload(value: object, *, tokens: list[str]) -> object:
    if isinstance(value, dict):
        return {str(key): _redact_payload(item, tokens=tokens) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_payload(item, tokens=tokens) for item in value]
    if isinstance(value, tuple):
        return [_redact_payload(item, tokens=tokens) for item in value]
    if isinstance(value, str):
        return _redact_text(value, tokens=tokens)
    return value


def _receipt_path(receipt_dir: Path, *, trade_date: str, run_id: str) -> Path:
    digest = hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:10]
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", run_id).strip("._-")[:64] or "run"
    return receipt_dir / (f"stock_limit_price_daily_refresh_{trade_date.replace('-', '')}_{slug}_{digest}.json")


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    try:
        with temp_path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True, default=str)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _build_receipt(
    *,
    invocation_mode: str,
    as_of_date: str,
    run_id: str,
    source_ip: str | None,
    status: str,
    exit_code: int,
    result: dict[str, object],
) -> dict[str, object]:
    return {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "task_name": TASK_NAME,
        "source_version": SOURCE_VERSION,
        "vendor_endpoint": VENDOR_ENDPOINT,
        "invocation_mode": invocation_mode,
        "as_of_date": as_of_date,
        "run_id": run_id,
        "source_ip": source_ip,
        "status": status,
        "exit_code": exit_code,
        "result": result,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.run_once and args.dry_run:
        parser.error("--run-once and --dry-run are mutually exclusive")
    if args.source_ip and not args.run_once:
        parser.error("--source-ip requires --run-once")

    try:
        as_of_date = _normalize_as_of_date(args.as_of_date)
        run_id = _normalize_run_id(args.run_id, trade_date=as_of_date)
        source_ip = resolve_vendor_source_ip(args.source_ip) if args.source_ip else None
    except ValueError as exc:
        parser.error(str(exc))

    settings = get_settings()
    tokens = _configured_tokens(settings)
    duckdb_path = str(args.duckdb_path or settings.duckdb_path)
    dry_run = not bool(args.run_once)
    invocation_mode = "dry_run" if dry_run else "run_once"

    try:
        if source_ip is not None:
            with _vendor_source_network(source_ip):
                result = refresh_stock_limit_prices_for_trade_date(
                    duckdb_path=duckdb_path,
                    trade_date=as_of_date,
                    dry_run=False,
                    run_id=run_id,
                )
        else:
            result = refresh_stock_limit_prices_for_trade_date(
                duckdb_path=duckdb_path,
                trade_date=as_of_date,
                dry_run=dry_run,
                run_id=run_id,
            )
    except Exception as exc:  # noqa: BLE001 - CLI must persist a bounded failure receipt
        result = {
            "status": "failed",
            "trade_date": as_of_date,
            "duckdb_path": duckdb_path,
            "vendor_endpoint": VENDOR_ENDPOINT,
            "error": safe_error_message(exc),
        }

    status = str(result.get("status") or "failed")
    exit_code = 0 if status in SUCCESS_STATUSES else 1
    receipt = _build_receipt(
        invocation_mode=invocation_mode,
        as_of_date=as_of_date,
        run_id=run_id,
        source_ip=source_ip,
        status=status,
        exit_code=exit_code,
        result=result,
    )
    redacted_receipt = _redact_payload(receipt, tokens=tokens)
    assert isinstance(redacted_receipt, dict)
    receipt_path = _receipt_path(
        args.receipt_dir,
        trade_date=as_of_date,
        run_id=run_id,
    )
    try:
        _write_json_atomic(receipt_path, redacted_receipt)
    except Exception as exc:  # noqa: BLE001 - emit a masked operational failure only
        message = _redact_text(safe_error_message(exc), tokens=tokens)
        print(f"receipt write failed: {message}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "result": redacted_receipt["result"],
                "receipt_path": str(receipt_path),
            },
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
