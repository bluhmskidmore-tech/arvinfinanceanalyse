from __future__ import annotations

import importlib
from decimal import Decimal
from pathlib import Path

import duckdb
import pytest

import backend.app.tasks.accounting_asset_movement as movement_task
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    CACHE_MANIFEST_STREAM,
    GovernanceRepository,
)
from backend.app.tasks.accounting_asset_movement import (
    AccountingAssetMovementChainBrokenError,
    AccountingAssetMovementControlWarning,
    AccountingAssetMovementPositionSourceMissingError,
    AccountingAssetMovementSourceMissingError,
    materialize_accounting_asset_movement_on_connection,
)

_ZQTZ_DDL = """
create table fact_formal_zqtz_balance_daily (
  report_date varchar,
  instrument_code varchar,
  portfolio_name varchar,
  cost_center varchar,
  maturity_date varchar,
  accounting_basis varchar,
  position_scope varchar,
  currency_basis varchar,
  market_value_amount decimal(24, 8),
  amortized_cost_amount decimal(24, 8),
  source_version varchar,
  rule_version varchar
)
"""

_GL_DDL = """
create table product_category_pnl_canonical_fact (
  report_date varchar,
  account_code varchar,
  currency varchar,
  account_name varchar,
  beginning_balance decimal(24, 8),
  ending_balance decimal(24, 8),
  monthly_pnl decimal(24, 8),
  daily_avg_balance decimal(24, 8),
  annual_avg_balance decimal(24, 8),
  days_in_period integer,
  source_version varchar,
  rule_version varchar
)
"""

# 总账侧：TPL=110、AC=220+4+1=225、OCI=80（期初 TPL=100、AC=205、OCI=70）。
_GL_ROWS_2026_02 = [
    ("2026-02-28", "14101010001", "CNX", "TPL", "100", "110", "0", "0", "0", 28, "sv-gl", "rv-gl"),
    ("2026-02-28", "14201010001", "CNX", "AC bond", "200", "220", "0", "0", "0", 28, "sv-gl", "rv-gl"),
    ("2026-02-28", "14301010001", "CNX", "Voucher bond", "4", "4", "0", "0", "0", 28, "sv-gl", "rv-gl"),
    ("2026-02-28", "14301010002", "CNX", "Voucher accrued", "1", "1", "0", "0", "0", 28, "sv-gl", "rv-gl"),
    ("2026-02-28", "14401010001", "CNX", "OCI debt", "70", "80", "0", "0", "0", 28, "sv-gl", "rv-gl"),
    ("2026-02-28", "14402010001", "CNX", "OCI equity", "90", "99", "0", "0", "0", 28, "sv-gl", "rv-gl"),
]


