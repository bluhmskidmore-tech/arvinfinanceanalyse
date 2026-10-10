import json

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


def test_ready_endpoint_returns_503_when_a_dependency_is_degraded(
    monkeypatch: pytest.MonkeyPatch,
):
    """降级必须体现在状态码上：外部探活只看 HTTP 状态，不会解析 body。"""
    health_module = load_module(
        "backend.app.api.routes.health",
        "backend/app/api/routes/health.py",
    )

    degraded_payload = {
        "status": "degraded",
        "checks": {
            "postgresql": {"ok": True},
            "duckdb": {"ok": False, "error": "database is locked"},
            "redis": {"ok": True},
            "object_store": {"ok": True},
        },
    }
    monkeypatch.setattr(health_module, "get_settings", lambda: object())
    monkeypatch.setattr(
        health_module,
        "ready_health_payload",
        lambda _settings: degraded_payload,
    )

    app = FastAPI()
    app.include_router(health_module.router)
    client = TestClient(app)

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == degraded_payload


def test_ready_health_payload_keeps_prewarm_out_of_dependency_status(
    monkeypatch: pytest.MonkeyPatch,
):
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
    assert payload["checks"]["home_snapshot_prewarm"] == {
        "ok": False,
        "status": "warming",
    }


def test_ready_health_payload_exposes_only_non_topology_status_fields(
    monkeypatch: pytest.MonkeyPatch,
):
    health_service = load_module(
        "backend.app.services.health_service",
        "backend/app/services/health_service.py",
    )
    object_store_diagnostics = {
        "ok": False,
        "mode": "minio",
        "endpoint": "minio:9000",
        "bucket": "artifacts",
        "tcp_reachable": True,
        "read_write_supported": False,
        "error": "MinIO object-store read/write operations are not implemented.",
    }

    class PostgresRepo:
        def __init__(self, *args, **kwargs):
            pass

        def healthcheck(self) -> dict[str, object]:
            return {
                "ok": True,
                "dsn": "postgresql://u:***@db.internal:5432/app",
                "driver": "psycopg",
                "can_connect": True,
                "sql_roundtrip": True,
                "bootstrap_visible": True,
                "missing_tables": [],
                "error": None,
            }

    class DuckDBRepo:
        def __init__(self, *args, **kwargs):
            pass

        def healthcheck(self) -> dict[str, object]:
            return {
                "ok": True,
                "mode": "read_only",
                "path": "C:/internal/data/moss.duckdb",
                "can_connect": True,
                "sql_roundtrip": True,
            }

    class RedisRepo:
        def __init__(self, *args, **kwargs):
            pass

        def healthcheck(self) -> dict[str, object]:
            return {"ok": True, "dsn": "redis://cache.internal:6379/0"}

    class ReachableUnsupportedObjectStoreRepo:
        def __init__(self, *args, **kwargs):
            pass

        def healthcheck(self) -> dict[str, object]:
            return object_store_diagnostics

    monkeypatch.setattr(health_service, "PostgresRepository", PostgresRepo)
    monkeypatch.setattr(health_service, "DuckDBRepository", DuckDBRepo)
    monkeypatch.setattr(health_service, "RedisRepository", RedisRepo)
    monkeypatch.setattr(
        health_service,
        "ObjectStoreRepository",
        ReachableUnsupportedObjectStoreRepo,
    )
    monkeypatch.setattr(
        health_service,
        "home_snapshot_prewarm_status",
        lambda: {
            "ok": True,
            "status": "ready",
            "report_date": "2026-08-26",
            "last_step_durations_ms": {"load_internal_snapshot": 12.0},
            "error": None,
        },
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
            "object_store_mode": "minio",
            "local_archive_path": "/tmp/archive",
        },
    )()

    payload = health_service.ready_health_payload(settings)

    assert payload["status"] == "degraded"
    assert payload["checks"] == {
        "postgresql": {
            "ok": True,
            "can_connect": True,
            "sql_roundtrip": True,
            "bootstrap_visible": True,
        },
        "duckdb": {
            "ok": True,
            "can_connect": True,
            "sql_roundtrip": True,
        },
        "redis": {"ok": True},
        "object_store": {
            "ok": False,
            "mode": "minio",
            "tcp_reachable": True,
            "read_write_supported": False,
        },
        "home_snapshot_prewarm": {"ok": True, "status": "ready"},
    }


