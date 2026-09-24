"""DuckDB writer for ``std_external_macro_daily`` (external macro ETL)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

import duckdb
from backend.app.repositories.task_write_guard import require_repository_task_write_scope

_INSERT_SQL = """
insert or replace into std_external_macro_daily (
  series_id, vendor_name, domain, trade_date, value_numeric,
  frequency, unit, source_version, vendor_version, rule_version,
  ingest_batch_id, raw_zone_path, created_at
) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


@dataclass(frozen=True)
class StdExternalMacroDailyRow:
    series_id: str
    vendor_name: str
    domain: str
    trade_date: str
    value_numeric: float | None
    frequency: str | None
    unit: str | None
    source_version: str
    vendor_version: str
    rule_version: str
    ingest_batch_id: str
    raw_zone_path: str
    created_at: datetime


def upsert_macro_daily_rows(
    conn: duckdb.DuckDBPyConnection,
    rows: Sequence[StdExternalMacroDailyRow],
) -> int:
    require_repository_task_write_scope("upsert_macro_daily_rows")
    count = 0
    for row in rows:
        conn.execute(
            _INSERT_SQL,
            [
                row.series_id,
                row.vendor_name,
                row.domain,
                row.trade_date,
                row.value_numeric,
                row.frequency,
                row.unit,
                row.source_version,
                row.vendor_version,
                row.rule_version,
                row.ingest_batch_id,
                row.raw_zone_path,
                row.created_at,
            ],
        )
        count += 1
    return count
