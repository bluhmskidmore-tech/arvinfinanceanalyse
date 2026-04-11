from __future__ import annotations

import pytest

from tests.helpers import load_module


def _load_registry_modules():
    contracts_mod = load_module(
        "backend.app.core_finance.module_contracts",
        "backend/app/core_finance/module_contracts.py",
    )
    registry_mod = load_module(
        "backend.app.core_finance.module_registry",
        "backend/app/core_finance/module_registry.py",
    )
    return contracts_mod, registry_mod


def _descriptor(contracts_mod, **overrides):
    payload = {
        "module_name": "mock_standard_module",
        "basis": "formal",
        "input_sources": ("mock_source",),
        "fact_tables": ("fact_formal_mock_standard_daily",),
        "rule_version": "rv_mock_standard_v1",
        "cache_key_prefix": "mock_standard:materialize",
        "lock_key_prefix": "lock:duckdb:{basis}:mock-standard:materialize",
        "cache_version_prefix": "cv_mock_standard",
        "result_kind_family": "mock-standard",
        "supports_standard_queries": True,
        "supports_custom_queries": False,
    }
    payload.update(overrides)
    return contracts_mod.FormalComputeModuleDescriptor(**payload)


def test_descriptor_rejects_non_formal_basis():
    contracts_mod, _registry_mod = _load_registry_modules()

    with pytest.raises(ValueError, match="formal"):
        _descriptor(contracts_mod, basis="scenario")


def test_descriptor_rejects_mixed_fact_table_domains():
    contracts_mod, _registry_mod = _load_registry_modules()

    with pytest.raises(ValueError, match="fact table"):
        _descriptor(
            contracts_mod,
            fact_tables=(
                "fact_formal_mock_standard_daily",
                "fact_scenario_mock_standard_daily",
            ),
        )


def test_registry_rejects_duplicate_module_names():
    contracts_mod, registry_mod = _load_registry_modules()
    registry_mod.clear_formal_modules()
    descriptor = _descriptor(contracts_mod)

    registry_mod.register_formal_module(descriptor)

    with pytest.raises(ValueError, match="already registered"):
        registry_mod.register_formal_module(descriptor)


def test_registry_rejects_duplicate_cache_keys_across_modules():
    contracts_mod, registry_mod = _load_registry_modules()
    registry_mod.clear_formal_modules()
    registry_mod.register_formal_module(_descriptor(contracts_mod))

    with pytest.raises(ValueError, match="cache_key"):
        registry_mod.register_formal_module(
            _descriptor(
                contracts_mod,
                module_name="other_module",
            )
        )


def test_registry_rejects_duplicate_lock_keys_across_modules():
    contracts_mod, registry_mod = _load_registry_modules()
    registry_mod.clear_formal_modules()
    registry_mod.register_formal_module(_descriptor(contracts_mod))

    with pytest.raises(ValueError, match="lock_key"):
        registry_mod.register_formal_module(
            _descriptor(
                contracts_mod,
                module_name="other_module",
                cache_key_prefix="other_module:materialize",
                cache_version_prefix="cv_other_module",
            )
        )


def test_registry_rejects_duplicate_cache_versions_across_modules():
    contracts_mod, registry_mod = _load_registry_modules()
    registry_mod.clear_formal_modules()
    registry_mod.register_formal_module(_descriptor(contracts_mod))

    with pytest.raises(ValueError, match="cache_version"):
        registry_mod.register_formal_module(
            _descriptor(
                contracts_mod,
                module_name="other_module",
                cache_key_prefix="other_module:materialize",
                lock_key_prefix="lock:duckdb:{basis}:other-module:materialize",
                cache_version_prefix="cv_mock_standard",
            )
        )


def test_registry_rejects_reused_fact_tables_across_modules():
    contracts_mod, registry_mod = _load_registry_modules()
    registry_mod.clear_formal_modules()
    registry_mod.register_formal_module(_descriptor(contracts_mod))

    with pytest.raises(ValueError, match="fact_tables"):
        registry_mod.register_formal_module(
            _descriptor(
                contracts_mod,
                module_name="other_module",
                cache_key_prefix="other_module:materialize",
                lock_key_prefix="lock:duckdb:{basis}:other-module:materialize",
                cache_version_prefix="cv_other_module",
            )
        )
