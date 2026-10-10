"""DuckDB writer for ``std_external_supply_auction_calendar`` (research calendar ETL)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

import duckdb
from backend.app.repositories.task_write_guard import require_repository_task_write_scope

_DELETE_SQL = """
delete from std_external_supply_auction_calendar
where series_id = ? and event_id = ?
"""

_INSERT_SQL = """
insert or replace into std_external_supply_auction_calendar (
  series_id, event_id, vendor_name, source_family, domain, event_date,
  event_kind, title, issuer, market, instrument_type, term_label,
  amount_numeric, amount_unit, currency, status, severity,
  headline_text, headline_url, headline_published_at,
  source_version, vendor_version, rule_version, ingest_batch_id, created_at
) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


@dataclass(frozen=True)
class StdSupplyAuctionCalendarRow:
    series_id: str
    event_id: str
    vendor_name: object
    source_family: object
    domain: object
    event_date: str
    event_kind: str
    title: str
    issuer: object
    market: object
    instrument_type: object
    term_label: object
    amount_numeric: object
    amount_unit: object
    currency: object
    status: object
    severity: object
    headline_text: object
    headline_url: object
    headline_published_at: object
    source_version: object
    vendor_version: object
    rule_version: object
    ingest_batch_id: str
    created_at: datetime


def upsert_supply_auction_calendar_rows(
    conn: duckdb.DuckDBPyConnection,
    rows: Sequence[StdSupplyAuctionCalendarRow],
) -> int:
    require_repository_task_write_scope("upsert_supply_auction_calendar_rows")
    count = 0
    for row in rows:
        conn.execute(_DELETE_SQL, [row.series_id, row.event_id])
        conn.execute(
            _INSERT_SQL,
            [
                row.series_id,
                row.event_id,
                row.vendor_name,
                row.source_family,
                row.domain,
                row.event_date,
                row.event_kind,
                row.title,
                row.issuer,
                row.market,
                row.instrument_type,
                row.term_label,
                row.amount_numeric,
                row.amount_unit,
                row.currency,
                row.status,
                row.severity,
                row.headline_text,
                row.headline_url,
                row.headline_published_at,
                row.source_version,
                row.vendor_version,
                row.rule_version,
                row.ingest_batch_id,
                row.created_at,
            ],
        )
        count += 1
    return count
