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
           2.0, 11.0, 9.0, 1000.0, 10000.0, 'Trading', 'sv_d', 'vv_choice_stock_20260604_0123456789ab'),
          (?, '600000.SH', 10.0, 10.4, 9.9, 10.2, 1.2, 2.0,
           3.0, 11.2, 9.2, 1200.0, 12000.0, 'Trading', 'sv_d', 'vv_choice_stock_20260605_0123456789ab')
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


def test_stock_candidate_loader_normalizes_daily_amount_by_vendor_generation(tmp_path, caplog):
    """amount 两代 vendor 单位口径:tushare 代际=千元(×1000 归一化为元),choice_native=元,NULL 无法定标输出 NULL。"""
    db_path = _seeded_db(tmp_path)
    writer = duckdb.connect(str(db_path), read_only=False)
    try:
        for stock_code, amount, vendor in (
            ("600100.SH", 300_000.0, "vv_choice_tushare_stock_20251231_001"),
            ("600200.SH", 500_000_000.0, None),
            ("600300.SH", None, None),
        ):
            writer.execute(
                "insert into choice_stock_universe values (?, ?, 'N', 'sv_u', 'vv_u')",
                [_AS_OF_DATE, stock_code],
            )
            writer.execute(
                "insert into choice_stock_sector_membership values (?, ?, '801780', '银行', 'sv_m', 'vv_m')",
                [_AS_OF_DATE, stock_code],
            )
            writer.execute(
                """
                insert into choice_stock_daily_observation values
                  (?, ?, 10.0, 10.4, 9.9, 10.2, 1.2, 2.0, 3.0, 11.2, 9.2, 1200.0, ?, 'Trading', 'sv_d', ?)
                """,
                [_AS_OF_DATE, stock_code, amount, vendor],
            )
            writer.execute(
                "insert into choice_stock_limit_quality values (?, ?, '0', 0, 'sv_l', 'vv_l')",
                [_AS_OF_DATE, stock_code],
            )
    finally:
        writer.close()

    with caplog.at_level("WARNING", logger="backend.app.services.market_data_livermore_service"):
        snapshots, _, _, _ = _load_stock_candidate_snapshots(
            duckdb_path=str(db_path),
            as_of_date=_AS_OF_DATE,
            sector_rank_payload={"items": [{"sector_code": "801780", "sector_name": "银行", "rank": 1}]},
        )

    by_code = {snapshot.stock_code: snapshot for snapshot in snapshots}
    # 种子行 vendor(vv_choice_stock_*)属 choice_native 代际:单位=元,原值透传。
    assert by_code["600000.SH"].daily_amount == 12000.0
    # tushare 代际:单位=千元,读取时 ×1000 归一化为元。
    assert by_code["600100.SH"].daily_amount == 300_000_000.0
    # vendor_version 为 NULL:无法定标 → daily_amount 输出 NULL。
    assert by_code["600200.SH"].daily_amount is None
    # amount 与 vendor_version 均为 NULL:同样无法定标,但不属于"amount 非空、
    # 无法定标"的告警计数范畴(不能定标的原因不是缺单位信息,而是压根没有值)。
    assert by_code["600300.SH"].daily_amount is None
    # 告警计数须仅统计 amount 非空且 vendor_version 为 NULL 的行(600200.SH 一行),
    # 不得把 600300.SH(amount 本身为空)计入,避免夸大计数。
    warning_messages = [
        record.getMessage() for record in caplog.records if record.levelname == "WARNING"
    ]
    assert any("null vendor_version" in message for message in warning_messages)
    assert any(
        "1 rows with non-null amount but null vendor_version" in message
        for message in warning_messages
    )


def test_stock_candidate_loader_fails_closed_without_vendor_version_column(tmp_path, caplog):
    """观察表缺 vendor_version 列:无法定标,daily_amount fail-closed 输出 NULL,
    主查询不得 Binder Error(快照与其余字段照常返回),并有告警说明。"""
    db_path = _seeded_db(tmp_path)
    writer = duckdb.connect(str(db_path), read_only=False)
    try:
        writer.execute("alter table choice_stock_daily_observation drop column vendor_version")
    finally:
        writer.close()

    with caplog.at_level("WARNING", logger="backend.app.services.market_data_livermore_service"):
        snapshots, _, _, _ = _load_stock_candidate_snapshots(
            duckdb_path=str(db_path),
            as_of_date=_AS_OF_DATE,
            sector_rank_payload={"items": [{"sector_code": "801780", "sector_name": "银行", "rank": 1}]},
        )

    assert [snapshot.stock_code for snapshot in snapshots] == ["600000.SH"]
    assert snapshots[0].daily_amount is None
    assert snapshots[0].close_value == 10.2
    assert any(
        "unit basis unavailable" in record.getMessage()
        for record in caplog.records
        if record.levelname == "WARNING"
    )


def test_risk_exit_loader_normalizes_volume_history_by_vendor_generation(tmp_path):
    """风险退出加载器 volume 历史(20 日均量输入)统一为股:tushare 代际=手(×100),
    choice_native=股,NULL vendor 无法定标 → 该行按现有语义整行剔除。"""
    db_path = _seeded_db(tmp_path)
    writer = duckdb.connect(str(db_path), read_only=False)
    try:
        writer.executemany(
            """
            insert into choice_stock_daily_observation values
              (?, '600000.SH', 9.6, 9.9, 9.5, ?, 1.0, 0.3, 1.8, 10.8, 8.8, ?, 9000.0, 'Trading', 'sv_d', ?)
            """,
            [
                # tushare 代际:500 手 → 50_000 股。
                ("2026-06-02", 9.7, 500.0, "vv_choice_tushare_stock_20251231_001"),
                # NULL vendor:volume 无法定标 → 加载器剔除该行(close 亦不入序列)。
                ("2026-06-03", 9.8, 800.0, None),
            ],
        )
    finally:
        writer.close()

    snapshots, _, _, _ = _load_risk_exit_snapshots(
        duckdb_path=str(db_path),
        as_of_date=_AS_OF_DATE,
    )

    assert [snapshot.stock_code for snapshot in snapshots] == ["600000.SH"]
    snapshot = snapshots[0]
    # 2026-06-03(NULL vendor)整行剔除;其余按日期升序。
    assert snapshot.close_history == [9.7, 10.0, 10.2]
    assert snapshot.volume_history == [50_000.0, 1000.0, 1200.0]


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
