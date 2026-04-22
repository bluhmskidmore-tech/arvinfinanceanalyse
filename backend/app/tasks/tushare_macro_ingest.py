"""One-shot Tushare macro ingest: raw zone + external_data_catalog + source manifest (M2a)."""

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
from backend.app.repositories.tushare_adapter import VendorAdapter
from backend.app.services.tushare_macro_ingest_service import TushareMacroIngestService

logger = logging.getLogger(__name__)


def _new_ingest_batch_id() -> str:
    compact = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    suffix = uuid.uuid4().hex[:8]
    return f"tushare-macro-{compact}-{suffix}"


def run_tushare_macro_ingest_once(ingest_batch_id: str | None = None) -> dict[str, object]:
    """Apply DuckDB migrations, then run all M2a seed series through the ingest service."""
    settings = get_settings()
    batch = ingest_batch_id or _new_ingest_batch_id()
    db_path = settings.duckdb_path
    db_file = Path(db_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        apply_pending_migrations_on_connection(conn)
    finally:
        conn.close()

    catalog_repo = ExternalDataCatalogRepository(path=db_path)
    raw_zone = RawZoneRepository()
    gov = GovernanceRepository(base_dir=settings.governance_path)
    manifest_repo = SourceManifestRepository(governance_repo=gov)
    service = TushareMacroIngestService(
        adapter=VendorAdapter(),
        raw_zone_repo=raw_zone,
        catalog_repo=catalog_repo,
        manifest_repo=manifest_repo,
    )
    results = service.ingest_all_seed_series(batch)
    logger.info("tushare macro ingest completed batch_id=%s series=%s", batch, len(results))
    return {
        "ingest_batch_id": batch,
        "results": results,
    }
