from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import duckdb
from backend.app.governance.settings import get_settings
from backend.app.repositories.user_scope_repo import UserScopeRepository
from backend.app.security.auth_context import ROLE_HEADER_TRUST_ENV
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.helpers import load_module
from tests.test_bond_analytics_materialize_flow import REPORT_DATE
from tests.test_bond_analytics_service import _configure_and_materialize
from tests.test_risk_tensor_service import (
    _configure_and_materialize_degraded_snapshot,
    _configure_and_materialize_risk_tensor,
    _configure_and_materialize_risk_tensor_with_tyw_liability,
)

RISK_TENSOR_READ_HEADERS = {"X-User-Id": "risk-tensor-read-user", "X-User-Role": "viewer"}


def _risk_tensor_scope_repo(tmp_path: Path, monkeypatch) -> UserScopeRepository:
    sqlite_path = tmp_path / "risk-tensor-read-scope.db"
    dsn = f"sqlite:///{sqlite_path.as_posix()}"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", dsn)
    monkeypatch.setenv("MOSS_GOVERNANCE_SQL_DSN", "")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    return UserScopeRepository(dsn)


def _grant_risk_tensor_read(tmp_path: Path, monkeypatch) -> None:
    _risk_tensor_scope_repo(tmp_path, monkeypatch).grant_scope(
        user_id="*",
        role=None,
        resource="risk_tensor",
        action="read",
    )


def _risk_tensor_client(tmp_path: Path, monkeypatch, *, raise_server_exceptions: bool = True) -> TestClient:
    _grant_risk_tensor_read(tmp_path, monkeypatch)
    client = TestClient(
        load_module("backend.app.main", "backend/app/main.py").app,
        raise_server_exceptions=raise_server_exceptions,
    )
    client.headers.update(RISK_TENSOR_READ_HEADERS)
    return client


def test_risk_tensor_read_surfaces_require_explicit_read_scope(tmp_path: Path, monkeypatch) -> None:
    route_module = load_module(
        "backend.app.api.routes.risk_tensor",
        "backend/app/api/routes/risk_tensor.py",
    )
    monkeypatch.setattr(
        route_module,
        "risk_tensor_dates_envelope",
        lambda **_kwargs: {"result_meta": {"result_kind": "risk.tensor.dates"}, "result": {}},
    )
    monkeypatch.setattr(
        route_module,
        "risk_tensor_envelope",
        lambda **_kwargs: {"result_meta": {"result_kind": "risk.tensor"}, "result": {}},
    )
    monkeypatch.setattr(
        route_module,
        "risk_scenario_stress_envelope",
        lambda **_kwargs: {"result_meta": {"result_kind": "risk.tensor.scenario_stress"}, "result": {}},
    )
    _risk_tensor_scope_repo(tmp_path, monkeypatch)
    app = FastAPI()
    app.include_router(route_module.router)
    client = TestClient(app)

    for path, params in (
        ("/api/risk/tensor/dates", {}),
        ("/api/risk/tensor", {"report_date": REPORT_DATE}),
        ("/api/risk/scenario-stress", {"report_date": REPORT_DATE}),
    ):
        response = client.get(path, params=params or None, headers=RISK_TENSOR_READ_HEADERS)
        assert response.status_code == 403, f"{path}: {response.status_code} {response.text}"


