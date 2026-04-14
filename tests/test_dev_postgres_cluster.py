from dataclasses import replace
from pathlib import Path

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


def test_dev_postgres_cluster_env_mapping_targets_local_runtime_paths():
    module = load_module(
        "scripts.dev_postgres_cluster",
        "scripts/dev_postgres_cluster.py",
    )

    config = module.build_cluster_config(ROOT)
    env = module.build_env_mapping(config)

    assert env["MOSS_POSTGRES_DSN"] == "postgresql://moss:moss@127.0.0.1:55432/moss"
    assert env["MOSS_GOVERNANCE_SQL_DSN"] == "postgresql://moss:moss@127.0.0.1:55432/moss"
    assert env["MOSS_REDIS_DSN"] == "redis://127.0.0.1:6379/11"
    assert env["MOSS_DUCKDB_PATH"] == str(ROOT / "tmp-governance" / "runtime-clean" / "moss.duckdb")
    assert env["MOSS_GOVERNANCE_PATH"] == str(ROOT / "tmp-governance" / "runtime-clean" / "governance")
    assert env["MOSS_LOCAL_ARCHIVE_PATH"] == str(ROOT / "tmp-governance" / "runtime-clean" / "archive")
    assert env["MOSS_DATA_INPUT_ROOT"] == str(ROOT / "tmp-governance" / "runtime-clean" / "data_input")


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


def test_reset_schema_refuses_non_dev_endpoint():
    module = load_module(
        "scripts.dev_postgres_cluster",
        "scripts/dev_postgres_cluster.py",
    )

    config = module.build_cluster_config(ROOT)
    wrong_port = replace(config, port=5432)
    with pytest.raises(RuntimeError, match="reset-schema refused"):
        module.command_reset_schema(wrong_port)
