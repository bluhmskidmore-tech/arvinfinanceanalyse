from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import duckdb
from backend.app.repositories.raw_zone_repo import RawZoneRepository
from backend.app.schemas.external_data import ExternalDataCatalogEntry

_INSERT_SQL = """
insert or replace into std_external_supply_auction_calendar (
  series_id, event_id, vendor_name, source_family, domain, event_date,
  event_kind, title, issuer, market, instrument_type, term_label,
  amount_numeric, amount_unit, currency, status, severity,
  headline_text, headline_url, headline_published_at,
  source_version, vendor_version, rule_version, ingest_batch_id, created_at
) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def _rows_from_raw_payload(raw: object) -> list[dict[str, Any]]:
    if not isinstance(raw, dict):
        return []
    rows = raw.get("rows", [])
    if not isinstance(rows, list):
        return []
    return [item for item in rows if isinstance(item, dict)]


class ExternalStdResearchCalendarEtlService:
    def __init__(
        self,
        raw_zone_repo: RawZoneRepository,
        conn: duckdb.DuckDBPyConnection,
    ) -> None:
        self._raw = raw_zone_repo
        self._conn = conn

    def materialize_from_raw(
        self,
        raw_zone_path: str,
        catalog_entry: ExternalDataCatalogEntry,
        ingest_batch_id: str,
    ) -> int:
        if catalog_entry.standardized_table not in (None, "std_external_supply_auction_calendar"):
            msg = (
                "Research calendar ETL only supports std_external_supply_auction_calendar, "
                f"got {catalog_entry.standardized_table!r}"
            )
            raise ValueError(msg)
        payload = json.loads(self._raw.read_bytes(raw_zone_path).decode("utf-8"))
        rows = _rows_from_raw_payload(payload)
        now = datetime.now(UTC).replace(microsecond=0)
        count = 0
        for row in rows:
            event_id = str(row.get("event_id", "")).strip()
            event_date = str(row.get("event_date", "")).strip()
            event_kind = str(row.get("event_kind", "")).strip()
            title = str(row.get("title", "")).strip()
            if not (event_id and event_date and event_kind and title):
                continue
            self._conn.execute(
                """
                delete from std_external_supply_auction_calendar
                where series_id = ? and event_id = ?
                """,
                [catalog_entry.series_id, event_id],
            )
            self._conn.execute(
                _INSERT_SQL,
                [
                    catalog_entry.series_id,
                    event_id,
                    row.get("vendor_name") or catalog_entry.vendor_name,
                    row.get("source_family") or catalog_entry.source_family,
                    row.get("domain") or str(catalog_entry.domain),
                    event_date,
                    event_kind,
                    title,
                    row.get("issuer"),
                    row.get("market"),
                    row.get("instrument_type"),
                    row.get("term_label"),
                    row.get("amount_numeric"),
                    row.get("amount_unit"),
                    row.get("currency"),
                    row.get("status"),
                    row.get("severity"),
                    row.get("headline_text"),
                    row.get("headline_url"),
                    row.get("headline_published_at"),
                    row.get("source_version") or f"ingest_{ingest_batch_id[:12]}",
                    row.get("vendor_version") or f"{catalog_entry.vendor_name}|{catalog_entry.catalog_version}",
                    row.get("rule_version") or "rv_supply_auction_v1",
                    ingest_batch_id,
                    now,
                ],
            )
            count += 1
        return count
