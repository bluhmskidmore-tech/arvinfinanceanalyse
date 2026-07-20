from __future__ import annotations

import platform as _platform
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import duckdb
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Windows / Py3.14: SQLAlchemy import paths can call platform.machine() during
# backend imports. Keep this aligned with the existing executive service tests.
_platform.machine = lambda: "AMD64"  # type: ignore[method-assign, assignment]

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.api.routes import executive as executive_routes
from backend.app.governance.settings import get_settings
from backend.app.repositories.user_scope_repo import UserScopeRepository
from backend.app.security.auth_context import ROLE_HEADER_TRUST_ENV
from backend.app.services import executive_service

EXECUTIVE_READ_HEADERS = {"X-User-Id": "executive-reserved-user", "X-User-Role": "viewer"}
REPORT_DATE = "2026-06-30"


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Any:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _grant_executive_read_scope(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sqlite_path = tmp_path / "executive-reserved-scope.db"
    dsn = f"sqlite:///{sqlite_path.as_posix()}"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", dsn)
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    UserScopeRepository(dsn).grant_scope(
        user_id="*",
        role=None,
        resource="executive",
        action="read",
    )


def _reserved_route_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    _grant_executive_read_scope(tmp_path, monkeypatch)

    def _service_should_not_run(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise AssertionError("reserved executive route must fail before calling its service")

    monkeypatch.setattr(executive_routes, "executive_risk_overview", _service_should_not_run)
    monkeypatch.setattr(executive_routes, "executive_contribution", _service_should_not_run)
    monkeypatch.setattr(executive_routes, "executive_alerts", _service_should_not_run)

    app = FastAPI()
    app.include_router(executive_routes.router)
    client = TestClient(app)
    client.headers.update(EXECUTIVE_READ_HEADERS)
    return client


@pytest.mark.parametrize(
    "path,route_name",
    [
        ("/ui/risk/overview", "risk_overview"),
        ("/ui/home/contribution", "contribution"),
        ("/ui/home/alerts", "alerts"),
    ],
)
def test_executive_reserved_routes_return_stable_503_detail(
    path: str,
    route_name: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _reserved_route_client(tmp_path, monkeypatch)

    response = client.get(path, params={"report_date": "2025-99-99"})

    assert response.status_code == 503
    assert response.json() == {
        "detail": f"Executive route {route_name} is reserved by the current boundary."
    }


def _install_service_settings(
    duckdb_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        executive_service,
        "get_settings",
        lambda: SimpleNamespace(
            duckdb_path=str(duckdb_path),
            governance_path="",
        ),
    )


def _seed_product_category_read_model(duckdb_path: Path) -> None:
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table product_category_pnl_formal_read_model (
              report_date varchar,
              view varchar,
              sort_order integer,
              category_id varchar,
              category_name varchar,
              side varchar,
              level integer,
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
        conn.executemany(
            """
            insert into product_category_pnl_formal_read_model values
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    REPORT_DATE,
                    "monthly",
                    1,
                    "bond_ac",
                    "Bond AC",
                    "asset",
                    1,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    300_000_000.0,
                    None,
                    False,
                    "[]",
                    "sv_contribution_unit",
                    "rv_contribution_unit",
                ),
                (
                    REPORT_DATE,
                    "monthly",
                    2,
                    "bond_tpl",
                    "Bond TPL",
                    "asset",
                    1,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    100_000_000.0,
                    None,
                    False,
                    "[]",
                    "sv_contribution_unit",
                    "rv_contribution_unit",
                ),
            ],
        )
    finally:
        conn.close()


def _seed_bond_analytics_fact(duckdb_path: Path) -> None:
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_formal_bond_analytics_daily (
              report_date varchar,
              instrument_code varchar,
              instrument_name varchar,
              portfolio_name varchar,
              cost_center varchar,
              asset_class_raw varchar,
              asset_class_std varchar,
              bond_type varchar,
              issuer_name varchar,
              industry_name varchar,
              rating varchar,
              accounting_class varchar,
              accounting_rule_id varchar,
              currency_code varchar,
              face_value double,
              market_value_native double,
              market_value double,
              amortized_cost double,
              accrued_interest double,
              coupon_rate double,
              interest_mode varchar,
              interest_payment_frequency varchar,
              interest_rate_style varchar,
              ytm double,
              maturity_date varchar,
              next_call_date varchar,
              years_to_maturity double,
              tenor_bucket varchar,
              macaulay_duration double,
              modified_duration double,
              convexity double,
              dv01 double,
              is_credit boolean,
              spread_dv01 double,
              source_version varchar,
              rule_version varchar,
              ingest_batch_id varchar,
              trace_id varchar
            )
            """
        )
        conn.execute(
            """
            insert into fact_formal_bond_analytics_daily values (
              ?, 'BOND-AC', 'Unit test bond', 'Portfolio', 'Desk',
              'credit bond', 'credit', 'credit', 'Issuer A', 'Industry', 'AAA',
              'AC', 'rule_ac', 'CNY', 100000000.0, 100000000.0, 100000000.0,
              99000000.0, 0.0, 0.03, 'fixed', 'annual', 'fixed', 0.04,
              '2036-06-30', null, 10.0, '10Y', 8.3, 8.0, 70.0, 800000.0,
              true, 80000.0, 'sv_bond_unit', 'rv_bond_unit', 'ib_bond_unit',
              'tr_bond_unit'
            )
            """,
            [REPORT_DATE],
        )
    finally:
        conn.close()


def test_executive_risk_overview_service_reads_duckdb_fact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    duckdb_path = tmp_path / "executive-risk.duckdb"
    _seed_bond_analytics_fact(duckdb_path)
    _install_service_settings(duckdb_path, monkeypatch)

    out = executive_service.executive_risk_overview(report_date=REPORT_DATE)

    assert out["result_meta"]["result_kind"] == "executive.risk-overview"
    assert out["result_meta"]["vendor_status"] == "ok"
    signals = {item["id"]: item for item in out["result"]["signals"]}
    assert signals["duration"]["value"]["raw"] == pytest.approx(8.0)
    assert signals["leverage"]["value"]["raw"] == pytest.approx(800_000.0)
    # Seed data is 100% credit; pct contract stores raw as a decimal ratio (1.0),
    # while display renders percent-points ("100.0%").
    assert signals["credit"]["value"]["raw"] == pytest.approx(1.0)
    assert signals["credit"]["value"]["display"] == "100.0%"


def test_executive_contribution_service_reads_product_category_repo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    duckdb_path = tmp_path / "executive-contribution.duckdb"
    _seed_product_category_read_model(duckdb_path)
    _install_service_settings(duckdb_path, monkeypatch)

    out = executive_service.executive_contribution(report_date=REPORT_DATE)

    assert out["result_meta"]["result_kind"] == "executive.contribution"
    assert out["result_meta"]["vendor_status"] == "ok"
    rows = {item["id"]: item for item in out["result"]["rows"]}
    assert rows["rates"]["contribution"]["raw"] == pytest.approx(300_000_000.0)
    assert rows["trading"]["contribution"]["raw"] == pytest.approx(100_000_000.0)
    assert rows["credit"]["contribution"]["raw"] == pytest.approx(0.0)


def test_executive_alerts_service_reads_duckdb_fact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    duckdb_path = tmp_path / "executive-alerts.duckdb"
    _seed_bond_analytics_fact(duckdb_path)
    _install_service_settings(duckdb_path, monkeypatch)

    out = executive_service.executive_alerts(report_date=REPORT_DATE)

    assert out["result_meta"]["result_kind"] == "executive.alerts"
    assert out["result_meta"]["vendor_status"] == "ok"
    assert {item["id"] for item in out["result"]["items"]} >= {"R_DUR_HIGH", "R_CREDIT_CONC"}
