from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.helpers import load_module


def _load_runtime_suite():
    schema_mod = load_module(
        "backend.app.schemas.formal_compute_runtime",
        "backend/app/schemas/formal_compute_runtime.py",
    )
    registry_mod = load_module(
        "backend.app.core_finance.module_registry",
        "backend/app/core_finance/module_registry.py",
    )
    runtime_mod = load_module(
        "backend.app.tasks.formal_compute_runtime",
        "backend/app/tasks/formal_compute_runtime.py",
    )
    fixture_mod = load_module(
        "tests.fixtures.formal_compute.mock_standard_module",
        "tests/fixtures/formal_compute/mock_standard_module.py",
    )
    return schema_mod, registry_mod, runtime_mod, fixture_mod


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_runtime_records_running_completed_and_manifest(tmp_path):
    _schema_mod, registry_mod, runtime_mod, fixture_mod = _load_runtime_suite()
    registry_mod.clear_formal_modules()
    descriptor = registry_mod.register_formal_module(fixture_mod.MOCK_STANDARD_MODULE)
    governance_dir = tmp_path / "governance"

    payload = runtime_mod.run_formal_materialize(
        descriptor=descriptor,
        job_name="mock_standard_materialize",
        report_date="2025-12-31",
        governance_dir=str(governance_dir),
        lock_base_dir=str(tmp_path),
        execute_materialization=fixture_mod.run_mock_materialization,
    )

    build_runs = _read_jsonl(governance_dir / "cache_build_run.jsonl")
    manifests = _read_jsonl(governance_dir / "cache_manifest.jsonl")

    assert payload["status"] == "completed"
    assert payload["cache_key"] == descriptor.cache_key
    assert payload["cache_version"] == descriptor.cache_version
    assert payload["rule_version"] == descriptor.rule_version
    assert payload["mock_rows"] == 2
    assert build_runs[0]["cache_version"] == descriptor.cache_version
    assert build_runs[0]["status"] == "running"
    assert build_runs[-1]["cache_version"] == descriptor.cache_version
    assert build_runs[-1]["status"] == "completed"
    assert manifests[-1]["cache_key"] == descriptor.cache_key
    assert manifests[-1]["cache_version"] == descriptor.cache_version
    assert manifests[-1]["rule_version"] == descriptor.rule_version


def test_runtime_records_failure_without_manifest(tmp_path):
    _schema_mod, registry_mod, runtime_mod, fixture_mod = _load_runtime_suite()
    registry_mod.clear_formal_modules()
    descriptor = registry_mod.register_formal_module(fixture_mod.MOCK_STANDARD_MODULE)
    governance_dir = tmp_path / "governance"

    with pytest.raises(RuntimeError, match="mock failure"):
        runtime_mod.run_formal_materialize(
            descriptor=descriptor,
            job_name="mock_standard_materialize",
            report_date="2025-12-31",
            governance_dir=str(governance_dir),
            lock_base_dir=str(tmp_path),
            execute_materialization=fixture_mod.run_mock_failure,
        )

    build_runs = _read_jsonl(governance_dir / "cache_build_run.jsonl")
    manifests = _read_jsonl(governance_dir / "cache_manifest.jsonl")
    assert [record["status"] for record in build_runs] == ["running", "failed"]
    assert manifests == []


def test_runtime_preserves_computed_source_version_on_structured_write_failure(tmp_path):
    schema_mod, registry_mod, runtime_mod, fixture_mod = _load_runtime_suite()
    registry_mod.clear_formal_modules()
    descriptor = registry_mod.register_formal_module(fixture_mod.MOCK_STANDARD_MODULE)
    governance_dir = tmp_path / "governance"

    def _fail_after_lineage():
        raise schema_mod.FormalComputeMaterializeFailure(
            source_version="sv_mock_standard_v1",
            message="mock failure after lineage",
        )

    with pytest.raises(RuntimeError, match="mock failure after lineage"):
        runtime_mod.run_formal_materialize(
            descriptor=descriptor,
            job_name="mock_standard_materialize",
            report_date="2025-12-31",
            governance_dir=str(governance_dir),
            lock_base_dir=str(tmp_path),
            execute_materialization=_fail_after_lineage,
        )

    build_runs = _read_jsonl(governance_dir / "cache_build_run.jsonl")
    assert build_runs[-1]["status"] == "failed"
    assert build_runs[-1]["source_version"] == "sv_mock_standard_v1"


def test_runtime_uses_schema_failure_contract():
    schema_mod, _registry_mod, runtime_mod, _fixture_mod = _load_runtime_suite()

    assert runtime_mod.FormalComputeMaterializeFailure is schema_mod.FormalComputeMaterializeFailure
