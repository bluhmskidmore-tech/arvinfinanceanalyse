from __future__ import annotations

import sys
from pathlib import Path

import duckdb

from tests.helpers import load_module


def _load_pretrade_module():
    return load_module(
        "scripts.export_livermore_pretrade_check",
        "scripts/export_livermore_pretrade_check.py",
    )


def _create_pretrade_db(path: Path) -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(str(path), read_only=False)
    conn.execute(
        """
        create table livermore_candidate_history (
          snapshot_as_of_date varchar,
          stock_code varchar,
          stock_name varchar,
          candidate_rank integer,
          sector_name varchar,
          selection_close double,
          market_state varchar,
          data_status varchar,
          closed_up_limit boolean,
          source_version varchar,
          vendor_version varchar,
          run_id varchar,
          signal_kind varchar
        )
        """
    )
    conn.execute(
        """
        create table choice_stock_daily_observation (
          trade_date varchar,
          stock_code varchar,
          close_value double,
          amount double,
          turn double,
          tradestatus varchar,
          highlimit varchar,
          lowlimit varchar,
          pctchange double,
          volume double,
          vendor_version varchar
        )
        """
    )
    conn.execute(
        """
        create table choice_stock_limit_quality (
          as_of_date varchar,
          stock_code varchar,
          issurgedlimit varchar,
          isdeclinelimit varchar,
          hlimitedays integer,
          llimitedays integer,
          field_key varchar
        )
        """
    )
    conn.execute(
        """
        create table choice_stock_factor_snapshot (
          as_of_date varchar,
          stock_code varchar
        )
        """
    )
    return conn


def _seed_candidate(
    conn: duckdb.DuckDBPyConnection,
    *,
    rank: int,
    code: str,
    sector: str = "Tech",
    market_state: str = "HOT",
    data_status: str = "complete",
) -> None:
    conn.execute(
        """
        insert into livermore_candidate_history values
          ('2026-05-27', ?, ?, ?, ?, 10.0, ?, ?, false, 'sv', 'vv', 'run', 'factor_screen')
        """,
        [code, f"Stock {rank}", rank, sector, market_state, data_status],
    )


def _seed_daily(
    conn: duckdb.DuckDBPyConnection,
    *,
    code: str,
    close: float = 10.0,
    amount: float = 1000.0,
    tradestatus: str = "\u4ea4\u6613",
    highlimit: str = "11.0",
    lowlimit: str = "9.0",
    vendor_version: str | None = "vv_choice_stock_test",
) -> None:
    conn.execute(
        """
        insert into choice_stock_daily_observation values
          ('2026-05-27', ?, ?, ?, 1.0, ?, ?, ?, 0.1, 100.0, ?)
        """,
        [code, close, amount, tradestatus, highlimit, lowlimit, vendor_version],
    )


def _seed_limit(
    conn: duckdb.DuckDBPyConnection,
    *,
    code: str,
    up: str = "0",
    down: str = "0",
) -> None:
    conn.execute(
        """
        insert into choice_stock_limit_quality values
          ('2026-05-27', ?, ?, ?, 0, 0, 'daily_limit_flags')
        """,
        [code, up, down],
    )


def _seed_factor(conn: duckdb.DuckDBPyConnection, *codes: str) -> None:
    conn.executemany(
        "insert into choice_stock_factor_snapshot values ('2026-05-27', ?)",
        [(code,) for code in codes],
    )


def test_pretrade_export_writes_top_rows_and_marks_overheat_review(tmp_path: Path) -> None:
    module = _load_pretrade_module()
    db_path = tmp_path / "moss.duckdb"
    conn = _create_pretrade_db(db_path)
    try:
        for rank, code in enumerate(["000001.SZ", "000002.SZ", "000003.SZ"], start=1):
            _seed_candidate(conn, rank=rank, code=code, market_state="OVERHEAT", data_status="pending")
            _seed_daily(conn, code=code)
            _seed_limit(conn, code=code)
        _seed_factor(conn, "000001.SZ", "000002.SZ", "000003.SZ")
    finally:
        conn.close()

    result = module.export_livermore_pretrade_check(
        duckdb_path=db_path,
        output_dir=tmp_path / "out",
        top_n=2,
        today="2026-05-31",
    )

    assert result["status"] == "completed"
    assert result["candidate_count"] == 3
    assert result["decision"]["action"] == "review_only"
    assert "market_state OVERHEAT; use review-only output" in result["decision"]["reasons"]
    assert [row["stock_code"] for row in result["rows"]] == ["000001.SZ", "000002.SZ"]
    assert all(row["row_action"] == "review" for row in result["rows"])
    assert Path(result["output_paths"]["csv"]).exists()
    assert Path(result["output_paths"]["json"]).exists()
    assert Path(result["output_paths"]["summary"]).exists()


