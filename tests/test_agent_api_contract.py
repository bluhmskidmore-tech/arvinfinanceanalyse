"""
Agent HTTP + schema contracts.

Production default (`agent_enabled=False`): `POST /api/agent/query` returns **503** with
`AgentDisabledResponse` — not a live Agent. Tests that return 200 use an isolated FastAPI
app with `agent_enabled` stubbed True to exercise envelope/schema only.
"""

from __future__ import annotations

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


def test_default_app_agent_query_is_disabled_503(monkeypatch, tmp_path):
    """Unmocked app: Agent is disabled unless the feature flag is explicitly enabled."""
    def disabled_settings():
        return type(
            "SettingsStub",
            (),
            {
                "agent_enabled": False,
                "agent_provider": "local",
                "duckdb_path": str(tmp_path / "moss.duckdb"),
                "governance_path": str(tmp_path / "governance"),
            },
        )()
    for route in default_app.routes:
        if getattr(route, "path", None) == "/api/agent/query":
            monkeypatch.setitem(route.endpoint.__globals__, "get_settings", disabled_settings)
    client = TestClient(default_app)
    response = client.post("/api/agent/query", json={"question": "PnL summary"})

    assert response.status_code == 503
    body = response.json()
    assert body["enabled"] is False
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


def test_agent_request_schema_accepts_page_context():
    module = load_module(
        "backend.app.agent.schemas.agent_request",
        "backend/app/agent/schemas/agent_request.py",
    )

    request = module.AgentQueryRequest(
        question="解释当前页面",
        page_context={
            "page_id": "reconciliation",
            "current_filters": {"report_date": "2026-03-31", "status": "BREAK"},
            "selected_rows": [
                {"book_id": "BOOK-A", "instrument_id": "BOND-1", "difference": 12.3}
            ],
            "context_note": "Current reconciliation page filters and top break row.",
        },
    )

    assert request.page_context.page_id == "reconciliation"
    assert request.page_context.current_filters["status"] == "BREAK"
    assert request.page_context.selected_rows[0]["instrument_id"] == "BOND-1"
    assert request.page_context.context_note == "Current reconciliation page filters and top break row."


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


def test_agent_response_schema_exposes_passive_suggested_actions():
    module = load_module(
        "backend.app.agent.schemas.agent_response",
        "backend/app/agent/schemas/agent_response.py",
    )
    action_model = getattr(module, "AgentSuggestedAction", None)
    assert action_model is not None
    assert {"type", "label", "payload", "requires_confirmation"} <= set(action_model.model_fields)
    assert "suggested_actions" in module.AgentEnvelope.model_fields


