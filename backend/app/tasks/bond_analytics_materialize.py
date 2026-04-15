from __future__ import annotations

from datetime import date
from pathlib import Path

from backend.app.core_finance.bond_analytics.engine import (
    MISSING_SOURCE_VERSION,
    compute_bond_analytics_rows,
)
from backend.app.core_finance.module_contracts import FormalComputeModuleDescriptor
from backend.app.core_finance.module_registry import ensure_formal_module
from backend.app.governance.settings import get_settings
from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository
from backend.app.schemas.formal_compute_runtime import (
    FormalComputeMaterializeFailure,
    FormalComputeMaterializeResult,
)
from backend.app.tasks.broker import register_actor_once
from backend.app.tasks.formal_compute_runtime import run_formal_materialize


BOND_ANALYTICS_MODULE = ensure_formal_module(
    FormalComputeModuleDescriptor(
        module_name="bond_analytics",
        basis="formal",
        input_sources=("zqtz_bond_daily_snapshot",),
        fact_tables=("fact_formal_bond_analytics_daily",),
        rule_version="rv_bond_analytics_formal_materialize_v1",
        result_kind_family="bond-analytics",
        supports_standard_queries=True,
        supports_custom_queries=True,
    )
)
BOND_ANALYTICS_FORMAL_BASIS = BOND_ANALYTICS_MODULE.basis
CACHE_KEY = BOND_ANALYTICS_MODULE.cache_key
BOND_ANALYTICS_LOCK = BOND_ANALYTICS_MODULE.lock_definition
RULE_VERSION = BOND_ANALYTICS_MODULE.rule_version
CACHE_VERSION = BOND_ANALYTICS_MODULE.cache_version


def _execute_bond_analytics_materialization(
    *,
    report_date: str,
    duckdb_file: Path,
) -> FormalComputeMaterializeResult:
    repo = BondAnalyticsRepository(str(duckdb_file))
    snapshot_rows = repo.load_snapshot_rows(report_date)
    combined_source_version = _combine_source_versions(snapshot_rows)

    try:
        analytics_rows = compute_bond_analytics_rows(
            snapshot_rows,
            date.fromisoformat(report_date),
        )
        repo.replace_bond_analytics_rows(
            report_date=report_date,
            rows=analytics_rows,
        )
    except Exception as exc:
        raise FormalComputeMaterializeFailure(
            source_version=combined_source_version,
            vendor_version="vv_none",
            message=str(exc),
        ) from exc

    return FormalComputeMaterializeResult(
        source_version=combined_source_version,
        vendor_version="vv_none",
        payload={
            "row_count": len(analytics_rows),
        },
    )


def _materialize_bond_analytics_facts(
    *,
    report_date: str,
    duckdb_path: str | None = None,
    governance_dir: str | None = None,
    run_id: str | None = None,
) -> dict[str, object]:
    settings = get_settings()
    duckdb_file = Path(duckdb_path or settings.duckdb_path)
    duckdb_file.parent.mkdir(parents=True, exist_ok=True)
    governance_path = Path(governance_dir or settings.governance_path)

    return run_formal_materialize(
        descriptor=BOND_ANALYTICS_MODULE,
        job_name="bond_analytics_materialize",
        report_date=report_date,
        governance_dir=str(governance_path),
        lock_base_dir=str(duckdb_file.parent),
        run_id=run_id,
        execute_materialization=lambda: _execute_bond_analytics_materialization(
            report_date=report_date,
            duckdb_file=duckdb_file,
        ),
    )


materialize_bond_analytics_facts = register_actor_once(
    "materialize_bond_analytics_facts",
    _materialize_bond_analytics_facts,
)


def _combine_source_versions(snapshot_rows: list[dict[str, object]]) -> str:
    values = sorted(
        {
            str(row.get("source_version") or "").strip() or MISSING_SOURCE_VERSION
            for row in snapshot_rows
        }
    )
    return "__".join(values) or "sv_bond_analytics_empty"
