import os
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "cleanup-dev-artifacts.ps1"


def _old_timestamp(days: int = 30) -> float:
    return time.time() - days * 24 * 60 * 60


def _write_file(path: Path, text: str = "scratch", *, days_old: int = 30) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    timestamp = _old_timestamp(days_old)
    os.utime(path, (timestamp, timestamp))
    return path


def _make_dir(path: Path, *, days_old: int = 30) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _write_file(path / "artifact.txt", days_old=days_old)
    timestamp = _old_timestamp(days_old)
    os.utime(path, (timestamp, timestamp))
    return path


def _run_cleanup(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SCRIPT),
            "-RepoRoot",
            str(repo_root),
            *args,
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )
    return completed.stdout.replace("\\", "/")


def test_cleanup_dev_artifacts_dry_run_lists_candidates_without_deleting(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    old_pytest = _make_dir(repo_root / ".codex-tmp" / "pytest-old")
    recent_pytest = _make_dir(repo_root / ".codex-tmp" / "pytest-new", days_old=1)
    old_log = _write_file(repo_root / "api.log")
    recent_log = _write_file(repo_root / "recent.log", days_old=1)

    output = _run_cleanup(repo_root)

    assert "DRY-RUN cleanup-dev-artifacts" in output
    assert ".codex-tmp/pytest-old" in output
    assert "api.log" in output
    assert ".codex-tmp/pytest-new" not in output
    assert "recent.log" not in output
    assert old_pytest.exists()
    assert recent_pytest.exists()
    assert old_log.exists()
    assert recent_log.exists()


def test_cleanup_dev_artifacts_apply_respects_protected_paths_and_extensions(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    removable_pytest = _make_dir(repo_root / ".codex-tmp" / "pytest-remove")
    protected_pytest = _make_dir(repo_root / ".codex-tmp" / "pytest-with-csv")
    _write_file(protected_pytest / "business.csv")
    os.utime(protected_pytest, (_old_timestamp(), _old_timestamp()))
    removable_cache = _make_dir(repo_root / "backend" / "app" / "__pycache__")
    protected_git_cache = _make_dir(repo_root / ".git" / "__pycache__")
    protected_data_cache = _make_dir(repo_root / "data" / "__pycache__")

    output = _run_cleanup(repo_root, "-Apply")

    assert "APPLY cleanup-dev-artifacts" in output
    assert not removable_pytest.exists()
    assert not removable_cache.exists()
    assert protected_pytest.exists()
    assert protected_git_cache.exists()
    assert protected_data_cache.exists()
    assert "Skipped protected" in output


def test_cleanup_dev_artifacts_screenshots_require_explicit_flag(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    root_screenshot = _write_file(repo_root / "page.png", days_old=30)
    frontend_screenshot = _write_file(repo_root / "frontend" / "page.png", days_old=30)

    first_output = _run_cleanup(repo_root, "-Apply")

    assert "page.png" not in first_output
    assert root_screenshot.exists()
    assert frontend_screenshot.exists()

    second_output = _run_cleanup(repo_root, "-Apply", "-IncludeScreenshots")

    assert "page.png" in second_output
    assert not root_screenshot.exists()
    assert not frontend_screenshot.exists()


def test_maintenance_doc_records_cleanup_and_parallelism_boundaries():
    doc = (ROOT / "docs" / "MAINTENANCE.md").read_text(encoding="utf-8")

    assert "cleanup-dev-artifacts.ps1" in doc
    assert "dry-run" in doc
    assert "DuckDB" in doc
    assert "backend/app/tasks/" in doc
    assert "MOSS_DEV_WORKER_PROCESSES" in doc
    assert "read/vendor queue" in doc
    assert "materialize/write queue" in doc
