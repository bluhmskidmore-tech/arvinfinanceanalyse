"""One-shot governed ingest for official NBS monthly CPI and PPI releases."""

from __future__ import annotations

import argparse
import json
import time
import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
from backend.app.governance.locks import acquire_lock, resolve_duckdb_writer_lock
from backend.app.governance.settings import get_settings
from backend.app.network.source_bound_socks_proxy import resolve_vendor_source_ip
from backend.app.repositories.duckdb_migrations import apply_pending_migrations_on_connection
from backend.app.repositories.external_data_catalog_repo import ExternalDataCatalogRepository
from backend.app.repositories.governance_repo import GovernanceRepository
from backend.app.repositories.nbs_inflation_release_adapter import (
    NbsInflationReleaseAdapter,
    NbsInflationReleaseError,
)
from backend.app.repositories.raw_zone_repo import RawZoneRepository
from backend.app.repositories.source_manifest_repo import SourceManifestRepository
from backend.app.repositories.task_write_guard import repository_task_write_scope
from backend.app.services.external_std_macro_etl_service import ExternalStdMacroEtlService
from backend.app.services.nbs_inflation_release_ingest_service import (
    NbsInflationReleaseIngestService,
)


def _new_ingest_batch_id() -> str:
    compact = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"nbs-inflation-{compact}-{uuid.uuid4().hex[:8]}"


def run_nbs_inflation_release_ingest_once(
    ingest_batch_id: str | None = None,
    *,
    reference_date: date | None = None,
    reference_month: str | None = None,
    source_ip: str | None = None,
) -> dict[str, object]:
    """Ingest official CPI/PPI only; default to the latest two complete months."""
    started = time.monotonic()
    batch = ingest_batch_id or _new_ingest_batch_id()
    effective_date = reference_date or date.today()
    settings = get_settings()
    db_file = Path(settings.duckdb_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)
    governance_path = Path(settings.governance_path)
    governance_path.mkdir(parents=True, exist_ok=True)
    try:
        resolved_source_ip = (
            resolve_vendor_source_ip(source_ip) if source_ip is not None else None
        )
        with acquire_lock(resolve_duckdb_writer_lock(db_file), base_dir=db_file.parent):
            conn = duckdb.connect(str(db_file), read_only=False)
            try:
                apply_pending_migrations_on_connection(conn)
                raw_zone = RawZoneRepository()
                service = NbsInflationReleaseIngestService(
                    adapter=NbsInflationReleaseAdapter(source_ip=resolved_source_ip),
                    raw_zone_repo=raw_zone,
                    catalog_repo=ExternalDataCatalogRepository(conn=conn),
                    manifest_repo=SourceManifestRepository(
                        governance_repo=GovernanceRepository(base_dir=governance_path)
                    ),
                    etl_service=ExternalStdMacroEtlService(raw_zone, conn),
                )
                with repository_task_write_scope(__name__):
                    result = service.ingest_release_month(
                        batch,
                        reference_date=effective_date,
                        reference_month=reference_month,
                    )
            finally:
                conn.close()
        return {
            **result,
            "ingest_batch_id": batch,
            "source_ip": resolved_source_ip,
            "elapsed_seconds": round(time.monotonic() - started, 3),
        }
    except NbsInflationReleaseError as exc:
        return {
            "status": "blocked",
            "ingest_batch_id": batch,
            "reference_month": reference_month,
            "source_ip": source_ip,
            "error": f"NBS inflation release blocked (error_type={type(exc).__name__}).",
            "elapsed_seconds": round(time.monotonic() - started, 3),
        }
    except Exception as exc:  # noqa: BLE001 - Vendor/ETL failures must return an error receipt and a nonzero CLI exit.
        return {
            "status": "error",
            "ingest_batch_id": batch,
            "reference_month": reference_month,
            "source_ip": source_ip,
            "error": f"NBS inflation ingest failed (error_type={type(exc).__name__}).",
            "elapsed_seconds": round(time.monotonic() - started, 3),
        }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reference-month",
        default=None,
        help=(
            "Optional single release month in YYYY-MM format; omitted selects the latest "
            "two complete months."
        ),
    )
    parser.add_argument(
        "--source-ip",
        default=None,
        help="Optional local IPv4 address used for NBS HTTPS egress.",
    )
    args = parser.parse_args(argv)
    result = run_nbs_inflation_release_ingest_once(
        reference_month=args.reference_month,
        source_ip=args.source_ip,
    )
    print(json.dumps(result, ensure_ascii=False, default=str))
    return 0 if result.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
