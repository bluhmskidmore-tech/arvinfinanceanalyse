from __future__ import annotations

import importlib
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
            (?, 'BOND-001', '缁勫悎A', 'CC100', 'H', 'AC', 'CNX', 10, 5, 2, 0, 17, 'sv_fi_1', 'rv_fi_1', 'batch-1', 'tr-fi-1')
            """,
            [REPORT_DATE],
        )
        conn.execute(
            """
            insert into fact_nonstd_pnl_bridge values
            (?, 'NONSTD-001', '缁勫悎A', 'CC100', 3, 1, 0, 0, 4, 'sv_nonstd_1', 'rv_nonstd_1', 'batch-2', 'tr-nonstd-1')
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
            (?, 'BOND-001', '缁勫悎A', 'CC100', 'H', 'AC', 'asset', 'CNY', 1000, 950, 12, 'sv_balance_zqtz_1', 'rv_balance_1')
            """,
            [REPORT_DATE],
        )
        conn.execute(
            """
            insert into fact_formal_tyw_balance_daily values
            (?, 'TYW-001', '鏈烘瀯A', 'repo', 'H', 'AC', 'asset', 'CNY', 500, 8, 'sv_balance_tyw_1', 'rv_balance_1')
            """,
            [REPORT_DATE],
        )
    finally:
        conn.close()


def _seed_agent_risk_tensor_tables(duckdb_path: Path, governance_dir: Path) -> None:
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_formal_bond_analytics_daily (
              report_date varchar
            )
            """
        )
        conn.execute(
            """
            create table fact_formal_risk_tensor_daily (
              report_date varchar,
              portfolio_dv01 double,
              krd_1y double,
              krd_3y double,
              krd_5y double,
              krd_7y double,
              krd_10y double,
              krd_30y double,
              cs01 double,
              portfolio_convexity double,
              portfolio_modified_duration double,
              issuer_concentration_hhi double,
              issuer_top5_weight double,
              liquidity_gap_30d double,
              liquidity_gap_90d double,
              liquidity_gap_30d_ratio double,
              total_market_value double,
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
            insert into fact_formal_bond_analytics_daily values (?)
            """,
            [REPORT_DATE],
        )
        conn.execute(
            """
            insert into fact_formal_risk_tensor_daily values
            (?, 12.34, 1.00, 2.00, 3.00, 2.50, 2.10, 1.10, 0.88, 0.45, 4.20, 0.12, 0.34, 100, 250, 0.40, 1500, 3, 'ok', '[]', 'sv_risk_tensor_1', 'sv_bond_analytics_1', 'rv_risk_tensor_1', 'cv_risk_tensor_1', 'tr-risk-1')
            """,
            [REPORT_DATE],
        )
    finally:
        conn.close()

    governance_repo_module = load_module(
        "backend.app.repositories.governance_repo",
        "backend/app/repositories/governance_repo.py",
    )
    bond_task_module = load_module(
        "backend.app.tasks.bond_analytics_materialize",
        "backend/app/tasks/bond_analytics_materialize.py",
    )
    governance_repo = governance_repo_module.GovernanceRepository(base_dir=governance_dir)
    governance_repo.append(
        governance_repo_module.CACHE_BUILD_RUN_STREAM,
        {
            "run_id": "bond-analytics-run-1",
            "job_name": "bond_analytics_materialize",
            "status": "completed",
            "cache_key": bond_task_module.CACHE_KEY,
            "source_version": "sv_bond_analytics_1",
            "vendor_version": "vv_none",
            "rule_version": "rv_bond_analytics_1",
            "cache_version": "cv_bond_analytics_1",
            "report_date": REPORT_DATE,
        },
    )


def _seed_agent_market_data_tables(duckdb_path: Path) -> None:
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_choice_macro_daily (
              series_id varchar,
              series_name varchar,
              trade_date varchar,
              value_numeric double,
              frequency varchar,
              unit varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              quality_flag varchar,
              run_id varchar
            )
            """
        )
        conn.execute(
            """
            insert into fact_choice_macro_daily values
            ('cn_cpi_yoy', 'CN CPI YoY', ?, 0.7, 'monthly', 'pct', 'sv_macro_1', 'vv_macro_1', 'rv_macro_1', 'ok', 'macro-run-1')
            """,
            [REPORT_DATE],
        )
    finally:
        conn.close()


def _seed_agent_news_tables(duckdb_path: Path) -> None:
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table choice_news_event (
              event_key varchar,
              received_at varchar,
              group_id varchar,
              content_type varchar,
              serial_id integer,
              request_id integer,
              error_code integer,
              error_msg varchar,
              topic_code varchar,
              item_index integer,
              payload_text varchar,
              payload_json varchar
            )
            """
        )
        conn.execute(
            """
            insert into choice_news_event values
            ('evt-1', ?, 'g-1', 'text', 1, 10, 0, '', 'macro', 0, 'macro headline', '{}')
            """,
            [f"{REPORT_DATE}T09:00:00Z"],
        )
    finally:
        conn.close()


