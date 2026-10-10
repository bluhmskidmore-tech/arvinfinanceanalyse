from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Protocol, SupportsFloat, SupportsIndex, cast

import duckdb
from backend.app.core_finance.adjusted_returns import (
    STOCK_ADJUSTMENT_FACTOR_TABLE,
    ensure_stock_adjustment_factor_schema,
    normalize_duckdb_path,
)
from backend.app.governance.locks import acquire_lock, resolve_duckdb_writer_lock
from backend.app.governance.settings import get_settings
from backend.app.repositories.task_write_guard import repository_task_write_scope
from backend.app.repositories.tushare_adapter import (
    TUSHARE_TOKEN_ENV,
    import_tushare_pro,
    resolve_tushare_token_with_settings_fallback,
)
from backend.app.tasks.broker import register_actor_once

TASK_NAME = "stock_adjustment_factor_daily_refresh"
SOURCE_VERSION = "stock_adjustment_factor_daily_refresh_v1"
VENDOR_ENDPOINT = "tushare.pro.adj_factor"
WRITE_SCOPE = "positive_close_observation_codes"
_CANONICAL_STOCK_CODE_RE = re.compile(r"^[0-9]{6}\.(?:SH|SZ|BJ)$")


class _AdjustmentFactorClient(Protocol):
    def adj_factor(self, *, trade_date: str, fields: str) -> object: ...


