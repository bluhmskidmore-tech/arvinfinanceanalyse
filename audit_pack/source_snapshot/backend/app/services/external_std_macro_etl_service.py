"""Raw JSON (Tushare macro shape) → ``std_external_macro_daily`` (M2b)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import duckdb
from backend.app.repositories.raw_zone_repo import RawZoneRepository
from backend.app.repositories.tushare_catalog_seed import TUSHARE_M2A_SERIES, get_m2a_series_by_id
from backend.app.schemas.external_data import ExternalDataCatalogEntry

_INSERT_SQL = """
insert or replace into std_external_macro_daily (
  series_id, vendor_name, domain, trade_date, value_numeric,
  frequency, unit, source_version, vendor_version, rule_version,
  ingest_batch_id, raw_zone_path, created_at
) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def _rows_from_raw_payload(raw: object) -> list[dict[str, Any]]:
    if not isinstance(raw, dict):
        return []
    rlist = raw.get("rows", [])
    if not isinstance(rlist, list):
        return []
    out: list[dict[str, Any]] = []
    for item in rlist:
        if not isinstance(item, dict):
            continue
        out.append(item)
    return out


def _row_value_num(row: dict[str, Any]) -> float | None:
    for key in ("value", "value_numeric"):
        v = row.get(key)
        if v is not None and isinstance(v, (int, float)):
            return float(v)
    return None


class ExternalStdMacroEtlService:
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
        if catalog_entry.standardized_table not in (None, "std_external_macro_daily"):
            msg = f"ETL only supports std_external_macro_daily, got {catalog_entry.standardized_table!r}"
            raise ValueError(msg)
        body = self._raw.read_bytes(raw_zone_path)
        payload = json.loads(body.decode("utf-8"))
        rows = _rows_from_raw_payload(payload)
        now = datetime.now(UTC).replace(microsecond=0)
        series_id = catalog_entry.series_id
        vendor = catalog_entry.vendor_name
        dom = str(catalog_entry.domain)
        count = 0
        for row in rows:
            td = str(row.get("trade_date", "")).strip()
            if not td:
                continue
            vnum = _row_value_num(row)
            source_version: str | None
            v = row.get("source_version")
            source_version = str(v) if v is not None else None
            if source_version is None and isinstance(payload, dict) and "fetched_at" in payload:
                source_version = f"raw@{payload.get('fetched_at')}"
            if source_version is None:
                source_version = f"ingest_{ingest_batch_id[:12]}"
            vver = f"{vendor}|{catalog_entry.catalog_version}"
            rver = "m2b.external_std_macro_etl.v1"
            self._conn.execute(
                _INSERT_SQL,
                [
                    series_id,
                    vendor,
                    dom,
                    td,
                    vnum,
                    catalog_entry.frequency,
                    catalog_entry.unit,
                    source_version,
                    vver,
                    rver,
                    ingest_batch_id,
                    raw_zone_path,
                    now,
                ],
            )
            count += 1
        return count

    def _series_paths_for_batch(
        self,
        ingest_batch_id: str,
    ) -> Iterator[tuple[str, str]]:
        for cfg in TUSHARE_M2A_SERIES:
            tpl = str(cfg.get("raw_zone_path_template", ""))
            path = tpl.format(ingest_batch_id=ingest_batch_id)
            yield cfg["series_id"], path

    def materialize_all_for_batch(self, ingest_batch_id: str) -> dict[str, int]:
        out: dict[str, int] = {}
        for series_id, rel_path in self._series_paths_for_batch(ingest_batch_id):
            p = str(rel_path)
            try:
                _ = self._raw.read_bytes(p)
            except FileNotFoundError:
                out[series_id] = 0
                continue
            cfg = get_m2a_series_by_id(series_id)
            if cfg is None:
                out[series_id] = 0
                continue
            entry = ExternalDataCatalogEntry(
                series_id=cfg["series_id"],
                series_name=cfg["series_name"],
                vendor_name="tushare",
                source_family="tushare_macro",
                domain="macro",
                frequency=cfg["frequency"],
                unit=cfg["unit"],
                refresh_tier="on_demand",
                fetch_mode="batch_materialize",
                raw_zone_path=cfg["raw_zone_path_template"],
                standardized_table="std_external_macro_daily",
                view_name="vw_external_macro_daily",
                access_path="select 1",
                catalog_version="m2b.tushare_macro.v1",
                created_at=datetime.now(UTC).replace(microsecond=0).isoformat(),
            )
            n = self.materialize_from_raw(p, entry, ingest_batch_id)
            out[series_id] = n
        return out
