"""Contract tests for analytical dashboard KPI endpoints."""
from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

import duckdb
import pytest
from fastapi.testclient import TestClient

from backend.app.core_finance.bond_analytics.engine import BondAnalyticsRow
from backend.app.governance.settings import get_settings
from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository
from tests.helpers import load_module


def _perf_records(caplog, endpoint: str):
    return [
        record
        for record in caplog.records
        if record.name == "backend.app.api.perf" and getattr(record, "endpoint", None) == endpoint
    ]


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


def _zqtz_ddl() -> str:
    return """
    create table if not exists fact_formal_zqtz_balance_daily (
      report_date varchar,
      instrument_code varchar,
      instrument_name varchar,
      portfolio_name varchar,
      cost_center varchar,
      account_category varchar,
      asset_class varchar,
      bond_type varchar,
      sub_type varchar,
      business_type_primary varchar,
      issuer_name varchar,
      industry_name varchar,
      rating varchar,
      invest_type_std varchar,
      accounting_basis varchar,
      position_scope varchar,
      currency_basis varchar,
      currency_code varchar,
      face_value_amount decimal(24, 8),
      market_value_amount decimal(24, 8),
      amortized_cost_amount decimal(24, 8),
      accrued_interest_amount decimal(24, 8),
      coupon_rate decimal(18, 8),
      ytm_value decimal(18, 8),
      maturity_date varchar,
      interest_mode varchar,
      is_issuance_like boolean,
      source_version varchar,
      rule_version varchar,
      ingest_batch_id varchar,
      trace_id varchar,
      overdue_principal_days integer,
      overdue_interest_days integer,
      value_date varchar,
      customer_attribute varchar
    )
    """


def _zqtz_asset_row(*, rd: str, mv: Decimal, ytm: Decimal) -> tuple[object, ...]:
    return (
        rd,
        f"B-{rd}",
        "Bond",
        "Portfolio",
        "CostCenter",
        "AC",
        "rate",
        "rate_bond",
        "",
        "bond",
        "Issuer",
        "Industry",
        "AAA",
        "invest",
        "book",
        "asset",
        "CNY",
        "CNY",
        mv,
        mv,
        mv,
        Decimal("0"),
        Decimal("0.025"),
        ytm,
        "2030-01-01",
        "fixed",
        False,
        "sv-zqtz",
        "rv-zqtz",
        "ib-zqtz",
        "tr-zqtz",
        0,
        0,
        "2026-01-01",
        "",
    )


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


def test_daily_changes_use_formal_zqtz_balance_when_bond_analytics_prior_is_sparse(
    tmp_path,
    monkeypatch,
) -> None:
    duckdb_path = tmp_path / "dash-zqtz-balance.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()

    d1 = "2026-04-29"
    d2 = "2026-04-30"
    repo = BondAnalyticsRepository(str(duckdb_path))
    repo.replace_bond_analytics_rows(
        report_date=d2,
        rows=[_one_bond_row(rd=d2, mv=Decimal("900000"), ytm=Decimal("0.03"))],
    )

    con = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        con.execute(_zqtz_ddl())
        zqtz_prev = _zqtz_asset_row(rd=d1, mv=Decimal("1000000"), ytm=Decimal("0.03"))
        zqtz_cur = _zqtz_asset_row(rd=d2, mv=Decimal("1200000"), ytm=Decimal("0.04"))
        zqtz_insert = (
            "insert into fact_formal_zqtz_balance_daily values ("
            + ",".join(["?"] * len(zqtz_prev))
            + ")"
        )
        con.execute(zqtz_insert, list(zqtz_prev))
        con.execute(zqtz_insert, list(zqtz_cur))

        con.execute(_tyw_ddl())
        tyw_insert = "insert into fact_formal_tyw_balance_daily values (" + ",".join(["?"] * 21) + ")"
        tyw_rows = [
            (d1, "pa-prev", "REPO", "asset", "CP-A", "", "", "", "", "", "asset", "CNY", "CNY", Decimal("200000"), Decimal("0"), Decimal("2.5"), "2030-01-01", "sv", "rv", "ib", "tr"),
            (d1, "pl-prev", "REPO", "liability", "CP-L", "", "", "", "", "", "liability", "CNY", "CNY", Decimal("300000"), Decimal("0"), Decimal("3.0"), "2030-01-01", "sv", "rv", "ib", "tr"),
            (d2, "pa-cur", "REPO", "asset", "CP-A", "", "", "", "", "", "asset", "CNY", "CNY", Decimal("210000"), Decimal("0"), Decimal("2.5"), "2030-01-01", "sv", "rv", "ib", "tr"),
            (d2, "pl-cur", "REPO", "liability", "CP-L", "", "", "", "", "", "liability", "CNY", "CNY", Decimal("310000"), Decimal("0"), Decimal("3.0"), "2030-01-01", "sv", "rv", "ib", "tr"),
        ]
        for row in tyw_rows:
            con.execute(tyw_insert, list(row))
    finally:
        con.close()

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    cm = client.get("/api/dashboard/core_metrics", params={"report_date": d2})
    assert cm.status_code == 200, cm.text
    bonds = cm.json()["result"]["bond_investments"]
    assert bonds["total_amount"]["raw"] == pytest.approx(1_200_000.0)
    assert bonds["weighted_avg_rate"]["raw"] == pytest.approx(0.04)
    assert bonds["change_amount"]["raw"] == pytest.approx(200_000.0)

    dc = client.get("/api/dashboard/daily-changes", params={"report_date": d2})
    assert dc.status_code == 200, dc.text
    day = dc.json()["result"]["periods"][0]
    assert day["period"] == "day"
    assert day["bond_investments_change"]["raw"] == pytest.approx(200_000.0)
    assert day["interbank_assets_change"]["raw"] == pytest.approx(10_000.0)
    assert day["interbank_liabilities_change"]["raw"] == pytest.approx(10_000.0)
    assert day["net_change"]["raw"] == pytest.approx(220_000.0)

    get_settings.cache_clear()


