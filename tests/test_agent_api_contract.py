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

from backend.app.governance.settings import get_settings
from backend.app.main import app as default_app
from backend.app.security.auth_context import ROLE_HEADER_TRUST_ENV
from tests.helpers import load_module

AGENT_READ_HEADERS = {"X-User-Id": "agent-read-user", "X-User-Role": "viewer"}


def _agent_scope_dsn(tmp_path) -> str:
    return f"sqlite:///{(tmp_path / 'agent-read-scope.db').as_posix()}"


def _configure_agent_scope_store(tmp_path, monkeypatch):
    from backend.app.repositories.user_scope_repo import UserScopeRepository

    auth_dsn = _agent_scope_dsn(tmp_path)
    monkeypatch.setenv("MOSS_POSTGRES_DSN", auth_dsn)
    monkeypatch.delenv("MOSS_GOVERNANCE_SQL_DSN", raising=False)
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    return UserScopeRepository(auth_dsn)


def _agent_auth_fields(tmp_path) -> dict[str, str]:
    return {
        "postgres_dsn": f"sqlite:///{(tmp_path / 'agent-read-scope.db').as_posix()}",
        "governance_sql_dsn": "",
    }


def _seed_agent_read_scope(tmp_path, monkeypatch, *, user_id: str = "*") -> None:
    _configure_agent_scope_store(tmp_path, monkeypatch).grant_scope(
        user_id=user_id,
        role=None,
        resource="agent",
        action="read",
    )


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
            sql_executed=[
                "select count(*), sum(total_pnl) from fact_formal_pnl_fi where report_date = ?",
            ],
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
            sql_executed=[
                "select count(*), sum(total_pnl) from fact_formal_pnl_fi where report_date = ?",
            ],
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


def test_agent_enabled_endpoints_require_explicit_read_scope(tmp_path, monkeypatch) -> None:
    route_module = load_module(
        "backend.app.api.routes.agent",
        "backend/app/api/routes/agent.py",
    )
    _configure_agent_scope_store(tmp_path, monkeypatch)
    monkeypatch.setattr(
        route_module,
        "get_settings",
        lambda: type(
            "SettingsStub",
            (),
            {
                "agent_enabled": True,
                "agent_provider": "hermes",
                "agent_hermes_transport": "bridge",
                "agent_hermes_model": "gpt-test",
                "agent_hermes_toolsets": "file",
                "duckdb_path": str(tmp_path / "moss.duckdb"),
                "governance_path": str(tmp_path / "governance"),
                "postgres_dsn": f"sqlite:///{(tmp_path / 'agent-read-scope.db').as_posix()}",
                "governance_sql_dsn": "",
            },
        )(),
    )
    calls: list[str] = []

    def unexpected_agent_call(*_args, **_kwargs):
        calls.append("called")
        raise AssertionError("Agent service should not run without agent/read.")

    monkeypatch.setattr(route_module, "execute_hermes_agent_query", unexpected_agent_call)
    monkeypatch.setattr(route_module, "create_agent_run", unexpected_agent_call)
    monkeypatch.setattr(route_module, "get_agent_run_owner", unexpected_agent_call)

    app = FastAPI()
    app.include_router(route_module.router)
    client = TestClient(app, raise_server_exceptions=False)

    query_response = client.post("/api/agent/query", json={"question": "ping"}, headers=AGENT_READ_HEADERS)
    create_response = client.post("/api/agent/runs", json={"question": "ping"}, headers=AGENT_READ_HEADERS)
    status_response = client.get("/api/agent/runs/agent_run:nope", headers=AGENT_READ_HEADERS)

    assert query_response.status_code == 403
    assert create_response.status_code == 403
    assert status_response.status_code == 403
    assert calls == []


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
    assert {"type", "label", "payload", "requires_confirmation", "confirmation_token"} <= set(action_model.model_fields)
    assert "suggested_actions" in module.AgentEnvelope.model_fields
    assert "evidence_strength" in module.AgentEvidence.model_fields
    assert "evidence_strength" in module.AgentResultMeta.model_fields


def test_agent_provider_runtime_schema_downgrades_ok_quality_flag():
    module = load_module(
        "backend.app.agent.schemas.agent_response",
        "backend/app/agent/schemas/agent_response.py",
    )

    evidence = module.AgentEvidence(
        tables_used=["dexter_sidecar"],
        evidence_rows=5,
        quality_flag="ok",
        evidence_strength="provider_runtime",
    )
    meta = module.AgentResultMeta(
        trace_id="tr_provider_runtime",
        basis="analytical",
        result_kind="agent.dexter",
        formal_use_allowed=False,
        source_version="sv_dexter_sidecar",
        vendor_version="vv_dexter",
        rule_version="rv_agent_dexter_v1",
        cache_version="cv_agent_dexter_v1",
        quality_flag="ok",
        evidence_strength="provider_runtime",
    )

    assert evidence.quality_flag == "warning"
    assert meta.quality_flag == "warning"


