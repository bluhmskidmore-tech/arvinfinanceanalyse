"""External storage launch, task/read consistency, and closed-file recovery probes."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from _pytest_duckdb_guard import register_pytest_duckdb_temp_root

from backend.app.governance.settings import Settings, get_settings
from backend.app.repositories.duckdb_repo import read_only_connection
from backend.app.repositories.governance_repo import GovernanceRepository
from backend.app.repositories.object_store_repo import ObjectStoreRepository
from backend.app.repositories.source_manifest_repo import SourceManifestRepository
from backend.app.repositories.user_scope_repo import UserScopeRepository
from backend.app.security.auth_context import ROLE_HEADER_TRUST_ENV
from scripts.archive_storage_migration import (
    SAMPLE_OWNERSHIP_MARKER,
    apply_sample_archive_relocation,
    plan_archive_relocation,
)
from tests.helpers import ROOT, load_module
from tests.test_snapshot_materialize_flow import _load_tasks, _write_synthetic_snapshot_inputs


@pytest.mark.parametrize("source", ["default", "constructor", "env_file", "process"])
def test_input_root_explicit_metadata_survives_path_normalization(tmp_path, monkeypatch, source):
    monkeypatch.delenv("MOSS_DATA_INPUT_ROOT", raising=False)
    monkeypatch.delenv("RAW_FILES_DIR", raising=False)
    external = tmp_path / "external-inputs"
    options = {"_env_file": None, "environment": "development"}
    if source == "constructor":
        options["data_input_root"] = external
    elif source == "env_file":
        env_file = tmp_path / "storage.env"
        env_file.write_text(f"MOSS_DATA_INPUT_ROOT={external.as_posix()}\n", encoding="utf-8")
        options["_env_file"] = env_file
    elif source == "process":
        monkeypatch.setenv("MOSS_DATA_INPUT_ROOT", str(external))
    settings = Settings(**options)
    assert settings._data_input_root_explicit is (source != "default")
    # Post-init path normalization adds the field even when it was a default;
    # the private initial snapshot must preserve the actual configuration origin.
    assert "data_input_root" in settings.model_fields_set
    assert "_data_input_root_explicit" not in settings.model_dump()


def _stage_dev_env(root: Path) -> None:
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    for name in ("dev-env.ps1", "dev_postgres_cluster.py"):
        shutil.copy2(ROOT / "scripts" / name, scripts / name)
    (scripts / "dev-python.ps1").write_text(
        "function Resolve-DevPython { param([object]$RequiredModules) return $env:TEST_STORAGE_PYTHON }\n",
        encoding="utf-8",
    )


def _run_dev_env(root: Path, paths: dict[str, str], *, probe: bool = False):
    powershell = shutil.which("powershell")
    if powershell is None:
        pytest.skip("Windows PowerShell is unavailable")
    command = ". (Join-Path $env:TEST_STORAGE_REPO 'scripts/dev-env.ps1'); "
    if probe:
        command += "Assert-DevBootstrapStorageReady -ProbeLabel external-storage-test; "
    command += "@{ " + "; ".join(f"{key}=$env:{key}" for key in paths) + " } | ConvertTo-Json -Compress"
    return subprocess.run(
        [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        cwd=root.parent,
        env={**os.environ, **paths, "TEST_STORAGE_REPO": str(root), "TEST_STORAGE_PYTHON": sys.executable},
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )


def test_dev_env_preserves_explicit_external_paths_through_python_helper(tmp_path):
    root = tmp_path / "repo"
    _stage_dev_env(root)
    external = tmp_path / "external storage"
    paths = {
        "MOSS_DUCKDB_PATH": str(external / "moss.duckdb"),
        "MOSS_GOVERNANCE_PATH": str(external / "governance"),
        "MOSS_DATA_INPUT_ROOT": str(external / "inputs"),
        "MOSS_LOCAL_ARCHIVE_PATH": str(external / "archive"),
        "MOSS_FINANCIAL_PUBLICATION_ROOT": str(external / "publications"),
    }

    completed = _run_dev_env(root, paths)

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == paths
    assert not external.exists()


def test_dev_storage_preflight_refuses_missing_explicit_database_without_repo_fallback(tmp_path):
    root = tmp_path / "repo"
    _stage_dev_env(root)
    sentinel = root / "data" / "moss.duckdb"
    sentinel.parent.mkdir()
    sentinel.write_bytes(b"repository database must never be opened by this missing-path probe")
    external = tmp_path / "missing external storage"
    paths = {
        "MOSS_DUCKDB_PATH": str(external / "moss.duckdb"),
        "MOSS_GOVERNANCE_PATH": str(external / "governance"),
        "MOSS_DATA_INPUT_ROOT": str(external / "inputs"),
        "MOSS_LOCAL_ARCHIVE_PATH": str(external / "archive"),
    }

    completed = _run_dev_env(root, paths, probe=True)

    assert completed.returncode != 0
    assert "Missing MOSS_DUCKDB_PATH" in completed.stderr
    assert re.sub(r"\s+", "", str(external / "moss.duckdb")) in re.sub(r"\s+", "", completed.stderr)
    assert not external.exists()
    assert sentinel.read_bytes().startswith(b"repository database must never be opened")


def _configure_sample_storage(root: Path, monkeypatch, *, scope_database: Path | None = None) -> None:
    for key, path in {
        "MOSS_DUCKDB_PATH": root / "moss.duckdb",
        "MOSS_GOVERNANCE_PATH": root / "governance",
        "MOSS_DATA_INPUT_ROOT": root / "inputs",
        "MOSS_LOCAL_ARCHIVE_PATH": root / "archive",
        "MOSS_FINANCIAL_PUBLICATION_ROOT": root / "publications",
    }.items():
        monkeypatch.setenv(key, str(path))
    # Authorization storage is not part of this DuckDB/archive migration. Keep
    # its pooled SQLite handles outside the directory moved by the recovery probe.
    sqlite_dsn = f"sqlite:///{(scope_database or root.parent / 'scope.db').as_posix()}"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", sqlite_dsn)
    monkeypatch.setenv("MOSS_GOVERNANCE_SQL_DSN", sqlite_dsn)
    monkeypatch.setenv("MOSS_ENVIRONMENT", "development")
    monkeypatch.setenv("MOSS_OBJECT_STORE_MODE", "local")
    monkeypatch.setenv("MOSS_GOVERNANCE_BACKEND", "jsonl")
    monkeypatch.setenv("MOSS_FINANCIAL_PUBLICATION_ENABLED", "false")
    monkeypatch.setenv("MOSS_SYSTEM_READ_PUBLICATION_ENABLED", "false")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()


def _snapshot_summary(database: Path) -> dict[str, list]:
    with read_only_connection(str(database)) as conn:
        return {
            table: conn.execute(
                f"select report_date, currency_code, source_version, rule_version, "
                f"count(*), sum({amount}) from {table} group by 1, 2, 3, 4 order by 1, 2, 3, 4"
            ).fetchall()
            for table, amount in (
                ("zqtz_bond_daily_snapshot", "market_value_native"),
                ("tyw_interbank_daily_snapshot", "principal_native"),
            )
        }


def _positions_result() -> dict:
    settings = get_settings()
    UserScopeRepository(settings.governance_sql_dsn).grant_scope(
        user_id="external-storage-reader", role=None, resource="positions", action="read"
    )
    app = FastAPI()
    app.include_router(load_module("backend.app.api.routes.positions", "backend/app/api/routes/positions.py").router)
    with TestClient(app) as client:
        response = client.get(
            "/api/positions/bonds?report_date=2025-12-31",
            headers={"X-User-Id": "external-storage-reader", "X-User-Role": "viewer"},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["total"] == 2
    assert payload["result_meta"]["formal_use_allowed"] is False
    assert payload["result_meta"]["resolved_report_date"] == "2025-12-31"
    return payload


@pytest.fixture
def external_storage_sample(tmp_path, tmp_path_factory):
    with tempfile.TemporaryDirectory(prefix="moss-external-storage-sample-") as directory:
        owned = register_pytest_duckdb_temp_root(directory)
        (owned / SAMPLE_OWNERSHIP_MARKER).write_text(
            '{"format_version":1,"purpose":"moss-archive-migration-sample"}', encoding="utf-8"
        )
        try:
            yield owned
        finally:
            receipt = owned / "pytest-duckdb-guard-attempts.jsonl"
            if receipt.is_file():
                shutil.copy2(receipt, tmp_path / "external-storage-guard-attempts.jsonl")
            register_pytest_duckdb_temp_root(tmp_path_factory.getbasetemp())


def test_external_task_api_storage_and_closed_database_recovery(external_storage_sample, tmp_path, monkeypatch):
    owned = external_storage_sample
    source = owned / "external source"
    _write_synthetic_snapshot_inputs(source / "inputs", "2025-12-31")
    _configure_sample_storage(source, monkeypatch, scope_database=tmp_path / "scope.db")
    ingest, snapshots = _load_tasks()

    ingest.ingest_demo_manifest.fn()
    materialized = snapshots.materialize_standard_snapshots.fn()

    assert materialized["status"] == "completed"
    assert (materialized["zqtz_rows"], materialized["tyw_rows"]) == (2, 2)
    settings = get_settings()
    manifests = SourceManifestRepository(
        governance_repo=GovernanceRepository(settings.governance_path)
    ).load_all()
    assert len(manifests) == 2
    assert all(Path(row["archived_path"]).is_relative_to(source / "archive") for row in manifests)
    before_summary = _snapshot_summary(source / "moss.duckdb")
    before_api = _positions_result()
    assert before_api["result_meta"]["source_version"] in {row["source_version"] for row in manifests}
    assert not Path(str(source / "moss.duckdb") + ".wal").exists()

    recovery = owned / "isolated recovery"
    # All task and read connections have closed. Copy one consistent sample,
    # including governance and archived bytes, without touching active storage.
    recovery.mkdir()
    for item in source.iterdir():
        if item.name == "archive":
            continue
        if item.is_dir():
            shutil.copytree(item, recovery / item.name)
        else:
            shutil.copy2(item, recovery / item.name)
    history = {
        name: (source / "governance" / name).read_bytes()
        for name in ("source_manifest.jsonl", "snapshot_manifest.jsonl")
    }
    plan = plan_archive_relocation(source / "archive", recovery / "archive")
    assert not (recovery / "archive").exists()
    assert all((source / "governance" / name).read_bytes() == payload for name, payload in history.items())
    apply_sample_archive_relocation(plan, owned)
    assert hashlib.sha256((source / "moss.duckdb").read_bytes()).digest() == hashlib.sha256(
        (recovery / "moss.duckdb").read_bytes()
    ).digest()
    for manifest in manifests:
        relative = Path(manifest["archived_path"]).relative_to(source / "archive")
        assert (source / "archive" / relative).read_bytes() == (recovery / "archive" / relative).read_bytes()
    source.rename(owned / "source unavailable after recovery")
    _configure_sample_storage(recovery, monkeypatch, scope_database=tmp_path / "scope.db")
    assert _snapshot_summary(recovery / "moss.duckdb") == before_summary
    after_api = _positions_result()
    assert after_api["result"] == before_api["result"]
    assert after_api["result_meta"]["source_version"] == before_api["result_meta"]["source_version"]

    # Historical records retain their exact bytes and absolute identity. Only
    # the trusted physical-location receipt is new.
    assert all((recovery / "governance" / name).read_bytes() == payload for name, payload in history.items())
    store = ObjectStoreRepository("unused", "unused", "unused", "unused", mode="local", local_archive_path=str(recovery / "archive"))
    assert store.read_archived_bytes(str(manifests[0]["archived_path"]))
    rematerialized = snapshots.materialize_standard_snapshots.fn()
    assert rematerialized["status"] == "completed"
    assert _snapshot_summary(recovery / "moss.duckdb") == before_summary
    assert _positions_result()["result"] == before_api["result"]
    assert (recovery / "governance" / "source_manifest.jsonl").read_bytes() == history["source_manifest.jsonl"]
    assert (recovery / "governance" / "snapshot_manifest.jsonl").read_bytes().startswith(history["snapshot_manifest.jsonl"])
    previews = load_module("backend.app.tasks.materialize", "backend/app/tasks/materialize.py")
    preview_result = previews.materialize_cache_view.fn()
    assert preview_result["status"] == "completed"
    with read_only_connection(str(recovery / "moss.duckdb")) as connection:
        preview_sources = {
            row[0]
            for table in ("phase1_zqtz_preview_rows", "phase1_tyw_preview_rows")
            for row in connection.execute(f"select distinct source_version from {table}").fetchall()
        }
    assert preview_sources == {row["source_version"] for row in manifests}
    get_settings.cache_clear()
