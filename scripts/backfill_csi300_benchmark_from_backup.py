from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import duckdb

from backend.app.governance.locks import LockDefinition, acquire_lock


FACT_TABLE = "fact_choice_macro_daily"
FACT_COLUMNS = (
    "series_id",
    "series_name",
    "trade_date",
    "value_numeric",
    "frequency",
    "unit",
    "source_version",
    "vendor_version",
    "rule_version",
    "quality_flag",
    "run_id",
)
DEFAULT_SERIES_IDS = ("CA.CSI300",)
LOCK = LockDefinition(key="lock:duckdb:csi300-benchmark-backfill", ttl_seconds=900)
VALUE_TOLERANCE = 1e-9


@dataclass(frozen=True)
class MacroDailyRow:
    series_id: str
    series_name: str
    trade_date: str
    value_numeric: float
    frequency: str
    unit: str
    source_version: str
    vendor_version: str
    rule_version: str
    quality_flag: str
    run_id: str

    @property
    def key(self) -> tuple[str, str]:
        return (self.series_id, self.trade_date)

    def as_insert_tuple(self) -> tuple[object, ...]:
        return (
            self.series_id,
            self.series_name,
            self.trade_date,
            self.value_numeric,
            self.frequency,
            self.unit,
            self.source_version,
            self.vendor_version,
            self.rule_version,
            self.quality_flag,
            self.run_id,
        )


def backfill_csi300_benchmark_from_backup(
    *,
    duckdb_path: str | Path,
    backup_duckdb_path: str | Path,
    start_date: str,
    end_date: str,
    series_ids: Iterable[str] | None = None,
    dry_run: bool = False,
    governance_dir: str | Path | None = None,
) -> dict[str, object]:
    resolved_duckdb_path = _resolve_existing_path(duckdb_path, field_name="duckdb_path")
    resolved_backup_path = _resolve_existing_path(backup_duckdb_path, field_name="backup_duckdb_path")
    parsed_start = _parse_iso_date(start_date, field_name="start_date")
    parsed_end = _parse_iso_date(end_date, field_name="end_date")
    if parsed_end < parsed_start:
        raise ValueError("end_date must be on or after start_date.")
    normalized_series_ids = _normalize_series_ids(series_ids or DEFAULT_SERIES_IDS)

    source_conn = duckdb.connect(str(resolved_backup_path), read_only=True)
    try:
        _require_fact_table(source_conn, source="backup")
        source_rows = _load_rows(
            source_conn,
            series_ids=normalized_series_ids,
            start_date=parsed_start.isoformat(),
            end_date=parsed_end.isoformat(),
            source="backup",
        )
    finally:
        source_conn.close()

    target_conn = duckdb.connect(str(resolved_duckdb_path), read_only=bool(dry_run))
    try:
        _require_fact_table(target_conn, source="target")
        target_rows = _load_rows(
            target_conn,
            series_ids=normalized_series_ids,
            start_date=parsed_start.isoformat(),
            end_date=parsed_end.isoformat(),
            source="target",
        )
        conflicts = _find_conflicts(source_rows, target_rows)
        if conflicts:
            sample = ", ".join(f"{series_id}@{trade_date}" for series_id, trade_date in conflicts[:5])
            raise ValueError(f"Refusing backfill: found conflicting existing rows ({sample}).")

        missing_rows = [row for key, row in source_rows.items() if key not in target_rows]
        inserted_rows: list[MacroDailyRow] = []
        if not dry_run and missing_rows:
            lock_dir = Path(governance_dir) if governance_dir is not None else resolved_duckdb_path.parent
            with acquire_lock(LOCK, base_dir=lock_dir, timeout_seconds=5.0):
                _insert_rows(target_conn, missing_rows)
                inserted_rows = missing_rows
    finally:
        target_conn.close()

    report_rows = [] if dry_run else inserted_rows
    return {
        "status": "dry_run" if dry_run else "completed",
        "duckdb_path": str(resolved_duckdb_path),
        "backup_duckdb_path": str(resolved_backup_path),
        "start_date": parsed_start.isoformat(),
        "end_date": parsed_end.isoformat(),
        "series_ids": list(normalized_series_ids),
        "tables_used": [FACT_TABLE],
        "source_rows": len(source_rows),
        "target_existing_rows": len(target_rows),
        "conflict_count": 0,
        "would_insert_count": len(missing_rows),
        "inserted_count": len(report_rows),
        "inserted_by_series": dict(Counter(row.series_id for row in report_rows)),
        "inserted_min_date": _min_trade_date(report_rows),
        "inserted_max_date": _max_trade_date(report_rows),
    }


def _resolve_existing_path(path_value: str | Path, *, field_name: str) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        raise FileNotFoundError(f"{field_name} not found: {path}")
    return path


