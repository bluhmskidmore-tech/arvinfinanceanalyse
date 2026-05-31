from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb
import pytest

from backend.app.tasks.choice_stock_materialize import choice_stock_history_start_date, ensure_choice_stock_schema
from tests.helpers import load_module


def _open_choice_db(path: Path) -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(str(path), read_only=False)
    ensure_choice_stock_schema(conn)
    return conn


def _seed_complete_choice_date(
    conn: duckdb.DuckDBPyConnection,
    *,
    as_of_date: str,
    run_id: str,
    source_version: str = "sv_source",
    vendor_version: str = "vv_source",
) -> None:
    history_start = choice_stock_history_start_date(as_of_date)
    conn.execute(
        """
        insert into choice_stock_materialize_run values
          (?, ?, 'completed', 'catalog.yaml', ?, ?, 'rv_choice_stock_materialization_front_layer_v1', 7, 42, 'start', 'end', '')
        """,
        [run_id, as_of_date, source_version, vendor_version],
    )
    audits = [
        ("stock_universe", "a_share_universe_sector_001004", "completed"),
        ("sector_membership", "sw2021_industry_membership", "completed"),
        ("sector_strength", "daily_return_turnover_amplitude", "completed_tushare_fallback"),
        ("stock_ohlcv", "daily_ohlcv_amount", "completed_tushare_fallback"),
        ("stock_status", "daily_trade_status", "completed_tushare_fallback"),
        ("limit_up_quality", "daily_limit_flags", "completed_tushare_fallback"),
        ("limit_up_quality", "point_in_time_limit_streaks", "completed"),
    ]
    conn.executemany(
        """
        insert into choice_stock_request_audit values
          (?, ?, ?, ?, 'csd', 'indicator', '{}', '{}', ?, 1, 0, '', ?, ?, 'rv_choice_stock_materialization_front_layer_v1')
        """,
        [
            (run_id, as_of_date, family, field_key, status, source_version, vendor_version)
            for family, field_key, status in audits
        ],
    )
    conn.execute(
        "insert into choice_stock_universe values (?, '000001.SZ', '平安银行', 'a_share_universe_sector_001004', ?, ?, 'rv', ?)",
        [as_of_date, source_version, vendor_version, run_id],
    )
    conn.execute(
        "insert into choice_stock_sector_membership values (?, '000001.SZ', '银行', '801780', 'sw2021_industry_membership', ?, ?, 'rv', ?)",
        [as_of_date, source_version, vendor_version, run_id],
    )
    conn.execute(
        "insert into choice_stock_limit_quality values (?, '000001.SZ', '0', '0', 0, 0, 'point_in_time_limit_streaks', ?, ?, 'rv', ?)",
        [as_of_date, source_version, vendor_version, run_id],
    )
    daily_field_keys = json.dumps(
        [
            "daily_limit_flags",
            "daily_ohlcv_amount",
            "daily_return_turnover_amplitude",
            "daily_trade_status",
        ],
        separators=(",", ":"),
    )
    conn.executemany(
        """
        insert into choice_stock_daily_observation values
          (?, '000001.SZ', 10, 11, 9, 10.5, 1000, 2000, 1.2, 0.8, 2.0, '交易', '涨停', '跌停', ?, ?, ?, 'rv', ?)
        """,
        [
            (history_start, daily_field_keys, source_version, vendor_version, run_id),
            (as_of_date, daily_field_keys, source_version, vendor_version, run_id),
        ],
    )


def _seed_target_old_rows(conn: duckdb.DuckDBPyConnection, *, as_of_date: str) -> None:
    _seed_complete_choice_date(
        conn,
        as_of_date=as_of_date,
        run_id="old-run",
        source_version="sv_old",
        vendor_version="vv_old",
    )
    conn.execute(
        """
        insert into choice_stock_daily_observation values
          ('2026-12-31', '000001.SZ', 1, 1, 1, 1, 1, 1, 1, 1, 1, '交易', '涨停', '跌停', '["daily_ohlcv_amount"]', 'sv_keep', 'vv_keep', 'rv', 'keep-run')
        """
    )