def test_agent_query_executes_when_agent_setting_is_on(monkeypatch, tmp_path):
    route_module = load_module(
        "backend.app.api.routes.agent",
        "backend/app/api/routes/agent.py",
    )
    _seed_agent_read_scope(tmp_path, monkeypatch)
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
                **_agent_auth_fields(tmp_path),
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


def test_agent_envelope_contract_exposes_read_only_sql_disclosure(monkeypatch, tmp_path):
    """Governed intent envelopes must disclose the executed/equivalent read-only SQL."""
    route_module = load_module(
        "backend.app.api.routes.agent",
        "backend/app/api/routes/agent.py",
    )
    _seed_agent_read_scope(tmp_path, monkeypatch)
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
                **_agent_auth_fields(tmp_path),
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
    client = TestClient(app)

    response = client.post("/api/agent/query", json={"question": "PnL summary"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["evidence"]["sql_executed"]
    assert all(sql.lower().startswith("select") for sql in payload["evidence"]["sql_executed"])
    assert payload["result_meta"]["sql_executed"] == payload["evidence"]["sql_executed"]


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


def test_agent_query_maps_executor_value_error_when_agent_is_on(monkeypatch, tmp_path):
    route_module = load_module(
        "backend.app.api.routes.agent",
        "backend/app/api/routes/agent.py",
    )
    _seed_agent_read_scope(tmp_path, monkeypatch)
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
                **_agent_auth_fields(tmp_path),
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


def test_agent_query_maps_executor_runtime_error_when_agent_is_on(monkeypatch, tmp_path):
    route_module = load_module(
        "backend.app.api.routes.agent",
        "backend/app/api/routes/agent.py",
    )
    _seed_agent_read_scope(tmp_path, monkeypatch)
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
                **_agent_auth_fields(tmp_path),
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
    _seed_agent_read_scope(tmp_path, monkeypatch)
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
                **_agent_auth_fields(tmp_path),
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
    _seed_agent_read_scope(tmp_path, monkeypatch)
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
                **_agent_auth_fields(tmp_path),
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
    _seed_agent_read_scope(tmp_path, monkeypatch)
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
                **_agent_auth_fields(tmp_path),
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


def test_agent_query_requires_confirmation_token_for_confirmed_suggested_action(monkeypatch, tmp_path):
    from backend.app.agent.runtime.action_token import agent_action_confirmation_token

    route_module = load_module(
        "backend.app.api.routes.agent",
        "backend/app/api/routes/agent.py",
    )
    _seed_agent_read_scope(tmp_path, monkeypatch)
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
                **_agent_auth_fields(tmp_path),
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
    confirmed_action = {
        "type": "execute_intent",
        "label": "Portfolio overview",
        "payload": {"intent": "portfolio_overview"},
    }
    confirmed_token = agent_action_confirmation_token(
        action_type=confirmed_action["type"],
        label=confirmed_action["label"],
        payload=confirmed_action["payload"],
    )

    missing_token_response = client.post(
        "/api/agent/query",
        json={
            "question": "组合概览",
            "context": {
                "intent": "portfolio_overview",
                "suggested_action_requires_confirmation": True,
            },
        },
    )
    missing_action_response = client.post(
        "/api/agent/query",
        json={
            "question": "portfolio overview",
            "context": {
                "intent": "portfolio_overview",
                "suggested_action_requires_confirmation": True,
                "suggested_action_confirmation_token": confirmed_token,
            },
        },
    )
    confirmed_response = client.post(
        "/api/agent/query",
        json={
            "question": "组合概览",
            "context": {
                "intent": "portfolio_overview",
                "suggested_action_requires_confirmation": True,
                "suggested_action_confirmation_token": confirmed_token,
                "suggested_action": confirmed_action,
            },
        },
    )
    malformed_token_response = client.post(
        "/api/agent/query",
        json={
            "question": "缁勫悎姒傝",
            "context": {
                "intent": "portfolio_overview",
                "suggested_action_requires_confirmation": True,
                "suggested_action_confirmation_token": "agent_action:test-token",
            },
        },
    )

    mismatched_action_response = client.post(
        "/api/agent/query",
        json={
            "question": "portfolio overview",
            "context": {
                "intent": "portfolio_overview",
                "suggested_action_requires_confirmation": True,
                "suggested_action_confirmation_token": confirmed_token,
                "suggested_action": {
                    "type": "execute_intent",
                    "label": "Duration risk",
                    "payload": {"intent": "duration_risk"},
                },
            },
        },
    )

    assert missing_token_response.status_code == 403
    assert "confirmation token" in missing_token_response.json()["detail"]
    assert missing_action_response.status_code == 403
    assert "confirmation token" in missing_action_response.json()["detail"]
    assert malformed_token_response.status_code == 403
    assert "confirmation token" in malformed_token_response.json()["detail"]
    assert mismatched_action_response.status_code == 403
    assert "confirmation token" in mismatched_action_response.json()["detail"]
    assert confirmed_response.status_code == 200
    assert calls
    assert calls[-1][0].context["suggested_action_confirmation_token"] == confirmed_token


def test_agent_query_rejects_expired_suggested_action_confirmation_token(monkeypatch, tmp_path):
    from backend.app.agent.runtime.action_token import agent_action_confirmation_token

    route_module = load_module(
        "backend.app.api.routes.agent",
        "backend/app/api/routes/agent.py",
    )
    _seed_agent_read_scope(tmp_path, monkeypatch)
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
                **_agent_auth_fields(tmp_path),
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
    confirmed_action = {
        "type": "execute_intent",
        "label": "Portfolio overview",
        "payload": {"intent": "portfolio_overview"},
    }
    expired_token = agent_action_confirmation_token(
        action_type=confirmed_action["type"],
        label=confirmed_action["label"],
        payload=confirmed_action["payload"],
        expires_at=1,
    )

    response = client.post(
        "/api/agent/query",
        json={
            "question": "portfolio overview",
            "context": {
                "intent": "portfolio_overview",
                "suggested_action_requires_confirmation": True,
                "suggested_action_confirmation_token": expired_token,
                "suggested_action": confirmed_action,
            },
        },
    )

    assert response.status_code == 403
    assert "confirmation token" in response.json()["detail"]
    assert calls == []


def test_agent_endpoints_require_token_when_suggested_action_payload_requires_confirmation(monkeypatch, tmp_path):
    route_module = load_module(
        "backend.app.api.routes.agent",
        "backend/app/api/routes/agent.py",
    )
    _seed_agent_read_scope(tmp_path, monkeypatch)
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
                "agent_hermes_toolsets": "evidence",
                "agent_hermes_timeout_seconds": 11.0,
                "duckdb_path": str(tmp_path / "moss.duckdb"),
                "governance_path": str(tmp_path / "governance"),
                **_agent_auth_fields(tmp_path),
            },
        )(),
    )
    calls = []

    def fake_execute_hermes_agent_query(request, governance_dir, settings):
        calls.append((request, governance_dir, settings.agent_hermes_model))
        return _sample_agent_envelope()

    monkeypatch.setattr(route_module, "execute_hermes_agent_query", fake_execute_hermes_agent_query)
    app = FastAPI()
    app.include_router(route_module.router)
    client = TestClient(app)
    body = {
        "question": "run suggested action",
        "context": {
            "suggested_action": {
                "type": "execute_intent",
                "label": "Refresh page",
                "payload": {"intent": "refresh_page"},
                "requires_confirmation": True,
            }
        },
    }

    query_response = client.post("/api/agent/query", json=body)
    runs_response = client.post("/api/agent/runs", json=body)

    assert query_response.status_code == 403
    assert "confirmation token" in query_response.json()["detail"]
    assert runs_response.status_code == 403
    assert "confirmation token" in runs_response.json()["detail"]
    assert not calls