def test_ready_health_payload_omits_storage_topology_and_raw_diagnostics(tmp_path):
    """就绪探针只返回状态，不暴露 DSN、存储路径、端点、桶名或异常原文。"""
    from backend.app.governance.settings import Settings

    health_service = load_module(
        "backend.app.services.health_service",
        "backend/app/services/health_service.py",
    )

    missing_duckdb_path = tmp_path / "missing.duckdb"
    unreachable_postgres_dsn = "postgresql://probe:probe@127.0.0.1:1/moss-probe-db"
    settings = Settings(
        environment="production",
        postgres_dsn=unreachable_postgres_dsn,
        duckdb_path=str(missing_duckdb_path),
        redis_dsn="redis://127.0.0.1:1/0",
        object_store_mode="local",
        local_archive_path=str(tmp_path / "archive"),
        _env_file=None,
    )

    payload = health_service.ready_health_payload(settings)
    body_text = json.dumps(payload)

    assert payload["status"] == "degraded"
    duckdb_check = payload["checks"]["duckdb"]
    postgres_check = payload["checks"]["postgresql"]
    redis_check = payload["checks"]["redis"]
    object_store_check = payload["checks"]["object_store"]
    assert duckdb_check["ok"] is False
    assert "path" not in duckdb_check
    assert postgres_check["ok"] is False
    assert "dsn" not in postgres_check
    assert "error" not in postgres_check
    assert "dsn" not in redis_check
    assert "path" not in object_store_check
    assert "endpoint" not in object_store_check
    assert "bucket" not in object_store_check
    assert "error" not in object_store_check
    assert str(missing_duckdb_path) not in body_text
    assert "127.0.0.1" not in body_text
    assert "moss-probe-db" not in body_text
    assert str(tmp_path / "archive") not in body_text
    assert "ConnectionRefusedError" not in body_text
    assert "OperationalError" not in body_text


def test_ready_endpoint_response_body_excludes_sensitive_check_details(monkeypatch: pytest.MonkeyPatch, tmp_path):
    """端到端：真实 /health/ready 响应也不携带内部存储拓扑。"""
    from backend.app.governance.settings import Settings

    health_module = load_module(
        "backend.app.api.routes.health",
        "backend/app/api/routes/health.py",
    )

    missing_duckdb_path = tmp_path / "missing.duckdb"
    settings = Settings(
        environment="production",
        postgres_dsn="postgresql://probe:probe@127.0.0.1:1/moss-probe-db",
        duckdb_path=str(missing_duckdb_path),
        redis_dsn="redis://127.0.0.1:1/0",
        object_store_mode="local",
        local_archive_path=str(tmp_path / "archive"),
        _env_file=None,
    )
    monkeypatch.setattr(health_module, "get_settings", lambda: settings)

    app = FastAPI()
    app.include_router(health_module.router)
    client = TestClient(app)

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert str(missing_duckdb_path) not in response.text
    payload = response.json()
    assert "path" not in payload["checks"]["duckdb"]
    assert "dsn" not in payload["checks"]["postgresql"]
    assert "error" not in payload["checks"]["postgresql"]
    assert "dsn" not in payload["checks"]["redis"]
    assert "path" not in payload["checks"]["object_store"]
    assert "endpoint" not in payload["checks"]["object_store"]
    assert "bucket" not in payload["checks"]["object_store"]
    assert "error" not in payload["checks"]["object_store"]
