#!/usr/bin/env python3
"""Backfill fact_livermore_gate_supplement_daily from landed CSI300 macro history.

Derives breadth_5d and limit_up_quality_ok (CSI300 proxy) and writes DuckDB via the
existing task/materialize path. Use after choice_macro refresh or when stock-analysis
shows LIVERMORE_BREADTH_MISSING / LIVERMORE_LIMIT_UP_QUALITY_MISSING.

Usage (repo root):
  python scripts/backfill_livermore_gate_supplement.py
  python scripts/backfill_livermore_gate_supplement.py --as-of 2026-05-27 --lookback-days 90
  python scripts/backfill_livermore_gate_supplement.py --duckdb-path data/moss.duckdb --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def backfill_livermore_gate_supplement(
    *,
    duckdb_path: str | Path,
    as_of_date: date | None = None,
    lookback_days: int = 90,
    dry_run: bool = False,
) -> dict[str, object]:
    resolved_path = Path(duckdb_path)
    if not resolved_path.is_absolute():
        resolved_path = ROOT / resolved_path
    if not resolved_path.exists():
        raise FileNotFoundError(f"DuckDB file not found: {resolved_path}")

    if dry_run:
        from backend.app.services.livermore_gate_supplement_compute_service import (
            _load_csi300_daily_returns,
        )

        target = as_of_date or date.today()
        daily_returns = _load_csi300_daily_returns(
            duckdb_path=str(resolved_path),
            end_date=target,
            lookback_days=lookback_days,
        )
        return {
            "status": "dry_run",
            "duckdb_path": str(resolved_path),
            "as_of_date": target.isoformat(),
            "lookback_days": lookback_days,
            "csi300_return_points": len(daily_returns),
            "first_return_date": daily_returns[0]["trade_date"] if daily_returns else None,
            "last_return_date": daily_returns[-1]["trade_date"] if daily_returns else None,
        }

    from backend.app.services.livermore_gate_supplement_compute_service import (
        compute_and_materialize_gate_supplement,
    )

    return compute_and_materialize_gate_supplement(
        duckdb_path=str(resolved_path),
        as_of_date=as_of_date,
        lookback_days=lookback_days,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill Livermore gate supplement (breadth / limit-up proxy) into DuckDB."
    )
    parser.add_argument("--duckdb-path", default="data/moss.duckdb")
    parser.add_argument("--as-of", default="", help="Optional YYYY-MM-DD end date (default: today).")
    parser.add_argument("--lookback-days", type=int, default=90, help="CSI300 history window (default 90).")
    parser.add_argument("--dry-run", action="store_true", help="Inspect CSI300 returns without writing.")
    args = parser.parse_args()

    parsed_as_of: date | None = None
    if args.as_of.strip():
        parsed_as_of = date.fromisoformat(args.as_of.strip())

    try:
        result = backfill_livermore_gate_supplement(
            duckdb_path=args.duckdb_path,
            as_of_date=parsed_as_of,
            lookback_days=max(7, int(args.lookback_days)),
            dry_run=args.dry_run,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    status = str(result.get("status") or "")
    if status in {"completed", "dry_run"}:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
