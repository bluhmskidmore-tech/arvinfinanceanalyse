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
    assert "python -m dramatiq backend.app.tasks.worker_bootstrap" in text
    assert "postgresql://moss:moss@postgres:5432/moss" in text
    assert "redis://redis:6379/0" in text
    assert "minio:9000" in text
