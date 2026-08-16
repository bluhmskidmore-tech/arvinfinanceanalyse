from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import duckdb
from backend.app.core_finance.livermore_strategy import (
    BroadIndexObservation,
    MarketGateSupplement,
    evaluate_market_gate,
)

BENCHMARK_SERIES_ID = "CA.CSI300"
TABLE_BENCHMARK_DAILY = "fact_choice_macro_daily"
TABLE_BENCHMARK_SNAPSHOT = "choice_market_snapshot"
TABLE_GATE_SUPPLEMENT = "fact_livermore_gate_supplement_daily"
TABLE_CANDIDATE_HISTORY = "livermore_candidate_history"
PERSISTED_EXPOSURE_TABLES = ("livermore_monitor_append", "livermore_gate_history", "livermore_gate_supplement")


@dataclass(frozen=True)
class ExposurePoint:
    exposure: float
    state: str
    source: str


def load_gate_exposure_by_date(
    conn: duckdb.DuckDBPyConnection,
    start: str | date,
    end: str | date,
) -> dict[str, ExposurePoint]:
    start_date = _parse_date(start)
    end_date = _parse_date(end)
    if end_date < start_date:
        raise ValueError("end must be on or after start")

    tables = _table_names(conn)
    points = _load_persisted_points(conn, tables=tables, start=start_date, end=end_date)
    replayed = _replay_points(conn, tables=tables, start=start_date, end=end_date)
    for date_key, point in replayed.items():
        points.setdefault(date_key, point)

    for day in _date_range(start_date, end_date):
        points.setdefault(day.isoformat(), ExposurePoint(exposure=0.0, state="NO_DATA", source="missing"))
    return {key: points[key] for key in sorted(points)}


def _load_persisted_points(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    start: date,
    end: date,
) -> dict[str, ExposurePoint]:
    points: dict[str, ExposurePoint] = {}
    for table in PERSISTED_EXPOSURE_TABLES:
        generic_points = _load_generic_persisted_points(
            conn,
            tables=tables,
            table=table,
            start=start,
            end=end,
        )
        for date_key, point in generic_points.items():
            points.setdefault(date_key, point)
    for date_key, point in _load_candidate_history_points(conn, tables=tables, start=start, end=end).items():
        points.setdefault(date_key, point)
    return points


def _load_candidate_history_points(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    start: date,
    end: date,
) -> dict[str, ExposurePoint]:
    if TABLE_CANDIDATE_HISTORY not in tables:
        return {}
    columns = _columns(conn, TABLE_CANDIDATE_HISTORY)
    if not {"snapshot_as_of_date", "signal_evidence_json"}.issubset(columns):
        return {}
    rows = conn.execute(
        f"""
        select snapshot_as_of_date, signal_evidence_json
        from {TABLE_CANDIDATE_HISTORY}
        where signal_evidence_json is not null
          and cast(snapshot_as_of_date as date) >= cast(? as date)
          and cast(snapshot_as_of_date as date) <= cast(? as date)
        order by cast(snapshot_as_of_date as date)
        """,
        [start.isoformat(), end.isoformat()],
    ).fetchall()
    buckets: dict[str, list[ExposurePoint]] = {}
    for raw_date, raw_evidence in rows:
        date_key = str(raw_date)[:10]
        evidence = _json_object(raw_evidence)
        exposure = _first_float(
            _nested(evidence, ("market_gate", "exposure")),
            evidence.get("market_gate_exposure"),
            evidence.get("exposure"),
        )
        if exposure is None:
            continue
        state = _text(
            _nested(evidence, ("market_gate", "state"))
            or evidence.get("market_state")
            or evidence.get("state")
        ) or "UNKNOWN"
        buckets.setdefault(date_key, []).append(
            ExposurePoint(
                exposure=_clamp_exposure(exposure),
                state=state,
                source=f"persisted:{TABLE_CANDIDATE_HISTORY}",
            ),
        )
    points: dict[str, ExposurePoint] = {}
    for date_key, candidates in buckets.items():
        exposures = {round(point.exposure, 10) for point in candidates}
        states = {point.state for point in candidates}
        if len(exposures) == 1 and len(states) == 1:
            points[date_key] = candidates[0]
    return points


def _load_generic_persisted_points(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    table: str,
    start: date,
    end: date,
) -> dict[str, ExposurePoint]:
    if table not in tables:
        return {}
    columns = _columns(conn, table)
    date_col = _first_present(columns, ("trade_date", "date", "snapshot_as_of_date", "as_of_date"))
    exposure_col = _first_present(columns, ("exposure", "market_gate_exposure", "value"))
    state_col = _first_present(columns, ("state", "market_state"))
    if not date_col or not exposure_col:
        return {}
    state_select = state_col if state_col else "'UNKNOWN'"
    rows = conn.execute(
        f"""
        select {date_col}, {exposure_col}, {state_select}
        from {table}
        where cast({date_col} as date) >= cast(? as date)
          and cast({date_col} as date) <= cast(? as date)
          and {exposure_col} is not null
        order by cast({date_col} as date)
        """,
        [start.isoformat(), end.isoformat()],
    ).fetchall()
    points: dict[str, ExposurePoint] = {}
    for raw_date, raw_exposure, raw_state in rows:
        exposure = _first_float(raw_exposure)
        if exposure is None:
            continue
        points.setdefault(
            str(raw_date)[:10],
            ExposurePoint(
                exposure=_clamp_exposure(exposure),
                state=_text(raw_state) or "UNKNOWN",
                source=f"persisted:{table}",
            ),
        )
    return points