def _seed_movement_sources(
    conn: duckdb.DuckDBPyConnection,
    *,
    zqtz_rows: list[tuple[object, ...]],
) -> None:
    conn.execute(_ZQTZ_DDL)
    conn.execute(_GL_DDL)
    if zqtz_rows:
        conn.executemany(
            """
            insert into fact_formal_zqtz_balance_daily (
              report_date, accounting_basis, position_scope, currency_basis,
              market_value_amount, amortized_cost_amount, source_version, rule_version
            ) values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            zqtz_rows,
        )
    conn.executemany(
        "insert into product_category_pnl_canonical_fact values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        _GL_ROWS_2026_02,
    )


def _persisted_rows(conn: duckdb.DuckDBPyConnection, report_date: str) -> dict[str, dict[str, object]]:
    rows = conn.execute(
        """
        select basis_bucket, previous_balance, current_balance, balance_change,
               zqtz_amount, gl_amount, reconciliation_diff, reconciliation_status,
               chain_status, position_source_basis
        from fact_accounting_asset_movement_monthly
        where report_date = ?
        order by sort_order
        """,
        [report_date],
    ).fetchall()
    return {
        row[0]: {
            "previous_balance": row[1],
            "current_balance": row[2],
            "balance_change": row[3],
            "zqtz_amount": row[4],
            "gl_amount": row[5],
            "reconciliation_diff": row[6],
            "reconciliation_status": row[7],
            "chain_status": row[8],
            "position_source_basis": row[9],
        }
        for row in rows
    }


def test_accounting_asset_movement_materialize_writes_monthly_reconciliation_rows():
    conn = duckdb.connect(":memory:")
    try:
        # 头寸侧与总账口径一致：AC 摊余 225、FVOCI 市值 80、FVTPL 市值 110。
        _seed_movement_sources(
            conn,
            zqtz_rows=[
                ("2026-02-28", "FVTPL", "asset", "CNY", "110", "0", "sv-zqtz", "rv-zqtz"),
                ("2026-02-28", "AC", "asset", "CNY", "0", "225", "sv-zqtz", "rv-zqtz"),
                ("2026-02-28", "FVOCI", "asset", "CNY", "80", "0", "sv-zqtz", "rv-zqtz"),
            ],
        )

        written = materialize_accounting_asset_movement_on_connection(
            conn,
            report_date="2026-02-28",
            currency_basis="CNX",
        )
        by_bucket = _persisted_rows(conn, "2026-02-28")
    finally:
        conn.close()

    assert len(written) == 3
    assert by_bucket["AC"]["previous_balance"] == Decimal("205.00000000")
    assert by_bucket["AC"]["current_balance"] == Decimal("225.00000000")
    assert by_bucket["AC"]["balance_change"] == Decimal("20.00000000")
    assert by_bucket["AC"]["zqtz_amount"] == Decimal("225.00000000")
    assert by_bucket["AC"]["reconciliation_status"] == "matched"
    assert by_bucket["TPL"]["reconciliation_status"] == "matched"
    assert by_bucket["OCI"]["current_balance"] == Decimal("80.00000000")
    assert by_bucket["OCI"]["reconciliation_status"] == "matched"


def test_cnx_reconciliation_reads_independent_position_source_not_the_ledger():
    """回归：CNX 曾经从 product_category_pnl_canonical_fact 自取头寸，
    diff 恒为 0、status 恒为 matched。现在头寸侧必须来自 ZQTZ 正式头寸表，
    两侧不一致时必须报出来。"""
    conn = duckdb.connect(":memory:")
    try:
        _seed_movement_sources(
            conn,
            zqtz_rows=[
                # 与总账差 1 元（TPL）、差 5 元（AC）、完全缺失（OCI）。
                ("2026-02-28", "FVTPL", "asset", "CNY", "111", "0", "sv-zqtz", "rv-zqtz"),
                ("2026-02-28", "AC", "asset", "CNY", "0", "220", "sv-zqtz", "rv-zqtz"),
            ],
        )
        materialize_accounting_asset_movement_on_connection(
            conn,
            report_date="2026-02-28",
            currency_basis="CNX",
        )
        by_bucket = _persisted_rows(conn, "2026-02-28")
    finally:
        conn.close()

    assert by_bucket["TPL"]["zqtz_amount"] == Decimal("111.00000000")
    assert by_bucket["TPL"]["gl_amount"] == Decimal("110.00000000")
    assert by_bucket["TPL"]["reconciliation_diff"] == Decimal("1.00000000")
    assert by_bucket["TPL"]["reconciliation_status"] == "mismatch"

    assert by_bucket["AC"]["zqtz_amount"] == Decimal("220.00000000")
    assert by_bucket["AC"]["reconciliation_diff"] == Decimal("-5.00000000")
    assert by_bucket["AC"]["reconciliation_status"] == "mismatch"

    # 总账有余额、头寸源没有对应分类：gl_only，不能是 matched。
    assert by_bucket["OCI"]["zqtz_amount"] == Decimal("0E-8")
    assert by_bucket["OCI"]["reconciliation_status"] == "gl_only"


def test_reconciliation_uses_relative_tolerance_not_one_cent():
    """千亿级余额上 0.01 元的绝对容差没有可操作性；容差必须随头寸规模缩放。"""
    conn = duckdb.connect(":memory:")
    try:
        conn.execute(_ZQTZ_DDL)
        conn.execute(_GL_DDL)
        conn.executemany(
            "insert into product_category_pnl_canonical_fact values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "2026-02-28", "14101010001", "CNX", "TPL",
                    "100000000000", "100000000000", "0", "0", "0", 28, "sv-gl", "rv-gl",
                ),
            ],
        )
        conn.executemany(
            """
            insert into fact_formal_zqtz_balance_daily (
              report_date, accounting_basis, position_scope, currency_basis,
              market_value_amount, amortized_cost_amount, source_version, rule_version
            ) values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                # 1e11 上差 50 元 = 5e-10 相对差，属于舍入噪声。
                ("2026-02-28", "FVTPL", "asset", "CNY", "100000000050", "0", "sv-zqtz", "rv-zqtz"),
            ],
        )
        materialize_accounting_asset_movement_on_connection(
            conn,
            report_date="2026-02-28",
            currency_basis="CNX",
        )
        tolerated = _persisted_rows(conn, "2026-02-28")["TPL"]

        conn.execute("update fact_formal_zqtz_balance_daily set market_value_amount = '100500000000'")
        materialize_accounting_asset_movement_on_connection(
            conn,
            report_date="2026-02-28",
            currency_basis="CNX",
        )
        breached = _persisted_rows(conn, "2026-02-28")["TPL"]
    finally:
        conn.close()

    assert tolerated["reconciliation_diff"] == Decimal("50.00000000")
    assert tolerated["reconciliation_status"] == "matched"
    # 5e-3 相对差远超 1e-6 容差。
    assert breached["reconciliation_status"] == "mismatch"