def test_pretrade_export_blocks_suspended_and_missing_daily_rows(tmp_path: Path) -> None:
    module = _load_pretrade_module()
    db_path = tmp_path / "moss.duckdb"
    conn = _create_pretrade_db(db_path)
    try:
        _seed_candidate(conn, rank=1, code="000001.SZ")
        _seed_candidate(conn, rank=2, code="000002.SZ")
        _seed_daily(conn, code="000001.SZ", tradestatus="halt")
        _seed_limit(conn, code="000001.SZ")
        _seed_factor(conn, "000001.SZ", "000002.SZ")
    finally:
        conn.close()

    result = module.export_livermore_pretrade_check(
        duckdb_path=db_path,
        output_dir=tmp_path / "out",
        top_n=2,
        today="2026-05-31",
    )

    assert result["decision"]["action"] == "blocked"
    assert {row["stock_code"]: row["row_action"] for row in result["rows"]} == {
        "000001.SZ": "blocked",
        "000002.SZ": "blocked",
    }
    flags_by_code = {
        row["stock_code"]: {flag["kind"] for flag in row["risk_flags"]}
        for row in result["rows"]
    }
    assert "suspended" in flags_by_code["000001.SZ"]
    assert "missing_daily_observation" in flags_by_code["000002.SZ"]
    assert "missing_amount" in flags_by_code["000002.SZ"]


def test_pretrade_export_flags_review_level_liquidity_limit_and_sector_concentration(tmp_path: Path) -> None:
    module = _load_pretrade_module()
    db_path = tmp_path / "moss.duckdb"
    conn = _create_pretrade_db(db_path)
    try:
        for rank, code in enumerate(["000001.SZ", "000002.SZ", "000003.SZ"], start=1):
            _seed_candidate(conn, rank=rank, code=code, sector="Auto")
            _seed_daily(conn, code=code, close=11.0 if rank == 1 else 10.0, amount=500.0)
            _seed_limit(conn, code=code, up="1" if rank == 1 else "0")
        _seed_factor(conn, "000001.SZ", "000002.SZ", "000003.SZ")
    finally:
        conn.close()

    result = module.export_livermore_pretrade_check(
        duckdb_path=db_path,
        output_dir=tmp_path / "out",
        top_n=3,
        min_amount=1000.0,
        max_sector_weight=0.5,
        today="2026-05-31",
    )

    assert result["decision"]["action"] == "review_only"
    assert result["portfolio_flags"] == [
        {
            "kind": "sector_concentration",
            "severity": "review",
            "sector_name": "Auto",
            "weight": 1.0,
            "threshold": 0.5,
        }
    ]
    first_flags = {flag["kind"] for flag in result["rows"][0]["risk_flags"]}
    assert {"limit_up", "low_liquidity"} <= first_flags


def test_pretrade_export_compares_min_amount_in_rmb_for_tushare_rows(tmp_path: Path) -> None:
    module = _load_pretrade_module()
    db_path = tmp_path / "moss.duckdb"
    conn = _create_pretrade_db(db_path)
    try:
        _seed_candidate(conn, rank=1, code="000001.SZ")
        _seed_daily(
            conn,
            code="000001.SZ",
            amount=300_000.0,
            vendor_version="vv_choice_tushare_stock_20251231",
        )
        _seed_limit(conn, code="000001.SZ")
        _seed_factor(conn, "000001.SZ")
    finally:
        conn.close()

    result = module.export_livermore_pretrade_check(
        duckdb_path=db_path,
        output_dir=tmp_path / "out",
        top_n=1,
        min_amount=200_000_000.0,
        today="2026-05-27",
    )

    row = result["rows"][0]
    assert row["amount"] == 300_000_000.0
    assert "low_liquidity" not in {flag["kind"] for flag in row["risk_flags"]}