def refresh_stock_adjustment_factors_for_trade_date(
    *,
    duckdb_path: str | Path,
    trade_date: str | date,
    dry_run: bool = False,
    tushare_client: object | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    resolved_path = normalize_duckdb_path(duckdb_path)
    if not resolved_path.is_file():
        raise RuntimeError(f"DuckDB file not found: {resolved_path}")
    normalized_trade_date = _normalize_trade_date(trade_date, field_name="trade_date")
    started_at = _normalize_now(now)
    vendor_version = f"vv_tushare_adj_factor_{normalized_trade_date.replace('-', '')}"

    with duckdb.connect(str(resolved_path), read_only=True) as preflight_conn:
        required_codes = _load_required_codes(preflight_conn, trade_date=normalized_trade_date)
    if dry_run:
        return {
            "status": "dry_run",
            "trade_date": normalized_trade_date,
            "duckdb_path": str(resolved_path),
            "required_code_count": len(required_codes),
            "required_codes_preview": required_codes[:10],
            "would_call_tushare": bool(required_codes),
            "vendor_valid_row_count": None,
            "scoped_vendor_row_count": None,
            "write_scope": WRITE_SCOPE,
            "vendor_endpoint": VENDOR_ENDPOINT,
            "vendor_version": vendor_version,
            "table": STOCK_ADJUSTMENT_FACTOR_TABLE,
            "source_version": SOURCE_VERSION,
        }
    if not required_codes:
        return {
            "status": "not_ready",
            "trade_date": normalized_trade_date,
            "duckdb_path": str(resolved_path),
            "required_code_count": 0,
            "required_codes_preview": [],
            "requested_cell_count": 0,
            "raw_vendor_row_count": 0,
            "returned_exact_row_count": 0,
            "vendor_valid_row_count": 0,
            "scoped_vendor_row_count": 0,
            "extra_code_count": 0,
            "existing_same_count": 0,
            "inserted_count": 0,
            "required_cells_covered": False,
            "reason": "no_positive_close_observation_rows",
            "write_scope": WRITE_SCOPE,
            "vendor_endpoint": VENDOR_ENDPOINT,
            "vendor_version": vendor_version,
            "table": STOCK_ADJUSTMENT_FACTOR_TABLE,
            "source_version": SOURCE_VERSION,
        }

    client = tushare_client or _DefaultTushareAdjustmentClient()
    raw_records = _records_from_tabular_payload(
        cast(_AdjustmentFactorClient, client).adj_factor(
            trade_date=normalized_trade_date.replace("-", ""),
            fields="ts_code,trade_date,adj_factor",
        )
    )
    vendor_rows = _normalize_vendor_rows(raw_records, trade_date=normalized_trade_date)
    run_id = _build_run_id(normalized_trade_date, now=started_at)

    writer_lock = resolve_duckdb_writer_lock(resolved_path)
    with acquire_lock(writer_lock, base_dir=resolved_path.parent):
        with duckdb.connect(str(resolved_path), read_only=False) as conn:
            ensure_stock_adjustment_factor_schema(conn)
            locked_required_codes = _load_required_codes(conn, trade_date=normalized_trade_date)
            if not locked_required_codes:
                return {
                    "status": "not_ready",
                    "trade_date": normalized_trade_date,
                    "duckdb_path": str(resolved_path),
                    "required_code_count": 0,
                    "required_codes_preview": [],
                    "requested_cell_count": 0,
                    "raw_vendor_row_count": len(raw_records),
                    "returned_exact_row_count": len(vendor_rows),
                    "vendor_valid_row_count": len(vendor_rows),
                    "scoped_vendor_row_count": 0,
                    "extra_code_count": len({str(row["stock_code"]) for row in vendor_rows}),
                    "existing_same_count": 0,
                    "inserted_count": 0,
                    "required_cells_covered": False,
                    "reason": "no_positive_close_observation_rows",
                    "write_scope": WRITE_SCOPE,
                    "vendor_endpoint": VENDOR_ENDPOINT,
                    "vendor_version": vendor_version,
                    "table": STOCK_ADJUSTMENT_FACTOR_TABLE,
                    "source_version": SOURCE_VERSION,
                }
            _assert_required_coverage(
                required_codes=locked_required_codes,
                vendor_rows=vendor_rows,
                trade_date=normalized_trade_date,
            )
            scoped_vendor_rows = _scope_vendor_rows_to_required_codes(
                vendor_rows=vendor_rows,
                required_codes=locked_required_codes,
            )
            source_version = _source_version(scoped_vendor_rows)
            existing_rows = _load_existing_factor_rows(conn, trade_date=normalized_trade_date)
            write_rows, existing_same_count = _plan_writes(
                existing_rows=existing_rows,
                fetched_rows=scoped_vendor_rows,
            )
            if write_rows:
                with repository_task_write_scope(__name__):
                    conn.execute("begin transaction")
                    try:
                        conn.executemany(
                            f"""
                            insert into {STOCK_ADJUSTMENT_FACTOR_TABLE}
                            (stock_code, trade_date, adj_factor, source_version, run_id)
                            values (?, ?, ?, ?, ?)
                            """,
                            [
                                (
                                    row["stock_code"],
                                    row["trade_date"],
                                    row["adj_factor"],
                                    source_version,
                                    run_id,
                                )
                                for row in write_rows
                            ],
                        )
                        conn.execute("commit")
                    except Exception:
                        _rollback_quietly(conn)
                        raise

    locked_required_code_set = set(locked_required_codes)
    completed_at = datetime.now(UTC)
    return {
        "status": "completed",
        "trade_date": normalized_trade_date,
        "duckdb_path": str(resolved_path),
        "required_code_count": len(locked_required_codes),
        "required_codes_preview": locked_required_codes[:10],
        "requested_cell_count": len(locked_required_codes),
        "raw_vendor_row_count": len(raw_records),
        "returned_exact_row_count": len(vendor_rows),
        "vendor_valid_row_count": len(vendor_rows),
        "scoped_vendor_row_count": len(scoped_vendor_rows),
        "extra_code_count": len(
            {str(row["stock_code"]) for row in vendor_rows if str(row["stock_code"]) not in locked_required_code_set}
        ),
        "existing_same_count": existing_same_count,
        "inserted_count": len(write_rows),
        "required_cells_covered": True,
        "write_scope": WRITE_SCOPE,
        "source_version": source_version,
        "vendor_endpoint": VENDOR_ENDPOINT,
        "vendor_version": vendor_version,
        "run_id": run_id,
        "table": STOCK_ADJUSTMENT_FACTOR_TABLE,
        "started_at": started_at.astimezone(UTC).isoformat(),
        "completed_at": completed_at.astimezone(UTC).isoformat(),
    }


class _DefaultTushareAdjustmentClient:
    def __init__(self) -> None:
        token = resolve_tushare_token_with_settings_fallback(get_settings())
        if not token:
            raise RuntimeError(
                f"{TUSHARE_TOKEN_ENV} is not set; add it to config/.env or export it before calling Tushare pro API."
            )
        self._api = import_tushare_pro().pro_api(token)

    def adj_factor(self, **kwargs: object) -> object:
        return self._api.adj_factor(**kwargs)


def safe_error_message(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {' '.join(str(exc).split()) or 'no error details'}"[:300]


def _load_required_codes(conn: duckdb.DuckDBPyConnection, *, trade_date: str) -> list[str]:
    tables = {str(row[0]) for row in conn.execute("show tables").fetchall()}
    if "choice_stock_daily_observation" not in tables:
        raise RuntimeError("choice_stock_daily_observation is required for daily adjustment factor refresh")
    rows = conn.execute(
        """
        select stock_code
        from choice_stock_daily_observation
        where cast(trade_date as varchar) = ?
          and try_cast(close_value as double) > 0
          and isfinite(try_cast(close_value as double))
        order by stock_code
        """,
        [trade_date],
    ).fetchall()
    codes: list[str] = []
    seen: set[str] = set()
    for index, row in enumerate(rows):
        stock_code = _normalize_stock_code(row[0], field_name=f"required[{index}].stock_code")
        if stock_code in seen:
            continue
        seen.add(stock_code)
        codes.append(stock_code)
    return codes


def _assert_required_coverage(
    *,
    required_codes: list[str],
    vendor_rows: list[dict[str, object]],
    trade_date: str,
) -> None:
    required_cells = {(code, trade_date) for code in required_codes}
    returned_cells = {(str(row["stock_code"]), str(row["trade_date"])) for row in vendor_rows}
    missing_cells = sorted(required_cells - returned_cells)
    if missing_cells:
        preview = ", ".join(f"{code}@{trade_date_text}" for code, trade_date_text in missing_cells[:10])
        raise RuntimeError(
            f"missing required cells for {trade_date}: "
            f"{len(missing_cells)}/{len(required_cells)}; preview: {preview}"
        )


def _scope_vendor_rows_to_required_codes(
    *,
    vendor_rows: list[dict[str, object]],
    required_codes: list[str],
) -> list[dict[str, object]]:
    required_code_set = set(required_codes)
    return [row for row in vendor_rows if str(row["stock_code"]) in required_code_set]


def _normalize_vendor_rows(
    raw_records: list[dict[str, object]],
    *,
    trade_date: str,
) -> list[dict[str, object]]:
    rows_by_key: dict[tuple[str, str], dict[str, object]] = {}
    for index, record in enumerate(raw_records):
        stock_code = _normalize_stock_code(record.get("ts_code"), field_name=f"vendor[{index}].ts_code")
        vendor_trade_date = _normalize_trade_date(
            record.get("trade_date"),
            field_name=f"vendor[{index}].trade_date",
        )
        if vendor_trade_date != trade_date:
            raise RuntimeError(
                f"vendor[{index}].trade_date returned {vendor_trade_date}, expected {trade_date}"
            )
        adj_factor = _positive_finite_float(record.get("adj_factor"), field_name=f"vendor[{index}].adj_factor")
        key = (stock_code, vendor_trade_date)
        previous = rows_by_key.get(key)
        if previous is not None:
            if not math.isclose(float(cast(float, previous["adj_factor"])), adj_factor, rel_tol=0.0, abs_tol=1e-12):
                raise RuntimeError(f"conflicting vendor duplicate for {stock_code} on {vendor_trade_date}")
            continue
        rows_by_key[key] = {
            "stock_code": stock_code,
            "trade_date": vendor_trade_date,
            "adj_factor": adj_factor,
        }
    return [rows_by_key[key] for key in sorted(rows_by_key)]


def _load_existing_factor_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    trade_date: str,
) -> dict[tuple[str, str], float]:
    rows = conn.execute(
        f"""
        select stock_code, trade_date, adj_factor
        from {STOCK_ADJUSTMENT_FACTOR_TABLE}
        where cast(trade_date as varchar) = ?
        order by stock_code
        """,
        [trade_date],
    ).fetchall()
    existing: dict[tuple[str, str], float] = {}
    for index, row in enumerate(rows):
        stock_code = _normalize_stock_code(row[0], field_name=f"existing[{index}].stock_code")
        stored_trade_date = _normalize_trade_date(row[1], field_name=f"existing[{index}].trade_date")
        adj_factor = _positive_finite_float(row[2], field_name=f"existing[{index}].adj_factor")
        key = (stock_code, stored_trade_date)
        if key in existing:
            raise RuntimeError(f"existing factor table has duplicate natural keys for {stock_code}@{stored_trade_date}")
        existing[key] = adj_factor
    return existing


def _plan_writes(
    *,
    existing_rows: dict[tuple[str, str], float],
    fetched_rows: list[dict[str, object]],
) -> tuple[list[dict[str, object]], int]:
    write_rows: list[dict[str, object]] = []
    existing_same_count = 0
    for row in fetched_rows:
        cell = (str(row["stock_code"]), str(row["trade_date"]))
        adj_factor = float(cast(float, row["adj_factor"]))
        existing = existing_rows.get(cell)
        if existing is None:
            write_rows.append(row)
            continue
        if not math.isclose(existing, adj_factor, rel_tol=0.0, abs_tol=1e-12):
            raise RuntimeError(
                f"conflicting existing factor for {cell[0]} on {cell[1]}: "
                f"existing={existing} vendor={adj_factor}"
            )
        existing_same_count += 1
    return write_rows, existing_same_count


def _records_from_tabular_payload(payload: object) -> list[dict[str, object]]:
    if payload is None:
        return []
    to_dict = getattr(payload, "to_dict", None)
    if callable(to_dict):
        records = to_dict(orient="records")
        return [dict(record) for record in records if isinstance(record, dict)]
    if isinstance(payload, list):
        return [dict(record) for record in payload if isinstance(record, dict)]
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            return [dict(record) for record in data if isinstance(record, dict)]
    raise RuntimeError("Unsupported adj_factor response; expected DataFrame-like object.")


def _source_version(rows: list[dict[str, object]]) -> str:
    encoded = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode(
        "utf-8"
    )
    return "sv_stock_adjustment_factor_daily_" + hashlib.sha256(encoded).hexdigest()[:12]


def _build_run_id(trade_date: str, *, now: datetime) -> str:
    return (
        "stock_adjustment_factor_daily_refresh:"
        f"{trade_date}:{_normalize_now(now).astimezone(UTC).strftime('%Y%m%dT%H%M%SZ')}:{uuid.uuid4().hex[:8]}"
    )


def _normalize_now(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _normalize_stock_code(value: object, *, field_name: str) -> str:
    text = str(value or "").strip().upper()
    if not _CANONICAL_STOCK_CODE_RE.fullmatch(text):
        raise RuntimeError(f"{field_name} must be a canonical A-share stock code")
    return text


def _normalize_trade_date(value: object, *, field_name: str) -> str:
    text = str(value or "").strip()
    if len(text) == 8 and text.isdigit():
        text = f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    elif len(text) != 10:
        raise RuntimeError(f"{field_name} must be a valid YYYY-MM-DD date")
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise RuntimeError(f"{field_name} must be a valid YYYY-MM-DD date") from exc


def _positive_finite_float(value: object, *, field_name: str) -> float:
    if isinstance(value, bool):
        raise RuntimeError(f"{field_name} must be a positive finite number")
    try:
        number = float(cast(str | bytes | bytearray | SupportsFloat | SupportsIndex, value))
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{field_name} must be a positive finite number") from exc
    if not math.isfinite(number) or number <= 0:
        raise RuntimeError(f"{field_name} must be a positive finite number")
    return number


def _rollback_quietly(conn: duckdb.DuckDBPyConnection) -> None:
    try:
        conn.execute("rollback")
    except duckdb.Error:
        return


def _refresh_stock_adjustment_factors_for_trade_date_task(**kwargs: object) -> dict[str, Any]:
    return refresh_stock_adjustment_factors_for_trade_date(**kwargs)  # type: ignore[arg-type]


refresh_stock_adjustment_factors_for_trade_date_task = register_actor_once(
    "refresh_stock_adjustment_factors_for_trade_date",
    _refresh_stock_adjustment_factors_for_trade_date_task,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Refresh stock_adjustment_factor for one trade date from Tushare adj_factor.",
    )
    parser.add_argument("--duckdb-path", "--db-path", dest="duckdb_path", default="data/moss.duckdb")
    parser.add_argument("--trade-date", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    payload = refresh_stock_adjustment_factors_for_trade_date(
        duckdb_path=args.duckdb_path,
        trade_date=args.trade_date,
        dry_run=bool(args.dry_run),
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
