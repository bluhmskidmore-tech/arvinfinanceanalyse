from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from backend.app.core_finance.bond_analytics.engine import (
    MISSING_SOURCE_VERSION,
    FormalCNYClosureError,
    compute_bond_analytics_rows,
)
from backend.app.core_finance.module_contracts import FormalComputeModuleDescriptor
from backend.app.core_finance.module_registry import ensure_formal_module
from backend.app.governance.settings import get_settings
from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository
from backend.app.repositories.task_write_guard import repository_task_write_scope
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
logger = logging.getLogger(__name__)


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
        with repository_task_write_scope(__name__):
            repo.replace_bond_analytics_rows(
                report_date=report_date,
                rows=analytics_rows,
            )
    except FormalCNYClosureError as exc:
        try:
            with repository_task_write_scope(__name__):
                repo.invalidate_report_date_facts(report_date=report_date)
        except Exception as invalidation_exc:
            raise FormalComputeMaterializeFailure(
                source_version=combined_source_version,
                vendor_version="vv_none",
                message=(
                    f"{exc}; failed to invalidate stale facts for report_date={report_date}: "
                    f"{invalidation_exc}"
                ),
            ) from invalidation_exc
        raise FormalComputeMaterializeFailure(
            source_version=combined_source_version,
            vendor_version="vv_none",
            message=str(exc),
        ) from exc
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


def ensure_yield_curve_inputs_on_or_before(*args: object, **kwargs: object) -> object:
    from backend.app.tasks.yield_curve_materialize import (
        ensure_yield_curve_inputs_on_or_before as _ensure,
    )

    return _ensure(*args, **kwargs)


def _yield_curve_anchor_dates_for_materialization(
    *,
    duckdb_path: str,
    report_date: str,
) -> tuple[str, ...]:
    report_dt = date.fromisoformat(report_date)
    anchors = {
        report_dt.isoformat(),
        report_dt.replace(day=1).isoformat(),
    }
    prior_balance_date = BondAnalyticsRepository(duckdb_path).resolve_prior_curve_anchor_report_date(
        report_date=report_date,
    )
    if prior_balance_date:
        anchors.add(prior_balance_date)
    return tuple(sorted(anchors))


def _execute_bond_analytics_with_curve_preparation(
    *,
    report_date: str,
    duckdb_file: Path,
) -> FormalComputeMaterializeResult:
    try:
        ensure_yield_curve_inputs_on_or_before(
            anchor_dates=_yield_curve_anchor_dates_for_materialization(
                duckdb_path=str(duckdb_file),
                report_date=report_date,
            ),
            duckdb_path=str(duckdb_file),
        )
    except Exception as exc:
        raise FormalComputeMaterializeFailure(
            source_version=BOND_ANALYTICS_MODULE.running_source_version,
            vendor_version="vv_none",
            message=f"yield_curve_prepare_failed: {exc}",
        ) from exc
    return _execute_bond_analytics_materialization(
        report_date=report_date,
        duckdb_file=duckdb_file,
    )


def _invalidate_bond_analytics_worker_caches(report_date: str) -> None:
    cache_clearers = (
        (
            "bond analytics",
            lambda: _invalidate_bond_analytics_cache_for_report_date(report_date),
        ),
        ("bond dashboard", _clear_bond_dashboard_cache),
        ("risk tensor", _invalidate_risk_tensor_cache),
        ("Campisi attribution", _clear_campisi_cache),
        ("PnL attribution", _invalidate_pnl_attribution_cache),
        ("executive home snapshot", _invalidate_executive_home_cache),
        ("dashboard", _invalidate_dashboard_cache),
    )
    for cache_name, clear_cache in cache_clearers:
        try:
            clear_cache()
        except Exception as exc:  # pragma: no cover - cache clearing must not fail materialization
            logger.warning("failed to clear %s runtime cache: %s", cache_name, exc)


def _invalidate_bond_analytics_cache_for_report_date(report_date: str) -> None:
    from backend.app.services.bond_analytics_service import (
        _invalidate_bond_analytics_caches_for_report_date,
    )

    _invalidate_bond_analytics_caches_for_report_date(report_date)


def _clear_bond_dashboard_cache() -> None:
    from backend.app.services.bond_dashboard_service import clear_bond_dashboard_runtime_cache

    clear_bond_dashboard_runtime_cache()


def _invalidate_risk_tensor_cache() -> None:
    from backend.app.services.risk_tensor_service import invalidate_risk_tensor_read_cache

    invalidate_risk_tensor_read_cache()


def _clear_campisi_cache() -> None:
    from backend.app.services.campisi_attribution_service import (
        clear_campisi_four_effects_runtime_cache,
    )

    clear_campisi_four_effects_runtime_cache()


def _invalidate_pnl_attribution_cache() -> None:
    from backend.app.services.pnl_attribution_service import invalidate_pnl_attribution_read_cache

    invalidate_pnl_attribution_read_cache()


def _invalidate_executive_home_cache() -> None:
    from backend.app.services.executive_service import invalidate_home_snapshot_cache

    invalidate_home_snapshot_cache()


def _invalidate_dashboard_cache() -> None:
    from backend.app.services.dashboard_service import invalidate_dashboard_cache

    invalidate_dashboard_cache()


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

    try:
        return run_formal_materialize(
            descriptor=BOND_ANALYTICS_MODULE,
            job_name="bond_analytics_materialize",
            report_date=report_date,
            governance_dir=str(governance_path),
            lock_base_dir=str(duckdb_file.parent),
            duckdb_path=str(duckdb_file),
            run_id=run_id,
            execute_materialization=lambda: _execute_bond_analytics_with_curve_preparation(
                report_date=report_date,
                duckdb_file=duckdb_file,
            ),
        )
    finally:
        _invalidate_bond_analytics_worker_caches(report_date)


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
