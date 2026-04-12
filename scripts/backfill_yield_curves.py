from __future__ import annotations

import argparse
import sys
from datetime import date
from datetime import timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import duckdb

from backend.app.repositories.akshare_adapter import VendorAdapter
from backend.app.repositories.yield_curve_repo import YieldCurveRepository


SUPPORTED_CURVE_TYPES = ("treasury", "cdb", "aaa_credit")
# Keep this aligned with backend.app.tasks.yield_curve_materialize.RULE_VERSION.
RULE_VERSION = "rv_yield_curve_formal_materialize_v1"


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


def get_month_end_dates(duckdb_path: Path, start_date: str, end_date: str) -> list[str]:
    """Return the last available trading date of each month from zqtz snapshots."""
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        row = conn.execute(
            """
            select 1
            from information_schema.tables
            where table_name = 'zqtz_bond_daily_snapshot'
            limit 1
            """
        ).fetchone()
        if row is None:
            raise RuntimeError("DuckDB is missing table zqtz_bond_daily_snapshot.")

        rows = conn.execute(
            """
            with scoped_dates as (
              select cast(report_date as date) as report_date
              from zqtz_bond_daily_snapshot
              where cast(report_date as date) between ? and ?
            )
            select max(report_date) as month_end
            from scoped_dates
            group by extract(year from report_date), extract(month from report_date)
            order by month_end
            """,
            [start_date, end_date],
        ).fetchall()
        return [month_end.isoformat() for (month_end,) in rows if month_end is not None]
    finally:
        conn.close()


def backfill_curve(
    *,
    adapter: VendorAdapter,
    repo: YieldCurveRepository,
    trade_date: str,
    curve_type: str,
    rule_version: str,
    max_backtrack_days: int,
) -> tuple[bool, str]:
    """Fetch and persist a single curve snapshot, walking backward when the anchor date is unavailable."""
    anchor = date.fromisoformat(trade_date)
    failures: list[str] = []
    for offset in range(max_backtrack_days + 1):
        candidate_date = (anchor - timedelta(days=offset)).isoformat()
        try:
            snapshot = adapter.fetch_yield_curve(curve_type=curve_type, trade_date=candidate_date)
            repo.replace_curve_snapshots(
                trade_date=snapshot.trade_date,
                snapshots=[snapshot],
                rule_version=rule_version,
            )
            if snapshot.trade_date == trade_date:
                return True, f"{snapshot.vendor_name} @ {snapshot.trade_date}"
            return True, f"{snapshot.vendor_name} @ {snapshot.trade_date} (fallback from {trade_date})"
        except Exception as exc:
            failures.append(f"{candidate_date}: {exc}")
    return False, " | ".join(failures[-3:])


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
        dates = get_month_end_dates(duckdb_path, start.isoformat(), end.isoformat())
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

    adapter = VendorAdapter()
    preflight = adapter.preflight()
    print(f"AkShare preflight: {preflight.detail}")
    if not preflight.ok:
        print("Continuing anyway: fetch_yield_curve may still succeed through Choice or ChinaBond fallbacks.")
    print()

    repo = YieldCurveRepository(str(duckdb_path))
    total = len(dates) * len(curve_types)
    skipped = 0
    written = 0
    failed = 0
    failures: list[tuple[str, str, str]] = []

    for index, trade_date in enumerate(dates, start=1):
        print(f"[{index}/{len(dates)}] {trade_date}")
        for curve_type in curve_types:
            existing = repo.fetch_curve_snapshot(trade_date, curve_type)
            if existing is not None:
                print(f"  SKIP {curve_type}: already present")
                skipped += 1
                continue

            ok, detail = backfill_curve(
                adapter=adapter,
                repo=repo,
                trade_date=trade_date,
                curve_type=curve_type,
                rule_version=RULE_VERSION,
                max_backtrack_days=args.max_backtrack_days,
            )
            if ok:
                print(f"  OK   {curve_type}: written via {detail}")
                written += 1
            else:
                print(f"  FAIL {curve_type}: {detail}")
                failed += 1
                failures.append((trade_date, curve_type, detail))

    print()
    print("=== Backfill Summary ===")
    print(f"Total tasks: {total}")
    print(f"Written: {written}")
    print(f"Skipped: {skipped}")
    print(f"Failed: {failed}")

    if failures:
        print()
        print("Failed curves:")
        for trade_date, curve_type, message in failures:
            print(f"  - {trade_date} {curve_type}: {message}")

    print()
    print(
        "After rerunning the downstream bond analytics materialization, "
        "Campisi roll_down / rate_effect / spread_effect can read governed curve data."
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
