"""Canonical strict refresh for the governed MOSS core financial data chain.

The command is intentionally report-date driven and fail-fast. It does not guess
an as-of date, silently select an FX CSV, or continue after a failed required step.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.governance.locks import (  # noqa: E402
    LockDefinition,
    acquire_lock,
    resolve_duckdb_writer_lock,
)
from backend.app.governance.settings import get_settings  # noqa: E402
from backend.app.repositories.choice_fx_catalog import discover_formal_fx_candidates  # noqa: E402
from backend.app.repositories.duckdb_repo import read_only_connection  # noqa: E402
from backend.app.schemas.curve_recovery import normalize_curve_recovery_options  # noqa: E402


GLOBAL_REFRESH_RULE_VERSION = "rv_global_core_data_refresh_v1"
GLOBAL_REFRESH_LOCK = LockDefinition(key="lock:global-core-data-refresh", ttl_seconds=7200)
GLOBAL_REFRESH_STEP_NAMES = (
    "formal_balance",
    "bond_analytics",
    "risk_tensor",
    "formal_pnl",
    "product_category_pnl",
    "accounting_asset_movement",
    "source_preview",
    "verify",
)
FINANCIAL_PUBLICATION_PREPARE_STEP_NAME = "pnl_by_business_page_prepare"

REQUIRED_DATE_TABLES = (
    ("zqtz_bond_daily_snapshot", "report_date", 1),
    ("tyw_interbank_daily_snapshot", "report_date", 1),
    ("fx_daily_mid", "trade_date", 1),
    ("fact_formal_zqtz_balance_daily", "report_date", 1),
    ("fact_formal_tyw_balance_daily", "report_date", 1),
    ("fact_formal_bond_analytics_daily", "report_date", 1),
    ("fact_formal_risk_tensor_daily", "report_date", 1),
    ("fact_formal_pnl_fi", "report_date", 1),
    ("product_category_pnl_canonical_fact", "report_date", 1),
    ("product_category_pnl_formal_read_model", "report_date", 1),
    ("fact_accounting_asset_movement_monthly", "report_date", 1),
    ("phase1_source_preview_summary", "report_date", 1),
)

RefreshStep = tuple[str, Callable[[], dict[str, object]]]
PublicationPlanFactory = Callable[
    [str, str, str | None, tuple[Mapping[str, object], ...]],
    object,
]


def _bounded_pnl_resource_profile_enabled() -> bool:
    from backend.app.tasks.pnl_by_business_resource_scope import (
        PNL_BY_BUSINESS_BOUNDED_RESOURCE_PROFILE,
        PNL_BY_BUSINESS_RESOURCE_PROFILE_ENV,
    )

    profile = str(os.getenv(PNL_BY_BUSINESS_RESOURCE_PROFILE_ENV) or "").strip()
    if not profile:
        return False
    if profile != PNL_BY_BUSINESS_BOUNDED_RESOURCE_PROFILE:
        raise RuntimeError(f"Unsupported pnl-by-business resource profile: {profile!r}")
    return True


def _resource_limits_from_exception(exc: Exception) -> dict[str, object] | None:
    from backend.app.tasks.pnl_by_business_resource_scope import (
        PnlByBusinessResourceBudgetExceeded,
    )

    if not isinstance(exc, PnlByBusinessResourceBudgetExceeded):
        return None
    receipt = getattr(exc, "receipt", None)
    return dict(receipt) if isinstance(receipt, Mapping) else None


def _publish_with_optional_pnl_resource_scope(
    *,
    settings: Any,
    publication_root: str,
    plan: Any,
    publisher: Callable[..., Any],
) -> tuple[Any, dict[str, object] | None]:
    if not _bounded_pnl_resource_profile_enabled():
        return (
            publisher(
                source_duckdb_path=settings.duckdb_path,
                publication_root=publication_root,
                plan=plan,
            ),
            None,
        )

    from backend.app.repositories.financial_result_publication_repo import (
        generation_database_path,
    )
    from backend.app.tasks.pnl_by_business_resource_scope import (
        PnlByBusinessTaskResourceScope,
    )

    writer_lock = resolve_duckdb_writer_lock(settings.duckdb_path, ttl_seconds=3600)
    resource_scope = PnlByBusinessTaskResourceScope(
        settings.duckdb_path,
        scope_name="global_refresh_pnl_by_business_publication",
        max_database_instances=2,
    )
    final_database_path = generation_database_path(publication_root, str(plan.generation))
    with acquire_lock(
        writer_lock,
        base_dir=Path(settings.duckdb_path).parent,
    ), resource_scope:
        resource_scope.bind_database(
            settings.duckdb_path,
            read_only=False,
            label="global_refresh_publication_source",
        )
        if final_database_path.is_file():
            resource_scope.bind_database(
                final_database_path,
                read_only=True,
                label="global_refresh_existing_candidate",
            )

        def initialize_candidate_connection(
            connection: Any,
            candidate_path: Path,
            label: str,
        ) -> None:
            resource_scope.configure_connection(
                connection,
                database_path=candidate_path,
                read_only=False,
                label=f"global_refresh_{label}",
            )

        def observe_publication_stage(stage: str) -> None:
            if stage == "candidate_sealed":
                resource_scope.bind_database(
                    final_database_path,
                    read_only=True,
                    label="global_refresh_sealed_candidate",
                )
            elif stage == "candidate_validated":
                resource_scope.assert_within_budget(stage)
            elif stage == "before_pointer_commit":
                resource_scope.freeze_for_pointer_commit()

        publication = publisher(
            source_duckdb_path=settings.duckdb_path,
            publication_root=publication_root,
            plan=plan,
            writer_lock_already_held=True,
            source_connection=resource_scope.database_connection(settings.duckdb_path),
            candidate_connection_initializer=initialize_candidate_connection,
            on_stage=observe_publication_stage,
        )
    return publication, resource_scope.receipt(stage="global_refresh_publication_complete")


class GlobalDataRefreshFailed(RuntimeError):
    def __init__(self, receipt: dict[str, object]):
        self.receipt = receipt
        super().__init__(f"Global data refresh failed at step={receipt.get('failed_step')}")


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _normalize_report_date(value: str) -> str:
    text = str(value or "").strip()
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise ValueError("report_date must be a valid calendar date in YYYY-MM-DD format.") from exc


def _normalize_expected_fx_source_version(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("expected_fx_source_version must be a string or None.")
    normalized = value.strip()
    if not normalized:
        raise ValueError("expected_fx_source_version must be a non-empty string.")
    return normalized


def _resolve_fx_input_context(
    *,
    fx_source_path: str | None,
    use_existing_fx_only: bool,
    expected_fx_source_version: str | None,
) -> dict[str, object]:
    if type(use_existing_fx_only) is not bool:
        raise TypeError("use_existing_fx_only must be a bool.")
    normalized_expected_fx_source_version = _normalize_expected_fx_source_version(
        expected_fx_source_version
    )
    if use_existing_fx_only:
        if fx_source_path is not None:
            raise ValueError("use_existing_fx_only=True conflicts with an explicit fx_source_path.")
        if normalized_expected_fx_source_version is None:
            raise ValueError(
                "use_existing_fx_only=True requires expected_fx_source_version."
            )
        fx_input_mode = "existing_canonical"
    else:
        if normalized_expected_fx_source_version is not None:
            raise ValueError("expected_fx_source_version requires use_existing_fx_only=True.")
        fx_input_mode = "explicit_source" if fx_source_path is not None else "provider_refresh"
    return {
        "fx_input_mode": fx_input_mode,
        "use_existing_fx_only": use_existing_fx_only,
        "expected_fx_source_version": normalized_expected_fx_source_version,
    }


def _require_completed(step_name: str, result: dict[str, object]) -> None:
    status = str(result.get("status") or "").strip().lower()
    if status and status != "completed":
        raise RuntimeError(f"Required step {step_name} returned non-completed status={status!r}.")


def _execute_refresh_steps(
    *,
    report_date: str,
    run_id: str,
    steps: list[RefreshStep],
    on_progress: Callable[[dict[str, object]], None] | None = None,
) -> dict[str, object]:
    receipt: dict[str, object] = {
        "status": "running",
        "run_id": run_id,
        "report_date": report_date,
        "rule_version": GLOBAL_REFRESH_RULE_VERSION,
        "started_at": _utc_now(),
        "steps": [],
    }
    step_receipts = receipt["steps"]
    assert isinstance(step_receipts, list)

    for step_name, execute in steps:
        if on_progress is not None:
            on_progress({**receipt, "current_step": step_name})
        step_started_at = _utc_now()
        started = perf_counter()
        try:
            result = execute()
            if not isinstance(result, dict):
                raise TypeError(f"Required step {step_name} returned a non-object payload.")
            _require_completed(step_name, result)
        except Exception as exc:
            failed_step: dict[str, object] = {
                "name": step_name,
                "status": "failed",
                "started_at": step_started_at,
                "finished_at": _utc_now(),
                "elapsed_seconds": round(perf_counter() - started, 3),
                "error_type": exc.__class__.__name__,
                "error_message": str(exc),
            }
            resource_limits = _resource_limits_from_exception(exc)
            if resource_limits is not None:
                failed_step["failure_category"] = "resource_over_budget"
                failed_step["resource_limits"] = resource_limits
            step_receipts.append(failed_step)
            receipt.update(
                {
                    "status": "failed",
                    "failed_step": step_name,
                    "finished_at": _utc_now(),
                }
            )
            if on_progress is not None:
                on_progress(receipt)
            raise GlobalDataRefreshFailed(receipt) from exc

        step_receipts.append(
            {
                "name": step_name,
                "status": "completed",
                "started_at": step_started_at,
                "finished_at": _utc_now(),
                "elapsed_seconds": round(perf_counter() - started, 3),
                "result": result,
            }
        )
        if on_progress is not None:
            on_progress(receipt)

    receipt.update({"status": "completed", "finished_at": _utc_now()})
    if on_progress is not None:
        on_progress(receipt)
    return receipt


def _build_refresh_steps(
    *,
    settings,
    report_date: str,
    run_id: str,
    fx_source_path: str | None,
    use_existing_fx_only: bool = False,
    expected_fx_source_version: str | None = None,
    use_existing_curves_only: bool = False,
    expected_curve_snapshots: list[dict[str, str]] | None = None,
) -> list[RefreshStep]:
    duckdb_path = str(settings.duckdb_path)
    governance_dir = str(settings.governance_path)

    def formal_balance() -> dict[str, object]:
        from backend.app.tasks.formal_balance_pipeline import run_formal_balance_pipeline_sync

        if use_existing_fx_only:
            return run_formal_balance_pipeline_sync(
                report_date=report_date,
                data_root=str(settings.data_input_root),
                duckdb_path=duckdb_path,
                governance_dir=governance_dir,
                archive_dir=str(settings.local_archive_path),
                fx_source_path=fx_source_path,
                use_existing_fx_only=True,
                expected_fx_source_version=expected_fx_source_version,
            )
        return run_formal_balance_pipeline_sync(
            report_date=report_date,
            data_root=str(settings.data_input_root),
            duckdb_path=duckdb_path,
            governance_dir=governance_dir,
            archive_dir=str(settings.local_archive_path),
            fx_source_path=fx_source_path,
        )

    def bond_analytics() -> dict[str, object]:
        from backend.app.tasks.bond_analytics_materialize import materialize_bond_analytics_facts

        if use_existing_curves_only:
            return materialize_bond_analytics_facts.fn(
                report_date=report_date,
                duckdb_path=duckdb_path,
                governance_dir=governance_dir,
                run_id=f"{run_id}:bond_analytics",
                use_existing_curves_only=True,
                expected_curve_snapshots=expected_curve_snapshots,
            )
        return materialize_bond_analytics_facts.fn(
            report_date=report_date,
            duckdb_path=duckdb_path,
            governance_dir=governance_dir,
            run_id=f"{run_id}:bond_analytics",
        )

    def risk_tensor() -> dict[str, object]:
        from backend.app.tasks.risk_tensor_materialize import materialize_risk_tensor_facts

        return materialize_risk_tensor_facts.fn(
            report_date=report_date,
            duckdb_path=duckdb_path,
            governance_dir=governance_dir,
            run_id=f"{run_id}:risk_tensor",
        )

    def formal_pnl() -> dict[str, object]:
        from backend.app.services.pnl_source_service import (
            load_latest_pnl_refresh_input,
            resolve_pnl_data_input_root,
        )
        from backend.app.tasks.pnl_materialize import run_pnl_materialize_sync

        refresh_input = load_latest_pnl_refresh_input(
            governance_dir=governance_dir,
            data_root=resolve_pnl_data_input_root(),
            report_date=report_date,
            archive_root=settings.local_archive_path,
        )
        if str(refresh_input.report_date) != report_date:
            raise ValueError(
                "PnL source date did not match the requested global report date: "
                f"requested={report_date}, resolved={refresh_input.report_date}."
            )
        return run_pnl_materialize_sync(
            report_date=refresh_input.report_date,
            is_month_end=refresh_input.is_month_end,
            fi_rows=refresh_input.fi_rows,
            nonstd_rows_by_type=refresh_input.nonstd_rows_by_type,
            duckdb_path=duckdb_path,
            governance_dir=governance_dir,
            run_id=f"{run_id}:formal_pnl",
        )

    def product_category_pnl() -> dict[str, object]:
        from backend.app.services.product_category_pnl_service import run_product_category_refresh_sync

        return run_product_category_refresh_sync(
            settings,
            run_id=f"{run_id}:product_category_pnl",
        )

    def accounting_asset_movement() -> dict[str, object]:
        from backend.app.tasks.accounting_asset_movement import (
            refresh_accounting_asset_movement_window_sync,
        )

        return refresh_accounting_asset_movement_window_sync(
            report_dates=[report_date],
            anchor_report_date=report_date,
            duckdb_path=duckdb_path,
            governance_dir=governance_dir,
            currency_basis="CNX",
            product_category_refreshed_dates=[report_date],
            formal_balance_refreshed_dates=[report_date],
            run_id=f"{run_id}:accounting_asset_movement",
        )

    def source_preview() -> dict[str, object]:
        from backend.app.tasks.source_preview_refresh import refresh_source_preview_cache

        return refresh_source_preview_cache.fn(
            duckdb_path=duckdb_path,
            governance_dir=governance_dir,
            data_root=str(settings.data_input_root),
            run_id=f"{run_id}:source_preview",
        )

    def verify() -> dict[str, object]:
        return _verify_report_date(
            duckdb_path=duckdb_path,
            choice_macro_catalog_file=Path(settings.choice_macro_catalog_file),
            report_date=report_date,
        )

    steps: list[RefreshStep] = [
        ("formal_balance", formal_balance),
        ("bond_analytics", bond_analytics),
        ("risk_tensor", risk_tensor),
        ("formal_pnl", formal_pnl),
        ("product_category_pnl", product_category_pnl),
        ("accounting_asset_movement", accounting_asset_movement),
        ("source_preview", source_preview),
        ("verify", verify),
    ]
    if bool(getattr(settings, "financial_publication_enabled", False)):

        def prepare_pnl_by_business_page() -> dict[str, object]:
            from backend.app.tasks.pnl_by_business_page_publication import (
                prepare_pnl_by_business_page_envelope,
            )

            prepare_run_id = f"{run_id}:{FINANCIAL_PUBLICATION_PREPARE_STEP_NAME}"
            if not _bounded_pnl_resource_profile_enabled():
                return prepare_pnl_by_business_page_envelope(
                    duckdb_path=str(settings.duckdb_path),
                    governance_dir=str(settings.governance_path),
                    year=date.fromisoformat(report_date).year,
                    as_of_date=report_date,
                    run_id=prepare_run_id,
                )

            from backend.app.tasks.pnl_by_business_resource_scope import (
                PnlByBusinessTaskResourceScope,
            )

            writer_lock = resolve_duckdb_writer_lock(
                settings.duckdb_path,
                ttl_seconds=3600,
            )
            resource_scope = PnlByBusinessTaskResourceScope(
                duckdb_path=str(settings.duckdb_path),
                scope_name="global_refresh_pnl_by_business_page_prepare",
            )
            with acquire_lock(
                writer_lock,
                base_dir=Path(settings.duckdb_path).parent,
            ), resource_scope:
                resource_scope.bind_database(
                    settings.duckdb_path,
                    read_only=True,
                    label="global_refresh_page_prepare_read",
                )
                result = prepare_pnl_by_business_page_envelope(
                    duckdb_path=str(settings.duckdb_path),
                    governance_dir=str(settings.governance_path),
                    year=date.fromisoformat(report_date).year,
                    as_of_date=report_date,
                    run_id=prepare_run_id,
                    writer_lock_already_held=True,
                    resource_scope=resource_scope,
                )
            result["resource_limits"] = resource_scope.receipt(
                stage="global_refresh_page_prepare_complete"
            )
            return result

        steps.append((FINANCIAL_PUBLICATION_PREPARE_STEP_NAME, prepare_pnl_by_business_page))
    return steps


def _verify_report_date(
    *,
    duckdb_path: str,
    choice_macro_catalog_file: Path,
    report_date: str,
) -> dict[str, object]:
    checks: list[dict[str, object]] = []
    failures: list[str] = []
    with read_only_connection(duckdb_path) as conn:
        existing_tables = {
            str(row[0])
            for row in conn.execute(
                "select table_name from information_schema.tables where table_schema = 'main'"
            ).fetchall()
        }
        for table_name, date_column, minimum_rows in REQUIRED_DATE_TABLES:
            if table_name not in existing_tables:
                checks.append({"table": table_name, "status": "missing", "row_count": 0})
                failures.append(f"missing table {table_name}")
                continue
            count_row = conn.execute(
                f'select count(*) from "{table_name}" where cast("{date_column}" as varchar) = ?',
                [report_date],
            ).fetchone()
            if count_row is None:
                raise RuntimeError(f"{table_name} COUNT query returned no row")
            row_count = int(count_row[0])
            status = "completed" if row_count >= minimum_rows else "failed"
            checks.append({"table": table_name, "status": status, "row_count": row_count})
            if row_count < minimum_rows:
                failures.append(f"{table_name} has {row_count} rows for {report_date}")

        candidates = discover_formal_fx_candidates(catalog_path=choice_macro_catalog_file)
        required_bases = {candidate.base_currency.upper() for candidate in candidates}
        fx_rows = conn.execute(
            """
            select
              upper(base_currency),
              upper(quote_currency),
              mid_rate,
              source_name,
              source_version,
              vendor_name,
              vendor_version,
              vendor_series_code,
              cast(observed_trade_date as varchar)
            from fx_daily_mid
            where cast(trade_date as varchar) = ?
            """,
            [report_date],
        ).fetchall()
        observed_bases = {str(row[0]) for row in fx_rows if str(row[1]) == "CNY"}
        missing_bases = sorted(required_bases - observed_bases)
        duplicate_count = len(fx_rows) - len({(str(row[0]), str(row[1])) for row in fx_rows})
        invalid_lineage_count = sum(
            1
            for row in fx_rows
            if row[2] is None
            or row[2] <= 0
            or any(not str(row[index] or "").strip() for index in (3, 4, 5, 6, 7, 8))
        )
        fx_check: dict[str, object] = {
            "table": "fx_daily_mid",
            "status": "completed"
            if not missing_bases and duplicate_count == 0 and invalid_lineage_count == 0
            else "failed",
            "required_base_currencies": sorted(required_bases),
            "observed_base_currencies": sorted(observed_bases),
            "missing_base_currencies": missing_bases,
            "duplicate_grain_count": duplicate_count,
            "invalid_lineage_or_rate_count": invalid_lineage_count,
        }
        checks.append(fx_check)
        if fx_check["status"] != "completed":
            failures.append(
                "fx_daily_mid failed completeness/duplicate/lineage checks: "
                f"missing={missing_bases}, duplicates={duplicate_count}, invalid={invalid_lineage_count}"
            )

    if failures:
        raise RuntimeError("; ".join(failures))
    return {"status": "completed", "report_date": report_date, "checks": checks}


def run_global_data_refresh(
    *,
    report_date: str,
    fx_source_path: str | None = None,
    use_existing_fx_only: bool = False,
    expected_fx_source_version: str | None = None,
    use_existing_curves_only: bool = False,
    expected_curve_snapshots: list[dict[str, str]] | None = None,
    dry_run: bool = False,
    on_progress: Callable[[dict[str, object]], None] | None = None,
    publication_plan_factory: PublicationPlanFactory | None = None,
    data_update_run_id: str | None = None,
) -> dict[str, object]:
    from backend.app.repositories.system_read_publication_repo import (
        active_system_read_scope,
    )

    with active_system_read_scope():
        return _run_global_data_refresh_active(
            report_date=report_date,
            fx_source_path=fx_source_path,
            use_existing_fx_only=use_existing_fx_only,
            expected_fx_source_version=expected_fx_source_version,
            use_existing_curves_only=use_existing_curves_only,
            expected_curve_snapshots=expected_curve_snapshots,
            dry_run=dry_run,
            on_progress=on_progress,
            publication_plan_factory=publication_plan_factory,
            data_update_run_id=data_update_run_id,
        )


def _run_global_data_refresh_active(
    *,
    report_date: str,
    fx_source_path: str | None = None,
    use_existing_fx_only: bool = False,
    expected_fx_source_version: str | None = None,
    use_existing_curves_only: bool = False,
    expected_curve_snapshots: list[dict[str, str]] | None = None,
    dry_run: bool = False,
    on_progress: Callable[[dict[str, object]], None] | None = None,
    publication_plan_factory: PublicationPlanFactory | None = None,
    data_update_run_id: str | None = None,
) -> dict[str, object]:
    normalized_report_date = _normalize_report_date(report_date)
    normalized_expected_curve_snapshots = normalize_curve_recovery_options(
        use_existing_curves_only=use_existing_curves_only,
        expected_curve_snapshots=expected_curve_snapshots,
    )
    curve_input_mode = "existing_canonical" if use_existing_curves_only else "provider_refresh"
    curve_input_context: dict[str, object] = {
        "curve_input_mode": curve_input_mode,
        "use_existing_curves_only": use_existing_curves_only,
        "expected_curve_snapshots": normalized_expected_curve_snapshots,
    }
    normalized_fx_source_path = str(fx_source_path or "").strip() or None
    normalized_expected_fx_source_version = _normalize_expected_fx_source_version(
        expected_fx_source_version
    )
    fx_input_context = _resolve_fx_input_context(
        fx_source_path=normalized_fx_source_path,
        use_existing_fx_only=use_existing_fx_only,
        expected_fx_source_version=normalized_expected_fx_source_version,
    )
    if normalized_fx_source_path is not None and not Path(normalized_fx_source_path).is_file():
        raise FileNotFoundError(f"Explicit FX source file not found: {normalized_fx_source_path}")

    run_id = f"global_core_data_refresh:{normalized_report_date}:{_utc_now()}"
    if dry_run:
        return {
            "status": "dry_run",
            "run_id": run_id,
            "report_date": normalized_report_date,
            "rule_version": GLOBAL_REFRESH_RULE_VERSION,
            "fx_source_path": normalized_fx_source_path,
            **fx_input_context,
            **curve_input_context,
            "steps": list(GLOBAL_REFRESH_STEP_NAMES),
            "required_date_tables": [item[0] for item in REQUIRED_DATE_TABLES],
        }

    settings = get_settings()
    publication_enabled = bool(getattr(settings, "financial_publication_enabled", False))
    system_read_publication_enabled = bool(
        getattr(settings, "system_read_publication_enabled", False)
    )
    publication_root = str(getattr(settings, "financial_publication_root", "") or "").strip()
    if publication_enabled and not publication_root:
        raise ValueError("Financial publication is enabled but its publication root is empty.")
    if system_read_publication_enabled and not publication_enabled:
        raise ValueError(
            "System read publication requires financial publication to be enabled."
        )
    normalized_data_update_run_id = str(data_update_run_id or "").strip()
    if system_read_publication_enabled and not normalized_data_update_run_id:
        raise ValueError(
            "System read publication requires a correlated data_update_run_id; "
            "standalone refresh freshness is unsupported."
        )
    if publication_enabled and publication_plan_factory is None:
        from backend.app.tasks.pnl_by_business_page_publication import (
            build_pnl_by_business_financial_publication_plan,
        )

        def default_publication_plan_factory(
            active_report_date: str,
            active_run_id: str,
            active_expected_previous_generation: str | None,
            active_step_receipts: tuple[Mapping[str, object], ...],
        ) -> object:
            return build_pnl_by_business_financial_publication_plan(
                settings,
                report_date=active_report_date,
                run_id=active_run_id,
                expected_previous_generation=active_expected_previous_generation,
                step_receipts=active_step_receipts,
            )

        publication_plan_factory = default_publication_plan_factory
    steps = _build_refresh_steps(
        settings=settings,
        report_date=normalized_report_date,
        run_id=run_id,
        fx_source_path=normalized_fx_source_path,
        use_existing_fx_only=use_existing_fx_only,
        expected_fx_source_version=normalized_expected_fx_source_version,
        use_existing_curves_only=use_existing_curves_only,
        expected_curve_snapshots=normalized_expected_curve_snapshots,
    )
    progress_callback: Callable[[dict[str, object]], None] | None = None
    if on_progress is not None:

        def progress_callback(payload: dict[str, object]) -> None:
            on_progress({**payload, **fx_input_context, **curve_input_context})

    with acquire_lock(GLOBAL_REFRESH_LOCK, base_dir=Path(settings.duckdb_path).parent):
        expected_previous_generation: str | None = None
        if publication_enabled:
            from backend.app.repositories.financial_result_publication_repo import (
                read_publication_pointer,
            )

            previous_pointer = read_publication_pointer(publication_root, require_valid=False)
            if previous_pointer is not None:
                expected_previous_generation = str(previous_pointer["generation"])
        try:
            receipt = _execute_refresh_steps(
                report_date=normalized_report_date,
                run_id=run_id,
                steps=steps,
                on_progress=progress_callback,
            )
        except GlobalDataRefreshFailed as exc:
            exc.receipt.update(fx_input_context)
            exc.receipt.update(curve_input_context)
            raise
        receipt.update(fx_input_context)
        receipt.update(curve_input_context)
        if not publication_enabled:
            return receipt
        assert publication_plan_factory is not None
        step_receipts = receipt.get("steps")
        assert isinstance(step_receipts, list)
        publication_started_at = _utc_now()
        started = perf_counter()
        if progress_callback is not None:
            progress_callback({**receipt, "status": "running", "current_step": "publish"})
        try:
            from backend.app.tasks.financial_result_publication import (
                FinancialPublicationPlan,
                publish_financial_result,
            )

            plan = publication_plan_factory(
                normalized_report_date,
                run_id,
                expected_previous_generation,
                tuple(step_receipts),
            )
            if not isinstance(plan, FinancialPublicationPlan):
                raise TypeError("Financial publication plan factory returned an invalid plan.")
            publication, publication_resource_limits = (
                _publish_with_optional_pnl_resource_scope(
                    settings=settings,
                    publication_root=publication_root,
                    plan=plan,
                    publisher=publish_financial_result,
                )
            )
        except Exception as exc:
            failed_step: dict[str, object] = {
                "name": "publish",
                "status": "failed",
                "started_at": publication_started_at,
                "finished_at": _utc_now(),
                "elapsed_seconds": round(perf_counter() - started, 3),
                "error_type": exc.__class__.__name__,
                "error_message": str(exc),
            }
            resource_limits = _resource_limits_from_exception(exc)
            if resource_limits is not None:
                failed_step["failure_category"] = "resource_over_budget"
                failed_step["resource_limits"] = resource_limits
            step_receipts.append(failed_step)
            receipt.update(
                {
                    "status": "failed",
                    "failed_step": "publish",
                    "finished_at": _utc_now(),
                }
            )
            if progress_callback is not None:
                progress_callback(receipt)
            raise GlobalDataRefreshFailed(receipt) from exc
        publication_result: dict[str, object] = {
            "status": "completed",
            "generation": publication.generation,
            "manifest_sha256": publication.manifest_sha256,
            "recovered_after_commit": publication.recovered_after_commit,
        }
        if publication_resource_limits is not None:
            publication_result["resource_limits"] = publication_resource_limits
        step_receipts.append(
            {
                "name": "publish",
                "status": "completed",
                "started_at": publication_started_at,
                "finished_at": _utc_now(),
                "elapsed_seconds": round(perf_counter() - started, 3),
                "result": publication_result,
            }
        )
        if system_read_publication_enabled:
            system_publication_started_at = _utc_now()
            system_started = perf_counter()
            if progress_callback is not None:
                progress_callback(
                    {
                        **receipt,
                        "status": "running",
                        "current_step": "system_read_publish",
                    }
                )
            try:
                from backend.app.tasks.system_read_publication import (
                    publish_system_read_generation,
                )

                system_publication = publish_system_read_generation(
                    settings,
                    report_date=normalized_report_date,
                    data_update_run_id=normalized_data_update_run_id,
                    global_run_id=run_id,
                    step_receipts=tuple(step_receipts),
                    pnl_generation=publication.generation,
                    pnl_manifest_sha256=publication.manifest_sha256,
                    required_date_tables=REQUIRED_DATE_TABLES,
                )
            except Exception as exc:
                failed_system_step: dict[str, object] = {
                    "name": "system_read_publish",
                    "status": "failed",
                    "started_at": system_publication_started_at,
                    "finished_at": _utc_now(),
                    "elapsed_seconds": round(perf_counter() - system_started, 3),
                    "error_type": exc.__class__.__name__,
                    "error_message": str(exc),
                }
                resource_limits = _resource_limits_from_exception(exc)
                if resource_limits is not None:
                    failed_system_step["failure_category"] = "resource_over_budget"
                    failed_system_step["resource_limits"] = resource_limits
                step_receipts.append(failed_system_step)
                receipt.update(
                    {
                        "status": "failed",
                        "failed_step": "system_read_publish",
                        "finished_at": _utc_now(),
                    }
                )
                if progress_callback is not None:
                    progress_callback(receipt)
                raise GlobalDataRefreshFailed(receipt) from exc
            system_publication_result: dict[str, object] = {
                "status": "completed",
                "generation": system_publication.generation,
                "manifest_sha256": system_publication.manifest_sha256,
                "recovered_after_commit": system_publication.recovered_after_commit,
                "data_update_run_id": normalized_data_update_run_id,
                "global_run_id": run_id,
            }
            system_resource_limits = getattr(system_publication, "resource_limits", None)
            if system_resource_limits is not None:
                system_publication_result["resource_limits"] = dict(
                    system_resource_limits
                )
            step_receipts.append(
                {
                    "name": "system_read_publish",
                    "status": "completed",
                    "started_at": system_publication_started_at,
                    "finished_at": _utc_now(),
                    "elapsed_seconds": round(perf_counter() - system_started, 3),
                    "result": system_publication_result,
                }
            )
        receipt.update({"status": "completed", "finished_at": _utc_now()})
        if progress_callback is not None:
            progress_callback(receipt)
        return receipt


def _emit(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the strict, report-date-driven MOSS core financial data refresh."
    )
    parser.add_argument("--report-date", required=True, help="Required target date in YYYY-MM-DD format.")
    parser.add_argument(
        "--fx-source-path",
        help="Optional explicit governed FX CSV override; never auto-discovered.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print the plan without writing data.")
    args = parser.parse_args()

    try:
        payload = run_global_data_refresh(
            report_date=args.report_date,
            fx_source_path=args.fx_source_path,
            dry_run=args.dry_run,
        )
    except GlobalDataRefreshFailed as exc:
        _emit(exc.receipt)
        return 1
    except Exception as exc:
        _emit(
            {
                "status": "failed",
                "failed_step": "preflight",
                "error_type": exc.__class__.__name__,
                "error_message": str(exc),
            }
        )
        return 1

    _emit(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
