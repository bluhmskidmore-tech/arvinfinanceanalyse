from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from time import perf_counter

import duckdb
from backend.app.core_finance.bond_analytics.engine import (
    MISSING_SOURCE_VERSION,
    FormalCNYClosureError,
    compute_bond_analytics_rows,
)
from backend.app.core_finance.fixed_income_version_set import FIXED_INCOME_VERSION_SET
from backend.app.core_finance.module_registry import ensure_formal_module
from backend.app.governance.locks import LockDefinition
from backend.app.governance.settings import get_settings
from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository
from backend.app.repositories.governance_repo import CACHE_BUILD_RUN_STREAM, GovernanceRepository
from backend.app.repositories.task_write_guard import repository_task_write_scope
from backend.app.schemas.curve_recovery import (
    CURVE_RECOVERY_TYPES,
    normalize_curve_recovery_options,
)
from backend.app.schemas.formal_compute_runtime import (
    FormalComputeMaterializeFailure,
    FormalComputeMaterializeResult,
)
from backend.app.tasks.broker import register_actor_once
from backend.app.tasks.formal_compute_runtime import run_formal_materialize

_BOND_ANALYTICS_VERSION = FIXED_INCOME_VERSION_SET.bond_analytics
BOND_ANALYTICS_MODULE = ensure_formal_module(_BOND_ANALYTICS_VERSION.descriptor)
BOND_ANALYTICS_FORMAL_BASIS = BOND_ANALYTICS_MODULE.basis
CACHE_KEY = BOND_ANALYTICS_MODULE.cache_key
BOND_ANALYTICS_LOCK = LockDefinition(
    key=BOND_ANALYTICS_MODULE.lock_key,
    ttl_seconds=BOND_ANALYTICS_MODULE.lock_ttl_seconds,
)
RULE_VERSION = BOND_ANALYTICS_MODULE.rule_version
CACHE_VERSION = BOND_ANALYTICS_MODULE.cache_version
logger = logging.getLogger(__name__)
MAX_CURVE_RECOVERY_LOOKBACK_DAYS = 40
CURVE_VENDOR_TIMEOUT_SECONDS = 180.0


@dataclass
class _BondRunDiagnostics:
    governance_repo: GovernanceRepository
    run_id: str
    report_date: str
    started_at: str
    phase_timings_seconds: dict[str, float] = dataclass_field(default_factory=dict)


_ACTIVE_BOND_RUN: ContextVar[_BondRunDiagnostics | None] = ContextVar("bond_run_diagnostics", default=None)


@contextmanager
def _bond_phase(phase: str) -> Iterator[None]:
    diagnostics = _ACTIVE_BOND_RUN.get()
    if diagnostics is None:
        yield
        return
    started_at = datetime.now(UTC).isoformat()
    started = perf_counter()

    def record(phase_status: str, error: Exception | None = None) -> None:
        details: dict[str, object] = {}
        if phase_status != "running":
            elapsed = round(perf_counter() - started, 6)
            diagnostics.phase_timings_seconds[phase] = elapsed
            details["phase_elapsed_seconds"] = elapsed
            details["phase_finished_at"] = datetime.now(UTC).isoformat()
        if error is not None:
            details["error_message"] = f"Bond materialization phase failed (error_type={type(error).__name__})."
        try:
            diagnostics.governance_repo.append(
                CACHE_BUILD_RUN_STREAM,
                {
                    "run_id": diagnostics.run_id,
                    "job_name": _BOND_ANALYTICS_VERSION.job_name,
                    "cache_key": CACHE_KEY,
                    "cache_version": CACHE_VERSION,
                    "rule_version": RULE_VERSION,
                    "source_version": BOND_ANALYTICS_MODULE.running_source_version,
                    "vendor_version": BOND_ANALYTICS_MODULE.vendor_version,
                    "report_date": diagnostics.report_date,
                    "queued_at": diagnostics.started_at,
                    "started_at": diagnostics.started_at,
                    "lock": BOND_ANALYTICS_MODULE.lock_key,
                    "status": "running",
                    "phase": phase,
                    "phase_status": phase_status,
                    "phase_started_at": started_at,
                    **details,
                },
            )
        except Exception as exc:  # noqa: BLE001 - Optional phase diagnostics must never replace the primary materialization failure.
            # The formal runtime remains responsible for terminal governance.
            logger.warning(
                "failed to record bond materialization phase=%s run_id=%s error_type=%s",
                phase, diagnostics.run_id, type(exc).__name__,
            )

    record("running")
    try:
        yield
    except Exception as exc:
        record("failed", exc)
        raise
    else:
        record("completed")


