from __future__ import annotations

import logging
import sys
from dataclasses import replace as dataclass_replace
from decimal import Decimal

import duckdb
import pytest

from tests.helpers import load_module

pytestmark = [pytest.mark.integration, pytest.mark.materialize]

_DRIFT_WARNING_MARKER = "native principal drift detected"


def _load_modules():
    repo_mod = sys.modules.get("backend.app.repositories.balance_analysis_repo")
    if repo_mod is None:
        repo_mod = load_module(
            "backend.app.repositories.balance_analysis_repo",
            "backend/app/repositories/balance_analysis_repo.py",
        )
    task_mod = sys.modules.get("backend.app.tasks.balance_analysis_materialize")
    if task_mod is None:
        task_mod = load_module(
            "backend.app.tasks.balance_analysis_materialize",
            "backend/app/tasks/balance_analysis_materialize.py",
        )
    return repo_mod, task_mod


def _create_tyw_tables(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        create table tyw_interbank_daily_snapshot (
          report_date date,
          position_id varchar,
          product_type varchar,
          position_side varchar,
          counterparty_name varchar,
          account_type varchar,
          special_account_type varchar,
          core_customer_type varchar,
          currency_code varchar,
          principal_native decimal(24, 8),
          accrued_interest_native decimal(24, 8),
          funding_cost_rate decimal(18, 8),
          maturity_date date,
          pledged_bond_code varchar,
          source_version varchar,
          rule_version varchar,
          ingest_batch_id varchar,
          trace_id varchar
        )
        """
    )
    conn.execute(
        """
        create table fact_formal_tyw_balance_daily (
          report_date varchar,
          position_id varchar,
          product_type varchar,
          position_side varchar,
          counterparty_name varchar,
          account_type varchar,
          special_account_type varchar,
          core_customer_type varchar,
          invest_type_std varchar,
          accounting_basis varchar,
          position_scope varchar,
          currency_basis varchar,
          currency_code varchar,
          principal_amount decimal(24, 8),
          accrued_interest_amount decimal(24, 8),
          funding_cost_rate decimal(18, 8),
          maturity_date varchar,
          source_version varchar,
          rule_version varchar,
          ingest_batch_id varchar,
          trace_id varchar
        )
        """
    )


def _insert_snapshot_row(
    conn: duckdb.DuckDBPyConnection,
    *,
    report_date: str,
    position_id: str,
    principal: Decimal,
    ingest_batch_id: str = "ib-1",
) -> None:
    conn.execute(
        """
        insert into tyw_interbank_daily_snapshot (
          report_date, position_id, product_type, position_side, counterparty_name,
          account_type, special_account_type, core_customer_type, currency_code,
          principal_native, accrued_interest_native, funding_cost_rate, maturity_date,
          pledged_bond_code, source_version, rule_version, ingest_batch_id, trace_id
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            report_date, position_id, "持有至到期同业存单", "liability", "银行A",
            "负债账户", "一般", "股份制银行", "CNY",
            principal, Decimal("1"), Decimal("0.015"), "2026-06-30",
            None, "sv-t-1", "rv-snap-1", ingest_batch_id, f"trace-{position_id}",
        ],
    )