def test_pretrade_export_legacy_schema_fails_closed_to_null_amount_and_warns(
    tmp_path: Path,
    caplog,
) -> None:
    module = _load_pretrade_module()
    db_path = tmp_path / "moss.duckdb"
    conn = _create_pretrade_db(db_path)
    try:
        _seed_candidate(conn, rank=1, code="000001.SZ")
        _seed_daily(conn, code="000001.SZ", amount=1_234.0)
        _seed_limit(conn, code="000001.SZ")
        _seed_factor(conn, "000001.SZ")
        conn.execute("alter table choice_stock_daily_observation drop column vendor_version")
    finally:
        conn.close()

    result = module.export_livermore_pretrade_check(
        duckdb_path=db_path,
        output_dir=tmp_path / "out",
        top_n=1,
        today="2026-05-27",
    )

    row = result["rows"][0]
    assert row["amount"] is None
    assert "missing_amount" in {flag["kind"] for flag in row["risk_flags"]}
    assert "low_liquidity" not in {flag["kind"] for flag in row["risk_flags"]}
    assert "vendor_version" in caplog.text


def test_pretrade_export_legacy_schema_does_not_misjudge_low_liquidity_with_positive_threshold(
    tmp_path: Path,
) -> None:
    """缺 vendor_version 列时,raw tushare 量级(千元)若直接与 --min-amount(元)比较会
    把高流动性股票误判为低流动性(如 raw 300_000 对应 3 亿元,被 2 亿元阈值误判)。
    fail-closed 后 amount 应为 NULL,该行流动性判定为 missing_amount,不产生
    low_liquidity 误判。"""
    module = _load_pretrade_module()
    db_path = tmp_path / "moss.duckdb"
    conn = _create_pretrade_db(db_path)
    try:
        _seed_candidate(conn, rank=1, code="000001.SZ")
        _seed_daily(conn, code="000001.SZ", amount=300_000.0)
        _seed_limit(conn, code="000001.SZ")
        _seed_factor(conn, "000001.SZ")
        conn.execute("alter table choice_stock_daily_observation drop column vendor_version")
    finally:
        conn.close()

    result = module.export_livermore_pretrade_check(
        duckdb_path=db_path,
        output_dir=tmp_path / "out",
        top_n=1,
        min_amount=200_000_000.0,
        today="2026-05-27",
    )

    row = result["rows"][0]
    assert row["amount"] is None
    flag_kinds = {flag["kind"] for flag in row["risk_flags"]}
    assert "low_liquidity" not in flag_kinds
    assert "missing_amount" in flag_kinds


def test_pretrade_export_null_vendor_row_propagates_none_amount_with_warning(
    tmp_path: Path,
    caplog,
) -> None:
    module = _load_pretrade_module()
    db_path = tmp_path / "moss.duckdb"
    conn = _create_pretrade_db(db_path)
    try:
        _seed_candidate(conn, rank=1, code="000001.SZ")
        _seed_daily(conn, code="000001.SZ", amount=1_000_000.0, vendor_version=None)
        _seed_limit(conn, code="000001.SZ")
        _seed_factor(conn, "000001.SZ")
    finally:
        conn.close()

    result = module.export_livermore_pretrade_check(
        duckdb_path=db_path,
        output_dir=tmp_path / "out",
        top_n=1,
        today="2026-05-27",
    )

    row = result["rows"][0]
    assert row["amount"] is None
    assert "vendor_version" in caplog.text


def test_pretrade_export_main_emits_json(monkeypatch, capsys) -> None:
    module = _load_pretrade_module()
    monkeypatch.setattr(
        module,
        "export_livermore_pretrade_check",
        lambda **_kwargs: {"status": "completed", "decision": {"action": "review_only"}},
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "export_livermore_pretrade_check.py",
            "--duckdb-path",
            "data/moss.duckdb",
        ],
    )

    assert module.main() == 0
    assert '"review_only"' in capsys.readouterr().out