def _execute_bond_analytics_materialization(
    *,
    report_date: str,
    duckdb_file: Path,
    expected_curve_snapshots: list[dict[str, str]] | None = None,
) -> FormalComputeMaterializeResult:
    repo = BondAnalyticsRepository(str(duckdb_file))
    with _bond_phase("source_read"):
        snapshot_rows = repo.load_snapshot_rows(report_date)
        combined_source_version = _combine_source_versions(snapshot_rows)
    qualified_curve_dependencies = None
    if expected_curve_snapshots is not None:
        with _bond_phase("curve_validation"):
            qualified_curve_dependencies = _validate_expected_curve_dependencies(
                report_date=report_date,
                duckdb_file=duckdb_file,
                expected_curve_snapshots=expected_curve_snapshots,
            )

    try:
        with _bond_phase("compute"):
            analytics_rows = compute_bond_analytics_rows(
                snapshot_rows,
                date.fromisoformat(report_date),
            )
        with _bond_phase("write"), repository_task_write_scope(__name__):
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
                vendor_version=BOND_ANALYTICS_MODULE.vendor_version,
                message=(
                    f"{exc}; failed to invalidate stale facts for report_date={report_date}: "
                    f"{invalidation_exc}"
                ),
            ) from invalidation_exc
        raise FormalComputeMaterializeFailure(
            source_version=combined_source_version,
            vendor_version=BOND_ANALYTICS_MODULE.vendor_version,
            message=str(exc),
        ) from exc
    except Exception as exc:
        raise FormalComputeMaterializeFailure(
            source_version=combined_source_version,
            vendor_version=BOND_ANALYTICS_MODULE.vendor_version,
            message=str(exc),
        ) from exc

    return FormalComputeMaterializeResult(
        source_version=combined_source_version,
        vendor_version=BOND_ANALYTICS_MODULE.vendor_version,
        payload={
            "row_count": len(analytics_rows),
            **(
                {"qualified_curve_dependencies": qualified_curve_dependencies}
                if qualified_curve_dependencies is not None
                else {}
            ),
        },
    )


def ensure_yield_curve_inputs_on_or_before(
    *,
    anchor_dates: tuple[str, ...],
    duckdb_path: str,
    curve_types: tuple[str, ...] | None = None,
    max_backtrack_days: int | None = None,
    vendor_timeout_seconds: float | None = None,
) -> None:
    from backend.app.tasks.yield_curve_materialize import (
        MAX_BACKTRACK_DAYS,
        SUPPORTED_CURVE_TYPES,
    )
    from backend.app.tasks.yield_curve_materialize import (
        ensure_yield_curve_inputs_on_or_before as _ensure,
    )

    _ensure(
        anchor_dates=anchor_dates,
        duckdb_path=duckdb_path,
        curve_types=SUPPORTED_CURVE_TYPES if curve_types is None else curve_types,
        max_backtrack_days=MAX_BACKTRACK_DAYS if max_backtrack_days is None else max_backtrack_days,
        vendor_timeout_seconds=vendor_timeout_seconds,
    )


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


