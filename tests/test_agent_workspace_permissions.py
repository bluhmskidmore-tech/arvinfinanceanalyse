from __future__ import annotations

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
from tests.test_agent_api_contract import (
    _agent_auth_fields,
    _seed_agent_read_scope,
    _seed_agent_scope,
)

import pytest

pytestmark = [
    pytest.mark.excluded_surface_acceptance,
    pytest.mark.surface_agent_mvp,
]

OWNER_HEADERS = {
    "X-User-Id": "workspace-owner",
    "X-User-Role": "reviewer",
}
OTHER_HEADERS = {
    "X-User-Id": "workspace-other",
    "X-User-Role": "reviewer",
}
SPOOFED_HEADERS = {
    "X-User-Id": "spoofed-owner",
    "X-User-Role": "admin",
}


def _settings(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        environment="production",
        agent_enabled=True,
        agent_provider="local",
        duckdb_path=str(tmp_path / "moss.duckdb"),
        governance_path=str(tmp_path / "governance"),
        **_agent_auth_fields(tmp_path),
    )


def _sample_envelope(question: str) -> AgentEnvelope:
    return AgentEnvelope(
        answer=f"Server answer for: {question}",
        cards=[],
        evidence=AgentEvidence(
            tables_used=["fact_formal_bond_analytics_daily"],
            filters_applied={"report_date": "2026-03-31"},
            evidence_rows=1,
            quality_flag="ok",
        ),
        result_meta=AgentResultMeta(
            trace_id=f"tr_workspace_{question.replace(' ', '_')}",
            basis="formal",
            result_kind="agent.duration_risk",
            formal_use_allowed=False,
            source_version="sv_workspace_test",
            vendor_version="vv_workspace_test",
            rule_version="rv_workspace_test",
            cache_version="cv_workspace_test",
            quality_flag="ok",
            scenario_flag=False,
            tables_used=["fact_formal_bond_analytics_daily"],
            filters_applied={"report_date": "2026-03-31"},
            evidence_rows=1,
        ),
    )


def _client(monkeypatch, tmp_path: Path) -> TestClient:
    route_module = load_module(
        "backend.app.api.routes.agent",
        "backend/app/api/routes/agent.py",
    )
    _seed_agent_read_scope(tmp_path, monkeypatch)
    _seed_agent_scope(tmp_path, monkeypatch, action="write")
    _seed_agent_scope(tmp_path, monkeypatch, action="execute")
    monkeypatch.setenv("MOSS_AUTH_TRUST_X_USER_ROLE_FOR_DEV_TEST", "1")
    settings = _settings(tmp_path)
    monkeypatch.setattr(route_module, "get_settings", lambda: settings)
    workspace_route_module = __import__(
        "backend.app.api.routes.agent_workspace",
        fromlist=["get_settings"],
    )
    monkeypatch.setattr(
        workspace_route_module,
        "get_settings",
        lambda: settings,
    )

    def execute(request, *_args, **_kwargs):
        return _sample_envelope(request.question)

    monkeypatch.setattr(route_module, "execute_agent_query", execute)
    service_module = __import__(
        "backend.app.services.agent_run_service",
        fromlist=["execute_agent_run_task"],
    )
    service_module._AGENT_RUN_LATEST_RECORDS.clear()

    def dispatch_inline(*, run_id):
        return service_module.execute_agent_run_by_id(
            run_id=run_id,
            settings=settings,
            executor=execute,
        )

    monkeypatch.setattr(service_module.execute_agent_run_task, "send", dispatch_inline)
    app = FastAPI()
    app.include_router(route_module.router)
    return TestClient(app)