def test_core_metrics_falls_back_to_bond_analytics_when_zqtz_date_is_missing(
    tmp_path,
    monkeypatch,
) -> None:
    duckdb_path = tmp_path / "dash-zqtz-sparse.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()

    d1 = "2026-04-29"
    d2 = "2026-04-30"
    repo = BondAnalyticsRepository(str(duckdb_path))
    repo.replace_bond_analytics_rows(
        report_date=d2,
        rows=[
            _one_bond_row(rd=d2, mv=Decimal("1200000"), ytm=Decimal("0.04"), bond_type="gov"),
            _one_bond_row(rd=d2, mv=Decimal("300000"), ytm=Decimal("0.03"), bond_type="corp"),
        ],
    )

    con = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        con.execute(_zqtz_ddl())
        zqtz_prev = _zqtz_asset_row(rd=d1, mv=Decimal("1000000"), ytm=Decimal("3.0"))
        con.execute(
            "insert into fact_formal_zqtz_balance_daily values ("
            + ",".join(["?"] * len(zqtz_prev))
            + ")",
            list(zqtz_prev),
        )
    finally:
        con.close()

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    cm = client.get("/api/dashboard/core_metrics")
    assert cm.status_code == 200, cm.text
    body = cm.json()["result"]
    assert body["report_date"] == d2
    bonds = body["bond_investments"]
    assert bonds["total_amount"]["raw"] == pytest.approx(1_500_000.0)
    assert bonds["weighted_avg_rate"]["raw"] == pytest.approx(0.038)
    assert bonds["top_3_details"][0]["name"] == "gov"
    assert bonds["top_3_details"][0]["amount"].startswith("0.01")

    get_settings.cache_clear()


