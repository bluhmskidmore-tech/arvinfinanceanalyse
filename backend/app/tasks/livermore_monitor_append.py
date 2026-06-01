from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import duckdb

TABLE_HIST = "livermore_candidate_history"
_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MONITOR_JSONL = _REPO_ROOT / "data" / "livermore_monitor.jsonl"


def append_daily_monitor(
    *,
    duckdb_path: str,
    as_of_date: str | None = None,
    monitor_jsonl_path: str | None = None,
) -> dict:
    """Append one daily Livermore monitor JSON line after candidate-history backfill."""
    duckdb_file = Path(duckdb_path)
    if not duckdb_file.is_file():
        return {}

    try:
        conn = duckdb.connect(str(duckdb_file), read_only=True)
    except Exception:
        return {}

    try:
        tables = {str(row[0]) for row in conn.execute("show tables").fetchall()}
        if TABLE_HIST not in tables:
            return {}

        resolved_as_of = _resolve_as_of_date(conn, as_of_date)
        if not resolved_as_of:
            record = _empty_monitor_record()
            _append_jsonl_line(record, monitor_jsonl_path)
            return record

        day_row = conn.execute(
            f"""
            select
              coalesce(sum(case when signal_kind = 'stock_candidate' then 1 else 0 end), 0),
              coalesce(sum(case when signal_kind = 'mean_reversion' then 1 else 0 end), 0),
              max(formula_version),
              max(
                coalesce(
                  nullif(trim(market_state), ''),
                  nullif(trim(json_extract_string(signal_evidence_json, '$.market_state')), '')
                )
              )
            from {TABLE_HIST}
            where snapshot_as_of_date = ?
            """,
            [resolved_as_of],
        ).fetchone()

        rolling_row = conn.execute(
            f"""
            select
              sum(case when return_5d > 0 then 1 else 0 end) * 1.0
                / nullif(count(return_5d), 0) as win_5d,
              avg(return_5d) as avg_5d
            from {TABLE_HIST}
            where signal_kind = 'stock_candidate'
              and return_5d is not null
              and snapshot_as_of_date in (
                select distinct snapshot_as_of_date
                from {TABLE_HIST}
                where snapshot_as_of_date <= ?
                order by snapshot_as_of_date desc
                limit 20
              )
            """,
            [resolved_as_of],
        ).fetchone()
    except Exception:
        return {}
    finally:
        conn.close()

    stock_count = int(day_row[0] or 0) if day_row else 0
    mean_reversion_count = int(day_row[1] or 0) if day_row else 0
    formula_version = _optional_text(day_row[2] if day_row else None)
    market_state = _optional_text(day_row[3] if day_row else None)

    rolling_win = _optional_float(rolling_row[0] if rolling_row else None)
    rolling_avg = _optional_float(rolling_row[1] if rolling_row else None)

    record: dict[str, object] = {
        "as_of_date": resolved_as_of,
        "stock_candidate_count": stock_count,
        "mean_reversion_count": mean_reversion_count,
        "rolling_win_5d_20d": rolling_win,
        "rolling_avg_5d_20d": rolling_avg,
        "formula_version": formula_version,
        "market_state": market_state,
        "timestamp": _monitor_timestamp(resolved_as_of),
    }
    _append_jsonl_line(record, monitor_jsonl_path)
    return record


def _resolve_as_of_date(conn: duckdb.DuckDBPyConnection, as_of_date: str | None) -> str | None:
    if as_of_date is not None:
        text = as_of_date.strip()
        if not text:
            return None
        return date.fromisoformat(text[:10]).isoformat()

    row = conn.execute(
        f"""
        select max(snapshot_as_of_date)
        from {TABLE_HIST}
        where snapshot_as_of_date is not null
        """
    ).fetchone()
    if row is None or row[0] is None:
        return None
    text = str(row[0]).strip()
    if len(text) < 10:
        return None
    try:
        return date.fromisoformat(text[:10].replace("/", "-")).isoformat()
    except ValueError:
        return None


def _empty_monitor_record() -> dict[str, object]:
    return {
        "as_of_date": None,
        "stock_candidate_count": 0,
        "mean_reversion_count": 0,
        "rolling_win_5d_20d": None,
        "rolling_avg_5d_20d": None,
        "formula_version": None,
        "market_state": None,
        "timestamp": datetime.now().replace(microsecond=0).isoformat(timespec="seconds"),
    }


def _monitor_timestamp(as_of_date: str) -> str:
    now = datetime.now().replace(microsecond=0)
    try:
        day = date.fromisoformat(as_of_date[:10])
    except ValueError:
        return now.isoformat(timespec="seconds")
    return datetime.combine(day, now.time()).isoformat(timespec="seconds")


def _append_jsonl_line(record: dict[str, object], monitor_jsonl_path: str | None) -> None:
    path = Path(monitor_jsonl_path) if monitor_jsonl_path else DEFAULT_MONITOR_JSONL
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
        handle.write("\n")


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), 6)
    except (TypeError, ValueError):
        return None
