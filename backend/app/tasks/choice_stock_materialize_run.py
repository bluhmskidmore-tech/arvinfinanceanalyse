from __future__ import annotations

import argparse
import hashlib
import json
import sys

from backend.app.governance.settings import get_settings
from backend.app.tasks.choice_stock_materialize import (
    ChoiceStockMaterializationCoverage,
    load_choice_stock_materialization_coverage,
    materialize_choice_stock_factor_snapshot,
    materialize_choice_stock_inputs,
)
from backend.app.tasks.choice_stock_theme_overlay_refresh import (
    refresh_choice_stock_theme_overlay,
)


def _emit_json_payload(payload: dict[str, object]) -> None:
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    print(rendered, file=sys.stdout)


def _coverage_payload(coverage: ChoiceStockMaterializationCoverage) -> dict[str, object]:
    return {
        "as_of_date": coverage.as_of_date,
        "full_coverage": coverage.full_coverage,
        "status": coverage.status,
        "completed_request_items": coverage.completed_request_items,
        "missing_request_items": coverage.missing_request_items,
        "message": coverage.message,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Choice stock materialization into DuckDB.")
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument("--duckdb-path")
    parser.add_argument("--catalog-path")
    parser.add_argument("--verify-coverage", action="store_true")
    parser.add_argument("--factor-snapshot", action="store_true")
    parser.add_argument("--factor-max-stock-count", type=int)
    parser.add_argument(
        "--theme-overlay-mode",
        choices=("off", "dry_run", "archive"),
        default="off",
    )
    args = parser.parse_args()

    if args.factor_snapshot:
        payload = materialize_choice_stock_factor_snapshot(
            as_of_date=args.as_of_date,
            duckdb_path=args.duckdb_path,
            max_stock_count=args.factor_max_stock_count,
        )
    else:
        payload = materialize_choice_stock_inputs(
            as_of_date=args.as_of_date,
            duckdb_path=args.duckdb_path,
            catalog_path=args.catalog_path,
            enable_tushare_concept_fallback=False,
        )
        if args.verify_coverage:
            coverage_duckdb_path = args.duckdb_path or str(get_settings().duckdb_path)
            coverage = load_choice_stock_materialization_coverage(
                duckdb_path=coverage_duckdb_path,
                as_of_date=args.as_of_date,
            )
            payload["coverage"] = _coverage_payload(coverage)

    if args.theme_overlay_mode == "off":
        theme_overlay = refresh_choice_stock_theme_overlay(mode="off")
    else:
        settings = get_settings()
        parent_run_id = str(payload.get("run_id") or "").strip()
        if not parent_run_id:
            raise ValueError("Choice stock materialization result is missing run_id")
        digest = hashlib.sha256(f"{parent_run_id}|{args.as_of_date}".encode()).hexdigest()[:16]
        theme_overlay = refresh_choice_stock_theme_overlay(
            mode=args.theme_overlay_mode,
            duckdb_path=str(args.duckdb_path or settings.duckdb_path),
            governance_dir=str(settings.governance_path),
            archive_root=str(settings.local_archive_path),
            expected_report_date=args.as_of_date,
            run_id=f"{parent_run_id}:theme-overlay",
            source_version=f"sv_choice_stock_theme_overlay_{digest}",
            vendor_version="vv_tushare_ths_current_overlay_v1",
        )
    payload["theme_overlay"] = theme_overlay
    _emit_json_payload(payload)


if __name__ == "__main__":
    main()
