from __future__ import annotations

import json
from decimal import Decimal

import pytest

from tests.helpers import load_module
from tests.test_bond_analytics_materialize_flow import REPORT_DATE, _seed_bond_snapshot_rows


def _read_jsonl(path):
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _configure_upstream(tmp_path):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    _seed_bond_snapshot_rows(str(duckdb_path))
    bond_task_mod = load_module(
        "backend.app.tasks.bond_analytics_materialize",
        "backend/app/tasks/bond_analytics_materialize.py",
    )
    bond_task_mod.materialize_bond_analytics_facts.fn(
        report_date=REPORT_DATE,
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )
    return duckdb_path, governance_dir, bond_task_mod


def _configure_upstream_with_semiannual_coupon(tmp_path):
    duckdb_path = tmp_path / "moss.semiannual.duckdb"
    governance_dir = tmp_path / "governance.semiannual"
    _seed_bond_snapshot_rows(str(duckdb_path))

    import duckdb

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            update zqtz_bond_daily_snapshot
            set maturity_date = ?, coupon_rate = ?, interest_mode = ?, next_call_date = ?
            where report_date = ?
              and instrument_code = 'CB-001'
            """,
            ["2028-12-15", "0.08", "semi-annual", "2026-05-15", REPORT_DATE],
        )
    finally:
        conn.close()

    bond_task_mod = load_module(
        "backend.app.tasks.bond_analytics_materialize",
        "backend/app/tasks/bond_analytics_materialize.py",
    )
    bond_task_mod.materialize_bond_analytics_facts.fn(
        report_date=REPORT_DATE,
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )
    return duckdb_path, governance_dir, bond_task_mod


def test_risk_tensor_materialize_writes_fact_and_governance_records(tmp_path):
    duckdb_path, governance_dir, bond_task_mod = _configure_upstream(tmp_path)
    risk_task_mod = load_module(
        "backend.app.tasks.risk_tensor_materialize",
        "backend/app/tasks/risk_tensor_materialize.py",
    )
    repo_mod = load_module(
        "backend.app.repositories.risk_tensor_repo",
        "backend/app/repositories/risk_tensor_repo.py",
    )

    payload = risk_task_mod.materialize_risk_tensor_facts.fn(
        report_date=REPORT_DATE,
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    row = repo_mod.RiskTensorRepository(str(duckdb_path)).fetch_risk_tensor_row(REPORT_DATE)
    build_runs = _read_jsonl(governance_dir / "cache_build_run.jsonl")
    manifests = _read_jsonl(governance_dir / "cache_manifest.jsonl")

    assert payload["status"] == "completed"
    assert payload["cache_key"] == risk_task_mod.CACHE_KEY
    assert payload["rule_version"] == risk_task_mod.RULE_VERSION
    assert payload["source_version"] == "sv_risk_tensor__sv_bond_snap_1"
    assert payload["payload"]["run"]["status"] == "completed"
    assert payload["payload"]["lineage"]["module_name"] == "risk_tensor"
    assert payload["payload"]["lineage"]["basis"] == "formal"
    assert payload["payload"]["lineage"]["source_version"] == payload["source_version"]
    assert payload["payload"]["lineage"]["rule_version"] == payload["rule_version"]
    assert payload["payload"]["lineage"]["vendor_version"] == payload["vendor_version"]
    assert payload["payload"]["result"]["bond_count"] == 3
    assert row is not None
    assert row["source_version"] == "sv_risk_tensor__sv_bond_snap_1"
    assert row["upstream_source_version"] == "sv_bond_snap_1"
    assert row["cache_version"] == risk_task_mod.CACHE_VERSION
    assert row["bond_count"] == 3
    assert row["asset_cashflow_30d"] == row["liquidity_gap_30d"]
    assert row["asset_cashflow_90d"] == row["liquidity_gap_90d"]
    assert row["liability_cashflow_30d"] == 0
    assert row["liability_cashflow_90d"] == 0
    assert row["liquidity_gap_30d"] == row["asset_cashflow_30d"] - row["liability_cashflow_30d"]
    assert any(record["cache_key"] == bond_task_mod.CACHE_KEY for record in build_runs)
    assert any(record["cache_key"] == risk_task_mod.CACHE_KEY and record["status"] == "completed" for record in build_runs)
    assert any(record["cache_key"] == risk_task_mod.CACHE_KEY and record["cache_version"] == risk_task_mod.CACHE_VERSION for record in manifests)


def test_risk_tensor_materialize_requires_completed_upstream_lineage(tmp_path):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    risk_task_mod = load_module(
        "backend.app.tasks.risk_tensor_materialize",
        "backend/app/tasks/risk_tensor_materialize.py",
    )

    with pytest.raises(RuntimeError, match="requires completed bond_analytics lineage"):
        risk_task_mod.materialize_risk_tensor_facts.fn(
            report_date=REPORT_DATE,
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
        )


def test_risk_tensor_materialize_fails_closed_on_pct_style_bond_rates(tmp_path):
    duckdb_path, governance_dir, _bond_task_mod = _configure_upstream(tmp_path)
    risk_task_mod = load_module(
        "backend.app.tasks.risk_tensor_materialize",
        "backend/app/tasks/risk_tensor_materialize.py",
    )

    import duckdb

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            update fact_formal_bond_analytics_daily
            set coupon_rate = ?
            where report_date = ?
              and instrument_code = 'CB-001'
            """,
            ["2.5", REPORT_DATE],
        )
    finally:
        conn.close()

    with pytest.raises(RuntimeError, match="decimal-form bond analytics rates"):
        risk_task_mod.materialize_risk_tensor_facts.fn(
            report_date=REPORT_DATE,
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
        )


