from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.agent.schemas.agent_response import (
    AgentEnvelope,
    AgentEvidence,
    AgentResultMeta,
)
from backend.app.repositories.agent_workspace_repo import (
    AGENT_WORKSPACE_PROJECT_STREAM,
)
from backend.app.repositories.governance_repo import GovernanceRepository
from tests.helpers import load_module
from tests.test_agent_api_contract import (
    _agent_auth_fields,
    _seed_agent_read_scope,
    _seed_agent_scope,
)

pytestmark = [
    pytest.mark.excluded_surface_acceptance,
    pytest.mark.surface_agent_mvp,
]


def _settings(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        environment="production",
        agent_enabled=True,
        agent_provider="local",
        duckdb_path=str(tmp_path / "moss.duckdb"),
        governance_path=str(tmp_path / "governance"),
        **_agent_auth_fields(tmp_path),
    )


def _loopback_request() -> SimpleNamespace:
    return SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))


def _sample_envelope() -> AgentEnvelope:
    return AgentEnvelope(
        answer="Workspace-backed answer.",
        cards=[],
        evidence=AgentEvidence(
            tables_used=["fact_formal_pnl_fi"],
            filters_applied={"report_date": "2026-06-30"},
            evidence_rows=1,
            quality_flag="ok",
        ),
        result_meta=AgentResultMeta(
            trace_id="tr_workspace_api",
            basis="formal",
            result_kind="agent.workspace_test",
            formal_use_allowed=False,
            source_version="sv_workspace_test",
            vendor_version="vv_none",
            rule_version="rv_workspace_v1",
            cache_version="cv_workspace_v1",
            quality_flag="ok",
            scenario_flag=False,
            tables_used=["fact_formal_pnl_fi"],
            filters_applied={"report_date": "2026-06-30"},
            evidence_rows=1,
        ),
    )


def _client(
    monkeypatch,
    tmp_path: Path,
    *,
    complete_runs: bool = True,
    grant_write: bool = True,
    grant_execute: bool = True,
    raise_server_exceptions: bool = True,
    client_host: str = "testclient",
) -> tuple[TestClient, SimpleNamespace]:
    monkeypatch.setenv("MOSS_AUTH_TRUST_X_USER_ROLE_FOR_DEV_TEST", "1")
    _seed_agent_read_scope(tmp_path, monkeypatch)
    if grant_write:
        _seed_agent_scope(tmp_path, monkeypatch, action="write")
    if grant_execute:
        _seed_agent_scope(tmp_path, monkeypatch, action="execute")
    settings = _settings(tmp_path)
    route_module = load_module(
        "backend.app.api.routes.agent",
        "backend/app/api/routes/agent.py",
    )
    workspace_route_module = importlib.import_module(
        "backend.app.api.routes.agent_workspace"
    )
    monkeypatch.setattr(route_module, "get_settings", lambda: settings)
    monkeypatch.setattr(workspace_route_module, "get_settings", lambda: settings)

    service_module = __import__(
        "backend.app.services.agent_run_service",
        fromlist=["execute_agent_run_task"],
    )
    service_module._AGENT_RUN_LATEST_RECORDS.clear()

    if complete_runs:

        def dispatch_inline(*, run_id: str):
            return service_module.execute_agent_run_by_id(
                run_id=run_id,
                settings=settings,
                executor=lambda _request, _governance_dir, _settings: _sample_envelope(),
            )

    else:

        def dispatch_inline(*, run_id: str):
            return None

    monkeypatch.setattr(
        service_module.execute_agent_run_task,
        "send",
        dispatch_inline,
    )
    app = FastAPI()
    app.include_router(route_module.router)
    return TestClient(
        app,
        client=(client_host, 50000),
        raise_server_exceptions=raise_server_exceptions,
    ), settings


def _headers(user_id: str) -> dict[str, str]:
    return {
        "X-User-Id": user_id,
        "X-User-Role": "reviewer",
    }


