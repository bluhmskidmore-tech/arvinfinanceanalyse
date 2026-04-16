from __future__ import annotations

from pathlib import Path

from tests.helpers import load_module


def test_balance_analysis_module_descriptor_matches_runtime_contract():
    registry_mod = load_module(
        "backend.app.core_finance.module_registry",
        "backend/app/core_finance/module_registry.py",
    )
    task_mod = load_module(
        "backend.app.tasks.balance_analysis_materialize",
        "backend/app/tasks/balance_analysis_materialize.py",
    )

    descriptor = registry_mod.get_formal_module("balance_analysis")
    by_zqtz_fact_table = registry_mod.get_formal_module_by_fact_table("fact_formal_zqtz_balance_daily")
    by_tyw_fact_table = registry_mod.get_formal_module_by_fact_table("fact_formal_tyw_balance_daily")
    service_mod = load_module(
        "backend.app.services.balance_analysis_service",
        "backend/app/services/balance_analysis_service.py",
    )

    assert descriptor.fact_tables == (
        "fact_formal_zqtz_balance_daily",
        "fact_formal_tyw_balance_daily",
    )
    assert by_zqtz_fact_table == descriptor
    assert by_tyw_fact_table == descriptor
    assert descriptor.cache_key == task_mod.CACHE_KEY
    assert descriptor.lock_key == task_mod.BALANCE_ANALYSIS_LOCK.key
    assert descriptor.cache_version == task_mod.CACHE_VERSION
    assert descriptor.result_kind_family == "balance-analysis"
    assert service_mod.BALANCE_ANALYSIS_MODULE == descriptor
    assert service_mod.CACHE_KEY == descriptor.cache_key
    assert service_mod.CACHE_VERSION == descriptor.cache_version
    assert service_mod.RULE_VERSION == descriptor.rule_version
    assert service_mod.BALANCE_ANALYSIS_LOCK.key == descriptor.lock_key


def test_balance_analysis_materialize_uses_schema_failure_contract():
    path = Path(__file__).resolve().parents[1] / "backend" / "app" / "tasks" / "balance_analysis_materialize.py"
    src = path.read_text(encoding="utf-8")

    assert "backend.app.schemas.formal_compute_runtime" in src
    assert "FormalComputeMaterializeFailure" in src
    assert "from backend.app.tasks.formal_compute_runtime import run_formal_materialize" in src
    assert "FormalComputeMaterializeFailure,\n    run_formal_materialize" not in src
