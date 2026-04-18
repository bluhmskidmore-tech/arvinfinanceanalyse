from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from backend.app.governance.locks import acquire_lock
from backend.app.governance.settings import get_settings
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    CACHE_MANIFEST_STREAM,
    GovernanceRepository,
)
from backend.app.repositories.job_state_repo import JobStateRepository
from backend.app.repositories.object_store_repo import ObjectStoreRepository
from backend.app.repositories.source_manifest_repo import SourceManifestRepository
from backend.app.repositories.source_preview_repo import (
    RULE_VERSION,
    cleanup_preview_backups,
    materialize_source_previews,
    restore_preview_tables,
    snapshot_preview_tables,
)
from backend.app.services.ingest_service import IngestService
from backend.app.tasks.broker import register_actor_once
from backend.app.tasks.ingest import resolve_data_input_root
from backend.app.tasks.materialize import resolve_materialize_lock


SOURCE_PREVIEW_REFRESH_JOB_NAME = "source_preview_refresh"
SOURCE_PREVIEW_REFRESH_CACHE_KEY = "source_preview.foundation"
SOURCE_PREVIEW_REFRESH_SOURCE_FAMILIES = ("zqtz", "tyw")
logger = logging.getLogger(__name__)


def build_source_preview_refresh_lock_key(duckdb_path: str | Path) -> str:
    return resolve_materialize_lock(Path(duckdb_path)).key