def _create_project_and_conversation(
    client: TestClient,
    *,
    headers: dict[str, str],
) -> tuple[dict[str, object], dict[str, object]]:
    project_response = client.post(
        "/api/agent/projects",
        json={"name": "Rates review"},
        headers=headers,
    )
    assert project_response.status_code == 200
    project = project_response.json()
    conversation_response = client.post(
        f"/api/agent/projects/{project['project_id']}/conversations",
        json={"title": "June duration review"},
        headers=headers,
    )
    assert conversation_response.status_code == 200
    return project, conversation_response.json()


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("post", "/api/agent/projects", {"name": "Blocked project"}),
        ("get", "/api/agent/projects", None),
        ("get", "/api/agent/projects/project:blocked", None),
        ("patch", "/api/agent/projects/project:blocked", {"archived": True}),
        (
            "post",
            "/api/agent/projects/project:blocked/conversations",
            {"title": "Blocked conversation"},
        ),
        ("get", "/api/agent/projects/project:blocked/conversations", None),
        ("get", "/api/agent/conversations/conversation:blocked", None),
        ("get", "/api/agent/conversations/conversation:blocked/messages", None),
        ("get", "/api/agent/conversations/conversation:blocked/artifacts", None),
        ("get", "/api/agent/artifacts/artifact:blocked", None),
    ],
)
def test_workspace_endpoints_fail_closed_without_writing_when_agent_is_disabled(
    monkeypatch,
    tmp_path,
    method: str,
    path: str,
    payload: dict[str, object] | None,
) -> None:
    client, settings = _client(monkeypatch, tmp_path, client_host="127.0.0.1")
    settings.agent_enabled = False
    workspace_route_module = importlib.import_module(
        "backend.app.api.routes.agent_workspace"
    )

    def storage_write_attempted(**_kwargs):
        raise AssertionError("Disabled Agent workspace endpoint attempted a storage write.")

    for service_name in ("create_project", "update_project", "create_conversation"):
        monkeypatch.setattr(
            workspace_route_module,
            service_name,
            storage_write_attempted,
        )
    response = client.request(
        method.upper(),
        path,
        json=payload,
        headers=_headers("workspace-owner"),
    )

    assert response.status_code == 503, (path, response.json())
    assert response.json()["detail"] == "Agent endpoint is planned but disabled in Phase 1."


def test_workspace_development_environment_bypasses_scope_store(monkeypatch) -> None:
    workspace_route_module = importlib.import_module(
        "backend.app.api.routes.agent_workspace"
    )
    scope_checks: list[str] = []

    def unexpected_scope_check(**kwargs):
        scope_checks.append(str(kwargs["action"]))
        raise AssertionError("development Agent workspace request reached the scope store")

    monkeypatch.setattr(
        workspace_route_module,
        "ensure_user_allowed",
        unexpected_scope_check,
    )
    auth = workspace_route_module.AuthContext(
        user_id="development-agent-user",
        role="developer",
        identity_source="fallback",
    )
    settings = SimpleNamespace(
        agent_enabled=True,
        environment="development",
        agent_dev_scope_bypass=True,
    )

    workspace_route_module._ensure_agent_workspace_allowed(
        auth,
        settings,
        http_request=_loopback_request(),
        action="read",
    )
    workspace_route_module._ensure_agent_workspace_allowed(
        auth,
        settings,
        http_request=_loopback_request(),
        action="write",
    )

    assert scope_checks == []


