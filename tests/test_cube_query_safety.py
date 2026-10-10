"""Corrections to landed Cube reads; these guards do not promote formal use."""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.routes import cube_query as route
from backend.app.schemas.cube_query import CubeQueryRequest
from backend.app.security.auth_context import AuthContext, get_auth_context
from backend.app.services.analytical_bridge_service import AnalyticalBridgeService

pytestmark = pytest.mark.excluded_surface_regression


@pytest.fixture
def cube_db():
    conn = duckdb.connect(":memory:")
    for name in ("05_balance_analysis.sql", "08_product_category_pnl.sql"):
        for sql in Path("backend/app/schema_registry/duckdb", name).read_text(encoding="utf-8").split("-- MOSS:STMT"):
            if sql.strip():
                conn.execute(sql)
    conn.executemany(
        "insert into fact_formal_zqtz_balance_daily "
        "(report_date,instrument_code,currency_basis,currency_code,rating,market_value_amount,source_version,rule_version) "
        "values (?,?,?,?,?,?,?,?)",
        [
            ("2026-03-31", "CNY-BOND", "native", "CNY", "AAA", 100, "sv_native", "rv_native"),
            ("2026-03-31", "CNY-BOND", "CNY", "CNY", "AAA", 100, "sv_cny", "rv_cny"),
            ("2026-03-31", "USD-BOND", "native", "USD", "NATIVE-ONLY", 7, "sv_native", "rv_native"),
            ("2026-03-31", "USD-BOND", "CNY", "USD", "AA", 50, "sv_cny", "rv_cny"),
        ],
    )
    conn.executemany(
        "insert into product_category_pnl_formal_read_model "
        "(report_date,view,category_id,category_name,side,level,business_net_income,is_total,children_json,source_version,rule_version) "
        "values (?,?,?,?,?,?,?,?,?,?,?)",
        [
            ("2026-03-31", view, category, category, "asset", level, income * scale, False, children, "sv_" + view, "rv_category")
            for view, scale in (("monthly", 1), ("qtd", 3), ("ytd", 9), ("year_to_report_month_end", 9))
            for category, level, income, children in (
                ("bond_investment", 0, 10, '["bond_ac"]'),
                ("bond_ac", 1, 10, "[]"),
                ("derivatives", 0, 5, "[]"),
            )
        ],
    )
    yield conn
    conn.close()


def _client(monkeypatch, conn=None, *, error=None):
    class Repo:
        def fetchall(self, sql, params=None):
            if error is not None:
                raise error
            return conn.execute(sql, list(params or [])).fetchall()

    settings = SimpleNamespace(duckdb_path=":memory:")
    app = FastAPI()
    app.include_router(route.router)
    app.dependency_overrides[get_auth_context] = lambda: AuthContext(user_id="cube-guard", role="viewer", identity_source="test")
    app.dependency_overrides[route.get_settings] = lambda: settings
    monkeypatch.setattr(route, "_ensure_cube_read_allowed", lambda auth: None)
    monkeypatch.setattr(route, "AnalyticalBridgeService", lambda: AnalyticalBridgeService(repo_factory=lambda _: Repo()))
    return TestClient(app, raise_server_exceptions=False)


def _query(fact="balance", **overrides):
    payload = {
        "report_date": "2026-03-31", "fact_table": fact, "basis": "analytical",
        "measures": ["sum(market_value)" if fact == "balance" else "sum(business_net_income)"],
        "filters": {"currency_basis": ["CNY"]} if fact == "balance" else {"view": ["monthly"], "category_id": ["bond_investment"]},
    }
    return {**payload, **overrides}


