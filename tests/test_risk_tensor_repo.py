from __future__ import annotations

import time
from datetime import date
from decimal import Decimal

import duckdb

from tests.helpers import load_module


def _sample_tensor(core_mod):
    return core_mod.PortfolioRiskTensor(
        report_date=date(2026, 3, 31),
        portfolio_dv01=Decimal("1.25000000"),
        krd_1y=Decimal("0.25000000"),
        krd_3y=Decimal("0"),
        krd_5y=Decimal("1.00000000"),
        krd_7y=Decimal("0"),
        krd_10y=Decimal("0"),
        krd_30y=Decimal("0"),
        cs01=Decimal("0.75000000"),
        portfolio_convexity=Decimal("2.50000000"),
        portfolio_modified_duration=Decimal("1.50000000"),
        issuer_concentration_hhi=Decimal("0.50000000"),
        issuer_top5_weight=Decimal("1.00000000"),
        asset_cashflow_30d=Decimal("12.00000000"),
        asset_cashflow_90d=Decimal("12.00000000"),
        liability_cashflow_30d=Decimal("2.00000000"),
        liability_cashflow_90d=Decimal("2.00000000"),
        liquidity_gap_30d=Decimal("10.00000000"),
        liquidity_gap_90d=Decimal("10.00000000"),
        liquidity_gap_30d_ratio=Decimal("0.10000000"),
        total_market_value=Decimal("100.00000000"),
        bond_count=2,
        quality_flag="warning",
        warnings=["synthetic warning"],
    )


def test_risk_tensor_repo_round_trip_preserves_lineage_and_warnings(tmp_path):
    # Load core before repo so the repo module binds PortfolioRiskTensor from the
    # same module object we mutate via load_module (avoids stale class identity).
    core_mod = load_module(
        "backend.app.core_finance.risk_tensor",
        "backend/app/core_finance/risk_tensor.py",
    )
    repo_mod = load_module(
        "backend.app.repositories.risk_tensor_repo",
        "backend/app/repositories/risk_tensor_repo.py",
    )
    repo = repo_mod.RiskTensorRepository(str(tmp_path / "moss.duckdb"))

    tensor = _sample_tensor(core_mod)

    repo.replace_risk_tensor_row(
        report_date="2026-03-31",
        tensor=tensor,
        source_version="sv_risk_tensor__sv_bond_snap_1",
        upstream_source_version="sv_bond_snap_1",
        liability_source_version="sv_tyw_liability_synthetic",
        liability_rule_version="rv_tyw_formal_synthetic",
        rule_version="rv_risk_tensor_formal_materialize_v1",
        cache_version="cv_risk_tensor_formal__rv_risk_tensor_formal_materialize_v1",
        trace_id="trace_risk_tensor_20260331",
    )

    row = None
    for _ in range(10):
        row = repo.fetch_risk_tensor_row("2026-03-31")
        if row is not None:
            break
        time.sleep(0.05)

    assert row is not None
    assert row["source_version"] == "sv_risk_tensor__sv_bond_snap_1"
    assert row["upstream_source_version"] == "sv_bond_snap_1"
    assert row["liability_source_version"] == "sv_tyw_liability_synthetic"
    assert row["liability_rule_version"] == "rv_tyw_formal_synthetic"
    assert row["rule_version"] == "rv_risk_tensor_formal_materialize_v1"
    assert row["cache_version"] == "cv_risk_tensor_formal__rv_risk_tensor_formal_materialize_v1"
    assert row["quality_flag"] == "warning"
    assert row["warnings"] == ["synthetic warning"]
    assert row["bond_count"] == 2
    assert row["portfolio_dv01"] == Decimal("1.25000000")
    assert row["portfolio_modified_duration"] == Decimal("1.50000000")
    assert row["liquidity_gap_30d_ratio"] == Decimal("0.10000000")
    assert row["asset_cashflow_30d"] == Decimal("12.00000000")
    assert row["asset_cashflow_90d"] == Decimal("12.00000000")
    assert row["liability_cashflow_30d"] == Decimal("2.00000000")
    assert row["liability_cashflow_90d"] == Decimal("2.00000000")
    assert row["liquidity_gap_30d"] == row["asset_cashflow_30d"] - row["liability_cashflow_30d"]
    assert row["liquidity_gap_90d"] == row["asset_cashflow_90d"] - row["liability_cashflow_90d"]


def test_risk_tensor_read_paths_work_while_read_only_connection_is_open(tmp_path):
    core_mod = load_module(
        "backend.app.core_finance.risk_tensor",
        "backend/app/core_finance/risk_tensor.py",
    )
    repo_mod = load_module(
        "backend.app.repositories.risk_tensor_repo",
        "backend/app/repositories/risk_tensor_repo.py",
    )
    duckdb_path = tmp_path / "moss.duckdb"
    repo = repo_mod.RiskTensorRepository(str(duckdb_path))
    repo.replace_risk_tensor_row(
        report_date="2026-03-31",
        tensor=_sample_tensor(core_mod),
        source_version="sv_risk_tensor__sv_bond_snap_1",
        upstream_source_version="sv_bond_snap_1",
        liability_source_version="sv_tyw_liability_synthetic",
        liability_rule_version="rv_tyw_formal_synthetic",
        rule_version="rv_risk_tensor_formal_materialize_v1",
        cache_version="cv_risk_tensor_formal__rv_risk_tensor_formal_materialize_v1",
        trace_id="trace_risk_tensor_20260331",
    )

    held_read_conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        lineage_rows = repo.list_report_date_lineage_rows()
        row = repo.fetch_risk_tensor_row("2026-03-31")
    finally:
        held_read_conn.close()

    assert lineage_rows == [
        {
            "report_date": "2026-03-31",
            "upstream_source_version": "sv_bond_snap_1",
            "liability_source_version": "sv_tyw_liability_synthetic",
            "liability_rule_version": "rv_tyw_formal_synthetic",
        }
    ]
    assert row is not None
    assert row["source_version"] == "sv_risk_tensor__sv_bond_snap_1"