def _insert_fact_row(
    conn: duckdb.DuckDBPyConnection,
    *,
    report_date: str,
    position_id: str,
    currency_basis: str,
    principal: Decimal,
) -> None:
    conn.execute(
        """
        insert into fact_formal_tyw_balance_daily (
          report_date, position_id, product_type, position_side, counterparty_name,
          account_type, special_account_type, core_customer_type, invest_type_std,
          accounting_basis, position_scope, currency_basis, currency_code, principal_amount,
          accrued_interest_amount, funding_cost_rate, maturity_date, source_version,
          rule_version, ingest_batch_id, trace_id
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            report_date, position_id, "持有至到期同业存单", "liability", "银行A",
            "负债账户", "一般", "股份制银行", "H",
            "AC", "liability", currency_basis, "CNY", principal,
            Decimal("1"), Decimal("0.015"), "2026-06-30", "sv-t-1",
            "rv-1", "ib-1", f"trace-{position_id}",
        ],
    )


def test_batch_consistency_reports_drift_days_and_ignores_cny_basis_rows(tmp_path) -> None:
    repo_mod, task_mod = _load_modules()
    db_path = tmp_path / "tyw_consistency.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _create_tyw_tables(conn)
        # 2026-01-05：一致（fact 侧另有 CNY basis 行，必须被排除在核对之外）。
        _insert_snapshot_row(conn, report_date="2026-01-05", position_id="pos-a", principal=Decimal("100"))
        _insert_snapshot_row(conn, report_date="2026-01-05", position_id="pos-b", principal=Decimal("50"))
        _insert_fact_row(conn, report_date="2026-01-05", position_id="pos-a", currency_basis="native", principal=Decimal("100"))
        _insert_fact_row(conn, report_date="2026-01-05", position_id="pos-b", currency_basis="native", principal=Decimal("50"))
        _insert_fact_row(conn, report_date="2026-01-05", position_id="pos-a", currency_basis="CNY", principal=Decimal("720"))
        _insert_fact_row(conn, report_date="2026-01-05", position_id="pos-b", currency_basis="CNY", principal=Decimal("360"))
        # 2026-01-06：漂移（snapshot 150 vs fact native 60）。
        _insert_snapshot_row(conn, report_date="2026-01-06", position_id="pos-a", principal=Decimal("100"))
        _insert_snapshot_row(conn, report_date="2026-01-06", position_id="pos-b", principal=Decimal("50"))
        _insert_fact_row(conn, report_date="2026-01-06", position_id="pos-a", currency_basis="native", principal=Decimal("60"))
        # 2026-01-07：差 0.005 元，在 0.01 容差内。
        _insert_snapshot_row(conn, report_date="2026-01-07", position_id="pos-a", principal=Decimal("100.000"))
        _insert_fact_row(conn, report_date="2026-01-07", position_id="pos-a", currency_basis="native", principal=Decimal("100.005"))
    finally:
        conn.close()

    repo = repo_mod.BalanceAnalysisRepository(str(db_path))
    rows = repo.fetch_tyw_snapshot_fact_native_consistency_rows()
    assert [row["report_date"] for row in rows] == ["2026-01-05", "2026-01-06", "2026-01-07"]
    day_1, day_2, day_3 = rows
    assert day_1["snapshot_row_count"] == 2
    assert day_1["fact_native_row_count"] == 2
    assert day_1["principal_native_diff"] == Decimal("0")
    assert day_2["snapshot_principal_native_total"] == Decimal("150")
    assert day_2["fact_principal_native_total"] == Decimal("60")
    assert day_2["principal_native_diff"] == Decimal("-90")
    assert day_3["principal_native_diff"] == Decimal("0.005")

    entries = task_mod.check_tyw_snapshot_fact_consistency(duckdb_path=str(db_path))
    assert [(entry["report_date"], entry["status"]) for entry in entries] == [
        ("2026-01-05", "consistent"),
        ("2026-01-06", "drift"),
        ("2026-01-07", "consistent"),
    ]
    drift_entry = entries[1]
    assert Decimal(drift_entry["principal_native_diff"]) == Decimal("-90")
    assert Decimal(drift_entry["snapshot_principal_native_total"]) == Decimal("150")
    assert Decimal(drift_entry["fact_principal_native_total"]) == Decimal("60")
    assert drift_entry["tolerance"] == "0.01"


def test_batch_consistency_emits_zero_entry_for_explicitly_requested_empty_date(tmp_path) -> None:
    _repo_mod, task_mod = _load_modules()
    db_path = tmp_path / "tyw_consistency_empty.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _create_tyw_tables(conn)
    finally:
        conn.close()

    entries = task_mod.check_tyw_snapshot_fact_consistency(
        duckdb_path=str(db_path),
        report_dates=["2026-03-31"],
    )
    assert entries == [
        {
            "report_date": "2026-03-31",
            "status": "consistent",
            "snapshot_row_count": 0,
            "fact_native_row_count": 0,
            "snapshot_principal_native_total": "0",
            "fact_principal_native_total": "0",
            "principal_native_diff": "0",
            "tolerance": "0.01",
        }
    ]


def test_repo_consistency_scopes_snapshot_side_to_ingest_batch_id(tmp_path) -> None:
    repo_mod, _task_mod = _load_modules()
    db_path = tmp_path / "tyw_consistency_batch.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _create_tyw_tables(conn)
        _insert_snapshot_row(conn, report_date="2026-01-06", position_id="pos-a", principal=Decimal("150"), ingest_batch_id="ib-1")
        _insert_snapshot_row(conn, report_date="2026-01-06", position_id="pos-x", principal=Decimal("999"), ingest_batch_id="ib-x")
        _insert_fact_row(conn, report_date="2026-01-06", position_id="pos-a", currency_basis="native", principal=Decimal("150"))
    finally:
        conn.close()

    repo = repo_mod.BalanceAnalysisRepository(str(db_path))
    scoped = repo.fetch_tyw_snapshot_fact_native_consistency_rows(
        report_dates=["2026-01-06"],
        snapshot_ingest_batch_id="ib-1",
    )
    assert scoped[0]["snapshot_principal_native_total"] == Decimal("150")
    assert scoped[0]["principal_native_diff"] == Decimal("0")

    unscoped = repo.fetch_tyw_snapshot_fact_native_consistency_rows(report_dates=["2026-01-06"])
    assert unscoped[0]["snapshot_principal_native_total"] == Decimal("1149")
    assert unscoped[0]["principal_native_diff"] == Decimal("-999")


def _seed_materialize_snapshot(duckdb_path: str, *, report_date: str) -> None:
    snapshot_mod = sys.modules.get("backend.app.repositories.snapshot_repo")
    if snapshot_mod is None:
        snapshot_mod = load_module(
            "backend.app.repositories.snapshot_repo",
            "backend/app/repositories/snapshot_repo.py",
        )
    conn = duckdb.connect(duckdb_path, read_only=False)
    try:
        snapshot_mod.ensure_snapshot_tables(conn)
        _insert_snapshot_row(conn, report_date=report_date, position_id="pos-1", principal=Decimal("100"), ingest_batch_id="ib-t-1")
    finally:
        conn.close()


def test_materialize_reports_consistent_snapshot_fact_metadata_without_warning(tmp_path, caplog) -> None:
    _repo_mod, task_mod = _load_modules()
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    _seed_materialize_snapshot(str(duckdb_path), report_date="2026-02-10")

    with caplog.at_level(logging.WARNING, logger="backend.app.tasks.balance_analysis_materialize"):
        payload = task_mod.materialize_balance_analysis_facts.fn(
            report_date="2026-02-10",
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
            use_existing_fx_only=True,
        )

    assert payload["status"] == "completed"
    assert payload["tyw_rows"] == 2  # native + CNY
    meta = payload["tyw_snapshot_fact_consistency"]
    assert meta["status"] == "consistent"
    assert meta["report_date"] == "2026-02-10"
    assert meta["snapshot_row_count"] == 1
    assert meta["fact_native_row_count"] == 1
    assert Decimal(meta["principal_native_diff"]) == Decimal("0")
    assert not [record for record in caplog.records if _DRIFT_WARNING_MARKER in record.getMessage()]


def test_materialize_warns_and_exposes_drift_metadata_when_fact_diverges_from_snapshot(
    tmp_path,
    monkeypatch,
    caplog,
) -> None:
    _repo_mod, task_mod = _load_modules()
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    _seed_materialize_snapshot(str(duckdb_path), report_date="2026-02-10")

    real_project = task_mod.project_tyw_formal_balance_row

    def _drifting_project(row, **kwargs):
        fact_row = real_project(row, **kwargs)
        if kwargs.get("currency_basis") == "native":
            return dataclass_replace(fact_row, principal_amount=fact_row.principal_amount + Decimal("5"))
        return fact_row

    monkeypatch.setattr(task_mod, "project_tyw_formal_balance_row", _drifting_project)

    with caplog.at_level(logging.WARNING, logger="backend.app.tasks.balance_analysis_materialize"):
        payload = task_mod.materialize_balance_analysis_facts.fn(
            report_date="2026-02-10",
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
            use_existing_fx_only=True,
        )

    # 漂移只告警并暴露元数据，物化本身不失败、不自动重物化。
    assert payload["status"] == "completed"
    meta = payload["tyw_snapshot_fact_consistency"]
    assert meta["status"] == "drift"
    assert Decimal(meta["snapshot_principal_native_total"]) == Decimal("100")
    assert Decimal(meta["fact_principal_native_total"]) == Decimal("105")
    assert Decimal(meta["principal_native_diff"]) == Decimal("5")

    drift_records = [record for record in caplog.records if _DRIFT_WARNING_MARKER in record.getMessage()]
    assert len(drift_records) == 1
    assert "2026-02-10" in drift_records[0].getMessage()
