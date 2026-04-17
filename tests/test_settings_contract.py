"""Contract tests for backend.app.governance.settings (defaults, env overrides, helpers)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from backend.app.governance.settings import (
    DEV_POSTGRES_DSN,
    Settings,
    get_settings,
    resolve_governance_sql_dsn,
    resolve_postgres_dsn,
    resolve_repo_relative_path,
)


def test_settings_defaults():
    s = Settings()
    assert s.environment == "development"
    assert s.agent_enabled is False
    assert s.governance_backend == "jsonl"
    assert s.object_store_mode == "local"
    assert s.ftp_rate_pct == Decimal("1.75")
    assert isinstance(s.governance_path, Path)
    assert isinstance(s.data_input_root, Path)
    assert isinstance(s.local_archive_path, Path)


def test_settings_env_overrides(monkeypatch):
    repo_root = Path(__file__).resolve().parents[1]
    monkeypatch.setenv("MOSS_ENVIRONMENT", "staging")
    monkeypatch.setenv("MOSS_AGENT_ENABLED", "true")
    monkeypatch.setenv("MOSS_GOVERNANCE_BACKEND", "sql-authority")
    monkeypatch.setenv("MOSS_OBJECT_STORE_MODE", "minio")
    monkeypatch.setenv("MOSS_FTP_RATE_PCT", "2.5")
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", "custom/gov")
    monkeypatch.setenv("MOSS_DATA_INPUT_ROOT", "custom/in")
    monkeypatch.setenv("MOSS_LOCAL_ARCHIVE_PATH", "custom/archive")

    s = Settings()
    assert s.environment == "staging"
    assert s.agent_enabled is True
    assert s.governance_backend == "sql-authority"
    assert s.object_store_mode == "minio"
    assert s.ftp_rate_pct == Decimal("2.5")
    assert s.governance_path == (repo_root / "custom" / "gov").resolve()
    assert s.data_input_root == (repo_root / "custom" / "in").resolve()
    assert s.local_archive_path == (repo_root / "custom" / "archive").resolve()


def test_settings_core_storage_paths_resolve_relative_to_repo_root():
    repo_root = Path(__file__).resolve().parents[1]

    s = Settings()

    assert s.duckdb_path == str((repo_root / "data" / "moss.duckdb").resolve())
    assert s.governance_path == (repo_root / "data" / "governance").resolve()
    assert s.data_input_root == (repo_root / "data_input").resolve()
    assert s.local_archive_path == (repo_root / "data" / "archive").resolve()
    assert s.product_category_source_dir == (
        repo_root / "data_input" / "pnl_总账对账-日均"
    ).resolve()


def test_get_settings_returns_settings_instance():
    assert isinstance(get_settings(), Settings)


def test_get_settings_cache_clear_callable_and_safe():
    clear = getattr(get_settings, "cache_clear", None)
    assert callable(clear)
    clear()
    clear()


def test_settings_extra_ignore_unknown_env(monkeypatch):
    monkeypatch.setenv("MOSS_TOTALLY_UNKNOWN_FUTURE_FIELD_XYZ", "should-be-ignored")
    # Must not raise; model has extra="ignore"
    s = Settings()
    assert not hasattr(s, "totally_unknown_future_field_xyz")


def test_resolve_postgres_dsn_prefers_local_dev_cluster_when_default_dsn_and_cluster_layout_exist(tmp_path):
    repo_root = tmp_path / "repo"
    (repo_root / "tmp-governance" / "pgdev" / "data").mkdir(parents=True, exist_ok=True)

    assert (
        resolve_postgres_dsn("postgresql://moss:moss@localhost:5432/moss", repo_root=repo_root)
        == DEV_POSTGRES_DSN
    )


def test_resolve_postgres_dsn_preserves_explicit_nondefault_value(tmp_path):
    repo_root = tmp_path / "repo"
    (repo_root / "tmp-governance" / "pgdev" / "data").mkdir(parents=True, exist_ok=True)

    assert (
        resolve_postgres_dsn("postgresql://custom:secret@db.internal:5433/moss", repo_root=repo_root)
        == "postgresql://custom:secret@db.internal:5433/moss"
    )


def test_resolve_governance_sql_dsn_defaults_to_resolved_postgres_dsn_when_empty():
    assert resolve_governance_sql_dsn("", DEV_POSTGRES_DSN) == DEV_POSTGRES_DSN
    assert resolve_governance_sql_dsn("postgresql://other", DEV_POSTGRES_DSN) == "postgresql://other"


def test_resolve_repo_relative_path_anchors_relative_config_paths_to_repo_root(tmp_path):
    repo_root = tmp_path / "repo"
    expected = (repo_root / "config" / "choice_macro_catalog.json").resolve()

    assert resolve_repo_relative_path(
        "config/choice_macro_catalog.json",
        repo_root=repo_root,
    ) == str(expected)


def test_resolve_repo_relative_path_preserves_absolute_and_empty_values(tmp_path):
    absolute = tmp_path / "choice_macro_catalog.json"

    assert resolve_repo_relative_path(str(absolute), repo_root=tmp_path) == str(absolute)
    assert resolve_repo_relative_path("", repo_root=tmp_path) == ""