def test_risk_tensor_read_paths_do_not_mutate_legacy_schema(tmp_path):
    repo_mod = load_module(
        "backend.app.repositories.risk_tensor_repo",
        "backend/app/repositories/risk_tensor_repo.py",
    )
    duckdb_path = tmp_path / "legacy.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_formal_risk_tensor_daily (
                report_date varchar,
                portfolio_dv01 decimal(24, 8),
                krd_1y decimal(24, 8),
                krd_3y decimal(24, 8),
                krd_5y decimal(24, 8),
                krd_7y decimal(24, 8),
                krd_10y decimal(24, 8),
                krd_30y decimal(24, 8),
                cs01 decimal(24, 8),
                portfolio_convexity decimal(24, 8),
                portfolio_modified_duration decimal(24, 8),
                issuer_concentration_hhi decimal(24, 8),
                issuer_top5_weight decimal(24, 8),
                liquidity_gap_30d decimal(24, 8),
                liquidity_gap_90d decimal(24, 8),
                liquidity_gap_30d_ratio decimal(24, 8),
                total_market_value decimal(24, 8),
                bond_count integer,
                quality_flag varchar,
                warnings_json varchar,
                source_version varchar,
                upstream_source_version varchar,
                rule_version varchar,
                cache_version varchar,
                trace_id varchar
            )
            """
        )
        conn.execute(
            """
            insert into fact_formal_risk_tensor_daily values (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                "2026-03-31",
                Decimal("1.25"),
                Decimal("0.25"),
                Decimal("0"),
                Decimal("1.00"),
                Decimal("0"),
                Decimal("0"),
                Decimal("0"),
                Decimal("0.75"),
                Decimal("2.50"),
                Decimal("1.50"),
                Decimal("0.50"),
                Decimal("1.00"),
                Decimal("10.00"),
                Decimal("10.00"),
                Decimal("0.10"),
                Decimal("100.00"),
                2,
                "warning",
                '["legacy warning"]',
                "sv_risk_tensor__sv_bond_snap_1",
                "sv_bond_snap_1",
                "rv_risk_tensor_formal_materialize_v1",
                "cv_risk_tensor_formal__rv_risk_tensor_formal_materialize_v1",
                "trace_risk_tensor_20260331",
            ],
        )
    finally:
        conn.close()

    repo = repo_mod.RiskTensorRepository(str(duckdb_path))

    lineage_rows = repo.list_report_date_lineage_rows()
    row = repo.fetch_risk_tensor_row("2026-03-31")

    assert lineage_rows == [
        {
            "report_date": "2026-03-31",
            "upstream_source_version": "sv_bond_snap_1",
            "liability_source_version": "",
            "liability_rule_version": "",
        }
    ]
    assert row is not None
    assert row["asset_cashflow_30d"] == 0
    assert row["asset_cashflow_90d"] == 0
    assert row["liability_cashflow_30d"] == 0
    assert row["liability_cashflow_90d"] == 0
    assert row["liability_source_version"] == ""
    assert row["liability_rule_version"] == ""
    assert row["warnings"] == ["legacy warning"]

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        columns = {str(row[1]) for row in conn.execute("pragma table_info('fact_formal_risk_tensor_daily')").fetchall()}
    finally:
        conn.close()
    assert "asset_cashflow_30d" not in columns
    assert "liability_source_version" not in columns


def test_load_current_tyw_liability_lineage_by_report_date_deduplicates_and_sorts(tmp_path):
    repo_mod = load_module(
        "backend.app.repositories.risk_tensor_repo",
        "backend/app/repositories/risk_tensor_repo.py",
    )
    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_formal_tyw_balance_daily (
              report_date varchar,
              position_scope varchar,
              currency_basis varchar,
              source_version varchar,
              rule_version varchar
            )
            """
        )
        conn.executemany(
            """
            insert into fact_formal_tyw_balance_daily values (?, ?, ?, ?, ?)
            """,
            [
                ("2026-03-31", "liability", "CNY", "sv_b", "rv_2"),
                ("2026-03-31", "liability", "CNY", "sv_a", "rv_1"),
                ("2026-03-31", "liability", "CNY", "sv_b", "rv_2"),
                ("2026-04-30", "asset", "CNY", "sv_ignored", "rv_ignored"),
                ("2026-04-30", "liability", "USD", "sv_ignored", "rv_ignored"),
                ("2026-04-30", "liability", "CNY", "", "rv_3"),
            ],
        )
    finally:
        conn.close()

    lineage = repo_mod.load_current_tyw_liability_lineage_by_report_date(
        duckdb_path=str(duckdb_path),
    )

    assert lineage == {
        "2026-03-31": {
            "source_version": "sv_a__sv_b",
            "rule_version": "rv_1__rv_2",
        },
        "2026-04-30": {
            "source_version": "",
            "rule_version": "rv_3",
        },
    }
