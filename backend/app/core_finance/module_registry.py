from __future__ import annotations

import sys

from backend.app.core_finance.module_contracts import FormalComputeModuleDescriptor


_FORMAL_MODULES: dict[str, FormalComputeModuleDescriptor] = {}
_FORMAL_FACT_TABLE_TO_MODULE: dict[str, str] = {}
_FORMAL_RESULT_KIND_FAMILY_TO_MODULE: dict[str, str] = {}


def clear_formal_modules() -> None:
    _FORMAL_MODULES.clear()
    _FORMAL_FACT_TABLE_TO_MODULE.clear()
    _FORMAL_RESULT_KIND_FAMILY_TO_MODULE.clear()
    _purge_loaded_formal_module_dependents()


def register_formal_module(
    descriptor: FormalComputeModuleDescriptor,
) -> FormalComputeModuleDescriptor:
    existing = _FORMAL_MODULES.get(descriptor.module_name)
    if existing is not None:
        raise ValueError(f"Formal compute module {descriptor.module_name!r} is already registered")
    _assert_no_identity_collisions(descriptor)
    _FORMAL_MODULES[descriptor.module_name] = descriptor
    _bind_module_indexes(descriptor)
    return descriptor


def ensure_formal_module(
    descriptor: FormalComputeModuleDescriptor,
) -> FormalComputeModuleDescriptor:
    existing = _FORMAL_MODULES.get(descriptor.module_name)
    if existing is None:
        _assert_no_identity_collisions(descriptor)
        _FORMAL_MODULES[descriptor.module_name] = descriptor
        _bind_module_indexes(descriptor)
        return descriptor
    if existing != descriptor:
        raise ValueError(
            f"Formal compute module {descriptor.module_name!r} is already registered with a different descriptor"
        )
    return existing


def get_formal_module(module_name: str) -> FormalComputeModuleDescriptor:
    try:
        return _FORMAL_MODULES[module_name]
    except KeyError as exc:
        raise KeyError(f"Unknown formal compute module {module_name!r}") from exc


def get_formal_module_by_fact_table(fact_table: str) -> FormalComputeModuleDescriptor:
    module_name = _FORMAL_FACT_TABLE_TO_MODULE.get(fact_table)
    if module_name is None:
        raise KeyError(f"Unknown formal fact table {fact_table!r}")
    return get_formal_module(module_name)


def require_registered_formal_module(
    descriptor: FormalComputeModuleDescriptor,
) -> FormalComputeModuleDescriptor:
    existing = _FORMAL_MODULES.get(descriptor.module_name)
    if existing is None:
        raise ValueError(
            f"Formal compute module {descriptor.module_name!r} is not registered in module_registry"
        )
    if existing != descriptor:
        raise ValueError(
            f"Formal compute module {descriptor.module_name!r} must use the registered descriptor from module_registry"
        )
    return existing


def list_formal_modules() -> tuple[FormalComputeModuleDescriptor, ...]:
    return tuple(_FORMAL_MODULES.values())


def _assert_no_identity_collisions(
    descriptor: FormalComputeModuleDescriptor,
) -> None:
    for existing in _FORMAL_MODULES.values():
        if existing.cache_key == descriptor.cache_key:
            raise ValueError(
                f"Formal compute module {descriptor.module_name!r} reuses cache_key {descriptor.cache_key!r}"
            )
        if existing.cache_version == descriptor.cache_version:
            raise ValueError(
                f"Formal compute module {descriptor.module_name!r} reuses cache_version {descriptor.cache_version!r}"
            )
        if existing.lock_key == descriptor.lock_key:
            raise ValueError(
                f"Formal compute module {descriptor.module_name!r} reuses lock_key {descriptor.lock_key!r}"
            )
        overlapping_fact_tables = sorted(set(existing.fact_tables) & set(descriptor.fact_tables))
        if overlapping_fact_tables:
            raise ValueError(
                f"Formal compute module {descriptor.module_name!r} reuses fact_tables {overlapping_fact_tables!r}"
            )
        if existing.result_kind_family == descriptor.result_kind_family:
            raise ValueError(
                "Formal compute module "
                f"{descriptor.module_name!r} reuses result_kind_family {descriptor.result_kind_family!r}"
            )


def _bind_module_indexes(
    descriptor: FormalComputeModuleDescriptor,
) -> None:
    _FORMAL_RESULT_KIND_FAMILY_TO_MODULE[descriptor.result_kind_family] = descriptor.module_name
    for fact_table in descriptor.fact_tables:
        _FORMAL_FACT_TABLE_TO_MODULE[fact_table] = descriptor.module_name


def _purge_loaded_formal_module_dependents() -> None:
    module_prefixes = (
        "backend.app.tasks.balance_analysis_materialize",
        "backend.app.tasks.bond_analytics_materialize",
        "backend.app.tasks.pnl_materialize",
        "backend.app.tasks.risk_tensor_materialize",
        "backend.app.tasks.yield_curve_materialize",
        "backend.app.services.balance_analysis_service",
        "backend.app.services.bond_analytics_service",
        "backend.app.services.pnl_bridge_service",
        "backend.app.services.pnl_service",
        "backend.app.services.risk_tensor_service",
    )
    for loaded_name in list(sys.modules):
        if loaded_name in module_prefixes:
            sys.modules.pop(loaded_name, None)
