from __future__ import annotations

import importlib
import logging
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.agent.schemas.agent_response import (
    AgentEnvelope,
    AgentEvidence,
    AgentResultMeta,
)
from tests.helpers import load_module

import pytest

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_agent_mvp,
]


def _settings(tmp_path: Path, *, bypass: bool) -> SimpleNamespace:
    return SimpleNamespace(
        environment="development",
        agent_enabled=True,
        agent_dev_scope_bypass=bypass,
        agent_provider="local",
        duckdb_path=str(tmp_path / "moss.duckdb"),
        governance_path=str(tmp_path / "governance"),
        postgres_dsn=f"sqlite:///{(tmp_path / 'agent-scope.db').as_posix()}",
        governance_sql_dsn="",
    )


def _sample_envelope() -> AgentEnvelope:
    return AgentEnvelope(
        answer="Development bypass response.",
        cards=[],
        evidence=AgentEvidence(
            tables_used=["agent_dev_bypass_test"],
            evidence_rows=1,
            quality_flag="warning",
        ),
        result_meta=AgentResultMeta(
            trace_id="tr_agent_dev_bypass_guard",
            basis="analytical",
            result_kind="agent.dev_bypass_guard",
            formal_use_allowed=False,
            source_version="sv_test",
            vendor_version="vv_test",
            rule_version="rv_test",
            cache_version="cv_test",
            quality_flag="warning",
            scenario_flag=False,
            tables_used=["agent_dev_bypass_test"],
            evidence_rows=1,
        ),
    )


def _client(monkeypatch, settings: SimpleNamespace, *, client_host: str) -> TestClient:
    route_module = load_module(
        "backend.app.api.routes.agent",
        "backend/app/api/routes/agent.py",
    )
    workspace_route_module = importlib.import_module(
        "backend.app.api.routes.agent_workspace"
    )
    monkeypatch.setattr(route_module, "get_settings", lambda: settings)
    monkeypatch.setattr(workspace_route_module, "get_settings", lambda: settings)
    app = FastAPI()
    app.include_router(route_module.router)
    return TestClient(
        app,
        client=(client_host, 50000),
        raise_server_exceptions=False,
    )


def test_agent_dev_scope_bypass_allows_loopback_query_and_workspace_write(
    monkeypatch,
    tmp_path,
) -> None:
    settings = _settings(tmp_path, bypass=True)
    client = _client(monkeypatch, settings, client_host="127.0.0.1")
    route_module = importlib.import_module("backend.app.api.routes.agent")
    workspace_route_module = importlib.import_module(
        "backend.app.api.routes.agent_workspace"
    )
    scope_checks: list[str] = []

    def unexpected_scope_check(**kwargs):
        scope_checks.append(str(kwargs["action"]))
        raise AssertionError("loopback development bypass reached scope store")

    monkeypatch.setattr(route_module, "ensure_user_allowed", unexpected_scope_check)
    monkeypatch.setattr(
        workspace_route_module,
        "ensure_user_allowed",
        unexpected_scope_check,
    )
    monkeypatch.setattr(
        route_module,
        "execute_agent_query",
        lambda *_args, **_kwargs: _sample_envelope(),
    )

    query_response = client.post("/api/agent/query", json={"question": "ping"})
    project_response = client.post(
        "/api/agent/projects",
        json={"name": "Loopback dev project"},
    )

    assert query_response.status_code == 200
    assert project_response.status_code == 200, project_response.text
    assert scope_checks == []


def test_agent_dev_scope_bypass_rejects_non_loopback_query_and_workspace_write(
    monkeypatch,
    tmp_path,
    caplog,
) -> None:
    settings = _settings(tmp_path, bypass=True)
    client = _client(monkeypatch, settings, client_host="10.0.0.5")
    route_module = importlib.import_module("backend.app.api.routes.agent")
    workspace_route_module = importlib.import_module(
        "backend.app.api.routes.agent_workspace"
    )
    calls: list[str] = []

    def unexpected_scope_check(**kwargs):
        calls.append(f"scope:{kwargs['action']}")
        raise AssertionError("non-loopback bypass fell through to scope store")

    def unexpected_agent_call(*_args, **_kwargs):
        calls.append("agent")
        raise AssertionError("non-loopback query reached agent execution")

    def unexpected_workspace_write(**_kwargs):
        calls.append("workspace")
        raise AssertionError("non-loopback workspace write reached storage")

    monkeypatch.setattr(route_module, "ensure_user_allowed", unexpected_scope_check)
    monkeypatch.setattr(
        workspace_route_module,
        "ensure_user_allowed",
        unexpected_scope_check,
    )
    monkeypatch.setattr(route_module, "execute_agent_query", unexpected_agent_call)
    monkeypatch.setattr(
        workspace_route_module,
        "create_project",
        unexpected_workspace_write,
    )

    with caplog.at_level(
        logging.WARNING,
        logger="backend.app.api.routes.agent_workspace",
    ):
        query_response = client.post("/api/agent/query", json={"question": "ping"})
        project_response = client.post(
            "/api/agent/projects",
            json={"name": "Remote dev project"},
        )

    assert query_response.status_code == 403
    assert project_response.status_code == 403
    assert "10.0.0.5" in caplog.text
    assert "non-loopback" in caplog.text
    assert calls == []


def test_agent_dev_scope_bypass_false_still_uses_scope_authorization(
    monkeypatch,
    tmp_path,
) -> None:
    settings = _settings(tmp_path, bypass=False)
    client = _client(monkeypatch, settings, client_host="127.0.0.1")
    route_module = importlib.import_module("backend.app.api.routes.agent")
    workspace_route_module = importlib.import_module(
        "backend.app.api.routes.agent_workspace"
    )
    scope_checks: list[str] = []

    def reject_scope_check(**kwargs):
        scope_checks.append(f"{kwargs['resource']}:{kwargs['action']}")
        raise PermissionError("missing development test scope")

    monkeypatch.setattr(route_module, "ensure_user_allowed", reject_scope_check)
    monkeypatch.setattr(
        workspace_route_module,
        "ensure_user_allowed",
        reject_scope_check,
    )
    monkeypatch.setattr(
        route_module,
        "execute_agent_query",
        lambda *_args, **_kwargs: _sample_envelope(),
    )

    query_response = client.post("/api/agent/query", json={"question": "ping"})
    project_response = client.post(
        "/api/agent/projects",
        json={"name": "Scoped dev project"},
    )

    assert query_response.status_code == 403
    assert project_response.status_code == 403
    assert scope_checks == ["agent:read", "agent:write"]
