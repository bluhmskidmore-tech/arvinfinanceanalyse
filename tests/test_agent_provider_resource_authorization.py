from __future__ import annotations

import importlib
import json

import duckdb
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import update

from backend.app.agent.schemas.agent_request import AgentQueryRequest
from backend.app.governance.settings import get_settings
from backend.app.models.governance import UserRoleScope
from backend.app.repositories.user_scope_repo import UserScopeRepository
from backend.app.security.auth_context import (
    AuthContext,
    get_auth_context,
    reset_scope_decision_cache,
)
from backend.app.services import dexter_agent_service, hermes_agent_service
from tests.helpers import load_module

pytestmark = [pytest.mark.excluded_surface_acceptance, pytest.mark.surface_agent_mvp]

SYNTHETIC_NEWS = "SYNTHETIC_RESTRICTED_NEWS_0922"
NEWS_REQUEST = {
    "question": "Read stored headlines",
    "context": {"intent": "news"},
    "routing_surface": "standalone_workbench",
}
DEXTER_REQUEST = {
    "question": "external provider health check",
    "filters": {
        "research_domain": "stock",
        "stock_code": "000001.SZ",
        "as_of_date": "2026-09-22",
    },
}
MACRO_REQUEST = {
    "question": "external provider health check",
    "filters": {"research_domain": "macro", "as_of_date": "2026-09-22"},
}


@pytest.fixture
def boundary(tmp_path, monkeypatch):
    # Other Agent tests replace modules through load_module; bind the router and
    # dispatch proxy to the same current service instance for this test.
    route = load_module("backend.app.api.routes.agent", "backend/app/api/routes/agent.py")
    monkeypatch.setattr(
        route, "execute_dexter_agent_query", dexter_agent_service.execute_dexter_agent_query
    )
    monkeypatch.setattr(
        route, "execute_hermes_agent_query", hermes_agent_service.execute_hermes_agent_query
    )
    dsn = f"sqlite:///{(tmp_path / 'scope.db').as_posix()}"
    for key, value in {
        "MOSS_ENVIRONMENT": "test",
        "MOSS_AGENT_ENABLED": "true",
        "MOSS_AGENT_DEV_SCOPE_BYPASS": "false",
        "MOSS_POSTGRES_DSN": dsn,
        "MOSS_GOVERNANCE_SQL_DSN": dsn,
        "MOSS_GOVERNANCE_BACKEND_MODE": "jsonl",
        "MOSS_GOVERNANCE_PATH": str(tmp_path / "governance"),
        "MOSS_DUCKDB_PATH": str(tmp_path / "synthetic.duckdb"),
        "MOSS_AGENT_ACTION_TOKEN_SECRET": "synthetic-audit-secret-not-real",
        "MOSS_AGENT_PROVIDER": "hermes",
    }.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    settings = get_settings()
    monkeypatch.setattr(route, "get_settings", lambda: settings)
    scopes = UserScopeRepository(dsn)
    scopes.grant_scope(user_id="audit-user", role=None, resource="agent", action="read")
    with duckdb.connect(settings.duckdb_path) as conn:
        conn.execute("""create table choice_news_event (
            event_key varchar, received_at varchar, group_id varchar, content_type varchar,
            serial_id bigint, request_id bigint, error_code bigint, error_msg varchar,
            topic_code varchar, item_index bigint, payload_text varchar, payload_json varchar
        )""")
        conn.execute(
            "insert into choice_news_event values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                "synthetic-event",
                "2026-09-01T08:00:00Z",
                "synthetic",
                "text",
                1,
                1,
                0,
                "",
                "000001.SZ",
                0,
                SYNTHETIC_NEWS,
                "{}",
            ],
        )
        conn.execute("""create table fact_choice_macro_daily (
            series_id varchar, series_name varchar, trade_date varchar, value_numeric double,
            frequency varchar, unit varchar, source_version varchar, vendor_version varchar,
            rule_version varchar, quality_flag varchar, run_id varchar
        )""")
        conn.execute("""insert into fact_choice_macro_daily values (
            'legacy.yield.choice.treasury.10Y', 'SYNTHETIC_MACRO_0922', '2026-09-01', 2.0,
            'daily', 'percent', 'synthetic', 'synthetic', 'synthetic', 'ok', 'synthetic'
        )""")
    app = FastAPI()
    app.include_router(route.router)
    app.dependency_overrides[get_auth_context] = lambda: AuthContext(
        user_id="audit-user", role="reviewer", identity_source="test"
    )
    with TestClient(app, raise_server_exceptions=True) as client:
        yield client, settings, scopes


def test_dexter_provider_must_authorize_landed_news_before_prompt(
    boundary, monkeypatch
):
    client, settings, _scopes = boundary
    settings.agent_provider = "dexter"
    observed = []

    def fake_provider(**kwargs):
        observed.append(kwargs["prompt_override"])
        return {
            "answer": "Synthetic provider answer",
            "command": "synthetic",
            "model": "synthetic",
            "toolsets": "research",
            "transport": "cli",
        }

    monkeypatch.setattr(dexter_agent_service, "run_dexter_agent", fake_provider)
    assert client.post("/api/agent/query", json=NEWS_REQUEST).status_code == 403
    response = client.post("/api/agent/query", json=DEXTER_REQUEST)

    assert response.status_code == 403, response.text
    assert observed == []


