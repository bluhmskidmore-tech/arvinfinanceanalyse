from fastapi import APIRouter

from backend.app.governance.settings import get_settings
from backend.app.repositories.duckdb_repo import DuckDBRepository
from backend.app.repositories.object_store_repo import ObjectStoreRepository
from backend.app.repositories.postgres_repo import PostgresRepository
from backend.app.repositories.redis_repo import RedisRepository

router = APIRouter(prefix="/health")


@router.get("/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def ready() -> dict[str, object]:
    settings = get_settings()
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
    }
    overall = "ok" if all(item["ok"] for item in checks.values()) else "degraded"
    return {"status": overall, "checks": checks}
