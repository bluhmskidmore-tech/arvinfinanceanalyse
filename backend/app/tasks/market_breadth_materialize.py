"""Materialize daily all-market breadth + limit-up seal/break counts into DuckDB.

Aggregates the already-landed ``choice_stock_daily_observation`` table (full
A-share daily OHLCV with pctchange) into
``fact_market_breadth_daily``, then derives the Livermore market-gate
supplement inputs (``breadth_5d`` / ``limit_up_quality_ok``) with the formal
definitions in :mod:`backend.app.core_finance.market_breadth` and writes them
through the existing gate-supplement materialize task.

Choice ``HIGHLIMIT`` is a yes/no flag, not a price, so the limit-up leg is
built on that flag plus a derived limit price (see
:mod:`backend.app.core_finance.market_breadth`): the flag names sealed boards
and the derivation finds boards that were touched intraday and lost. ST names
come from the latest ``choice_stock_universe`` snapshot at or before the trade
date.

The Tushare ``stk_limit`` price basis is kept only as an opt-in cross-check:
pass ``limit_price_loader`` (for example :func:`_load_tushare_limit_prices`) to
record an independent count alongside the flag basis. It never gates the
result, so a vendor outage can no longer make ``limit_up_quality_ok`` missing.

Advance/decline breadth does not depend on the limit-up leg, so a date whose
limit-up leg is unavailable still lands its breadth counts; only
``limit_up_quality_ok`` degrades to missing (``NULL``) for that date, and a
previously materialized limit-up leg for the same date is kept.
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
    LimitUpDaySummary,
    LimitUpObservation,
    MarketBreadthDaily,
    build_gate_supplement_values,
    is_st_name,
    summarize_limit_up_day,
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

RULE_VERSION = "rv_market_breadth_daily_v3"
SOURCE_TABLE = "choice_stock_daily_observation"
UNIVERSE_TABLE = "choice_stock_universe"
TABLE_NAME = "fact_market_breadth_daily"
LIMIT_UP_BASIS = "choice_highlimit_flag_and_derived_limit_price"
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
    missing-input degradation). An unresolvable limit-up leg only sets
    ``limit_up_quality_available`` to ``False``; the breadth rows still land.

    Only the latest window date and window dates that have no row yet are
    written; rows already materialized under a superseded rule version are
    left untouched.
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
            latest_row = daily_rows[-1]
            latest_trade_date = str(latest_row["trade_date"])
            dates_to_write = _resolve_dates_to_write(conn, daily_rows)
            limit_up_evidence = _apply_limit_up_legs(
                conn,
                daily_rows,
                dates_to_write=dates_to_write,
            )
            unavailable_dates = set(limit_up_evidence.pop("limit_up_unavailable_dates"))
            if latest_trade_date in unavailable_dates and _keep_last_known_limit_counts(
                conn, latest_row
            ):
                unavailable_dates.discard(latest_trade_date)
            limit_up_quality_available = latest_trade_date not in unavailable_dates
            limit_price_evidence = _cross_check_latest_limit_prices(
                conn,
                latest_row,
                limit_price_loader=limit_price_loader,
            )
            daily_rows_to_write = [
                row for row in daily_rows if str(row["trade_date"]) in dates_to_write
            ]
            _replace_daily_rows(conn, daily_rows_to_write, run_id=effective_run)
        finally:
            conn.close()

    breadth_rows = [
        MarketBreadthDaily(
            trade_date=date.fromisoformat(str(row["trade_date"])),
            advancing_count=int(row["advancing_count"]),
            declining_count=int(row["declining_count"]),
            limit_up_sealed_count=int(row["limit_up_sealed_count"] or 0),
            limit_up_broken_count=int(row["limit_up_broken_count"] or 0),
        )
        for row in daily_rows
    ]
    supplement_rows = [
        row
        for row in _build_supplement_rows(
            breadth_rows,
            quality_unavailable_dates=frozenset(
                date.fromisoformat(text) for text in unavailable_dates
            ),
        )
        if str(row["trade_date"]) in dates_to_write
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
        **limit_up_evidence,
        **limit_price_evidence,
        "limit_up_quality_available": limit_up_quality_available,
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
    if not _table_exists(conn, SOURCE_TABLE):
        return []
    rows = conn.execute(
        f"""
        with parsed as (
          select
            cast(trade_date as varchar) as trade_date,
            pctchange
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
          sum(case when pctchange = 0 then 1 else 0 end) as unchanged_count
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
            "limit_up_sealed_count": None,
            "limit_up_broken_count": None,
        }
        for row in rows
    ]


