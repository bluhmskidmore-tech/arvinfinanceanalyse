from __future__ import annotations

from dataclasses import dataclass

from backend.app.core_finance.module_contracts import FormalComputeModuleDescriptor

CONFIGURED_CURRENT_VERSION_STATE = "configured_current"


def _require_non_blank(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} is required")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} is required")
    return normalized


def compose_risk_tensor_source_version(
    *,
    upstream_source_version: str,
    liability_source_version: str,
) -> str:
    """Compose the exact risk source summary from its persisted lineage fields."""

    normalized_upstream_source = _require_non_blank(
        upstream_source_version,
        field_name="risk_tensor.upstream_source_version",
    )
    if not isinstance(liability_source_version, str):
        raise ValueError("risk_tensor.liability_source_version must be an explicit string")
    normalized_liability_source = liability_source_version.strip()
    parts = ["sv_risk_tensor", normalized_upstream_source]
    if normalized_liability_source:
        parts.append(normalized_liability_source)
    return "__".join(parts)


@dataclass(slots=True, frozen=True)
class MaterializeModuleVersion:
    """Import-safe version metadata backed by the formal module descriptor."""

    job_name: str
    descriptor: FormalComputeModuleDescriptor

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "job_name",
            _require_non_blank(self.job_name, field_name="job_name"),
        )

    @property
    def module_name(self) -> str:
        return self.descriptor.module_name

    @property
    def basis(self) -> str:
        return self.descriptor.basis

    @property
    def rule_version(self) -> str:
        return self.descriptor.rule_version

    @property
    def result_kind_family(self) -> str:
        return self.descriptor.result_kind_family

    @property
    def input_sources(self) -> tuple[str, ...]:
        return self.descriptor.input_sources

    @property
    def fact_tables(self) -> tuple[str, ...]:
        return self.descriptor.fact_tables

    @property
    def cache_key(self) -> str:
        return self.descriptor.cache_key

    @property
    def cache_version(self) -> str:
        return self.descriptor.cache_version

    @property
    def running_source_version(self) -> str:
        return self.descriptor.running_source_version

    @property
    def stable_output_version(self) -> str:
        return self.descriptor.stable_output_version

    @property
    def vendor_version(self) -> str:
        return self.descriptor.vendor_version

    @property
    def lock_key(self) -> str:
        return self.descriptor.lock_key

    @property
    def lock_ttl_seconds(self) -> int:
        return self.descriptor.lock_ttl_seconds

    def emit_descriptor_fragment(self) -> dict[str, object]:
        """Return configured metadata without claiming owner approval or release eligibility."""

        return {
            "module_name": self.module_name,
            "job_name": self.job_name,
            "basis": self.basis,
            "rule_version": self.rule_version,
            "cache_key": self.cache_key,
            "cache_version": self.cache_version,
            "running_source_version": self.running_source_version,
            "stable_output_version": self.stable_output_version,
            "vendor_version": self.vendor_version,
            "lock_key": self.lock_key,
            "lock_ttl_seconds": self.lock_ttl_seconds,
            "result_kind_family": self.result_kind_family,
            "supports_standard_queries": self.descriptor.supports_standard_queries,
            "supports_custom_queries": self.descriptor.supports_custom_queries,
            "input_sources": list(self.input_sources),
            "fact_tables": list(self.fact_tables),
        }

    def emit_runtime_lineage(
        self,
        *,
        run_id: str,
        report_date: str,
        source_version: str,
        vendor_version: str,
    ) -> dict[str, object]:
        """Bind descriptor metadata to lineage observed during one materialization run."""

        normalized_vendor_version = _require_non_blank(
            vendor_version,
            field_name=f"{self.module_name}.vendor_version",
        )
        return {
            "cache_key": self.cache_key,
            "cache_version": self.stable_output_version,
            "source_version": _require_non_blank(
                source_version,
                field_name=f"{self.module_name}.source_version",
            ),
            "vendor_version": normalized_vendor_version,
            "rule_version": self.rule_version,
            "basis": self.basis,
            "module_name": self.module_name,
            "result_kind_family": self.result_kind_family,
            "run_id": _require_non_blank(run_id, field_name=f"{self.module_name}.run_id"),
            "report_date": _require_non_blank(
                report_date,
                field_name=f"{self.module_name}.report_date",
            ),
            "input_sources": list(self.input_sources),
            "fact_tables": list(self.fact_tables),
        }

    def emit_manifest_min_lineage(
        self,
        *,
        run_id: str,
        report_date: str,
        source_version: str,
        vendor_version: str,
    ) -> dict[str, object]:
        """Match the existing formal-compute manifest lineage subset exactly."""

        runtime_lineage = self.emit_runtime_lineage(
            run_id=run_id,
            report_date=report_date,
            source_version=source_version,
            vendor_version=vendor_version,
        )
        return {key: value for key, value in runtime_lineage.items() if key not in {"cache_key", "cache_version"}}


