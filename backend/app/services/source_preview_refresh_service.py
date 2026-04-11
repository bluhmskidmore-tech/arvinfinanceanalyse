from __future__ import annotations

from datetime import datetime, timezone

from backend.app.governance.locks import LockDefinition, acquire_lock
from backend.app.governance.settings import Settings
from backend.app.repositories.governance_repo import CACHE_BUILD_RUN_STREAM, GovernanceRepository
from backend.app.repositories.job_state_repo import JobStateRepository
from backend.app.tasks.source_preview_refresh import (
    SOURCE_PREVIEW_REFRESH_CACHE_KEY,
    SOURCE_PREVIEW_REFRESH_JOB_NAME,
    SOURCE_PREVIEW_REFRESH_SOURCE_FAMILIES,
    build_source_preview_refresh_lock_key,
    refresh_source_preview_cache,
)


IN_FLIGHT_STATUSES = {"queued", "running"}
SAFE_SYNC_FALLBACK_MESSAGES = ("queue disabled", "broker unavailable")
SAFE_SYNC_FALLBACK_EXCEPTIONS = (ConnectionError, OSError, TimeoutError)


class SourcePreviewRefreshServiceError(RuntimeError):
    pass


class SourcePreviewRefreshConflictError(RuntimeError):
    pass


def refresh_source_preview(settings: Settings) -> dict[str, object]:
    try:
        with acquire_lock(
            _refresh_trigger_lock(settings),
            base_dir=settings.governance_path,
            timeout_seconds=0.1,
        ):
            existing = _latest_inflight_refresh(settings)
            if existing is not None:
                raise SourcePreviewRefreshConflictError(
                    "Source preview refresh already in progress."
                )

            run_id = _build_run_id()
            lock_key = build_source_preview_refresh_lock_key(settings.duckdb_path)
            preview_sources = list(SOURCE_PREVIEW_REFRESH_SOURCE_FAMILIES)
            GovernanceRepository(base_dir=settings.governance_path).append(
                CACHE_BUILD_RUN_STREAM,
                {
                    "run_id": run_id,
                    "job_name": SOURCE_PREVIEW_REFRESH_JOB_NAME,
                    "status": "queued",
                    "cache_key": SOURCE_PREVIEW_REFRESH_CACHE_KEY,
                    "lock": lock_key,
                    "source_version": "sv_preview_pending",
                    "vendor_version": "vv_none",
                    "preview_sources": preview_sources,
                },
            )
            _record_job_state_transition(
                settings=settings,
                run_id=run_id,
                status="queued",
                source_version="sv_preview_pending",
                vendor_version="vv_none",
                queued_at=datetime.now(timezone.utc).isoformat(),
            )

            actor_kwargs = {
                "duckdb_path": str(settings.duckdb_path),
                "governance_dir": str(settings.governance_path),
            }
            try:
                refresh_source_preview_cache.send(run_id=run_id, **actor_kwargs)
                return {
                    "status": "queued",
                    "run_id": run_id,
                    "job_name": SOURCE_PREVIEW_REFRESH_JOB_NAME,
                    "trigger_mode": "async",
                    "cache_key": SOURCE_PREVIEW_REFRESH_CACHE_KEY,
                    "preview_sources": preview_sources,
                }
            except Exception as exc:
                if _should_use_sync_fallback(settings, exc):
                    try:
                        payload = refresh_source_preview_cache.fn(
                            run_id=run_id,
                            **actor_kwargs,
                        )
                    except Exception as fallback_exc:
                        raise SourcePreviewRefreshServiceError(
                            "Source preview refresh failed during sync fallback."
                        ) from fallback_exc
                    return {
                        **payload,
                        "job_name": SOURCE_PREVIEW_REFRESH_JOB_NAME,
                        "trigger_mode": "sync-fallback",
                    }

                _record_dispatch_failure(
                    settings=settings,
                    run_id=run_id,
                    lock_key=lock_key,
                    error_message="Source preview refresh queue dispatch failed.",
                )
                raise SourcePreviewRefreshServiceError(
                    "Source preview refresh queue dispatch failed."
                ) from exc
    except TimeoutError as exc:
        raise SourcePreviewRefreshConflictError(
            "Source preview refresh already in progress."
        ) from exc


