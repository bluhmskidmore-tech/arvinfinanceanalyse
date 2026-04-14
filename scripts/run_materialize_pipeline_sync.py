"""Run Steps 5.1–5.5 synchronously (Dramatiq .fn), no Redis/worker.

Stop uvicorn first if DuckDB is exclusively locked by the API process.
Usage (from repo root):
  python scripts/run_materialize_pipeline_sync.py --report-date 2025-12-31
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.governance.settings import Settings, get_settings
from backend.app.services.pnl_service import load_latest_pnl_refresh_input
from backend.app.services.product_category_pnl_service import run_product_category_refresh_sync
from backend.app.tasks.bond_analytics_materialize import materialize_bond_analytics_facts
from backend.app.tasks.balance_analysis_materialize import materialize_balance_analysis_facts
from backend.app.tasks.pnl_materialize import run_pnl_materialize_sync
from backend.app.tasks.source_preview_refresh import (
    SOURCE_PREVIEW_REFRESH_JOB_NAME,
    refresh_source_preview_cache,
)
from backend.app.tasks.ingest import resolve_data_input_root
from backend.app.services.pnl_source_service import resolve_pnl_data_input_root


def _source_preview(settings: Settings) -> None:
    run_id = f"{SOURCE_PREVIEW_REFRESH_JOB_NAME}:{datetime.now(timezone.utc).isoformat()}"
    print("5.1 source_preview_refresh ...", flush=True)
    refresh_source_preview_cache.fn(
        run_id=run_id,
        duckdb_path=str(settings.duckdb_path),
        governance_dir=str(settings.governance_path),
        governance_sql_dsn=settings.governance_sql_dsn,
        governance_backend_mode=settings.source_preview_governance_backend,
        data_root=str(resolve_data_input_root()),
    )
    print("5.1 done", flush=True)


def _balance(settings: Settings, report_date: str) -> None:
    run_id = f"balance_analysis_materialize:{datetime.now(timezone.utc).isoformat()}"
    print(f"5.2 balance_analysis {report_date} ...", flush=True)
    materialize_balance_analysis_facts.fn(
        report_date=report_date,
        duckdb_path=str(settings.duckdb_path),
        governance_dir=str(settings.governance_path),
        run_id=run_id,
    )
    print("5.2 done", flush=True)


def _bond(settings: Settings, report_date: str) -> None:
    run_id = f"bond_analytics_materialize:{datetime.now(timezone.utc).isoformat()}"
    print(f"5.3 bond_analytics {report_date} ...", flush=True)
    materialize_bond_analytics_facts.fn(
        report_date=report_date,
        duckdb_path=str(settings.duckdb_path),
        governance_dir=str(settings.governance_path),
        run_id=run_id,
    )
    print("5.3 done", flush=True)


def _pnl(settings: Settings, report_date: str | None) -> None:
    print("5.4 pnl ...", flush=True)
    refresh_input = load_latest_pnl_refresh_input(
        governance_dir=settings.governance_path,
        data_root=resolve_pnl_data_input_root(),
        report_date=report_date,
    )
    run_id = f"pnl_materialize:{datetime.now(timezone.utc).isoformat()}"
    run_pnl_materialize_sync(
        report_date=refresh_input.report_date,
        is_month_end=refresh_input.is_month_end,
        fi_rows=refresh_input.fi_rows,
        nonstd_rows_by_type=refresh_input.nonstd_rows_by_type,
        duckdb_path=str(settings.duckdb_path),
        governance_dir=str(settings.governance_path),
        run_id=run_id,
    )
    print("5.4 done", flush=True)


def _product_category(settings: Settings) -> None:
    print("5.5 product_category_pnl ...", flush=True)
    run_product_category_refresh_sync(settings)
    print("5.5 done", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-date", default="2025-12-31")
    parser.add_argument(
        "--pnl-report-date",
        default=None,
        help="Optional override for PnL source scan (default: auto from FI files)",
    )
    parser.add_argument(
        "--skip",
        nargs="*",
        default=[],
        choices=["source", "balance", "bond", "pnl", "product_category"],
        help="Steps to skip",
    )
    args = parser.parse_args()
    settings = get_settings()
    skip = set(args.skip)

    if "source" not in skip:
        _source_preview(settings)
    if "balance" not in skip:
        _balance(settings, args.report_date)
    if "bond" not in skip:
        _bond(settings, args.report_date)
    if "pnl" not in skip:
        _pnl(settings, args.pnl_report_date)
    if "product_category" not in skip:
        _product_category(settings)

    print("pipeline complete", flush=True)


if __name__ == "__main__":
    main()
