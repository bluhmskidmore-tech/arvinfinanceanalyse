from __future__ import annotations

import json
import sys
from decimal import Decimal

import duckdb
import pytest

from tests.helpers import load_module


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


def _seed_snapshot_and_fx_tables(duckdb_path: str) -> None:
    snapshot_mod = sys.modules.get("backend.app.repositories.snapshot_repo")
    if snapshot_mod is None:
        snapshot_mod = load_module(
            "backend.app.repositories.snapshot_repo",
            "backend/app/repositories/snapshot_repo.py",
        )

    conn = duckdb.connect(duckdb_path, read_only=False)
    try:
        snapshot_mod.ensure_snapshot_tables(conn)
        conn.execute(
            """
            create table if not exists fx_daily_mid (
              trade_date date,
              base_currency varchar,
              quote_currency varchar,
              mid_rate decimal(24, 8),
              source_name varchar,
              is_business_day boolean,
              is_carry_forward boolean,
              source_version varchar
            )
            """
        )
        conn.execute(
            """
            insert into zqtz_bond_daily_snapshot (
              report_date, instrument_code, instrument_name, portfolio_name, cost_center,
              account_category, asset_class, bond_type, issuer_name, industry_name, rating,
              currency_code, face_value_native, market_value_native, amortized_cost_native,
              accrued_interest_native, coupon_rate, ytm_value, maturity_date, next_call_date,
              overdue_days, is_issuance_like, interest_mode, source_version, rule_version,
              ingest_batch_id, trace_id
            ) values (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                "2025-12-31",
                "240001.IB",
                "债券A",
                "组合A",
                "CC100",
                "可供出售债券",
                "债券类",
                "国债",
                "发行人A",
                "主权",
                "AAA",
                "USD",
                Decimal("100"),
                Decimal("100"),
                Decimal("90"),
                Decimal("5"),
                Decimal("0.025"),
                Decimal("0.03"),
                "2027-12-31",
                None,
                0,
                False,
                "固定",
                "sv-z-1",
                "rv-snap-1",
                "ib-z-1",
                "trace-z-1",
            ],
        )
        conn.execute(
            """
            insert into tyw_interbank_daily_snapshot (
              report_date, position_id, product_type, position_side, counterparty_name,
              account_type, special_account_type, core_customer_type, currency_code,
              principal_native, accrued_interest_native, funding_cost_rate, maturity_date,
              pledged_bond_code, source_version, rule_version, ingest_batch_id, trace_id
            ) values (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                "2025-12-31",
                "pos-1",
                "持有至到期同业存单",
                "liability",
                "银行A",
                "负债账户",
                "一般",
                "股份制银行",
                "USD",
                Decimal("10"),
                Decimal("2"),
                Decimal("0.015"),
                "2026-06-30",
                None,
                "sv-t-1",
                "rv-snap-1",
                "ib-t-1",
                "trace-t-1",
            ],
        )
        conn.execute(
            """
            insert into fx_daily_mid values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "2025-12-31",
                "USD",
                "CNY",
                Decimal("7.2"),
                "CFETS",
                True,
                False,
                "sv-fx-1",
            ],
        )
    finally:
        conn.close()


def test_balance_analysis_materialize_writes_formal_fact_tables_and_governance_records(tmp_path):
    repo_mod, task_mod = _load_modules()

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    _seed_snapshot_and_fx_tables(str(duckdb_path))

    payload = task_mod.materialize_balance_analysis_facts.fn(
        report_date="2025-12-31",
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    assert payload["status"] == "completed"
    assert payload["report_date"] == "2025-12-31"
    assert payload["zqtz_rows"] == 2
    assert payload["tyw_rows"] == 2

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        zqtz_rows = conn.execute(
            """
            select report_date, instrument_code, invest_type_std, accounting_basis,
                   position_scope, currency_basis, market_value_amount, source_version
            from fact_formal_zqtz_balance_daily
            order by currency_basis
            """
        ).fetchall()
        tyw_rows = conn.execute(
            """
            select report_date, position_id, invest_type_std, accounting_basis,
                   position_scope, currency_basis, principal_amount, source_version
            from fact_formal_tyw_balance_daily
            order by currency_basis
            """
        ).fetchall()
    finally:
        conn.close()

    assert zqtz_rows == [
        ("2025-12-31", "240001.IB", "A", "FVOCI", "asset", "CNY", Decimal("720.00000000"), "sv-z-1"),
        ("2025-12-31", "240001.IB", "A", "FVOCI", "asset", "native", Decimal("100.00000000"), "sv-z-1"),
    ]
    assert tyw_rows == [
        ("2025-12-31", "pos-1", "H", "AC", "liability", "CNY", Decimal("72.00000000"), "sv-t-1"),
        ("2025-12-31", "pos-1", "H", "AC", "liability", "native", Decimal("10.00000000"), "sv-t-1"),
    ]

    repo = repo_mod.BalanceAnalysisRepository(str(duckdb_path))
    assert repo.list_report_dates() == ["2025-12-31"]

    build_runs = [
        json.loads(line)
        for line in (governance_dir / "cache_build_run.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    manifests = [
        json.loads(line)
        for line in (governance_dir / "cache_manifest.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert build_runs[0]["status"] == "running"
    assert build_runs[0]["started_at"]
    assert build_runs[-1]["status"] == "completed"
    assert build_runs[-1]["cache_key"] == task_mod.CACHE_KEY
    assert manifests[-1]["cache_key"] == task_mod.CACHE_KEY
    assert manifests[-1]["rule_version"] == task_mod.RULE_VERSION


def test_balance_analysis_materialize_fails_when_required_fx_rate_is_missing(tmp_path):
    _repo_mod, task_mod = _load_modules()

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    _seed_snapshot_and_fx_tables(str(duckdb_path))

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute("delete from fx_daily_mid")
    finally:
        conn.close()

    with pytest.raises(ValueError, match="fx"):
        task_mod.materialize_balance_analysis_facts.fn(
            report_date="2025-12-31",
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
        )


def test_balance_analysis_materialize_preserves_computed_lineage_when_write_fails(tmp_path, monkeypatch):
    repo_mod, task_mod = _load_modules()

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    _seed_snapshot_and_fx_tables(str(duckdb_path))

    def _fail_replace(self, **_kwargs):
        raise RuntimeError("synthetic write failure")

    monkeypatch.setattr(
        repo_mod.BalanceAnalysisRepository,
        "replace_formal_balance_rows",
        _fail_replace,
    )

    with pytest.raises(RuntimeError, match="synthetic write failure"):
        task_mod.materialize_balance_analysis_facts.fn(
            report_date="2025-12-31",
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
        )

    build_runs = [
        json.loads(line)
        for line in (governance_dir / "cache_build_run.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert build_runs[-1]["status"] == "failed"
    assert build_runs[-1]["source_version"] == "sv-fx-1__sv-t-1__sv-z-1"


def test_balance_analysis_materialize_fails_when_only_prior_business_day_fx_exists(tmp_path):
    _repo_mod, task_mod = _load_modules()

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    _seed_snapshot_and_fx_tables(str(duckdb_path))

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute("delete from fx_daily_mid where trade_date = '2025-12-31'")
        conn.execute(
            """
            insert into fx_daily_mid values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "2025-12-30",
                "USD",
                "CNY",
                Decimal("7.1"),
                "CFETS",
                True,
                False,
                "sv-fx-prev",
            ],
        )
    finally:
        conn.close()

    with pytest.raises(ValueError, match="fx"):
        task_mod.materialize_balance_analysis_facts.fn(
            report_date="2025-12-31",
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
        )
