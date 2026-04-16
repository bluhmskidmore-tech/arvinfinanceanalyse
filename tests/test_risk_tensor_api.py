from __future__ import annotations

from decimal import Decimal

import duckdb
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from tests.helpers import load_module
from tests.test_bond_analytics_materialize_flow import REPORT_DATE
from tests.test_bond_analytics_service import _configure_and_materialize
from tests.test_risk_tensor_service import (
    _configure_and_materialize_degraded_snapshot,
    _configure_and_materialize_risk_tensor,
    _configure_and_materialize_risk_tensor_with_tyw_liability,
)


def test_risk_tensor_api_returns_formal_envelope(tmp_path, monkeypatch):
    _configure_and_materialize_risk_tensor(tmp_path, monkeypatch)

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
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
    assert isinstance(payload["result"]["portfolio_dv01"], str)
    assert isinstance(payload["result"]["cs01"], str)
    assert isinstance(payload["result"]["portfolio_convexity"], str)
    assert len(payload["result"]["portfolio_dv01"].split(".")[1]) == 8
    assert payload["result"]["asset_cashflow_30d"] == "14.00000000"
    assert payload["result"]["liability_cashflow_30d"] == "0.00000000"
    assert (
        Decimal(payload["result"]["liquidity_gap_30d"])
        == Decimal(payload["result"]["asset_cashflow_30d"])
        - Decimal(payload["result"]["liability_cashflow_30d"])
    )

    get_settings.cache_clear()


def test_risk_tensor_api_returns_available_report_dates(tmp_path, monkeypatch):
    _configure_and_materialize_risk_tensor(tmp_path, monkeypatch)

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/risk/tensor/dates")

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["basis"] == "formal"
    assert payload["result_meta"]["result_kind"] == "risk.tensor.dates"
    assert payload["result_meta"]["formal_use_allowed"] is True
    assert payload["result"]["report_dates"] == [REPORT_DATE]

    get_settings.cache_clear()


def test_risk_tensor_api_returns_404_for_absent_report_date(tmp_path, monkeypatch):
    _configure_and_materialize_risk_tensor(tmp_path, monkeypatch)

    client = TestClient(
        load_module("backend.app.main", "backend/app/main.py").app,
        raise_server_exceptions=False,
    )
    response = client.get(
        "/api/risk/tensor",
        params={"report_date": "2026-04-30"},
    )

    assert response.status_code == 404
    assert "No risk tensor data found" in response.json()["detail"]

    get_settings.cache_clear()


def test_risk_tensor_api_returns_503_when_upstream_exists_but_downstream_fact_is_missing(tmp_path, monkeypatch):
    _configure_and_materialize(tmp_path, monkeypatch)

    client = TestClient(
        load_module("backend.app.main", "backend/app/main.py").app,
        raise_server_exceptions=False,
    )
    response = client.get(
        "/api/risk/tensor",
        params={"report_date": REPORT_DATE},
    )

    assert response.status_code == 503
    assert "Risk tensor fact missing" in response.json()["detail"]

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

    client = TestClient(
        load_module("backend.app.main", "backend/app/main.py").app,
        raise_server_exceptions=False,
    )
    response = client.get(
        "/api/risk/tensor",
        params={"report_date": REPORT_DATE},
    )

    assert response.status_code == 503
    assert "Risk tensor stale against bond analytics lineage" in response.json()["detail"]

    get_settings.cache_clear()


def test_risk_tensor_api_returns_non_empty_degraded_tensor_when_materialized_snapshot_rows_are_partial(tmp_path, monkeypatch):
    _configure_and_materialize_degraded_snapshot(tmp_path, monkeypatch)

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
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
    assert any("Unsupported tenor buckets" in warning for warning in payload["result"]["warnings"])
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

    client = TestClient(
        load_module("backend.app.main", "backend/app/main.py").app,
        raise_server_exceptions=False,
    )
    response = client.get(
        "/api/risk/tensor",
        params={"report_date": REPORT_DATE},
    )

    assert response.status_code == 503
    assert "Risk tensor stale against TYW liability lineage" in response.json()["detail"]

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

    client = TestClient(
        load_module("backend.app.main", "backend/app/main.py").app,
        raise_server_exceptions=False,
    )
    response = client.get(
        "/api/risk/tensor",
        params={"report_date": REPORT_DATE},
    )

    assert response.status_code == 503
    assert "Risk tensor stale against TYW liability lineage" in response.json()["detail"]

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
