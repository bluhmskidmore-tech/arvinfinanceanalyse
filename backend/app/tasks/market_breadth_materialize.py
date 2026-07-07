"""Materialize daily all-market breadth + limit-up seal/break counts into DuckDB.

Aggregates the already-landed ``choice_stock_daily_observation`` table (full
A-share daily OHLCV with pctchange and exchange limit prices) into
``fact_market_breadth_daily``, then derives the Livermore market-gate
supplement inputs (``breadth_5d`` / ``limit_up_quality_ok``) with the formal
definitions in :mod:`backend.app.core_finance.market_breadth` and writes them
through the existing gate-supplement materialize task.

No vendor calls are made; this is an offline derivation from landed data.
API-safe callers must not use this module (DuckDB write path).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date, timedelta
from pathlib import Path

import duckdb
from backend.app.core_finance.market_breadth import (
    BREADTH_WINDOW_DAYS,
    LIMIT_PRICE_TOLERANCE,
    MarketBreadthDaily,
    build_gate_supplement_values,
)
from backend.app.governance.locks import LockDefinition, acquire_lock
from backend.app.repositories.duckdb_migrations import apply_pending_migrations_on_connection
from backend.app.schema_registry.duckdb_loader import REGISTRY_DIR, parse_registry_sql_text
from backend.app.tasks.livermore_gate_supplement import materialize_livermore_gate_supplement_daily

MARKET_BREADTH_LOCK = LockDefinition(
    key="lock:duckdb:market-breadth-daily",
    ttl_seconds=600,
)
RULE_VERSION = "rv_market_breadth_daily_v1"
SOURCE_TABLE = "choice_stock_daily_observation"
TABLE_NAME = "fact_market_breadth_daily"
# Days with fewer landed observations are treated as partial universe landings
# and excluded (full A-share universe is ~5000+ stocks per day).
MIN_OBSERVATIONS_PER_DAY_DEFAULT = 1000
# Extra calendar-day buffer so the earliest requested date still has a full
# 5-trading-day breadth window plus holiday slack.
_WINDOW_BUFFER_CALENDAR_DAYS = 10


def ensure_market_breadth_daily_schema(conn: duckdb.DuckDBPyConnection) -> None:
    text = (REGISTRY_DIR / "33_market_breadth_daily.sql").read_text(encoding="utf-8")
    for statement in parse_registry_sql_text(text):
        conn.execute(statement)


def materialize_market_breadth_daily(
    *,
    duckdb_path: str,
    as_of_date: date | None = None,
    lookback_days: int = 30,
    min_observations_per_day: int = MIN_OBSERVATIONS_PER_DAY_DEFAULT,
    run_id: str | None = None,
) -> dict[str, object]:
    """Aggregate daily breadth counts and derive gate supplement rows.

    Returns a summary dict; ``status`` is ``insufficient_data`` when the
    landed source table has no usable rows in the window (no writes to the
    gate supplement table happen in that case, preserving the existing
    missing-input degradation).
    """
    target_date = as_of_date or date.today()
    path = Path(duckdb_path)
    if not path.is_file():
        return _insufficient(
            message=f"DuckDB file not found: {path}",
        )
    effective_run = run_id or f"market_breadth:{uuid.uuid4().hex[:12]}"
    window_start = target_date - timedelta(
        days=int(lookback_days) + BREADTH_WINDOW_DAYS + _WINDOW_BUFFER_CALENDAR_DAYS
    )

    with acquire_lock(MARKET_BREADTH_LOCK, base_dir=path.parent):
        conn = duckdb.connect(str(path), read_only=False)
        try:
            apply_pending_migrations_on_connection(conn)
            daily_rows = _aggregate_daily_counts(
                conn,
                window_start=window_start,
                window_end=target_date,
                min_observations_per_day=int(min_observations_per_day),
            )
            if not daily_rows:
                return _insufficient(
                    message=(
                        f"No usable {SOURCE_TABLE} rows between "
                        f"{window_start.isoformat()} and {target_date.isoformat()}."
                    ),
                )
            _replace_daily_rows(conn, daily_rows, run_id=effective_run)
        finally:
            conn.close()

    breadth_rows = [
        MarketBreadthDaily(
            trade_date=date.fromisoformat(str(row["trade_date"])),
            advancing_count=int(row["advancing_count"]),
            declining_count=int(row["declining_count"]),
            limit_up_sealed_count=int(row["limit_up_sealed_count"]),
            limit_up_broken_count=int(row["limit_up_broken_count"]),
        )
        for row in daily_rows
    ]
    supplement_rows = _build_supplement_rows(breadth_rows)

    materialize_result: dict[str, object] | None = None
    if supplement_rows:
        materialize_result = dict(
            materialize_livermore_gate_supplement_daily(
                duckdb_path=str(path),
                rows=supplement_rows,
                run_id=effective_run,
            )
        )

    return {
        "status": "completed",
        "run_id": effective_run,
        "table": TABLE_NAME,
        "rule_version": RULE_VERSION,
        "daily_row_count": len(daily_rows),
        "supplement_row_count": len(supplement_rows),
        "first_date": str(daily_rows[0]["trade_date"]),
        "last_date": str(daily_rows[-1]["trade_date"]),
        "first_supplement_date": str(supplement_rows[0]["trade_date"]) if supplement_rows else None,
        "last_supplement_date": str(supplement_rows[-1]["trade_date"]) if supplement_rows else None,
        "materialize_result": materialize_result,
    }


def _insufficient(*, message: str) -> dict[str, object]:
    return {
        "status": "insufficient_data",
        "message": message,
        "table": TABLE_NAME,
        "rule_version": RULE_VERSION,
        "daily_row_count": 0,
        "supplement_row_count": 0,
    }


def _aggregate_daily_counts(
    conn: duckdb.DuckDBPyConnection,
    *,
    window_start: date,
    window_end: date,
    min_observations_per_day: int,
) -> list[dict[str, object]]:
    exists = conn.execute(
        """
        select 1
        from information_schema.tables
        where table_schema = 'main' and table_name = ?
        limit 1
        """,
        [SOURCE_TABLE],
    ).fetchone()
    if exists is None:
        return []
    rows = conn.execute(
        f"""
        with parsed as (
          select
            cast(trade_date as varchar) as trade_date,
            pctchange,
            close_value,
            high_value,
            try_cast(highlimit as double) as limit_price
          from {SOURCE_TABLE}
          where pctchange is not null
            and cast(trade_date as date) >= cast(? as date)
            and cast(trade_date as date) <= cast(? as date)
        )
        select
          trade_date,
          count(*) as total_count,
          sum(case when pctchange > 0 then 1 else 0 end) as advancing_count,
          sum(case when pctchange < 0 then 1 else 0 end) as declining_count,
          sum(case when pctchange = 0 then 1 else 0 end) as unchanged_count,
          sum(case when limit_price is not null and high_value is not null and close_value is not null
                   and high_value >= limit_price - {LIMIT_PRICE_TOLERANCE}
                   and abs(close_value - limit_price) < {LIMIT_PRICE_TOLERANCE}
              then 1 else 0 end) as limit_up_sealed_count,
          sum(case when limit_price is not null and high_value is not null and close_value is not null
                   and high_value >= limit_price - {LIMIT_PRICE_TOLERANCE}
                   and abs(close_value - limit_price) >= {LIMIT_PRICE_TOLERANCE}
              then 1 else 0 end) as limit_up_broken_count
        from parsed
        group by trade_date
        having count(*) >= ?
        order by trade_date
        """,
        [window_start.isoformat(), window_end.isoformat(), min_observations_per_day],
    ).fetchall()
    return [
        {
            "trade_date": str(row[0]),
            "total_count": int(row[1]),
            "advancing_count": int(row[2]),
            "declining_count": int(row[3]),
            "unchanged_count": int(row[4]),
            "limit_up_sealed_count": int(row[5]),
            "limit_up_broken_count": int(row[6]),
        }
        for row in rows
    ]


def _replace_daily_rows(
    conn: duckdb.DuckDBPyConnection,
    daily_rows: list[dict[str, object]],
    *,
    run_id: str,
) -> None:
    conn.execute("begin transaction")
    try:
        for row in daily_rows:
            conn.execute(
                f"delete from {TABLE_NAME} where trade_date = ?",
                [row["trade_date"]],
            )
            conn.execute(
                f"""
                insert into {TABLE_NAME} (
                  trade_date, total_count, advancing_count, declining_count, unchanged_count,
                  limit_up_sealed_count, limit_up_broken_count,
                  source_version, vendor_version, rule_version, run_id
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    row["trade_date"],
                    row["total_count"],
                    row["advancing_count"],
                    row["declining_count"],
                    row["unchanged_count"],
                    row["limit_up_sealed_count"],
                    row["limit_up_broken_count"],
                    _row_source_version(row),
                    _vendor_version(str(row["trade_date"])),
                    RULE_VERSION,
                    run_id,
                ],
            )
        conn.execute("commit")
    except Exception:
        conn.execute("rollback")
        raise


