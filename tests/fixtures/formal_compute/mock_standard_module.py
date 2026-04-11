from __future__ import annotations

from backend.app.core_finance.module_contracts import FormalComputeModuleDescriptor


MOCK_STANDARD_MODULE = FormalComputeModuleDescriptor(
    module_name="mock_standard_module",
    basis="formal",
    input_sources=("mock_source",),
    fact_tables=("fact_formal_mock_standard_daily",),
    rule_version="rv_mock_standard_v1",
    cache_key_prefix="mock_standard:materialize",
    lock_key_prefix="lock:duckdb:{basis}:mock-standard:materialize",
    cache_version_prefix="cv_mock_standard",
    result_kind_family="mock-standard",
    supports_standard_queries=True,
    supports_custom_queries=False,
)


def run_mock_materialization() -> dict[str, object]:
    return {
        "source_version": "sv_mock_standard_v1",
        "vendor_version": "vv_none",
        "payload": {
            "mock_rows": 2,
        },
    }


def run_mock_failure() -> dict[str, object]:
    raise RuntimeError("mock failure")
