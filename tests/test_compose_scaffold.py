from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_docker_compose_declares_phase1_services():
    compose_path = ROOT / "docker-compose.yml"
    assert compose_path.exists(), f"Missing compose file: {compose_path}"

    text = compose_path.read_text(encoding="utf-8")
    for service_name in ("api", "worker", "postgres", "redis", "minio"):
        assert f"{service_name}:" in text


def test_docker_compose_bootstraps_backend_dependencies_and_uses_container_hosts():
    compose_path = ROOT / "docker-compose.yml"
    text = compose_path.read_text(encoding="utf-8")

    assert "pip install -e ./backend" in text
    assert "python -m dramatiq --processes 1 --threads 8 backend.app.tasks.worker_bootstrap" in text
    assert (
        "postgresql://${MOSS_POSTGRES_USER:-moss}:${MOSS_POSTGRES_PASSWORD:?Set "
        "MOSS_POSTGRES_PASSWORD for docker compose}@postgres:5432/${MOSS_POSTGRES_DB:-moss}"
    ) in text
    assert "redis://redis:6379/0" in text
    assert "minio:9000" in text
    assert "MOSS_VITE_API_PROXY: http://api:8000" in text


def test_docker_compose_worker_has_one_migration_free_duckdb_writer_process():
    compose_path = ROOT / "docker-compose.yml"
    text = compose_path.read_text(encoding="utf-8")
    api_section = text.split("\n  api:\n", maxsplit=1)[1].split("\n  worker:\n", maxsplit=1)[0]
    worker_section = text.split("\n  worker:\n", maxsplit=1)[1].split("\n  postgres:\n", maxsplit=1)[0]

    assert "healthcheck:" in api_section
    assert "http://127.0.0.1:8000/health" in api_section
    assert "--processes 1" in worker_section
    assert "MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS: \"1\"" in worker_section
    assert "api:\n        condition: service_healthy" in worker_section


def test_docker_compose_requires_explicit_secret_values():
    compose_path = ROOT / "docker-compose.yml"
    text = compose_path.read_text(encoding="utf-8")

    forbidden_fragments = [
        "postgresql://moss:moss@",
        "POSTGRES_PASSWORD: moss",
        "MOSS_MINIO_ACCESS_KEY: minioadmin",
        "MOSS_MINIO_SECRET_KEY: minioadmin",
        "MINIO_ROOT_USER: minioadmin",
        "MINIO_ROOT_PASSWORD: minioadmin",
    ]
    for fragment in forbidden_fragments:
        assert fragment not in text

    assert "${MOSS_POSTGRES_PASSWORD:?Set MOSS_POSTGRES_PASSWORD for docker compose}" in text
    assert "${MOSS_MINIO_ROOT_USER:?Set MOSS_MINIO_ROOT_USER for docker compose}" in text
    assert "${MOSS_MINIO_ROOT_PASSWORD:?Set MOSS_MINIO_ROOT_PASSWORD for docker compose}" in text


def test_docker_compose_binds_infrastructure_ports_to_loopback():
    compose_path = ROOT / "docker-compose.yml"
    text = compose_path.read_text(encoding="utf-8")

    assert '"5173:5173"' not in text
    assert '"5432:5432"' not in text
    assert '"6379:6379"' not in text
    assert '"9000:9000"' not in text
    assert '"9001:9001"' not in text

    assert '"127.0.0.1:${MOSS_FRONTEND_PORT:-5173}:5173"' in text
    assert '"127.0.0.1:${MOSS_POSTGRES_PORT:-5432}:5432"' in text
    assert '"127.0.0.1:${MOSS_REDIS_PORT:-6379}:6379"' in text
    assert '"127.0.0.1:${MOSS_MINIO_PORT:-9000}:9000"' in text
    assert '"127.0.0.1:${MOSS_MINIO_CONSOLE_PORT:-9001}:9001"' in text
