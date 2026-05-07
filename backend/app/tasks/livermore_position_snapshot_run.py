from __future__ import annotations

import argparse
import json
import sys

from backend.app.governance.settings import get_settings
from backend.app.services.market_data_livermore_service import _risk_exit_input_block_reason
from backend.app.tasks.livermore_position_snapshot_materialize import (
    FACT_SOURCE,
    materialize_livermore_position_snapshot,
)


def _emit_json_payload(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stdout)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Materialize Livermore position snapshots into DuckDB."
    )
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument("--csv-path")
    parser.add_argument("--duckdb-path")
    parser.add_argument(
        "--check-risk-inputs",
        action="store_true",
        help="Check whether landed Livermore position facts can feed risk_exit.",
    )
    args = parser.parse_args()

    if not args.csv_path and not args.check_risk_inputs:
        parser.error("--csv-path is required unless --check-risk-inputs is set.")

    duckdb_path = args.duckdb_path or str(get_settings().duckdb_path)
    if args.csv_path:
        payload = materialize_livermore_position_snapshot(
            as_of_date=args.as_of_date,
            csv_path=args.csv_path,
            duckdb_path=args.duckdb_path,
        )
    else:
        payload = {
            "status": "blocked",
            "fact_source": FACT_SOURCE,
            "as_of_date": args.as_of_date,
        }

    if args.check_risk_inputs:
        block_reason = _risk_exit_input_block_reason(
            duckdb_path=duckdb_path,
            as_of_date=args.as_of_date,
        )
        payload["risk_exit_input_status"] = "blocked" if block_reason else "ready"
        payload["risk_exit_input_block_reason"] = block_reason

    _emit_json_payload(payload)


if __name__ == "__main__":
    main()
