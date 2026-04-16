from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASKS_DIR = ROOT / "backend" / "app" / "tasks"
DUCKDB_REPO = ROOT / "backend" / "app" / "repositories" / "duckdb_repo.py"


def test_duckdb_repository_is_explicitly_read_only():
    if not DUCKDB_REPO.exists():
        raise AssertionError(f"Missing DuckDB repository file: {DUCKDB_REPO}")

    text = DUCKDB_REPO.read_text(encoding="utf-8")
    assert "read_only" in text or "DuckDB is read-only" in text


def test_materialize_task_exists_as_the_write_entrypoint():
    materialize_path = TASKS_DIR / "materialize.py"
    if not materialize_path.exists():
        raise AssertionError(f"Missing materialize task file: {materialize_path}")

    text = materialize_path.read_text(encoding="utf-8")
    assert "materialize" in text
