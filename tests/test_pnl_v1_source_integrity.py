"""Synthetic normalized inputs -> real materialization -> V1 HTTP admission.

Only the refresh-input loader is replaced; facts, rule/FX guards and envelopes
use the real local code. No parser, production store or live service is used.
MOSS_PNL_V1_BEFORE_ROOT can select preserved pre-edit service/repository bytes
for a failure demonstration without reverting the shared working tree.
"""

from __future__ import annotations

import os
from copy import deepcopy
from decimal import Decimal
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from backend.app.repositories.user_scope_repo import UserScopeRepository
from tests.helpers import load_module

REPORT_DATE = "2026-06-30"


def _fi(code="SYNTHETIC-FI", **overrides):
    return {
        "report_date": REPORT_DATE,
        "instrument_code": code,
        "instrument_name": code,
        "portfolio_name": "SYNTHETIC-DESK",
        "cost_center": "SYNTHETIC-CC",
        "invest_type_raw": "T",
        "asset_class": "企业债",
        "interest_income_514": "106",
        "fair_value_change_516": "0",
        "capital_gain_517": "0",
        "currency_basis": "CNY",
        "event_type": "fi_cumulative_realized_517",
        "source_version": "sv_synthetic_fi",
        "trace_id": f"tr_synthetic_{code}",
        **overrides,
    }


def _nonstd(code="JM-SYNTHETIC", journal="514", **overrides):
    return {
        "voucher_date": REPORT_DATE,
        "account_code": f"{journal}-SYNTHETIC",
        "asset_code": code,
        "portfolio_name": "SYNTHETIC-DESK",
        "cost_center": "SYNTHETIC-CC",
        "dc_flag": "credit",
        "raw_amount": "1",
        "event_type": "synthetic",
        "source_file": f"synthetic-{journal}.xlsx",
        "source_version": f"sv_synthetic_{journal}",
        "trace_id": f"tr_synthetic_{journal}_{code}",
        **overrides,
    }


