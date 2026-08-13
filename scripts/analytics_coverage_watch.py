"""Coverage guard for the formal bond-analytics lane and the month-end yield curve.

Lifecycle: permanent
Verify: python -m pytest tests/test_analytics_coverage_watch.py

Read-only. Two independent cadences are checked, because the surfaces it guards have different
rhythms:

* daily  — every `zqtz_bond_daily_snapshot` report_date must also exist in
  `fact_formal_bond_analytics_daily` and `fact_formal_risk_tensor_daily`.
* month-end — every recent month covered by the snapshot must have at least one
  `fact_formal_yield_curve_daily` observation. The curve is materialized roughly once per month and
  its trade_date is not always the calendar month end, so the check is per month, not per date.

The guard alerts only. It never writes to DuckDB and never triggers a materialization: repairing a
daily gap means holding the formal materialize write lock for ~5s per date (a 59-date gap is ~5
minutes), and repairing a curve gap means fetching vendor curves that shift duration/DV01 for the
whole month. Both are operator decisions, not unattended-timer decisions.
"""

from __future__ import annotations

import argparse
import calendar
from datetime import UTC, date, datetime
import json
import os
from pathlib import Path
import sys
from tempfile import NamedTemporaryFile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.governance.settings import get_settings  # noqa: E402
from backend.app.repositories.duckdb_repo import read_only_connection  # noqa: E402


SUCCESS_STATUSES = frozenset({"covered"})
RECEIPT_SCHEMA_VERSION = 1
TASK_NAME = "analytics_coverage_watch"

UPSTREAM_SNAPSHOT_TABLE = "zqtz_bond_daily_snapshot"
DAILY_FACT_TABLES = (
    "fact_formal_bond_analytics_daily",
    "fact_formal_risk_tensor_daily",
)
YIELD_CURVE_TABLE = "fact_formal_yield_curve_daily"
DEFAULT_CURVE_LOOKBACK_MONTHS = 12
MAX_LISTED_DATES = 50


def _safe_error(exc: BaseException) -> str:
    message = " ".join(str(exc).split()) or "no error details"
    return f"{type(exc).__name__}: {message[:300]}"


def _table_exists(conn, table: str) -> bool:
    rows = conn.execute(
        "select 1 from information_schema.tables where table_name = ? limit 1",
        [table],
    ).fetchall()
    return bool(rows)


def _distinct_dates(conn, table: str, column: str) -> list[str]:
    if not _table_exists(conn, table):
        return []
    rows = conn.execute(
        f"select distinct cast({column} as varchar) from {table} "  # noqa: S608 - identifiers are module constants
        f"where {column} is not null order by 1"
    ).fetchall()
    return [str(row[0]) for row in rows]


def _truncate(dates: list[str]) -> tuple[list[str], bool]:
    if len(dates) <= MAX_LISTED_DATES:
        return dates, False
    return dates[:MAX_LISTED_DATES], True


def _month_key(report_date: str) -> str:
    return report_date[:7]


def _is_calendar_month_end(report_date: str) -> bool:
    parsed = date.fromisoformat(report_date)
    return parsed.day == calendar.monthrange(parsed.year, parsed.month)[1]


def _expected_month_end_dates(upstream_dates: list[str]) -> dict[str, str]:
    """Latest snapshot report_date per covered month — the actionable curve target."""
    expected: dict[str, str] = {}
    for report_date in upstream_dates:
        expected[_month_key(report_date)] = report_date
    return expected


def _month_end_gaps(
    *,
    upstream_dates: list[str],
    curve_dates: list[str],
    lookback_months: int,
) -> tuple[list[str], list[dict[str, str]]]:
    expected_by_month = _expected_month_end_dates(upstream_dates)
    covered_months = sorted(expected_by_month)
    if not covered_months:
        return [], []

    checked_months = covered_months[-max(1, lookback_months):]
    latest_month = covered_months[-1]
    if not _is_calendar_month_end(expected_by_month[latest_month]):
        # The latest month is still in progress; its curve is not due yet.
        checked_months = [month for month in checked_months if month != latest_month]

    curve_months = {_month_key(trade_date) for trade_date in curve_dates}
    missing = [
        {
            "month": month,
            "expected_month_end_report_date": expected_by_month[month],
        }
        for month in checked_months
        if month not in curve_months
    ]
    return checked_months, missing


def _failed_result(*, code: str, message: str, duckdb_path: str) -> dict[str, object]:
    return {
        "status": "failed",
        "checked_at": datetime.now(UTC).isoformat(),
        "duckdb_path": duckdb_path,
        "upstream_table": UPSTREAM_SNAPSHOT_TABLE,
        "upstream_report_date_count": 0,
        "latest_upstream_report_date": None,
        "daily": {},
        "month_end": {},
        "alert": {
            "active": True,
            "code": code,
            "severity": "high",
            "message": message,
        },
    }


