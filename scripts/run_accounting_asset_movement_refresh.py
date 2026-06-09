"""Operator entry point for accounting asset movement refresh.

This script delegates writes to the task-level sync wrapper. It does not use
API/service write paths or repository internals.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.governance.settings import get_settings  # noqa: E402
from backend.app.tasks.accounting_asset_movement import (  # noqa: E402
    refresh_accounting_asset_movement_window_sync,
)


BOUNDARY = {
    "operator_entrypoint": True,
    "writes_duckdb_via_task": True,
    "uses_api_or_service_write_path": False,
    "changes_schema": False,
}


def run_accounting_asset_movement_refresh(
    *,
    report_dates: list[str],
    anchor_report_date: str,
    duckdb_path: str | Path | None = None,
    governance_dir: str | Path | None = None,
    currency_basis: str = "CNX",
    product_category_refreshed_dates: list[str] | None = None,
    formal_balance_refreshed_dates: list[str] | None = None,
    run_id: str | None = None,
    dry_run: bool = False,
) -> dict[str, object]:
    kwargs = _task_kwargs(
        report_dates=report_dates,
        anchor_report_date=anchor_report_date,
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        currency_basis=currency_basis,
        product_category_refreshed_dates=product_category_refreshed_dates,
        formal_balance_refreshed_dates=formal_balance_refreshed_dates,
        run_id=run_id,
    )
    if dry_run:
        return {
            "status": "dry_run",
            "would_call": kwargs,
            "boundary": dict(BOUNDARY),
        }
    return refresh_accounting_asset_movement_window_sync(**kwargs)


def _task_kwargs(
    *,
    report_dates: list[str],
    anchor_report_date: str,
    duckdb_path: str | Path | None,
    governance_dir: str | Path | None,
    currency_basis: str,
    product_category_refreshed_dates: list[str] | None,
    formal_balance_refreshed_dates: list[str] | None,
    run_id: str | None,
) -> dict[str, object]:
    settings = get_settings()
    normalized_dates = _normalize_date_list(report_dates, field_name="report_dates")
    normalized_anchor = _normalize_iso_date(
        anchor_report_date,
        field_name="anchor_report_date",
    )
    resolved_run_id = (
        run_id.strip()
        if isinstance(run_id, str) and run_id.strip()
        else _default_run_id("accounting_asset_movement_refresh", normalized_anchor)
    )
    return {
        "report_dates": normalized_dates,
        "anchor_report_date": normalized_anchor,
        "duckdb_path": str(Path(duckdb_path) if duckdb_path is not None else settings.duckdb_path),
        "governance_dir": str(
            Path(governance_dir)
            if governance_dir is not None
            else settings.governance_path
        ),
        "currency_basis": str(currency_basis or "CNX").strip() or "CNX",
        "product_category_refreshed_dates": _normalize_date_list(
            product_category_refreshed_dates or normalized_dates,
            field_name="product_category_refreshed_dates",
        ),
        "formal_balance_refreshed_dates": _normalize_date_list(
            formal_balance_refreshed_dates or normalized_dates,
            field_name="formal_balance_refreshed_dates",
        ),
        "run_id": resolved_run_id,
    }


def _normalize_date_list(values: list[str], *, field_name: str) -> list[str]:
    if not values:
        raise ValueError(f"{field_name} is required.")
    normalized: list[str] = []
    for value in values:
        date_text = _normalize_iso_date(value, field_name=field_name)
        if date_text not in normalized:
            normalized.append(date_text)
    return normalized


def _normalize_iso_date(value: str, *, field_name: str) -> str:
    text = str(value or "").strip()[:10]
    if not text:
        raise ValueError(f"{field_name} is required.")
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"{field_name} must contain YYYY-MM-DD values.") from exc
    return text


def _default_run_id(job_name: str, report_date: str) -> str:
    stamp = datetime.now(UTC).isoformat()
    return f"{job_name}:{report_date}:{stamp}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the accounting asset movement task-level refresh wrapper.",
    )
    parser.add_argument("--report-date", action="append", dest="report_dates")
    parser.add_argument("--anchor-report-date")
    parser.add_argument("--duckdb-path")
    parser.add_argument("--governance-dir")
    parser.add_argument("--currency-basis", default="CNX")
    parser.add_argument(
        "--product-category-refreshed-date",
        action="append",
        dest="product_category_refreshed_dates",
    )
    parser.add_argument(
        "--formal-balance-refreshed-date",
        action="append",
        dest="formal_balance_refreshed_dates",
    )
    parser.add_argument("--run-id")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    report_dates = args.report_dates or []
    anchor_report_date = args.anchor_report_date or (report_dates[-1] if report_dates else "")
    try:
        result = run_accounting_asset_movement_refresh(
            report_dates=report_dates,
            anchor_report_date=anchor_report_date,
            duckdb_path=args.duckdb_path,
            governance_dir=args.governance_dir,
            currency_basis=args.currency_basis,
            product_category_refreshed_dates=args.product_category_refreshed_dates,
            formal_balance_refreshed_dates=args.formal_balance_refreshed_dates,
            run_id=args.run_id,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result.get("status") in {"completed", "dry_run"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