def source_preview_refresh_status(
    settings: Settings,
    *,
    run_id: str | None = None,
) -> dict[str, object]:
    records = _load_source_preview_refresh_records(settings)
    if run_id is not None:
        records = [record for record in records if str(record.get("run_id")) == run_id]
        if not records:
            raise ValueError(f"Unknown source preview refresh run_id={run_id}")
    if not records:
        return {
            "status": "idle",
            "job_name": SOURCE_PREVIEW_REFRESH_JOB_NAME,
            "cache_key": SOURCE_PREVIEW_REFRESH_CACHE_KEY,
            "trigger_mode": "idle",
            "preview_sources": list(SOURCE_PREVIEW_REFRESH_SOURCE_FAMILIES),
        }

    latest = records[-1]
    status = str(latest.get("status", "unknown"))
    return {
        **latest,
        "trigger_mode": "async" if status in {"queued", "running"} else "terminal",
    }


def _build_run_id() -> str:
    return f"{SOURCE_PREVIEW_REFRESH_JOB_NAME}:{datetime.now(timezone.utc).isoformat()}"


def _refresh_trigger_lock(settings: Settings) -> LockDefinition:
    return LockDefinition(
        key=f"{build_source_preview_refresh_lock_key(settings.duckdb_path)}:trigger",
        ttl_seconds=30,
    )


def _latest_inflight_refresh(settings: Settings) -> dict[str, object] | None:
    by_run_id: dict[str, dict[str, object]] = {}
    for record in _load_source_preview_refresh_records(settings):
        by_run_id[str(record.get("run_id"))] = record
    for record in reversed(list(by_run_id.values())):
        if str(record.get("status")) in IN_FLIGHT_STATUSES:
            return record
    return None


def _record_dispatch_failure(
    *,
    settings: Settings,
    run_id: str,
    lock_key: str,
    error_message: str,
) -> None:
    GovernanceRepository(base_dir=settings.governance_path).append(
        CACHE_BUILD_RUN_STREAM,
        {
            "run_id": run_id,
            "job_name": SOURCE_PREVIEW_REFRESH_JOB_NAME,
            "status": "failed",
            "cache_key": SOURCE_PREVIEW_REFRESH_CACHE_KEY,
            "lock": lock_key,
            "source_version": "sv_preview_failed",
            "vendor_version": "vv_none",
            "preview_sources": list(SOURCE_PREVIEW_REFRESH_SOURCE_FAMILIES),
            "error_message": error_message,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    _record_job_state_transition(
        settings=settings,
        run_id=run_id,
        status="failed",
        source_version="sv_preview_failed",
        vendor_version="vv_none",
        error_message=error_message,
        finished_at=datetime.now(timezone.utc).isoformat(),
    )


def _should_use_sync_fallback(settings: Settings, exc: Exception) -> bool:
    if str(settings.environment).lower() == "production":
        return False
    if isinstance(exc, SAFE_SYNC_FALLBACK_EXCEPTIONS):
        return True
    message = str(exc).lower()
    return any(marker in message for marker in SAFE_SYNC_FALLBACK_MESSAGES)


def _load_source_preview_refresh_records(settings: Settings) -> list[dict[str, object]]:
    return [
        record
        for record in GovernanceRepository(base_dir=settings.governance_path).read_all(
            CACHE_BUILD_RUN_STREAM
        )
        if str(record.get("cache_key")) == SOURCE_PREVIEW_REFRESH_CACHE_KEY
        and str(record.get("job_name")) == SOURCE_PREVIEW_REFRESH_JOB_NAME
    ]


def _record_job_state_transition(
    *,
    settings: Settings,
    run_id: str,
    status: str,
    source_version: str,
    vendor_version: str,
    queued_at: str | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
    error_message: str | None = None,
) -> None:
    if not str(settings.job_state_dsn or "").strip():
        return
    JobStateRepository(settings.job_state_dsn).record_transition(
        run_id=run_id,
        job_name=SOURCE_PREVIEW_REFRESH_JOB_NAME,
        cache_key=SOURCE_PREVIEW_REFRESH_CACHE_KEY,
        status=status,
        report_date=None,
        source_version=source_version,
        vendor_version=vendor_version,
        queued_at=queued_at,
        started_at=started_at,
        finished_at=finished_at,
        error_message=error_message,
    )