def _build_supplement_rows(breadth_rows: list[MarketBreadthDaily]) -> list[dict[str, object]]:
    supplement_rows: list[dict[str, object]] = []
    for value in build_gate_supplement_values(breadth_rows):
        trade_date = value["trade_date"]
        trade_date_text = trade_date.isoformat() if isinstance(trade_date, date) else str(trade_date)
        digest = hashlib.sha256(
            json.dumps(
                {
                    "trade_date": trade_date_text,
                    "breadth_5d": value["breadth_5d"],
                    "limit_up_quality_ok": value["limit_up_quality_ok"],
                },
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()[:12]
        supplement_rows.append(
            {
                "trade_date": trade_date,
                "breadth_5d": value["breadth_5d"],
                "limit_up_quality_ok": value["limit_up_quality_ok"],
                "source_version": f"sv_market_breadth_{digest}",
                "vendor_version": _vendor_version(trade_date_text),
            }
        )
    return supplement_rows


def _row_source_version(row: dict[str, object]) -> str:
    digest = hashlib.sha256(
        json.dumps(row, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:12]
    return f"sv_market_breadth_daily_{digest}"


def _vendor_version(trade_date_text: str) -> str:
    return f"vv_choice_stock_daily_observation_{trade_date_text.replace('-', '')}"


materialize_market_breadth_daily.fn = materialize_market_breadth_daily