@pytest.fixture
def synthetic_v1(tmp_path, monkeypatch):
    db = tmp_path / "synthetic-pnl.duckdb"
    governance = tmp_path / "governance"
    scope_dsn = f"sqlite:///{(tmp_path / 'scope.db').as_posix()}"
    for key, value in {
        "MOSS_ENVIRONMENT": "test",
        "MOSS_GOVERNANCE_BACKEND": "jsonl",
        "MOSS_POSTGRES_DSN": scope_dsn,
        "MOSS_GOVERNANCE_SQL_DSN": scope_dsn,
        "MOSS_DUCKDB_PATH": str(db),
        "MOSS_GOVERNANCE_PATH": str(governance),
        "MOSS_DATA_INPUT_ROOT": str(tmp_path / "empty-inputs"),
        "MOSS_LOCAL_ARCHIVE_PATH": str(tmp_path / "archive"),
        "MOSS_FINANCIAL_PUBLICATION_ENABLED": "false",
        "MOSS_SYSTEM_READ_PUBLICATION_ENABLED": "false",
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("MOSS_REDIS_DSN", raising=False)
    get_settings.cache_clear()

    service = import_module("backend.app.services.pnl_service")
    before_root = os.environ.get("MOSS_PNL_V1_BEFORE_ROOT")
    if before_root:
        before = Path(before_root)
        service = load_module(
            "tests._pnl_v1_before_service", str(before / "backend/app/services/pnl_service.py"),
        )
        before_repo = load_module(
            "tests._pnl_v1_before_repo", str(before / "backend/app/repositories/pnl_repo.py"),
        )
        monkeypatch.setattr(service, "PnlRepository", before_repo.PnlRepository)
    routes = import_module("backend.app.api.routes.pnl")
    task = import_module("backend.app.tasks.pnl_materialize")
    UserScopeRepository(scope_dsn).grant_scope(
        user_id="anonymous", role="viewer", resource="pnl", action="read",
    )
    refresh = SimpleNamespace(report_date=REPORT_DATE, is_month_end=True, fi_rows=[], nonstd_rows_by_type={})
    monkeypatch.setattr(service, "load_latest_pnl_refresh_input", lambda **_kwargs: refresh)
    monkeypatch.setattr(routes, "_pnl_service", lambda: service)
    app = FastAPI()
    app.include_router(routes.router)

    def seed(*, fi=None, nonstd=None, fx_version=None):
        refresh.fi_rows = deepcopy(fi if fi is not None else [_fi()])
        refresh.nonstd_rows_by_type = deepcopy(nonstd if nonstd is not None else {})
        if fx_version is not None:
            with duckdb.connect(str(db)) as connection:
                connection.execute("""
                    create table fx_daily_mid (
                        trade_date varchar, base_currency varchar, quote_currency varchar,
                        mid_rate decimal(18, 8), source_name varchar, is_business_day boolean,
                        is_carry_forward boolean, source_version varchar, observed_trade_date varchar
                    )
                """)
                connection.execute(
                    "insert into fx_daily_mid values (?, 'USD', 'CNY', 7, 'synthetic', true, false, ?, ?)",
                    [REPORT_DATE, fx_version, REPORT_DATE],
                )
        receipt = task.materialize_pnl_facts.fn(
            report_date=REPORT_DATE, is_month_end=True,
            fi_rows=deepcopy(refresh.fi_rows), nonstd_rows_by_type=deepcopy(refresh.nonstd_rows_by_type),
            duckdb_path=str(db), governance_dir=str(governance),
            formal_pnl_enabled=True, formal_pnl_scope_json='["*"]',
        )
        assert receipt["status"] == "completed"
        return receipt

    with TestClient(app) as client:
        def request():
            # Input-loader test doubles have no file identity; exercise admission
            # independently of the separately covered byte-fingerprint cache.
            service.clear_pnl_v1_data_runtime_cache()
            return client.get("/api/pnl/v1-data", params={"date": REPORT_DATE})

        yield SimpleNamespace(
            seed=seed, request=request, refresh=refresh, db=db, service=service,
            repo=service.PnlRepository(str(db)),
        )
    service.clear_pnl_v1_data_runtime_cache()
    get_settings.cache_clear()


def test_v1_matching_sources_publish_supported_fi_and_nonstd_components(synthetic_v1):
    chain = synthetic_v1
    chain.seed(fi=[_fi(fair_value_change_516="3", capital_gain_517="10")], nonstd={
        "514": [_nonstd(raw_amount="106")], "517": [_nonstd(journal="517", raw_amount="20")],
    })
    response = chain.request()
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["result_meta"]["rule_version"] == "rv_pnl_phase2_materialize_v7"
    rows = {row["source"]: row for row in body["result"]["rows"]}
    for field, amount in {
        "interest_income": "100", "fair_value_change": "3", "capital_gain": "-9.43", "total_pnl": "93.57",
    }.items():
        assert Decimal(rows["FI"][field]).quantize(Decimal("0.01")) == Decimal(amount)
    assert Decimal(rows["NonStd"]["interest_income"]) == Decimal("100")
    assert Decimal(rows["NonStd"]["capital_gain"]) == Decimal("20")
    assert Decimal(rows["NonStd"]["total_pnl"]) == Decimal("120")


@pytest.mark.parametrize("portfolios", [("SYNTHETIC-DESK",), ("SYNTHETIC-DESK", "OTHER-DESK")])
def test_v1_nonstd_rounds_at_stored_cost_center_grain_before_portfolio_projection(synthetic_v1, portfolios):
    chain = synthetic_v1
    chain.seed(fi=[], nonstd={"514": [
        _nonstd(portfolio_name=portfolio, cost_center=cost_center)
        for portfolio in portfolios for cost_center in ("CC-1", "CC-2")
    ]})
    stored = chain.repo.fetch_nonstd_bridge_rows(REPORT_DATE)
    assert len(stored) == 2 * len(portfolios)
    assert all(row["total_pnl"] == Decimal("0.94339623") for row in stored)
    response = chain.request()
    assert response.status_code == 200, response.text
    rows = response.json()["result"]["rows"]
    assert {row["portfolio"] for row in rows} == set(portfolios)
    assert len(rows) == len(portfolios)
    assert all(Decimal(row["interest_income"]) == Decimal("1.88679246") for row in rows)
    assert all(Decimal(row["total_pnl"]) == Decimal("1.88679246") for row in rows)


def test_v1_nonstd_sums_entries_before_rounding_within_one_cost_center(synthetic_v1):
    chain = synthetic_v1
    chain.seed(fi=[], nonstd={"514": [_nonstd(), _nonstd()]})
    assert chain.repo.fetch_nonstd_bridge_rows(REPORT_DATE)[0]["total_pnl"] == Decimal("1.88679245")
    response = chain.request()
    assert response.status_code == 200, response.text
    assert Decimal(response.json()["result"]["rows"][0]["total_pnl"]) == Decimal("1.88679245")


@pytest.mark.parametrize("surface", ["fi", "nonstd"])
def test_v1_preserves_independently_stored_component_and_total_rounding(synthetic_v1, surface):
    chain = synthetic_v1
    if surface == "fi":
        chain.seed(fi=[_fi(interest_income_514="1", fair_value_change_516="0.000000005")])
        stored = chain.repo.fetch_formal_fi_rows(REPORT_DATE)[0]
    else:
        chain.seed(fi=[], nonstd={
            "514": [_nonstd()], "516": [_nonstd(journal="516", raw_amount="0.000000005")],
        })
        stored = chain.repo.fetch_nonstd_bridge_rows(REPORT_DATE)[0]
    assert stored["interest_income_514"] == Decimal("0.94339623")
    assert stored["fair_value_change_516"] == Decimal("0.00000001")
    assert stored["total_pnl"] == Decimal("0.94339623")
    response = chain.request()
    assert response.status_code == 200, response.text
    row = response.json()["result"]["rows"][0]
    assert Decimal(row["interest_income"]) == stored["interest_income_514"]
    assert Decimal(row["fair_value_change"]) == stored["fair_value_change_516"]
    assert Decimal(row["total_pnl"]) == stored["total_pnl"]


@pytest.mark.parametrize("surface", ["fi", "nonstd"])
def test_v1_rejects_offsetting_source_edits_at_distinct_formal_grains(synthetic_v1, surface):
    chain = synthetic_v1
    if surface == "fi":
        chain.seed(fi=[_fi("FIRST", interest_income_514="106"), _fi("SECOND", interest_income_514="212")])
        rows, field = chain.refresh.fi_rows, "interest_income_514"
    else:
        chain.seed(fi=[], nonstd={"514": [_nonstd(cost_center="CC-1", raw_amount="106"),
                                         _nonstd(cost_center="CC-2", raw_amount="212")]})
        rows, field = chain.refresh.nonstd_rows_by_type["514"], "raw_amount"
    assert chain.request().status_code == 200
    rows[0][field], rows[1][field] = "159", "159"
    response = chain.request()
    assert response.status_code == 503, response.text
    assert "source does not match" in response.json()["detail"]


@pytest.mark.parametrize("surface", ["fi", "nonstd"])
@pytest.mark.parametrize("change", ["missing", "extra", "duplicate", "version"])
def test_v1_requires_exact_source_population_and_version(synthetic_v1, surface, change):
    chain = synthetic_v1
    chain.seed(fi=[_fi()] if surface == "fi" else [],
               nonstd={} if surface == "fi" else {"514": [_nonstd()]})
    rows = chain.refresh.fi_rows if surface == "fi" else chain.refresh.nonstd_rows_by_type["514"]
    if change == "missing":
        rows.clear()
    elif change == "version":
        rows[0]["source_version"] = "sv_synthetic_replacement_same_amount"
    else:
        added = deepcopy(rows[0])
        if change == "extra":
            added["instrument_code" if surface == "fi" else "asset_code"] = "EXTRA"
        rows.append(added)
    response = chain.request()
    assert response.status_code == 503, response.text
    assert "source does not match" in response.json()["detail"]


@pytest.mark.parametrize("invest_type", ["H", "A"])
def test_v1_rejects_nonzero_516_when_formal_recognition_excludes_it(synthetic_v1, invest_type):
    chain = synthetic_v1
    chain.seed(fi=[_fi(invest_type_raw=invest_type, fair_value_change_516="5")])
    assert chain.repo.fetch_formal_fi_rows(REPORT_DATE)[0]["fair_value_change_516"] == Decimal("0")
    response = chain.request()
    assert response.status_code == 503, response.text
    assert "detail components differ" in response.json()["detail"]


def test_v1_rejects_legacy_rule_without_claiming_current_rule_compatibility(synthetic_v1):
    chain = synthetic_v1
    chain.seed()
    with duckdb.connect(str(chain.db)) as connection:
        connection.execute("update fact_formal_pnl_fi set rule_version = 'rv_pnl_phase2_materialize_v6'")
    response = chain.request()
    assert response.status_code == 503, response.text
    assert "Historical rule is unsupported" in response.json()["detail"]


def test_v1_rejects_nonstd_manual_amount_missing_from_its_display_components(synthetic_v1):
    chain = synthetic_v1
    chain.seed(fi=[], nonstd={
        "514": [_nonstd()], "adjustment": [_nonstd(journal="adjustment", raw_amount="1")],
    })
    response = chain.request()
    assert response.status_code == 503, response.text
    assert "detail components differ" in response.json()["detail"]


@pytest.mark.parametrize("missing", ["cost_center", "source_version"])
def test_v1_rejects_missing_source_comparison_evidence(synthetic_v1, missing):
    chain = synthetic_v1
    chain.seed()
    del chain.refresh.fi_rows[0][missing]
    response = chain.request()
    assert response.status_code == 503, response.text
    assert "source does not match" in response.json()["detail"]


def test_v1_fx_lineage_is_retained_and_numeric_reader_stays_compatible(synthetic_v1):
    chain = synthetic_v1
    chain.seed(fi=[_fi(fx_base_currency="USD")], fx_version="sv_synthetic_fx")
    assert chain.repo.fetch_formal_fx_rates_with_lineage(REPORT_DATE, {"USD"}) == {
        "USD": (Decimal("7"), "sv_synthetic_fx"),
    }
    assert chain.repo.fetch_formal_fx_rates(REPORT_DATE, {"USD"}) == {"USD": Decimal("7")}
    response = chain.request()
    assert response.status_code == 200, response.text
    assert Decimal(response.json()["result"]["rows"][0]["interest_income"]) == Decimal("700")
    assert set(chain.repo.fetch_formal_fi_rows(REPORT_DATE)[0]["source_version"].split("__")) == {
        "sv_synthetic_fi", "sv_synthetic_fx",
    }


@pytest.mark.parametrize("change", ["missing_lineage", "replacement_version", "missing_pnl_lineage"])
def test_v1_rejects_fx_or_pnl_lineage_gaps_without_changing_fx_number(synthetic_v1, change):
    chain = synthetic_v1
    chain.seed(fi=[_fi(fx_base_currency="USD")], fx_version="sv_synthetic_fx")
    if change == "missing_pnl_lineage":
        chain.refresh.fi_rows[0]["source_version"] = ""
    else:
        version = "" if change == "missing_lineage" else "sv_synthetic_new_fx"
        with duckdb.connect(str(chain.db)) as connection:
            connection.execute("update fx_daily_mid set source_version = ?", [version])
    response = chain.request()
    assert response.status_code == 503, response.text
    assert "source does not match" in response.json()["detail"]