def test_workspace_development_bypass_requires_explicit_opt_in(monkeypatch) -> None:
    workspace_route_module = importlib.import_module(
        "backend.app.api.routes.agent_workspace"
    )
    scope_checks: list[str] = []

    def record_scope_check(**kwargs):
        scope_checks.append(str(kwargs["action"]))

    monkeypatch.setattr(
        workspace_route_module,
        "ensure_user_allowed",
        record_scope_check,
    )
    auth = workspace_route_module.AuthContext(
        user_id="development-agent-user",
        role="developer",
        identity_source="fallback",
    )

    workspace_route_module._ensure_agent_workspace_allowed(
        auth,
        SimpleNamespace(
            agent_enabled=True,
            environment="development",
            agent_dev_scope_bypass=False,
        ),
        http_request=_loopback_request(),
        action="read",
    )
    workspace_route_module._ensure_agent_workspace_allowed(
        auth,
        SimpleNamespace(
            agent_enabled=True,
            agent_dev_scope_bypass=True,
        ),
        http_request=_loopback_request(),
        action="write",
    )
    workspace_route_module._ensure_agent_workspace_allowed(
        auth,
        SimpleNamespace(
            agent_enabled=True,
            environment=" ",
            agent_dev_scope_bypass=True,
        ),
        http_request=_loopback_request(),
        action="read",
    )
    workspace_route_module._ensure_agent_workspace_allowed(
        auth,
        SimpleNamespace(
            agent_enabled=True,
            environment="staging",
            agent_dev_scope_bypass=True,
        ),
        http_request=_loopback_request(),
        action="write",
    )

    assert scope_checks == ["read", "write", "read", "write"]


def test_workspace_development_bypass_preserves_owner_isolation(
    monkeypatch,
    tmp_path,
) -> None:
    client, settings = _client(monkeypatch, tmp_path, client_host="127.0.0.1")
    settings.environment = "development"
    settings.agent_dev_scope_bypass = True
    workspace_route_module = importlib.import_module(
        "backend.app.api.routes.agent_workspace"
    )

    def unexpected_scope_check(**_kwargs):
        raise AssertionError("explicit development bypass reached the scope store")

    monkeypatch.setattr(
        workspace_route_module,
        "ensure_user_allowed",
        unexpected_scope_check,
    )
    owner_headers = _headers("development-owner")
    project_response = client.post(
        "/api/agent/projects",
        json={"name": "Development project"},
        headers=owner_headers,
    )

    assert project_response.status_code == 200
    project_id = project_response.json()["project_id"]
    denied = client.get(
        f"/api/agent/projects/{project_id}",
        headers=_headers("development-other-user"),
    )
    assert denied.status_code == 403


def test_workspace_mutations_require_write_scope_before_storage_access(
    monkeypatch,
    tmp_path,
) -> None:
    client, _settings_value = _client(
        monkeypatch,
        tmp_path,
        grant_write=False,
        raise_server_exceptions=False,
    )
    workspace_route_module = importlib.import_module(
        "backend.app.api.routes.agent_workspace"
    )
    storage_calls: list[str] = []

    def unexpected_storage_call(**_kwargs):
        storage_calls.append("called")
        raise AssertionError("workspace mutation reached storage without agent/write")

    for service_name in ("create_project", "update_project", "create_conversation"):
        monkeypatch.setattr(
            workspace_route_module,
            service_name,
            unexpected_storage_call,
        )

    responses = [
        client.post(
            "/api/agent/projects",
            json={"name": "Blocked project"},
        ),
        client.patch(
            "/api/agent/projects/project:blocked",
            json={"archived": True},
        ),
        client.post(
            "/api/agent/projects/project:blocked/conversations",
            json={"title": "Blocked conversation"},
        ),
    ]

    assert [response.status_code for response in responses] == [403, 403, 403]
    assert all(
        "write agent" in response.json()["detail"]
        for response in responses
    )
    assert storage_calls == []