def test_materialize_marks_gl_only_when_position_source_table_is_absent():
    conn = duckdb.connect(":memory:")
    try:
        conn.execute(_GL_DDL)
        conn.executemany(
            "insert into product_category_pnl_canonical_fact values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            _GL_ROWS_2026_02,
        )
        with pytest.warns(AccountingAssetMovementControlWarning, match="position source"):
            materialize_accounting_asset_movement_on_connection(
                conn,
                report_date="2026-02-28",
                currency_basis="CNX",
            )
        by_bucket = _persisted_rows(conn, "2026-02-28")
    finally:
        conn.close()

    assert {row["reconciliation_status"] for row in by_bucket.values()} == {"gl_only"}


def test_materialize_position_source_gate_refuses_to_persist_when_enforced(monkeypatch):
    monkeypatch.setenv(movement_task.CONTROL_GATE_ENV, "enforce")
    conn = duckdb.connect(":memory:")
    try:
        conn.execute(_ZQTZ_DDL)
        conn.execute(_GL_DDL)
        conn.executemany(
            "insert into product_category_pnl_canonical_fact values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            _GL_ROWS_2026_02,
        )
        with pytest.raises(AccountingAssetMovementPositionSourceMissingError):
            materialize_accounting_asset_movement_on_connection(
                conn,
                report_date="2026-02-28",
                currency_basis="CNX",
            )
        row_count = conn.execute(
            "select count(*) from fact_accounting_asset_movement_monthly"
        ).fetchone()[0]
    finally:
        conn.close()

    assert row_count == 0


def test_chain_continuity_gate_refuses_to_persist_when_enforced(monkeypatch):
    """previous_balance(2026-02) 必须等于 current_balance(2026-01)。"""
    monkeypatch.setenv(movement_task.CONTROL_GATE_ENV, "enforce")
    conn = duckdb.connect(":memory:")
    try:
        _seed_movement_sources(
            conn,
            zqtz_rows=[
                ("2026-01-31", "FVTPL", "asset", "CNY", "500", "0", "sv-zqtz", "rv-zqtz"),
                ("2026-02-28", "FVTPL", "asset", "CNY", "110", "0", "sv-zqtz", "rv-zqtz"),
                ("2026-02-28", "AC", "asset", "CNY", "0", "225", "sv-zqtz", "rv-zqtz"),
                ("2026-02-28", "FVOCI", "asset", "CNY", "80", "0", "sv-zqtz", "rv-zqtz"),
            ],
        )
        # 上月期末 TPL=500，本月期初 TPL=100 —— 缺口 400。
        conn.executemany(
            "insert into product_category_pnl_canonical_fact values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "2026-01-31", "14101010001", "CNX", "TPL",
                    "480", "500", "0", "0", "0", 31, "sv-gl", "rv-gl",
                ),
            ],
        )
        materialize_accounting_asset_movement_on_connection(
            conn,
            report_date="2026-01-31",
            currency_basis="CNX",
        )
        with pytest.raises(AccountingAssetMovementChainBrokenError, match="chain is broken"):
            materialize_accounting_asset_movement_on_connection(
                conn,
                report_date="2026-02-28",
                currency_basis="CNX",
            )
        february_row_count = conn.execute(
            """
            select count(*)
            from fact_accounting_asset_movement_monthly
            where report_date = '2026-02-28'
            """
        ).fetchone()[0]
    finally:
        conn.close()

    assert february_row_count == 0


def test_chain_continuity_gate_warns_and_still_persists_by_default():
    conn = duckdb.connect(":memory:")
    try:
        _seed_movement_sources(
            conn,
            zqtz_rows=[
                ("2026-01-31", "FVTPL", "asset", "CNY", "500", "0", "sv-zqtz", "rv-zqtz"),
                ("2026-02-28", "FVTPL", "asset", "CNY", "110", "0", "sv-zqtz", "rv-zqtz"),
                ("2026-02-28", "AC", "asset", "CNY", "0", "225", "sv-zqtz", "rv-zqtz"),
                ("2026-02-28", "FVOCI", "asset", "CNY", "80", "0", "sv-zqtz", "rv-zqtz"),
            ],
        )
        conn.executemany(
            "insert into product_category_pnl_canonical_fact values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "2026-01-31", "14101010001", "CNX", "TPL",
                    "480", "500", "0", "0", "0", 31, "sv-gl", "rv-gl",
                ),
            ],
        )
        materialize_accounting_asset_movement_on_connection(
            conn,
            report_date="2026-01-31",
            currency_basis="CNX",
        )
        with pytest.warns(AccountingAssetMovementControlWarning, match="chain is broken"):
            materialize_accounting_asset_movement_on_connection(
                conn,
                report_date="2026-02-28",
                currency_basis="CNX",
            )
        february_row_count = conn.execute(
            """
            select count(*)
            from fact_accounting_asset_movement_monthly
            where report_date = '2026-02-28'
            """
        ).fetchone()[0]
    finally:
        conn.close()

    assert february_row_count == 3