def test_agent_query_executes_when_agent_setting_is_on(monkeypatch, tmp_path):
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
                "agent_provider": "local",
                "duckdb_path": str(tmp_path / "moss.duckdb"),
                "governance_path": str(tmp_path / "governance"),
            },
        )(),
    )
    calls = []

    def fake_execute_agent_query(request, duckdb_path, governance_dir):
        calls.append((request, duckdb_path, governance_dir))
        return _sample_agent_envelope()

    monkeypatch.setattr(route_module, "execute_agent_query", fake_execute_agent_query)
    app = FastAPI()
    app.include_router(route_module.router)
    client = TestClient(app)
    response = client.post("/api/agent/query", json={"question": "PnL summary"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["result_kind"] == "agent.pnl_summary"
    assert payload["result_meta"]["formal_use_allowed"] is True
    assert calls


def test_agent_query_returns_disabled_when_agent_is_off(monkeypatch, tmp_path):
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
                "agent_provider": "local",
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
    payload = response.json()
    assert payload["enabled"] is False
    assert "disabled" in payload["detail"].lower()
    assert "result_meta" not in payload


def test_disabled_agent_query_appends_disabled_audit_log(monkeypatch, tmp_path):
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
                "agent_provider": "local",
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
    audit_path = tmp_path / "governance" / "agent_audit.jsonl"
    assert audit_path.exists()
    audit_payload = json.loads(audit_path.read_text(encoding="utf-8").splitlines()[-1])
    assert audit_payload["tools_used"] == ["agent_disabled"]
    assert audit_payload["result_meta"]["result_kind"] == "agent.disabled"
    assert audit_payload["result_meta"]["formal_use_allowed"] is False


def test_agent_query_maps_executor_value_error_when_agent_is_on(monkeypatch):
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
                "agent_provider": "local",
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
    assert response.json()["detail"] == "No agent data found."


def test_agent_query_maps_executor_runtime_error_when_agent_is_on(monkeypatch):
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
                "agent_provider": "local",
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
    assert response.json()["detail"] == "DuckDB read path unavailable."


def test_agent_query_routes_to_hermes_provider_when_configured(monkeypatch, tmp_path):
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
                "agent_provider": "hermes",
                "agent_hermes_command": "hermes",
                "agent_hermes_wsl_distro": "",
                "agent_hermes_model": "gpt-test",
                "agent_hermes_timeout_seconds": 9.0,
                "duckdb_path": str(tmp_path / "moss.duckdb"),
                "governance_path": str(tmp_path / "governance"),
            },
        )(),
    )
    calls = []

    def fake_execute_hermes_agent_query(request, governance_dir, settings):
        calls.append((request, governance_dir, settings.agent_hermes_model))
        return _sample_agent_envelope().model_copy(
            update={
                "answer": "Hermes answered.",
                "result_meta": _sample_agent_envelope().result_meta.model_copy(
                    update={
                        "result_kind": "agent.hermes",
                        "vendor_version": "vv_hermes",
                        "formal_use_allowed": False,
                    }
                ),
            }
        )

    monkeypatch.setattr(route_module, "execute_hermes_agent_query", fake_execute_hermes_agent_query)
    app = FastAPI()
    app.include_router(route_module.router)
    client = TestClient(app)

    response = client.post("/api/agent/query", json={"question": "external provider health check"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "Hermes answered."
    assert payload["result_meta"]["result_kind"] == "agent.hermes"
    assert payload["result_meta"]["vendor_version"] == "vv_hermes"
    assert calls
    assert calls[0][2] == "gpt-test"


def test_agent_query_keeps_plain_analysis_chat_local_when_hermes_configured(monkeypatch, tmp_path):
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
                "agent_provider": "hermes",
                "agent_hermes_command": "hermes",
                "agent_hermes_wsl_distro": "",
                "agent_hermes_model": "gpt-test",
                "agent_hermes_timeout_seconds": 9.0,
                "duckdb_path": str(tmp_path / "moss.duckdb"),
                "governance_path": str(tmp_path / "governance"),
            },
        )(),
    )
    local_calls = []
    hermes_calls = []
    local_envelope = _sample_agent_envelope().model_copy(
        update={
            "answer": "Local analysis chat answered.",
            "result_meta": _sample_agent_envelope().result_meta.model_copy(
                update={
                    "result_kind": "agent.analysis_chat",
                    "formal_use_allowed": False,
                }
            ),
        }
    )

    def fake_execute_agent_query(request, duckdb_path, governance_dir):
        local_calls.append((request, duckdb_path, governance_dir))
        return local_envelope

    def fake_execute_hermes_agent_query(request, governance_dir, settings):
        hermes_calls.append((request, governance_dir, settings))
        return _sample_agent_envelope()

    monkeypatch.setattr(route_module, "execute_agent_query", fake_execute_agent_query)
    monkeypatch.setattr(route_module, "execute_hermes_agent_query", fake_execute_hermes_agent_query)
    app = FastAPI()
    app.include_router(route_module.router)
    client = TestClient(app)

    response = client.post("/api/agent/query", json={"question": "帮我判断今天的主要风险"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "Local analysis chat answered."
    assert payload["result_meta"]["result_kind"] == "agent.analysis_chat"
    assert local_calls
    assert not hermes_calls


def test_agent_query_keeps_explicit_governed_intent_local_when_hermes_configured(monkeypatch, tmp_path):
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
                "agent_provider": "hermes",
                "agent_hermes_command": "hermes",
                "agent_hermes_wsl_distro": "",
                "agent_hermes_model": "gpt-test",
                "agent_hermes_timeout_seconds": 9.0,
                "duckdb_path": str(tmp_path / "moss.duckdb"),
                "governance_path": str(tmp_path / "governance"),
            },
        )(),
    )
    local_calls = []
    hermes_calls = []

    def fake_execute_agent_query(request, duckdb_path, governance_dir):
        local_calls.append((request, duckdb_path, governance_dir))
        return _sample_agent_envelope()

    def fake_execute_hermes_agent_query(request, governance_dir, settings):
        hermes_calls.append((request, governance_dir, settings))
        return _sample_agent_envelope()

    monkeypatch.setattr(route_module, "execute_agent_query", fake_execute_agent_query)
    monkeypatch.setattr(route_module, "execute_hermes_agent_query", fake_execute_hermes_agent_query)
    app = FastAPI()
    app.include_router(route_module.router)
    client = TestClient(app)

    response = client.post(
        "/api/agent/query",
        json={"question": "组合概览", "context": {"intent": "portfolio_overview"}},
    )

    assert response.status_code == 200
    assert response.json()["result_meta"]["result_kind"] == "agent.pnl_summary"
    assert local_calls
    assert local_calls[0][0].context["intent"] == "portfolio_overview"
    assert not hermes_calls


