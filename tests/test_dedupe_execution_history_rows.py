"""dedupe_execution_history_rows：保留规则与写入侧对齐（审计发现 3）。

覆盖：
- 脚本直接复用写入侧 ``_execution_history_row_priority``（同一函数对象，
  非复刻），保留 (已填 *_net_adj 收益数 desc, candidate_rank asc,
  run_id 字典序 desc) 最大行，priority 完全平手保留最小 rowid；
- 审计场景："旧 run 部分回补 + 新 run 完整回补"必须保留收益完整行
  （旧 first_physical_row 规则会错保部分回补的首物理行并删掉完整行）；
- dry-run 只出计划不删行，keep/delete 行引用带
  ``populated_net_adj_return_count`` 等选择依据；
- execute 事务删除后重复键清零、幂等重跑无新计划；
- 表缺 *_net_adj 列时校验 fail-closed。
"""
from __future__ import annotations

import json

import duckdb
import pytest

from backend.app.tasks.livermore_candidate_history_materialize import (
    _execution_history_row_priority,
)
from tests.helpers import load_module

SIGNAL_DATE = "2026-03-01"
FORMULA_VERSION = "fv_livermore_candidate_execution_dual_adjust_v5"


def _load_script():
    return load_module(
        "scripts.dedupe_execution_history_rows",
        "scripts/dedupe_execution_history_rows.py",
    )


