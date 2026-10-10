"""Archive and materialize official NBS quarterly GDP release evidence."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from backend.app.repositories.external_data_catalog_repo import ExternalDataCatalogRepository
from backend.app.repositories.nbs_gdp_catalog_seed import (
    NBS_GDP_SERIES_ID,
    NBS_GDP_SOURCE_FAMILY,
    build_nbs_gdp_catalog_entry,
)
from backend.app.repositories.nbs_gdp_release_adapter import NbsGdpReleaseAdapter
from backend.app.repositories.raw_zone_repo import RawZoneRepository
from backend.app.repositories.source_manifest_repo import SourceManifestRepository
from backend.app.services.external_std_macro_etl_service import ExternalStdMacroEtlService

RULE_VERSION = "rv_nbs_gdp_release_v1"


class NbsGdpReleaseIngestService:
    def __init__(
        self,
        *,
        adapter: NbsGdpReleaseAdapter,
        raw_zone_repo: RawZoneRepository,
        catalog_repo: ExternalDataCatalogRepository,
        manifest_repo: SourceManifestRepository,
        etl_service: ExternalStdMacroEtlService,
    ) -> None:
        self._adapter = adapter
        self._raw_zone = raw_zone_repo
        self._catalog = catalog_repo
        self._manifest = manifest_repo
        self._etl = etl_service

    def ingest_release(self, ingest_batch_id: str, *, reference_date: date) -> dict[str, object]:
        html_archives: dict[str, dict[str, object]] = {}

        def archive_before_parse(release_url: str, payload: bytes) -> None:
            source_name = Path(urlparse(release_url).path).name or "release.html"
            filename = f"nbs_gdp_release_{source_name}"
            html_archives[release_url] = self._raw_zone.archive_bytes(
                "nbs",
                ingest_batch_id,
                filename,
                payload,
            )

        document = self._adapter.discover_and_fetch(
            reference_date=reference_date,
            before_parse=archive_before_parse,
        )
        html_meta = html_archives.get(document.release_url)
        if html_meta is None:
            raise ValueError("NBS release HTML must be archived before parsing")

        digest = hashlib.sha256(document.html_bytes).hexdigest()
        source_version = f"nbs_gdp_release_sha256_{digest}"
        vendor_version = f"vv_nbs_gdp_release_sha256_{digest}"
        rows = self._validated_rows(document.observations, source_version=source_version)
        latest_observation = max(str(row["trade_date"]) for row in rows)
        normalized_payload = {
            "series_id": NBS_GDP_SERIES_ID,
            "vendor_name": "nbs",
            "release_url": document.release_url,
            "source_version": source_version,
            "rows": rows,
        }
        normalized_bytes = json.dumps(
            normalized_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        normalized_meta = self._raw_zone.archive_bytes(
            "nbs",
            ingest_batch_id,
            "nbs_gdp_quarterly.json",
            normalized_bytes,
        )
        normalized_path = str(normalized_meta["raw_zone_path"])
        catalog_entry = build_nbs_gdp_catalog_entry()
        materialized_rows = self._etl.materialize_from_raw(
            normalized_path,
            catalog_entry,
            ingest_batch_id,
            vendor_version=vendor_version,
            rule_version=RULE_VERSION,
        )
        if materialized_rows != len(rows):
            raise ValueError("NBS GDP materialized row count does not match validated input")

        self._catalog.register(catalog_entry)
        self._manifest.add_many(
            [
                {
                    "vendor_name": "nbs",
                    "source_family": NBS_GDP_SOURCE_FAMILY,
                    "source_version": source_version,
                    "ingest_batch_id": ingest_batch_id,
                    "report_date": latest_observation,
                    "source_file": "nbs_gdp_quarterly.json",
                    "archived_path": normalized_path,
                    "release_url": document.release_url,
                    "content_sha256": digest,
                    "html_archive_path": str(html_meta["raw_zone_path"]),
                    "normalized_archive_path": normalized_path,
                    "rule_version": RULE_VERSION,
                }
            ]
        )
        return {
            "status": "success",
            "series_id": NBS_GDP_SERIES_ID,
            "release_url": document.release_url,
            "latest_observation": latest_observation,
            "materialized_rows": materialized_rows,
            "source_version": source_version,
            "vendor_version": vendor_version,
            "rule_version": RULE_VERSION,
            "html_raw_zone_path": str(html_meta["raw_zone_path"]),
            "normalized_raw_zone_path": normalized_path,
        }

    @staticmethod
    def _validated_rows(
        observations: list[dict[str, object]],
        *,
        source_version: str,
    ) -> list[dict[str, object]]:
        if not observations:
            raise ValueError("NBS GDP observations must be a non-empty list")
        by_date: dict[str, dict[str, object]] = {}
        for index, row in enumerate(observations):
            trade_date = str(row.get("trade_date", ""))
            try:
                date.fromisoformat(trade_date)
            except ValueError as exc:
                raise ValueError(f"NBS GDP row {index} has invalid trade_date") from exc
            value = row.get("value")
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
            ):
                raise ValueError(f"NBS GDP row {index} must contain a finite numeric value")
            if str(row.get("source_version", "")) != source_version:
                raise ValueError(f"NBS GDP row {index} source version does not match HTML")
            normalized = {
                "trade_date": trade_date,
                "value": float(value),
                "source_version": source_version,
            }
            existing = by_date.get(trade_date)
            if existing is not None and existing != normalized:
                raise ValueError(f"NBS GDP row {index} conflicts with a duplicate period")
            by_date[trade_date] = normalized
        return [by_date[key] for key in sorted(by_date)]