def test_workspace_projects_conversations_runs_messages_and_artifacts_are_closed_loop(
    monkeypatch,
    tmp_path,
) -> None:
    client, _settings_value = _client(monkeypatch, tmp_path)
    headers = _headers("workspace-owner")
    project, conversation = _create_project_and_conversation(
        client,
        headers=headers,
    )

    assert project["default_scope"] == "all"
    assert project["default_currency_basis"] == "CNY"
    assert project["archived_at"] is None
    assert conversation["last_run_id"] is None

    created_response = client.post(
        "/api/agent/runs",
        json={
            "question": "Summarize the June duration review.",
            "context": {
                "conversation_id": f"  {conversation['conversation_id']}  ",
                "artifact_refs": ["artifact:client-spoof"],
                "retry_of_run_id": "agent_run:client-spoof",
            },
        },
        headers=headers,
    )
    assert created_response.status_code == 200
    created = created_response.json()
    assert created["conversation_id"] == conversation["conversation_id"]
    assert "artifact_refs" not in created
    assert "retry_of_run_id" not in created

    status = client.get(
        f"/api/agent/runs/{created['run_id']}",
        headers=headers,
    ).json()
    artifact_id = f"artifact:{created['run_id']}"
    assert status["status"] == "completed"
    assert status["conversation_id"] == conversation["conversation_id"]
    assert status["artifact_refs"] == [artifact_id]

    runs_response = client.get(
        "/api/agent/runs",
        params={"conversation_id": conversation["conversation_id"]},
        headers=headers,
    )
    assert runs_response.status_code == 200
    assert [run["run_id"] for run in runs_response.json()["items"]] == [
        created["run_id"]
    ]

    messages_response = client.get(
        f"/api/agent/conversations/{conversation['conversation_id']}/messages",
        headers=headers,
    )
    assert messages_response.status_code == 200
    messages = messages_response.json()["items"]
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "Summarize the June duration review."
    assert messages[1]["artifact_refs"] == [artifact_id]
    assert messages[1]["result"]["answer"] == "Workspace-backed answer."

    artifacts_response = client.get(
        f"/api/agent/conversations/{conversation['conversation_id']}/artifacts",
        headers=headers,
    )
    assert artifacts_response.status_code == 200
    artifacts = artifacts_response.json()["items"]
    assert [artifact["artifact_id"] for artifact in artifacts] == [artifact_id]
    assert artifacts[0]["result_meta"]["trace_id"] == "tr_workspace_api"

    artifact_response = client.get(
        f"/api/agent/artifacts/{artifact_id}",
        headers=headers,
    )
    assert artifact_response.status_code == 200
    assert artifact_response.json()["content"]["answer"] == "Workspace-backed answer."

    conversations_response = client.get(
        f"/api/agent/projects/{project['project_id']}/conversations",
        headers=headers,
    )
    assert conversations_response.status_code == 200
    restored = conversations_response.json()["items"][0]
    assert restored["last_run_id"] == created["run_id"]


def test_workspace_project_and_conversation_names_round_trip_unicode_verbatim(
    monkeypatch,
    tmp_path,
) -> None:
    client, _settings_value = _client(monkeypatch, tmp_path)
    headers = _headers("workspace-owner")
    project_name = "利率复核项目"
    conversation_title = "七月久期复盘"

    project_response = client.post(
        "/api/agent/projects",
        json={"name": project_name},
        headers=headers,
    )
    assert project_response.status_code == 200
    project = project_response.json()
    assert project["name"] == project_name

    listed_projects_response = client.get("/api/agent/projects", headers=headers)
    assert listed_projects_response.status_code == 200
    assert listed_projects_response.json()["items"] == [project]

    fetched_project_response = client.get(
        f"/api/agent/projects/{project['project_id']}",
        headers=headers,
    )
    assert fetched_project_response.status_code == 200
    assert fetched_project_response.json()["name"] == project_name

    conversation_response = client.post(
        f"/api/agent/projects/{project['project_id']}/conversations",
        json={"title": conversation_title},
        headers=headers,
    )
    assert conversation_response.status_code == 200
    conversation = conversation_response.json()
    assert conversation["title"] == conversation_title

    listed_conversations_response = client.get(
        f"/api/agent/projects/{project['project_id']}/conversations",
        headers=headers,
    )
    assert listed_conversations_response.status_code == 200
    assert listed_conversations_response.json()["items"] == [conversation]

    fetched_conversation_response = client.get(
        f"/api/agent/conversations/{conversation['conversation_id']}",
        headers=headers,
    )
    assert fetched_conversation_response.status_code == 200
    assert fetched_conversation_response.json()["title"] == conversation_title