def _seed_agent_product_pnl_tables(duckdb_path: Path) -> None:
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table product_category_pnl_formal_read_model (
              sort_order integer,
              category_id varchar,
              category_name varchar,
              side varchar,
              level integer,
              view varchar,
              report_date varchar,
              baseline_ftp_rate_pct double,
              cnx_scale double,
              cny_scale double,
              foreign_scale double,
              cnx_cash double,
              cny_cash double,
              foreign_cash double,
              cny_ftp double,
              foreign_ftp double,
              cny_net double,
              foreign_net double,
              business_net_income double,
              weighted_yield double,
              is_total boolean,
              children_json varchar,
              source_version varchar,
              rule_version varchar
            )
            """
        )
        conn.execute(
            """
            insert into product_category_pnl_formal_read_model values
            (1, 'asset_total', 'Asset Total', 'asset', 0, 'monthly', ?, 1.75, 100, 80, 20, 1000, 800, 200, 10, 3, 20, 5, 25, 2.5, true, '[]', 'sv_product_1', 'rv_product_1'),
            (2, 'liability_total', 'Liability Total', 'liability', 0, 'monthly', ?, 1.75, 50, 40, 10, 500, 400, 100, 8, 2, 12, 3, 15, 1.5, true, '[]', 'sv_product_1', 'rv_product_1'),
            (3, 'grand_total', 'Grand Total', 'all', 0, 'monthly', ?, 1.75, 150, 120, 30, 1500, 1200, 300, 18, 5, 32, 8, 40, 2.0, true, '[]', 'sv_product_1', 'rv_product_1')
            """,
            [REPORT_DATE, REPORT_DATE, REPORT_DATE],
        )
    finally:
        conn.close()


def _seed_agent_pnl_bridge_tables(duckdb_path: Path, governance_dir: Path) -> None:
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
            create table fact_formal_zqtz_balance_daily (
              report_date varchar,
              instrument_code varchar,
              instrument_name varchar,
              portfolio_name varchar,
              cost_center varchar,
              account_category varchar,
              asset_class varchar,
              bond_type varchar,
              issuer_name varchar,
              industry_name varchar,
              rating varchar,
              invest_type_std varchar,
              accounting_basis varchar,
              position_scope varchar,
              currency_basis varchar,
              currency_code varchar,
              face_value_amount double,
              market_value_amount double,
              amortized_cost_amount double,
              accrued_interest_amount double,
              coupon_rate double,
              ytm_value double,
              maturity_date varchar,
              interest_mode varchar,
              is_issuance_like boolean,
              overdue_principal_days integer,
              overdue_interest_days integer,
              value_date varchar,
              customer_attribute varchar,
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
            (?, 'BOND-001', '缁勫悎A', 'CC100', 'H', 'AC', 'CNY', 10, 5, 2, 0, 17, 'sv_fi_bridge_1', 'rv_fi_bridge_1', 'batch-1', 'tr-fi-bridge-1')
            """,
            [REPORT_DATE],
        )
        conn.execute(
            """
            insert into fact_formal_zqtz_balance_daily values
            (?, 'BOND-001', 'Bond 001', '缁勫悎A', 'CC100', '鍊哄埜', 'bond', 'treasury', 'issuerA', 'industryA', 'AAA', 'H', 'AC', 'asset', 'CNY', 'CNY', 1000, 980, 970, 12, 2.5, 2.8, '2028-03-31', 'fixed', false, 0, 0, ?, 'normal', 'sv_balance_bridge_1', 'rv_balance_bridge_1', 'batch-balance-1', 'tr-balance-1')
            """,
            [REPORT_DATE, REPORT_DATE],
        )
    finally:
        conn.close()

    governance_repo_module = load_module(
        "backend.app.repositories.governance_repo",
        "backend/app/repositories/governance_repo.py",
    )
    pnl_task_module = load_module(
        "backend.app.tasks.pnl_materialize",
        "backend/app/tasks/pnl_materialize.py",
    )
    governance_repo = governance_repo_module.GovernanceRepository(base_dir=governance_dir)
    governance_repo.append(
        governance_repo_module.CACHE_MANIFEST_STREAM,
        {
            "cache_key": pnl_task_module.CACHE_KEY,
            "source_version": "sv_pnl_bridge_manifest_1",
            "vendor_version": "vv_none",
            "rule_version": pnl_task_module.RULE_VERSION,
        },
    )