def _refresh_source_preview_cache(
    duckdb_path: str | None = None,
    governance_dir: str | None = None,
    data_root: str | None = None,
    run_id: str | None = None,
    governance_sql_dsn: str | None = None,
    governance_backend_mode: str | None = None,
) -> dict[str, object]:
    settings = get_settings()
    duckdb_file = Path(duckdb_path or settings.duckdb_path)
    duckdb_file.parent.mkdir(parents=True, exist_ok=True)
    governance_path = Path(governance_dir or settings.governance_path)
    resolved_data_root = Path(data_root) if data_root is not None else resolve_data_input_root()
    governance_repo = _governance_repo(
        settings=settings,
        governance_path=governance_path,
        governance_sql_dsn=governance_sql_dsn,
        governance_backend_mode=governance_backend_mode,
    )
    materialize_lock = resolve_materialize_lock(duckdb_file)
    started_at = datetime.now(timezone.utc).isoformat()
    run_id = run_id or f"{SOURCE_PREVIEW_REFRESH_JOB_NAME}:{started_at}"
    logger.info("starting source_preview_refresh", extra={"run_id": run_id})

    governance_repo.append(
        CACHE_BUILD_RUN_STREAM,
        {
            "run_id": run_id,
            "job_name": SOURCE_PREVIEW_REFRESH_JOB_NAME,
            "status": "running",
            "cache_key": SOURCE_PREVIEW_REFRESH_CACHE_KEY,
            "lock": materialize_lock.key,
            "source_version": "sv_preview_running",
            "vendor_version": "vv_none",
            "preview_sources": list(SOURCE_PREVIEW_REFRESH_SOURCE_FAMILIES),
            "started_at": started_at,
        },
    )
    _record_job_state_transition(
        settings=settings,
        run_id=run_id,
        status="running",
        source_version="sv_preview_running",
        vendor_version="vv_none",
        started_at=started_at,
    )

    ingest_batch_id = ""
    snapshot_ready = False
    preview_summaries: list[dict[str, object]] = []

    try:
        ingest_summary = _run_source_preview_ingest(
            settings=settings,
            governance_path=governance_path,
            data_root=resolved_data_root,
            governance_sql_dsn=governance_sql_dsn,
            governance_backend_mode=governance_backend_mode,
        )
        ingest_batch_id = str(ingest_summary.get("ingest_batch_id") or "")
        selected_ingest_batch_id = ingest_batch_id or None
        with acquire_lock(materialize_lock, base_dir=duckdb_file.parent):
            snapshot_preview_tables(str(duckdb_file))
            snapshot_ready = True
            preview_summaries = materialize_source_previews(
                duckdb_path=str(duckdb_file),
                governance_dir=str(governance_path),
                ingest_batch_id=selected_ingest_batch_id,
                source_families=list(SOURCE_PREVIEW_REFRESH_SOURCE_FAMILIES),
            )
            try:
                cleanup_preview_backups(str(duckdb_file))
            except Exception:
                pass
    except Exception as exc:
        if snapshot_ready:
            try:
                restore_preview_tables(str(duckdb_file))
            finally:
                try:
                    cleanup_preview_backups(str(duckdb_file))
                except Exception:
                    pass

        logger.error("task failed: %s", exc, exc_info=True)
        governance_repo.append(
            CACHE_BUILD_RUN_STREAM,
            {
                "run_id": run_id,
                "job_name": SOURCE_PREVIEW_REFRESH_JOB_NAME,
                "status": "failed",
                "cache_key": SOURCE_PREVIEW_REFRESH_CACHE_KEY,
                "lock": materialize_lock.key,
                "source_version": "sv_preview_failed",
                "vendor_version": "vv_none",
                "preview_sources": list(SOURCE_PREVIEW_REFRESH_SOURCE_FAMILIES),
                "ingest_batch_id": ingest_batch_id or None,
                "error_message": str(exc),
                "finished_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        _record_job_state_transition(
            settings=settings,
            run_id=run_id,
            status="failed",
            source_version="sv_preview_failed",
            vendor_version="vv_none",
            error_message=str(exc),
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
        raise

    preview_sources = [str(summary["source_family"]) for summary in preview_summaries]
    report_dates = sorted(
        {
            str(summary["report_date"])
            for summary in preview_summaries
            if str(summary.get("report_date") or "").strip()
        }
    )
    source_version = _join_source_versions(summary["source_version"] for summary in preview_summaries)
    finished_at = datetime.now(timezone.utc).isoformat()

    governance_repo.append_many_atomic(
        [
            (
                CACHE_MANIFEST_STREAM,
                {
                    "cache_key": SOURCE_PREVIEW_REFRESH_CACHE_KEY,
                    "source_version": source_version,
                    "vendor_version": "vv_none",
                    "rule_version": RULE_VERSION,
                },
            ),
            (
                CACHE_BUILD_RUN_STREAM,
                {
                    "run_id": run_id,
                    "job_name": SOURCE_PREVIEW_REFRESH_JOB_NAME,
                    "status": "completed",
                    "cache_key": SOURCE_PREVIEW_REFRESH_CACHE_KEY,
                    "lock": materialize_lock.key,
                    "source_version": source_version,
                    "vendor_version": "vv_none",
                    "preview_sources": preview_sources,
                    "ingest_batch_id": ingest_batch_id or None,
                    "report_dates": report_dates,
                    "rule_version": RULE_VERSION,
                    "finished_at": finished_at,
                },
            ),
        ]
    )
    _record_job_state_transition(
        settings=settings,
        run_id=run_id,
        status="completed",
        source_version=source_version,
        vendor_version="vv_none",
        finished_at=finished_at,
    )

    logger.info("completed source_preview_refresh", extra={"run_id": run_id, "preview_sources": preview_sources})
    return {
        "status": "completed",
        "run_id": run_id,
        "job_name": SOURCE_PREVIEW_REFRESH_JOB_NAME,
        "lock": materialize_lock.key,
        "cache_key": SOURCE_PREVIEW_REFRESH_CACHE_KEY,
        "preview_sources": preview_sources,
        "ingest_batch_id": ingest_batch_id or None,
        "report_dates": report_dates,
        "rule_version": RULE_VERSION,
        "source_version": source_version,
        "vendor_version": "vv_none",
    }


def _run_source_preview_ingest(
    *,
    settings,
    governance_path: Path,
    data_root: Path,
    governance_sql_dsn: str | None = None,
    governance_backend_mode: str | None = None,
) -> dict[str, object]:
    service = IngestService(
        data_root=data_root,
        manifest_repo=SourceManifestRepository(
            governance_repo=_governance_repo(
                settings=settings,
                governance_path=governance_path,
                governance_sql_dsn=governance_sql_dsn,
                governance_backend_mode=governance_backend_mode,
            ),
        ),
        object_store_repo=ObjectStoreRepository(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            bucket=settings.minio_bucket,
            mode=settings.object_store_mode,
            local_archive_path=str(settings.local_archive_path),
        ),
    )
    service.source_family_allowlist = set(SOURCE_PREVIEW_REFRESH_SOURCE_FAMILIES)
    return service.run().model_dump(mode="json")


def _join_source_versions(versions) -> str:
    ordered: list[str] = []
    seen: set[str] = set()
    for version in versions:
        normalized = str(version or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    if not ordered:
        return "sv_preview_empty"
    return "__".join(ordered)


refresh_source_preview_cache = register_actor_once(
    "refresh_source_preview_cache",
    _refresh_source_preview_cache,
)


def _record_job_state_transition(
    *,
    settings,
    run_id: str,
    status: str,
    source_version: str,
    vendor_version: str,
    started_at: str | None = None,
    finished_at: str | None = None,
    error_message: str | None = None,
) -> None:
    if not str(getattr(settings, "job_state_dsn", "") or "").strip():
        return
    JobStateRepository(settings.job_state_dsn).record_transition(
        run_id=run_id,
        job_name=SOURCE_PREVIEW_REFRESH_JOB_NAME,
        cache_key=SOURCE_PREVIEW_REFRESH_CACHE_KEY,
        status=status,
        report_date=None,
        source_version=source_version,
        vendor_version=vendor_version,
        started_at=started_at,
        finished_at=finished_at,
        error_message=error_message,
    )


def _governance_repo(
    *,
    settings,
    governance_path: Path,
    governance_sql_dsn: str | None = None,
    governance_backend_mode: str | None = None,
) -> GovernanceRepository:
    return GovernanceRepository(
        base_dir=governance_path,
        sql_dsn=governance_sql_dsn
        if governance_sql_dsn is not None
        else getattr(settings, "governance_sql_dsn", ""),
        backend_mode=governance_backend_mode
        if governance_backend_mode is not None
        else getattr(settings, "source_preview_governance_backend", "jsonl"),
    )