def check_analytics_coverage(
    *,
    duckdb_path: str | Path,
    curve_lookback_months: int = DEFAULT_CURVE_LOOKBACK_MONTHS,
) -> dict[str, object]:
    duckdb_path_text = str(duckdb_path)
    try:
        with read_only_connection(duckdb_path_text) as conn:
            upstream_dates = _distinct_dates(conn, UPSTREAM_SNAPSHOT_TABLE, "report_date")
            daily_dates = {
                table: _distinct_dates(conn, table, "report_date")
                for table in DAILY_FACT_TABLES
            }
            curve_dates = _distinct_dates(conn, YIELD_CURVE_TABLE, "trade_date")
    except Exception as exc:  # noqa: BLE001 - the watch must emit an actionable receipt
        return _failed_result(
            code="analytics_coverage_check_failed",
            message=_safe_error(exc),
            duckdb_path=duckdb_path_text,
        )

    checked_at = datetime.now(UTC).isoformat()
    if not upstream_dates:
        return {
            "status": "no_upstream_data",
            "checked_at": checked_at,
            "duckdb_path": duckdb_path_text,
            "upstream_table": UPSTREAM_SNAPSHOT_TABLE,
            "upstream_report_date_count": 0,
            "latest_upstream_report_date": None,
            "daily": {},
            "month_end": {},
            "alert": {
                "active": True,
                "code": "analytics_coverage_upstream_empty",
                "severity": "high",
                "message": (
                    f"No report_date values were found in {UPSTREAM_SNAPSHOT_TABLE}; "
                    "daily analytics coverage cannot be evaluated."
                ),
            },
        }

    upstream_set = set(upstream_dates)
    daily: dict[str, object] = {}
    total_missing_daily = 0
    for table, fact_dates in daily_dates.items():
        missing = sorted(upstream_set.difference(fact_dates))
        listed, truncated = _truncate(missing)
        total_missing_daily += len(missing)
        daily[table] = {
            "report_date_count": len(fact_dates),
            "latest_report_date": fact_dates[-1] if fact_dates else None,
            "missing_count": len(missing),
            "missing_report_dates": listed,
            "missing_report_dates_truncated": truncated,
        }

    checked_months, missing_months = _month_end_gaps(
        upstream_dates=upstream_dates,
        curve_dates=curve_dates,
        lookback_months=curve_lookback_months,
    )
    month_end = {
        "table": YIELD_CURVE_TABLE,
        "lookback_months": curve_lookback_months,
        "checked_months": checked_months,
        "trade_date_count": len(curve_dates),
        "latest_trade_date": curve_dates[-1] if curve_dates else None,
        "missing_count": len(missing_months),
        "missing_months": missing_months,
    }

    result: dict[str, object] = {
        "status": "covered",
        "checked_at": checked_at,
        "duckdb_path": duckdb_path_text,
        "upstream_table": UPSTREAM_SNAPSHOT_TABLE,
        "upstream_report_date_count": len(upstream_dates),
        "latest_upstream_report_date": upstream_dates[-1],
        "daily": daily,
        "month_end": month_end,
        "alert": None,
    }
    if total_missing_daily or missing_months:
        if total_missing_daily and missing_months:
            code = "analytics_coverage_gap"
        elif total_missing_daily:
            code = "analytics_daily_coverage_gap"
        else:
            code = "yield_curve_month_end_gap"
        daily_detail = ", ".join(
            f"{table} missing {daily[table]['missing_count']}"  # type: ignore[index]
            for table in DAILY_FACT_TABLES
        )
        month_detail = ", ".join(
            f"{item['month']} (expected {item['expected_month_end_report_date']})"
            for item in missing_months
        ) or "none"
        result["status"] = "gap_detected"
        result["alert"] = {
            "active": True,
            "code": code,
            "severity": "high",
            "message": (
                f"daily coverage vs {UPSTREAM_SNAPSHOT_TABLE}: {daily_detail}; "
                f"{YIELD_CURVE_TABLE} months missing: {month_detail}"
            ),
        }
    return result


def _write_receipt_atomic(path: Path, receipt: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            json.dump(receipt, handle, ensure_ascii=False, default=str, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary_path.replace(path)
    except Exception:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-once", action="store_true", required=True)
    parser.add_argument("--duckdb-path")
    parser.add_argument(
        "--curve-lookback-months",
        type=int,
        default=DEFAULT_CURVE_LOOKBACK_MONTHS,
    )
    parser.add_argument("--receipt-path", type=Path)
    parser.add_argument(
        "--run-kind",
        choices=("manual", "scheduled"),
        default="manual",
    )
    args = parser.parse_args(argv)
    settings = get_settings()
    result = check_analytics_coverage(
        duckdb_path=args.duckdb_path or settings.duckdb_path,
        curve_lookback_months=args.curve_lookback_months,
    )
    status = str(result.get("status") or "failed")
    exit_code = 0 if status in SUCCESS_STATUSES else 1
    receipt = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "run_kind": args.run_kind,
        "task_name": TASK_NAME,
        "status": status,
        "exit_code": exit_code,
        "alert": result.get("alert"),
        "result": result,
    }
    print(json.dumps(receipt, ensure_ascii=False, default=str))
    if args.receipt_path is not None:
        try:
            _write_receipt_atomic(args.receipt_path, receipt)
        except Exception as exc:  # noqa: BLE001 - receipt durability is mandatory
            print(f"receipt write failed: {_safe_error(exc)}", file=sys.stderr)
            return 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
