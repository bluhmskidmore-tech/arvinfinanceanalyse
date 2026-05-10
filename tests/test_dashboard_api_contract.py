"""Contract tests for analytical dashboard KPI endpoints."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import duckdb
import pytest
from fastapi.testclient import TestClient

from backend.app.core_finance.bond_analytics.engine import BondAnalyticsRow
from backend.app.governance.settings import get_settings
from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository
from tests.helpers import load_module


def _tyw_ddl() -> str:
    return """
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


def _one_bond_row(*, rd: str, mv: Decimal, ytm: Decimal, bond_type: str = "国债") -> BondAnalyticsRow:
    return BondAnalyticsRow(
        report_date=date.fromisoformat(rd),
        instrument_code="B1",
        instrument_name="B1",
        portfolio_name="P1",
        cost_center="C1",
        asset_class_raw="x",
        asset_class_std="rate",
        bond_type=bond_type,
        issuer_name="I",
        industry_name="银行",
        rating="AAA",
        accounting_class="AC",
        accounting_rule_id="r1",
        currency_code="CNY",
        face_value=mv,
        market_value_native=mv,
        market_value=mv,
        amortized_cost=mv,
        accrued_interest=Decimal("0"),
        coupon_rate=Decimal("0.025"),
        interest_mode="fixed",
        interest_payment_frequency="annual",
        interest_rate_style="fixed",
        ytm=ytm,
        maturity_date=date(2030, 1, 1),
        next_call_date=None,
        years_to_maturity=Decimal("2.5"),
        tenor_bucket="1-3Y",
        macaulay_duration=Decimal("2"),
        modified_duration=Decimal("1.9"),
        convexity=Decimal("0.01"),
        dv01=Decimal("1"),
        is_credit=False,
        spread_dv01=Decimal("0"),
        source_version="sv",
        rule_version="rv",
        ingest_batch_id="ib",
        trace_id="tr",
    )


def test_core_metrics_latest_anchor_and_three_cards(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "dash-core.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()

    d1 = "2026-03-30"
    d2 = "2026-03-31"
    repo = BondAnalyticsRepository(str(duckdb_path))
    repo.replace_bond_analytics_rows(
        report_date=d1,
        rows=[_one_bond_row(rd=d1, mv=Decimal("1000000"), ytm=Decimal("0.03"))],
    )
    repo.replace_bond_analytics_rows(
        report_date=d2,
        rows=[
            _one_bond_row(rd=d2, mv=Decimal("1100000"), ytm=Decimal("0.032")),
            _one_bond_row(
                rd=d2,
                mv=Decimal("500000"),
                ytm=Decimal("0.04"),
                bond_type="政金债",
            ),
        ],
    )

    con = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        con.execute(_tyw_ddl())
        row_a = (
            d2,
            "p1",
            "REPO",
            "资产",
            "CP-A",
            "",
            "",
            "",
            "",
            "",
            "",
            "CNY",
            "CNY",
            Decimal("200000"),
            Decimal("0"),
            Decimal("2.5"),
            "2030-01-01",
            "sv",
            "rv",
            "ib",
            "tr",
        )
        row_l = (
            d2,
            "p2",
            "REPO",
            "负债",
            "CP-L",
            "",
            "",
            "",
            "",
            "",
            "",
            "CNY",
            "CNY",
            Decimal("300000"),
            Decimal("0"),
            Decimal("3.0"),
            "2030-01-01",
            "sv",
            "rv",
            "ib",
            "tr",
        )
        q = (
            "insert into fact_formal_tyw_balance_daily values ("
            + ",".join(["?"] * len(row_a))
            + ")"
        )
        con.execute(q, list(row_a))
        con.execute(q, list(row_l))
    finally:
        con.close()

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    rsp = client.get("/api/dashboard/core_metrics")
    assert rsp.status_code == 200, rsp.text
    payload = rsp.json()
    assert payload["result_meta"]["basis"] == "analytical"
    body = payload["result"]
    assert body["report_date"] == d2
    bonds = body["bond_investments"]
    assert bonds["total_amount"]["raw"] == pytest.approx(1_600_000.0)
    assert bonds["total_amount"]["unit"] == "yuan"
    assert bonds["total_amount"]["precision"] == 2
    assert bonds["total_amount"]["display"] == "0.02 亿"
    assert bonds["weighted_avg_rate"]["raw"] == pytest.approx(0.0345)
    assert bonds["weighted_avg_rate"]["precision"] == 2
    assert bonds["weighted_avg_rate"]["display"] == "3.45%"
    assert bonds["change_amount"]["raw"] == pytest.approx(600_000.0)
    assert bonds["change_amount"]["precision"] == 2
    assert bonds["change_amount"]["display"] == "+0.01 亿"
    assert bonds["change_pct"]["raw"] == pytest.approx(0.6)
    assert bonds["change_pct"]["precision"] == 2
    assert bonds["change_pct"]["display"] == "+60.00%"
    assert bonds["top_3_details"][0]["amount"] == "0.01 亿"
    assert bonds["top_3_details"][0]["rate"] == "3.20%"

    rsp2 = client.get("/api/dashboard/core_metrics", params={"report_date": d1})
    assert rsp2.status_code == 200
    assert rsp2.json()["result"]["report_date"] == d1

    dc = client.get("/api/dashboard/daily-changes", params={"report_date": d2})
    assert dc.status_code == 200, dc.text
    periods = dc.json()["result"]["periods"]
    assert len(periods) == 3
    assert {p["period"] for p in periods} == {"day", "week", "month"}
    assert periods[0]["period"] == "day"
    assert periods[1]["period"] == "week"
    assert periods[2]["period"] == "month"
    assert periods[0]["bond_investments_change"]["raw"] == pytest.approx(600_000.0)
    assert periods[0]["bond_investments_change"]["precision"] == 2
    assert periods[0]["bond_investments_change"]["display"] == "+0.01 亿"

    get_settings.cache_clear()


def test_dashboard_endpoints_empty_db(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "empty-dash.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    cm = client.get("/api/dashboard/core_metrics")
    assert cm.status_code == 200
    assert cm.json()["result_meta"]["quality_flag"] == "warning"
    assert cm.json()["result"]["report_date"] == ""

    dy = client.get("/api/dashboard/daily-changes")
    assert dy.status_code == 200
    assert dy.json()["result"]["periods"] == []

    get_settings.cache_clear()
