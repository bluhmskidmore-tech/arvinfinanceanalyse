"""Wave-2 Livermore loaders reuse a shared read-only connection.

Extends the wave-1 demonstration wiring to the remaining stock loaders: when
the orchestrator passes one connection, each loader queries on it and does NOT
close it, and the results are identical to the self-managed (own connection)
path.
"""

from __future__ import annotations

import duckdb

from backend.app.services.market_data_livermore_service import (
    _load_factor_screen_rows,
    _load_risk_exit_snapshots,
    _load_sector_rank_inputs,
    _load_stock_candidate_snapshots,
    _load_trading_stock_snapshot_inputs,
    _risk_exit_input_block_reason,
    _shared_read_only_connection,
)

_AS_OF_DATE = "2026-06-05"


def _seed_stock_tables(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        create table choice_stock_universe (
          as_of_date varchar, stock_code varchar, stock_name varchar,
          source_version varchar, vendor_version varchar
        )
        """
    )
    conn.execute(
        """
        create table choice_stock_sector_membership (
          as_of_date varchar, stock_code varchar, sw2021code varchar, sw2021 varchar,
          source_version varchar, vendor_version varchar
        )
        """
    )
    conn.execute(
        """
        create table choice_stock_daily_observation (
          trade_date varchar, stock_code varchar, open_value double, high_value double,
          low_value double, close_value double, turn double, pctchange double,
          amplitude double, highlimit double, lowlimit double, volume double,
          amount double, tradestatus varchar, source_version varchar, vendor_version varchar
        )
        """
    )
    conn.execute(
        """
        create table choice_stock_limit_quality (
          as_of_date varchar, stock_code varchar, issurgedlimit varchar, hlimitedays integer,
          source_version varchar, vendor_version varchar
        )
        """
    )
    conn.execute(
        "insert into choice_stock_universe values (?, '600000.SH', '浦发银行', 'sv_u', 'vv_u')",
        [_AS_OF_DATE],
    )
    conn.execute(
        "insert into choice_stock_sector_membership values (?, '600000.SH', '801780', '银行', 'sv_m', 'vv_m')",
        [_AS_OF_DATE],
    )
    conn.execute(
        """
        insert into choice_stock_daily_observation values
          ('2026-06-04', '600000.SH', 9.8, 10.1, 9.7, 10.0, 1.1, 0.5,
           2.0, 11.0, 9.0, 1000.0, 10000.0, 'Trading', 'sv_d', 'vv_d'),
          (?, '600000.SH', 10.0, 10.4, 9.9, 10.2, 1.2, 2.0,
           3.0, 11.2, 9.2, 1200.0, 12000.0, 'Trading', 'sv_d', 'vv_d')
        """,
        [_AS_OF_DATE],
    )
    conn.execute(
        "insert into choice_stock_limit_quality values (?, '600000.SH', '0', 0, 'sv_l', 'vv_l')",
        [_AS_OF_DATE],
    )
    conn.execute(
        """
        create table livermore_position_snapshot (
          as_of_date varchar, stock_code varchar, stock_name varchar, entry_cost double,
          bars_since_entry integer, position_status varchar, source_version varchar, vendor_version varchar
        )
        """
    )
    conn.execute(
        "insert into livermore_position_snapshot values (?, '600000.SH', '浦发银行', 9.5, 3, 'ACTIVE', 'sv_p', 'vv_p')",
        [_AS_OF_DATE],
    )


def _seeded_db(tmp_path):
    db_path = tmp_path / "moss.duckdb"
    writer = duckdb.connect(str(db_path), read_only=False)
    try:
        _seed_stock_tables(writer)
    finally:
        writer.close()
    return db_path


def test_sector_rank_loader_reuses_shared_connection(tmp_path):
    db_path = _seeded_db(tmp_path)

    self_managed = _load_sector_rank_inputs(duckdb_path=str(db_path), as_of_date=_AS_OF_DATE)
    with _shared_read_only_connection(str(db_path)) as shared_conn:
        assert shared_conn is not None
        borrowed = _load_sector_rank_inputs(
            duckdb_path=str(db_path),
            as_of_date=_AS_OF_DATE,
            conn=shared_conn,
        )
        # Loader must not close a borrowed connection.
        assert shared_conn.execute("select 1").fetchone()[0] == 1

    assert borrowed == self_managed
    rows, tables_used, _, _ = borrowed
    assert [row.stock_code for row in rows] == ["600000.SH"]
    assert "choice_stock_sector_membership" in tables_used


def test_stock_candidate_loader_reuses_shared_connection(tmp_path):
    db_path = _seeded_db(tmp_path)
    sector_rank_payload = {"items": [{"sector_code": "801780", "sector_name": "银行", "rank": 1}]}

    self_managed = _load_stock_candidate_snapshots(
        duckdb_path=str(db_path),
        as_of_date=_AS_OF_DATE,
        sector_rank_payload=sector_rank_payload,
    )
    with _shared_read_only_connection(str(db_path)) as shared_conn:
        assert shared_conn is not None
        borrowed = _load_stock_candidate_snapshots(
            duckdb_path=str(db_path),
            as_of_date=_AS_OF_DATE,
            sector_rank_payload=sector_rank_payload,
            conn=shared_conn,
        )
        assert shared_conn.execute("select 1").fetchone()[0] == 1

    assert borrowed == self_managed
    snapshots, tables_used, _, _ = borrowed
    assert [snapshot.stock_code for snapshot in snapshots] == ["600000.SH"]
    assert "choice_stock_limit_quality" in tables_used


def test_trading_snapshot_inputs_loader_reuses_shared_connection(tmp_path):
    db_path = _seeded_db(tmp_path)

    self_managed = _load_trading_stock_snapshot_inputs(
        duckdb_path=str(db_path),
        as_of_date=_AS_OF_DATE,
        include_concepts=True,
        include_limit_quality=True,
    )
    with _shared_read_only_connection(str(db_path)) as shared_conn:
        assert shared_conn is not None
        borrowed = _load_trading_stock_snapshot_inputs(
            duckdb_path=str(db_path),
            as_of_date=_AS_OF_DATE,
            include_concepts=True,
            include_limit_quality=True,
            conn=shared_conn,
        )
        assert shared_conn.execute("select 1").fetchone()[0] == 1

    assert borrowed == self_managed
    assert [row.stock_code for row in borrowed.current_rows] == ["600000.SH"]


def test_factor_screen_loader_reuses_shared_connection_when_table_missing(tmp_path):
    db_path = _seeded_db(tmp_path)

    self_managed = _load_factor_screen_rows(duckdb_path=str(db_path), as_of_date=_AS_OF_DATE)
    with _shared_read_only_connection(str(db_path)) as shared_conn:
        assert shared_conn is not None
        borrowed = _load_factor_screen_rows(
            duckdb_path=str(db_path),
            as_of_date=_AS_OF_DATE,
            conn=shared_conn,
        )
        assert shared_conn.execute("select 1").fetchone()[0] == 1

    assert borrowed == self_managed
    assert borrowed.unavailable_reason == "choice_stock_factor_snapshot table is missing."


def test_risk_exit_loader_and_block_reason_reuse_shared_connection(tmp_path):
    db_path = _seeded_db(tmp_path)

    self_managed = _load_risk_exit_snapshots(duckdb_path=str(db_path), as_of_date=_AS_OF_DATE)
    self_managed_reason = _risk_exit_input_block_reason(duckdb_path=str(db_path), as_of_date=_AS_OF_DATE)
    with _shared_read_only_connection(str(db_path)) as shared_conn:
        assert shared_conn is not None
        borrowed = _load_risk_exit_snapshots(
            duckdb_path=str(db_path),
            as_of_date=_AS_OF_DATE,
            conn=shared_conn,
        )
        borrowed_reason = _risk_exit_input_block_reason(
            duckdb_path=str(db_path),
            as_of_date=_AS_OF_DATE,
            conn=shared_conn,
        )
        assert shared_conn.execute("select 1").fetchone()[0] == 1

    assert borrowed == self_managed
    assert borrowed_reason == self_managed_reason == ""
    snapshots, tables_used, _, _ = borrowed
    assert [snapshot.stock_code for snapshot in snapshots] == ["600000.SH"]
    assert "livermore_position_snapshot" in tables_used


def test_loaders_self_manage_when_shared_connection_unavailable(tmp_path):
    missing = tmp_path / "absent.duckdb"
    with _shared_read_only_connection(str(missing)) as shared_conn:
        assert shared_conn is None
        rows, tables_used, sources, vendors = _load_sector_rank_inputs(
            duckdb_path=str(missing),
            as_of_date=_AS_OF_DATE,
            conn=shared_conn,
        )
    assert (rows, tables_used, sources, vendors) == ([], [], [], [])