def test_balance_rows_count_lineage_and_drill_keep_single_cny_basis(cube_db, monkeypatch):
    client = _client(monkeypatch, cube_db)
    result = client.post("/api/cube/query", json=_query(dimensions=["currency_basis", "rating"], measures=["sum(market_value)", "count(*)"] ))
    assert result.status_code == 200, result.text
    body = result.json()
    assert sum(Decimal(row["market_value"]) for row in body["rows"]) == 150
    assert sum(row["count"] for row in body["rows"]) == 2
    assert body["total_rows"] == 2
    assert body["result_meta"]["evidence_rows"] == 2
    assert body["result_meta"]["source_version"] == "sv_cny"
    assert body["result_meta"]["rule_version"] == "rv_cny"
    assert body["result_meta"]["filters_applied"] == {"currency_basis": ["CNY"]}
    assert body["result_meta"]["amount_currency_basis"] == "CNY"
    paths = {row["dimension"]: row["available_values"] for row in body["drill_paths"]}
    assert paths == {"currency_basis": ["CNY"], "rating": ["AA", "AAA"]}
    filtered = client.post("/api/cube/query", json=_query(filters={"currency_basis": ["CNY"], "rating": ["AAA"]})).json()
    assert Decimal(filtered["rows"][0]["market_value"]) == 100


@pytest.mark.parametrize("values", [None, [], ["native"], ["CNY", "native"], ["CNY", "CNY"], ["CNY", ""]])
def test_balance_rejects_missing_or_non_single_cny_basis(monkeypatch, values):
    filters = {} if values is None else {"currency_basis": values}
    response = _client(monkeypatch, error=AssertionError("must validate before querying")).post("/api/cube/query", json=_query(filters=filters))
    assert response.status_code == 400
    assert "currency_basis" in response.json()["detail"]


@pytest.mark.parametrize("category,expected", [("bond_investment", 10), ("bond_ac", 10), ("derivatives", 5)])
def test_product_reads_one_preaggregated_category_without_parent_or_period_overlap(cube_db, monkeypatch, category, expected):
    response = _client(monkeypatch, cube_db).post("/api/cube/query", json=_query("product_category", dimensions=["category_id", "view"], filters={"view": ["monthly"], "category_id": [category]}))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_rows"] == 1
    assert Decimal(body["rows"][0]["business_net_income"]) == expected
    assert body["result_meta"]["formal_use_allowed"] is False
    assert body["result_meta"]["source_version"] == "sv_monthly"
    assert {row["dimension"]: row["available_values"] for row in body["drill_paths"]} == {"category_id": [category], "view": ["monthly"]}


@pytest.mark.parametrize("filters", [
    {}, {"category_id": ["bond_ac"]}, {"view": ["monthly"]},
    {"view": ["monthly", "qtd"], "category_id": ["bond_ac"]},
    {"view": ["unknown"], "category_id": ["bond_ac"]},
    {"view": ["monthly"], "category_id": ["bond_investment", "bond_ac"]},
    {"view": ["monthly"], "category_id": ["unknown"]},
])
def test_product_rejects_unconfirmed_period_or_category_sets(monkeypatch, filters):
    response = _client(monkeypatch, error=AssertionError("must validate before querying")).post("/api/cube/query", json=_query("product_category", filters=filters))
    assert response.status_code == 400


@pytest.mark.parametrize("measure", ["sum(weighted_yield)", "avg(business_net_income)", "count(*)"])
def test_product_rejects_measures_outside_landed_preaggregate_contract(monkeypatch, measure):
    response = _client(monkeypatch, error=AssertionError("must validate before querying")).post("/api/cube/query", json=_query("product_category", measures=[measure]))
    assert response.status_code == 400


def test_product_duplicate_read_model_rows_are_unavailable(cube_db, monkeypatch):
    cube_db.execute("insert into product_category_pnl_formal_read_model select * from product_category_pnl_formal_read_model where view='monthly' and category_id='bond_ac'")
    response = _client(monkeypatch, cube_db).post("/api/cube/query", json=_query("product_category", filters={"view": ["monthly"], "category_id": ["bond_ac"]}))
    assert response.status_code == 503


