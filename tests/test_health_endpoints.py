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
        "backend.app.api.routes.health",
        "backend/app/api/routes/health.py",
    )

    monkeypatch.setattr(
        health_module,
        "get_settings",
        lambda: object(),
    )
    monkeypatch.setattr(
        health_module,
        "ready_health_payload",
        lambda _settings: {
            "status": "ok",
            "checks": {
                "postgresql": {"ok": True},
                "duckdb": {"ok": True},
                "redis": {"ok": True},
                "object_store": {"ok": True},
                "home_snapshot_prewarm": {
                    "ok": False,
                    "status": "warming",
                    "report_date": None,
                    "allow_partial": False,
                    "last_duration_ms": None,
                    "last_step_durations_ms": {},
                    "error": None,
                },
            },
        },
    )

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
            "home_snapshot_prewarm": {
                "ok": False,
                "status": "warming",
                "report_date": None,
                "allow_partial": False,
                "last_duration_ms": None,
                "last_step_durations_ms": {},
                "error": None,
            },
        },
    }


def test_ready_health_payload_keeps_prewarm_out_of_dependency_status(monkeypatch: pytest.MonkeyPatch):
    health_service = load_module(
        "backend.app.services.health_service",
        "backend/app/services/health_service.py",
    )

    class FakeRepo:
        def __init__(self, *args, **kwargs):
            pass

        def healthcheck(self) -> dict[str, object]:
            return {"ok": True}

    monkeypatch.setattr(health_service, "PostgresRepository", FakeRepo)
    monkeypatch.setattr(health_service, "DuckDBRepository", FakeRepo)
    monkeypatch.setattr(health_service, "RedisRepository", FakeRepo)
    monkeypatch.setattr(health_service, "ObjectStoreRepository", FakeRepo)
    monkeypatch.setattr(
        health_service,
        "home_snapshot_prewarm_status",
        lambda: {"ok": False, "status": "warming"},
    )
    settings = type(
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
    )()

    payload = health_service.ready_health_payload(settings)

    assert payload["status"] == "ok"
    assert payload["checks"]["home_snapshot_prewarm"] == {"ok": False, "status": "warming"}