def test_daily_changes_missing_formal_zqtz_balance_baseline_returns_null_numeric(
    tmp_path,
    monkeypatch,
) -> None:
    duckdb_path = tmp_path / "dash-missing-baseline.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()

    d1 = "2026-04-29"
    d2 = "2026-04-30"
    repo = BondAnalyticsRepository(str(duckdb_path))
    repo.replace_bond_analytics_rows(
        report_date=d2,
        rows=[_one_bond_row(rd=d2, mv=Decimal("1000000"), ytm=Decimal("0.03"))],
    )

    con = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        con.execute(_tyw_ddl())
        row_a_prev = (
            d1,
            "pa-prev",
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
        row_l_prev = (
            d1,
            "pl-prev",
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
        row_a_cur = (
            d2,
            "pa-cur",
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
            Decimal("210000"),
            Decimal("0"),
            Decimal("2.5"),
            "2030-01-01",
            "sv",
            "rv",
            "ib",
            "tr",
        )
        row_l_cur = (
            d2,
            "pl-cur",
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
            Decimal("310000"),
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
            + ",".join(["?"] * len(row_a_prev))
            + ")"
        )
        for row in (row_a_prev, row_l_prev, row_a_cur, row_l_cur):
            con.execute(q, list(row))
    finally:
        con.close()

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    cm = client.get("/api/dashboard/core_metrics", params={"report_date": d2})
    assert cm.status_code == 200, cm.text
    bonds = cm.json()["result"]["bond_investments"]
    assert bonds["total_amount"]["raw"] == pytest.approx(1_000_000.0)
    assert bonds["change_amount"]["raw"] is None
    assert bonds["change_amount"]["display"] == "—"
    assert bonds["change_pct"]["raw"] is None
    assert bonds["change_pct"]["display"] == "—"

    dc = client.get("/api/dashboard/daily-changes", params={"report_date": d2})
    assert dc.status_code == 200, dc.text
    day = dc.json()["result"]["periods"][0]
    assert day["period"] == "day"
    assert day["bond_investments_change"]["raw"] is None
    assert day["bond_investments_change"]["display"] == "—"
    assert day["interbank_assets_change"]["raw"] == pytest.approx(10_000.0)
    assert day["interbank_liabilities_change"]["raw"] == pytest.approx(10_000.0)
    assert day["net_change"]["raw"] is None
    assert day["net_change"]["display"] == "—"

    get_settings.cache_clear()


def test_core_metrics_uses_batch_date_aggregates(monkeypatch) -> None:
    service = load_module(
        "tests._dashboard_service_core_batch",
        "backend/app/services/dashboard_service.py",
    )
    calls: list[tuple[str, object]] = []

    class Repo:
        def list_merged_report_dates(self):
            return ["2026-04-30", "2026-04-29"]

        def fetch_bond_core_metrics_for_dates(self, report_dates):
            calls.append(("bond-batch", tuple(report_dates)))
            return {
                "2026-04-30": (Decimal("110"), Decimal("0.03"), [("bond", Decimal("110"), Decimal("0.03"))], True),
                "2026-04-29": (Decimal("100"), Decimal("0.02"), [], True),
            }

        def fetch_tyw_core_metrics_for_dates(self, report_dates, *, asset_side: bool):
            calls.append(("tyw-batch", asset_side, tuple(report_dates)))
            if asset_side:
                return {
                    "2026-04-30": (Decimal("210"), Decimal("0.025"), [("asset", Decimal("210"), Decimal("0.025"))], True),
                    "2026-04-29": (Decimal("200"), Decimal("0.02"), [], True),
                }
            return {
                "2026-04-30": (Decimal("310"), Decimal("0.03"), [("liab", Decimal("310"), Decimal("0.03"))], True),
                "2026-04-29": (Decimal("300"), Decimal("0.025"), [], True),
            }

        def fetch_bond_core_metrics(self, report_date: str):
            calls.append(("bond-single", report_date))
            return Decimal("0"), None, [], False

        def fetch_tyw_core_metrics(self, report_date: str, *, asset_side: bool):
            calls.append(("tyw-single", asset_side, report_date))
            return Decimal("0"), None, [], False

    monkeypatch.setattr(service, "_repo", lambda: Repo())

    out = service.get_core_metrics(report_date="2026-04-30")

    assert out["result"]["bond_investments"]["change_amount"]["raw"] == pytest.approx(10.0)
    assert ("bond-batch", ("2026-04-30", "2026-04-29")) in calls
    assert ("tyw-batch", True, ("2026-04-30", "2026-04-29")) in calls
    assert ("tyw-batch", False, ("2026-04-30", "2026-04-29")) in calls
    assert [call for call in calls if "single" in call[0]] == []


def test_daily_changes_uses_one_batch_per_domain(monkeypatch) -> None:
    service = load_module(
        "tests._dashboard_service_daily_batch",
        "backend/app/services/dashboard_service.py",
    )
    calls: list[tuple[str, object]] = []
    dates = [
        "2026-04-30",
        "2026-04-29",
        "2026-04-28",
        "2026-04-27",
        "2026-04-26",
        "2026-04-25",
        "2026-04-01",
    ]

    class Repo:
        def list_merged_report_dates(self):
            return dates

        def fetch_bond_core_metrics_for_dates(self, report_dates):
            calls.append(("bond-batch", tuple(report_dates)))
            return {
                d: (Decimal(str(i + 1)) * Decimal("100"), Decimal("0.03"), [], True)
                for i, d in enumerate(report_dates)
            }

        def fetch_tyw_core_metrics_for_dates(self, report_dates, *, asset_side: bool):
            calls.append(("tyw-batch", asset_side, tuple(report_dates)))
            base = Decimal("1000") if asset_side else Decimal("2000")
            return {
                d: (base + Decimal(str(i)), Decimal("0.02"), [], True)
                for i, d in enumerate(report_dates)
            }

        def fetch_bond_core_metrics(self, report_date: str):
            calls.append(("bond-single", report_date))
            return Decimal("0"), None, [], False

        def fetch_tyw_core_metrics(self, report_date: str, *, asset_side: bool):
            calls.append(("tyw-single", asset_side, report_date))
            return Decimal("0"), None, [], False

    monkeypatch.setattr(service, "_repo", lambda: Repo())

    out = service.get_daily_changes(report_date="2026-04-30")

    assert [p["period"] for p in out["result"]["periods"]] == ["day", "week", "month"]
    batch_dates = ("2026-04-30", "2026-04-29", "2026-04-25", "2026-04-01")
    assert ("bond-batch", batch_dates) in calls
    assert ("tyw-batch", True, batch_dates) in calls
    assert ("tyw-batch", False, batch_dates) in calls
    assert [call for call in calls if "single" in call[0]] == []


def test_dashboard_core_metrics_logs_api_perf(tmp_path, monkeypatch, caplog) -> None:
    duckdb_path = tmp_path / "empty-dash-perf.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    with caplog.at_level(logging.INFO, logger="backend.app.api.perf"):
        response = client.get("/api/dashboard/core_metrics")

    assert response.status_code == 200
    records = _perf_records(caplog, "/api/dashboard/core_metrics")
    assert records
    record = records[-1]
    assert record.getMessage() == "moss_api_perf"
    assert getattr(record, "duration_ms") >= 0
    assert getattr(record, "result_kind") == "dashboard.core_metrics"
    assert getattr(record, "trace_id")
    assert getattr(record, "duckdb_statement_count") is None
    get_settings.cache_clear()
