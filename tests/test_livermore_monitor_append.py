from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

from backend.app.tasks.livermore_monitor_append import append_daily_monitor


def _ensure_monitor_test_schema(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        create table if not exists livermore_candidate_history (
          snapshot_as_of_date varchar,
          stock_code varchar,
          candidate_rank integer,
          selection_close double,
          data_status varchar,
          formula_version varchar,
          source_version varchar,
          vendor_version varchar,
          rule_version varchar,
          run_id varchar,
          signal_kind varchar,
          return_5d double,
          market_state varchar,
          signal_evidence_json varchar
        )
        """
    )


def _insert_rows(
    conn: duckdb.DuckDBPyConnection,
    rows: list[tuple[str, str, str, float | None, str | None, str | None, str | None]],
) -> None:
    _ensure_monitor_test_schema(conn)
    conn.executemany(
        """
        insert into livermore_candidate_history (
          snapshot_as_of_date,
          stock_code,
          candidate_rank,
          selection_close,
          data_status,
          formula_version,
          source_version,
          vendor_version,
          rule_version,
          run_id,
          signal_kind,
          return_5d,
          market_state,
          signal_evidence_json
        ) values (?, ?, 1, 10.0, 'complete', ?, 'sv_test', 'vv_test', 'rv_test', 'run_test', ?, ?, ?, ?)
        """,
        [(row[0], row[1], row[4], row[2], row[3], row[5], row[6]) for row in rows],
    )


def test_append_daily_monitor_returns_expected_fields(tmp_path: Path) -> None:
    duckdb_path = tmp_path / "monitor.duckdb"
    monitor_path = tmp_path / "livermore_monitor.jsonl"
    conn = duckdb.connect(str(duckdb_path))
    try:
        _insert_rows(
            conn,
            [
                ("2026-05-13", "000001", "stock_candidate", 0.05, "fv_v7", "HOT", None),
                ("2026-05-13", "000002", "stock_candidate", -0.02, "fv_v7", "HOT", None),
                ("2026-05-13", "000003", "mean_reversion", None, "fv_mr", "WARM", '{"market_state":"WARM"}'),
                ("2026-05-14", "000004", "stock_candidate", 0.03, "fv_v7", "HOT", None),
                ("2026-05-15", "000005", "stock_candidate", 0.01, "fv_v8", "HOT", None),
                ("2026-05-15", "000006", "stock_candidate", 0.02, "fv_v8", "HOT", None),
                ("2026-05-15", "000007", "mean_reversion", 0.04, "fv_mr", "HOT", None),
            ],
        )
    finally:
        conn.close()

    result = append_daily_monitor(
        duckdb_path=str(duckdb_path),
        as_of_date="2026-05-15",
        monitor_jsonl_path=str(monitor_path),
    )

    assert isinstance(result, dict)
    assert result["as_of_date"] == "2026-05-15"
    assert isinstance(result["stock_candidate_count"], int)
    assert result["stock_candidate_count"] == 2
    assert isinstance(result["mean_reversion_count"], int)
    assert result["mean_reversion_count"] == 1
    assert isinstance(result["rolling_win_5d_20d"], float)
    assert isinstance(result["rolling_avg_5d_20d"], float)
    assert result["formula_version"] == "fv_v8"
    assert result["market_state"] == "HOT"
    assert isinstance(result["timestamp"], str)
    assert "2026-05-15" in result["timestamp"]


def test_append_daily_monitor_appends_without_overwrite(tmp_path: Path) -> None:
    duckdb_path = tmp_path / "monitor.duckdb"
    monitor_path = tmp_path / "livermore_monitor.jsonl"
    conn = duckdb.connect(str(duckdb_path))
    try:
        _insert_rows(
            conn,
            [
                ("2026-05-14", "000001", "stock_candidate", 0.01, "fv_v7", "HOT", None),
                ("2026-05-15", "000002", "stock_candidate", 0.02, "fv_v7", "HOT", None),
            ],
        )
    finally:
        conn.close()

    append_daily_monitor(
        duckdb_path=str(duckdb_path),
        as_of_date="2026-05-14",
        monitor_jsonl_path=str(monitor_path),
    )
    append_daily_monitor(
        duckdb_path=str(duckdb_path),
        as_of_date="2026-05-15",
        monitor_jsonl_path=str(monitor_path),
    )

    lines = monitor_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    second = json.loads(lines[1])
    assert first["as_of_date"] == "2026-05-14"
    assert second["as_of_date"] == "2026-05-15"


def test_append_daily_monitor_empty_table_returns_zero_counts(tmp_path: Path) -> None:
    duckdb_path = tmp_path / "empty.duckdb"
    monitor_path = tmp_path / "livermore_monitor.jsonl"
    conn = duckdb.connect(str(duckdb_path))
    try:
        _ensure_monitor_test_schema(conn)
    finally:
        conn.close()

    result = append_daily_monitor(
        duckdb_path=str(duckdb_path),
        as_of_date="2026-05-15",
        monitor_jsonl_path=str(monitor_path),
    )

    assert result["as_of_date"] == "2026-05-15"
    assert result["stock_candidate_count"] == 0
    assert result["mean_reversion_count"] == 0
    assert result["rolling_win_5d_20d"] is None
    assert result["rolling_avg_5d_20d"] is None


def test_append_daily_monitor_missing_duckdb_returns_empty(tmp_path: Path) -> None:
    monitor_path = tmp_path / "livermore_monitor.jsonl"
    result = append_daily_monitor(
        duckdb_path=str(tmp_path / "missing.duckdb"),
        as_of_date="2026-05-15",
        monitor_jsonl_path=str(monitor_path),
    )
    assert result == {}
    assert not monitor_path.exists()