def test_choice_stock_asof_copy_replaces_target_slice_and_preserves_lineage(tmp_path: Path) -> None:
    module = load_module(
        "scripts.copy_choice_stock_asof_from_duckdb",
        "scripts/copy_choice_stock_asof_from_duckdb.py",
    )
    source_path = tmp_path / "source.duckdb"
    target_path = tmp_path / "target.duckdb"
    as_of_date = "2026-01-10"

    source = _open_choice_db(source_path)
    try:
        _seed_complete_choice_date(source, as_of_date=as_of_date, run_id="source-run")
    finally:
        source.close()
    target = _open_choice_db(target_path)
    try:
        _seed_target_old_rows(target, as_of_date=as_of_date)
    finally:
        target.close()

    result = module.copy_choice_stock_asof_from_duckdb(
        source_duckdb_path=source_path,
        target_duckdb_path=target_path,
        as_of_date=as_of_date,
        governance_dir=tmp_path / "governance",
    )

    assert result["status"] == "completed"
    assert result["inserted_counts"]["choice_stock_materialize_run"] == 1
    assert result["inserted_counts"]["choice_stock_request_audit"] == 7
    assert result["inserted_counts"]["choice_stock_daily_observation"] == 2

    conn = duckdb.connect(str(target_path), read_only=True)
    try:
        run_ids = conn.execute(
            "select distinct run_id from choice_stock_universe where as_of_date = ?",
            [as_of_date],
        ).fetchall()
        assert run_ids == [("source-run",)]
        assert conn.execute(
            "select count(*) from choice_stock_daily_observation where run_id = 'old-run'"
        ).fetchone()[0] == 0
        assert conn.execute(
            "select count(*) from choice_stock_daily_observation where run_id = 'keep-run'"
        ).fetchone()[0] == 1
    finally:
        conn.close()


def test_choice_stock_asof_copy_dry_run_does_not_write(tmp_path: Path) -> None:
    module = load_module(
        "scripts.copy_choice_stock_asof_from_duckdb",
        "scripts/copy_choice_stock_asof_from_duckdb.py",
    )
    source_path = tmp_path / "source.duckdb"
    target_path = tmp_path / "target.duckdb"
    as_of_date = "2026-01-10"
    source = _open_choice_db(source_path)
    try:
        _seed_complete_choice_date(source, as_of_date=as_of_date, run_id="source-run")
    finally:
        source.close()
    target = _open_choice_db(target_path)
    try:
        _seed_target_old_rows(target, as_of_date=as_of_date)
    finally:
        target.close()

    result = module.copy_choice_stock_asof_from_duckdb(
        source_duckdb_path=source_path,
        target_duckdb_path=target_path,
        as_of_date=as_of_date,
        dry_run=True,
    )

    assert result["status"] == "dry_run"
    assert result["inserted_counts"] == {}
    conn = duckdb.connect(str(target_path), read_only=True)
    try:
        assert conn.execute(
            "select distinct run_id from choice_stock_universe where as_of_date = ?",
            [as_of_date],
        ).fetchall() == [("old-run",)]
    finally:
        conn.close()


def test_choice_stock_asof_copy_rejects_incomplete_source(tmp_path: Path) -> None:
    module = load_module(
        "scripts.copy_choice_stock_asof_from_duckdb",
        "scripts/copy_choice_stock_asof_from_duckdb.py",
    )
    source_path = tmp_path / "source.duckdb"
    target_path = tmp_path / "target.duckdb"
    _open_choice_db(source_path).close()
    _open_choice_db(target_path).close()

    with pytest.raises(ValueError, match="not complete"):
        module.copy_choice_stock_asof_from_duckdb(
            source_duckdb_path=source_path,
            target_duckdb_path=target_path,
            as_of_date="2026-01-10",
        )


def test_choice_stock_asof_copy_main_emits_json(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    module = load_module(
        "scripts.copy_choice_stock_asof_from_duckdb",
        "scripts/copy_choice_stock_asof_from_duckdb.py",
    )
    monkeypatch.setattr(
        module,
        "copy_choice_stock_asof_from_duckdb",
        lambda **_kwargs: {"status": "completed", "inserted_counts": {}},
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "copy_choice_stock_asof_from_duckdb.py",
            "--source-duckdb-path",
            "source.duckdb",
            "--target-duckdb-path",
            "target.duckdb",
            "--as-of-date",
            "2026-01-10",
        ],
    )

    assert module.main() == 0
    assert json.loads(capsys.readouterr().out) == {"status": "completed", "inserted_counts": {}}
