"""Ingest Tushare macro series into raw zone + external_data_catalog + source manifest (M2a)."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from backend.app.repositories.external_data_catalog_repo import ExternalDataCatalogRepository
from backend.app.repositories.raw_zone_repo import RawZoneRepository
from backend.app.repositories.source_manifest_repo import SourceManifestRepository
from backend.app.repositories.tushare_adapter import VendorAdapter
from backend.app.repositories.tushare_catalog_seed import TUSHARE_M2A_SERIES, get_m2a_series_by_id
from backend.app.schemas.external_data import ExternalDataCatalogEntry

CATALOG_VERSION_M2A = "m2a.tushare_macro.v1"
ACCESS_PATH_PLACEHOLDER = "select 1 -- m2a placeholder, std table comes in M2b"
_SOURCE_FAMILY = "tushare_macro"


def _source_version_from_payload(payload: object) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return f"sv_tushare_macro_{hashlib.sha256(raw).hexdigest()[:12]}"


def _filename_from_template(template: str, ingest_batch_id: str) -> str:
    path = Path(template.format(ingest_batch_id=ingest_batch_id))
    return path.name


def _latest_trade_date(rows: list[object]) -> str:
    best = ""
    for item in rows:
        if not isinstance(item, dict):
            continue
        td = str(item.get("trade_date", ""))
        if td and td > best:
            best = td
    return best or datetime.now(UTC).date().isoformat()


class TushareMacroIngestService:
    def __init__(
        self,
        *,
        adapter: VendorAdapter,
        raw_zone_repo: RawZoneRepository,
        catalog_repo: ExternalDataCatalogRepository,
        manifest_repo: SourceManifestRepository,
    ) -> None:
        self._adapter = adapter
        self._raw_zone = raw_zone_repo
        self._catalog = catalog_repo
        self._manifest = manifest_repo

    def ingest_series(self, series_id: str, ingest_batch_id: str) -> dict[str, object]:
        cfg = get_m2a_series_by_id(series_id)
        if cfg is None:
            msg = f"Unknown Tushare M2a series_id: {series_id!r}"
            raise ValueError(msg)

        payload = self._adapter.fetch_macro_snapshot(series_id)
        raw_path_template = cfg["raw_zone_path_template"]
        filename = _filename_from_template(raw_path_template, ingest_batch_id)
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        raw_meta = self._raw_zone.archive_bytes("tushare", ingest_batch_id, filename, body)
        raw_zone_path = str(raw_meta["raw_zone_path"])
        source_version = _source_version_from_payload(payload)
        row_list = payload.get("rows", [])
        if not isinstance(row_list, list):
            row_list = []
        report_date = _latest_trade_date(row_list)

        entry = ExternalDataCatalogEntry(
            series_id=cfg["series_id"],
            series_name=cfg["series_name"],
            vendor_name=self._adapter.vendor_name,
            source_family=_SOURCE_FAMILY,
            domain="macro",
            frequency=cfg["frequency"],
            unit=cfg["unit"],
            refresh_tier="on_demand",
            fetch_mode="live",
            raw_zone_path=raw_path_template,
            standardized_table="std_external_macro_daily",
            view_name="vw_external_macro_daily",
            access_path=ACCESS_PATH_PLACEHOLDER,
            catalog_version=CATALOG_VERSION_M2A,
            created_at=datetime.now(UTC).replace(microsecond=0).isoformat(),
        )
        catalog_entry = self._catalog.register(entry)

        manifest_rows = self._manifest.add_many(
            [
                {
                    "vendor_name": self._adapter.vendor_name,
                    "source_family": _SOURCE_FAMILY,
                    "source_version": source_version,
                    "ingest_batch_id": ingest_batch_id,
                    "report_date": report_date,
                    "source_file": filename,
                    "archived_path": raw_zone_path,
                }
            ]
        )
        manifest_record = manifest_rows[0] if manifest_rows else {}

        return {
            "series_id": series_id,
            "raw_zone_path": raw_zone_path,
            "catalog_entry": catalog_entry,
            "manifest_record": manifest_record,
        }

    def ingest_all_seed_series(self, ingest_batch_id: str) -> list[dict[str, object]]:
        return [self.ingest_series(c["series_id"], ingest_batch_id) for c in TUSHARE_M2A_SERIES]
