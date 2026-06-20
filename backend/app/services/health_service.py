from __future__ import annotations

from backend.app.governance.settings import Settings
from backend.app.repositories.duckdb_repo import DuckDBRepository
from backend.app.repositories.object_store_repo import ObjectStoreRepository
from backend.app.repositories.postgres_repo import PostgresRepository
from backend.app.repositories.redis_repo import RedisRepository
from backend.app.services.executive_service import home_snapshot_prewarm_status


def ready_health_payload(settings: Settings) -> dict[str, object]:
    checks = {
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
    dependency_checks = {
        key: value
        for key, value in checks.items()
        if key != "home_snapshot_prewarm"
    }
    overall = "ok" if all(item["ok"] for item in dependency_checks.values()) else "degraded"
    return {"status": overall, "checks": checks}