def test_materialize_persists_three_distinguishable_control_conclusions():
    """gl_only / mismatch / chain_broken 必须以三个不同的值落库。

    这些结论此前只进 governance manifest 的 lineage，读模型看不到，页面上
    "根本没有对手方"和"真的对不平"长得完全一样。
    """
    conn = duckdb.connect(":memory:")
    try:
        _seed_movement_sources(
            conn,
            zqtz_rows=[
                # 一月：三桶都与总账一致，作为跨月比较的基准。
                ("2026-01-31", "FVTPL", "asset", "CNY", "110", "0", "sv-zqtz", "rv-zqtz"),
                # 二月：TPL 对得上、AC 差 5 元、OCI 头寸侧完全没有。
                ("2026-02-28", "FVTPL", "asset", "CNY", "110", "0", "sv-zqtz", "rv-zqtz"),
                ("2026-02-28", "AC", "asset", "CNY", "0", "220", "sv-zqtz", "rv-zqtz"),
            ],
        )
        conn.executemany(
            "insert into product_category_pnl_canonical_fact values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                # 一月期末 TPL=500，二月期初 TPL=100 —— 勾稽缺口 400。
                (
                    "2026-01-31", "14101010001", "CNX", "TPL",
                    "480", "500", "0", "0", "0", 31, "sv-gl", "rv-gl",
                ),
            ],
        )
        materialize_accounting_asset_movement_on_connection(
            conn,
            report_date="2026-01-31",
            currency_basis="CNX",
        )
        with pytest.warns(AccountingAssetMovementControlWarning, match="chain is broken"):
            materialize_accounting_asset_movement_on_connection(
                conn,
                report_date="2026-02-28",
                currency_basis="CNX",
            )
        by_bucket = _persisted_rows(conn, "2026-02-28")
        january = _persisted_rows(conn, "2026-01-31")
    finally:
        conn.close()

    assert by_bucket["TPL"]["reconciliation_status"] == "chain_broken"
    assert by_bucket["TPL"]["chain_status"] == "broken"
    assert by_bucket["AC"]["reconciliation_status"] == "mismatch"
    assert by_bucket["OCI"]["reconciliation_status"] == "gl_only"
    assert {row["position_source_basis"] for row in by_bucket.values()} == {"CNY"}
    # 首月没有可比基准，不能被当成断裂。
    assert {row["chain_status"] for row in january.values()} == {"no_prior_month"}


def test_materialize_records_unavailable_position_source_basis():
    conn = duckdb.connect(":memory:")
    try:
        conn.execute(_GL_DDL)
        conn.executemany(
            "insert into product_category_pnl_canonical_fact values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            _GL_ROWS_2026_02,
        )
        with pytest.warns(AccountingAssetMovementControlWarning, match="position source"):
            materialize_accounting_asset_movement_on_connection(
                conn,
                report_date="2026-02-28",
                currency_basis="CNX",
            )
        by_bucket = _persisted_rows(conn, "2026-02-28")
    finally:
        conn.close()

    # zqtz_amount / reconciliation_diff 在这些行上是"无对手方"的产物；口径列是
    # 读取端判断该不该按不适用呈现的唯一依据。
    assert {row["position_source_basis"] for row in by_bucket.values()} == {"unavailable"}
    assert {row["reconciliation_status"] for row in by_bucket.values()} == {"gl_only"}


def test_control_conclusions_persist_with_the_gate_switched_off(monkeypatch):
    """gate_mode='off' 只表示不拦截，不表示不判断。"""
    monkeypatch.setenv(movement_task.CONTROL_GATE_ENV, "off")
    conn = duckdb.connect(":memory:")
    try:
        _seed_movement_sources(
            conn,
            zqtz_rows=[
                ("2026-01-31", "FVTPL", "asset", "CNY", "500", "0", "sv-zqtz", "rv-zqtz"),
                ("2026-02-28", "FVTPL", "asset", "CNY", "110", "0", "sv-zqtz", "rv-zqtz"),
                ("2026-02-28", "AC", "asset", "CNY", "0", "225", "sv-zqtz", "rv-zqtz"),
                ("2026-02-28", "FVOCI", "asset", "CNY", "80", "0", "sv-zqtz", "rv-zqtz"),
            ],
        )
        conn.executemany(
            "insert into product_category_pnl_canonical_fact values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "2026-01-31", "14101010001", "CNX", "TPL",
                    "480", "500", "0", "0", "0", 31, "sv-gl", "rv-gl",
                ),
            ],
        )
        materialize_accounting_asset_movement_on_connection(
            conn,
            report_date="2026-01-31",
            currency_basis="CNX",
        )
        materialize_accounting_asset_movement_on_connection(
            conn,
            report_date="2026-02-28",
            currency_basis="CNX",
        )
        by_bucket = _persisted_rows(conn, "2026-02-28")
    finally:
        conn.close()

    assert by_bucket["TPL"]["chain_status"] == "broken"
    assert by_bucket["TPL"]["reconciliation_status"] == "chain_broken"


