from __future__ import annotations

from backend.app.core_finance.module_contracts import FormalComputeModuleDescriptor


_FORMAL_MODULES: dict[str, FormalComputeModuleDescriptor] = {}


def clear_formal_modules() -> None:
    _FORMAL_MODULES.clear()


def register_formal_module(
    descriptor: FormalComputeModuleDescriptor,
) -> FormalComputeModuleDescriptor:
    existing = _FORMAL_MODULES.get(descriptor.module_name)
    if existing is not None:
        raise ValueError(f"Formal compute module {descriptor.module_name!r} is already registered")
    _assert_no_identity_collisions(descriptor)
    _FORMAL_MODULES[descriptor.module_name] = descriptor
    return descriptor


def ensure_formal_module(
    descriptor: FormalComputeModuleDescriptor,
) -> FormalComputeModuleDescriptor:
    existing = _FORMAL_MODULES.get(descriptor.module_name)
    if existing is None:
        _assert_no_identity_collisions(descriptor)
        _FORMAL_MODULES[descriptor.module_name] = descriptor
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
