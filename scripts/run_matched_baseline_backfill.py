#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.core_finance.matched_baseline import CONTROL_SAMPLE_SIZE, backfill_matched_baseline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill Livermore matched-baseline control returns.")
    parser.add_argument("--db-path", "--duckdb-path", dest="duckdb_path", default="data/moss.duckdb")
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--sample-size", type=int, default=CONTROL_SAMPLE_SIZE)
    parser.add_argument("--report-path", default="docs/pnl/2026-07-matched-baseline-report.md")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    result = backfill_matched_baseline(
        duckdb_path=args.duckdb_path,
        start_date=args.start_date,
        end_date=args.end_date,
        sample_size=args.sample_size,
        dry_run=args.dry_run,
        report_path=args.report_path,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