def test_lab_failure_must_authorize_local_recovery_resource(boundary, monkeypatch):
    client, settings, scopes = boundary
    scopes.grant_scope(
        user_id="audit-user", role=None, resource="agent", action="execute"
    )

    def failed_provider(**_kwargs):
        raise hermes_agent_service.HermesRuntimeError("synthetic provider unavailable")

    monkeypatch.setattr(hermes_agent_service, "run_hermes_agent", failed_provider)

    _dispatch_inline(
        monkeypatch, settings, hermes_agent_service.execute_hermes_agent_query
    )
    assert client.post("/api/agent/query", json=NEWS_REQUEST).status_code == 403
    created = client.post("/api/agent/lab/runs", json=NEWS_REQUEST)

    assert created.status_code == 403, created.text


def _grant(scopes, *resources):
    for resource in resources:
        scopes.grant_scope(
            user_id="audit-user", role=None, resource=resource, action="read"
        )


def _revoke(scopes, resource):
    # Mutate only this test's SQLite scope store, then model an expired read-decision cache.
    with scopes.engine.begin() as conn:
        conn.execute(
            update(UserRoleScope)
            .where(UserRoleScope.resource == resource)
            .values(is_active=False)
        )
    reset_scope_decision_cache()


def _capture_dexter(monkeypatch):
    prompts = []

    def fake_provider(**kwargs):
        prompts.append(kwargs["prompt_override"])
        return {
            "answer": "Synthetic provider answer",
            "command": "synthetic",
            "model": "synthetic",
            "toolsets": "research",
            "transport": "cli",
        }

    monkeypatch.setattr(dexter_agent_service, "run_dexter_agent", fake_provider)
    return prompts


def _dispatch_inline(monkeypatch, settings, executor):
    service = importlib.import_module("backend.app.services.agent_run_service")

    def send(*, run_id):
        return service.execute_agent_run_by_id(
            run_id=run_id, settings=settings, executor=executor
        )

    monkeypatch.setattr(service.execute_agent_run_task, "send", send)


@pytest.mark.parametrize("endpoint", ["/query", "/runs"])
@pytest.mark.parametrize("missing", ["market_data.livermore", "choice_news.data"])
def test_dexter_requires_each_stock_research_scope(
    boundary, monkeypatch, endpoint, missing
):
    client, settings, scopes = boundary
    settings.agent_provider = "dexter"
    _grant(
        scopes,
        *(
            resource
            for resource in ("market_data.livermore", "choice_news.data")
            if resource != missing
        ),
    )
    prompts = _capture_dexter(monkeypatch)
    _dispatch_inline(
        monkeypatch, settings, dexter_agent_service.execute_dexter_agent_query
    )

    response = client.post("/api/agent" + endpoint, json=DEXTER_REQUEST)

    assert response.status_code == 403, response.text
    assert missing in response.json()["detail"]
    assert prompts == []


@pytest.mark.parametrize("endpoint", ["/query", "/runs"])
@pytest.mark.parametrize(
    ("payload", "resources", "marker"),
    [
        (DEXTER_REQUEST, ("market_data.livermore", "choice_news.data"), SYNTHETIC_NEWS),
        (MACRO_REQUEST, ("macro_vendor",), "SYNTHETIC_MACRO_0922"),
    ],
)
def test_authorized_dexter_research_reaches_provider(
    boundary, monkeypatch, endpoint, payload, resources, marker
):
    client, settings, scopes = boundary
    settings.agent_provider = "dexter"
    _grant(scopes, *resources)
    prompts = _capture_dexter(monkeypatch)
    _dispatch_inline(
        monkeypatch, settings, dexter_agent_service.execute_dexter_agent_query
    )

    response = client.post("/api/agent" + endpoint, json=payload)

    assert response.status_code == 200, response.text
    assert len(prompts) == 1
    assert marker in prompts[0]
    if endpoint == "/runs":
        status = client.get("/api/agent/runs/" + response.json()["run_id"])
        assert status.json()["status"] == "completed", status.text


@pytest.mark.parametrize("endpoint", ["/query", "/runs"])
def test_dexter_macro_requires_macro_resource(boundary, monkeypatch, endpoint):
    client, settings, _scopes = boundary
    settings.agent_provider = "dexter"
    prompts = _capture_dexter(monkeypatch)
    _dispatch_inline(
        monkeypatch, settings, dexter_agent_service.execute_dexter_agent_query
    )

    response = client.post("/api/agent" + endpoint, json=MACRO_REQUEST)

    assert response.status_code == 403, response.text
    assert "macro_vendor" in response.json()["detail"]
    assert prompts == []


