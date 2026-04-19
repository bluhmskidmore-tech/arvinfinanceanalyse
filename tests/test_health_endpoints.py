import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.helpers import load_module


def test_fastapi_application_exposes_live_and_ready_health_routes():
    module = load_module("backend.app.main", "backend/app/main.py")
    app = getattr(module, "app", None)
    if app is None:
        pytest.fail("backend.app.main must expose a module-level 'app'")

    paths = {route.path for route in app.routes}
    assert "/health" in paths
    assert "/health/live" in paths
    assert "/health/ready" in paths


def test_ready_endpoint_returns_200_and_check_payload(monkeypatch: pytest.MonkeyPatch):
    health_module = load_module(
        "backend.app.api.routes.health_contract",
        "backend/app/api/routes/health.py",
    )

    class FakeRepo:
        def __init__(self, *args, **kwargs):
            pass

        def healthcheck(self) -> dict[str, object]:
            return {"ok": True}

    monkeypatch.setattr(
        health_module,
        "get_settings",
        lambda: type(
            "Settings",
            (),
            {
                "postgres_dsn": "postgresql://u:p@db/app",
                "duckdb_path": "/tmp/app.duckdb",
                "redis_dsn": "redis://cache:6379/0",
                "minio_endpoint": "minio:9000",
                "minio_access_key": "minio",
                "minio_secret_key": "minio",
                "minio_bucket": "artifacts",
                "object_store_mode": "local",
                "local_archive_path": "/tmp/archive",
            },
        )(),
    )
    monkeypatch.setattr(health_module, "PostgresRepository", FakeRepo)
    monkeypatch.setattr(health_module, "DuckDBRepository", FakeRepo)
    monkeypatch.setattr(health_module, "RedisRepository", FakeRepo)
    monkeypatch.setattr(health_module, "ObjectStoreRepository", FakeRepo)

    app = FastAPI()
    app.include_router(health_module.router)
    client = TestClient(app)

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "checks": {
            "postgresql": {"ok": True},
            "duckdb": {"ok": True},
            "redis": {"ok": True},
            "object_store": {"ok": True},
        },
    }
