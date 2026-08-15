from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import duckdb
from backend.app.repositories.external_std_calendar_repo import (
    StdSupplyAuctionCalendarRow,
    upsert_supply_auction_calendar_rows,
)
from backend.app.repositories.raw_zone_repo import RawZoneRepository
from backend.app.schemas.external_data import ExternalDataCatalogEntry


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
        fact_rows: list[StdSupplyAuctionCalendarRow] = []
        for row in rows:
            event_id = str(row.get("event_id", "")).strip()
            event_date = str(row.get("event_date", "")).strip()
            event_kind = str(row.get("event_kind", "")).strip()
            title = str(row.get("title", "")).strip()
            if not (event_id and event_date and event_kind and title):
                continue
            fact_rows.append(
                StdSupplyAuctionCalendarRow(
                    series_id=catalog_entry.series_id,
                    event_id=event_id,
                    vendor_name=row.get("vendor_name") or catalog_entry.vendor_name,
                    source_family=row.get("source_family") or catalog_entry.source_family,
                    domain=row.get("domain") or str(catalog_entry.domain),
                    event_date=event_date,
                    event_kind=event_kind,
                    title=title,
                    issuer=row.get("issuer"),
                    market=row.get("market"),
                    instrument_type=row.get("instrument_type"),
                    term_label=row.get("term_label"),
                    amount_numeric=row.get("amount_numeric"),
                    amount_unit=row.get("amount_unit"),
                    currency=row.get("currency"),
                    status=row.get("status"),
                    severity=row.get("severity"),
                    headline_text=row.get("headline_text"),
                    headline_url=row.get("headline_url"),
                    headline_published_at=row.get("headline_published_at"),
                    source_version=row.get("source_version") or f"ingest_{ingest_batch_id[:12]}",
                    vendor_version=(
                        row.get("vendor_version")
                        or f"{catalog_entry.vendor_name}|{catalog_entry.catalog_version}"
                    ),
                    rule_version=row.get("rule_version") or "rv_supply_auction_v1",
                    ingest_batch_id=ingest_batch_id,
                    created_at=now,
                )
            )
        return upsert_supply_auction_calendar_rows(self._conn, fact_rows)
