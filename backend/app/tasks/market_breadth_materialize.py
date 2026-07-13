"""Materialize daily all-market breadth + limit-up seal/break counts into DuckDB.

Aggregates the already-landed ``choice_stock_daily_observation`` table (full
A-share daily OHLCV with pctchange) into
``fact_market_breadth_daily``, then derives the Livermore market-gate
supplement inputs (``breadth_5d`` / ``limit_up_quality_ok``) with the formal
definitions in :mod:`backend.app.core_finance.market_breadth` and writes them
through the existing gate-supplement materialize task.

Choice ``HIGHLIMIT`` is a yes/no flag, not a price. When the latest landed
date does not contain numeric limit prices, this task loads that date's
Tushare ``stk_limit.up_limit`` prices before classifying sealed/broken boards.
API-safe callers must not use this module (DuckDB write path).
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path

import duckdb
import requests
from backend.app.core_finance.market_breadth import (
    BREADTH_WINDOW_DAYS,
    LIMIT_PRICE_TOLERANCE,
    MarketBreadthDaily,
    build_gate_supplement_values,
)
from backend.app.governance.locks import LockDefinition, acquire_lock
from backend.app.governance.settings import get_settings
from backend.app.repositories.duckdb_migrations import apply_pending_migrations_on_connection
from backend.app.repositories.tushare_adapter import resolve_tushare_token_with_settings_fallback
from backend.app.schema_registry.duckdb_loader import REGISTRY_DIR, parse_registry_sql_text
from backend.app.tasks.livermore_gate_supplement import materialize_livermore_gate_supplement_daily

MARKET_BREADTH_LOCK = LockDefinition(
    key="lock:duckdb:market-breadth-daily",
    ttl_seconds=600,
)
logger = logging.getLogger(__name__)

RULE_VERSION = "rv_market_breadth_daily_v2"
SOURCE_TABLE = "choice_stock_daily_observation"
TABLE_NAME = "fact_market_breadth_daily"
TUSHARE_PRO_API_URL = "https://api.tushare.pro"
TUSHARE_PRO_TIMEOUT_SECONDS = (10.0, 30.0)
LimitPriceLoader = Callable[[date], dict[str, float]]
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
    limit_price_loader: LimitPriceLoader | None = None,
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
            write_latest_only = any(
                int(row.get("numeric_limit_price_count") or 0) < int(row["total_count"])
                for row in daily_rows
            )
            limit_price_evidence = _enrich_latest_limit_counts(
                conn,
                daily_rows,
                limit_price_loader=limit_price_loader or _load_tushare_limit_prices,
            )
            if not bool(limit_price_evidence["limit_price_complete"]):
                return {
                    "status": str(limit_price_evidence["limit_price_failure_status"]),
                    "message": str(limit_price_evidence["limit_price_message"]),
                    "table": TABLE_NAME,
                    "rule_version": RULE_VERSION,
                    "daily_row_count": 0,
                    "supplement_row_count": 0,
                    **limit_price_evidence,
                }
            daily_rows_to_write = [daily_rows[-1]] if write_latest_only else daily_rows
            _replace_daily_rows(conn, daily_rows_to_write, run_id=effective_run)
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
    if write_latest_only:
        latest_trade_date = str(daily_rows[-1]["trade_date"])
        supplement_rows = [
            row for row in supplement_rows if str(row["trade_date"]) == latest_trade_date
        ]
    vendor_version_by_date = {
        str(row["trade_date"]): str(row.get("vendor_version") or _vendor_version(str(row["trade_date"])))
        for row in daily_rows
    }
    for row in supplement_rows:
        row["vendor_version"] = vendor_version_by_date.get(
            str(row["trade_date"]),
            str(row["vendor_version"]),
        )

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
        "daily_written_row_count": len(daily_rows_to_write),
        "supplement_row_count": len(supplement_rows),
        "first_date": str(daily_rows[0]["trade_date"]),
        "last_date": str(daily_rows[-1]["trade_date"]),
        "first_supplement_date": str(supplement_rows[0]["trade_date"]) if supplement_rows else None,
        "last_supplement_date": str(supplement_rows[-1]["trade_date"]) if supplement_rows else None,
        "historical_rows_preserved": len(daily_rows) - len(daily_rows_to_write),
        **limit_price_evidence,
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
              then 1 else 0 end) as limit_up_broken_count,
          sum(case when limit_price is not null then 1 else 0 end) as numeric_limit_price_count
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
            "numeric_limit_price_count": int(row[7]),
        }
        for row in rows
    ]


def _enrich_latest_limit_counts(
    conn: duckdb.DuckDBPyConnection,
    daily_rows: list[dict[str, object]],
    *,
    limit_price_loader: LimitPriceLoader,
) -> dict[str, object]:
    latest = daily_rows[-1]
    trade_date_text = str(latest["trade_date"])
    total_count = int(latest["total_count"])
    numeric_count = int(latest.get("numeric_limit_price_count") or 0)
    if numeric_count == total_count:
        return {
            "limit_price_complete": True,
            "limit_price_basis": "landed_numeric_highlimit",
            "limit_price_matched_count": numeric_count,
        }
    if numeric_count > 0:
        return {
            "limit_price_complete": False,
            "limit_price_failure_status": "limit_price_incomplete",
            "limit_price_message": (
                f"Landed numeric limit prices matched {numeric_count} of {total_count} "
                f"stocks for {trade_date_text}; no rows were written."
            ),
            "limit_price_basis": "incomplete_landed_numeric_highlimit",
            "limit_price_matched_count": numeric_count,
        }

    trade_date_value = date.fromisoformat(trade_date_text)
    try:
        prices = limit_price_loader(trade_date_value)
    except Exception as exc:
        logger.warning(
            "Tushare stk_limit enrichment failed for %s; existing rows are preserved.",
            trade_date_text,
            exc_info=True,
        )
        return {
            "limit_price_complete": False,
            "limit_price_failure_status": "limit_price_unavailable",
            "limit_price_message": (
                f"Tushare stk_limit was unavailable for {trade_date_text}; "
                "no rows were written."
            ),
            "limit_price_basis": "unavailable",
            "limit_price_matched_count": 0,
            "limit_price_error": f"{type(exc).__name__}: {exc}",
        }

    matched_count, sealed_count, broken_count = _classify_limit_counts(
        conn,
        trade_date=trade_date_value,
        limit_prices=prices,
    )
    if matched_count != total_count:
        return {
            "limit_price_complete": False,
            "limit_price_failure_status": "limit_price_incomplete",
            "limit_price_message": (
                f"Tushare stk_limit matched {matched_count} of {total_count} stocks "
                f"for {trade_date_text}; no rows were written."
            ),
            "limit_price_basis": "incomplete_tushare_stk_limit",
            "limit_price_matched_count": matched_count,
        }

    digest = hashlib.sha256(
        json.dumps(prices, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:12]
    latest["limit_up_sealed_count"] = sealed_count
    latest["limit_up_broken_count"] = broken_count
    latest["vendor_version"] = (
        f"{_vendor_version(trade_date_text)}+"
        f"vv_tushare_stk_limit_{trade_date_text.replace('-', '')}_{digest}"
    )
    return {
        "limit_price_complete": True,
        "limit_price_basis": "tushare_stk_limit",
        "limit_price_matched_count": matched_count,
    }


def _classify_limit_counts(
    conn: duckdb.DuckDBPyConnection,
    *,
    trade_date: date,
    limit_prices: dict[str, float],
) -> tuple[int, int, int]:
    rows = conn.execute(
        f"""
        select stock_code, high_value, close_value
        from {SOURCE_TABLE}
        where cast(trade_date as date) = cast(? as date)
          and pctchange is not null
          and high_value is not null
          and close_value is not null
        """,
        [trade_date.isoformat()],
    ).fetchall()
    matched_count = 0
    sealed_count = 0
    broken_count = 0
    for stock_code, high_value, close_value in rows:
        limit_price = limit_prices.get(str(stock_code))
        if limit_price is None:
            continue
        matched_count += 1
        if float(high_value) < limit_price - LIMIT_PRICE_TOLERANCE:
            continue
        if abs(float(close_value) - limit_price) < LIMIT_PRICE_TOLERANCE:
            sealed_count += 1
        else:
            broken_count += 1
    return matched_count, sealed_count, broken_count


def _load_tushare_limit_prices(trade_date: date) -> dict[str, float]:
    token = resolve_tushare_token_with_settings_fallback(get_settings())
    if not token:
        raise RuntimeError("MOSS_TUSHARE_TOKEN or settings.tushare_token is required.")
    response = requests.post(
        TUSHARE_PRO_API_URL,
        json={
            "api_name": "stk_limit",
            "token": token,
            "params": {"trade_date": trade_date.strftime("%Y%m%d")},
            "fields": "trade_date,ts_code,up_limit,down_limit",
        },
        timeout=TUSHARE_PRO_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    if int(payload.get("code") or 0) != 0:
        raise RuntimeError(str(payload.get("msg") or "Tushare stk_limit request failed."))
    data = payload.get("data") or {}
    fields = [str(value) for value in data.get("fields") or []]
    positions = {name: index for index, name in enumerate(fields)}
    if "ts_code" not in positions or "up_limit" not in positions:
        raise RuntimeError("Tushare stk_limit response is missing ts_code/up_limit.")
    prices: dict[str, float] = {}
    for item in data.get("items") or []:
        try:
            code = str(item[positions["ts_code"]]).strip()
            value = float(item[positions["up_limit"]])
        except (IndexError, TypeError, ValueError):
            continue
        if code and value > 0:
            prices[code] = value
    if not prices:
        raise RuntimeError(f"Tushare stk_limit returned no usable prices for {trade_date.isoformat()}.")
    return prices


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
                    str(row.get("vendor_version") or _vendor_version(str(row["trade_date"]))),
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
