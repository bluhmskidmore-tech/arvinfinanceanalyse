"""Check freshness of the stock-analysis critical supply series."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.governance.settings import get_settings  # noqa: E402
from backend.app.services.supply_freshness_service import (  # noqa: E402
    DEFAULT_CRITICAL_AFTER_TRADING_DAYS,
    DEFAULT_STALE_AFTER_TRADING_DAYS,
    build_supply_freshness_report,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duckdb-path", type=Path, help="Override the configured DuckDB path.")
    parser.add_argument(
        "--governance-path",
        type=Path,
        help="Override the configured governance directory.",
    )
    parser.add_argument(
        "--as-of-date",
        help="Evaluation date (YYYY-MM-DD); defaults to today and rolls weekends back.",
    )
    parser.add_argument(
        "--stale-after-trading-days",
        type=int,
        default=DEFAULT_STALE_AFTER_TRADING_DAYS,
    )
    parser.add_argument(
        "--critical-after-trading-days",
        type=int,
        default=DEFAULT_CRITICAL_AFTER_TRADING_DAYS,
    )
    parser.add_argument(
        "--fail-on",
        choices=("stale", "critical"),
        default="critical",
        help=(
            "Return exit code 1 at this severity. Missing/unavailable inputs fail "
            "at either level (default: critical)."
        ),
    )
    parser.add_argument("--json", action="store_true", help="Print the structured JSON report.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    settings = get_settings()
    duckdb_path = args.duckdb_path or Path(settings.duckdb_path)
    governance_path = args.governance_path or Path(settings.governance_path)
    try:
        report = build_supply_freshness_report(
            duckdb_path=duckdb_path,
            governance_path=governance_path,
            as_of_date=args.as_of_date,
            stale_after_trading_days=args.stale_after_trading_days,
            critical_after_trading_days=args.critical_after_trading_days,
        )
    except ValueError as exc:
        parser.error(str(exc))

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_human_report(report)
    return 1 if _should_fail(report, fail_on=args.fail_on) else 0


def _should_fail(report: dict[str, object], *, fail_on: str) -> bool:
    statuses = {
        str(item.get("status") or "")
        for item in report.get("series", [])
        if isinstance(item, dict)
    }
    always_fail = {"missing", "unavailable"}
    if statuses & always_fail:
        return True
    if fail_on == "stale":
        return bool(statuses & {"stale", "critical"})
    return "critical" in statuses


def _print_human_report(report: dict[str, object]) -> None:
    print(
        "supply_freshness "
        f"status={report.get('status')} expected_date={report.get('expected_date')}"
    )
    for raw_item in report.get("series", []):
        if not isinstance(raw_item, dict):
            continue
        print(
            f"{str(raw_item.get('status') or 'unknown').upper():11} "
            f"{raw_item.get('name')} "
            f"latest_date={raw_item.get('latest_date')} "
            f"lag_trading_days={raw_item.get('lag_trading_days')} "
            f"reason={raw_item.get('reason')}"
        )
    calendar = report.get("calendar")
    if isinstance(calendar, dict) and calendar.get("limitation"):
        print(f"limitation: {calendar['limitation']}")


if __name__ == "__main__":
    raise SystemExit(main())
