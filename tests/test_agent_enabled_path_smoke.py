from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb
from fastapi.testclient import TestClient

from tests.helpers import load_module


REPORT_DATE = "2026-03-31"


def _seed_agent_pnl_tables(duckdb_path: Path) -> None:
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_formal_pnl_fi (
              report_date varchar,
              instrument_code varchar,
              portfolio_name varchar,
              cost_center varchar,
              invest_type_std varchar,
              accounting_basis varchar,
              currency_basis varchar,
              interest_income_514 double,
              fair_value_change_516 double,
              capital_gain_517 double,
              manual_adjustment double,
              total_pnl double,
              source_version varchar,
              rule_version varchar,
              ingest_batch_id varchar,
              trace_id varchar
            )
            """
        )
        conn.execute(
            """
            create table fact_nonstd_pnl_bridge (
              report_date varchar,
              bond_code varchar,
              portfolio_name varchar,
              cost_center varchar,
              interest_income_514 double,
              fair_value_change_516 double,
              capital_gain_517 double,
              manual_adjustment double,
              total_pnl double,
              source_version varchar,
              rule_version varchar,
              ingest_batch_id varchar,
              trace_id varchar
            )
            """
        )
        conn.execute(
            """
            insert into fact_formal_pnl_fi values
            (?, 'BOND-001', '组合A', 'CC100', 'H', 'AC', 'CNX', 10, 5, 2, 0, 17, 'sv_fi_1', 'rv_fi_1', 'batch-1', 'tr-fi-1')
            """,
            [REPORT_DATE],
        )
        conn.execute(
            """
            insert into fact_nonstd_pnl_bridge values
            (?, 'NONSTD-001', '组合A', 'CC100', 3, 1, 0, 0, 4, 'sv_nonstd_1', 'rv_nonstd_1', 'batch-2', 'tr-nonstd-1')
            """,
            [REPORT_DATE],
        )
    finally:
        conn.close()


def _seed_agent_balance_tables(duckdb_path: Path) -> None:
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_formal_zqtz_balance_daily (
              report_date varchar,
              instrument_code varchar,
              portfolio_name varchar,
              cost_center varchar,
              invest_type_std varchar,
              accounting_basis varchar,
              position_scope varchar,
              currency_basis varchar,
              market_value_amount double,
              amortized_cost_amount double,
              accrued_interest_amount double,
              source_version varchar,
              rule_version varchar
            )
            """
        )
        conn.execute(
            """
            create table fact_formal_tyw_balance_daily (
              report_date varchar,
              position_id varchar,
              counterparty_name varchar,
              product_type varchar,
              invest_type_std varchar,
              accounting_basis varchar,
              position_scope varchar,
              currency_basis varchar,
              principal_amount double,
              accrued_interest_amount double,
              source_version varchar,
              rule_version varchar
            )
            """
        )
        conn.execute(
            """
            insert into fact_formal_zqtz_balance_daily values
            (?, 'BOND-001', '组合A', 'CC100', 'H', 'AC', 'asset', 'CNY', 1000, 950, 12, 'sv_balance_zqtz_1', 'rv_balance_1')
            """,
            [REPORT_DATE],
        )
        conn.execute(
            """
            insert into fact_formal_tyw_balance_daily values
            (?, 'TYW-001', '机构A', 'repo', 'H', 'AC', 'asset', 'CNY', 500, 8, 'sv_balance_tyw_1', 'rv_balance_1')
            """,
            [REPORT_DATE],
        )
    finally:
        conn.close()


def _fresh_main_module():
    for module_name in (
        "backend.app.main",
        "backend.app.api",
        "backend.app.api.routes.agent",
        "backend.app.services.agent_service",
        "backend.app.agent.runtime.tool_registry",
        "backend.app.agent.tools.analysis_view_tool",
        "backend.app.governance.settings",
    ):
        sys.modules.pop(module_name, None)
    return load_module("backend.app.main", "backend/app/main.py")


def test_agent_query_enabled_path_returns_real_envelope_and_audit(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    _seed_agent_pnl_tables(duckdb_path)

    monkeypatch.setenv("MOSS_AGENT_ENABLED", "true")
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))

    client = TestClient(_fresh_main_module().app)
    response = client.post(
        "/api/agent/query",
        json={"question": "PnL summary", "context": {"user_id": "u_smoke"}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["basis"] == "formal"
    assert payload["result_meta"]["result_kind"] == "agent.pnl_summary"
    assert payload["result_meta"]["formal_use_allowed"] is True
    assert payload["evidence"]["tables_used"] == ["fact_formal_pnl_fi", "fact_nonstd_pnl_bridge"]
    assert payload["evidence"]["filters_applied"] == {"report_date": REPORT_DATE}
    assert payload["evidence"]["evidence_rows"] == 2
    assert any(card["title"] == "Total PnL" for card in payload["cards"])
    assert REPORT_DATE in payload["answer"]

    audit_path = governance_dir / "agent_audit.jsonl"
    assert audit_path.exists()
    audit_payload = json.loads(audit_path.read_text(encoding="utf-8").splitlines()[-1])
    assert audit_payload["user_id"] == "u_smoke"
    assert audit_payload["query_text"] == "PnL summary"
    assert audit_payload["tools_used"] == ["analysis_view_tool", "evidence_tool"]
    assert audit_payload["tables_used"] == ["fact_formal_pnl_fi", "fact_nonstd_pnl_bridge"]


def test_agent_query_enabled_path_returns_real_portfolio_overview_and_audit(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss-balance.duckdb"
    governance_dir = tmp_path / "governance-balance"
    _seed_agent_balance_tables(duckdb_path)

    monkeypatch.setenv("MOSS_AGENT_ENABLED", "true")
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))

    client = TestClient(_fresh_main_module().app)
    response = client.post(
        "/api/agent/query",
        json={
            "question": "portfolio overview",
            "position_scope": "asset",
            "currency_basis": "CNY",
            "context": {"user_id": "u_balance"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["basis"] == "formal"
    assert payload["result_meta"]["result_kind"] == "agent.portfolio_overview"
    assert payload["result_meta"]["formal_use_allowed"] is True
    assert payload["evidence"]["tables_used"] == [
        "fact_formal_zqtz_balance_daily",
        "fact_formal_tyw_balance_daily",
    ]
    assert payload["evidence"]["filters_applied"] == {
        "report_date": REPORT_DATE,
        "position_scope": "asset",
        "currency_basis": "CNY",
    }
    assert payload["evidence"]["evidence_rows"] == 2
    assert any(card["title"] == "Total Market Value" for card in payload["cards"])
    assert REPORT_DATE in payload["answer"]

    audit_path = governance_dir / "agent_audit.jsonl"
    assert audit_path.exists()
    audit_payload = json.loads(audit_path.read_text(encoding="utf-8").splitlines()[-1])
    assert audit_payload["user_id"] == "u_balance"
    assert audit_payload["query_text"] == "portfolio overview"
    assert audit_payload["tools_used"] == ["analysis_view_tool", "evidence_tool"]
    assert audit_payload["tables_used"] == [
        "fact_formal_zqtz_balance_daily",
        "fact_formal_tyw_balance_daily",
    ]
