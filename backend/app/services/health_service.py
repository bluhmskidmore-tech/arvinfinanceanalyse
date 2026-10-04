from __future__ import annotations

import logging

from backend.app.governance.settings import Settings
from backend.app.repositories.duckdb_repo import DuckDBRepository
from backend.app.repositories.object_store_repo import ObjectStoreRepository
from backend.app.repositories.postgres_repo import PostgresRepository
from backend.app.repositories.redis_repo import RedisRepository
from backend.app.services.executive_service import home_snapshot_prewarm_status

logger = logging.getLogger(__name__)

# The readiness route is unauthenticated, so expose only status-level fields.
# An allowlist is deliberate: repository health checks may gain new diagnostic
# fields over time, and those fields must not become public by default.
_READY_CHECK_PUBLIC_FIELDS: dict[str, tuple[str, ...]] = {
    "postgresql": ("ok", "can_connect", "sql_roundtrip", "bootstrap_visible"),
    "duckdb": ("ok", "can_connect", "sql_roundtrip"),
    "redis": ("ok",),
    "object_store": ("ok", "mode", "tcp_reachable", "read_write_supported"),
    "home_snapshot_prewarm": ("ok", "status"),
}


def _sanitize_ready_check(component: str, result: object) -> object:
    if not isinstance(result, dict):
        return result
    public_fields = _READY_CHECK_PUBLIC_FIELDS.get(component, ("ok", "status"))
    sanitized = {field: result[field] for field in public_fields if field in result}
    suppressed_fields = tuple(sorted(set(result).difference(sanitized)))
    if suppressed_fields:
        logger.info(
            "/health/ready %s check fields suppressed from response body: %s",
            component,
            ", ".join(suppressed_fields),
        )
    return sanitized


def ready_health_payload(settings: Settings) -> dict[str, object]:
    raw_checks = {
        "postgresql": PostgresRepository(settings.postgres_dsn).healthcheck(),
        "duckdb": DuckDBRepository(settings.duckdb_path).healthcheck(),
        "redis": RedisRepository(settings.redis_dsn).healthcheck(),
        "object_store": ObjectStoreRepository(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            bucket=settings.minio_bucket,
            mode=settings.object_store_mode,
            local_archive_path=str(settings.local_archive_path),
        ).healthcheck(),
        "home_snapshot_prewarm": home_snapshot_prewarm_status(),
    }
    checks = {
        component: _sanitize_ready_check(component, result) for component, result in raw_checks.items()
    }
    dependency_checks = {
        key: value
        for key, value in checks.items()
        if key != "home_snapshot_prewarm"
    }
    overall = "ok" if all(
        item["ok"] if isinstance(item, dict) else False
        for item in dependency_checks.values()
    ) else "degraded"
    return {"status": overall, "checks": checks}