@pytest.mark.parametrize("lab", [False, True])
def test_retry_rechecks_original_provider_resources(boundary, monkeypatch, lab):
    client, settings, scopes = boundary
    settings.agent_provider = "hermes" if lab else "dexter"
    scopes.grant_scope(
        user_id="audit-user", role=None, resource="agent", action="execute"
    )
    _grant(scopes, "market_data.livermore", "choice_news.data")
    dispatches = []
    service = importlib.import_module("backend.app.services.agent_run_service")
    monkeypatch.setattr(
        service.execute_agent_run_task,
        "send",
        lambda **kwargs: dispatches.append(kwargs),
    )
    created = client.post(
        "/api/agent/lab/runs" if lab else "/api/agent/runs",
        json=NEWS_REQUEST if lab else DEXTER_REQUEST,
    )
    assert created.status_code == 200, created.text
    run_id = created.json()["run_id"]
    assert client.post("/api/agent/runs/" + run_id + "/cancel").status_code == 200
    _revoke(scopes, "choice_news.data")
    # A non-Lab retry retains its stored Dexter provider even if today's setting changed.
    settings.agent_provider = "hermes"

    retried = client.post("/api/agent/runs/" + run_id + "/retry")

    assert retried.status_code == 403, retried.text
    assert "choice_news.data" in retried.json()["detail"]
    assert len(dispatches) == 1


def test_hermes_recovery_checks_permission_before_local_execution(
    boundary, monkeypatch
):
    _client, settings, _scopes = boundary
    request = AgentQueryRequest.model_validate(NEWS_REQUEST)
    request.context.update(user_id="audit-user", user_role="reviewer")

    def unexpected_local(*_args, **_kwargs):
        raise AssertionError("unauthorized recovery reached local execution")

    monkeypatch.setattr(hermes_agent_service, "execute_agent_query", unexpected_local)
    with pytest.raises(PermissionError, match="choice_news.data"):
        hermes_agent_service.build_local_recovery_envelope(
            request=request,
            governance_dir=str(settings.governance_path),
            settings=settings,
        )


def test_authorized_lab_recovery_returns_landed_news(boundary, monkeypatch):
    client, settings, scopes = boundary
    scopes.grant_scope(
        user_id="audit-user", role=None, resource="agent", action="execute"
    )
    _grant(scopes, "choice_news.data")

    def failed_provider(**_kwargs):
        raise hermes_agent_service.HermesRuntimeError("synthetic provider unavailable")

    monkeypatch.setattr(hermes_agent_service, "run_hermes_agent", failed_provider)
    _dispatch_inline(
        monkeypatch, settings, hermes_agent_service.execute_hermes_agent_query
    )
    created = client.post("/api/agent/lab/runs", json=NEWS_REQUEST)

    assert created.status_code == 200, created.text
    status = client.get("/api/agent/runs/" + created.json()["run_id"])
    assert status.json()["status"] == "completed", status.text
    assert SYNTHETIC_NEWS in json.dumps(status.json())


def test_dexter_execution_rechecks_scopes_before_building_context(
    boundary, monkeypatch
):
    _client, settings, scopes = boundary
    _grant(scopes, "market_data.livermore", "choice_news.data")
    _revoke(scopes, "choice_news.data")
    request = AgentQueryRequest.model_validate(DEXTER_REQUEST)
    request.context.update(user_id="audit-user", user_role="reviewer")

    def unexpected_context(**_kwargs):
        raise AssertionError("unauthorized provider reached the context builder")

    monkeypatch.setattr(
        dexter_agent_service, "build_dexter_research_context", unexpected_context
    )
    with pytest.raises(PermissionError, match="choice_news.data"):
        dexter_agent_service.execute_dexter_agent_query(
            request, str(settings.governance_path), settings
        )


def test_provider_business_reads_require_server_bound_user(boundary, monkeypatch):
    _client, settings, _scopes = boundary
    prompts = _capture_dexter(monkeypatch)

    with pytest.raises(PermissionError, match="server-bound user"):
        dexter_agent_service.execute_dexter_agent_query(
            AgentQueryRequest.model_validate(DEXTER_REQUEST),
            str(settings.governance_path),
            settings,
        )
    with pytest.raises(PermissionError, match="server-bound user"):
        hermes_agent_service.build_local_recovery_envelope(
            request=AgentQueryRequest.model_validate(NEWS_REQUEST),
            governance_dir=str(settings.governance_path),
            settings=settings,
        )
    assert prompts == []


@pytest.mark.parametrize(
    "error", [PermissionError("read revoked"), RuntimeError("scope store unavailable")]
)
def test_query_propagates_provider_resource_check_failure(boundary, monkeypatch, error):
    client, settings, scopes = boundary
    settings.agent_provider = "dexter"
    _grant(scopes, "market_data.livermore", "choice_news.data")
    prompts = _capture_dexter(monkeypatch)

    def denied_at_execution(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(
        dexter_agent_service,
        "ensure_agent_execution_resources_allowed",
        denied_at_execution,
    )
    response = client.post("/api/agent/query", json=DEXTER_REQUEST)

    assert response.status_code == (
        403 if isinstance(error, PermissionError) else 503
    ), response.text
    assert prompts == []