def test_risk_tensor_api_returns_formal_envelope(tmp_path, monkeypatch):
    _configure_and_materialize_risk_tensor(tmp_path, monkeypatch)

    client = _risk_tensor_client(tmp_path, monkeypatch)
    response = client.get(
        "/api/risk/tensor",
        params={"report_date": REPORT_DATE},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["basis"] == "formal"
    assert payload["result_meta"]["result_kind"] == "risk.tensor"
    assert payload["result_meta"]["formal_use_allowed"] is True
    assert payload["result_meta"]["quality_flag"] == "ok"
    assert payload["result"]["report_date"] == REPORT_DATE
    assert payload["result"]["bond_count"] == 3
    assert isinstance(payload["result"]["portfolio_dv01"], dict)
    assert isinstance(payload["result"]["regulatory_dv01"], dict)
    assert isinstance(payload["result"]["cs01"], dict)
    assert isinstance(payload["result"]["portfolio_convexity"], dict)
    assert payload["result"]["portfolio_dv01"]["unit"] == "dv01"
    assert payload["result"]["regulatory_dv01"]["unit"] == "dv01"
    assert payload["result"]["regulatory_dv01"]["raw"] == payload["result"]["portfolio_dv01"]["raw"]
    assert payload["result"]["asset_cashflow_30d"]["raw"] == 14.0
    assert payload["result"]["liability_cashflow_30d"]["raw"] == 0.0
    assert (
        Decimal(str(payload["result"]["liquidity_gap_30d"]["raw"]))
        == Decimal(str(payload["result"]["asset_cashflow_30d"]["raw"]))
        - Decimal(str(payload["result"]["liability_cashflow_30d"]["raw"]))
    )

    get_settings.cache_clear()


def test_risk_tensor_api_503_preserves_structured_result_meta(tmp_path, monkeypatch):
    route_module = load_module(
        "backend.app.api.routes.risk_tensor",
        "backend/app/api/routes/risk_tensor.py",
    )
    monkeypatch.setattr(
        route_module,
        "risk_tensor_envelope",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("materialized fact unavailable")),
    )
    client = _risk_tensor_client(tmp_path, monkeypatch, raise_server_exceptions=False)

    response = client.get("/api/risk/tensor", params={"report_date": REPORT_DATE})

    assert response.status_code == 503
    payload = response.json()
    assert payload["result_meta"]["basis"] == "formal"
    assert payload["result_meta"]["result_kind"] == "risk.tensor"
    assert payload["result_meta"]["source_surface"] == "risk_tensor"
    assert payload["result_meta"]["requested_report_date"] == REPORT_DATE
    assert payload["result_meta"]["quality_flag"] == "error"
    assert payload["result"]["readiness"] == "unavailable"


