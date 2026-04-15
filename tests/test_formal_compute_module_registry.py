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


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("module_name", " "),
        ("rule_version", " "),
        ("result_kind_family", " "),
    ],
)
def test_descriptor_requires_minimal_identity_fields(field_name, value):
    contracts_mod, _registry_mod = _load_registry_modules()

    with pytest.raises(ValueError, match="required"):
        _descriptor(contracts_mod, **{field_name: value})


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

    other = _descriptor(
        contracts_mod,
        module_name="other_module",
        fact_tables=("fact_formal_other_module_daily",),
        result_kind_family="other-module",
    )
    registry_mod.register_formal_module(other)

    current = registry_mod.get_formal_module("mock_standard_module")
    assert current.cache_key != other.cache_key


def test_registry_rejects_duplicate_lock_keys_across_modules():
    contracts_mod, registry_mod = _load_registry_modules()
    registry_mod.clear_formal_modules()
    registry_mod.register_formal_module(_descriptor(contracts_mod))

    other = _descriptor(
        contracts_mod,
        module_name="other_module",
        fact_tables=("fact_formal_other_module_daily",),
        result_kind_family="other-module",
    )
    registry_mod.register_formal_module(other)

    current = registry_mod.get_formal_module("mock_standard_module")
    assert current.lock_key != other.lock_key


def test_registry_rejects_duplicate_cache_versions_across_modules():
    contracts_mod, registry_mod = _load_registry_modules()
    registry_mod.clear_formal_modules()
    registry_mod.register_formal_module(_descriptor(contracts_mod))

    other = _descriptor(
        contracts_mod,
        module_name="other_module",
        fact_tables=("fact_formal_other_module_daily",),
        result_kind_family="other-module",
        rule_version="rv_mock_standard_v2",
    )
    registry_mod.register_formal_module(other)

    current = registry_mod.get_formal_module("mock_standard_module")
    assert current.cache_version != other.cache_version


def test_registry_rejects_reused_fact_tables_across_modules():
    contracts_mod, registry_mod = _load_registry_modules()
    registry_mod.clear_formal_modules()
    registry_mod.register_formal_module(_descriptor(contracts_mod))

    with pytest.raises(ValueError, match="fact_tables"):
        registry_mod.register_formal_module(
            _descriptor(
                contracts_mod,
                module_name="other_module",
            )
        )


def test_registry_rejects_reused_result_kind_family_across_modules():
    contracts_mod, registry_mod = _load_registry_modules()
    registry_mod.clear_formal_modules()
    registry_mod.register_formal_module(_descriptor(contracts_mod))

    with pytest.raises(ValueError, match="result_kind_family"):
        registry_mod.register_formal_module(
            _descriptor(
                contracts_mod,
                module_name="other_module",
                fact_tables=("fact_formal_other_module_daily",),
            )
        )


def test_registry_supports_lookup_module_by_fact_table():
    contracts_mod, registry_mod = _load_registry_modules()
    registry_mod.clear_formal_modules()
    descriptor = registry_mod.register_formal_module(_descriptor(contracts_mod))

    resolved = registry_mod.get_formal_module_by_fact_table("fact_formal_mock_standard_daily")
    assert resolved == descriptor

    with pytest.raises(KeyError, match="Unknown formal fact table"):
        registry_mod.get_formal_module_by_fact_table("fact_formal_unknown_daily")


def test_descriptor_uses_canonical_identity_rules():
    contracts_mod, _registry_mod = _load_registry_modules()
    descriptor = _descriptor(contracts_mod)

    assert descriptor.cache_key == "mock_standard_module:materialize:formal"
    assert descriptor.lock_key == "lock:duckdb:formal:mock-standard-module:materialize"
    assert descriptor.cache_version == "cv_mock_standard_module_formal__rv_mock_standard_v1"
    assert descriptor.stable_output_version == descriptor.cache_version
    assert descriptor.running_source_version == "sv_mock_standard_module_running"
