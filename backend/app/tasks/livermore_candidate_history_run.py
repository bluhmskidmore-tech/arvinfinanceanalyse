from __future__ import annotations

import argparse
import json
import sys

from backend.app.governance.settings import get_settings
from backend.app.tasks.livermore_candidate_history_materialize import (
    backfill_livermore_candidate_history,
    materialize_livermore_candidate_history,
)


def _emit_json_payload(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stdout)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Livermore candidate history materialization into DuckDB."
    )
    parser.add_argument("--duckdb-path")
    parser.add_argument("--as-of-date")
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    args = parser.parse_args()

    has_single_date = bool(args.as_of_date)
    has_range = bool(args.start_date or args.end_date)
    if has_single_date and has_range:
        parser.error("Use either --as-of-date or --start-date/--end-date, not both.")
    if not has_single_date and not has_range:
        parser.error("Either --as-of-date or --start-date/--end-date is required.")
    if has_range and not (args.start_date and args.end_date):
        parser.error("--start-date and --end-date must be provided together.")

    duckdb_path = args.duckdb_path or str(get_settings().duckdb_path)
    if has_single_date:
        payload = materialize_livermore_candidate_history(
            duckdb_path,
            as_of_date=args.as_of_date,
        )
    else:
        payload = backfill_livermore_candidate_history(
            duckdb_path,
            start_date=args.start_date,
            end_date=args.end_date,
        )
    _emit_json_payload(payload)


if __name__ == "__main__":
    main()