def test_agent_endpoints_reject_mutating_action_context(monkeypatch, tmp_path):
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
                "agent_provider": "hermes",
                "agent_hermes_command": "hermes",
                "agent_hermes_transport": "bridge",
                "agent_hermes_model": "gpt-test",
                "agent_hermes_timeout_seconds": 9.0,
                "duckdb_path": str(tmp_path / "moss.duckdb"),
                "governance_path": str(tmp_path / "governance"),
            },
        )(),
    )
    calls = []

    def fake_execute_agent_query(request, duckdb_path, governance_dir):
        calls.append(("local", request, duckdb_path, governance_dir))
        return _sample_agent_envelope()

    def fake_execute_hermes_agent_query(request, governance_dir, settings):
        calls.append(("hermes", request, governance_dir, settings))
        return _sample_agent_envelope()

    def fake_create_agent_run(**kwargs):
        calls.append(("run", kwargs))
        return {"run_id": "agent_run:blocked", "status": "queued"}

    monkeypatch.setattr(route_module, "execute_agent_query", fake_execute_agent_query)
    monkeypatch.setattr(route_module, "execute_hermes_agent_query", fake_execute_hermes_agent_query)
    monkeypatch.setattr(route_module, "create_agent_run", fake_create_agent_run)
    app = FastAPI()
    app.include_router(route_module.router)
    client = TestClient(app)

    payload = {
        "question": "refresh dashboard data",
        "context": {"action_type": "refresh"},
    }

    query_response = client.post("/api/agent/query", json=payload)
    run_response = client.post("/api/agent/runs", json=payload)

    assert query_response.status_code == 403
    assert run_response.status_code == 403
    assert "read-only" in query_response.json()["detail"]
    assert "read-only" in run_response.json()["detail"]
    assert not calls


def test_agent_query_routes_to_dexter_provider_when_configured(monkeypatch, tmp_path):
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
                "agent_provider": "dexter",
                "agent_dexter_command": "dexter",
                "agent_dexter_transport": "sidecar",
                "agent_dexter_model": "dexter-test",
                "agent_dexter_toolsets": "sql,files",
                "agent_dexter_timeout_seconds": 11.0,
                "duckdb_path": str(tmp_path / "moss.duckdb"),
                "governance_path": str(tmp_path / "governance"),
            },
        )(),
    )
    calls = []

    def fake_execute_dexter_agent_query(request, governance_dir, settings):
        calls.append((request, governance_dir, settings.agent_dexter_model))
        sample = _sample_agent_envelope()
        return sample.model_copy(
            update={
                "answer": "Dexter answered.",
                "evidence": sample.evidence.model_copy(
                    update={
                        "tables_used": ["dexter_sidecar"],
                        "filters_applied": {
                            "provider": "dexter",
                            "model": "dexter-test",
                            "transport": "sidecar",
                            "toolsets": "sql,files",
                        },
                    }
                ),
                "result_meta": sample.result_meta.model_copy(
                    update={
                        "result_kind": "agent.dexter",
                        "formal_use_allowed": False,
                        "source_version": "sv_dexter_sidecar",
                        "vendor_version": "vv_dexter",
                        "rule_version": "rv_agent_dexter_v1",
                        "cache_version": "cv_agent_dexter_v1",
                        "tables_used": ["dexter_sidecar"],
                        "filters_applied": {
                            "provider": "dexter",
                        },
                    }
                ),
            }
        )

    monkeypatch.setattr(route_module, "execute_dexter_agent_query", fake_execute_dexter_agent_query)
    app = FastAPI()
    app.include_router(route_module.router)
    client = TestClient(app)

    response = client.post("/api/agent/query", json={"question": "external provider health check"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "Dexter answered."
    assert payload["result_meta"]["result_kind"] == "agent.dexter"
    assert payload["result_meta"]["formal_use_allowed"] is False
    assert payload["result_meta"]["vendor_version"] == "vv_dexter"
    assert payload["evidence"]["tables_used"] == ["dexter_sidecar"]
    assert calls
    assert calls[0][2] == "dexter-test"
