"""One-shot Tushare macro ingest: raw zone + external_data_catalog + source manifest (M2a)."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path

import duckdb
from backend.app.governance.locks import acquire_lock, resolve_duckdb_writer_lock
from backend.app.governance.settings import get_settings
from backend.app.repositories.duckdb_migrations import apply_pending_migrations_on_connection
from backend.app.repositories.external_data_catalog_repo import ExternalDataCatalogRepository
from backend.app.repositories.governance_repo import GovernanceRepository
from backend.app.repositories.raw_zone_repo import RawZoneRepository
from backend.app.repositories.source_manifest_repo import SourceManifestRepository
from backend.app.repositories.task_write_guard import repository_task_write_scope
from backend.app.repositories.tushare_adapter import VendorAdapter
from backend.app.services.external_std_macro_etl_service import ExternalStdMacroEtlService
from backend.app.services.tushare_macro_ingest_service import TushareMacroIngestService
from backend.app.tasks.broker import register_actor_once

logger = logging.getLogger(__name__)


def _new_ingest_batch_id() -> str:
    compact = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    suffix = uuid.uuid4().hex[:8]
    return f"tushare-macro-{compact}-{suffix}"


def run_tushare_macro_ingest_once(ingest_batch_id: str | None = None) -> dict[str, object]:
    """Materialize all M2a seed series through one governed DuckDB write connection."""
    settings = get_settings()
    batch = ingest_batch_id or _new_ingest_batch_id()
    db_path = settings.duckdb_path
    db_file = Path(db_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)
    with acquire_lock(resolve_duckdb_writer_lock(db_file), base_dir=db_file.parent):
        conn = duckdb.connect(str(db_path), read_only=False)
        try:
            apply_pending_migrations_on_connection(conn)
            raw_zone = RawZoneRepository()
            catalog_repo = ExternalDataCatalogRepository(conn=conn)
            gov = GovernanceRepository(base_dir=settings.governance_path)
            manifest_repo = SourceManifestRepository(governance_repo=gov)
            service = TushareMacroIngestService(
                adapter=VendorAdapter(),
                raw_zone_repo=raw_zone,
                catalog_repo=catalog_repo,
                manifest_repo=manifest_repo,
                etl_service=ExternalStdMacroEtlService(raw_zone, conn),
            )
            with repository_task_write_scope(__name__):
                summary = service.ingest_all_seed_series_with_summary(batch)
            results = summary["results"]
            succeeded = summary["succeeded"]
            failed = summary["failed"]
            status = summary["status"]
            if failed:
                logger.error(
                    "tushare macro ingest failures batch_id=%s failed_count=%s failed_series=%s",
                    batch,
                    len(failed),
                    failed,
                )
            if failed and not succeeded:
                msg = f"tushare macro ingest batch {batch!r} failed for all {len(failed)} series"
                raise RuntimeError(msg)
            logger.info(
                "tushare macro ingest completed batch_id=%s series=%s failed=%s",
                batch,
                len(results),
                len(failed),
            )
            return {
                "ingest_batch_id": batch,
                "status": status,
                "results": results,
                "succeeded": succeeded,
                "failed": failed,
            }
        finally:
            conn.close()


refresh_tushare_macro = register_actor_once(
    "refresh_tushare_macro",
    run_tushare_macro_ingest_once,
    time_limit_ms=3_600_000,
)