def _seed_agent_bond_analytics_tables(duckdb_path: Path) -> None:
    repo_module = load_module(
        "backend.app.repositories.bond_analytics_repo",
        "backend/app/repositories/bond_analytics_repo.py",
    )
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        repo_module.ensure_bond_analytics_tables(conn)
        conn.execute(
            """
            insert into fact_formal_bond_analytics_daily values
            (?, 'BOND-001', 'Treasury Bond', '缁勫悎A', 'CC100', 'bond', 'rates', 'gov', 'issuerA', 'industryA', 'AAA', 'TPL', 'rule-1', 'CNY', 1000, 980, 970, 12, 2.5, 2.8, '2028-03-31', 2.0, '2Y', 4.1, 4.0, 0.5, 12.34, false, 0.12, 'sv_bond_1', 'rv_bond_1', 'batch-1', 'tr-bond-1'),
            (?, 'BOND-002', 'Credit Bond', '缁勫悎A', 'CC100', 'bond', 'credit', 'corp', 'issuerB', 'industryB', 'AA+', 'OCI', 'rule-2', 'CNY', 500, 510, 505, 8, 3.2, 3.5, '2029-03-31', 3.0, '3Y', 5.2, 5.0, 0.8, 6.78, true, 0.45, 'sv_bond_1', 'rv_bond_1', 'batch-1', 'tr-bond-2')
            """,
            [REPORT_DATE, REPORT_DATE],
        )
    finally:
        conn.close()


def _fresh_main_module():
    for module_name in (
        "backend.app.main",
        "backend.app.api",
        "backend.app.api.routes.agent",
        "backend.app.api.routes",
        "backend.app.services.agent_service",
        "backend.app.agent.runtime.tool_registry",
        "backend.app.agent.runtime",
        "backend.app.agent.tools.analysis_view_tool",
        "backend.app.agent.tools",
        "backend.app.governance.settings",
    ):
        sys.modules.pop(module_name, None)
    return importlib.import_module("backend.app.main")


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


