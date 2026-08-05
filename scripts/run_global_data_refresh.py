"""Canonical strict refresh for the governed MOSS core financial data chain.

The command is intentionally report-date driven and fail-fast. It does not guess
an as-of date, silently select an FX CSV, or continue after a failed required step.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from time import perf_counter
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import duckdb  # noqa: E402

from backend.app.governance.locks import LockDefinition, acquire_lock  # noqa: E402
from backend.app.governance.settings import get_settings  # noqa: E402
from backend.app.repositories.choice_fx_catalog import discover_formal_fx_candidates  # noqa: E402


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


def _require_completed(step_name: str, result: dict[str, object]) -> None:
    status = str(result.get("status") or "").strip().lower()
    if status and status != "completed":
        raise RuntimeError(f"Required step {step_name} returned non-completed status={status!r}.")


def _execute_refresh_steps(
    *,
    report_date: str,
    run_id: str,
    steps: list[RefreshStep],
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
        step_started_at = _utc_now()
        started = perf_counter()
        try:
            result = execute()
            if not isinstance(result, dict):
                raise TypeError(f"Required step {step_name} returned a non-object payload.")
            _require_completed(step_name, result)
        except Exception as exc:
            step_receipts.append(
                {
                    "name": step_name,
                    "status": "failed",
                    "started_at": step_started_at,
                    "finished_at": _utc_now(),
                    "elapsed_seconds": round(perf_counter() - started, 3),
                    "error_type": exc.__class__.__name__,
                    "error_message": str(exc),
                }
            )
            receipt.update(
                {
                    "status": "failed",
                    "failed_step": step_name,
                    "finished_at": _utc_now(),
                }
            )
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

    receipt.update({"status": "completed", "finished_at": _utc_now()})
    return receipt


def _build_refresh_steps(
    *,
    settings,
    report_date: str,
    run_id: str,
    fx_source_path: str | None,
) -> list[RefreshStep]:
    duckdb_path = str(settings.duckdb_path)
    governance_dir = str(settings.governance_path)

    def formal_balance() -> dict[str, object]:
        from backend.app.tasks.formal_balance_pipeline import run_formal_balance_pipeline_sync

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

    return [
        ("formal_balance", formal_balance),
        ("bond_analytics", bond_analytics),
        ("risk_tensor", risk_tensor),
        ("formal_pnl", formal_pnl),
        ("product_category_pnl", product_category_pnl),
        ("accounting_asset_movement", accounting_asset_movement),
        ("source_preview", source_preview),
        ("verify", verify),
    ]


def _verify_report_date(
    *,
    duckdb_path: str,
    choice_macro_catalog_file: Path,
    report_date: str,
) -> dict[str, object]:
    checks: list[dict[str, object]] = []
    failures: list[str] = []
    conn = duckdb.connect(duckdb_path, read_only=True)
    try:
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
            row_count = int(
                conn.execute(
                    f'select count(*) from "{table_name}" where cast("{date_column}" as varchar) = ?',
                    [report_date],
                ).fetchone()[0]
            )
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
        fx_check = {
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
    finally:
        conn.close()

    if failures:
        raise RuntimeError("; ".join(failures))
    return {"status": "completed", "report_date": report_date, "checks": checks}


def run_global_data_refresh(
    *,
    report_date: str,
    fx_source_path: str | None = None,
    dry_run: bool = False,
) -> dict[str, object]:
    normalized_report_date = _normalize_report_date(report_date)
    normalized_fx_source_path = str(fx_source_path or "").strip() or None
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
            "steps": list(GLOBAL_REFRESH_STEP_NAMES),
            "required_date_tables": [item[0] for item in REQUIRED_DATE_TABLES],
        }

    settings = get_settings()
    steps = _build_refresh_steps(
        settings=settings,
        report_date=normalized_report_date,
        run_id=run_id,
        fx_source_path=normalized_fx_source_path,
    )
    with acquire_lock(GLOBAL_REFRESH_LOCK, base_dir=Path(settings.duckdb_path).parent):
        return _execute_refresh_steps(
            report_date=normalized_report_date,
            run_id=run_id,
            steps=steps,
        )


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
