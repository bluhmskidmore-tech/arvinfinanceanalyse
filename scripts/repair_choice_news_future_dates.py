from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.tasks.choice_news import repair_existing_choice_news_future_dates


def _resolve_workspace_path(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return ROOT / path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Repair existing Choice news future dates using governed task-layer logic."
    )
    parser.add_argument("--duckdb-path", default="data/moss.duckdb", help="DuckDB file path.")
    parser.add_argument("--as-of-date", required=True, help="Report as-of date in YYYY-MM-DD.")
    parser.add_argument("--run-id", default="", help="Optional governance run id.")
    parser.add_argument("--governance-dir", default="", help="Governance output directory.")
    args = parser.parse_args()

    duckdb_path = _resolve_workspace_path(args.duckdb_path)
    if not duckdb_path.exists():
        print(f"ERROR: DuckDB file not found: {duckdb_path}", file=sys.stderr)
        return 2

    payload = repair_existing_choice_news_future_dates(
        duckdb_path=str(duckdb_path),
        as_of_date=args.as_of_date,
        run_id=args.run_id or None,
        governance_dir=args.governance_dir or None,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["unresolved_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