def test_accounting_asset_movement_materialize_refuses_missing_control_source():
    conn = duckdb.connect(":memory:")
    try:
        conn.execute(
            """
            create table product_category_pnl_canonical_fact (
              report_date varchar,
              account_code varchar,
              currency varchar
            )
            """
        )
        conn.execute(
            """
            create table fact_accounting_asset_movement_monthly (
              report_date varchar,
              report_month varchar,
              currency_basis varchar,
              sort_order integer,
              basis_bucket varchar,
              previous_balance decimal(24, 8),
              current_balance decimal(24, 8),
              balance_change decimal(24, 8),
              change_pct decimal(24, 8),
              contribution_pct decimal(24, 8),
              zqtz_amount decimal(24, 8),
              gl_amount decimal(24, 8),
              reconciliation_diff decimal(24, 8),
              reconciliation_status varchar,
              source_version varchar,
              rule_version varchar
            )
            """
        )

        try:
            materialize_accounting_asset_movement_on_connection(
                conn,
                report_date="2026-02-28",
                currency_basis="CNX",
            )
        except AccountingAssetMovementSourceMissingError:
            pass
        else:
            raise AssertionError("expected missing source rows to fail closed")

        row_count = conn.execute(
            "select count(*) from fact_accounting_asset_movement_monthly"
        ).fetchone()[0]
    finally:
        conn.close()

    assert row_count == 0


def test_task_owned_refresh_fails_closed_when_cutover_disabled(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_MOVEMENT_REFRESH_VIA_TASK", "0")

    with pytest.raises(RuntimeError, match="disabled"):
        movement_task.refresh_accounting_asset_movement_window.fn(
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
            report_dates=["2026-01-31"],
            anchor_report_date="2026-01-31",
            currency_basis="CNX",
        )


def test_task_owned_refresh_writes_governance_runs_and_manifests_for_each_report_date(
    tmp_path,
):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    report_dates = ["2026-01-31", "2026-02-28"]
    _seed_refresh_sources(duckdb_path, report_dates)

    payload = movement_task.refresh_accounting_asset_movement_window.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_dates=report_dates,
        anchor_report_date="2026-02-28",
        currency_basis="CNX",
        product_category_refreshed_dates=["2026-01-31"],
        formal_balance_refreshed_dates=["2026-02-28"],
    )

    assert payload["status"] == "completed"
    assert payload["report_date"] == "2026-02-28"
    assert payload["job_name"] == "accounting_asset_movement_refresh"
    assert payload["movement_refreshed_dates"] == report_dates
    assert payload["payloads_by_date"]["2026-02-28"]["row_count"] == 3

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        rows = conn.execute(
            """
            select cast(report_date as varchar), count(*)
            from fact_accounting_asset_movement_monthly
            group by 1
            order by 1
            """
        ).fetchall()
    finally:
        conn.close()

    assert rows == [("2026-01-31", 3), ("2026-02-28", 3)]

    governance_repo = GovernanceRepository(base_dir=governance_dir)
    build_runs = [
        row
        for row in governance_repo.read_all(CACHE_BUILD_RUN_STREAM)
        if row.get("run_id") == payload["run_id"]
    ]
    manifests = [
        row
        for row in governance_repo.read_all(CACHE_MANIFEST_STREAM)
        if row.get("run_id") == payload["run_id"]
    ]

    assert [row["status"] for row in build_runs] == ["queued", "running", "completed"]
    assert [row["job_name"] for row in build_runs] == [
        "accounting_asset_movement_refresh",
        "accounting_asset_movement_refresh",
        "accounting_asset_movement_refresh",
    ]
    assert sorted(row["report_date"] for row in manifests) == report_dates
    assert all(row["cache_key"] == movement_task.CACHE_KEY for row in manifests)
    assert all(row["cache_version"] == movement_task.CACHE_VERSION for row in manifests)
    assert all(row["fact_tables"] == ["fact_accounting_asset_movement_monthly"] for row in manifests)
    assert all(row["rule_version"] == movement_task.RULE_VERSION for row in manifests)
    assert manifests[0]["lineage"]["movement_refreshed_dates"] == report_dates
    assert manifests[0]["lineage"]["product_category_refreshed_dates"] == ["2026-01-31"]
    assert manifests[0]["lineage"]["formal_balance_refreshed_dates"] == ["2026-02-28"]


