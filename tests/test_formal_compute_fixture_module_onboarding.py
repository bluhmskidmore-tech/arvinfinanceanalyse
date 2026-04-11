from __future__ import annotations

from tests.helpers import load_module


def test_mock_standard_module_onboards_with_descriptor_and_shared_runtime_only(tmp_path):
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

    registry_mod.clear_formal_modules()
    descriptor = registry_mod.register_formal_module(fixture_mod.MOCK_STANDARD_MODULE)
    payload = runtime_mod.run_formal_materialize(
        descriptor=descriptor,
        job_name="mock_standard_materialize",
        report_date="2025-12-31",
        governance_dir=str(tmp_path / "governance"),
        lock_base_dir=str(tmp_path),
        execute_materialization=fixture_mod.run_mock_materialization,
    )

    assert descriptor.supports_standard_queries is True
    assert descriptor.supports_custom_queries is False
    assert payload["mock_rows"] == 2

