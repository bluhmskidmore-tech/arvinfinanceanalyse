from __future__ import annotations

import importlib
import types

from tests.helpers import load_module


def test_governance_repository_uses_env_sql_authority_when_backend_not_explicit(tmp_path, monkeypatch):
    governance_mod = load_module(
        "backend.app.repositories.governance_repo",
        "backend/app/repositories/governance_repo.py",
    )
    sql_path = tmp_path / "governance.db"
    monkeypatch.setenv("MOSS_GOVERNANCE_BACKEND", "sql-authority")
    monkeypatch.setenv("MOSS_GOVERNANCE_SQL_DSN", f"sqlite:///{sql_path.as_posix()}")

    repo = governance_mod.GovernanceRepository(base_dir=tmp_path)
    payload = {
        "run_id": "run-env",
        "job_name": "balance_analysis_materialize",
        "status": "queued",
        "cache_key": "balance_analysis:materialize:formal",
        "lock": "lock:duckdb:formal:balance-analysis:materialize",
        "source_version": "sv_env",
        "vendor_version": "vv_none",
        "rule_version": "rv_env",
    }
    repo.append(governance_mod.CACHE_BUILD_RUN_STREAM, payload)

    (tmp_path / "cache_build_run.jsonl").write_text(
        '{"run_id":"jsonl-only","status":"failed"}\n',
        encoding="utf-8",
    )

    rows = repo.read_all(governance_mod.CACHE_BUILD_RUN_STREAM)
    assert len(rows) == 1
    assert rows[0]["run_id"] == "run-env"
    assert rows[0]["status"] == "queued"


def test_governance_repository_defaults_to_sql_authority_in_production(tmp_path, monkeypatch):
    governance_mod = load_module(
        "backend.app.repositories.governance_repo",
        "backend/app/repositories/governance_repo.py",
    )
    sql_path = tmp_path / "governance.db"
    monkeypatch.setenv("MOSS_ENVIRONMENT", "production")
    monkeypatch.delenv("MOSS_GOVERNANCE_BACKEND", raising=False)
    monkeypatch.setenv("MOSS_GOVERNANCE_SQL_DSN", f"sqlite:///{sql_path.as_posix()}")

    repo = governance_mod.GovernanceRepository(base_dir=tmp_path)
    repo.append(
        governance_mod.CACHE_BUILD_RUN_STREAM,
        {
            "run_id": "run-prod-sql",
            "job_name": "pnl_materialize",
            "status": "completed",
            "cache_key": "pnl:phase2:materialize:formal",
            "source_version": "sv-prod",
        },
    )
    (tmp_path / "cache_build_run.jsonl").write_text(
        '{"run_id":"jsonl-stale","status":"failed"}\n',
        encoding="utf-8",
    )

    rows = repo.read_all(governance_mod.CACHE_BUILD_RUN_STREAM)

    assert repo.backend_mode == "sql-authority"
    assert [row["run_id"] for row in rows] == ["run-prod-sql"]


def test_governance_repository_rejects_jsonl_backend_in_production(tmp_path, monkeypatch):
    governance_mod = load_module(
        "backend.app.repositories.governance_repo",
        "backend/app/repositories/governance_repo.py",
    )
    monkeypatch.setenv("MOSS_ENVIRONMENT", "production")
    monkeypatch.setenv("MOSS_GOVERNANCE_BACKEND", "jsonl")

    try:
        governance_mod.GovernanceRepository(base_dir=tmp_path)
    except ValueError as exc:
        assert "production" in str(exc)
        assert "jsonl" in str(exc)
    else:
        raise AssertionError("production governance backend must reject jsonl")


def test_formal_compute_lineage_uses_env_sql_authority_without_explicit_args(tmp_path, monkeypatch):
    governance_mod = load_module(
        "backend.app.repositories.governance_repo",
        "backend/app/repositories/governance_repo.py",
    )
    lineage_mod = load_module(
        "backend.app.governance.formal_compute_lineage",
        "backend/app/governance/formal_compute_lineage.py",
    )
    sql_path = tmp_path / "governance.db"
    monkeypatch.setenv("MOSS_GOVERNANCE_BACKEND", "sql-authority")
    monkeypatch.setenv("MOSS_GOVERNANCE_SQL_DSN", f"sqlite:///{sql_path.as_posix()}")

    repo = governance_mod.GovernanceRepository(base_dir=tmp_path)
    repo.append(
        governance_mod.CACHE_MANIFEST_STREAM,
        {
            "cache_key": "pnl:launch:formal",
            "cache_version": "cv_sql_manifest",
            "source_version": "sv_sql_manifest",
            "vendor_version": "vv_sql_manifest",
            "rule_version": "rv_sql_manifest",
        },
    )

    (tmp_path / "cache_manifest.jsonl").write_text(
        '{"cache_key":"pnl:launch:formal","source_version":"sv_jsonl"}\n',
        encoding="utf-8",
    )

    lineage = lineage_mod.resolve_formal_manifest_lineage(
        governance_dir=str(tmp_path),
        cache_key="pnl:launch:formal",
    )

    assert lineage["cache_version"] == "cv_sql_manifest"
    assert lineage["source_version"] == "sv_sql_manifest"
    assert lineage["vendor_version"] == "vv_sql_manifest"
    assert lineage["rule_version"] == "rv_sql_manifest"


def test_worker_bootstrap_requests_broker_before_loading_task_modules(monkeypatch):
    broker_calls: list[str] = []
    imported_modules: list[str] = []
    startup_calls: list[str] = []

    fake_storage_bootstrap = types.ModuleType("backend.app.storage_bootstrap")
    fake_storage_bootstrap.run_startup_storage_migrations = lambda: startup_calls.append("migrated")
    fake_broker_module = types.ModuleType("backend.app.tasks.broker")
    fake_broker_module.get_broker = lambda: broker_calls.append("broker") or object()

    real_import_module = importlib.import_module

    def fake_import_module(name: str, package: str | None = None):
        imported_modules.append(name)
        if name == "backend.app.tasks.broker":
            return fake_broker_module
        if name.startswith("backend.app.tasks.") and name != "backend.app.tasks.broker":
            return types.ModuleType(name)
        return real_import_module(name, package)

    monkeypatch.setitem(importlib.sys.modules, "backend.app.storage_bootstrap", fake_storage_bootstrap)
    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    load_module(
        "backend.app.tasks.worker_bootstrap",
        "backend/app/tasks/worker_bootstrap.py",
    )

    assert startup_calls == ["migrated"]
    assert broker_calls == ["broker"]
    assert imported_modules.index("backend.app.tasks.broker") < imported_modules.index(
        "backend.app.tasks.dev_health"
    )