def replay_market_gate_payloads(
    conn: duckdb.DuckDBPyConnection,
    start: str | date,
    end: str | date,
) -> dict[str, dict[str, object]]:
    """Full ``evaluate_market_gate`` payloads per replayable date (pure replay).

    Uses exactly the same inputs and evaluation as the replay leg of
    :func:`load_gate_exposure_by_date` and never reads the persisted exposure
    tables, so callers can persist realtime gate labels or cross-check stored
    labels against what the official backtest would replay for those dates.
    """
    start_date = _parse_date(start)
    end_date = _parse_date(end)
    if end_date < start_date:
        raise ValueError("end must be on or after start")
    return _replay_gate_payloads(conn, tables=_table_names(conn), start=start_date, end=end_date)


def _replay_gate_payloads(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    start: date,
    end: date,
) -> dict[str, dict[str, object]]:
    observations = _load_broad_index_observations(conn, tables=tables, end=end)
    if not observations:
        return {}
    supplements = _load_gate_supplements(conn, tables=tables, start=start, end=end)
    history: list[BroadIndexObservation] = []
    payloads: dict[str, dict[str, object]] = {}
    for observation in observations:
        history.append(observation)
        if observation.trade_date < start or observation.trade_date > end:
            continue
        payloads[observation.trade_date.isoformat()] = evaluate_market_gate(
            history,
            supplement=supplements.get(observation.trade_date.isoformat()),
        )
    return payloads


def _replay_points(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    start: date,
    end: date,
) -> dict[str, ExposurePoint]:
    points: dict[str, ExposurePoint] = {}
    for date_key, gate in _replay_gate_payloads(conn, tables=tables, start=start, end=end).items():
        points[date_key] = ExposurePoint(
            exposure=_clamp_exposure(_first_float(gate.get("exposure")) or 0.0),
            state=_text(gate.get("state")) or "UNKNOWN",
            source="replayed",
        )
    return points


def _load_broad_index_observations(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    end: date,
) -> list[BroadIndexObservation]:
    by_date: dict[str, BroadIndexObservation] = {}
    for table in (TABLE_BENCHMARK_SNAPSHOT, TABLE_BENCHMARK_DAILY):
        if table not in tables:
            continue
        columns = _columns(conn, table)
        date_col = _first_present(columns, ("trade_date", "date"))
        value_col = _first_present(columns, ("value_numeric", "value", "close"))
        if not date_col or not value_col or "series_id" not in columns:
            continue
        quality_select = "quality_flag" if "quality_flag" in columns else "'ok'"
        rows = conn.execute(
            f"""
            select {date_col}, {value_col}, {quality_select}
            from {table}
            where series_id = ?
              and {value_col} is not null
              and cast({date_col} as date) <= cast(? as date)
            order by cast({date_col} as date)
            """,
            [BENCHMARK_SERIES_ID, end.isoformat()],
        ).fetchall()
        for raw_date, raw_value, raw_quality in rows:
            date_key = str(raw_date)[:10]
            close = _first_float(raw_value)
            if close is None:
                continue
            by_date[date_key] = BroadIndexObservation(
                trade_date=date.fromisoformat(date_key),
                close=close,
                quality_flag=_text(raw_quality) or "ok",
            )
    return [by_date[key] for key in sorted(by_date)]


def _load_gate_supplements(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    start: date,
    end: date,
) -> dict[str, MarketGateSupplement]:
    if TABLE_GATE_SUPPLEMENT not in tables:
        return {}
    columns = _columns(conn, TABLE_GATE_SUPPLEMENT)
    if not {"trade_date", "breadth_5d", "limit_up_quality_ok"}.issubset(columns):
        return {}
    rows = conn.execute(
        f"""
        select trade_date, breadth_5d, limit_up_quality_ok
        from {TABLE_GATE_SUPPLEMENT}
        where cast(trade_date as date) >= cast(? as date)
          and cast(trade_date as date) <= cast(? as date)
        """,
        [start.isoformat(), end.isoformat()],
    ).fetchall()
    supplements: dict[str, MarketGateSupplement] = {}
    for raw_date, raw_breadth, raw_limit_ok in rows:
        date_key = str(raw_date)[:10]
        supplements[date_key] = MarketGateSupplement(
            trade_date=date.fromisoformat(date_key),
            breadth_5d=_first_float(raw_breadth),
            limit_up_quality_ok=bool(raw_limit_ok) if raw_limit_ok is not None else None,
        )
    return supplements


def _table_names(conn: duckdb.DuckDBPyConnection) -> set[str]:
    return {str(row[0]) for row in conn.execute("show tables").fetchall()}


def _columns(conn: duckdb.DuckDBPyConnection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"pragma table_info('{table}')").fetchall()}


def _parse_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _date_range(start: date, end: date) -> list[date]:
    days = (end - start).days
    return [start + timedelta(days=offset) for offset in range(days + 1)]


def _json_object(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _nested(data: MappingLike, keys: tuple[str, ...]) -> object:
    current: object = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _first_present(columns: set[str], names: tuple[str, ...]) -> str:
    for name in names:
        if name in columns:
            return name
    return ""


def _first_float(*values: object) -> float | None:
    for value in values:
        if value is None:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if number == number and number not in {float("inf"), float("-inf")}:
            return number
    return None


def _clamp_exposure(value: float) -> float:
    return min(max(value, 0.0), 1.0)


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


MappingLike = dict[str, Any]
