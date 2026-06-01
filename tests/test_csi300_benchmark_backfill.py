from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb
import pytest

from tests.helpers import load_module


def _create_fact_choice_macro_daily(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        create table fact_choice_macro_daily (
          series_id varchar,
          series_name varchar,
          trade_date varchar,
          value_numeric double,
          frequency varchar,
          unit varchar,
          source_version varchar,
          vendor_version varchar,
          rule_version varchar,
          quality_flag varchar,
          run_id varchar
        )
        """
    )


def _insert_fact_row(
    conn: duckdb.DuckDBPyConnection,
    *,
    series_id: str = "CA.CSI300",
    trade_date: str,
    value_numeric: float,
    source_version: str = "sv_source",
    vendor_version: str = "vv_source",
    run_id: str = "run-source",
) -> None:
    conn.execute(
        """
        insert into fact_choice_macro_daily values
          (?, 'CSI300 Close', ?, ?, 'daily', 'index', ?, ?, 'rv_source', 'ok', ?)
        """,
        [series_id, trade_date, value_numeric, source_version, vendor_version, run_id],
    )


def _open_macro_db(path: Path) -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(str(path), read_only=False)
    _create_fact_choice_macro_daily(conn)
    return conn


def test_csi300_backfill_inserts_only_missing_rows_and_preserves_lineage(tmp_path: Path) -> None:
    module = load_module(
        "scripts.backfill_csi300_benchmark_from_backup",
        "scripts/backfill_csi300_benchmark_from_backup.py",
    )
    target_path = tmp_path / "current.duckdb"
    source_path = tmp_path / "backup.duckdb"

    target = _open_macro_db(target_path)
    try:
        _insert_fact_row(
            target,
            trade_date="2026-01-02",
            value_numeric=100.0,
            source_version="sv_current",
            vendor_version="vv_current",
            run_id="run-current",
        )
    finally:
        target.close()

    source = _open_macro_db(source_path)
    try:
        _insert_fact_row(source, trade_date="2026-01-01", value_numeric=99.0)
        _insert_fact_row(source, trade_date="2026-01-02", value_numeric=100.0)
        _insert_fact_row(source, series_id="CA.CSI300_PE", trade_date="2026-01-01", value_numeric=12.3)
    finally:
        source.close()

    result = module.backfill_csi300_benchmark_from_backup(
        duckdb_path=target_path,
        backup_duckdb_path=source_path,
        start_date="2026-01-01",
        end_date="2026-01-03",
        governance_dir=tmp_path / "governance",
    )

    assert result["status"] == "completed"
    assert result["inserted_count"] == 1
    assert result["inserted_by_series"] == {"CA.CSI300": 1}
    assert result["inserted_min_date"] == "2026-01-01"
    assert result["inserted_max_date"] == "2026-01-01"

    conn = duckdb.connect(str(target_path), read_only=True)
    try:
        rows = conn.execute(
            """
            select series_id, trade_date, value_numeric, source_version, vendor_version, run_id
            from fact_choice_macro_daily
            order by series_id, trade_date
            """
        ).fetchall()
    finally:
        conn.close()

    assert rows == [
        ("CA.CSI300", "2026-01-01", pytest.approx(99.0), "sv_source", "vv_source", "run-source"),
        ("CA.CSI300", "2026-01-02", pytest.approx(100.0), "sv_current", "vv_current", "run-current"),
    ]


def test_csi300_backfill_dry_run_does_not_write(tmp_path: Path) -> None:
    module = load_module(
        "scripts.backfill_csi300_benchmark_from_backup",
        "scripts/backfill_csi300_benchmark_from_backup.py",
    )
    target_path = tmp_path / "current.duckdb"
    source_path = tmp_path / "backup.duckdb"

    _open_macro_db(target_path).close()
    source = _open_macro_db(source_path)
    try:
        _insert_fact_row(source, trade_date="2026-01-01", value_numeric=99.0)
    finally:
        source.close()

    result = module.backfill_csi300_benchmark_from_backup(
        duckdb_path=target_path,
        backup_duckdb_path=source_path,
        start_date="2026-01-01",
        end_date="2026-01-01",
        dry_run=True,
    )

    assert result["status"] == "dry_run"
    assert result["inserted_count"] == 0
    assert result["would_insert_count"] == 1

    conn = duckdb.connect(str(target_path), read_only=True)
    try:
        assert conn.execute("select count(*) from fact_choice_macro_daily").fetchone()[0] == 0
    finally:
        conn.close()


def test_csi300_backfill_rejects_overlapping_value_conflicts(tmp_path: Path) -> None:
    module = load_module(
        "scripts.backfill_csi300_benchmark_from_backup",
        "scripts/backfill_csi300_benchmark_from_backup.py",
    )
    target_path = tmp_path / "current.duckdb"
    source_path = tmp_path / "backup.duckdb"

    target = _open_macro_db(target_path)
    try:
        _insert_fact_row(target, trade_date="2026-01-02", value_numeric=100.0)
    finally:
        target.close()
    source = _open_macro_db(source_path)
    try:
        _insert_fact_row(source, trade_date="2026-01-02", value_numeric=101.0)
    finally:
        source.close()

    with pytest.raises(ValueError, match="conflicting existing rows"):
        module.backfill_csi300_benchmark_from_backup(
            duckdb_path=target_path,
            backup_duckdb_path=source_path,
            start_date="2026-01-01",
            end_date="2026-01-03",
        )

    conn = duckdb.connect(str(target_path), read_only=True)
    try:
        assert conn.execute("select count(*) from fact_choice_macro_daily").fetchone()[0] == 1
    finally:
        conn.close()


def test_csi300_backfill_main_emits_json(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    module = load_module(
        "scripts.backfill_csi300_benchmark_from_backup",
        "scripts/backfill_csi300_benchmark_from_backup.py",
    )

    monkeypatch.setattr(
        module,
        "backfill_csi300_benchmark_from_backup",
        lambda **_kwargs: {"status": "completed", "inserted_count": 0},
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "backfill_csi300_benchmark_from_backup.py",
            "--duckdb-path",
            "current.duckdb",
            "--backup-duckdb-path",
            "backup.duckdb",
            "--start-date",
            "2026-01-01",
            "--end-date",
            "2026-01-02",
        ],
    )

    assert module.main() == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"status": "completed", "inserted_count": 0}
    assert captured.err == ""