def test_agent_query_enabled_path_returns_real_risk_tensor_and_audit(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss-risk.duckdb"
    governance_dir = tmp_path / "governance-risk"
    _seed_agent_risk_tensor_tables(duckdb_path, governance_dir)

    monkeypatch.setenv("MOSS_AGENT_ENABLED", "true")
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))

    client = TestClient(_fresh_main_module().app)
    response = client.post(
        "/api/agent/query",
        json={
            "question": "risk tensor KRD",
            "context": {"user_id": "u_risk", "report_date": REPORT_DATE},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["basis"] == "formal"
    assert payload["result_meta"]["result_kind"] == "agent.risk_tensor"
    assert payload["result_meta"]["formal_use_allowed"] is True
    assert payload["evidence"]["tables_used"] == ["fact_formal_risk_tensor_daily"]
    assert payload["evidence"]["filters_applied"] == {"report_date": REPORT_DATE}
    assert payload["evidence"]["evidence_rows"] == 3
    assert any(card["title"] == "Portfolio DV01" for card in payload["cards"])
    assert REPORT_DATE in payload["answer"]

    audit_path = governance_dir / "agent_audit.jsonl"
    assert audit_path.exists()
    audit_payload = json.loads(audit_path.read_text(encoding="utf-8").splitlines()[-1])
    assert audit_payload["user_id"] == "u_risk"
    assert audit_payload["query_text"] == "risk tensor KRD"
    assert audit_payload["tools_used"] == ["analysis_view_tool", "evidence_tool"]
    assert audit_payload["tables_used"] == ["fact_formal_risk_tensor_daily"]


def test_agent_query_enabled_path_risk_tensor_uses_latest_report_date_when_context_omits_date(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss-risk-latest.duckdb"
    governance_dir = tmp_path / "governance-risk-latest"
    _seed_agent_risk_tensor_tables(duckdb_path, governance_dir)

    monkeypatch.setenv("MOSS_AGENT_ENABLED", "true")
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))

    client = TestClient(_fresh_main_module().app)
    response = client.post(
        "/api/agent/query",
        json={
            "question": "risk tensor KRD",
            "context": {"user_id": "u_risk_latest"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["basis"] == "formal"
    assert payload["result_meta"]["result_kind"] == "agent.risk_tensor"
    assert payload["result_meta"]["formal_use_allowed"] is True
    assert payload["evidence"]["filters_applied"] == {"report_date": REPORT_DATE}
    assert payload["evidence"]["tables_used"] == ["fact_formal_risk_tensor_daily"]
    assert any(card["title"] == "Portfolio DV01" for card in payload["cards"])
    assert REPORT_DATE in payload["answer"]


def test_agent_query_enabled_path_returns_real_market_data_and_audit(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss-market.duckdb"
    governance_dir = tmp_path / "governance-market"
    _seed_agent_market_data_tables(duckdb_path)

    monkeypatch.setenv("MOSS_AGENT_ENABLED", "true")
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))

    client = TestClient(_fresh_main_module().app)
    response = client.post(
        "/api/agent/query",
        json={
            "question": "market data",
            "context": {"user_id": "u_market"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["basis"] == "analytical"
    assert payload["result_meta"]["result_kind"] == "agent.market_data"
    assert payload["result_meta"]["formal_use_allowed"] is False
    assert payload["evidence"]["tables_used"] == ["fact_choice_macro_daily", "fx_daily_mid"]
    series_val = int(next(c["value"] for c in payload["cards"] if c["title"] == "Series Count"))
    fx_formal_val = int(next(c["value"] for c in payload["cards"] if c["title"] == "Formal FX Candidates"))
    assert payload["evidence"]["evidence_rows"] == series_val + fx_formal_val
    assert any(card["title"] == "Series Count" for card in payload["cards"])

    audit_path = governance_dir / "agent_audit.jsonl"
    assert audit_path.exists()
    audit_payload = json.loads(audit_path.read_text(encoding="utf-8").splitlines()[-1])
    assert audit_payload["user_id"] == "u_market"
    assert audit_payload["query_text"] == "market data"
    assert audit_payload["tables_used"] == ["fact_choice_macro_daily", "fx_daily_mid"]


def test_agent_query_enabled_path_returns_real_news_and_audit(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss-news.duckdb"
    governance_dir = tmp_path / "governance-news"
    _seed_agent_news_tables(duckdb_path)

    monkeypatch.setenv("MOSS_AGENT_ENABLED", "true")
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))

    client = TestClient(_fresh_main_module().app)
    response = client.post(
        "/api/agent/query",
        json={
            "question": "news",
            "context": {"user_id": "u_news"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["basis"] == "analytical"
    assert payload["result_meta"]["result_kind"] == "agent.news"
    assert payload["result_meta"]["formal_use_allowed"] is False
    assert payload["evidence"]["tables_used"] == ["choice_news_event"]
    assert payload["evidence"]["evidence_rows"] == 1
    assert any(card["title"] == "Event Count" for card in payload["cards"])

    audit_path = governance_dir / "agent_audit.jsonl"
    assert audit_path.exists()
    audit_payload = json.loads(audit_path.read_text(encoding="utf-8").splitlines()[-1])
    assert audit_payload["user_id"] == "u_news"
    assert audit_payload["query_text"] == "news"
    assert audit_payload["tables_used"] == ["choice_news_event"]


def test_agent_query_enabled_path_returns_real_product_pnl_and_audit(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss-product-pnl.duckdb"
    governance_dir = tmp_path / "governance-product-pnl"
    _seed_agent_product_pnl_tables(duckdb_path)

    monkeypatch.setenv("MOSS_AGENT_ENABLED", "true")
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))

    client = TestClient(_fresh_main_module().app)
    response = client.post(
        "/api/agent/query",
        json={
            "question": "FTP",
            "filters": {"view": "monthly"},
            "context": {"user_id": "u_product"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["basis"] == "formal"
    assert payload["result_meta"]["result_kind"] == "agent.product_pnl"
    assert payload["result_meta"]["formal_use_allowed"] is True
    assert payload["evidence"]["tables_used"] == ["product_category_pnl_formal_read_model"]
    assert payload["evidence"]["filters_applied"] == {"report_date": REPORT_DATE, "view": "monthly"}
    assert payload["evidence"]["evidence_rows"] == 3
    assert any(card["title"] == "Grand Total" for card in payload["cards"])

    audit_path = governance_dir / "agent_audit.jsonl"
    assert audit_path.exists()
    audit_payload = json.loads(audit_path.read_text(encoding="utf-8").splitlines()[-1])
    assert audit_payload["user_id"] == "u_product"
    assert audit_payload["query_text"] == "FTP"
    assert audit_payload["tables_used"] == ["product_category_pnl_formal_read_model"]


def test_agent_query_enabled_path_returns_real_pnl_bridge_and_audit(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss-pnl-bridge.duckdb"
    governance_dir = tmp_path / "governance-pnl-bridge"
    _seed_agent_pnl_bridge_tables(duckdb_path, governance_dir)

    monkeypatch.setenv("MOSS_AGENT_ENABLED", "true")
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))

    client = TestClient(_fresh_main_module().app)
    response = client.post(
        "/api/agent/query",
        json={
            "question": "bridge",
            "context": {"user_id": "u_bridge"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["basis"] == "formal"
    assert payload["result_meta"]["result_kind"] == "agent.pnl_bridge"
    assert payload["result_meta"]["formal_use_allowed"] is True
    assert payload["evidence"]["tables_used"] == ["fact_formal_pnl_fi", "fact_formal_zqtz_balance_daily"]
    assert payload["evidence"]["filters_applied"] == {"report_date": REPORT_DATE}
    assert payload["evidence"]["evidence_rows"] == 1
    assert any(card["title"] == "Explained PnL" for card in payload["cards"])

    audit_path = governance_dir / "agent_audit.jsonl"
    assert audit_path.exists()
    audit_payload = json.loads(audit_path.read_text(encoding="utf-8").splitlines()[-1])
    assert audit_payload["user_id"] == "u_bridge"
    assert audit_payload["query_text"] == "bridge"
    assert audit_payload["tables_used"] == ["fact_formal_pnl_fi", "fact_formal_zqtz_balance_daily"]


def test_agent_query_enabled_path_returns_real_duration_risk_and_audit(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss-duration.duckdb"
    governance_dir = tmp_path / "governance-duration"
    _seed_agent_bond_analytics_tables(duckdb_path)

    monkeypatch.setenv("MOSS_AGENT_ENABLED", "true")
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))

    client = TestClient(_fresh_main_module().app)
    response = client.post(
        "/api/agent/query",
        json={
            "question": "duration",
            "context": {"user_id": "u_duration"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["basis"] == "formal"
    assert payload["result_meta"]["result_kind"] == "agent.duration_risk"
    assert payload["result_meta"]["formal_use_allowed"] is True
    assert payload["evidence"]["tables_used"] == ["fact_formal_bond_analytics_daily"]
    assert payload["evidence"]["evidence_rows"] == 2
    assert any(card["title"] == "Portfolio DV01" for card in payload["cards"])

    audit_path = governance_dir / "agent_audit.jsonl"
    assert audit_path.exists()
    audit_payload = json.loads(audit_path.read_text(encoding="utf-8").splitlines()[-1])
    assert audit_payload["user_id"] == "u_duration"
    assert audit_payload["query_text"] == "duration"
    assert audit_payload["tables_used"] == ["fact_formal_bond_analytics_daily"]


def test_agent_query_enabled_path_returns_real_credit_exposure_and_audit(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss-credit.duckdb"
    governance_dir = tmp_path / "governance-credit"
    _seed_agent_bond_analytics_tables(duckdb_path)

    monkeypatch.setenv("MOSS_AGENT_ENABLED", "true")
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))

    client = TestClient(_fresh_main_module().app)
    response = client.post(
        "/api/agent/query",
        json={
            "question": "credit",
            "context": {"user_id": "u_credit"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["basis"] == "formal"
    assert payload["result_meta"]["result_kind"] == "agent.credit_exposure"
    assert payload["result_meta"]["formal_use_allowed"] is True
    assert payload["evidence"]["tables_used"] == ["fact_formal_bond_analytics_daily"]
    assert payload["evidence"]["evidence_rows"] == 1
    assert any(card["title"] == "Credit Bond Count" for card in payload["cards"])

    audit_path = governance_dir / "agent_audit.jsonl"
    assert audit_path.exists()
    audit_payload = json.loads(audit_path.read_text(encoding="utf-8").splitlines()[-1])
    assert audit_payload["user_id"] == "u_credit"
    assert audit_payload["query_text"] == "credit"
    assert audit_payload["tables_used"] == ["fact_formal_bond_analytics_daily"]