def test_agent_query_routes_to_dexter_provider_when_configured(monkeypatch, tmp_path):
    route_module = load_module(
        "backend.app.api.routes.agent",
        "backend/app/api/routes/agent.py",
    )
    _seed_agent_read_scope(tmp_path, monkeypatch)
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
                **_agent_auth_fields(tmp_path),
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


def test_external_provider_envelopes_sanitize_toolsets_and_mark_provider_runtime_evidence():
    from backend.app.agent.schemas.agent_request import AgentQueryRequest
    from backend.app.services.dexter_agent_service import build_dexter_envelope
    from backend.app.services.hermes_agent_service import build_hermes_envelope

    request = AgentQueryRequest(question="external provider health check")

    hermes = build_hermes_envelope(
        request=request,
        result={
            "answer": "Hermes answered.",
            "model": "gpt-test",
            "toolsets": "file,terminal,query",
            "transport": "bridge",
        },
    )
    dexter = build_dexter_envelope(
        request=request,
        result={
            "answer": "Dexter answered.",
            "model": "dexter-test",
            "toolsets": "sql,files,research",
            "transport": "sidecar",
            "tables_used": ["dexter_sidecar"],
        },
        research_context=None,
    )

    assert hermes.evidence.filters_applied["toolsets"] == "query"
    assert hermes.result_meta.filters_applied["toolsets"] == "query"
    assert hermes.evidence.evidence_strength == "provider_runtime"
    assert hermes.result_meta.evidence_strength == "provider_runtime"
    assert hermes.result_meta.quality_flag == "warning"
    assert hermes.result_meta.formal_use_allowed is False

    assert dexter.evidence.filters_applied["toolsets"] == "research"
    assert dexter.result_meta.filters_applied["toolsets"] == "research"
    assert dexter.evidence.evidence_strength == "provider_runtime"
    assert dexter.result_meta.evidence_strength == "provider_runtime"
    assert dexter.result_meta.quality_flag == "warning"
    assert dexter.result_meta.formal_use_allowed is False
