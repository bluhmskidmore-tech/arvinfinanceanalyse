from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import duckdb

from backend.app.governance.locks import LockDefinition, acquire_lock
from backend.app.tasks.choice_stock_materialize import (
    choice_stock_history_start_date,
    load_choice_stock_materialization_coverage,
)


AS_OF_TABLES = (
    "choice_stock_materialize_run",
    "choice_stock_request_audit",
    "choice_stock_universe",
    "choice_stock_sector_membership",
    "choice_stock_limit_quality",
    "choice_stock_concept_membership",
    "choice_stock_intraday_movement_event",
)
DAILY_TABLE = "choice_stock_daily_observation"
FACTOR_TABLE = "choice_stock_factor_snapshot"
LOCK = LockDefinition(key="lock:duckdb:choice-stock-asof-copy", ttl_seconds=900)


@dataclass(frozen=True)
class TableCopySpec:
    table: str
    date_column: str
    start_date: str
    end_date: str


def copy_choice_stock_asof_from_duckdb(
    *,
    source_duckdb_path: str | Path,
    target_duckdb_path: str | Path,
    as_of_date: str,
    include_factor_snapshot: bool = False,
    dry_run: bool = False,
    governance_dir: str | Path | None = None,
) -> dict[str, object]:
    source_path = _resolve_existing_path(source_duckdb_path, field_name="source_duckdb_path")
    target_path = _resolve_existing_path(target_duckdb_path, field_name="target_duckdb_path")
    resolved_date = _parse_iso_date(as_of_date).isoformat()
    history_start = choice_stock_history_start_date(resolved_date)

    source_coverage = load_choice_stock_materialization_coverage(
        duckdb_path=str(source_path),
        as_of_date=resolved_date,
    )
    if not source_coverage.full_coverage:
        raise ValueError(
            f"Source Choice stock inputs are not complete for {resolved_date}: "
            f"{source_coverage.message}"
        )

    specs = _copy_specs(
        as_of_date=resolved_date,
        history_start=history_start,
        include_factor_snapshot=include_factor_snapshot,
    )
    target_conn = duckdb.connect(str(target_path), read_only=bool(dry_run))
    try:
        target_conn.execute(f"attach {_sql_string(str(source_path))} as src (read_only)")
        _validate_tables(target_conn, specs)
        source_counts = {
            spec.table: _count_source_rows(target_conn, spec)
            for spec in specs
        }
        target_existing_counts = {
            spec.table: _count_target_rows(target_conn, spec)
            for spec in specs
        }
        deleted_counts: dict[str, int] = {}
        inserted_counts: dict[str, int] = {}
        if not dry_run:
            lock_dir = Path(governance_dir) if governance_dir is not None else target_path.parent
            with acquire_lock(LOCK, base_dir=lock_dir, timeout_seconds=5.0):
                target_conn.execute("begin transaction")
                try:
                    for spec in specs:
                        deleted_counts[spec.table] = _delete_target_rows(target_conn, spec)
                        inserted_counts[spec.table] = _insert_source_rows(target_conn, spec)
                    target_conn.execute("commit")
                except Exception:
                    target_conn.execute("rollback")
                    raise
    finally:
        target_conn.close()

    copied_tables = [spec.table for spec in specs]
    return {
        "status": "dry_run" if dry_run else "completed",
        "source_duckdb_path": str(source_path),
        "target_duckdb_path": str(target_path),
        "as_of_date": resolved_date,
        "history_start_date": history_start,
        "include_factor_snapshot": include_factor_snapshot,
        "tables_used": copied_tables,
        "source_counts": source_counts,
        "target_existing_counts": target_existing_counts,
        "deleted_counts": deleted_counts,
        "inserted_counts": inserted_counts,
    }


def _copy_specs(
    *,
    as_of_date: str,
    history_start: str,
    include_factor_snapshot: bool,
) -> list[TableCopySpec]:
    specs = [TableCopySpec(table, "as_of_date", as_of_date, as_of_date) for table in AS_OF_TABLES]
    specs.append(TableCopySpec(DAILY_TABLE, "trade_date", history_start, as_of_date))
    if include_factor_snapshot:
        specs.append(TableCopySpec(FACTOR_TABLE, "as_of_date", as_of_date, as_of_date))
    return specs


def _resolve_existing_path(path_value: str | Path, *, field_name: str) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        raise FileNotFoundError(f"{field_name} not found: {path}")
    return path


def _parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(str(value or "").strip()[:10])
    except ValueError as exc:
        raise ValueError("as_of_date must be YYYY-MM-DD.") from exc


def _sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _validate_tables(conn: duckdb.DuckDBPyConnection, specs: list[TableCopySpec]) -> None:
    for spec in specs:
        target_columns = _table_columns(conn, "main", spec.table)
        source_columns = _table_columns(conn, "src", spec.table)
        if not target_columns:
            raise RuntimeError(f"target DuckDB is missing table {spec.table}.")
        if not source_columns:
            raise RuntimeError(f"source DuckDB is missing table {spec.table}.")
        if target_columns != source_columns:
            raise RuntimeError(f"Column mismatch for {spec.table}: source and target schemas differ.")


def _table_columns(conn: duckdb.DuckDBPyConnection, schema: str, table: str) -> list[str]:
    qualified = table if schema == "main" else f"{schema}.{table}"
    try:
        rows = conn.execute(f"describe select * from {qualified}").fetchall()
    except duckdb.Error:
        return []
    return [str(row[0]) for row in rows]


def _count_source_rows(conn: duckdb.DuckDBPyConnection, spec: TableCopySpec) -> int:
    return _count_rows(conn, f"src.{spec.table}", spec)


def _count_target_rows(conn: duckdb.DuckDBPyConnection, spec: TableCopySpec) -> int:
    return _count_rows(conn, spec.table, spec)


def _count_rows(conn: duckdb.DuckDBPyConnection, table: str, spec: TableCopySpec) -> int:
    row = conn.execute(
        f"""
        select count(*)::integer
        from {table}
        where cast({spec.date_column} as date) between cast(? as date) and cast(? as date)
        """,
        [spec.start_date, spec.end_date],
    ).fetchone()
    return int(row[0] or 0) if row else 0


def _delete_target_rows(conn: duckdb.DuckDBPyConnection, spec: TableCopySpec) -> int:
    count = _count_target_rows(conn, spec)
    conn.execute(
        f"""
        delete from {spec.table}
        where cast({spec.date_column} as date) between cast(? as date) and cast(? as date)
        """,
        [spec.start_date, spec.end_date],
    )
    return count


def _insert_source_rows(conn: duckdb.DuckDBPyConnection, spec: TableCopySpec) -> int:
    columns = _table_columns(conn, "main", spec.table)
    column_list = ", ".join(columns)
    conn.execute(
        f"""
        insert into {spec.table} ({column_list})
        select {column_list}
        from src.{spec.table}
        where cast({spec.date_column} as date) between cast(? as date) and cast(? as date)
        """,
        [spec.start_date, spec.end_date],
    )
    return _count_target_rows(conn, spec)


def main() -> int:
    parser = argparse.ArgumentParser(description="Copy complete Choice stock inputs for one as-of date between DuckDB files.")
    parser.add_argument("--source-duckdb-path", required=True)
    parser.add_argument("--target-duckdb-path", required=True)
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument("--include-factor-snapshot", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        result = copy_choice_stock_asof_from_duckdb(
            source_duckdb_path=args.source_duckdb_path,
            target_duckdb_path=args.target_duckdb_path,
            as_of_date=args.as_of_date,
            include_factor_snapshot=args.include_factor_snapshot,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