def test_workspace_owner_and_archive_guards_apply_to_linked_runs(
    monkeypatch,
    tmp_path,
) -> None:
    client, _settings_value = _client(
        monkeypatch,
        tmp_path,
        complete_runs=False,
    )
    owner_headers = _headers("workspace-owner")
    other_headers = _headers("other-user")
    project, conversation = _create_project_and_conversation(
        client,
        headers=owner_headers,
    )

    for method, path in (
        ("get", f"/api/agent/projects/{project['project_id']}"),
        ("get", f"/api/agent/conversations/{conversation['conversation_id']}"),
    ):
        response = getattr(client, method)(path, headers=other_headers)
        assert response.status_code == 403, (path, response.json())
    denied_run_list = client.get(
        "/api/agent/runs",
        params={"conversation_id": conversation["conversation_id"]},
        headers=other_headers,
    )
    assert denied_run_list.status_code == 403

    denied_run = client.post(
        "/api/agent/runs",
        json={
            "question": "Cross-owner run",
            "context": {"conversation_id": conversation["conversation_id"]},
        },
        headers=other_headers,
    )
    assert denied_run.status_code == 403

    retry_source = client.post(
        "/api/agent/runs",
        json={
            "question": "Retryable workspace run",
            "context": {"conversation_id": conversation["conversation_id"]},
        },
        headers=owner_headers,
    ).json()
    cancelled_source = client.post(
        f"/api/agent/runs/{retry_source['run_id']}/cancel",
        headers=owner_headers,
    )
    assert cancelled_source.status_code == 200
    retried_response = client.post(
        f"/api/agent/runs/{retry_source['run_id']}/retry",
        headers=owner_headers,
    )
    assert retried_response.status_code == 200
    retried = retried_response.json()
    assert retried["conversation_id"] == conversation["conversation_id"]
    assert retried["retry_of_run_id"] == retry_source["run_id"]
    client.post(
        f"/api/agent/runs/{retried['run_id']}/cancel",
        headers=owner_headers,
    )

    created = client.post(
        "/api/agent/runs",
        json={
            "question": "Queued workspace run",
            "context": {"conversation_id": conversation["conversation_id"]},
        },
        headers=owner_headers,
    ).json()
    archived_response = client.patch(
        f"/api/agent/projects/{project['project_id']}",
        json={"archived": True},
        headers=owner_headers,
    )
    assert archived_response.status_code == 200
    assert archived_response.json()["archived_at"] is not None

    new_conversation = client.post(
        f"/api/agent/projects/{project['project_id']}/conversations",
        json={"title": "Blocked conversation"},
        headers=owner_headers,
    )
    assert new_conversation.status_code == 409

    new_run = client.post(
        "/api/agent/runs",
        json={
            "question": "Blocked run",
            "context": {"conversation_id": conversation["conversation_id"]},
        },
        headers=owner_headers,
    )
    assert new_run.status_code == 409

    cancelled = client.post(
        f"/api/agent/runs/{created['run_id']}/cancel",
        headers=owner_headers,
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    retry = client.post(
        f"/api/agent/runs/{created['run_id']}/retry",
        headers=owner_headers,
    )
    assert retry.status_code == 409

    archived_projects = client.get(
        "/api/agent/projects",
        params={"include_archived": True},
        headers=owner_headers,
    ).json()["items"]
    assert [item["project_id"] for item in archived_projects] == [
        project["project_id"]
    ]


def _append_corrupt_project_record(
    settings: SimpleNamespace,
    *,
    project_id: str,
    owner: str,
) -> None:
    # Missing created_at/updated_at makes the stored record fail validation.
    GovernanceRepository(base_dir=settings.governance_path).append(
        AGENT_WORKSPACE_PROJECT_STREAM,
        {"project_id": project_id, "owner_user_id": owner, "name": "Broken"},
    )


def test_workspace_list_skips_corrupt_records_and_scopes_count_to_owner(
    monkeypatch,
    tmp_path,
) -> None:
    client, settings = _client(monkeypatch, tmp_path)
    headers = _headers("workspace-owner")
    project_response = client.post(
        "/api/agent/projects",
        json={"name": "Rates review"},
        headers=headers,
    )
    assert project_response.status_code == 200
    project = project_response.json()
    _append_corrupt_project_record(
        settings,
        project_id="project:corrupt",
        owner="workspace-owner",
    )

    listed = client.get("/api/agent/projects", headers=headers)
    other_listed = client.get(
        "/api/agent/projects",
        headers=_headers("other-user"),
    )

    assert listed.status_code == 200
    body = listed.json()
    assert [item["project_id"] for item in body["items"]] == [
        project["project_id"]
    ]
    assert body["corrupt_records"] == 1
    assert other_listed.status_code == 200
    assert other_listed.json()["items"] == []
    assert other_listed.json()["corrupt_records"] == 0


def test_workspace_corrupt_record_is_not_reported_as_missing(
    monkeypatch,
    tmp_path,
) -> None:
    client, settings = _client(
        monkeypatch,
        tmp_path,
        raise_server_exceptions=False,
    )
    _append_corrupt_project_record(
        settings,
        project_id="project:corrupt",
        owner="workspace-owner",
    )

    corrupt = client.get(
        "/api/agent/projects/project:corrupt",
        headers=_headers("workspace-owner"),
    )
    missing = client.get(
        "/api/agent/projects/project:missing",
        headers=_headers("workspace-owner"),
    )
    foreign = client.get(
        "/api/agent/projects/project:corrupt",
        headers=_headers("other-user"),
    )

    # Corrupt-but-present records map to 409 with a fixed structured detail,
    # never to 404 (missing) or a generic 500.
    assert corrupt.status_code == 409
    assert corrupt.json()["detail"] == {
        "code": "AGENT_WORKSPACE_RECORD_CORRUPT",
        "message": "Agent workspace record is corrupt and cannot be read.",
    }
    # Stored record contents must not leak into the error response.
    assert "Broken" not in corrupt.text
    assert missing.status_code == 404
    assert foreign.status_code == 403


def test_workspace_corrupt_record_detail_is_machine_actionable_and_stable(
    monkeypatch,
    tmp_path,
) -> None:
    """The corrupt-record 409 detail must be a dict with a stable code so clients
    can distinguish it from lifecycle-conflict 409s (whose detail is a string)."""
    client, settings = _client(monkeypatch, tmp_path)
    _append_corrupt_project_record(
        settings,
        project_id="project:corrupt",
        owner="workspace-owner",
    )

    corrupt = client.get(
        "/api/agent/projects/project:corrupt",
        headers=_headers("workspace-owner"),
    )

    assert corrupt.status_code == 409
    detail = corrupt.json()["detail"]
    assert isinstance(detail, dict)
    assert set(detail) == {"code", "message"}
    assert detail["code"] == "AGENT_WORKSPACE_RECORD_CORRUPT"


def test_workspace_disabled_error_uses_flat_agent_disabled_contract(
    monkeypatch,
    tmp_path,
) -> None:
    """Workspace endpoints share the flat AgentDisabledResponse 503 body with
    /api/agent/query instead of an HTTPException-style {"detail": str} wrapper."""
    client, settings = _client(monkeypatch, tmp_path, client_host="127.0.0.1")
    settings.agent_enabled = False

    response = client.get(
        "/api/agent/projects",
        headers=_headers("workspace-owner"),
    )

    assert response.status_code == 503
    body = response.json()
    assert body["enabled"] is False
    assert body["phase"] == "phase1"
    assert body["detail"] == "Agent endpoint is planned but disabled in Phase 1."
