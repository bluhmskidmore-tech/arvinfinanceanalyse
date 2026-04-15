from dataclasses import replace
from pathlib import Path
import subprocess

import duckdb
import pytest

from tests.helpers import ROOT, load_module


def test_dev_postgres_cluster_builds_expected_local_layout():
    module = load_module(
        "scripts.dev_postgres_cluster",
        "scripts/dev_postgres_cluster.py",
    )

    config = module.build_cluster_config(ROOT)

    assert config.repo_root == ROOT
    assert config.cluster_root == ROOT / "tmp-governance" / "pgdev"
    assert config.data_dir == ROOT / "tmp-governance" / "pgdev" / "data"
    assert config.runtime_root == ROOT / "tmp-governance" / "runtime-clean"
    assert config.port == 55432
    assert config.host == "127.0.0.1"
    assert config.database == "moss"
    assert config.user == "moss"


def test_dev_postgres_cluster_env_mapping_prefers_seeded_storage_root(tmp_path):
    module = load_module(
        "scripts.dev_postgres_cluster",
        "scripts/dev_postgres_cluster.py",
    )

    repo_root = tmp_path / "repo"
    repo_duckdb = repo_root / "data" / "moss.duckdb"
    repo_duckdb.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(repo_duckdb), read_only=False) as conn:
        conn.execute("create table fact_formal_bond_analytics_daily (report_date varchar)")
        conn.execute("insert into fact_formal_bond_analytics_daily values ('2026-02-28')")

    config = module.build_cluster_config(repo_root)
    env = module.build_env_mapping(config)

    assert env["MOSS_POSTGRES_DSN"] == "postgresql://moss:moss@127.0.0.1:55432/moss"
    assert env["MOSS_GOVERNANCE_SQL_DSN"] == "postgresql://moss:moss@127.0.0.1:55432/moss"
    assert env["MOSS_REDIS_DSN"] == "redis://127.0.0.1:6379/11"
    assert env["MOSS_DUCKDB_PATH"] == str(repo_root / "data" / "moss.duckdb")
    assert env["MOSS_GOVERNANCE_PATH"] == str(repo_root / "data" / "governance")
    assert env["MOSS_LOCAL_ARCHIVE_PATH"] == str(repo_root / "data" / "archive")
    assert env["MOSS_DATA_INPUT_ROOT"] == str(repo_root / "data_input")


def test_prepare_runtime_clean_paths_does_not_overwrite_existing_smoke_files(tmp_path):
    module = load_module(
        "scripts.dev_postgres_cluster",
        "scripts/dev_postgres_cluster.py",
    )

    repo_root = tmp_path / "repo"
    source_root = repo_root / "data_input"
    runtime_root = repo_root / "tmp-governance" / "runtime-clean"
    runtime_data_input = runtime_root / "data_input"
    source_root.mkdir(parents=True, exist_ok=True)
    runtime_data_input.mkdir(parents=True, exist_ok=True)

    for name in module.SMOKE_FILES:
        (source_root / name).write_text("source", encoding="utf-8")

    existing_target = runtime_data_input / module.SMOKE_FILES[0]
    existing_target.write_text("keep-existing", encoding="utf-8")

    config = module.DevPostgresClusterConfig(
        repo_root=repo_root,
        bin_dir=repo_root / "pgbin",
        cluster_root=repo_root / "tmp-governance" / "pgdev",
        data_dir=repo_root / "tmp-governance" / "pgdev" / "data",
        log_file=repo_root / "tmp-governance" / "pgdev" / "postgres.log",
        runtime_root=runtime_root,
        runtime_duckdb_path=runtime_root / "moss.duckdb",
        runtime_governance_path=runtime_root / "governance",
        runtime_archive_path=runtime_root / "archive",
        runtime_data_input_path=runtime_data_input,
    )

    module._prepare_runtime_clean_paths(config)

    assert existing_target.read_text(encoding="utf-8") == "keep-existing"