def test_risk_tensor_materialize_preserves_computed_source_version_when_write_fails(tmp_path, monkeypatch):
    duckdb_path, governance_dir, _bond_task_mod = _configure_upstream(tmp_path)
    risk_task_mod = load_module(
        "backend.app.tasks.risk_tensor_materialize",
        "backend/app/tasks/risk_tensor_materialize.py",
    )
    def _fail_replace(self, **_kwargs):
        raise RuntimeError("synthetic risk tensor write failure")

    monkeypatch.setattr(
        risk_task_mod.RiskTensorRepository,
        "replace_risk_tensor_row",
        _fail_replace,
    )

    with pytest.raises(RuntimeError, match="synthetic risk tensor write failure"):
        risk_task_mod.materialize_risk_tensor_facts.fn(
            report_date=REPORT_DATE,
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
        )

    build_runs = _read_jsonl(governance_dir / "cache_build_run.jsonl")
    risk_runs = [row for row in build_runs if row["cache_key"] == risk_task_mod.CACHE_KEY]
    assert risk_runs[-1]["status"] == "failed"
    assert risk_runs[-1]["source_version"] == "sv_risk_tensor__sv_bond_snap_1"
    assert risk_runs[-1]["finished_at"]
    assert risk_runs[-1]["failure_category"] == "materialize_failure"


def test_risk_tensor_module_descriptor_registers_without_collision():
    registry_mod = load_module(
        "backend.app.core_finance.module_registry",
        "backend/app/core_finance/module_registry.py",
    )
    bond_task_mod = load_module(
        "backend.app.tasks.bond_analytics_materialize",
        "backend/app/tasks/bond_analytics_materialize.py",
    )
    risk_task_mod = load_module(
        "backend.app.tasks.risk_tensor_materialize",
        "backend/app/tasks/risk_tensor_materialize.py",
    )

    descriptor = registry_mod.get_formal_module("risk_tensor")

    assert descriptor.cache_key == risk_task_mod.CACHE_KEY
    assert descriptor.cache_key != bond_task_mod.CACHE_KEY
    assert descriptor.lock_key != bond_task_mod.BOND_ANALYTICS_LOCK.key


def test_risk_tensor_materialize_uses_materialized_interest_mode_for_coupon_windows(tmp_path):
    duckdb_path, governance_dir, _bond_task_mod = _configure_upstream_with_semiannual_coupon(tmp_path)
    risk_task_mod = load_module(
        "backend.app.tasks.risk_tensor_materialize",
        "backend/app/tasks/risk_tensor_materialize.py",
    )
    repo_mod = load_module(
        "backend.app.repositories.risk_tensor_repo",
        "backend/app/repositories/risk_tensor_repo.py",
    )

    risk_task_mod.materialize_risk_tensor_facts.fn(
        report_date=REPORT_DATE,
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    row = repo_mod.RiskTensorRepository(str(duckdb_path)).fetch_risk_tensor_row(REPORT_DATE)

    assert row is not None
    assert row["liquidity_gap_30d"] == 8
    assert row["liquidity_gap_90d"] == 16
    assert row["asset_cashflow_30d"] == 8
    assert row["asset_cashflow_90d"] == 16
    assert row["liability_cashflow_30d"] == 0
    assert row["liability_cashflow_90d"] == 0
    assert any("Embedded optionality" in warning for warning in row["warnings"])


def test_risk_tensor_materialize_nets_formal_tyw_liability_cashflows(tmp_path):
    duckdb_path, governance_dir, _bond_task_mod = _configure_upstream(tmp_path)
    risk_task_mod = load_module(
        "backend.app.tasks.risk_tensor_materialize",
        "backend/app/tasks/risk_tensor_materialize.py",
    )
    repo_mod = load_module(
        "backend.app.repositories.risk_tensor_repo",
        "backend/app/repositories/risk_tensor_repo.py",
    )

    import duckdb

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table if not exists fact_formal_tyw_balance_daily (
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
        conn.execute(
            """
            insert into fact_formal_tyw_balance_daily (
              report_date, position_id, product_type, position_side, counterparty_name,
              account_type, special_account_type, core_customer_type, invest_type_std,
              accounting_basis, position_scope, currency_basis, currency_code, principal_amount,
              accrued_interest_amount, funding_cost_rate, maturity_date, source_version,
              rule_version, ingest_batch_id, trace_id
            ) values (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                REPORT_DATE,
                "TYW-L-1",
                "Interbank",
                "liability",
                "Bank L",
                "",
                "",
                "",
                "H",
                "AC",
                "liability",
                "CNY",
                "CNY",
                Decimal("4"),
                Decimal("0"),
                Decimal("0"),
                "2026-04-10",
                "sv_tyw_liab_1",
                "rv_balance_analysis_formal_materialize_v1",
                "ib-liab-1",
                "trace-liab-1",
            ],
        )
    finally:
        conn.close()

    risk_task_mod.materialize_risk_tensor_facts.fn(
        report_date=REPORT_DATE,
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    row = repo_mod.RiskTensorRepository(str(duckdb_path)).fetch_risk_tensor_row(REPORT_DATE)

    assert row is not None
    assert row["liability_source_version"] == "sv_tyw_liab_1"
    assert row["liability_rule_version"] == "rv_balance_analysis_formal_materialize_v1"
    assert row["source_version"] == "sv_risk_tensor__sv_bond_snap_1__sv_tyw_liab_1"
    assert row["asset_cashflow_30d"] == 14
    assert row["asset_cashflow_90d"] == 14
    assert row["liability_cashflow_30d"] == 4
    assert row["liability_cashflow_90d"] == 4
    assert row["liquidity_gap_30d"] == 10
    assert row["liquidity_gap_90d"] == 10
    assert row["liquidity_gap_30d"] == row["asset_cashflow_30d"] - row["liability_cashflow_30d"]
