#!/usr/bin/env python3
"""Roll forward livermore_position_snapshot ACTIVE rows to the latest CSI300 trade date.

Fixes LIVERMORE_RISK_INPUTS_MISSING when holdings exist but as_of_date lags broad-index
resolution. Does not invent new holdings — copies the latest ACTIVE snapshot and bumps
bars_since_entry by intervening CSI300 trading days.

Usage (repo root):
  python scripts/sync_livermore_position_snapshot.py --dry-run
  python scripts/sync_livermore_position_snapshot.py --target-as-of 2026-05-27
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

import duckdb

from backend.app.services.market_data_livermore_service import _risk_exit_input_block_reason


def _latest_csi300_trade_date(conn: duckdb.DuckDBPyConnection) -> str | None:
    row = conn.execute(
        """
        select max(cast(trade_date as date))
        from fact_choice_macro_daily
        where series_id = 'CA.CSI300'
        """
    ).fetchone()
    if not row or row[0] is None:
        return None
    value = row[0]
    return value.isoformat() if hasattr(value, "isoformat") else str(value)[:10]


def _latest_active_position_date(conn: duckdb.DuckDBPyConnection) -> str | None:
    row = conn.execute(
        """
        select max(cast(as_of_date as date))
        from livermore_position_snapshot
        where upper(coalesce(position_status, 'ACTIVE')) = 'ACTIVE'
        """
    ).fetchone()
    if not row or row[0] is None:
        return None
    value = row[0]
    return value.isoformat() if hasattr(value, "isoformat") else str(value)[:10]


def _count_csi300_trading_days_between(
    conn: duckdb.DuckDBPyConnection,
    *,
    start_exclusive: str,
    end_inclusive: str,
) -> int:
    row = conn.execute(
        """
        select count(*)::integer
        from fact_choice_macro_daily
        where series_id = 'CA.CSI300'
          and cast(trade_date as date) > cast(? as date)
          and cast(trade_date as date) <= cast(? as date)
        """,
        [start_exclusive, end_inclusive],
    ).fetchone()
    return int(row[0] or 0) if row else 0


def sync_livermore_position_snapshot(
    *,
    duckdb_path: str | Path,
    target_as_of: str | None = None,
    dry_run: bool = False,
) -> dict[str, object]:
    resolved_path = Path(duckdb_path)
    if not resolved_path.is_absolute():
        resolved_path = ROOT / resolved_path
    if not resolved_path.exists():
        raise FileNotFoundError(f"DuckDB file not found: {resolved_path}")

    conn = duckdb.connect(str(resolved_path), read_only=True)
    try:
        tables = {str(row[0]) for row in conn.execute("show tables").fetchall()}
        if "livermore_position_snapshot" not in tables:
            return {
                "status": "blocked",
                "reason": "livermore_position_snapshot table is not materialized.",
                "duckdb_path": str(resolved_path),
            }
        latest_trade = target_as_of or _latest_csi300_trade_date(conn)
        source_date = _latest_active_position_date(conn)
        if not latest_trade:
            return {
                "status": "blocked",
                "reason": "CA.CSI300 trade dates are unavailable.",
                "duckdb_path": str(resolved_path),
            }
        if not source_date:
            return {
                "status": "blocked",
                "reason": "No ACTIVE livermore_position_snapshot rows to roll forward.",
                "duckdb_path": str(resolved_path),
                "target_as_of_date": latest_trade,
            }
        if source_date >= latest_trade:
            block_reason = _risk_exit_input_block_reason(
                duckdb_path=str(resolved_path),
                as_of_date=latest_trade,
            )
            return {
                "status": "noop",
                "duckdb_path": str(resolved_path),
                "source_as_of_date": source_date,
                "target_as_of_date": latest_trade,
                "risk_exit_input_status": "blocked" if block_reason else "ready",
                "risk_exit_input_block_reason": block_reason,
            }

        trading_day_delta = _count_csi300_trading_days_between(
            conn,
            start_exclusive=source_date,
            end_inclusive=latest_trade,
        )
        source_rows = conn.execute(
            """
            select
              stock_code,
              stock_name,
              entry_cost,
              bars_since_entry,
              entry_date,
              position_quantity,
              position_status,
              source_system
            from livermore_position_snapshot
            where as_of_date = ?
              and upper(coalesce(position_status, 'ACTIVE')) = 'ACTIVE'
            order by stock_code asc
            """,
            [source_date],
        ).fetchall()
    finally:
        conn.close()

    if not source_rows:
        return {
            "status": "blocked",
            "reason": f"No ACTIVE rows on source as_of_date {source_date}.",
            "duckdb_path": str(resolved_path),
            "target_as_of_date": latest_trade,
        }

    rolled_rows: list[dict[str, object]] = []
    for row in source_rows:
        bars = row[3]
        bumped_bars = None
        if bars is not None:
            bumped_bars = int(bars) + trading_day_delta
        rolled_rows.append(
            {
                "stock_code": str(row[0] or ""),
                "stock_name": str(row[1] or ""),
                "entry_cost": row[2],
                "bars_since_entry": bumped_bars,
                "entry_date": row[4],
                "position_quantity": row[5],
                "position_status": str(row[6] or "ACTIVE"),
                "source_system": str(row[7] or "livermore_position_snapshot_rollforward"),
            }
        )

    if dry_run:
        return {
            "status": "dry_run",
            "duckdb_path": str(resolved_path),
            "source_as_of_date": source_date,
            "target_as_of_date": latest_trade,
            "trading_day_delta": trading_day_delta,
            "row_count": len(rolled_rows),
            "sample_stock_codes": [str(row["stock_code"]) for row in rolled_rows[:5]],
        }

    from backend.app.tasks.livermore_position_snapshot_materialize import (
        materialize_livermore_position_snapshot_rows,
    )

    payload = materialize_livermore_position_snapshot_rows(
        as_of_date=latest_trade,
        rows=rolled_rows,
        duckdb_path=str(resolved_path),
    )
    block_reason = _risk_exit_input_block_reason(
        duckdb_path=str(resolved_path),
        as_of_date=latest_trade,
    )
    return {
        "status": "completed",
        "duckdb_path": str(resolved_path),
        "source_as_of_date": source_date,
        "target_as_of_date": latest_trade,
        "trading_day_delta": trading_day_delta,
        "materialize_result": payload,
        "risk_exit_input_status": "blocked" if block_reason else "ready",
        "risk_exit_input_block_reason": block_reason,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Roll forward Livermore ACTIVE position snapshot to latest CSI300 trade date."
    )
    parser.add_argument("--duckdb-path", default="data/moss.duckdb")
    parser.add_argument("--target-as-of", default="", help="Optional YYYY-MM-DD target (default: latest CSI300).")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    target = args.target_as_of.strip()[:10] or None
    try:
        result = sync_livermore_position_snapshot(
            duckdb_path=args.duckdb_path,
            target_as_of=target,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    status = str(result.get("status") or "")
    if status in {"completed", "noop", "dry_run"}:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
