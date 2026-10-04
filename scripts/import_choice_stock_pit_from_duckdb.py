from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.tasks.choice_stock_pit_import import (  # noqa: E402
    import_choice_stock_pit_snapshot,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import one date's three reviewed native Choice PIT inputs from a staging DuckDB."
    )
    parser.add_argument("--duckdb-path", default="data/moss.duckdb")
    parser.add_argument("--source-duckdb-path", required=True)
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument("--expected-source-sha256", required=True)
    parser.add_argument("--receipt-path", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-plan-sha256", default="")
    parser.add_argument("--target-backup-path", default="")
    args = parser.parse_args()

    receipt_path = Path(args.receipt_path)
    try:
        result = import_choice_stock_pit_snapshot(
            args.duckdb_path,
            source_duckdb_path=args.source_duckdb_path,
            as_of_date=args.as_of_date,
            expected_source_sha256=args.expected_source_sha256,
            receipt_path=receipt_path,
            apply_changes=bool(args.apply),
            expected_plan_sha256=args.expected_plan_sha256 or None,
            target_backup_path=args.target_backup_path or None,
        )
    except Exception as exc:
        if receipt_path.exists():
            try:
                result = json.loads(receipt_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                result = {"status": "failed", "error": " ".join(str(exc).split())[:1000]}
        else:
            result = {"status": "failed", "error": " ".join(str(exc).split())[:1000]}
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, default=str))
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
