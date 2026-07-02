"""Ingest Tushare macro series into raw zone + external_data_catalog + source manifest (M2a)."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

from backend.app.repositories.external_data_catalog_repo import ExternalDataCatalogRepository
from backend.app.repositories.raw_zone_repo import RawZoneRepository
from backend.app.repositories.source_manifest_repo import SourceManifestRepository
from backend.app.repositories.tushare_adapter import VendorAdapter
from backend.app.repositories.tushare_catalog_seed import TUSHARE_M2A_SERIES, get_m2a_series_by_id
from backend.app.schemas.external_data import ExternalDataCatalogEntry
from backend.app.services.external_std_macro_etl_service import ExternalStdMacroEtlService

CATALOG_VERSION_M2A = "m2a.tushare_macro.v1"
ACCESS_PATH_PLACEHOLDER = "select 1 -- m2a placeholder, std table comes in M2b"
_SOURCE_FAMILY = "tushare_macro"

logger = logging.getLogger(__name__)


class TushareIngestFailure(TypedDict):
    series_id: str
    error: str


class TushareIngestBatchSummary(TypedDict):
    """Structured batch outcome: original per-series results plus success/failure split."""

    results: list[dict[str, object]]
    succeeded: list[str]
    failed: list[TushareIngestFailure]


def _error_summary(exc: Exception) -> str:
    text = f"{type(exc).__name__}: {exc}".strip()
    return text if len(text) <= 300 else text[:297] + "..."


def _access_path_vw_macro(series_id: str) -> str:
    s = str(series_id).replace("'", "''")
    return f"select * from vw_external_macro_daily where series_id = '{s}'"


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
        etl_service: ExternalStdMacroEtlService | None = None,
    ) -> None:
        self._adapter = adapter
        self._raw_zone = raw_zone_repo
        self._catalog = catalog_repo
        self._manifest = manifest_repo
        self._etl = etl_service

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

        if self._etl is not None:
            pre_entry = ExternalDataCatalogEntry(
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
            _ = self._etl.materialize_from_raw(raw_zone_path, pre_entry, ingest_batch_id)
            access_path = _access_path_vw_macro(cfg["series_id"])
        else:
            access_path = ACCESS_PATH_PLACEHOLDER

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
            access_path=access_path,
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

    def _ingest_series_with_retry(
        self,
        series_id: str,
        ingest_batch_id: str,
        *,
        max_retries: int = 2,
        retry_sleep_seconds: float = 1.0,
    ) -> dict[str, object]:
        """Run ``ingest_series`` with bounded retries; re-raise the last error when exhausted."""
        attempts = max(0, int(max_retries)) + 1
        for attempt in range(1, attempts + 1):
            try:
                return self.ingest_series(series_id, ingest_batch_id)
            except Exception as exc:
                if attempt >= attempts:
                    raise
                logger.warning(
                    "tushare macro ingest retry series_id=%s attempt=%s/%s error=%s",
                    series_id,
                    attempt,
                    attempts,
                    _error_summary(exc),
                )
                if retry_sleep_seconds > 0:
                    time.sleep(retry_sleep_seconds)
        msg = f"unreachable: retry loop exhausted for series {series_id!r}"
        raise RuntimeError(msg)

    def ingest_all_seed_series_with_summary(
        self,
        ingest_batch_id: str,
        *,
        max_retries: int = 2,
        retry_sleep_seconds: float = 1.0,
    ) -> TushareIngestBatchSummary:
        """Ingest every M2a seed series; a single failing series never aborts the batch.

        Additive companion to ``ingest_all_seed_series`` (whose list return shape has
        callers): ``results`` keeps the original per-series result dicts for the
        series that succeeded, while ``succeeded`` / ``failed`` summarize the batch
        so callers can alert on partial failures instead of failing silently.
        """
        results: list[dict[str, object]] = []
        succeeded: list[str] = []
        failed: list[TushareIngestFailure] = []
        for cfg in TUSHARE_M2A_SERIES:
            series_id = cfg["series_id"]
            try:
                result = self._ingest_series_with_retry(
                    series_id,
                    ingest_batch_id,
                    max_retries=max_retries,
                    retry_sleep_seconds=retry_sleep_seconds,
                )
            except Exception as exc:
                failed.append({"series_id": series_id, "error": _error_summary(exc)})
                continue
            results.append(result)
            succeeded.append(series_id)
        return {"results": results, "succeeded": succeeded, "failed": failed}
