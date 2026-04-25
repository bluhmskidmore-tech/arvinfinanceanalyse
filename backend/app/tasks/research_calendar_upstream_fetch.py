from __future__ import annotations

import logging
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
from backend.app.services.research_calendar_upstream_fetch_service import (
    archive_research_calendar_supply_auction_raw,
)
from backend.app.tasks.broker import register_actor_once

logger = logging.getLogger(__name__)


def _new_ingest_batch_id() -> str:
    compact = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    suffix = uuid.uuid4().hex[:8]
    return f"research-calendar-fetch-{compact}-{suffix}"


def _fetch_research_calendar_upstream_once(
    ingest_batch_id: str | None = None,
    page_count: int = 2,
    max_items: int = 20,
) -> dict[str, object]:
    settings = get_settings()
    batch = ingest_batch_id or _new_ingest_batch_id()
    db_path = settings.duckdb_path
    db_file = Path(db_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        apply_pending_migrations_on_connection(conn)
        raw_zone_repo = RawZoneRepository()
        fetch_result = archive_research_calendar_supply_auction_raw(
            raw_zone_repo=raw_zone_repo,
            ingest_batch_id=batch,
            page_count=page_count,
            max_items=max_items,
        )
        catalog_repo = ExternalDataCatalogRepository(conn=conn)
        governance_repo = GovernanceRepository(base_dir=settings.governance_path)
        manifest_repo = SourceManifestRepository(governance_repo=governance_repo)
        etl_service = ExternalStdResearchCalendarEtlService(raw_zone_repo, conn)
        ingest_service = ResearchCalendarIngestService(
            raw_zone_repo=raw_zone_repo,
            catalog_repo=catalog_repo,
            manifest_repo=manifest_repo,
            etl_service=etl_service,
        )
        materialized = ingest_service.materialize_all(batch)
    finally:
        conn.close()

    logger.info("research calendar upstream fetch completed batch_id=%s rows=%s", batch, fetch_result["row_count"])
    return {
        "ingest_batch_id": batch,
        "fetched_rows": fetch_result["row_count"],
        "raw_zone_path": fetch_result["raw_zone_path"],
        "results": materialized,
    }


fetch_research_calendar_upstream = register_actor_once(
    "fetch_research_calendar_upstream",
    _fetch_research_calendar_upstream_once,
)
