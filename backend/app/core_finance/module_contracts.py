from __future__ import annotations

from dataclasses import dataclass

from backend.app.governance.locks import LockDefinition


_ALLOWED_GOVERNED_FACT_PREFIXES = ("fact_formal_", "fact_nonstd_")


@dataclass(slots=True, frozen=True)
class FormalComputeModuleDescriptor:
    module_name: str
    basis: str
    input_sources: tuple[str, ...]
    fact_tables: tuple[str, ...]
    rule_version: str
    result_kind_family: str
    supports_standard_queries: bool = True
    supports_custom_queries: bool = False
    lock_ttl_seconds: int = 900
    vendor_version: str = "vv_none"
    cache_key_override: str | None = None
    lock_key_override: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "input_sources", tuple(self.input_sources))
        object.__setattr__(self, "fact_tables", tuple(self.fact_tables))

        if not self.module_name.strip():
            raise ValueError("module_name is required")
        if self.basis != "formal":
            raise ValueError("formal compute module descriptors must use basis='formal'")
        if not self.fact_tables:
            raise ValueError("At least one fact table is required")
        if any(
            not table.startswith(_ALLOWED_GOVERNED_FACT_PREFIXES)
            for table in self.fact_tables
        ):
            raise ValueError("Each fact table must remain inside the governed fact namespace")
        if not self.rule_version.strip():
            raise ValueError("rule_version is required")
        if not self.result_kind_family.strip():
            raise ValueError("result_kind_family is required")
        if self.cache_key_override is not None:
            cache_key_override = self.cache_key_override.strip()
            if not cache_key_override:
                raise ValueError("cache_key_override must be non-empty when provided")
            if not cache_key_override.endswith(f":{self.basis}"):
                raise ValueError("cache_key_override must remain basis-scoped")
            object.__setattr__(self, "cache_key_override", cache_key_override)
        if self.lock_key_override is not None:
            lock_key_override = self.lock_key_override.strip()
            if not lock_key_override:
                raise ValueError("lock_key_override must be non-empty when provided")
            if f":{self.basis}:" not in lock_key_override:
                raise ValueError("lock_key_override must remain basis-scoped")
            object.__setattr__(self, "lock_key_override", lock_key_override)

    @property
    def module_slug(self) -> str:
        return self.module_name.replace("_", "-")

    @property
    def cache_key(self) -> str:
        if self.cache_key_override is not None:
            return self.cache_key_override
        return f"{self.module_name}:materialize:{self.basis}"

    @property
    def lock_key(self) -> str:
        if self.lock_key_override is not None:
            return self.lock_key_override
        return f"lock:duckdb:formal:{self.module_slug}:materialize"

    @property
    def cache_version(self) -> str:
        # Stable output contract: one module + one rule_version -> one immutable cache version.
        return f"cv_{self.module_name}_{self.basis}__{self.rule_version}"

    @property
    def running_source_version(self) -> str:
        # Running marker contract: ephemeral in-flight source version, only for runtime status.
        return f"sv_{self.module_name}_running"

    @property
    def stable_output_version(self) -> str:
        # Stable marker contract: canonical version identifier for published formal outputs.
        return self.cache_version

    @property
    def lock_definition(self) -> LockDefinition:
        return LockDefinition(key=self.lock_key, ttl_seconds=self.lock_ttl_seconds)
