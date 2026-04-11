from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_dev_api_script_bootstraps_native_environment():
    script = (ROOT / "scripts" / "dev-api.ps1").read_text(encoding="utf-8")
    assert ". .\\scripts\\dev-env.ps1" in script or ". \"$root\\scripts\\dev-env.ps1\"" in script
    assert ". .\\.venv\\Scripts\\Activate.ps1" in script
    assert "uvicorn backend.app.main:app" in script


def test_dev_worker_script_bootstraps_native_environment():
    script = (ROOT / "scripts" / "dev-worker.ps1").read_text(encoding="utf-8")
    assert ". .\\scripts\\dev-env.ps1" in script or ". \"$root\\scripts\\dev-env.ps1\"" in script
    assert ". .\\.venv\\Scripts\\Activate.ps1" in script
    assert "dramatiq backend.app.tasks.worker_bootstrap" in script


def test_dev_env_script_sets_repo_relative_data_paths():
    script = (ROOT / "scripts" / "dev-env.ps1").read_text(encoding="utf-8")
    assert "Join-Path $root" in script
    assert 'Join-Path $root "data\\moss.duckdb"' in script
    assert 'Join-Path $root "data\\archive"' in script
    assert "F:\\MOSS-V3" not in script