def _table_exists(conn: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    return (
        conn.execute(
            """
            select 1
            from information_schema.tables
            where table_schema = 'main' and table_name = ?
            limit 1
            """,
            [table_name],
        ).fetchone()
        is not None
    )


def _resolve_dates_to_write(
    conn: duckdb.DuckDBPyConnection,
    daily_rows: list[dict[str, object]],
) -> frozenset[str]:
    """Latest window date plus window dates that have no materialized row yet.

    Rows written under a superseded rule version keep their values; only the
    latest date is refreshed on every run.
    """
    window_dates = [str(row["trade_date"]) for row in daily_rows]
    placeholders = ", ".join("?" for _ in window_dates)
    existing = {
        str(row[0])
        for row in conn.execute(
            f"select trade_date from {TABLE_NAME} where trade_date in ({placeholders})",
            window_dates,
        ).fetchall()
    }
    return frozenset(
        trade_date
        for trade_date in window_dates
        if trade_date == window_dates[-1] or trade_date not in existing
    )


def _apply_limit_up_legs(
    conn: duckdb.DuckDBPyConnection,
    daily_rows: list[dict[str, object]],
    *,
    dates_to_write: frozenset[str],
) -> dict[str, object]:
    """Classify sealed/broken boards for the dates being written, in place.

    Returns coverage evidence for the latest date plus the set of dates whose
    limit-up leg stays unavailable (vendor flag absent for the whole day).
    """
    latest_trade_date = str(daily_rows[-1]["trade_date"])
    st_names_available = _table_exists(conn, UNIVERSE_TABLE)
    observations_by_date = _load_limit_up_observations(
        conn,
        trade_dates=sorted(dates_to_write),
        st_names_available=st_names_available,
    )
    unavailable_dates: list[str] = []
    latest_summary: LimitUpDaySummary | None = None
    for row in daily_rows:
        trade_date_text = str(row["trade_date"])
        if trade_date_text not in dates_to_write:
            continue
        summary = summarize_limit_up_day(observations_by_date.get(trade_date_text, []))
        if trade_date_text == latest_trade_date:
            latest_summary = summary
        if not summary.evaluable:
            unavailable_dates.append(trade_date_text)
            continue
        row["limit_up_sealed_count"] = summary.sealed_count
        row["limit_up_broken_count"] = summary.broken_count
        row["vendor_version"] = (
            f"{_vendor_version(trade_date_text)}+"
            f"vv_choice_highlimit_flag_{trade_date_text.replace('-', '')}"
        )
    evidence = _limit_up_evidence(
        latest_summary,
        observations=observations_by_date.get(latest_trade_date, []),
        st_names_available=st_names_available,
    )
    evidence["limit_up_unavailable_dates"] = tuple(unavailable_dates)
    return evidence


def _limit_up_evidence(
    summary: LimitUpDaySummary | None,
    *,
    observations: list[LimitUpObservation],
    st_names_available: bool,
) -> dict[str, object]:
    """Coverage evidence for the latest date, including when it stays unavailable."""
    if summary is None:
        return {"limit_up_basis": LIMIT_UP_BASIS, "limit_up_flag_basis_available": False}
    return {
        "limit_up_basis": LIMIT_UP_BASIS,
        "limit_up_flag_basis_available": summary.evaluable,
        "limit_up_sealed_count": summary.sealed_count,
        "limit_up_broken_count": summary.broken_count,
        "limit_up_touched_count": summary.sealed_count + summary.broken_count,
        "limit_up_no_touch_count": summary.no_touch_count,
        "limit_up_out_of_band_count": summary.out_of_band_count,
        "limit_up_unclassified_count": summary.unclassified_count,
        "limit_up_absent_flag_count": summary.absent_flag_count,
        "limit_up_sealed_without_derived_touch_count": (
            summary.sealed_without_derived_touch_count
        ),
        "limit_up_st_name_source": UNIVERSE_TABLE if st_names_available else "unavailable",
        "limit_up_st_named_count": sum(
            1 for observation in observations if is_st_name(observation.stock_name)
        ),
        "limit_up_coverage_note": _limit_up_coverage_note(st_names_available=st_names_available),
    }


def _limit_up_coverage_note(*, st_names_available: bool) -> str:
    parts = [
        "Sealed boards come from the Choice HIGHLIMIT flag; broken boards are "
        "derived from prev_close = close / (1 + pctchange/100) and the board "
        "limit ratio.",
    ]
    parts.append(
        "ST names come from the latest choice_stock_universe snapshot at or "
        "before the trade date; the ST band is dropped when a row's own move "
        "is already wider than it."
        if st_names_available
        else "choice_stock_universe is not landed, so every main-board code "
        "uses the plain board band (ST approximated by board band)."
    )
    parts.append(
        "No listing-date field is landed, so first-day new listings are not "
        "excluded by date; rows whose own move sits outside their board band "
        "are reported as limit_up_out_of_band_count and left unclassified."
    )
    return " ".join(parts)


def _load_limit_up_observations(
    conn: duckdb.DuckDBPyConnection,
    *,
    trade_dates: list[str],
    st_names_available: bool,
) -> dict[str, list[LimitUpObservation]]:
    if not trade_dates:
        return {}
    placeholders = ", ".join("?" for _ in trade_dates)
    name_expression = (
        f"""(
          select u.stock_name
          from {UNIVERSE_TABLE} u
          where u.stock_code = o.stock_code
            and cast(u.as_of_date as varchar) <= cast(o.trade_date as varchar)
          order by u.as_of_date desc
          limit 1
        )"""
        if st_names_available
        else "cast(null as varchar)"
    )
    rows = conn.execute(
        f"""
        select
          cast(o.trade_date as varchar) as trade_date,
          o.stock_code,
          o.highlimit,
          o.pctchange,
          o.close_value,
          o.high_value,
          {name_expression} as stock_name
        from {SOURCE_TABLE} o
        where cast(o.trade_date as varchar) in ({placeholders})
        """,
        trade_dates,
    ).fetchall()
    observations_by_date: dict[str, list[LimitUpObservation]] = {}
    for trade_date, stock_code, limit_flag, pctchange, close_value, high_value, stock_name in rows:
        observations_by_date.setdefault(str(trade_date), []).append(
            LimitUpObservation(
                stock_code=str(stock_code),
                limit_flag=None if limit_flag is None else str(limit_flag),
                pctchange=None if pctchange is None else float(pctchange),
                close_value=None if close_value is None else float(close_value),
                high_value=None if high_value is None else float(high_value),
                stock_name=None if stock_name is None else str(stock_name),
            )
        )
    return observations_by_date


def _cross_check_latest_limit_prices(
    conn: duckdb.DuckDBPyConnection,
    latest_row: dict[str, object],
    *,
    limit_price_loader: LimitPriceLoader | None,
) -> dict[str, object]:
    """Independent limit-price count for the latest date; evidence only.

    Never raises and never changes the landed counts, so a vendor outage
    cannot make ``limit_up_quality_ok`` missing.
    """
    if limit_price_loader is None:
        return {"limit_price_cross_check": "not_attempted"}
    trade_date_text = str(latest_row["trade_date"])
    try:
        prices = limit_price_loader(date.fromisoformat(trade_date_text))
        matched_count, sealed_count, broken_count = _classify_limit_counts(
            conn,
            trade_date=date.fromisoformat(trade_date_text),
            limit_prices=prices,
        )
    except Exception as exc:
        logger.info(
            "Limit-price cross-check unavailable for %s; the flag basis is unaffected.",
            trade_date_text,
            exc_info=True,
        )
        return {
            "limit_price_cross_check": "unavailable",
            "limit_price_cross_check_error": f"{type(exc).__name__}: {exc}",
        }
    landed_sealed = latest_row.get("limit_up_sealed_count")
    landed_broken = latest_row.get("limit_up_broken_count")
    if matched_count != int(latest_row["total_count"]):
        status = "incomplete"
    elif sealed_count == landed_sealed and broken_count == landed_broken:
        status = "agreed"
    else:
        status = "disagreed"
    return {
        "limit_price_cross_check": status,
        "limit_price_cross_check_matched_count": matched_count,
        "limit_price_cross_check_sealed_count": sealed_count,
        "limit_price_cross_check_broken_count": broken_count,
    }


def _keep_last_known_limit_counts(
    conn: duckdb.DuckDBPyConnection,
    latest_row: dict[str, object],
) -> bool:
    """Resolve the limit-up leg for a date whose vendor flag basis is absent.

    A limit-up leg already materialized for that trade date stays authoritative
    (a later vendor outage must not erase it). Otherwise the counts are stored
    as ``NULL`` so "not classified" never reads as "no boards", and the caller
    degrades ``limit_up_quality_ok`` to missing. Returns whether limit-up
    quality remains evaluable for that date.
    """
    existing = conn.execute(
        f"""
        select limit_up_sealed_count, limit_up_broken_count, vendor_version
        from {TABLE_NAME}
        where trade_date = ?
        """,
        [latest_row["trade_date"]],
    ).fetchone()
    if existing is not None and existing[0] is not None and existing[1] is not None:
        latest_row["limit_up_sealed_count"] = int(existing[0])
        latest_row["limit_up_broken_count"] = int(existing[1])
        if existing[2]:
            latest_row["vendor_version"] = str(existing[2])
        return True
    latest_row["limit_up_sealed_count"] = None
    latest_row["limit_up_broken_count"] = None
    return False


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


def _build_supplement_rows(
    breadth_rows: list[MarketBreadthDaily],
    *,
    quality_unavailable_dates: frozenset[date] = frozenset(),
) -> list[dict[str, object]]:
    """Gate supplement inputs; dates in ``quality_unavailable_dates`` carry a missing limit-up leg."""
    supplement_rows: list[dict[str, object]] = []
    for value in build_gate_supplement_values(breadth_rows):
        trade_date = value["trade_date"]
        trade_date_text = trade_date.isoformat() if isinstance(trade_date, date) else str(trade_date)
        limit_up_quality_ok = (
            None if trade_date in quality_unavailable_dates else value["limit_up_quality_ok"]
        )
        digest = hashlib.sha256(
            json.dumps(
                {
                    "trade_date": trade_date_text,
                    "breadth_5d": value["breadth_5d"],
                    "limit_up_quality_ok": limit_up_quality_ok,
                },
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()[:12]
        supplement_rows.append(
            {
                "trade_date": trade_date,
                "breadth_5d": value["breadth_5d"],
                "limit_up_quality_ok": limit_up_quality_ok,
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
