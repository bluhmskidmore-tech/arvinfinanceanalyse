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
    backend_mypy_cache = _make_dir(repo_root / "backend" / ".mypy_cache")
    _write_file(backend_mypy_cache / "cache.db")
    os.utime(backend_mypy_cache, (_old_timestamp(), _old_timestamp()))
    protected_git_cache = _make_dir(repo_root / ".git" / "__pycache__")
    protected_data_cache = _make_dir(repo_root / "data" / "__pycache__")

    output = _run_cleanup(repo_root, "-Apply")

    assert "APPLY cleanup-dev-artifacts" in output
    assert not removable_pytest.exists()
    assert not protected_pytest.exists()
    assert not removable_cache.exists()
    assert not backend_mypy_cache.exists()
    assert protected_git_cache.exists()
    assert protected_data_cache.exists()
    assert "Skipped protected" in output


def test_cleanup_dev_artifacts_apply_removes_known_test_output_with_duckdb_artifacts(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    pytest_duckdb = _make_dir(repo_root / ".codex-tmp" / "pytest-db-run")
    _write_file(pytest_duckdb / "moss.duckdb")
    os.utime(pytest_duckdb, (_old_timestamp(), _old_timestamp()))

    test_output = _make_dir(repo_root / "test_output" / "accounting_asset_movement" / "run-001")
    _write_file(test_output / "movement.duckdb")
    os.utime(test_output, (_old_timestamp(), _old_timestamp()))
    os.utime(repo_root / "test_output", (_old_timestamp(), _old_timestamp()))

    output = _run_cleanup(repo_root, "-Apply")

    assert "APPLY cleanup-dev-artifacts" in output
    assert not pytest_duckdb.exists()
    assert not test_output.exists()


def test_cleanup_dev_artifacts_apply_removes_formal_balance_pipeline_generated_duckdb_artifacts(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    generated_root = _make_dir(repo_root / "test_output" / "formal_balance_pipeline" / "run-001")
    _write_file(generated_root / "moss.duckdb")
    os.utime(generated_root, (_old_timestamp(), _old_timestamp()))
    os.utime(repo_root / "test_output", (_old_timestamp(), _old_timestamp()))

    output = _run_cleanup(repo_root, "-Apply")

    assert "APPLY cleanup-dev-artifacts" in output
    assert not generated_root.exists()


def test_cleanup_dev_artifacts_apply_removes_old_test_output_children_when_root_was_touched_recently(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    recent_test_output_root = repo_root / "test_output"
    recent_test_output_root.mkdir()
    old_child = _make_dir(recent_test_output_root / "formal_balance_pipeline" / "run-001")
    _write_file(old_child / "moss.duckdb")
    os.utime(old_child, (_old_timestamp(), _old_timestamp()))
    os.utime(recent_test_output_root, (_old_timestamp(days=1), _old_timestamp(days=1)))

    output = _run_cleanup(repo_root, "-Apply")

    assert "APPLY cleanup-dev-artifacts" in output
    assert not old_child.exists()
    assert recent_test_output_root.exists()


def test_cleanup_dev_artifacts_apply_keeps_recent_descendants_under_old_test_output_directories(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    test_output_root = repo_root / "test_output"
    old_run_dir = test_output_root / "accounting_asset_movement" / "run-001"
    old_file = _write_file(old_run_dir / "old.duckdb", days_old=30)
    recent_file = _write_file(old_run_dir / "recent.duckdb", days_old=1)
    old_timestamp = _old_timestamp(30)
    os.utime(old_run_dir, (old_timestamp, old_timestamp))
    os.utime(test_output_root / "accounting_asset_movement", (old_timestamp, old_timestamp))
    os.utime(test_output_root, (old_timestamp, old_timestamp))

    output = _run_cleanup(repo_root, "-Apply")

    assert "APPLY cleanup-dev-artifacts" in output
    assert not old_file.exists()
    assert recent_file.exists()
    assert old_run_dir.exists()
    assert test_output_root.exists()


def test_cleanup_dev_artifacts_apply_keeps_unknown_test_output_subtrees_even_when_old_and_duckdb_backed(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    manual_evidence = _make_dir(repo_root / "test_output" / "manual-evidence")
    protected_file = _write_file(manual_evidence / "business.duckdb")
    os.utime(manual_evidence, (_old_timestamp(), _old_timestamp()))
    os.utime(repo_root / "test_output", (_old_timestamp(), _old_timestamp()))

    output = _run_cleanup(repo_root, "-Apply")

    assert "APPLY cleanup-dev-artifacts" in output
    assert manual_evidence.exists()
    assert protected_file.exists()


def test_cleanup_dev_artifacts_apply_keeps_business_and_governance_roots_even_when_they_contain_duckdb(
    tmp_path,
):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    protected_data = _make_dir(repo_root / "data" / "snapshots")
    protected_input = _make_dir(repo_root / "data_input" / "fx")
    protected_governance = _make_dir(repo_root / "tmp-governance" / "pgdev")
    _write_file(protected_data / "moss.duckdb")
    _write_file(protected_input / "fx_daily_mid.csv")
    _write_file(protected_governance / "governance.duckdb")
    for path in (protected_data, protected_input, protected_governance):
        os.utime(path, (_old_timestamp(), _old_timestamp()))

    output = _run_cleanup(repo_root, "-Apply")

    assert "APPLY cleanup-dev-artifacts" in output
    assert protected_data.exists()
    assert protected_input.exists()
    assert protected_governance.exists()


def test_cleanup_dev_artifacts_apply_removes_legacy_root_pytest_basetemp_with_db_artifacts(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    legacy_basetemp = _make_dir(repo_root / ".pytest-basetemp")
    _write_file(legacy_basetemp / "test_capture_ready_golden_samp114" / "moss.duckdb", days_old=30)
    os.utime(legacy_basetemp / "test_capture_ready_golden_samp114", (_old_timestamp(), _old_timestamp()))
    os.utime(legacy_basetemp, (_old_timestamp(), _old_timestamp()))

    output = _run_cleanup(repo_root, "-Apply")

    assert "APPLY cleanup-dev-artifacts" in output
    assert ".pytest-basetemp" in output
    assert not legacy_basetemp.exists()


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
    assert "docs/tushare_news_backup_refresh_runbook.md" in doc
    assert "docs/templates/tushare_news_backup_refresh_scheduler_handoff.md" in doc
    assert "docs/templates/tushare_news_backup_refresh_go_live_checklist.md" in doc
    assert "scripts/refresh_tushare_news_backup.py --dry-run" in doc
    assert "scripts/tushare_news_backup_timer_preflight.py --stage all" in doc
    assert "scripts/tushare_news_backup_timer_preflight.py --stage all --format markdown" in doc
    assert "scripts/tushare_news_backup_timer_preflight.py --stage all --format ops-gap" in doc
    assert "/ui/news/choice-events/latest" in doc
    assert "reserved ingest routes remain reserved" in doc