def test_prepare_runtime_clean_paths_seeds_runtime_duckdb_from_repo_when_runtime_is_empty(tmp_path):
    module = load_module(
        "scripts.dev_postgres_cluster",
        "scripts/dev_postgres_cluster.py",
    )

    repo_root = tmp_path / "repo"
    source_root = repo_root / "data_input"
    source_root.mkdir(parents=True, exist_ok=True)
    runtime_root = repo_root / "tmp-governance" / "runtime-clean"
    runtime_data_input = runtime_root / "data_input"
    runtime_data_input.mkdir(parents=True, exist_ok=True)

    repo_duckdb = repo_root / "data" / "moss.duckdb"
    repo_duckdb.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(repo_duckdb), read_only=False) as conn:
        conn.execute("create table fact_formal_bond_analytics_daily (report_date varchar)")
        conn.execute("insert into fact_formal_bond_analytics_daily values ('2026-02-28')")

    runtime_duckdb = runtime_root / "moss.duckdb"
    with duckdb.connect(str(runtime_duckdb), read_only=False) as conn:
        conn.execute("create table fact_formal_bond_analytics_daily (report_date varchar)")

    config = module.DevPostgresClusterConfig(
        repo_root=repo_root,
        bin_dir=repo_root / "pgbin",
        cluster_root=repo_root / "tmp-governance" / "pgdev",
        data_dir=repo_root / "tmp-governance" / "pgdev" / "data",
        log_file=repo_root / "tmp-governance" / "pgdev" / "postgres.log",
        runtime_root=runtime_root,
        runtime_duckdb_path=runtime_duckdb,
        runtime_governance_path=runtime_root / "governance",
        runtime_archive_path=runtime_root / "archive",
        runtime_data_input_path=runtime_data_input,
    )

    module._prepare_runtime_clean_paths(config)

    with duckdb.connect(str(runtime_duckdb), read_only=True) as conn:
        rows = conn.execute(
            "select report_date from fact_formal_bond_analytics_daily order by report_date"
        ).fetchall()
    assert rows == [("2026-02-28",)]


def test_dev_postgres_cluster_env_mapping_falls_back_to_repo_data_root_when_runtime_duckdb_is_empty(
    tmp_path,
):
    module = load_module(
        "scripts.dev_postgres_cluster",
        "scripts/dev_postgres_cluster.py",
    )

    repo_root = tmp_path / "repo"
    repo_duckdb = repo_root / "data" / "moss.duckdb"
    repo_duckdb.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(repo_duckdb), read_only=False) as conn:
        conn.execute("create table fact_formal_bond_analytics_daily (report_date varchar)")
        conn.execute("insert into fact_formal_bond_analytics_daily values ('2026-02-28')")

    runtime_root = repo_root / "tmp-governance" / "runtime-clean"
    runtime_duckdb = runtime_root / "moss.duckdb"
    runtime_duckdb.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(runtime_duckdb), read_only=False) as conn:
        conn.execute("create table fact_formal_bond_analytics_daily (report_date varchar)")

    config = module.DevPostgresClusterConfig(
        repo_root=repo_root,
        bin_dir=repo_root / "pgbin",
        cluster_root=repo_root / "tmp-governance" / "pgdev",
        data_dir=repo_root / "tmp-governance" / "pgdev" / "data",
        log_file=repo_root / "tmp-governance" / "pgdev" / "postgres.log",
        runtime_root=runtime_root,
        runtime_duckdb_path=runtime_duckdb,
        runtime_governance_path=runtime_root / "governance",
        runtime_archive_path=runtime_root / "archive",
        runtime_data_input_path=runtime_root / "data_input",
    )

    env = module.build_env_mapping(config)

    assert env["MOSS_DUCKDB_PATH"] == str(repo_root / "data" / "moss.duckdb")
    assert env["MOSS_GOVERNANCE_PATH"] == str(repo_root / "data" / "governance")
    assert env["MOSS_LOCAL_ARCHIVE_PATH"] == str(repo_root / "data" / "archive")
    assert env["MOSS_DATA_INPUT_ROOT"] == str(repo_root / "data_input")


def test_command_print_env_falls_back_to_repo_data_root_when_runtime_seed_copy_is_locked(
    tmp_path,
    monkeypatch,
):
    module = load_module(
        "scripts.dev_postgres_cluster",
        "scripts/dev_postgres_cluster.py",
    )

    repo_root = tmp_path / "repo"
    repo_duckdb = repo_root / "data" / "moss.duckdb"
    repo_duckdb.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(repo_duckdb), read_only=False) as conn:
        conn.execute("create table fact_formal_bond_analytics_daily (report_date varchar)")
        conn.execute("insert into fact_formal_bond_analytics_daily values ('2026-02-28')")

    runtime_root = repo_root / "tmp-governance" / "runtime-clean"
    runtime_data_input = runtime_root / "data_input"
    runtime_data_input.mkdir(parents=True, exist_ok=True)
    runtime_duckdb = runtime_root / "moss.duckdb"

    config = module.DevPostgresClusterConfig(
        repo_root=repo_root,
        bin_dir=repo_root / "pgbin",
        cluster_root=repo_root / "tmp-governance" / "pgdev",
        data_dir=repo_root / "tmp-governance" / "pgdev" / "data",
        log_file=repo_root / "tmp-governance" / "pgdev" / "postgres.log",
        runtime_root=runtime_root,
        runtime_duckdb_path=runtime_duckdb,
        runtime_governance_path=runtime_root / "governance",
        runtime_archive_path=runtime_root / "archive",
        runtime_data_input_path=runtime_data_input,
    )

    original_copy2 = module.shutil.copy2

    def locked_copy(src, dst, *args, **kwargs):
        if Path(dst) == runtime_duckdb:
            raise PermissionError("runtime duckdb locked")
        return original_copy2(src, dst, *args, **kwargs)

    monkeypatch.setattr(module.shutil, "copy2", locked_copy)

    env = module.command_print_env(config)

    assert env["MOSS_DUCKDB_PATH"] == str(repo_root / "data" / "moss.duckdb")