def _validate_expected_curve_dependencies(
    *,
    report_date: str,
    duckdb_file: Path,
    expected_curve_snapshots: list[dict[str, str]],
) -> list[dict[str, object]]:
    """Qualify the selector-resolved curve preparation dependencies before bond writes."""
    from backend.app.repositories.akshare_adapter import _prepare_curve_points
    from backend.app.repositories.yield_curve_repo import YieldCurveRepository
    from backend.app.schemas.yield_curve import YieldCurvePoint

    anchor_dates = _yield_curve_anchor_dates_for_materialization(
        duckdb_path=str(duckdb_file),
        report_date=report_date,
    )
    required_grains = {
        (anchor_date, curve_type)
        for anchor_date in anchor_dates
        for curve_type in CURVE_RECOVERY_TYPES
    }
    expected_by_grain = {
        (item["anchor_date"], item["curve_type"]): item
        for item in expected_curve_snapshots
    }
    missing = sorted(required_grains - set(expected_by_grain))
    unexpected = sorted(set(expected_by_grain) - required_grains)
    if missing or unexpected:
        raise ValueError(
            "expected_curve_snapshots does not match the bond curve dependency grains; "
            f"missing={missing}, unexpected={unexpected}."
        )

    selector = YieldCurveRepository(str(duckdb_file))
    selected = selector.resolve_curve_snapshots_many(sorted(required_grains))
    dependencies: list[dict[str, object]] = []
    for grain in sorted(required_grains):
        anchor_date, curve_type = grain
        expected = expected_by_grain[grain]
        snapshot, warning = selected.get(grain, (None, None))
        if snapshot is None:
            raise ValueError(
                f"Missing qualified {curve_type} curve snapshot on or before anchor_date={anchor_date}."
            )

        snapshot_date = str(snapshot.get("trade_date") or "")
        if snapshot_date != expected["snapshot_date"]:
            raise ValueError(
                f"Selected {curve_type} curve snapshot changed for anchor_date={anchor_date}: "
                f"expected={expected['snapshot_date']}, actual={snapshot_date or None}."
            )
        age_days = (date.fromisoformat(anchor_date) - date.fromisoformat(snapshot_date)).days
        if age_days < 0 or age_days > MAX_CURVE_RECOVERY_LOOKBACK_DAYS:
            raise ValueError(
                f"Selected {curve_type} curve snapshot is outside the "
                f"{MAX_CURVE_RECOVERY_LOOKBACK_DAYS}-day recovery window for "
                f"anchor_date={anchor_date}: snapshot_date={snapshot_date}."
            )

        lineage_fields = ("source_version", "vendor_name", "vendor_version", "rule_version")
        for field in lineage_fields:
            actual_value = str(snapshot.get(field) or "")
            if not actual_value:
                raise ValueError(
                    f"Selected {curve_type} curve snapshot has empty {field} "
                    f"for snapshot_date={snapshot_date}."
                )
            if actual_value != expected[field]:
                raise ValueError(
                    f"Selected {curve_type} curve {field} changed for anchor_date={anchor_date}: "
                    f"expected={expected[field]}, actual={actual_value}."
                )

        curve = snapshot.get("curve")
        if not isinstance(curve, dict) or not curve:
            raise ValueError(
                f"Selected {curve_type} curve snapshot has no usable tenor points "
                f"for snapshot_date={snapshot_date}."
            )
        actual_points = [
            YieldCurvePoint(tenor=str(tenor), rate_pct=Decimal(str(rate)))
            for tenor, rate in curve.items()
        ]
        prepared_points = _prepare_curve_points(
            curve_type=curve_type,
            points=actual_points,
        )
        prepared_curve = {point.tenor: point.rate_pct for point in prepared_points}
        actual_curve = {point.tenor: point.rate_pct for point in actual_points}
        if prepared_curve != actual_curve:
            raise ValueError(
                f"Selected {curve_type} curve snapshot does not satisfy the existing "
                f"standardized tenor rules for snapshot_date={snapshot_date}."
            )

        dependencies.append(
            {
                "anchor_date": anchor_date,
                "curve_type": curve_type,
                "snapshot_date": snapshot_date,
                **{field: str(snapshot[field]) for field in lineage_fields},
                "point_count": len(actual_points),
                "selector_warning": warning,
            }
        )
    return dependencies


