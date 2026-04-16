from __future__ import annotations

"""
Agent HTTP + schema contracts.

Production default (`agent_enabled=False`): `POST /api/agent/query` returns **503** with
`AgentDisabledResponse` — not a live Agent. Tests that return 200 use an isolated FastAPI
app with `agent_enabled` stubbed True to exercise envelope/schema only.
"""

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.main import app as default_app
from tests.helpers import load_module


def _sample_agent_envelope():
    schema_module = load_module(
        "backend.app.agent.schemas.agent_response",
        "backend/app/agent/schemas/agent_response.py",
    )
    return schema_module.AgentEnvelope(
        answer="PnL summary is available.",
        cards=[
            schema_module.AgentCard(
                type="metric",
                title="Total PnL",
                value="123.45",
            )
        ],
        evidence=schema_module.AgentEvidence(
            tables_used=["fact_formal_pnl_fi"],
            filters_applied={
                "report_date": "2026-03-31",
                "report_date_resolution": "latest_default",
            },
            evidence_rows=2,
            quality_flag="ok",
        ),
        result_meta=schema_module.AgentResultMeta(
            trace_id="tr_agent_api_contract",
            basis="formal",
            result_kind="agent.pnl_summary",
            formal_use_allowed=True,
            source_version="sv_agent_test",
            vendor_version="vv_none",
            rule_version="rv_agent_mvp_v1",
            cache_version="cv_agent_pnl_summary_v1",
            quality_flag="ok",
            scenario_flag=False,
            tables_used=["fact_formal_pnl_fi"],
            filters_applied={
                "report_date": "2026-03-31",
                "report_date_resolution": "latest_default",
            },
            sql_executed=[],
            evidence_rows=2,
        ),
    )


def _client_with_stubbed_agent(monkeypatch):
    route_module = load_module(
        "backend.app.api.routes.agent",
        "backend/app/api/routes/agent.py",
    )
    monkeypatch.setattr(
        route_module,
        "get_settings",
        lambda: type(
            "SettingsStub",
            (),
            {
                "agent_enabled": True,
                "duckdb_path": "test.duckdb",
                "governance_path": "test-governance",
            },
        )(),
    )
    monkeypatch.setattr(
        route_module,
        "execute_agent_query",
        lambda request, duckdb_path, governance_dir: _sample_agent_envelope(),
    )
    app = FastAPI()
    app.include_router(route_module.router)
    return TestClient(app)


def test_default_app_agent_query_is_phase1_disabled_stub_503():
    """Unmocked app: Agent remains off by default (see `Settings.agent_enabled`)."""
    client = TestClient(default_app)
    response = client.post("/api/agent/query", json={"question": "PnL summary"})

    assert response.status_code == 503
    body = response.json()
    assert body["enabled"] is False
    assert body["phase"] == "phase1"
    assert "disabled" in body["detail"].lower()


def test_agent_request_schema_defines_phase1_contract():
    module = load_module(
        "backend.app.agent.schemas.agent_request",
        "backend/app/agent/schemas/agent_request.py",
    )
    request_model = getattr(module, "AgentQueryRequest", None)
    assert request_model is not None

    fields = set(request_model.model_fields)
    assert {
        "question",
        "basis",
        "filters",
        "position_scope",
        "currency_basis",
        "context",
    } <= fields


def test_agent_response_schema_exposes_target_state_and_disabled_contracts():
    module = load_module(
        "backend.app.agent.schemas.agent_response",
        "backend/app/agent/schemas/agent_response.py",
    )
    assert getattr(module, "AgentEnvelope", None) is not None
    assert getattr(module, "AgentResultMeta", None) is not None
    disabled = getattr(module, "AgentDisabledResponse", None)
    assert disabled is not None
    assert {"enabled", "phase", "detail"} <= set(disabled.model_fields)