def test_reset_schema_refuses_non_dev_endpoint():
    module = load_module(
        "scripts.dev_postgres_cluster",
        "scripts/dev_postgres_cluster.py",
    )

    config = module.build_cluster_config(ROOT)
    wrong_port = replace(config, port=5432)
    with pytest.raises(RuntimeError, match="reset-schema refused"):
        module.command_reset_schema(wrong_port)


def test_run_checked_retry_retries_transient_psql_exit_code(monkeypatch):
    module = load_module(
        "scripts.dev_postgres_cluster",
        "scripts/dev_postgres_cluster.py",
    )

    calls: list[list[str]] = []

    def fake_run_checked(args, *, capture_output=False):
        calls.append(args)
        if len(calls) < 3:
            raise subprocess.CalledProcessError(2, args)
        return "ok"

    monkeypatch.setattr(module, "_run_checked", fake_run_checked)
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)

    result = module._run_checked_retry(["psql.exe", "-c", "select 1"], capture_output=True)

    assert result == "ok"
    assert len(calls) == 3


def test_run_checked_retry_does_not_swallow_non_retryable_exit_code(monkeypatch):
    module = load_module(
        "scripts.dev_postgres_cluster",
        "scripts/dev_postgres_cluster.py",
    )

    def fake_run_checked(args, *, capture_output=False):
        raise subprocess.CalledProcessError(1, args)

    monkeypatch.setattr(module, "_run_checked", fake_run_checked)
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)

    with pytest.raises(subprocess.CalledProcessError):
        module._run_checked_retry(["psql.exe", "-c", "select 1"], capture_output=True)


def test_wait_for_postgres_ready_retries_until_probe_succeeds(monkeypatch):
    module = load_module(
        "scripts.dev_postgres_cluster",
        "scripts/dev_postgres_cluster.py",
    )

    config = module.build_cluster_config(ROOT)
    attempts = {"count": 0}

    def fake_probe(_config, *, database=None):
        attempts["count"] += 1
        assert database is None
        return attempts["count"] >= 3

    monkeypatch.setattr(module, "_probe_postgres_ready", fake_probe)
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)

    module._wait_for_postgres_ready(config, attempts=5, retry_delay_seconds=0)

    assert attempts["count"] == 3


def test_wait_for_postgres_ready_raises_after_exhausting_retries(monkeypatch):
    module = load_module(
        "scripts.dev_postgres_cluster",
        "scripts/dev_postgres_cluster.py",
    )

    config = module.build_cluster_config(ROOT)
    monkeypatch.setattr(module, "_probe_postgres_ready", lambda _config, *, database=None: False)
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)

    with pytest.raises(RuntimeError, match="did not accept SQL connections"):
        module._wait_for_postgres_ready(config, attempts=3, retry_delay_seconds=0)


def test_wait_for_postgres_ready_can_target_application_database(monkeypatch):
    module = load_module(
        "scripts.dev_postgres_cluster",
        "scripts/dev_postgres_cluster.py",
    )

    config = module.build_cluster_config(ROOT)
    seen: list[str | None] = []

    def fake_probe(_config, *, database=None):
        seen.append(database)
        return True

    monkeypatch.setattr(module, "_probe_postgres_ready", fake_probe)

    module._wait_for_postgres_ready(config, database="moss", attempts=1, retry_delay_seconds=0)

    assert seen == ["moss"]


def test_resolve_python_executable_prefers_path_python(monkeypatch):
    module = load_module(
        "scripts.dev_postgres_cluster",
        "scripts/dev_postgres_cluster.py",
    )

    monkeypatch.setattr(module.shutil, "which", lambda name: r"C:\Python\python.exe" if name == "python" else None)
    monkeypatch.setattr(module.sys, "executable", r"C:\Fallback\python.exe")

    assert module._resolve_python_executable() == r"C:\Python\python.exe"
