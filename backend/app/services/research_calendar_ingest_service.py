from __future__ import annotations

import hashlib
import json
from pathlib import Path

from backend.app.repositories.external_data_catalog_repo import ExternalDataCatalogRepository
from backend.app.repositories.raw_zone_repo import RawZoneRepository
from backend.app.repositories.research_calendar_catalog_seed import (
    RESEARCH_CALENDAR_V1_SERIES,
    register_research_calendar_v1_catalog_descriptors,
)
from backend.app.repositories.source_manifest_repo import SourceManifestRepository
from backend.app.services.external_std_research_calendar_etl_service import (
    ExternalStdResearchCalendarEtlService,
)


def _source_version_from_payload(payload: object) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return f"sv_research_calendar_{hashlib.sha256(raw).hexdigest()[:12]}"


def _filename_from_template(template: str, ingest_batch_id: str) -> str:
    path = Path(template.format(ingest_batch_id=ingest_batch_id))
    return path.name


def _resolve_raw_zone_path(raw_zone_repo: RawZoneRepository, template: str, ingest_batch_id: str) -> str:
    rendered = template.format(ingest_batch_id=ingest_batch_id)
    raw_root = Path(raw_zone_repo.local_raw_path)
    candidate = Path(rendered)
    parts = candidate.parts
    if len(parts) >= 2 and parts[0] == "data" and parts[1] == "raw":
        return str(raw_root.joinpath(*parts[2:]))
    if candidate.is_absolute():
        return str(candidate)
    return str(raw_root / candidate)


class ResearchCalendarIngestService:
    def __init__(
        self,
        *,
        raw_zone_repo: RawZoneRepository,
        catalog_repo: ExternalDataCatalogRepository,
        manifest_repo: SourceManifestRepository,
        etl_service: ExternalStdResearchCalendarEtlService,
    ) -> None:
        self._raw = raw_zone_repo
        self._catalog = catalog_repo
        self._manifest = manifest_repo
        self._etl = etl_service

    def register_catalog(self) -> int:
        return register_research_calendar_v1_catalog_descriptors(self._catalog)

    def materialize_series(self, series_id: str, ingest_batch_id: str) -> dict[str, object]:
        cfg = next((item for item in RESEARCH_CALENDAR_V1_SERIES if item["series_id"] == series_id), None)
        if cfg is None:
            raise ValueError(f"Unknown research calendar series_id: {series_id!r}")

        entry = self._catalog.get_by_series_id(series_id)
        if entry is None:
            self.register_catalog()
            entry = self._catalog.get_by_series_id(series_id)
        if entry is None:
            raise RuntimeError(f"Failed to register catalog entry for {series_id}")

        raw_zone_path = _resolve_raw_zone_path(
            self._raw,
            cfg["raw_zone_path_template"],
            ingest_batch_id,
        )
        payload = json.loads(self._raw.read_bytes(raw_zone_path).decode("utf-8"))
        row_count = self._etl.materialize_from_raw(raw_zone_path, entry, ingest_batch_id)
        report_date = max(
            (str(item.get("event_date", "")) for item in payload.get("rows", []) if isinstance(item, dict)),
            default="",
        )
        manifest_rows = self._manifest.add_many(
            [
                {
                    "vendor_name": entry.vendor_name,
                    "source_family": entry.source_family,
                    "source_version": _source_version_from_payload(payload),
                    "ingest_batch_id": ingest_batch_id,
                    "report_date": report_date,
                    "source_file": _filename_from_template(cfg["raw_zone_path_template"], ingest_batch_id),
                    "archived_path": raw_zone_path,
                }
            ]
        )
        return {
            "series_id": series_id,
            "row_count": row_count,
            "raw_zone_path": raw_zone_path,
            "catalog_entry": entry.model_dump(),
            "manifest_record": manifest_rows[0] if manifest_rows else {},
        }

    def materialize_all(self, ingest_batch_id: str) -> list[dict[str, object]]:
        self.register_catalog()
        return [
            self.materialize_series(cfg["series_id"], ingest_batch_id)
            for cfg in RESEARCH_CALENDAR_V1_SERIES
        ]