def test_task_owned_refresh_records_reconciliation_control_evidence_in_lineage(tmp_path):
    """逐行结论落在 chain_status / position_source_basis 列上；lineage 里保留
    同一批次的汇总，方便按 run_id 复盘。"""
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    report_dates = ["2026-01-31", "2026-02-28"]
    _seed_refresh_sources(duckdb_path, report_dates)

    payload = movement_task.refresh_accounting_asset_movement_window.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_dates=report_dates,
        anchor_report_date="2026-02-28",
        currency_basis="CNX",
    )

    control_by_date = payload["reconciliation_control_by_date"]
    february = control_by_date["2026-02-28"]
    assert february["gate_mode"] == "warn"
    # 没有独立头寸源 -> 3 个桶全部 gl_only，一个 matched 都不能有。
    assert february["status_counts"] == {"gl_only": 3}
    assert february["unmatched_row_count"] == 3
    # 期初 (TPL 100 / AC 205 / OCI 70) vs 上月期末 (110 / 225 / 80)。
    assert february["chain_prior_report_date"] == "2026-01-31"
    assert february["chain_gaps"] == {
        "TPL": "-10.00000000",
        "AC": "-20.00000000",
        "OCI": "-10.00000000",
    }
    assert february["chain_status_counts"] == {"broken": 3}
    assert february["position_source_bases"] == ["unavailable"]

    manifests = [
        row
        for row in GovernanceRepository(base_dir=governance_dir).read_all(CACHE_MANIFEST_STREAM)
        if row.get("report_date") == "2026-02-28"
    ]
    assert manifests[-1]["lineage"]["reconciliation_control"] == february


def test_task_owned_refresh_holds_global_duckdb_writer_lock(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    _seed_refresh_sources(duckdb_path, ["2026-02-28"])

    materialize_mod = importlib.import_module("backend.app.tasks.materialize")
    locks_mod = importlib.import_module("backend.app.governance.locks")
    writer_lock = materialize_mod.resolve_materialize_lock(duckdb_path)
    observed = {"contention_checked": False}
    original_materialize = movement_task.materialize_accounting_asset_movement_on_connection

    def materialize_under_lock(conn, *, report_date: str, currency_basis: str = "CNX"):
        with pytest.raises(TimeoutError):
            with locks_mod.acquire_lock(
                writer_lock,
                base_dir=duckdb_path.parent,
                timeout_seconds=0.01,
            ):
                pass
        observed["contention_checked"] = True
        return original_materialize(conn, report_date=report_date, currency_basis=currency_basis)

    monkeypatch.setattr(
        movement_task,
        "materialize_accounting_asset_movement_on_connection",
        materialize_under_lock,
    )

    payload = movement_task.refresh_accounting_asset_movement_window.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_dates=["2026-02-28"],
        anchor_report_date="2026-02-28",
        currency_basis="CNX",
    )

    assert payload["status"] == "completed"
    assert payload["lock"].startswith(movement_task.ACCOUNTING_ASSET_MOVEMENT_REFRESH_LOCK.key)
    assert observed["contention_checked"] is True


def test_task_owned_refresh_materializes_missing_product_category_before_movement(
    tmp_path,
    monkeypatch,
):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    report_dates = ["2026-01-31", "2026-02-28"]
    _seed_refresh_sources(duckdb_path, report_dates)
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute("delete from product_category_pnl_canonical_fact")
    finally:
        conn.close()
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "product-category-202601.xlsx").write_bytes(b"placeholder")
    (source_dir / "product-category-202602.xlsx").write_bytes(b"placeholder")

    events: list[tuple[str, object]] = []

    def fake_product_category_refresh(**kwargs):
        events.append(("product", kwargs["source_dir"]))
        _seed_product_category_control_rows(duckdb_path, report_dates)
        return {"status": "completed"}

    original_materialize = movement_task.materialize_accounting_asset_movement_on_connection

    def tracked_materialize(conn, *, report_date: str, currency_basis: str = "CNX"):
        events.append(("movement", report_date))
        return original_materialize(conn, report_date=report_date, currency_basis=currency_basis)

    monkeypatch.setattr(movement_task, "materialize_product_category_pnl_sync", fake_product_category_refresh)
    monkeypatch.setattr(movement_task, "materialize_accounting_asset_movement_on_connection", tracked_materialize)

    payload = movement_task.refresh_accounting_asset_movement_window.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_dates=report_dates,
        anchor_report_date="2026-02-28",
        currency_basis="CNX",
        product_category_source_dir=str(source_dir),
    )

    assert payload["product_category_refreshed_dates"] == report_dates
    assert events[:3] == [
        ("product", str(source_dir)),
        ("movement", "2026-01-31"),
        ("movement", "2026-02-28"),
    ]