def _parse_iso_date(value: str, *, field_name: str) -> date:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} is required.")
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be YYYY-MM-DD.") from exc


def _normalize_series_ids(values: Iterable[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        normalized.append(text)
        seen.add(text)
    if not normalized:
        raise ValueError("At least one series_id is required.")
    return tuple(normalized)


def _require_fact_table(conn: duckdb.DuckDBPyConnection, *, source: str) -> None:
    row = conn.execute(
        """
        select 1
        from information_schema.tables
        where table_name = ?
        limit 1
        """,
        [FACT_TABLE],
    ).fetchone()
    if row is None:
        raise RuntimeError(f"{source} DuckDB is missing table {FACT_TABLE}.")

    existing_columns = {
        column_name
        for (column_name,) in conn.execute(
            """
            select column_name
            from information_schema.columns
            where table_name = ?
            """,
            [FACT_TABLE],
        ).fetchall()
    }
    missing = [column for column in FACT_COLUMNS if column not in existing_columns]
    if missing:
        raise RuntimeError(f"{source} DuckDB table {FACT_TABLE} is missing columns: {', '.join(missing)}")


def _load_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    series_ids: tuple[str, ...],
    start_date: str,
    end_date: str,
    source: str,
) -> dict[tuple[str, str], MacroDailyRow]:
    placeholders = ", ".join("?" for _ in series_ids)
    query = f"""
        select {", ".join(FACT_COLUMNS)}
        from {FACT_TABLE}
        where series_id in ({placeholders})
          and trade_date between ? and ?
          and value_numeric is not null
        order by series_id, trade_date
    """
    rows = conn.execute(query, [*series_ids, start_date, end_date]).fetchall()
    keyed: dict[tuple[str, str], MacroDailyRow] = {}
    duplicates: list[tuple[str, str]] = []
    for raw in rows:
        row = MacroDailyRow(*raw)
        if row.key in keyed:
            duplicates.append(row.key)
        keyed[row.key] = row
    if duplicates:
        sample = ", ".join(f"{series_id}@{trade_date}" for series_id, trade_date in duplicates[:5])
        raise ValueError(f"{source} DuckDB has duplicate {FACT_TABLE} rows ({sample}).")
    return keyed


def _find_conflicts(
    source_rows: dict[tuple[str, str], MacroDailyRow],
    target_rows: dict[tuple[str, str], MacroDailyRow],
) -> list[tuple[str, str]]:
    conflicts: list[tuple[str, str]] = []
    for key, source_row in source_rows.items():
        target_row = target_rows.get(key)
        if target_row is None:
            continue
        if abs(float(source_row.value_numeric) - float(target_row.value_numeric)) > VALUE_TOLERANCE:
            conflicts.append(key)
            continue
        if source_row.frequency != target_row.frequency or source_row.unit != target_row.unit:
            conflicts.append(key)
    return conflicts


def _insert_rows(conn: duckdb.DuckDBPyConnection, rows: list[MacroDailyRow]) -> None:
    placeholders = ", ".join("?" for _ in FACT_COLUMNS)
    conn.executemany(
        f"""
        insert into {FACT_TABLE} ({", ".join(FACT_COLUMNS)})
        values ({placeholders})
        """,
        [row.as_insert_tuple() for row in rows],
    )


def _min_trade_date(rows: list[MacroDailyRow]) -> str | None:
    return min((row.trade_date for row in rows), default=None)


def _max_trade_date(rows: list[MacroDailyRow]) -> str | None:
    return max((row.trade_date for row in rows), default=None)


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill CSI300 benchmark rows from a local DuckDB backup.")
    parser.add_argument("--duckdb-path", default="data/moss.duckdb", help="Current DuckDB file path.")
    parser.add_argument("--backup-duckdb-path", required=True, help="Backup DuckDB file path to read from.")
    parser.add_argument("--start-date", required=True, help="Inclusive start date in YYYY-MM-DD.")
    parser.add_argument("--end-date", required=True, help="Inclusive end date in YYYY-MM-DD.")
    parser.add_argument(
        "--series-ids",
        default=",".join(DEFAULT_SERIES_IDS),
        help="Comma-separated series IDs to copy. Defaults to CA.CSI300.",
    )
    parser.add_argument("--governance-dir", default=None, help="Directory for the DuckDB write lock.")
    parser.add_argument("--dry-run", action="store_true", help="Report rows that would be inserted without writing.")
    args = parser.parse_args()

    try:
        result = backfill_csi300_benchmark_from_backup(
            duckdb_path=args.duckdb_path,
            backup_duckdb_path=args.backup_duckdb_path,
            start_date=args.start_date,
            end_date=args.end_date,
            series_ids=args.series_ids.split(","),
            dry_run=args.dry_run,
            governance_dir=args.governance_dir,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