def test_agent_query_returns_200_with_envelope(monkeypatch, tmp_path):
    client = _client_with_stubbed_agent(monkeypatch)
    response = client.post("/api/agent/query", json={"question": "PnL summary"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "PnL summary is available."
    assert payload["cards"][0]["title"] == "Total PnL"

def test_agent_query_envelope_has_evidence(monkeypatch, tmp_path):
    client = _client_with_stubbed_agent(monkeypatch)
    response = client.post("/api/agent/query", json={"question": "PnL summary"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["evidence"]["tables_used"] == ["fact_formal_pnl_fi"]
    assert payload["evidence"]["filters_applied"] == {
        "report_date": "2026-03-31",
        "report_date_resolution": "latest_default",
    }
    assert payload["evidence"]["evidence_rows"] == 2

def test_agent_query_envelope_has_result_meta(monkeypatch, tmp_path):
    client = _client_with_stubbed_agent(monkeypatch)
    response = client.post("/api/agent/query", json={"question": "PnL summary"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["trace_id"] == "tr_agent_api_contract"
    assert payload["result_meta"]["result_kind"] == "agent.pnl_summary"
    assert payload["result_meta"]["tables_used"] == ["fact_formal_pnl_fi"]
    assert payload["result_meta"]["evidence_rows"] == 2

def test_agent_query_returns_disabled_fallback_when_agent_is_off(monkeypatch, tmp_path):
    route_module = load_module(
        "backend.app.api.routes.agent",
        "backend/app/api/routes/agent.py",
    )
    monkeypatch.setattr(
        route_module,
        "get_settings",
        lambda: type(
            "SettingsStub",
            (),
            {
                "agent_enabled": False,
                "duckdb_path": str(tmp_path / "moss.duckdb"),
                "governance_path": str(tmp_path / "governance"),
            },
        )(),
    )
    app = FastAPI()
    app.include_router(route_module.router)
    client = TestClient(app)
    response = client.post("/api/agent/query", json={"question": "PnL summary"})

    assert response.status_code == 503
    assert response.json() == {
        "enabled": False,
        "phase": "phase1",
        "detail": "Agent endpoint is planned but disabled in Phase 1.",
    }
def test_disabled_agent_query_appends_audit_log(monkeypatch, tmp_path):
    route_module = load_module(
        "backend.app.api.routes.agent",
        "backend/app/api/routes/agent.py",
    )
    monkeypatch.setattr(
        route_module,
        "get_settings",
        lambda: type(
            "SettingsStub",
            (),
            {
                "agent_enabled": False,
                "duckdb_path": str(tmp_path / "moss.duckdb"),
                "governance_path": str(tmp_path / "governance"),
            },
        )(),
    )
    app = FastAPI()
    app.include_router(route_module.router)
    client = TestClient(app)
    response = client.post("/api/agent/query", json={"question": "PnL summary"})

    assert response.status_code == 503
    content = (tmp_path / "governance" / "agent_audit.jsonl").read_text(encoding="utf-8")
    payload = json.loads(content.splitlines()[-1])
    assert payload["query_text"] == "PnL summary"
    assert payload["tools_used"] == ["agent_disabled"]
    assert payload["result_meta"]["result_kind"] == "agent.disabled"


def test_agent_query_returns_404_with_detail_when_executor_raises_value_error(monkeypatch):
    route_module = load_module(
        "backend.app.api.routes.agent",
        "backend/app/api/routes/agent.py",
    )
    monkeypatch.setattr(
        route_module,
        "get_settings",
        lambda: type(
            "SettingsStub",
            (),
            {
                "agent_enabled": True,
                "duckdb_path": "test.duckdb",
                "governance_path": "test-governance",
            },
        )(),
    )
    monkeypatch.setattr(
        route_module,
        "execute_agent_query",
        lambda request, duckdb_path, governance_dir: (_ for _ in ()).throw(
            ValueError("No agent data found.")
        ),
    )
    app = FastAPI()
    app.include_router(route_module.router)
    client = TestClient(app)

    response = client.post("/api/agent/query", json={"question": "PnL summary"})

    assert response.status_code == 404
    assert response.json() == {"detail": "No agent data found."}


def test_agent_query_returns_runtime_error_detail_instead_of_disabled_payload(monkeypatch):
    route_module = load_module(
        "backend.app.api.routes.agent",
        "backend/app/api/routes/agent.py",
    )
    monkeypatch.setattr(
        route_module,
        "get_settings",
        lambda: type(
            "SettingsStub",
            (),
            {
                "agent_enabled": True,
                "duckdb_path": "test.duckdb",
                "governance_path": "test-governance",
            },
        )(),
    )
    monkeypatch.setattr(
        route_module,
        "execute_agent_query",
        lambda request, duckdb_path, governance_dir: (_ for _ in ()).throw(
            RuntimeError("DuckDB read path unavailable.")
        ),
    )
    app = FastAPI()
    app.include_router(route_module.router)
    client = TestClient(app)

    response = client.post("/api/agent/query", json={"question": "PnL summary"})

    assert response.status_code == 503
    assert response.json() == {"detail": "DuckDB read path unavailable."}