def _create_project(
    client: TestClient,
    *,
    headers: dict[str, str] = OWNER_HEADERS,
    name: str = "Rates research",
) -> dict[str, object]:
    response = client.post(
        "/api/agent/projects",
        json={"name": name},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _create_conversation(
    client: TestClient,
    project_id: str,
    *,
    headers: dict[str, str] = OWNER_HEADERS,
    title: str = "Duration review",
) -> dict[str, object]:
    response = client.post(
        f"/api/agent/projects/{project_id}/conversations",
        json={"title": title},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _create_completed_run(
    client: TestClient,
    conversation_id: str,
    *,
    headers: dict[str, str] = OWNER_HEADERS,
    question: str = "Explain portfolio duration",
) -> dict[str, object]:
    created_response = client.post(
        "/api/agent/runs",
        json={
            "question": question,
            "context": {"conversation_id": conversation_id},
        },
        headers=headers,
    )
    assert created_response.status_code == 200, created_response.text
    run_id = created_response.json()["run_id"]
    status_response = client.get(
        f"/api/agent/runs/{run_id}",
        headers=headers,
    )
    assert status_response.status_code == 200, status_response.text
    completed = status_response.json()
    assert completed["status"] == "completed"
    return completed


def test_project_and_conversation_crud_are_owner_isolated(
    monkeypatch,
    tmp_path,
) -> None:
    client = _client(monkeypatch, tmp_path)
    project = _create_project(client)
    project_id = str(project["project_id"])

    owner_list = client.get("/api/agent/projects", headers=OWNER_HEADERS)
    other_list = client.get("/api/agent/projects", headers=OTHER_HEADERS)
    owner_get = client.get(
        f"/api/agent/projects/{project_id}",
        headers=OWNER_HEADERS,
    )
    other_get = client.get(
        f"/api/agent/projects/{project_id}",
        headers=OTHER_HEADERS,
    )
    other_patch = client.patch(
        f"/api/agent/projects/{project_id}",
        json={"name": "Hijacked"},
        headers=OTHER_HEADERS,
    )
    owner_patch = client.patch(
        f"/api/agent/projects/{project_id}",
        json={"name": "Rates research updated"},
        headers=OWNER_HEADERS,
    )

    assert owner_list.status_code == 200
    assert [item["project_id"] for item in owner_list.json()["items"]] == [
        project_id
    ]
    assert other_list.status_code == 200
    assert other_list.json()["items"] == []
    assert owner_get.status_code == 200
    assert owner_get.json()["owner_user_id"] == OWNER_HEADERS["X-User-Id"]
    assert other_get.status_code == 403
    assert other_patch.status_code == 403
    assert owner_patch.status_code == 200
    assert owner_patch.json()["name"] == "Rates research updated"

    conversation = _create_conversation(client, project_id)
    conversation_id = str(conversation["conversation_id"])
    owner_conversations = client.get(
        f"/api/agent/projects/{project_id}/conversations",
        headers=OWNER_HEADERS,
    )
    other_conversations = client.get(
        f"/api/agent/projects/{project_id}/conversations",
        headers=OTHER_HEADERS,
    )
    owner_conversation = client.get(
        f"/api/agent/conversations/{conversation_id}",
        headers=OWNER_HEADERS,
    )
    other_conversation = client.get(
        f"/api/agent/conversations/{conversation_id}",
        headers=OTHER_HEADERS,
    )

    assert owner_conversations.status_code == 200
    assert [
        item["conversation_id"]
        for item in owner_conversations.json()["items"]
    ] == [conversation_id]
    assert other_conversations.status_code == 403
    assert owner_conversation.status_code == 200
    assert owner_conversation.json()["project_id"] == project_id
    assert other_conversation.status_code == 403


def test_client_cannot_forge_workspace_owner(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)

    rejected = client.post(
        "/api/agent/projects",
        json={
            "name": "Spoofed owner",
            "owner_user_id": SPOOFED_HEADERS["X-User-Id"],
        },
        headers=OWNER_HEADERS,
    )
    assert rejected.status_code == 422

    project = _create_project(
        client,
        name="Owned by auth context",
    )
    assert project["owner_user_id"] == OWNER_HEADERS["X-User-Id"]
    assert (
        client.get(
            f"/api/agent/projects/{project['project_id']}",
            headers=SPOOFED_HEADERS,
        ).status_code
        == 403
    )
    assert (
        client.get(
            f"/api/agent/projects/{project['project_id']}",
            headers=OWNER_HEADERS,
        ).status_code
        == 200
    )


def test_archived_project_is_hidden_and_rejects_new_conversations_and_runs(
    monkeypatch,
    tmp_path,
) -> None:
    client = _client(monkeypatch, tmp_path)
    project = _create_project(client)
    project_id = str(project["project_id"])
    conversation = _create_conversation(client, project_id)
    conversation_id = str(conversation["conversation_id"])

    archived = client.patch(
        f"/api/agent/projects/{project_id}",
        json={"archived": True},
        headers=OWNER_HEADERS,
    )
    default_list = client.get("/api/agent/projects", headers=OWNER_HEADERS)
    archived_history = client.get(
        f"/api/agent/projects/{project_id}",
        headers=OWNER_HEADERS,
    )
    rejected_conversation = client.post(
        f"/api/agent/projects/{project_id}/conversations",
        json={"title": "Must not be created"},
        headers=OWNER_HEADERS,
    )
    rejected_run = client.post(
        "/api/agent/runs",
        json={
            "question": "Must not run",
            "context": {"conversation_id": conversation_id},
        },
        headers=OWNER_HEADERS,
    )

    assert archived.status_code == 200, archived.text
    assert archived.json()["archived_at"] is not None
    assert default_list.status_code == 200
    assert default_list.json()["items"] == []
    assert archived_history.status_code == 200
    assert archived_history.json()["project_id"] == project_id
    assert rejected_conversation.status_code == 409
    assert rejected_run.status_code == 409


def test_conversation_filter_restores_server_messages_and_artifacts(
    monkeypatch,
    tmp_path,
) -> None:
    client = _client(monkeypatch, tmp_path)
    project = _create_project(client)
    project_id = str(project["project_id"])
    conversation = _create_conversation(client, project_id)
    other_conversation = _create_conversation(
        client,
        project_id,
        title="Credit review",
    )
    conversation_id = str(conversation["conversation_id"])
    other_conversation_id = str(other_conversation["conversation_id"])

    completed = _create_completed_run(
        client,
        conversation_id,
        question="Explain duration move",
    )
    other_completed = _create_completed_run(
        client,
        other_conversation_id,
        question="Explain spread move",
    )
    run_id = str(completed["run_id"])

    filtered_runs = client.get(
        "/api/agent/runs",
        params={"conversation_id": conversation_id},
        headers=OWNER_HEADERS,
    )
    conversation_after_run = client.get(
        f"/api/agent/conversations/{conversation_id}",
        headers=OWNER_HEADERS,
    )
    messages_response = client.get(
        f"/api/agent/conversations/{conversation_id}/messages",
        headers=OWNER_HEADERS,
    )
    artifacts_response = client.get(
        f"/api/agent/conversations/{conversation_id}/artifacts",
        headers=OWNER_HEADERS,
    )

    assert filtered_runs.status_code == 200
    assert [item["run_id"] for item in filtered_runs.json()["items"]] == [
        run_id
    ]
    assert other_completed["run_id"] not in {
        item["run_id"] for item in filtered_runs.json()["items"]
    }
    assert conversation_after_run.status_code == 200
    assert conversation_after_run.json()["last_run_id"] == run_id

    assert messages_response.status_code == 200
    messages = messages_response.json()["items"]
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "Explain duration move"
    assert messages[0]["run_id"] == run_id
    assert messages[1]["content"] == "Server answer for: Explain duration move"
    assert messages[1]["result"]["result_meta"]["formal_use_allowed"] is False

    assert artifacts_response.status_code == 200
    artifacts = artifacts_response.json()["items"]
    assert len(artifacts) == 1
    artifact_id = artifacts[0]["artifact_id"]
    assert artifact_id == f"artifact:{run_id}"
    assert messages[1]["artifact_refs"] == [artifact_id]
    assert artifacts[0]["result_meta"]["trace_id"] == (
        completed["result"]["result_meta"]["trace_id"]
    )

    artifact_response = client.get(
        f"/api/agent/artifacts/{artifact_id}",
        headers=OWNER_HEADERS,
    )
    assert artifact_response.status_code == 200
    artifact = artifact_response.json()
    assert artifact["conversation_id"] == conversation_id
    assert artifact["run_id"] == run_id
    assert artifact["kind"] == "agent_envelope"
    assert artifact["content"]["answer"] == (
        "Server answer for: Explain duration move"
    )
    assert artifact["content"]["result_meta"]["formal_use_allowed"] is False


def test_cross_user_project_conversation_run_and_artifact_access_is_forbidden(
    monkeypatch,
    tmp_path,
) -> None:
    client = _client(monkeypatch, tmp_path)
    project = _create_project(client)
    project_id = str(project["project_id"])
    conversation = _create_conversation(client, project_id)
    conversation_id = str(conversation["conversation_id"])
    completed = _create_completed_run(client, conversation_id)
    run_id = str(completed["run_id"])
    artifact_id = f"artifact:{run_id}"

    responses = [
        client.get(
            f"/api/agent/projects/{project_id}",
            headers=OTHER_HEADERS,
        ),
        client.get(
            f"/api/agent/projects/{project_id}/conversations",
            headers=OTHER_HEADERS,
        ),
        client.get(
            f"/api/agent/conversations/{conversation_id}",
            headers=OTHER_HEADERS,
        ),
        client.get(
            f"/api/agent/conversations/{conversation_id}/messages",
            headers=OTHER_HEADERS,
        ),
        client.get(
            f"/api/agent/conversations/{conversation_id}/artifacts",
            headers=OTHER_HEADERS,
        ),
        client.get(
            "/api/agent/runs",
            params={"conversation_id": conversation_id},
            headers=OTHER_HEADERS,
        ),
        client.get(
            f"/api/agent/runs/{run_id}",
            headers=OTHER_HEADERS,
        ),
        client.get(
            f"/api/agent/artifacts/{artifact_id}",
            headers=OTHER_HEADERS,
        ),
    ]

    assert [response.status_code for response in responses] == [403] * len(
        responses
    )


def test_unknown_workspace_resources_return_404(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    project_id = "project:missing"
    conversation_id = "conversation:missing"
    run_id = "agent_run:missing"
    artifact_id = "artifact:agent_run:missing"

    responses = [
        client.get(
            f"/api/agent/projects/{project_id}",
            headers=OWNER_HEADERS,
        ),
        client.patch(
            f"/api/agent/projects/{project_id}",
            json={"name": "Missing"},
            headers=OWNER_HEADERS,
        ),
        client.get(
            f"/api/agent/projects/{project_id}/conversations",
            headers=OWNER_HEADERS,
        ),
        client.post(
            f"/api/agent/projects/{project_id}/conversations",
            json={"title": "Missing"},
            headers=OWNER_HEADERS,
        ),
        client.get(
            f"/api/agent/conversations/{conversation_id}",
            headers=OWNER_HEADERS,
        ),
        client.get(
            f"/api/agent/conversations/{conversation_id}/messages",
            headers=OWNER_HEADERS,
        ),
        client.get(
            f"/api/agent/conversations/{conversation_id}/artifacts",
            headers=OWNER_HEADERS,
        ),
        client.get(
            "/api/agent/runs",
            params={"conversation_id": conversation_id},
            headers=OWNER_HEADERS,
        ),
        client.get(
            f"/api/agent/runs/{run_id}",
            headers=OWNER_HEADERS,
        ),
        client.get(
            f"/api/agent/artifacts/{artifact_id}",
            headers=OWNER_HEADERS,
        ),
        client.post(
            "/api/agent/runs",
            json={
                "question": "Missing workspace",
                "context": {"conversation_id": conversation_id},
            },
            headers=OWNER_HEADERS,
        ),
    ]

    assert [response.status_code for response in responses] == [404] * len(
        responses
    )
