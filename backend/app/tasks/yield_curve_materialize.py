from __future__ import annotations

from pathlib import Path

from backend.app.core_finance.module_contracts import FormalComputeModuleDescriptor
from backend.app.core_finance.module_registry import ensure_formal_module
from backend.app.governance.settings import get_settings
from backend.app.repositories.akshare_adapter import VendorAdapter
from backend.app.repositories.yield_curve_repo import YieldCurveRepository
from backend.app.schemas.formal_compute_runtime import (
    FormalComputeMaterializeFailure,
    FormalComputeMaterializeResult,
)
from backend.app.tasks.broker import register_actor_once
from backend.app.tasks.formal_compute_runtime import run_formal_materialize


YIELD_CURVE_MODULE = ensure_formal_module(
    FormalComputeModuleDescriptor(
        module_name="yield_curve",
        basis="formal",
        input_sources=("akshare_yield_curve", "choice_yield_curve", "chinabond_gkh_yield_curve"),
        fact_tables=("fact_formal_yield_curve_daily",),
        rule_version="rv_yield_curve_formal_materialize_v1",
        cache_key_prefix="yield_curve:materialize",
        lock_key_prefix="lock:duckdb:{basis}:yield-curve:materialize",
        cache_version_prefix="cv_yield_curve",
        result_kind_family="yield-curve",
        supports_standard_queries=True,
        supports_custom_queries=False,
    )
)
CACHE_KEY = YIELD_CURVE_MODULE.cache_key
RULE_VERSION = YIELD_CURVE_MODULE.rule_version
CACHE_VERSION = YIELD_CURVE_MODULE.cache_version

SUPPORTED_CURVE_TYPES = ("treasury", "cdb", "aaa_credit")


def _normalize_curve_types(curve_types: tuple[str, ...]) -> tuple[str, ...]:
    normalized = tuple(str(curve_type).strip().lower() for curve_type in curve_types)
    unsupported = sorted({curve_type for curve_type in normalized if curve_type not in SUPPORTED_CURVE_TYPES})
    if unsupported:
        joined = ", ".join(unsupported)
        raise FormalComputeMaterializeFailure(
            source_version=f"sv_yield_curve_failed_unsupported_{joined.replace(',', '_').replace(' ', '')}",
            vendor_version="vv_none",
            message=f"Unsupported curve_type(s) for yield-curve / curve-effects stream: {joined}",
        )
    return normalized


def _execute_yield_curve_materialization(
    *,
    trade_date: str,
    curve_types: tuple[str, ...],
    duckdb_file: Path,
) -> FormalComputeMaterializeResult:
    curve_types = _normalize_curve_types(curve_types)
    adapter = VendorAdapter()
    repo = YieldCurveRepository(str(duckdb_file))

    snapshots = []
    for curve_type in curve_types:
        try:
            snapshots.append(adapter.fetch_yield_curve(curve_type=curve_type, trade_date=trade_date))
        except Exception as exc:
            raise FormalComputeMaterializeFailure(
                source_version=f"sv_yield_curve_failed_{trade_date.replace('-', '')}_{curve_type}",
                vendor_version="vv_none",
                message=f"Failed to materialize {curve_type} curve for trade_date={trade_date}: {exc}",
            ) from exc

    repo.replace_curve_snapshots(
        trade_date=trade_date,
        snapshots=snapshots,
        rule_version=RULE_VERSION,
    )

    source_version = "__".join(sorted({snapshot.source_version for snapshot in snapshots})) or "sv_yield_curve_empty"
    vendor_version = "__".join(sorted({snapshot.vendor_version for snapshot in snapshots})) or "vv_none"
    payload = {
        "curve_types": list(curve_types),
        "point_count": sum(len(snapshot.points) for snapshot in snapshots),
    }
    return FormalComputeMaterializeResult(
        source_version=source_version,
        vendor_version=vendor_version,
        payload=payload,
    )


def _materialize_yield_curve(
    *,
    trade_date: str,
    curve_types: list[str] | None = None,
    duckdb_path: str | None = None,
    governance_dir: str | None = None,
    run_id: str | None = None,
) -> dict[str, object]:
    settings = get_settings()
    duckdb_file = Path(duckdb_path or settings.duckdb_path)
    duckdb_file.parent.mkdir(parents=True, exist_ok=True)
    governance_path = Path(governance_dir or settings.governance_path)
    normalized_curve_types = tuple(curve_types or SUPPORTED_CURVE_TYPES)

    return run_formal_materialize(
        descriptor=YIELD_CURVE_MODULE,
        job_name="yield_curve_materialize",
        report_date=trade_date,
        governance_dir=str(governance_path),
        lock_base_dir=str(duckdb_file.parent),
        run_id=run_id,
        execute_materialization=lambda: _execute_yield_curve_materialization(
            trade_date=trade_date,
            curve_types=normalized_curve_types,
            duckdb_file=duckdb_file,
        ),
    )


materialize_yield_curve = register_actor_once(
    "materialize_yield_curve",
    _materialize_yield_curve,
)
