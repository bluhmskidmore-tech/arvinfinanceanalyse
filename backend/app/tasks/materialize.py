import duckdb
import os
import hashlib
import sys
from importlib import import_module
from pathlib import Path

from backend.app.repositories.duckdb_migrations import apply_pending_migrations_on_connection
from backend.app.governance.locks import LockDefinition, MATERIALIZE_LOCK, acquire_lock
from backend.app.governance.settings import get_settings
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    CACHE_MANIFEST_STREAM,
    GovernanceRepository,
)
from backend.app.schemas.materialize import (
    CacheBuildRunRecord,
    CacheManifestRecord,
    MaterializeBuildPayload,
)
from backend.app.tasks.broker import register_actor_once
from backend.app.tasks.build_runs import BuildRunRecord


def resolve_data_input_root() -> Path:
    configured_root = os.getenv("MOSS_DATA_INPUT_ROOT")
    if configured_root:
        return Path(configured_root).expanduser()
    return Path(get_settings().data_input_root).expanduser()


def resolve_materialize_lock(duckdb_file: Path) -> LockDefinition:
    canonical_path = os.path.normcase(str(duckdb_file.resolve()))
    digest = hashlib.sha256(canonical_path.encode("utf-8")).hexdigest()[:12]
    return LockDefinition(
        key=f"{MATERIALIZE_LOCK.key}:{digest}",
        ttl_seconds=MATERIALIZE_LOCK.ttl_seconds,
    )


def _source_preview_repo():
    return import_module("backend.app.repositories.source_preview_repo")


def snapshot_preview_tables(*args, **kwargs):
    return _source_preview_repo().snapshot_preview_tables(*args, **kwargs)


def materialize_source_previews(*args, **kwargs):
    return _source_preview_repo().materialize_source_previews(*args, **kwargs)


def restore_preview_tables(*args, **kwargs):
    return _source_preview_repo().restore_preview_tables(*args, **kwargs)


def cleanup_preview_backups(*args, **kwargs):
    return _source_preview_repo().cleanup_preview_backups(*args, **kwargs)


def ensure_phase1_materialize_runs_table(conn: duckdb.DuckDBPyConnection) -> None:
    """Baseline DDL is versioned in `duckdb_migrations` (also run at API/worker startup)."""
    apply_pending_migrations_on_connection(conn)


def _materialize_cache_view(
    duckdb_path: str | None = None,
    governance_dir: str | None = None,
    data_root: str | None = None,
    ingest_batch_id: str | None = None,
) -> dict[str, object]:
    """Single write entrypoint for preview materialize work."""
    settings = get_settings()
    duckdb_file = Path(duckdb_path or settings.duckdb_path)
    duckdb_file.parent.mkdir(parents=True, exist_ok=True)
    governance_path = Path(governance_dir or settings.governance_path)
    resolved_data_root = Path(data_root) if data_root is not None else resolve_data_input_root()
    run = BuildRunRecord(job_name="materialize", status="running")
    run_id = f"{run.job_name}:{run.created_at}"
    source_version = "sv_preview_empty"
    vendor_version = "vv_none"
    materialize_lock = resolve_materialize_lock(duckdb_file)

    with acquire_lock(materialize_lock, base_dir=duckdb_file.parent):
        repo = GovernanceRepository(base_dir=governance_path)
        conn = duckdb.connect(str(duckdb_file), read_only=False)
        snapshot_ready = False
        try:
            ensure_phase1_materialize_runs_table(conn)
            conn.execute(
                "insert into phase1_materialize_runs values (?, ?, ?)",
                [run_id, run.cache_key, "running"],
            )

            try:
                snapshot_preview_tables(str(duckdb_file))
                snapshot_ready = True
                preview_summaries = materialize_source_previews(
                    duckdb_path=str(duckdb_file),
                    governance_dir=str(governance_path),
                    data_root=str(resolved_data_root),
                    ingest_batch_id=ingest_batch_id,
                )
                source_version = "__".join(
                    str(summary["source_version"])
                    for summary in preview_summaries
                ) or "sv_preview_empty"

                conn.execute(
                    "update phase1_materialize_runs set status = ? where run_id = ?",
                    ["completed", run_id],
                )

                build_run = CacheBuildRunRecord(
                    run_id=run_id,
                    job_name=run.job_name,
                    status="completed",
                    cache_key=run.cache_key,
                    lock=materialize_lock.key,
                    source_version=source_version,
                    vendor_version=vendor_version,
                )
                cache_manifest = CacheManifestRecord(
                    cache_key=run.cache_key,
                    source_version=source_version,
                    vendor_version=vendor_version,
                    rule_version=_source_preview_repo().RULE_VERSION,
                )
                repo.append_many_atomic(
                    [
                        (CACHE_BUILD_RUN_STREAM, build_run.model_dump()),
                        (CACHE_MANIFEST_STREAM, cache_manifest.model_dump()),
                    ]
                )
                try:
                    cleanup_preview_backups(str(duckdb_file))
                except Exception:
                    pass

                return MaterializeBuildPayload(
                    status="completed",
                    lock=materialize_lock.key,
                    cache_key=run.cache_key,
                    run_id=run_id,
                    preview_sources=[str(summary["source_family"]) for summary in preview_summaries],
                    vendor_version=vendor_version,
                ).model_dump()
            except Exception:
                original_error = sys.exc_info()[1]
                conn.execute(
                    "update phase1_materialize_runs set status = ? where run_id = ?",
                    ["failed", run_id],
                )
                failed_run = CacheBuildRunRecord(
                    run_id=run_id,
                    job_name=run.job_name,
                    status="failed",
                    cache_key=run.cache_key,
                    lock=materialize_lock.key,
                    source_version=source_version,
                    vendor_version=vendor_version,
                )
                append_error: Exception | None = None
                try:
                    repo.append(CACHE_BUILD_RUN_STREAM, failed_run.model_dump())
                except Exception as exc:
                    append_error = exc
                if snapshot_ready:
                    try:
                        restore_preview_tables(str(duckdb_file))
                    except Exception as restore_error:
                        raise RuntimeError("Failed to restore preview tables after materialize error") from restore_error
                    try:
                        cleanup_preview_backups(str(duckdb_file))
                    except Exception:
                        pass
                if append_error is not None:
                    raise RuntimeError("Failed to append failed materialize lineage") from append_error
                raise original_error
        finally:
            conn.close()


materialize_cache_view = register_actor_once("materialize_cache_view", _materialize_cache_view)