def _create_table(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        create table livermore_candidate_execution_history (
          signal_date varchar,
          stock_code varchar,
          signal_kind varchar,
          candidate_rank integer,
          entry_date varchar,
          formula_version varchar,
          run_id varchar,
          return_1d_net_adj double,
          return_5d_net_adj double,
          return_10d_net_adj double,
          return_20d_net_adj double
        )
        """
    )


def _insert_row(
    conn: duckdb.DuckDBPyConnection,
    *,
    stock_code: str,
    run_id: str,
    candidate_rank: int = 1,
    entry_date: str = "2026-03-02",
    net_adj: tuple[float | None, float | None, float | None, float | None] = (
        0.01,
        0.02,
        0.03,
        0.04,
    ),
) -> None:
    conn.execute(
        "insert into livermore_candidate_execution_history values (?,?,?,?,?,?,?,?,?,?,?)",
        [
            SIGNAL_DATE,
            stock_code,
            "stock_candidate",
            candidate_rank,
            entry_date,
            FORMULA_VERSION,
            run_id,
            *net_adj,
        ],
    )


def _create_fixture_db(db_path: str) -> None:
    conn = duckdb.connect(db_path)
    try:
        _create_table(conn)
        # KEY1（审计场景）：旧 run 部分回补先插入，新 run 完整回补后插入。
        # 旧 first_physical_row 规则会保留部分回补行；写入侧规则保留完整行。
        _insert_row(conn, stock_code="000001.SZ", run_id="backfill:run-old", net_adj=(0.01, None, None, None))
        _insert_row(conn, stock_code="000001.SZ", run_id="backfill:run-new")
        # KEY2：收益填充相同，rank 2 先插入、rank 1 后插入 → 保留 rank 1
        # （kept run_id 字典序更小，证明 rank 优先级高于 run_id）。
        _insert_row(conn, stock_code="000002.SZ", run_id="backfill:run-b", candidate_rank=2)
        _insert_row(conn, stock_code="000002.SZ", run_id="backfill:run-a", candidate_rank=1)
        # KEY3（存量 14 键形态）：仅 run_id 后缀不同 → 保留字典序最大的
        # exp3c_shadow，即便它不是首物理行。
        _insert_row(conn, stock_code="000003.SZ", run_id="backfill:exp3b")
        _insert_row(conn, stock_code="000003.SZ", run_id="backfill:exp3c_shadow")
        # KEY4：priority 三键完全平手 → 确定性保留最小 rowid（首物理行）。
        _insert_row(conn, stock_code="000004.SZ", run_id="backfill:run-same", entry_date="2026-03-02")
        _insert_row(conn, stock_code="000004.SZ", run_id="backfill:run-same", entry_date="2026-03-03")
        # KEY5：非重复行，不得进入计划。
        _insert_row(conn, stock_code="000005.SZ", run_id="backfill:run-solo")
    finally:
        conn.close()


def _plan_by_stock(payload: dict) -> dict[str, dict]:
    return {plan["key"]["stock_code"]: plan for plan in payload["plans"]}


def test_keep_rule_reuses_write_side_priority_function() -> None:
    module = _load_script()
    # 直接引用写入侧函数对象，杜绝复刻漂移。
    assert module._execution_history_row_priority is _execution_history_row_priority
    assert module.KEEP_RULE == "write_side_execution_history_row_priority"


def test_dry_run_plans_write_side_keep_and_exposes_selection_basis(tmp_path) -> None:
    module = _load_script()
    db_path = str(tmp_path / "exec.duckdb")
    _create_fixture_db(db_path)

    payload = module.inspect_or_execute(module._resolve_workspace_path(db_path), execute=False)

    assert payload["status"] == "ok"
    assert payload["mode"] == "dry_run"
    assert payload["keep_rule"] == "write_side_execution_history_row_priority"
    assert "_execution_history_row_priority" in payload["keep_rule_reason"]
    assert payload["before"]["duplicate_key_count"] == 4
    assert payload["planned_delete_row_count"] == 4
    assert payload["deleted_row_count"] == 0
    assert payload["after"] is None

    plans = _plan_by_stock(payload)
    assert set(plans) == {"000001.SZ", "000002.SZ", "000003.SZ", "000004.SZ"}

    # 审计场景：保留收益完整的新 run 行，删除部分回补的首物理行。
    key1 = plans["000001.SZ"]
    assert key1["keep"]["run_id"] == "backfill:run-new"
    assert key1["keep"]["populated_net_adj_return_count"] == 4
    assert [row["run_id"] for row in key1["delete"]] == ["backfill:run-old"]
    assert key1["delete"][0]["populated_net_adj_return_count"] == 1

    # rank 优先于 run_id：保留 rank 1 行。
    key2 = plans["000002.SZ"]
    assert key2["keep"]["run_id"] == "backfill:run-a"
    assert key2["keep"]["candidate_rank"] == 1
    assert [row["candidate_rank"] for row in key2["delete"]] == [2]

    # run_id 字典序取最大：保留 exp3c_shadow（非首物理行）。
    key3 = plans["000003.SZ"]
    assert key3["keep"]["run_id"] == "backfill:exp3c_shadow"
    assert [row["run_id"] for row in key3["delete"]] == ["backfill:exp3b"]

    # 完全平手：保留最小 rowid（首物理行 entry_date=2026-03-02）。
    key4 = plans["000004.SZ"]
    assert key4["keep"]["entry_date"] == "2026-03-02"
    assert key4["keep"]["physical_rowid"] < key4["delete"][0]["physical_rowid"]

    # dry-run 不落盘。
    conn = duckdb.connect(db_path, read_only=True)
    try:
        count = conn.execute("select count(*) from livermore_candidate_execution_history").fetchone()[0]
    finally:
        conn.close()
    assert count == 9


def test_execute_deletes_lower_priority_rows_and_is_idempotent(tmp_path) -> None:
    module = _load_script()
    db_path = str(tmp_path / "exec.duckdb")
    _create_fixture_db(db_path)

    payload = module.inspect_or_execute(module._resolve_workspace_path(db_path), execute=True)

    assert payload["status"] == "ok"
    assert payload["mode"] == "execute"
    assert payload["deleted_row_count"] == 4
    assert payload["after"]["physical_row_count"] == 5
    assert payload["after"]["duplicate_key_count"] == 0

    conn = duckdb.connect(db_path, read_only=True)
    try:
        survivors = conn.execute(
            """
            select stock_code, candidate_rank, entry_date, run_id, return_5d_net_adj
            from livermore_candidate_execution_history
            order by stock_code
            """
        ).fetchall()
    finally:
        conn.close()

    by_stock = {row[0]: row for row in survivors}
    assert set(by_stock) == {"000001.SZ", "000002.SZ", "000003.SZ", "000004.SZ", "000005.SZ"}
    # 审计场景：保留的是收益完整行（return_5d_net_adj 已填）。
    assert by_stock["000001.SZ"][3] == "backfill:run-new"
    assert by_stock["000001.SZ"][4] == pytest.approx(0.02)
    assert by_stock["000002.SZ"][3] == "backfill:run-a"
    assert by_stock["000002.SZ"][1] == 1
    assert by_stock["000003.SZ"][3] == "backfill:exp3c_shadow"
    assert by_stock["000004.SZ"][2] == "2026-03-02"
    assert by_stock["000005.SZ"][3] == "backfill:run-solo"

    # 幂等：重复行清零后再跑无新删除计划。
    rerun = module.inspect_or_execute(module._resolve_workspace_path(db_path), execute=True)
    assert rerun["planned_delete_row_count"] == 0
    assert rerun["deleted_row_count"] == 0
    assert rerun["before"]["duplicate_key_count"] == 0


def test_validation_fails_closed_when_net_adj_columns_missing(tmp_path) -> None:
    # 保留规则依赖 *_net_adj 列：缺列的旧快照必须显式报错而非静默走错误口径。
    module = _load_script()
    db_path = str(tmp_path / "legacy.duckdb")
    conn = duckdb.connect(db_path)
    try:
        conn.execute(
            """
            create table livermore_candidate_execution_history (
              signal_date varchar, stock_code varchar, signal_kind varchar,
              candidate_rank integer, entry_date varchar,
              formula_version varchar, run_id varchar
            )
            """
        )
    finally:
        conn.close()

    with pytest.raises(ValueError, match="return_1d_net_adj"):
        module.inspect_or_execute(module._resolve_workspace_path(db_path), execute=False)


def test_cli_dry_run_prints_keep_rule_payload(tmp_path, capsys) -> None:
    module = _load_script()
    db_path = str(tmp_path / "exec.duckdb")
    _create_fixture_db(db_path)

    exit_code = module.main(["--duckdb-path", db_path])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok"
    assert payload["keep_rule"] == "write_side_execution_history_row_priority"
    assert payload["planned_delete_row_count"] == 4
