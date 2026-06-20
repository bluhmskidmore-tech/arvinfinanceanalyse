"""Compute breadth_5d and limit_up_quality_ok from landed market data.

Uses existing DuckDB tables (fact_choice_macro_daily / choice_market_snapshot)
to derive the market-gate supplement inputs without additional vendor calls.

**Breadth proxy** — 5-day market momentum breadth computed from the ratio of
up-days to total days in a trailing 5-day window of CSI300 daily returns.
When actual A-share advance/decline data becomes available this should be
replaced with a true breadth metric.

**Limit-up quality proxy** — a simplified signal based on CSI300 return
characteristics that approximates whether the quality of limit-up stocks
(sealed vs broken board) is healthy.  When Tushare ``limit_list`` or
Choice ``stk_limit`` data becomes available this should be replaced.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import duckdb
from backend.app.governance.locks import LockDefinition, acquire_lock
from backend.app.governance.settings import get_settings
from backend.app.repositories.governance_repo import CACHE_BUILD_RUN_STREAM, GovernanceRepository
from backend.app.tasks.livermore_gate_supplement import (
    RULE_VERSION as LIVERMORE_GATE_SUPPLEMENT_MATERIALIZE_RULE_VERSION,
)
from backend.app.tasks.livermore_gate_supplement import (
    materialize_livermore_gate_supplement_daily,
)

logger = logging.getLogger(__name__)

RULE_VERSION = "rv_livermore_gate_supplement_compute_v1"
BROAD_INDEX_SERIES_ID = "CA.CSI300"
PCT_CHG_SERIES_ID = "CA.CSI300_PCT_CHG"
BREADTH_WINDOW = 5
# Minimum number of historical daily returns needed to compute supplement.
MIN_HISTORY_FOR_SUPPLEMENT = BREADTH_WINDOW + 1
LIVERMORE_GATE_SUPPLEMENT_REFRESH_JOB_NAME = "livermore_gate_supplement_refresh"
LIVERMORE_GATE_SUPPLEMENT_REFRESH_CACHE_KEY = "livermore_gate_supplement_daily"
LIVERMORE_GATE_SUPPLEMENT_REFRESH_CACHE_VERSION = "cv_livermore_gate_supplement_refresh_v1"
LIVERMORE_GATE_SUPPLEMENT_REFRESH_LOCK_TIMEOUT_SECONDS = 30.0
LIVERMORE_GATE_SUPPLEMENT_IDEMPOTENCY_WAIT_TIMEOUT_SECONDS = 300.0
LIVERMORE_GATE_SUPPLEMENT_IDEMPOTENCY_LOCK_ATTEMPT_SECONDS = 0.25
LIVERMORE_GATE_SUPPLEMENT_IDEMPOTENCY_POLL_SECONDS = 0.05
LIVERMORE_GATE_SUPPLEMENT_IDEMPOTENCY_POLL_MAX_SECONDS = 1.0


def compute_and_materialize_gate_supplement(
    *,
    duckdb_path: str,
    as_of_date: date | None = None,
    lookback_days: int = 30,
    idempotency_key: str | None = None,
) -> dict[str, object]:
    """Compute breadth_5d + limit_up_quality_ok and write to DuckDB supplement table.

    Returns a summary dict suitable for API response.
    """
    target_date = as_of_date or date.today()
    target_date_text = target_date.isoformat()
    normalized_idempotency_key = _normalize_idempotency_key(idempotency_key)
    storage_target_digest = _storage_target_digest(duckdb_path)
    settings = get_settings()

    lock_definition = _refresh_trigger_lock(
        as_of_date=target_date_text,
        lookback_days=lookback_days,
        storage_target_digest=storage_target_digest,
    )
    if normalized_idempotency_key is not None:
        return _run_idempotent_refresh(
            duckdb_path=duckdb_path,
            target_date=target_date,
            target_date_text=target_date_text,
            lookback_days=lookback_days,
            idempotency_key=normalized_idempotency_key,
            storage_target_digest=storage_target_digest,
            lock_definition=lock_definition,
        )

    with acquire_lock(
        lock_definition,
        base_dir=settings.governance_path,
        timeout_seconds=LIVERMORE_GATE_SUPPLEMENT_REFRESH_LOCK_TIMEOUT_SECONDS,
    ):
        return _compute_gate_supplement_payload(
            duckdb_path=duckdb_path,
            target_date=target_date,
            target_date_text=target_date_text,
            lookback_days=lookback_days,
            idempotency_key=None,
            storage_target_digest=storage_target_digest,
        )


def _run_idempotent_refresh(
    *,
    duckdb_path: str,
    target_date: date,
    target_date_text: str,
    lookback_days: int,
    idempotency_key: str,
    storage_target_digest: str,
    lock_definition: LockDefinition,
) -> dict[str, object]:
    settings = get_settings()
    deadline = time.monotonic() + LIVERMORE_GATE_SUPPLEMENT_IDEMPOTENCY_WAIT_TIMEOUT_SECONDS
    poll_seconds = LIVERMORE_GATE_SUPPLEMENT_IDEMPOTENCY_POLL_SECONDS

    while True:
        existing_run = _latest_refresh_for_idempotency_key(
            as_of_date=target_date_text,
            lookback_days=lookback_days,
            idempotency_key=idempotency_key,
            storage_target_digest=storage_target_digest,
        )
        if existing_run is not None:
            return _idempotent_refresh_response(existing_run)

        remaining_seconds = deadline - time.monotonic()
        if remaining_seconds <= 0:
            existing_run = _latest_refresh_for_idempotency_key(
                as_of_date=target_date_text,
                lookback_days=lookback_days,
                idempotency_key=idempotency_key,
                storage_target_digest=storage_target_digest,
            )
            if existing_run is not None:
                return _idempotent_refresh_response(existing_run)
            raise TimeoutError(
                "Timed out waiting for Livermore gate supplement idempotency replay "
                f"as_of_date={target_date_text} lookback_days={int(lookback_days)}."
            )

        acquired_lock = False
        try:
            with acquire_lock(
                lock_definition,
                base_dir=settings.governance_path,
                timeout_seconds=min(
                    LIVERMORE_GATE_SUPPLEMENT_IDEMPOTENCY_LOCK_ATTEMPT_SECONDS,
                    remaining_seconds,
                ),
                poll_interval_seconds=min(
                    LIVERMORE_GATE_SUPPLEMENT_IDEMPOTENCY_POLL_SECONDS,
                    max(remaining_seconds, 0.0),
                ),
            ):
                acquired_lock = True
                existing_run = _latest_refresh_for_idempotency_key(
                    as_of_date=target_date_text,
                    lookback_days=lookback_days,
                    idempotency_key=idempotency_key,
                    storage_target_digest=storage_target_digest,
                )
                if existing_run is not None:
                    return _idempotent_refresh_response(existing_run)
                return _compute_gate_supplement_payload(
                    duckdb_path=duckdb_path,
                    target_date=target_date,
                    target_date_text=target_date_text,
                    lookback_days=lookback_days,
                    idempotency_key=idempotency_key,
                    storage_target_digest=storage_target_digest,
                )
        except TimeoutError:
            if acquired_lock:
                raise
            existing_run = _latest_refresh_for_idempotency_key(
                as_of_date=target_date_text,
                lookback_days=lookback_days,
                idempotency_key=idempotency_key,
                storage_target_digest=storage_target_digest,
            )
            if existing_run is not None:
                return _idempotent_refresh_response(existing_run)
            sleep_seconds = min(
                poll_seconds,
                max(deadline - time.monotonic(), 0.0),
            )
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)
                poll_seconds = min(
                    poll_seconds * 2,
                    LIVERMORE_GATE_SUPPLEMENT_IDEMPOTENCY_POLL_MAX_SECONDS,
                )


def _compute_gate_supplement_payload(
    *,
    duckdb_path: str,
    target_date: date,
    target_date_text: str,
    lookback_days: int,
    idempotency_key: str | None,
    storage_target_digest: str,
) -> dict[str, object]:
    daily_returns = _load_csi300_daily_returns(
        duckdb_path=duckdb_path,
        end_date=target_date,
        lookback_days=lookback_days,
    )

    if len(daily_returns) < MIN_HISTORY_FOR_SUPPLEMENT:
        return {
            "status": "insufficient_data",
            "message": (
                f"Need at least {MIN_HISTORY_FOR_SUPPLEMENT} daily return "
                f"observations; found {len(daily_returns)}."
            ),
            "computed_rows": 0,
            "idempotency_key": idempotency_key,
            "idempotency_replay": False,
        }

    supplement_rows = _compute_supplement_rows(daily_returns)
    if not supplement_rows:
        return {
            "status": "no_computable_dates",
            "message": "No trade dates yielded computable supplement rows.",
            "computed_rows": 0,
            "idempotency_key": idempotency_key,
            "idempotency_replay": False,
        }

    result = materialize_livermore_gate_supplement_daily(
        duckdb_path=duckdb_path,
        rows=supplement_rows,
    )

    payload: dict[str, object] = {
        "status": "completed",
        "computed_rows": len(supplement_rows),
        "first_date": str(supplement_rows[0]["trade_date"]),
        "last_date": str(supplement_rows[-1]["trade_date"]),
        "materialize_result": result,
        "idempotency_key": idempotency_key,
        "idempotency_replay": False,
    }
    if idempotency_key is not None:
        _record_idempotent_refresh(
            as_of_date=target_date_text,
            lookback_days=lookback_days,
            idempotency_key=idempotency_key,
            storage_target_digest=storage_target_digest,
            response_payload=payload,
        )
    return payload


def _normalize_idempotency_key(value: str | None) -> str | None:
    text = str(value or "").strip()
    return text or None


def _storage_target_digest(duckdb_path: str) -> str:
    target = Path(duckdb_path).expanduser().resolve(strict=False)
    return hashlib.sha256(os.path.normcase(str(target)).encode("utf-8")).hexdigest()[:16]


def _refresh_trigger_lock(*, as_of_date: str, lookback_days: int, storage_target_digest: str) -> LockDefinition:
    return LockDefinition(
        key=(
            "lock:livermore-gate-supplement-refresh:"
            f"{as_of_date}:{int(lookback_days)}:{storage_target_digest}"
        ),
        ttl_seconds=30,
    )


def _load_refresh_run_records() -> list[dict[str, object]]:
    settings = get_settings()
    return [
        record
        for record in GovernanceRepository(base_dir=settings.governance_path).read_all(CACHE_BUILD_RUN_STREAM)
        if str(record.get("cache_key")) == LIVERMORE_GATE_SUPPLEMENT_REFRESH_CACHE_KEY
        and str(record.get("job_name")) == LIVERMORE_GATE_SUPPLEMENT_REFRESH_JOB_NAME
    ]


def _latest_refresh_for_idempotency_key(
    *,
    as_of_date: str,
    lookback_days: int,
    idempotency_key: str,
    storage_target_digest: str,
) -> dict[str, object] | None:
    for record in reversed(_load_refresh_run_records()):
        if str(record.get("idempotency_key") or "").strip() != idempotency_key:
            continue
        if str(record.get("as_of_date")) != as_of_date:
            continue
        if str(record.get("lookback_days")) != str(int(lookback_days)):
            continue
        if str(record.get("storage_target_digest") or "").strip() != storage_target_digest:
            continue
        return record
    return None


def _idempotent_refresh_response(record: dict[str, object]) -> dict[str, object]:
    response_payload = record.get("response_payload")
    if isinstance(response_payload, dict):
        payload = dict(response_payload)
    else:
        payload = {
            "status": str(record.get("status") or "completed"),
            "materialize_result": {"run_id": str(record.get("run_id") or "")},
        }
    payload["idempotency_key"] = _normalize_idempotency_key(str(record.get("idempotency_key") or ""))
    payload["idempotency_replay"] = True
    return payload


def _record_idempotent_refresh(
    *,
    as_of_date: str,
    lookback_days: int,
    idempotency_key: str,
    storage_target_digest: str,
    response_payload: dict[str, object],
) -> None:
    settings = get_settings()
    materialize_result = response_payload.get("materialize_result")
    materialize_payload = materialize_result if isinstance(materialize_result, dict) else {}
    run_id = str(materialize_payload.get("run_id") or "")
    GovernanceRepository(base_dir=settings.governance_path).append(
        CACHE_BUILD_RUN_STREAM,
        {
            "run_id": run_id,
            "job_name": LIVERMORE_GATE_SUPPLEMENT_REFRESH_JOB_NAME,
            "status": "completed",
            "cache_key": LIVERMORE_GATE_SUPPLEMENT_REFRESH_CACHE_KEY,
            "cache_version": LIVERMORE_GATE_SUPPLEMENT_REFRESH_CACHE_VERSION,
            "rule_version": str(
                materialize_payload.get("rule_version") or LIVERMORE_GATE_SUPPLEMENT_MATERIALIZE_RULE_VERSION
            ),
            "report_date": as_of_date,
            "as_of_date": as_of_date,
            "lookback_days": int(lookback_days),
            "idempotency_key": idempotency_key,
            "storage_target_digest": storage_target_digest,
            "response_payload": response_payload,
            "finished_at": datetime.now(UTC).isoformat(),
        },
    )


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_csi300_daily_returns(
    *,
    duckdb_path: str,
    end_date: date,
    lookback_days: int,
) -> list[dict[str, Any]]:
    """Load CSI300 close + pct_chg from landed macro tables.

    Returns list of dicts with keys: trade_date (date), close (float),
    pct_chg (float | None).
    """
    duckdb_file = Path(duckdb_path)
    if not duckdb_file.exists():
        return []

    try:
        conn = duckdb.connect(str(duckdb_file), read_only=True)
    except duckdb.Error:
        return []

    try:
        tables = {row[0] for row in conn.execute("show tables").fetchall()}
        close_rows = _query_series_history(
            conn, tables, BROAD_INDEX_SERIES_ID, end_date, lookback_days
        )
        pct_chg_rows = _query_series_history(
            conn, tables, PCT_CHG_SERIES_ID, end_date, lookback_days
        )
    except duckdb.Error:
        return []
    finally:
        conn.close()

    # Index pct_chg by date
    pct_chg_by_date: dict[str, float] = {}
    for row in pct_chg_rows:
        pct_chg_by_date[row["trade_date"]] = row["value"]

    # Build merged list, computing pct_chg from close if not available
    result: list[dict[str, Any]] = []
    sorted_close = sorted(close_rows, key=lambda r: r["trade_date"])
    for i, row in enumerate(sorted_close):
        td = row["trade_date"]
        pct = pct_chg_by_date.get(td)
        if pct is None and i > 0:
            prev_close = sorted_close[i - 1]["value"]
            if prev_close and prev_close > 0:
                pct = (row["value"] - prev_close) / prev_close * 100
        result.append({
            "trade_date": td,
            "close": row["value"],
            "pct_chg": pct,
        })

    return result


def _query_series_history(
    conn: duckdb.DuckDBPyConnection,
    tables: set[str],
    series_id: str,
    end_date: date,
    lookback_days: int,
) -> list[dict[str, Any]]:
    """Query a single series from fact_choice_macro_daily / choice_market_snapshot."""
    queries: list[str] = []
    params: list[object] = []

    lookback_extra = lookback_days + BREADTH_WINDOW + 10  # extra buffer

    if "fact_choice_macro_daily" in tables:
        queries.append("""
            select
              cast(trade_date as date) as trade_date,
              cast(value_numeric as double) as value_numeric,
              0 as src_rank
            from fact_choice_macro_daily
            where series_id = ?
              and value_numeric is not null
              and cast(trade_date as date) <= ?
              and cast(trade_date as date) >= ?
        """)
        params.extend([series_id, end_date.isoformat(),
                       _offset_date(end_date, lookback_extra)])

    if "choice_market_snapshot" in tables:
        queries.append("""
            select
              cast(trade_date as date) as trade_date,
              cast(value_numeric as double) as value_numeric,
              1 as src_rank
            from choice_market_snapshot
            where series_id = ?
              and value_numeric is not null
              and cast(trade_date as date) <= ?
              and cast(trade_date as date) >= ?
        """)
        params.extend([series_id, end_date.isoformat(),
                       _offset_date(end_date, lookback_extra)])

    if not queries:
        return []

    sql = f"""
        with unioned as (
          {" union all ".join(queries)}
        ),
        deduped as (
          select
            trade_date,
            value_numeric,
            row_number() over (
              partition by trade_date
              order by src_rank asc
            ) as rn
          from unioned
        )
        select trade_date, value_numeric
        from deduped
        where rn = 1
        order by trade_date asc
    """
    rows = conn.execute(sql, params).fetchall()
    return [
        {"trade_date": str(row[0]), "value": float(row[1])}
        for row in rows
        if row[0] is not None and row[1] is not None
    ]


def _offset_date(d: date, days: int) -> str:
    from datetime import timedelta
    return (d - timedelta(days=days)).isoformat()


# ---------------------------------------------------------------------------
# Computation
# ---------------------------------------------------------------------------

def _compute_supplement_rows(
    daily_returns: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Compute breadth_5d and limit_up_quality_ok for each trade date.

    breadth_5d:
      Ratio of up-days (pct_chg > 0) in the trailing BREADTH_WINDOW days.
      Range [0.0, 1.0].  A value > 0.5 means more up-days than down-days.

    limit_up_quality_ok:
      True when the market shows healthy momentum characteristics:
      - No single-day drawdown exceeding -3% in the trailing window
      - Average return in the window is positive
      This is a proxy; replace with actual limit-up seal/break data when available.
    """
    rows: list[dict[str, Any]] = []
    for i in range(BREADTH_WINDOW, len(daily_returns)):
        window = daily_returns[i - BREADTH_WINDOW : i]
        current = daily_returns[i]
        td = current["trade_date"]

        # Skip if any window element lacks pct_chg
        pct_values = [d["pct_chg"] for d in window]
        if any(v is None for v in pct_values):
            continue

        # Breadth: ratio of positive return days
        up_days = sum(1 for v in pct_values if v > 0)
        breadth_5d = round(up_days / BREADTH_WINDOW, 4)

        # Limit-up quality proxy
        avg_return = sum(pct_values) / len(pct_values)
        max_drawdown = min(pct_values)
        limit_up_quality_ok = bool(avg_return > 0 and max_drawdown > -3.0)

        source_digest = hashlib.sha256(
            json.dumps(
                {"trade_date": td, "breadth_5d": breadth_5d, "lim": limit_up_quality_ok},
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()[:12]

        rows.append({
            "trade_date": td,
            "breadth_5d": breadth_5d,
            "limit_up_quality_ok": limit_up_quality_ok,
            "source_version": f"sv_gate_supplement_compute_{source_digest}",
            "vendor_version": f"vv_gate_supplement_proxy_{td.replace('-', '')}",
        })

    return rows
