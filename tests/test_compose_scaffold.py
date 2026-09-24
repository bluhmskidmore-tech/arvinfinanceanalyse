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

    # 容器安装必须走 backend/uv.lock 的冻结闭包：`uv export --frozen` + `--no-deps`
    # 安装，缺任何一段都会退回"容器内二次解析"，装出的版本与 OSV 扫描对象脱钩。
    assert "uv export --frozen --project backend" in text
    assert "uv pip install --system --no-deps -r /tmp/backend-requirements.txt" in text
    assert "uv pip install --system --no-deps -e ./backend" in text
    assert "pip install -e ./backend[dev]" not in text
    assert "python -m dramatiq --processes 1 --threads 8 backend.app.tasks.worker_bootstrap" in text
    assert (
        "postgresql://${MOSS_POSTGRES_USER:-moss}:${MOSS_POSTGRES_PASSWORD:?Set "
        "MOSS_POSTGRES_PASSWORD for docker compose}@postgres:5432/${MOSS_POSTGRES_DB:-moss}"
    ) in text
    assert "redis://redis:6379/0" in text
    assert "minio:9000" in text
    assert "MOSS_VITE_API_PROXY: http://api:8000" in text


def test_docker_compose_bootstraps_frontend_dependencies_in_a_container_volume():
    compose_path = ROOT / "docker-compose.yml"
    text = compose_path.read_text(encoding="utf-8")
    frontend_section = text.split("\n  frontend:\n", maxsplit=1)[1].split(
        "\nvolumes:\n", maxsplit=1
    )[0]

    assert "npm ci --legacy-peer-deps" in frontend_section
    assert "node_modules/.bin/vite" in frontend_section
    assert "- frontend_node_modules:/workspace/frontend/node_modules" in frontend_section
    assert "\nvolumes:\n  frontend_node_modules:\n" in text


def test_docker_compose_worker_has_one_migration_free_duckdb_writer_process():
    compose_path = ROOT / "docker-compose.yml"
    text = compose_path.read_text(encoding="utf-8")
    api_section = text.split("\n  api:\n", maxsplit=1)[1].split("\n  worker:\n", maxsplit=1)[0]
    worker_section = text.split("\n  worker:\n", maxsplit=1)[1].split("\n  postgres:\n", maxsplit=1)[0]

    assert "healthcheck:" in api_section
    assert "http://127.0.0.1:8000/health/ready" in api_section
    assert "import json,sys,urllib.request" in api_section
    assert "sys.exit(0 if payload.get('status') == 'ok' else 1)" in api_section
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
