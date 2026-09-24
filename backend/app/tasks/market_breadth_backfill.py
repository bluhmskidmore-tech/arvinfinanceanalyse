"""Bounded, idempotent backfill for historical market-breadth v3 rows."""

from __future__ import annotations

import argparse
import json
import uuid
from datetime import date
from pathlib import Path

import duckdb
from backend.app.governance.settings import get_settings
from backend.app.tasks.market_breadth_materialize import (
    MIN_OBSERVATIONS_PER_DAY_DEFAULT,
    RULE_VERSION,
    SOURCE_TABLE,
    TABLE_NAME,
    materialize_market_breadth_daily,
)


def _parse_date(value: str, *, field_name: str) -> date:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} is required.")
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field_name} must use YYYY-MM-DD.") from exc


def _validated_range(start_date: str, end_date: str) -> tuple[date, date]:
    start = _parse_date(start_date, field_name="start_date")
    end = _parse_date(end_date, field_name="end_date")
    if end < start:
        raise ValueError("end_date must be on or after start_date.")
    return start, end


def _require_table(conn: duckdb.DuckDBPyConnection, table_name: str) -> None:
    exists = conn.execute(
        """
        select 1
        from information_schema.tables
        where table_schema = 'main' and table_name = ?
        limit 1
        """,
        [table_name],
    ).fetchone()
    if exists is None:
        raise ValueError(f"Required DuckDB table is missing: {table_name}")


def build_market_breadth_backfill_plan(
    *,
    duckdb_path: str,
    start_date: str,
    end_date: str,
    min_observations_per_day: int = MIN_OBSERVATIONS_PER_DAY_DEFAULT,
) -> dict[str, object]:
    """Read-only plan of stale fact rows that have enough source observations."""

    start, end = _validated_range(start_date, end_date)
    minimum = int(min_observations_per_day)
    if minimum <= 0:
        raise ValueError("min_observations_per_day must be positive.")
    path = Path(duckdb_path)
    if not path.is_file():
        raise ValueError(f"DuckDB file not found: {path}")

    conn = duckdb.connect(str(path), read_only=True)
    try:
        _require_table(conn, SOURCE_TABLE)
        _require_table(conn, TABLE_NAME)
        rows = conn.execute(
            f"""
            with source_by_date as (
              select
                cast(trade_date as varchar) as trade_date,
                count(*) as observation_count
              from {SOURCE_TABLE}
              where pctchange is not null
                and cast(trade_date as date) between cast(? as date) and cast(? as date)
              group by cast(trade_date as varchar)
            )
            select
              cast(fact.trade_date as varchar) as trade_date,
              fact.rule_version,
              coalesce(source.observation_count, 0) as observation_count
            from {TABLE_NAME} fact
            left join source_by_date source
              on source.trade_date = cast(fact.trade_date as varchar)
            where cast(fact.trade_date as date) between cast(? as date) and cast(? as date)
              and fact.rule_version is distinct from ?
            order by cast(fact.trade_date as date)
            """,
            [
                start.isoformat(),
                end.isoformat(),
                start.isoformat(),
                end.isoformat(),
                RULE_VERSION,
            ],
        ).fetchall()
    finally:
        conn.close()

    eligible = [
        {
            "trade_date": str(trade_date),
            "from_rule_version": None if rule_version is None else str(rule_version),
            "observation_count": int(observation_count),
        }
        for trade_date, rule_version, observation_count in rows
        if int(observation_count) >= minimum
    ]
    skipped = [
        {
            "trade_date": str(trade_date),
            "from_rule_version": None if rule_version is None else str(rule_version),
            "observation_count": int(observation_count),
            "reason": "insufficient_source_observations",
        }
        for trade_date, rule_version, observation_count in rows
        if int(observation_count) < minimum
    ]
    return {
        "status": "dry_run",
        "duckdb_path": str(path.resolve()),
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "target_rule_version": RULE_VERSION,
        "min_observations_per_day": minimum,
        "would_recompute_row_count": len(eligible),
        "trade_dates": [str(item["trade_date"]) for item in eligible],
        "rows": eligible,
        "skipped_row_count": len(skipped),
        "skipped_rows": skipped,
    }


def apply_market_breadth_backfill(
    *,
    duckdb_path: str,
    start_date: str,
    end_date: str,
    min_observations_per_day: int = MIN_OBSERVATIONS_PER_DAY_DEFAULT,
    lookback_days: int = 30,
    run_id_prefix: str | None = None,
) -> dict[str, object]:
    """Recompute only stale planned dates, taking the writer lock one date at a time."""

    plan = build_market_breadth_backfill_plan(
        duckdb_path=duckdb_path,
        start_date=start_date,
        end_date=end_date,
        min_observations_per_day=min_observations_per_day,
    )
    trade_dates = [date.fromisoformat(str(value)) for value in plan["trade_dates"]]
    if not trade_dates:
        return {
            **plan,
            "status": "noop",
            "recomputed_row_count": 0,
            "per_date": [],
        }

    prefix = run_id_prefix or f"market_breadth_backfill:{uuid.uuid4().hex[:12]}"
    per_date: list[dict[str, object]] = []
    for trade_date in trade_dates:
        result = materialize_market_breadth_daily(
            duckdb_path=duckdb_path,
            as_of_date=trade_date,
            lookback_days=int(lookback_days),
            min_observations_per_day=int(min_observations_per_day),
            run_id=f"{prefix}:{trade_date.isoformat()}",
            recompute_trade_dates=frozenset({trade_date}),
        )
        if result.get("status") != "completed" or int(
            result.get("daily_written_row_count") or 0
        ) != 1:
            raise RuntimeError(
                f"Market-breadth backfill failed for {trade_date.isoformat()}: {result}"
            )
        per_date.append(
            {
                "trade_date": trade_date.isoformat(),
                "daily_written_row_count": result["daily_written_row_count"],
                "supplement_row_count": result["supplement_row_count"],
                "rule_version": result["rule_version"],
                "run_id": result["run_id"],
            }
        )

    return {
        **plan,
        "status": "completed",
        "run_id_prefix": prefix,
        "recomputed_row_count": len(per_date),
        "per_date": per_date,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", default=None)
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument(
        "--min-observations-per-day",
        type=int,
        default=MIN_OBSERVATIONS_PER_DAY_DEFAULT,
    )
    parser.add_argument("--lookback-days", type=int, default=30)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Read and print the plan only.")
    mode.add_argument("--apply", action="store_true", help="Apply the planned per-date rewrites.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    db_path = str(args.db_path or get_settings().duckdb_path)
    common = {
        "duckdb_path": db_path,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "min_observations_per_day": args.min_observations_per_day,
    }
    if args.dry_run:
        payload = build_market_breadth_backfill_plan(**common)
    else:
        payload = apply_market_breadth_backfill(
            **common,
            lookback_days=args.lookback_days,
        )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