def test_risk_scenario_stress_api_returns_scenario_envelope(tmp_path, monkeypatch):
    _configure_and_materialize_risk_tensor(tmp_path, monkeypatch)

    client = _risk_tensor_client(tmp_path, monkeypatch)
    response = client.get(
        "/api/risk/scenario-stress",
        params={"report_date": REPORT_DATE},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["basis"] == "scenario"
    assert payload["result_meta"]["result_kind"] == "risk.tensor.scenario_stress"
    assert payload["result_meta"]["formal_use_allowed"] is False
    assert payload["result_meta"]["scenario_flag"] is True
    assert payload["result"]["basis"] == "scenario"
    assert payload["result"]["scenario_set_id"] == "standard_risk_tensor_scenario_v1"
    assert payload["result"]["rule_version"] == "rv_risk_tensor_scenario_stress_v1"
    assert payload["result"]["source"]["result_kind"] == "risk.tensor"
    assert payload["result"]["source"]["rule_version"] == "rv_risk_tensor_formal_materialize_v3"
    assert payload["result"]["summary"]["scenario_count"] == 4
    assert payload["result"]["summary"]["available_count"] == 3
    assert payload["result"]["summary"]["review_required_count"] == 4
    assert payload["result"]["warnings"]
    assert payload["result"]["source_warnings"] == []
    assert {row["category"] for row in payload["result"]["scenarios"]} == {
        "rate",
        "credit",
        "liquidity",
        "fx",
    }
    assert all(row["human_review_required"] is True for row in payload["result"]["scenarios"])
    required_row_fields = {
        "scenario_key",
        "category",
        "label",
        "source_field",
        "shock",
        "estimated_impact",
        "measure",
        "calculation",
        "interpretation",
        "data_status",
        "human_review_required",
    }
    assert all(required_row_fields <= set(row) for row in payload["result"]["scenarios"])
    rate_scenario = next(row for row in payload["result"]["scenarios"] if row["category"] == "rate")
    assert rate_scenario["shock"]["raw"] == 10.0
    assert rate_scenario["estimated_impact"]["raw"] is not None

    get_settings.cache_clear()


def test_risk_tensor_api_returns_available_report_dates(tmp_path, monkeypatch):
    _configure_and_materialize_risk_tensor(tmp_path, monkeypatch)

    client = _risk_tensor_client(tmp_path, monkeypatch)
    response = client.get("/api/risk/tensor/dates")

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["basis"] == "formal"
    assert payload["result_meta"]["result_kind"] == "risk.tensor.dates"
    assert payload["result_meta"]["formal_use_allowed"] is True
    assert payload["result_meta"]["requested_report_date"] == REPORT_DATE
    assert payload["result_meta"]["resolved_report_date"] == REPORT_DATE
    assert payload["result_meta"]["as_of_date"] == REPORT_DATE
    assert payload["result"]["report_dates"] == [REPORT_DATE]

    get_settings.cache_clear()


def test_risk_tensor_api_returns_404_for_absent_report_date(tmp_path, monkeypatch):
    _configure_and_materialize_risk_tensor(tmp_path, monkeypatch)

    client = _risk_tensor_client(tmp_path, monkeypatch, raise_server_exceptions=False)
    response = client.get(
        "/api/risk/tensor",
        params={"report_date": "2026-04-30"},
    )

    assert response.status_code == 404
    assert "No risk tensor data found" in response.json()["detail"]

    get_settings.cache_clear()


def test_risk_tensor_api_returns_503_when_upstream_exists_but_downstream_fact_is_missing(tmp_path, monkeypatch):
    _configure_and_materialize(tmp_path, monkeypatch)

    client = _risk_tensor_client(tmp_path, monkeypatch, raise_server_exceptions=False)
    response = client.get(
        "/api/risk/tensor",
        params={"report_date": REPORT_DATE},
    )

    assert response.status_code == 503
    assert "Risk tensor fact missing" in response.json()["result"]["error"]

    get_settings.cache_clear()


def test_risk_tensor_api_returns_503_when_downstream_fact_is_stale_against_newer_upstream_lineage(tmp_path, monkeypatch):
    duckdb_path, governance_dir, _task_mod = _configure_and_materialize_risk_tensor(tmp_path, monkeypatch)

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            update zqtz_bond_daily_snapshot
            set source_version = ?
            where report_date = ?
              and instrument_code = 'CB-001'
            """,
            ["sv_bond_snap_2", REPORT_DATE],
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

    client = _risk_tensor_client(tmp_path, monkeypatch, raise_server_exceptions=False)
    response = client.get(
        "/api/risk/tensor",
        params={"report_date": REPORT_DATE},
    )

    assert response.status_code == 503
    assert "Risk tensor stale against bond analytics lineage" in response.json()["result"]["error"]

    get_settings.cache_clear()


def test_risk_tensor_api_returns_non_empty_degraded_tensor_when_materialized_snapshot_rows_are_partial(tmp_path, monkeypatch):
    _configure_and_materialize_degraded_snapshot(tmp_path, monkeypatch)

    client = _risk_tensor_client(tmp_path, monkeypatch)
    response = client.get(
        "/api/risk/tensor",
        params={"report_date": REPORT_DATE},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["basis"] == "formal"
    assert payload["result_meta"]["quality_flag"] == "warning"
    assert payload["result"]["bond_count"] == 3
    assert payload["result"]["quality_flag"] == "warning"
    assert any("Non-standard tenor buckets remapped" in warning for warning in payload["result"]["warnings"])
    assert any("without maturity_date" in warning for warning in payload["result"]["warnings"])

    get_settings.cache_clear()


def test_risk_tensor_api_returns_503_when_downstream_fact_is_stale_against_newer_tyw_liability_lineage(tmp_path, monkeypatch):
    duckdb_path, governance_dir, _task_mod = _configure_and_materialize_risk_tensor_with_tyw_liability(tmp_path, monkeypatch)

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            update fact_formal_tyw_balance_daily
            set source_version = ?
            where report_date = ?
              and position_id = 'TYW-L-1'
            """,
            ["sv_tyw_liab_2", REPORT_DATE],
        )
    finally:
        conn.close()

    client = _risk_tensor_client(tmp_path, monkeypatch, raise_server_exceptions=False)
    response = client.get(
        "/api/risk/tensor",
        params={"report_date": REPORT_DATE},
    )

    assert response.status_code == 503
    assert "Risk tensor stale against TYW liability lineage" in response.json()["result"]["error"]

    get_settings.cache_clear()


def test_risk_tensor_api_returns_503_when_downstream_fact_is_stale_against_newer_tyw_liability_rule_version(tmp_path, monkeypatch):
    duckdb_path, governance_dir, _task_mod = _configure_and_materialize_risk_tensor_with_tyw_liability(tmp_path, monkeypatch)

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            update fact_formal_tyw_balance_daily
            set rule_version = ?
            where report_date = ?
              and position_id = 'TYW-L-1'
            """,
            ["rv_balance_analysis_formal_materialize_v2", REPORT_DATE],
        )
    finally:
        conn.close()

    client = _risk_tensor_client(tmp_path, monkeypatch, raise_server_exceptions=False)
    response = client.get(
        "/api/risk/tensor",
        params={"report_date": REPORT_DATE},
    )

    assert response.status_code == 503
    assert "Risk tensor stale against TYW liability lineage" in response.json()["result"]["error"]

    get_settings.cache_clear()


def test_risk_tensor_api_rejects_invalid_report_date(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    client = TestClient(
        load_module("backend.app.main", "backend/app/main.py").app,
        raise_server_exceptions=False,
    )
    response = client.get(
        "/api/risk/tensor",
        params={"report_date": "2026-99-99"},
    )

    assert response.status_code == 422
    assert "Invalid report_date" in response.json()["detail"]

    get_settings.cache_clear()
