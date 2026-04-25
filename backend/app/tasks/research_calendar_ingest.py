from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

import duckdb
from backend.app.governance.settings import get_settings
from backend.app.repositories.duckdb_migrations import apply_pending_migrations_on_connection
from backend.app.repositories.external_data_catalog_repo import ExternalDataCatalogRepository
from backend.app.repositories.governance_repo import GovernanceRepository
from backend.app.repositories.raw_zone_repo import RawZoneRepository
from backend.app.repositories.source_manifest_repo import SourceManifestRepository
from backend.app.services.external_std_research_calendar_etl_service import (
    ExternalStdResearchCalendarEtlService,
)
from backend.app.services.research_calendar_ingest_service import ResearchCalendarIngestService


def _new_ingest_batch_id() -> str:
    compact = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    suffix = uuid.uuid4().hex[:8]
    return f"research-calendar-{compact}-{suffix}"


def run_research_calendar_ingest_once(ingest_batch_id: str | None = None) -> dict[str, object]:
    settings = get_settings()
    batch = ingest_batch_id or _new_ingest_batch_id()
    db_path = settings.duckdb_path
    db_file = Path(db_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        apply_pending_migrations_on_connection(conn)
        catalog_repo = ExternalDataCatalogRepository(conn=conn)
        raw_zone_repo = RawZoneRepository()
        governance_repo = GovernanceRepository(base_dir=settings.governance_path)
        manifest_repo = SourceManifestRepository(governance_repo=governance_repo)
        etl_service = ExternalStdResearchCalendarEtlService(raw_zone_repo, conn)
        service = ResearchCalendarIngestService(
            raw_zone_repo=raw_zone_repo,
            catalog_repo=catalog_repo,
            manifest_repo=manifest_repo,
            etl_service=etl_service,
        )
        results = service.materialize_all(batch)
    finally:
        conn.close()

    return {
        "ingest_batch_id": batch,
        "results": results,
    }
