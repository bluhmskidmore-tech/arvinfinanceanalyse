"""交易状态判定口径统一（MEDIUM-7）与 candidate_history_service tasks 延迟导入回归。

覆盖三件事：
1. 共享 ``is_trading_status`` 词表：'Trading'/'trading'/'交易'/'正常交易' 为 True，
   'Suspended'/None/'' 为 False。
2. market_data_livermore_service 侧：供应商落地中文交易状态时，
   trading 历史与当日快照不得静默取空。
3. ``import backend.app.services.livermore_candidate_history_service`` 不得把
   ``backend.app.tasks.*`` 带进 ``sys.modules``。
"""

from __future__ import annotations

import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import duckdb
import pytest

from backend.app.core_finance.field_normalization import (
    TRADING_STATUS_SQL_IN_LIST,
    TRADING_STATUS_VALUES,
    is_trading_status,
)
from backend.app.services import market_data_livermore_service as livermore_service

ROOT = Path(__file__).resolve().parents[1]
AS_OF_DATE = "2026-06-30"


@pytest.mark.parametrize(
    "value",
    ["Trading", "trading", "TRADING", " Trading ", "交易", "正常交易", " 正常交易 "],
)
def test_is_trading_status_accepts_known_variants(value: str) -> None:
    assert is_trading_status(value) is True


@pytest.mark.parametrize("value", ["Suspended", None, "", "   ", "停牌", "退市整理"])
def test_is_trading_status_rejects_non_trading_values(value: str | None) -> None:
    assert is_trading_status(value) is False


def test_trading_status_sql_in_list_derives_from_word_list() -> None:
    assert TRADING_STATUS_VALUES == ("trading", "交易", "正常交易")
    assert TRADING_STATUS_SQL_IN_LIST == "('trading', '交易', '正常交易')"
    for value in TRADING_STATUS_VALUES:
        assert f"'{value}'" in TRADING_STATUS_SQL_IN_LIST


def _seed_chinese_status_observation(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        create table choice_stock_daily_observation (
          trade_date varchar,
          stock_code varchar,
          close_value double,
          turn double,
          amount double,
          volume double,
          tradestatus varchar,
          pctchange double,
          low_value double,
          high_value double,
          amplitude double,
          vendor_version varchar
        )
        """
    )
    as_of = date.fromisoformat(AS_OF_DATE)
    rows: list[tuple[object, ...]] = []
    for offset in range(10):
        trade_date = (as_of - timedelta(days=offset)).isoformat()
        # 供应商中文状态：'交易' 与 '正常交易' 混排，另加一行停牌应被剔除。
        tradestatus = "正常交易" if offset % 2 else "交易"
        if offset == 5:
            tradestatus = "停牌"
        rows.append(
            (
                trade_date,
                "600000.SH",
                float(10 + offset),
                1.2,
                float(10000 + offset),
                float(100000 + offset),
                tradestatus,
                0.5,
                9.5,
                10.5,
                2.0,
                # choice_native 代际 vendor:amount/volume 归一化为恒等变换。
                "vv_choice_stock_20260630_001",
            )
        )
    conn.executemany(
        "insert into choice_stock_daily_observation values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )


def test_dual_stock_history_accepts_chinese_trading_status() -> None:
    conn = duckdb.connect(":memory:")
    try:
        _seed_chinese_status_observation(conn)
        actual = livermore_service._load_dual_stock_history_inputs(
            conn=conn,
            as_of_date=AS_OF_DATE,
            candidate_stock_codes=[],
            trading_stock_codes=["600000.SH"],
        )
    finally:
        conn.close()

    trading_history = actual.trading_history_by_code.get("600000.SH")
    assert trading_history is not None, "中文交易状态下 trading 历史不得静默取空"
    # 10 行里 1 行停牌被剔除，9 行 trading 状态保留。
    assert len(trading_history["close"]) == 9
    assert 15.0 not in trading_history["close"]


def test_trading_snapshot_inputs_accept_chinese_trading_status(tmp_path) -> None:
    db_path = tmp_path / "chinese-status.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        _seed_chinese_status_observation(conn)
        conn.execute(
            """
            create table choice_stock_universe (
              as_of_date varchar, stock_code varchar, stock_name varchar
            );
            create table choice_stock_sector_membership (
              as_of_date varchar, stock_code varchar, sw2021code varchar, sw2021 varchar
            )
            """
        )
        conn.execute(
            "insert into choice_stock_universe values (?, '600000.SH', 'Alpha')",
            [AS_OF_DATE],
        )
        conn.execute(
            "insert into choice_stock_sector_membership values (?, '600000.SH', '801780', 'Bank')",
            [AS_OF_DATE],
        )
    finally:
        conn.close()

    inputs = livermore_service._load_trading_stock_snapshot_inputs(
        duckdb_path=str(db_path),
        as_of_date=AS_OF_DATE,
    )

    assert [row.stock_code for row in inputs.current_rows] == ["600000.SH"]
    history = inputs.history_by_code.get("600000.SH")
    assert history is not None
    assert len(history["close"]) == 9


def test_candidate_history_service_import_does_not_load_tasks_modules() -> None:
    code = (
        "import sys; "
        "import backend.app.services.livermore_candidate_history_service; "
        "loaded = sorted(m for m in sys.modules if m.startswith('backend.app.tasks')); "
        "assert not loaded, loaded"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
