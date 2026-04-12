from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_dev_api_script_bootstraps_native_environment():
    script = (ROOT / "scripts" / "dev-api.ps1").read_text(encoding="utf-8")
    assert ". .\\scripts\\dev-env.ps1" in script or ". \"$root\\scripts\\dev-env.ps1\"" in script
    assert "dev-python.ps1" in script
    assert "Resolve-DevPython" in script
    assert "uvicorn backend.app.main:app" in script


def test_dev_worker_script_bootstraps_native_environment():
    script = (ROOT / "scripts" / "dev-worker.ps1").read_text(encoding="utf-8")
    assert ". .\\scripts\\dev-env.ps1" in script or ". \"$root\\scripts\\dev-env.ps1\"" in script
    assert "dev-python.ps1" in script
    assert "Resolve-DevPython" in script
    assert "dramatiq backend.app.tasks.worker_bootstrap" in script


def test_dev_env_script_sets_repo_relative_data_paths():
    script = (ROOT / "scripts" / "dev-env.ps1").read_text(encoding="utf-8")
    assert "Join-Path $root" in script
    assert 'Join-Path $root "data\\moss.duckdb"' in script
    assert 'Join-Path $root "data\\archive"' in script
    assert "dev_postgres_cluster.py" in script
    assert "F:\\MOSS-V3" not in script


def test_dev_up_script_bootstraps_local_postgres_and_starts_native_processes():
    script = (ROOT / "scripts" / "dev-up.ps1").read_text(encoding="utf-8")
    assert "dev-postgres-up.ps1" in script
    assert "dev-api.ps1" in script
    assert "dev-worker.ps1" in script
    assert "dev-frontend.ps1" in script
    assert "Start-Process" in script


def test_dev_down_script_stops_native_processes_and_local_postgres():
    script = (ROOT / "scripts" / "dev-down.ps1").read_text(encoding="utf-8")
    assert "dev-postgres-down.ps1" in script
    assert "backend.app.main:app" in script
    assert "backend.app.tasks.worker_bootstrap" in script