def test_task_owned_refresh_rematerializes_stale_zqtz_formal_before_movement(
    tmp_path,
    monkeypatch,
):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    report_dates = ["2026-01-31", "2026-02-28"]
    _seed_refresh_sources(duckdb_path, report_dates)
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_formal_zqtz_balance_daily (
              report_date varchar,
              instrument_code varchar,
              portfolio_name varchar,
              cost_center varchar,
              maturity_date varchar,
              accounting_basis varchar,
              position_scope varchar,
              currency_basis varchar,
              business_type_primary varchar,
              market_value_amount decimal(24, 8),
              amortized_cost_amount decimal(24, 8),
              source_version varchar,
              rule_version varchar
            )
            """
        )
        conn.executemany(
            """
            insert into fact_formal_zqtz_balance_daily (
              report_date, accounting_basis, position_scope, currency_basis,
              business_type_primary, market_value_amount, amortized_cost_amount,
              source_version, rule_version
            ) values (?, ?, 'asset', 'CNY', ?, ?, ?, 'sv-zqtz', 'rv-zqtz')
            """,
            [
                ("2026-01-31", "FVTPL", "", "110", "0"),
                ("2026-01-31", "AC", "", "0", "220"),
                ("2026-01-31", "FVOCI", "", "80", "0"),
                ("2026-02-28", "FVTPL", "fresh", "110", "0"),
                ("2026-02-28", "AC", "fresh", "0", "220"),
                ("2026-02-28", "FVOCI", "fresh", "80", "0"),
            ],
        )
        conn.execute(
            """
            update fact_formal_zqtz_balance_daily
            set business_type_primary = ''
            where report_date = '2026-01-31'
            """
        )
    finally:
        conn.close()
    data_root = tmp_path / "data_input"
    data_root.mkdir()
    (data_root / "ZQTZSHOW-20260131.xls").write_bytes(b"placeholder")

    events: list[tuple[str, object]] = []

    def fake_formal_pipeline(**kwargs):
        events.append(("formal", kwargs["report_date"]))
        conn = duckdb.connect(str(duckdb_path), read_only=False)
        try:
            conn.execute(
                """
                update fact_formal_zqtz_balance_daily
                set business_type_primary = 'fresh'
                where report_date = ?
                """,
                [kwargs["report_date"]],
            )
        finally:
            conn.close()
        return {"status": "completed", "report_date": kwargs["report_date"]}

    original_materialize = movement_task.materialize_accounting_asset_movement_on_connection

    def tracked_materialize(conn, *, report_date: str, currency_basis: str = "CNX"):
        events.append(("movement", report_date))
        return original_materialize(conn, report_date=report_date, currency_basis=currency_basis)

    monkeypatch.setattr(movement_task, "run_formal_balance_pipeline_sync", fake_formal_pipeline)
    monkeypatch.setattr(movement_task, "materialize_accounting_asset_movement_on_connection", tracked_materialize)

    payload = movement_task.refresh_accounting_asset_movement_window.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_dates=report_dates,
        anchor_report_date="2026-02-28",
        currency_basis="CNX",
        data_root=str(data_root),
        fx_source_path="test-output/fx.csv",
    )

    assert payload["formal_balance_refreshed_dates"] == ["2026-01-31"]
    assert events[:3] == [
        ("formal", "2026-01-31"),
        ("movement", "2026-01-31"),
        ("movement", "2026-02-28"),
    ]


def test_task_owned_refresh_rolls_back_all_target_dates_and_writes_failed_run_only(
    tmp_path,
    monkeypatch,
):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    report_dates = ["2026-01-31", "2026-02-28"]
    _seed_refresh_sources(duckdb_path, report_dates)

    original_materialize = movement_task.materialize_accounting_asset_movement_on_connection

    def fail_on_second_date(conn, *, report_date: str, currency_basis: str = "CNX"):
        if report_date == "2026-02-28":
            raise RuntimeError("movement window exploded")
        return original_materialize(
            conn,
            report_date=report_date,
            currency_basis=currency_basis,
        )

    monkeypatch.setattr(
        movement_task,
        "materialize_accounting_asset_movement_on_connection",
        fail_on_second_date,
    )

    with pytest.raises(RuntimeError, match="movement window exploded"):
        movement_task.refresh_accounting_asset_movement_window.fn(
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
            report_dates=report_dates,
            anchor_report_date="2026-02-28",
            currency_basis="CNX",
        )

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        table_exists = conn.execute(
            """
            select count(*)
            from information_schema.tables
            where table_name = 'fact_accounting_asset_movement_monthly'
            """
        ).fetchone()[0]
        row_count = (
            conn.execute(
                """
                select count(*)
                from fact_accounting_asset_movement_monthly
                where cast(report_date as varchar) in ('2026-01-31', '2026-02-28')
                """
            ).fetchone()[0]
            if table_exists
            else 0
        )
    finally:
        conn.close()

    assert row_count == 0

    governance_repo = GovernanceRepository(base_dir=governance_dir)
    build_runs = governance_repo.read_all(CACHE_BUILD_RUN_STREAM)
    manifests = governance_repo.read_all(CACHE_MANIFEST_STREAM)
    assert [row["status"] for row in build_runs] == ["queued", "running", "failed"]
    assert build_runs[-1]["error_message"] == "movement window exploded"
    assert manifests == []


def test_task_owned_refresh_marks_lock_failure_without_success_manifest(
    tmp_path,
    monkeypatch,
):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    _seed_refresh_sources(duckdb_path, ["2026-02-28"])

    def fail_lock(*_args, **_kwargs):
        raise TimeoutError("Timed out acquiring lock lock:duckdb:accounting-asset-movement")

    monkeypatch.setattr(movement_task, "acquire_lock", fail_lock)

    with pytest.raises(TimeoutError, match="Timed out acquiring lock"):
        movement_task.refresh_accounting_asset_movement_window.fn(
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
            report_dates=["2026-02-28"],
            anchor_report_date="2026-02-28",
            currency_basis="CNX",
        )

    governance_repo = GovernanceRepository(base_dir=governance_dir)
    build_runs = governance_repo.read_all(CACHE_BUILD_RUN_STREAM)
    manifests = governance_repo.read_all(CACHE_MANIFEST_STREAM)
    assert [row["status"] for row in build_runs] == ["queued", "running", "failed"]
    assert "Timed out acquiring lock" in str(build_runs[-1]["error_message"])
    assert manifests == []


def _seed_refresh_sources(duckdb_path: Path, report_dates: list[str]) -> None:
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table product_category_pnl_canonical_fact (
              report_date varchar,
              account_code varchar,
              currency varchar,
              account_name varchar,
              beginning_balance decimal(24, 8),
              ending_balance decimal(24, 8),
              monthly_pnl decimal(24, 8),
              daily_avg_balance decimal(24, 8),
              annual_avg_balance decimal(24, 8),
              days_in_period integer,
              source_version varchar,
              rule_version varchar
            )
            """
        )
        rows: list[tuple[object, ...]] = []
        for report_date in report_dates:
            rows.extend(
                [
                    (
                        report_date,
                        "14101010001",
                        "CNX",
                        "TPL",
                        "100",
                        "110",
                        "0",
                        "0",
                        "0",
                        28,
                        f"sv-gl-{report_date}",
                        f"rv-gl-{report_date}",
                    ),
                    (
                        report_date,
                        "14201010001",
                        "CNX",
                        "AC bond",
                        "200",
                        "220",
                        "0",
                        "0",
                        "0",
                        28,
                        f"sv-gl-{report_date}",
                        f"rv-gl-{report_date}",
                    ),
                    (
                        report_date,
                        "14301010001",
                        "CNX",
                        "Voucher bond",
                        "4",
                        "4",
                        "0",
                        "0",
                        "0",
                        28,
                        f"sv-gl-{report_date}",
                        f"rv-gl-{report_date}",
                    ),
                    (
                        report_date,
                        "14301010002",
                        "CNX",
                        "Voucher accrued",
                        "1",
                        "1",
                        "0",
                        "0",
                        "0",
                        28,
                        f"sv-gl-{report_date}",
                        f"rv-gl-{report_date}",
                    ),
                    (
                        report_date,
                        "14401010001",
                        "CNX",
                        "OCI debt",
                        "70",
                        "80",
                        "0",
                        "0",
                        "0",
                        28,
                        f"sv-gl-{report_date}",
                        f"rv-gl-{report_date}",
                    ),
                ]
            )
        conn.executemany(
            "insert into product_category_pnl_canonical_fact values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
    finally:
        conn.close()


def _seed_product_category_control_rows(duckdb_path: Path, report_dates: list[str]) -> None:
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        rows: list[tuple[object, ...]] = []
        for report_date in report_dates:
            rows.extend(
                [
                    (
                        report_date,
                        "14101010001",
                        "CNX",
                        "TPL",
                        "100",
                        "110",
                        "0",
                        "0",
                        "0",
                        28,
                        "sv-gl",
                        "rv-gl",
                    ),
                    (
                        report_date,
                        "14201010001",
                        "CNX",
                        "AC",
                        "200",
                        "220",
                        "0",
                        "0",
                        "0",
                        28,
                        "sv-gl",
                        "rv-gl",
                    ),
                    (
                        report_date,
                        "14401010001",
                        "CNX",
                        "OCI",
                        "70",
                        "80",
                        "0",
                        "0",
                        "0",
                        28,
                        "sv-gl",
                        "rv-gl",
                    ),
                ]
            )
        conn.executemany(
            "insert into product_category_pnl_canonical_fact values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
    finally:
        conn.close()
