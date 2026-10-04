"""Archive and materialize official NBS monthly CPI and PPI release evidence."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from backend.app.repositories.external_data_catalog_repo import ExternalDataCatalogRepository
from backend.app.repositories.nbs_inflation_catalog_seed import (
    NBS_INFLATION_SOURCE_FAMILY,
    build_nbs_inflation_catalog_entry,
    nbs_inflation_raw_filename,
)
from backend.app.repositories.nbs_inflation_release_adapter import (
    NbsInflationReleaseAdapter,
)
from backend.app.repositories.raw_zone_repo import RawZoneRepository
from backend.app.repositories.source_manifest_repo import SourceManifestRepository
from backend.app.services.external_std_macro_etl_service import ExternalStdMacroEtlService

RULE_VERSION = "rv_nbs_inflation_release_v1"


class NbsInflationReleaseIngestService:
    def __init__(
        self,
        *,
        adapter: NbsInflationReleaseAdapter,
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

    def ingest_release_month(
        self,
        ingest_batch_id: str,
        *,
        reference_date: date,
        reference_month: str | None = None,
    ) -> dict[str, object]:
        html_archives: dict[tuple[str, str], dict[str, object]] = {}

        def archive_before_parse(series_id: str, release_url: str, payload: bytes) -> None:
            source_name = Path(urlparse(release_url).path).name or "release.html"
            series_slug = series_id.rsplit(".", 2)[-2]
            filename = f"nbs_{series_slug}_release_{source_name}"
            html_archives[(series_id, release_url)] = self._raw_zone.archive_bytes(
                "nbs",
                ingest_batch_id,
                filename,
                payload,
            )

        documents = self._adapter.discover_and_fetch(
            reference_date=reference_date,
            reference_month=reference_month,
            before_parse=archive_before_parse,
        )
        results: list[dict[str, object]] = []
        total_materialized_rows = 0
        manifest_payloads: list[dict[str, object]] = []
        series_ids = sorted({document.series_id for document in documents})
        for series_id in series_ids:
            series_documents = sorted(
                (document for document in documents if document.series_id == series_id),
                key=lambda document: document.reference_month,
            )
            rows: list[dict[str, object]] = []
            digests: list[str] = []
            html_paths: list[str] = []
            release_urls: list[str] = []
            for document in series_documents:
                html_meta = html_archives.get((document.series_id, document.release_url))
                if html_meta is None:
                    raise ValueError("NBS inflation release HTML must be archived before parsing")
                digest = hashlib.sha256(document.html_bytes).hexdigest()
                source_version = f"nbs_inflation_release_sha256_{digest}"
                rows.append(
                    self._validated_observation(
                        document.observation,
                        source_version=source_version,
                    )
                )
                digests.append(digest)
                html_paths.append(str(html_meta["raw_zone_path"]))
                release_urls.append(document.release_url)
            combined_digest = hashlib.sha256("".join(digests).encode("ascii")).hexdigest()
            vendor_version = f"vv_nbs_inflation_release_sha256_{combined_digest}"
            normalized_payload = {
                "series_id": series_id,
                "vendor_name": "nbs",
                "release_urls": release_urls,
                "fetched_at": max(
                    document.fetched_at for document in series_documents
                ).isoformat(),
                "rows": rows,
            }
            normalized_bytes = json.dumps(
                normalized_payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            filename = nbs_inflation_raw_filename(series_id)
            normalized_meta = self._raw_zone.archive_bytes(
                "nbs",
                ingest_batch_id,
                filename,
                normalized_bytes,
            )
            normalized_path = str(normalized_meta["raw_zone_path"])
            catalog_entry = build_nbs_inflation_catalog_entry(series_id)
            materialized_rows = self._etl.materialize_from_raw(
                normalized_path,
                catalog_entry,
                ingest_batch_id,
                vendor_version=vendor_version,
                rule_version=RULE_VERSION,
            )
            total_materialized_rows += materialized_rows
            if materialized_rows != len(rows):
                raise ValueError(
                    f"NBS inflation materialized row count mismatch for {series_id}"
                )
            self._catalog.register(catalog_entry)
            for row, release_url, digest, html_path in zip(
                rows,
                release_urls,
                digests,
                html_paths,
                strict=True,
            ):
                manifest_payloads.append(
                    {
                        "vendor_name": "nbs",
                        "source_family": NBS_INFLATION_SOURCE_FAMILY,
                        "source_version": row["source_version"],
                        "ingest_batch_id": ingest_batch_id,
                        "report_date": row["trade_date"],
                        "source_file": filename,
                        "archived_path": normalized_path,
                        "release_url": release_url,
                        "content_sha256": digest,
                        "html_archive_path": html_path,
                        "normalized_archive_path": normalized_path,
                        "rule_version": RULE_VERSION,
                    }
                )
            results.append(
                {
                    "series_id": series_id,
                    "release_urls": release_urls,
                    "latest_observation": max(str(row["trade_date"]) for row in rows),
                    "materialized_rows": materialized_rows,
                    "source_versions": [str(row["source_version"]) for row in rows],
                    "vendor_version": vendor_version,
                    "rule_version": RULE_VERSION,
                    "html_raw_zone_paths": html_paths,
                    "normalized_raw_zone_path": normalized_path,
                }
            )
        self._manifest.add_many(manifest_payloads)
        reference_months = sorted({document.reference_month for document in documents})
        return {
            "status": "success",
            "reference_month": max(reference_months),
            "reference_months": reference_months,
            "results": results,
            "materialized_rows": total_materialized_rows,
        }

    @staticmethod
    def _validated_observation(
        observation: dict[str, object],
        *,
        source_version: str,
    ) -> dict[str, object]:
        trade_date = str(observation.get("trade_date", ""))
        try:
            date.fromisoformat(trade_date)
        except ValueError as exc:
            raise ValueError("NBS inflation observation has invalid trade_date") from exc
        value = observation.get("value")
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
        ):
            raise ValueError("NBS inflation observation must contain a finite numeric value")
        if str(observation.get("source_version", "")) != source_version:
            raise ValueError("NBS inflation observation source version does not match HTML")
        return {
            "trade_date": trade_date,
            "value": float(value),
            "source_version": source_version,
        }