@dataclass(slots=True, frozen=True)
class FixedIncomeVersionSet:
    """Configured-current fixed-income versions and explicit runtime lineage emitters."""

    engine_rule_version: str
    bond_analytics: MaterializeModuleVersion
    risk_tensor: MaterializeModuleVersion

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "engine_rule_version",
            _require_non_blank(
                self.engine_rule_version,
                field_name="engine_rule_version",
            ),
        )

    def emit_configured_current_fragment(self) -> dict[str, object]:
        """Disclose configured versions before a runner starts.

        ``configured_current`` describes code configuration only. It does not mean the
        versions are owner-approved, frozen, release-eligible, or promoted.
        """

        return {
            "version_state": CONFIGURED_CURRENT_VERSION_STATE,
            "engine_rule_version": self.engine_rule_version,
            "bond_analytics": self.bond_analytics.emit_descriptor_fragment(),
            "risk_tensor": self.risk_tensor.emit_descriptor_fragment(),
        }

    def emit_runtime_fragment(
        self,
        *,
        run_id: str,
        report_date: str,
        bond_source_version: str,
        bond_vendor_version: str,
        risk_source_version: str,
        risk_vendor_version: str,
        risk_upstream_source_version: str,
        risk_upstream_rule_version: str,
        risk_upstream_cache_version: str,
        liability_source_version: str,
        liability_rule_version: str,
    ) -> dict[str, object]:
        """Bind dynamic source, upstream, and liability lineage to configured versions."""

        bond_lineage = self.bond_analytics.emit_runtime_lineage(
            run_id=run_id,
            report_date=report_date,
            source_version=bond_source_version,
            vendor_version=bond_vendor_version,
        )
        risk_lineage = self.risk_tensor.emit_runtime_lineage(
            run_id=run_id,
            report_date=report_date,
            source_version=risk_source_version,
            vendor_version=risk_vendor_version,
        )
        normalized_upstream_source = _require_non_blank(
            risk_upstream_source_version,
            field_name="risk_tensor.upstream_source_version",
        )
        normalized_upstream_rule = _require_non_blank(
            risk_upstream_rule_version,
            field_name="risk_tensor.upstream_rule_version",
        )
        normalized_upstream_cache = _require_non_blank(
            risk_upstream_cache_version,
            field_name="risk_tensor.upstream_cache_version",
        )
        if normalized_upstream_source != bond_lineage["source_version"]:
            raise ValueError("risk_tensor upstream source_version must match bond runtime lineage")
        if normalized_upstream_rule != self.bond_analytics.rule_version:
            raise ValueError("risk_tensor upstream rule_version must match bond descriptor")
        if normalized_upstream_cache != self.bond_analytics.stable_output_version:
            raise ValueError("risk_tensor upstream cache_version must match bond descriptor")

        if not isinstance(liability_source_version, str) or not isinstance(
            liability_rule_version,
            str,
        ):
            raise ValueError("liability source_version and rule_version must be explicit strings")
        normalized_liability_source = liability_source_version.strip()
        normalized_liability_rule = liability_rule_version.strip()
        if bool(normalized_liability_source) != bool(normalized_liability_rule):
            raise ValueError("liability source_version and rule_version must either both be set or both be empty")
        expected_risk_source = compose_risk_tensor_source_version(
            upstream_source_version=normalized_upstream_source,
            liability_source_version=normalized_liability_source,
        )
        if risk_lineage["source_version"] != expected_risk_source:
            raise ValueError("risk_tensor.source_version must exactly encode upstream and liability lineage")

        fragment = self.emit_configured_current_fragment()
        fragment["runtime"] = {
            "bond_analytics": bond_lineage,
            "risk_tensor": {
                **risk_lineage,
                "upstream_lineage": {
                    "source_version": normalized_upstream_source,
                    "rule_version": normalized_upstream_rule,
                    "cache_version": normalized_upstream_cache,
                },
                "liability_lineage": {
                    "source_version": normalized_liability_source,
                    "rule_version": normalized_liability_rule,
                },
            },
        }
        return fragment


FIXED_INCOME_VERSION_SET = FixedIncomeVersionSet(
    engine_rule_version="rv_bond_analytics_engine_v3",
    bond_analytics=MaterializeModuleVersion(
        job_name="bond_analytics_materialize",
        descriptor=FormalComputeModuleDescriptor(
            module_name="bond_analytics",
            basis="formal",
            input_sources=("zqtz_bond_daily_snapshot",),
            fact_tables=("fact_formal_bond_analytics_daily",),
            rule_version="rv_bond_analytics_formal_materialize_v6",
            result_kind_family="bond-analytics",
            supports_standard_queries=True,
            supports_custom_queries=True,
        ),
    ),
    risk_tensor=MaterializeModuleVersion(
        job_name="risk_tensor_materialize",
        descriptor=FormalComputeModuleDescriptor(
            module_name="risk_tensor",
            basis="formal",
            input_sources=(
                "fact_formal_bond_analytics_daily",
                "fact_formal_tyw_balance_daily",
            ),
            fact_tables=("fact_formal_risk_tensor_daily",),
            rule_version="rv_risk_tensor_formal_materialize_v12",
            result_kind_family="risk-tensor",
            supports_standard_queries=True,
            supports_custom_queries=False,
        ),
    ),
)


__all__ = [
    "CONFIGURED_CURRENT_VERSION_STATE",
    "FIXED_INCOME_VERSION_SET",
    "FixedIncomeVersionSet",
    "MaterializeModuleVersion",
]
