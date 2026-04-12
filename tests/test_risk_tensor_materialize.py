from __future__ import annotations

import json

import pytest

from tests.helpers import load_module
from tests.test_bond_analytics_materialize_flow import REPORT_DATE, _seed_bond_snapshot_rows


def _read_jsonl(path):
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _configure_upstream(tmp_path):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    _seed_bond_snapshot_rows(str(duckdb_path))
    bond_task_mod = load_module(
        "backend.app.tasks.bond_analytics_materialize",
        "backend/app/tasks/bond_analytics_materialize.py",
    )
    bond_task_mod.materialize_bond_analytics_facts.fn(
        report_date=REPORT_DATE,
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )
    return duckdb_path, governance_dir, bond_task_mod


def test_risk_tensor_materialize_writes_fact_and_governance_records(tmp_path):
    duckdb_path, governance_dir, bond_task_mod = _configure_upstream(tmp_path)
    risk_task_mod = load_module(
        "backend.app.tasks.risk_tensor_materialize",
        "backend/app/tasks/risk_tensor_materialize.py",
    )
    repo_mod = load_module(
        "backend.app.repositories.risk_tensor_repo",
        "backend/app/repositories/risk_tensor_repo.py",
    )

    payload = risk_task_mod.materialize_risk_tensor_facts.fn(
        report_date=REPORT_DATE,
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    row = repo_mod.RiskTensorRepository(str(duckdb_path)).fetch_risk_tensor_row(REPORT_DATE)
    build_runs = _read_jsonl(governance_dir / "cache_build_run.jsonl")
    manifests = _read_jsonl(governance_dir / "cache_manifest.jsonl")

    assert payload["status"] == "completed"
    assert payload["cache_key"] == risk_task_mod.CACHE_KEY
    assert payload["rule_version"] == risk_task_mod.RULE_VERSION
    assert payload["source_version"] == "sv_risk_tensor__sv_bond_snap_1"
    assert row is not None
    assert row["source_version"] == "sv_risk_tensor__sv_bond_snap_1"
    assert row["upstream_source_version"] == "sv_bond_snap_1"
    assert row["cache_version"] == risk_task_mod.CACHE_VERSION
    assert row["bond_count"] == 3
    assert any(record["cache_key"] == bond_task_mod.CACHE_KEY for record in build_runs)
    assert any(record["cache_key"] == risk_task_mod.CACHE_KEY and record["status"] == "completed" for record in build_runs)
    assert any(record["cache_key"] == risk_task_mod.CACHE_KEY and record["cache_version"] == risk_task_mod.CACHE_VERSION for record in manifests)


def test_risk_tensor_materialize_requires_completed_upstream_lineage(tmp_path):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    risk_task_mod = load_module(
        "backend.app.tasks.risk_tensor_materialize",
        "backend/app/tasks/risk_tensor_materialize.py",
    )

    with pytest.raises(RuntimeError, match="requires completed bond_analytics lineage"):
        risk_task_mod.materialize_risk_tensor_facts.fn(
            report_date=REPORT_DATE,
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
        )


def test_risk_tensor_materialize_preserves_computed_source_version_when_write_fails(tmp_path, monkeypatch):
    duckdb_path, governance_dir, _bond_task_mod = _configure_upstream(tmp_path)
    risk_task_mod = load_module(
        "backend.app.tasks.risk_tensor_materialize",
        "backend/app/tasks/risk_tensor_materialize.py",
    )
    def _fail_replace(self, **_kwargs):
        raise RuntimeError("synthetic risk tensor write failure")

    monkeypatch.setattr(
        risk_task_mod.RiskTensorRepository,
        "replace_risk_tensor_row",
        _fail_replace,
    )

    with pytest.raises(RuntimeError, match="synthetic risk tensor write failure"):
        risk_task_mod.materialize_risk_tensor_facts.fn(
            report_date=REPORT_DATE,
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
        )

    build_runs = _read_jsonl(governance_dir / "cache_build_run.jsonl")
    risk_runs = [row for row in build_runs if row["cache_key"] == risk_task_mod.CACHE_KEY]
    assert risk_runs[-1]["status"] == "failed"
    assert risk_runs[-1]["source_version"] == "sv_risk_tensor__sv_bond_snap_1"


def test_risk_tensor_module_descriptor_registers_without_collision():
    registry_mod = load_module(
        "backend.app.core_finance.module_registry",
        "backend/app/core_finance/module_registry.py",
    )
    bond_task_mod = load_module(
        "backend.app.tasks.bond_analytics_materialize",
        "backend/app/tasks/bond_analytics_materialize.py",
    )
    risk_task_mod = load_module(
        "backend.app.tasks.risk_tensor_materialize",
        "backend/app/tasks/risk_tensor_materialize.py",
    )

    descriptor = registry_mod.get_formal_module("risk_tensor")

    assert descriptor.cache_key == risk_task_mod.CACHE_KEY
    assert descriptor.cache_key != bond_task_mod.CACHE_KEY
    assert descriptor.lock_key != bond_task_mod.BOND_ANALYTICS_LOCK.key
