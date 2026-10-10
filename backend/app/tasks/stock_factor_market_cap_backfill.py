"""Guarded writer for the operator's Tushare market-cap backfill."""

from __future__ import annotations

import stat
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

import duckdb
from backend.app.governance.locks import acquire_lock, resolve_duckdb_writer_lock
from backend.app.repositories.task_write_guard import (
    repository_task_write_scope,
    require_repository_task_write_scope,
)

SOURCE_VERSION = "tushare_daily_basic_market_cap_v1"
RULE_VERSION = "rv_tushare_daily_basic_market_cap_v1"
TABLE = "choice_stock_factor_snapshot"


def market_cap_target_identity(path: str | Path) -> tuple[int, int]:
    metadata = Path(path).stat(follow_symlinks=False)
    if not stat.S_ISREG(metadata.st_mode):
        raise PermissionError("DuckDB backfill target must be a regular file")
    return int(metadata.st_dev), int(metadata.st_ino)


def _ensure_market_cap_columns(conn: duckdb.DuckDBPyConnection) -> None:
    require_repository_task_write_scope("market_cap_backfill_schema")
    existing = {str(row[0]).lower() for row in conn.execute(f"describe {TABLE}").fetchall()}
    for column in ("total_mv", "circ_mv"):
        if column not in existing:
            conn.execute(f"alter table {TABLE} add column {column} double")


def _upsert_market_cap_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    as_of_date: str,
    records: Sequence[Mapping[str, Any]],
) -> dict[str, int]:
    require_repository_task_write_scope("market_cap_backfill_rows")
    _ensure_market_cap_columns(conn)
    updated = 0
    inserted = 0
    vendor_version = f"vv_tushare_daily_basic_{as_of_date.replace('-', '')}"
    for record in records:
        stock_code = str(record.get("ts_code") or "").strip()
        if not stock_code:
            continue
        total_mv = record.get("total_mv")
        circ_mv = record.get("circ_mv")
        total_mv_yuan = float(total_mv) * 10000 if total_mv == total_mv and total_mv is not None else None
        circ_mv_yuan = float(circ_mv) * 10000 if circ_mv == circ_mv and circ_mv is not None else None
        if total_mv_yuan is None and circ_mv_yuan is None:
            continue
        existing = conn.execute(
            f"select 1 from {TABLE} where as_of_date = ? and stock_code = ? limit 1",
            [as_of_date, stock_code],
        ).fetchone()
        if existing is not None:
            conn.execute(
                f"update {TABLE} set total_mv = ?, circ_mv = ? where as_of_date = ? and stock_code = ?",
                [total_mv_yuan, circ_mv_yuan, as_of_date, stock_code],
            )
            updated += 1
        else:
            conn.execute(
                f"""
                insert into {TABLE} (
                  as_of_date, stock_code, pe, pb, ps, roe, gross_margin,
                  three_month_return, twelve_month_return, volatility, dividend_yield,
                  total_mv, circ_mv, industry, source_version, vendor_version, rule_version, run_id
                ) values (?, ?, null, null, null, null, null, null, null, null, null, ?, ?, null, ?, ?, ?, ?)
                """,
                [
                    as_of_date,
                    stock_code,
                    total_mv_yuan,
                    circ_mv_yuan,
                    SOURCE_VERSION,
                    vendor_version,
                    RULE_VERSION,
                    f"tushare_market_cap:{as_of_date}",
                ],
            )
            inserted += 1
    return {"updated": updated, "inserted": inserted}


def backfill_market_cap_rows(
    *,
    duckdb_path: str | Path,
    as_of_date: str,
    records: Sequence[Mapping[str, Any]],
    expected_identity: tuple[int, int],
) -> dict[str, int]:
    """Write only the supplied target file/date, atomically under its writer lock."""
    if not str(duckdb_path).strip():
        raise ValueError("duckdb_path must be explicit")
    target = Path(duckdb_path).absolute()
    if market_cap_target_identity(target) != expected_identity:
        raise PermissionError("DuckDB target identity changed after the preflight read")
    if date.fromisoformat(as_of_date).isoformat() != as_of_date:
        raise ValueError("as_of_date must be YYYY-MM-DD")
    with acquire_lock(resolve_duckdb_writer_lock(target), base_dir=target.parent):
        if market_cap_target_identity(target) != expected_identity:
            raise PermissionError("DuckDB target identity changed while acquiring the writer lock")
        with repository_task_write_scope(__name__):
            conn = duckdb.connect(str(target), read_only=False)
            try:
                if market_cap_target_identity(target) != expected_identity:
                    raise PermissionError("DuckDB target identity changed while opening the writer connection")
                conn.execute("begin transaction")
                try:
                    result = _upsert_market_cap_rows(conn, as_of_date=as_of_date, records=records)
                    conn.execute("commit")
                except Exception:
                    conn.execute("rollback")
                    raise
                return result
            finally:
                conn.close()