@pytest.mark.parametrize("fact", ["balance", "product_category"])
def test_affected_formal_requests_remain_not_promoted(monkeypatch, fact):
    response = _client(monkeypatch, error=AssertionError("formal request must not query")).post("/api/cube/query", json=_query(fact, basis="formal"))
    assert response.status_code == 503
    assert "not promoted" in response.json()["detail"]


@pytest.mark.parametrize("dimensions", [[], ["portfolio"]])
@pytest.mark.parametrize("error", [RuntimeError("synthetic storage unavailable"), OSError("synthetic permission denied"), duckdb.IOException("synthetic storage unavailable")])
def test_ledger_storage_failure_is_503_with_or_without_dimensions(monkeypatch, dimensions, error):
    response = _client(monkeypatch, error=error).post("/api/cube/query", json=_query(basis="ledger", measures=["sum(fair_value)"], filters={}, dimensions=dimensions))
    assert response.status_code == 503


@pytest.mark.parametrize("dimensions", [[], ["portfolio"]])
def test_ledger_real_empty_table_stops_before_drill(monkeypatch, dimensions):
    class EmptyRepo:
        def fetchall(self, sql, params=None):
            assert "select count(*)" in sql, "empty query must not enter drill"
            return [(0,)]
    bridge = AnalyticalBridgeService(repo_factory=lambda _: EmptyRepo())
    response = bridge.execute(CubeQueryRequest(**_query(basis="ledger", measures=["sum(fair_value)"], filters={}, dimensions=dimensions)), ":memory:", auth=AuthContext(user_id="cube-guard", role="viewer", identity_source="test"))
    assert response.rows == []
    assert response.total_rows == 0
    assert response.drill_paths == []
    assert response.result_meta.quality_flag == "warning"


@pytest.mark.parametrize("dimensions", [[], ["portfolio"]])
def test_ledger_missing_table_is_explicitly_unavailable(cube_db, monkeypatch, dimensions):
    response = _client(monkeypatch, cube_db).post("/api/cube/query", json=_query(basis="ledger", measures=["sum(fair_value)"], filters={}, dimensions=dimensions))
    assert response.status_code == 503
    assert "not initialized" in response.json()["detail"]


@pytest.mark.parametrize("dimensions", [[], ["portfolio"]])
def test_ledger_empty_real_ddl_returns_empty_instead_of_storage_error(cube_db, monkeypatch, dimensions):
    for sql in Path("backend/app/schema_registry/duckdb/19_ledger_import.sql").read_text(encoding="utf-8").split("-- MOSS:STMT"):
        if sql.strip():
            cube_db.execute(sql)
    response = _client(monkeypatch, cube_db).post("/api/cube/query", json=_query(basis="ledger", measures=["sum(fair_value)"], filters={}, dimensions=dimensions))
    assert response.status_code == 200
    assert response.json()["rows"] == []
    assert response.json()["total_rows"] == 0
    assert response.json()["result_meta"]["quality_flag"] == "warning"


@pytest.mark.parametrize("value", [None, Decimal("0")])
def test_product_preaggregated_read_preserves_null_and_zero(cube_db, monkeypatch, value):
    cube_db.execute("update product_category_pnl_formal_read_model set business_net_income=? where category_id='bond_investment' and view='monthly'", [value])
    response = _client(monkeypatch, cube_db).post("/api/cube/query", json=_query("product_category"))
    assert response.status_code == 200
    actual = response.json()["rows"][0]["business_net_income"]
    assert actual is None if value is None else Decimal(actual) == 0


def test_missing_ledger_table_remains_identifiable_through_real_repository(tmp_path):
    path = tmp_path / "uninitialized.duckdb"
    duckdb.connect(str(path)).close()
    with pytest.raises(RuntimeError, match="not initialized"):
        AnalyticalBridgeService().execute(
            CubeQueryRequest(**_query(basis="ledger", measures=["sum(fair_value)"], filters={})), str(path),
            auth=AuthContext(user_id="cube-guard", role="viewer", identity_source="test"),
        )
