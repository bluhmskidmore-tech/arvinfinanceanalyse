"""交易状态判定口径统一（MEDIUM-7）与 candidate_history_service tasks 延迟导入回归。

覆盖四件事：
1. 共享 ``is_tradestatus_tradable`` 语义（docs/data_contracts.md §4.10）：
   'Trading'/'trading'/'交易'/'正常交易'/'复牌' 为 True，choice_native 代际
   空串/None/空白视为正常交易日亦为 True，'停牌一天'/'连续停牌'/'Suspended'
   等非空停牌值为 False；SQL 片段与 Python 判定同口径。
2. 共享 ``is_tradestatus_halted`` 停牌互补口径（非空且不可交易）及卖出顺延
   消费点回归：matched_baseline / candidate_history_materialize 的 entry
   block 与首个可卖 bar 在"停牌一天"/"连续停牌"等词值日必须顺延。
3. market_data_livermore_service 侧：供应商落地中文交易状态时，
   trading 历史与当日快照不得静默取空。
4. ``import backend.app.services.livermore_candidate_history_service`` 不得把
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
    TRADABLE_STATUS_SQL_IN_LIST,
    TRADABLE_STATUS_VALUES,
    TRADING_STATUS_VALUES,
    is_tradestatus_halted,
    is_tradestatus_tradable,
    tradable_status_sql_condition,
)
from backend.app.services import market_data_livermore_service as livermore_service

ROOT = Path(__file__).resolve().parents[1]
AS_OF_DATE = "2026-06-30"

_TRADABLE_SAMPLES = [
    "Trading",
    "trading",
    "TRADING",
    " Trading ",
    "交易",
    "正常交易",
    " 正常交易 ",
    "复牌",
    " 复牌 ",
    None,
    "",
    "   ",
]
_NON_TRADABLE_SAMPLES = [
    "Suspended",
    "停牌",
    "停牌一天",
    "连续停牌",
    "盘中停牌",
    "未上市",
    "退市整理",
    "unknown-status",
]


@pytest.mark.parametrize("value", _TRADABLE_SAMPLES)
def test_is_tradestatus_tradable_accepts_trading_resumption_and_blank(value: str | None) -> None:
    assert is_tradestatus_tradable(value) is True


@pytest.mark.parametrize("value", _NON_TRADABLE_SAMPLES)
def test_is_tradestatus_tradable_rejects_explicit_halt_and_unknown_values(value: str) -> None:
    assert is_tradestatus_tradable(value) is False


@pytest.mark.parametrize("value", _NON_TRADABLE_SAMPLES)
def test_is_tradestatus_halted_flags_all_nonempty_non_tradable_values(value: str) -> None:
    """生产真实词值"停牌一天"/"连续停牌"/"盘中停牌"及未知非空值均判停牌
    （fail-closed）；旧完整匹配词表只认"停牌"，漏判这些值导致卖出不顺延。"""
    assert is_tradestatus_halted(value) is True


@pytest.mark.parametrize("value", _TRADABLE_SAMPLES)
def test_is_tradestatus_halted_keeps_blank_trading_and_resumption_sellable(value: str | None) -> None:
    assert is_tradestatus_halted(value) is False


def test_is_tradestatus_halted_is_complement_of_tradable_on_nonempty_domain() -> None:
    """互补口径：halted == 非空 and not tradable；空串/None/空白既非可交易黑名单
    也非停牌（choice_native 正常交易日）。"""
    for value in (*_TRADABLE_SAMPLES, *_NON_TRADABLE_SAMPLES):
        text = str(value or "").strip()
        assert is_tradestatus_halted(value) is (bool(text) and not is_tradestatus_tradable(value)), value


def test_tradable_status_sql_in_list_derives_from_word_list() -> None:
    assert TRADING_STATUS_VALUES == ("trading", "交易", "正常交易")
    assert TRADABLE_STATUS_VALUES == ("trading", "交易", "正常交易", "复牌")
    assert TRADABLE_STATUS_SQL_IN_LIST == "('', 'trading', '交易', '正常交易', '复牌')"
    condition = tradable_status_sql_condition("tradestatus")
    assert condition == (
        "(lower(trim(coalesce(cast(tradestatus as varchar), ''))) in "
        "('', 'trading', '交易', '正常交易', '复牌'))"
    )


def test_tradable_status_sql_condition_matches_python_semantics() -> None:
    conn = duckdb.connect(":memory:")
    try:
        conn.execute("create table probe (tradestatus varchar)")
        samples = [*_TRADABLE_SAMPLES, *_NON_TRADABLE_SAMPLES]
        conn.executemany("insert into probe values (?)", [(value,) for value in samples])
        rows = conn.execute(
            f"select tradestatus, {tradable_status_sql_condition('tradestatus')} from probe"
        ).fetchall()
    finally:
        conn.close()
    assert len(rows) == len(samples)
    for value, sql_verdict in rows:
        assert bool(sql_verdict) is is_tradestatus_tradable(value), value
        # SQL 侧停牌判定 = 可交易条件的否定（NULL/空白归一为空串 → 可交易 →
        # 否定为 False），与 is_tradestatus_halted 完全同口径。
        assert (not bool(sql_verdict)) is is_tradestatus_halted(value), value


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


def _halt_window_bars() -> list[dict[str, object]]:
    """对齐生产 688260.SH 形态：停牌 bar 带前收陈旧 close（close 非空不可作可卖依据）。"""
    return [
        {"trade_date": "2026-06-25", "open_value": 136.0, "close_value": 144.0, "tradestatus": "正常交易"},
        {"trade_date": "2026-06-26", "open_value": 144.0, "close_value": 144.0, "tradestatus": "连续停牌"},
        {"trade_date": "2026-06-29", "open_value": 144.0, "close_value": 144.0, "tradestatus": "停牌一天"},
        {"trade_date": "2026-07-01", "open_value": 132.0, "close_value": 130.7, "tradestatus": "复牌"},
    ]


def test_matched_baseline_sell_defers_past_real_halt_values() -> None:
    """matched_baseline 卖出顺延回归：目标 bar 落"连续停牌"时跳过后续停牌值
    bar，顺延到复牌 bar；entry 落停牌值日记 entry_halted。"""
    import backend.app.core_finance.matched_baseline as matched_baseline_module

    bars = _halt_window_bars()
    exit_bar = matched_baseline_module._first_sellable_bar_at_or_after(bars, 1)
    assert exit_bar is not None
    assert exit_bar["trade_date"] == "2026-07-01"

    assert matched_baseline_module._entry_block_reason(bars[1], entry_price=144.0) == "entry_halted"
    assert matched_baseline_module._entry_block_reason(bars[3], entry_price=132.0) == ""
    blank_bar = {"trade_date": "2026-07-02", "close_value": 130.0, "tradestatus": ""}
    assert matched_baseline_module._entry_block_reason(blank_bar, entry_price=130.0) == ""


def test_execution_materialize_sell_defers_past_real_halt_values() -> None:
    """execution history 卖出顺延回归：与 matched_baseline 同口径。"""
    import backend.app.tasks.livermore_candidate_history_materialize as materialize_task

    bars = _halt_window_bars()
    exit_bar = materialize_task._first_sellable_bar_at_or_after(bars, 1)
    assert exit_bar is not None
    assert exit_bar["trade_date"] == "2026-07-01"

    assert materialize_task._entry_block_reason(bars[2], entry_price=144.0) == "entry_halted"
    assert materialize_task._entry_block_reason(bars[3], entry_price=132.0) == ""


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
