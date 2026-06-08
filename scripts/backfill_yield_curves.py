from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.tasks.yield_curve_materialize import (  # noqa: E402
    RULE_VERSION,
    SUPPORTED_CURVE_TYPES,
    list_yield_curve_month_end_anchors,
    materialize_yield_curve_month_end_backfill,
)


def _resolve_workspace_path(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return ROOT / path


def _parse_iso_date(value: str, *, field_name: str) -> date:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} is required.")
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be YYYY-MM-DD.") from exc


def _normalize_curve_types(raw_value: str) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for item in str(raw_value or "").split(","):
        curve_type = item.strip().lower()
        if not curve_type:
            continue
        if curve_type not in SUPPORTED_CURVE_TYPES:
            supported = ", ".join(SUPPORTED_CURVE_TYPES)
            raise ValueError(f"Unsupported curve type: {curve_type}. Supported: {supported}")
        if curve_type in seen:
            continue
        normalized.append(curve_type)
        seen.add(curve_type)
    if not normalized:
        raise ValueError("At least one curve type is required.")
    return normalized


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill governed yield curves for month-end trade dates.")
    parser.add_argument("--duckdb-path", default="data/moss.duckdb", help="DuckDB file path.")
    parser.add_argument("--start-date", default="2024-01-31", help="Inclusive start date in YYYY-MM-DD.")
    parser.add_argument("--end-date", default="2026-02-28", help="Inclusive end date in YYYY-MM-DD.")
    parser.add_argument(
        "--curve-types",
        default="treasury,cdb,aaa_credit",
        help="Comma-separated curve types.",
    )
    parser.add_argument(
        "--max-backtrack-days",
        type=int,
        default=40,
        help="How many calendar days to walk backward when the anchor date has no curve snapshot.",
    )
    parser.add_argument("--governance-dir", default="", help="Governance output directory.")
    parser.add_argument("--run-id", default="", help="Optional governance run id.")
    parser.add_argument("--dry-run", action="store_true", help="Print resolved month-end dates without writing data.")
    args = parser.parse_args()

    try:
        start = _parse_iso_date(args.start_date, field_name="start_date")
        end = _parse_iso_date(args.end_date, field_name="end_date")
        if end < start:
            raise ValueError("end_date must be on or after start_date.")
        curve_types = _normalize_curve_types(args.curve_types)
        if args.max_backtrack_days < 0:
            raise ValueError("max_backtrack_days must be non-negative.")
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    duckdb_path = _resolve_workspace_path(args.duckdb_path)
    if not duckdb_path.exists():
        print(f"ERROR: DuckDB file not found: {duckdb_path}", file=sys.stderr)
        return 2

    try:
        dates = list_yield_curve_month_end_anchors(
            duckdb_path=str(duckdb_path),
            start_date=start.isoformat(),
            end_date=end.isoformat(),
        )
    except Exception as exc:
        print(f"ERROR: Failed to resolve month-end dates: {exc}", file=sys.stderr)
        return 2

    print("=== Yield Curve Backfill ===")
    print(f"DuckDB: {duckdb_path}")
    print(f"Date range: {start.isoformat()} -> {end.isoformat()}")
    print(f"Month-end dates: {len(dates)}")
    print(f"Curve types: {', '.join(curve_types)}")
    print(f"Rule version: {RULE_VERSION}")
    print(f"Max backtrack days: {args.max_backtrack_days}")
    print()

    if not dates:
        print("No month-end trading dates found in the requested range.")
        return 0

    if args.dry_run:
        for trade_date in dates:
            print(f"  {trade_date}")
        print()
        print("--dry-run enabled; no data was written.")
        return 0

    payload = materialize_yield_curve_month_end_backfill.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=args.governance_dir or None,
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        curve_types=curve_types,
        max_backtrack_days=args.max_backtrack_days,
        run_id=args.run_id or None,
    )

    print()
    print("=== Backfill Summary ===")
    print(f"Total tasks: {payload['total_tasks']}")
    print(f"Written: {payload['written']}")
    print(f"Skipped: {payload['skipped']}")
    print(f"Failed: {payload['failed']}")

    failures = payload["failures"]
    if failures:
        print()
        print("Failed curves:")
        for failure in failures:
            print(f"  - {failure['anchor_date']} {failure['curve_type']}: {failure['message']}")

    print()
    print(
        "After rerunning the downstream bond analytics materialization, "
        "Campisi roll_down / rate_effect / spread_effect can read governed curve data."
    )
    return 1 if payload["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
