"""One-shot governed ingest for official NBS quarterly GDP releases."""

from __future__ import annotations

import time
import uuid
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
from backend.app.governance.settings import get_settings
from backend.app.repositories.duckdb_migrations import apply_pending_migrations_on_connection
from backend.app.repositories.external_data_catalog_repo import ExternalDataCatalogRepository
from backend.app.repositories.governance_repo import GovernanceRepository
from backend.app.repositories.nbs_gdp_release_adapter import (
    NbsGdpReleaseAdapter,
    NbsGdpReleaseError,
)
from backend.app.repositories.raw_zone_repo import RawZoneRepository
from backend.app.repositories.source_manifest_repo import SourceManifestRepository
from backend.app.services.external_std_macro_etl_service import ExternalStdMacroEtlService
from backend.app.services.nbs_gdp_release_ingest_service import NbsGdpReleaseIngestService
from backend.app.tasks.broker import register_actor_once


def _new_ingest_batch_id() -> str:
    compact = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"nbs-gdp-{compact}-{uuid.uuid4().hex[:8]}"


def run_nbs_gdp_release_ingest_once(
    ingest_batch_id: str | None = None,
    *,
    reference_date: date | None = None,
) -> dict[str, object]:
    started = time.monotonic()
    batch = ingest_batch_id or _new_ingest_batch_id()
    effective_date = reference_date or date.today()
    settings = get_settings()
    db_file = Path(settings.duckdb_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)
    governance_path = Path(settings.governance_path)
    governance_path.mkdir(parents=True, exist_ok=True)
    conn: duckdb.DuckDBPyConnection | None = None
    try:
        conn = duckdb.connect(str(db_file), read_only=False)
        apply_pending_migrations_on_connection(conn)
        raw_zone = RawZoneRepository()
        service = NbsGdpReleaseIngestService(
            adapter=NbsGdpReleaseAdapter(),
            raw_zone_repo=raw_zone,
            catalog_repo=ExternalDataCatalogRepository(conn=conn),
            manifest_repo=SourceManifestRepository(
                governance_repo=GovernanceRepository(base_dir=governance_path)
            ),
            etl_service=ExternalStdMacroEtlService(raw_zone, conn),
        )
        result = service.ingest_release(batch, reference_date=effective_date)
        return {
            **result,
            "ingest_batch_id": batch,
            "elapsed_seconds": round(time.monotonic() - started, 3),
        }
    except NbsGdpReleaseError as exc:
        return {
            "status": "blocked",
            "ingest_batch_id": batch,
            "error": f"{type(exc).__name__}: {exc}",
            "elapsed_seconds": round(time.monotonic() - started, 3),
        }
    except Exception as exc:
        return {
            "status": "error",
            "ingest_batch_id": batch,
            "error": f"{type(exc).__name__}: {exc}",
            "elapsed_seconds": round(time.monotonic() - started, 3),
        }
    finally:
        if conn is not None:
            conn.close()


refresh_nbs_gdp_release = register_actor_once(
    "refresh_nbs_gdp_release",
    run_nbs_gdp_release_ingest_once,
    time_limit_ms=3_600_000,
)