def _execute_bond_analytics_with_curve_preparation(
    *,
    report_date: str,
    duckdb_file: Path,
) -> FormalComputeMaterializeResult:
    try:
        with _bond_phase("curve_prepare"):
            ensure_yield_curve_inputs_on_or_before(
                anchor_dates=_yield_curve_anchor_dates_for_materialization(
                    duckdb_path=str(duckdb_file),
                    report_date=report_date,
                ),
                duckdb_path=str(duckdb_file),
                vendor_timeout_seconds=CURVE_VENDOR_TIMEOUT_SECONDS,
            )
    except Exception as exc:
        raise FormalComputeMaterializeFailure(
            source_version=BOND_ANALYTICS_MODULE.running_source_version,
            vendor_version=BOND_ANALYTICS_MODULE.vendor_version,
            message=f"yield_curve_prepare_failed: {exc}",
        ) from exc
    return _execute_bond_analytics_materialization(
        report_date=report_date,
        duckdb_file=duckdb_file,
    )


def _execute_bond_analytics_from_options(
    *,
    report_date: str,
    duckdb_file: Path,
    use_existing_curves_only: bool,
    expected_curve_snapshots: object,
) -> FormalComputeMaterializeResult:
    normalized_expected = (
        normalize_curve_recovery_options(
            use_existing_curves_only=use_existing_curves_only,
            expected_curve_snapshots=expected_curve_snapshots,
        )
        if expected_curve_snapshots is not None
        else None
    )
    try:
        # The formal runtime already holds the canonical writer lock here.
        # Close this probe before any reads or vendor calls; retain the real
        # write-time checks because another process may open the DB later.
        with _bond_phase("write_access"), repository_task_write_scope(__name__):
            connection = duckdb.connect(str(duckdb_file), read_only=False)
            connection.close()
    except Exception as exc:
        raise FormalComputeMaterializeFailure(
            source_version=BOND_ANALYTICS_MODULE.running_source_version,
            vendor_version=BOND_ANALYTICS_MODULE.vendor_version,
            message=f"duckdb_write_preflight_failed: {exc}",
        ) from exc
    if use_existing_curves_only:
        result = _execute_bond_analytics_materialization(
            report_date=report_date,
            duckdb_file=duckdb_file,
            expected_curve_snapshots=normalized_expected,
        )
    else:
        result = _execute_bond_analytics_with_curve_preparation(
            report_date=report_date,
            duckdb_file=duckdb_file,
        )
    diagnostics = _ACTIVE_BOND_RUN.get()
    if diagnostics is not None:
        result.payload["phase_timings_seconds"] = dict(diagnostics.phase_timings_seconds)
    return result


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
        except Exception as exc:  # noqa: BLE001 - A failed post-write cache hook must not invalidate materialized bond facts.  # pragma: no cover
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
    use_existing_curves_only: bool = False,
    expected_curve_snapshots: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    settings = get_settings()
    duckdb_file = Path(duckdb_path or settings.duckdb_path)
    duckdb_file.parent.mkdir(parents=True, exist_ok=True)
    governance_path = Path(governance_dir or settings.governance_path)
    started_at = datetime.now(UTC).isoformat()
    active_run_id = run_id or f"{_BOND_ANALYTICS_VERSION.job_name}:{started_at}"
    token = _ACTIVE_BOND_RUN.set(
        _BondRunDiagnostics(
            governance_repo=GovernanceRepository(base_dir=governance_path),
            run_id=active_run_id,
            report_date=report_date,
            started_at=started_at,
        )
    )
    try:
        return run_formal_materialize(
            descriptor=BOND_ANALYTICS_MODULE,
            job_name=_BOND_ANALYTICS_VERSION.job_name,
            report_date=report_date,
            governance_dir=str(governance_path),
            lock_base_dir=str(duckdb_file.parent),
            duckdb_path=str(duckdb_file),
            run_id=active_run_id,
            execute_materialization=lambda: _execute_bond_analytics_from_options(
                report_date=report_date,
                duckdb_file=duckdb_file,
                use_existing_curves_only=use_existing_curves_only,
                expected_curve_snapshots=expected_curve_snapshots,
            ),
        )
    finally:
        _ACTIVE_BOND_RUN.reset(token)
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
