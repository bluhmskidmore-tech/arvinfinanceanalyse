from __future__ import annotations

import asyncio
import importlib
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.agent.schemas.agent_request import AgentQueryRequest
from backend.app.agent.schemas.agent_response import (
    AgentEnvelope,
    AgentEvidence,
    AgentResultMeta,
)
from backend.app.agent.schemas.agent_run import AgentRunRecord, AgentRunStatusResponse
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
        agent_provider="hermes",
        agent_hermes_command="hermes",
        agent_hermes_wsl_distro="",
        agent_hermes_home="",
        agent_hermes_transport="bridge",
        agent_hermes_bridge_url="http://127.0.0.1:7891",
        agent_hermes_model="gpt-test",
        agent_hermes_toolsets="file",
        agent_hermes_max_turns=3,
        agent_hermes_timeout_seconds=9.0,
        duckdb_path=str(tmp_path / "moss.duckdb"),
        governance_path=str(tmp_path / "governance"),
        **_agent_auth_fields(tmp_path),
    )


def _sample_envelope() -> AgentEnvelope:
    return AgentEnvelope(
        answer="Hermes managed answer.",
        cards=[],
        evidence=AgentEvidence(
            tables_used=["hermes_cli"],
            filters_applied={
                "provider": "hermes",
                "model": "gpt-test",
                "transport": "bridge",
                "toolsets": "file",
            },
            evidence_rows=1,
            quality_flag="ok",
        ),
        result_meta=AgentResultMeta(
            trace_id="tr_agent_run_test",
            basis="formal",
            result_kind="agent.hermes",
            formal_use_allowed=False,
            source_version="sv_hermes_cli",
            vendor_version="vv_hermes",
            rule_version="rv_agent_hermes_v1",
            cache_version="cv_agent_hermes_v1",
            quality_flag="ok",
            scenario_flag=False,
            tables_used=["hermes_cli"],
            filters_applied={"provider": "hermes"},
            evidence_rows=1,
        ),
    )


def _local_settings(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        agent_enabled=True,
        agent_provider="local",
        duckdb_path=str(tmp_path / "moss.duckdb"),
        governance_path=str(tmp_path / "governance"),
        **_agent_auth_fields(tmp_path),
    )


def _local_envelope() -> AgentEnvelope:
    sample = _sample_envelope()
    return sample.model_copy(
        update={
            "answer": "Local managed answer.",
            "evidence": sample.evidence.model_copy(
                update={
                    "tables_used": ["fact_formal_bond_analytics_daily"],
                    "filters_applied": {"report_date": "2026-03-31"},
                    "sql_executed": ["select * from fact_formal_bond_analytics_daily where report_date = ?"],
                }
            ),
            "result_meta": sample.result_meta.model_copy(
                update={
                    "result_kind": "agent.duration_risk",
                    "tables_used": ["fact_formal_bond_analytics_daily"],
                }
            ),
        }
    )


def _local_client(monkeypatch, tmp_path: Path, execute):
    route_module = load_module(
        "backend.app.api.routes.agent",
        "backend/app/api/routes/agent.py",
    )
    _seed_agent_read_scope(tmp_path, monkeypatch)
    settings = _local_settings(tmp_path)
    monkeypatch.setattr(route_module, "get_settings", lambda: settings)
    monkeypatch.setattr(route_module, "execute_agent_query", execute)
    service_module = __import__(
        "backend.app.services.agent_run_service",
        fromlist=["execute_agent_run_task"],
    )

    def dispatch_inline(*, run_id):
        def local_executor(request, _governance_dir, _settings):
            return execute(
                request,
                str(tmp_path / "moss.duckdb"),
                str(tmp_path / "governance"),
            )

        return service_module.execute_agent_run_by_id(
            run_id=run_id,
            settings=settings,
            executor=local_executor,
        )

    monkeypatch.setattr(service_module.execute_agent_run_task, "send", dispatch_inline)
    app = FastAPI()
    app.include_router(route_module.router)
    return TestClient(app), settings


def _client(
    monkeypatch,
    tmp_path: Path,
    execute,
    *,
    grant_execute: bool = True,
    grant_write: bool = False,
    raise_server_exceptions: bool = True,
):
    route_module = load_module(
        "backend.app.api.routes.agent",
        "backend/app/api/routes/agent.py",
    )
    workspace_route_module = importlib.import_module(
        "backend.app.api.routes.agent_workspace"
    )
    _seed_agent_read_scope(tmp_path, monkeypatch)
    if grant_write:
        _seed_agent_scope(tmp_path, monkeypatch, action="write")
    if grant_execute:
        _seed_agent_scope(tmp_path, monkeypatch, action="execute")
    settings = _settings(tmp_path)
    monkeypatch.setattr(route_module, "get_settings", lambda: settings)
    monkeypatch.setattr(workspace_route_module, "get_settings", lambda: settings)
    monkeypatch.setattr(route_module, "execute_hermes_agent_query", execute)
    service_module = __import__(
        "backend.app.services.agent_run_service",
        fromlist=["execute_agent_run_task"],
    )

    def dispatch_inline(*, run_id):
        return service_module.execute_agent_run_by_id(
            run_id=run_id,
            settings=settings,
            executor=execute,
        )

    monkeypatch.setattr(service_module.execute_agent_run_task, "send", dispatch_inline)
    app = FastAPI()
    app.include_router(route_module.router)
    return TestClient(
        app,
        raise_server_exceptions=raise_server_exceptions,
    ), settings


def _wait_for_terminal(client: TestClient, run_id: str, headers: dict[str, str] | None = None) -> dict[str, object]:
    payload: dict[str, object] = {}
    for _ in range(200):
        payload = client.get(f"/api/agent/runs/{run_id}", headers=headers).json()
        status = payload.get("status")
        if status in {"completed", "failed"}:
            return payload
        time.sleep(0.05)
    raise AssertionError(f"agent run did not finish: {run_id}; last_payload={payload}")


def _wait_for_terminal_record(settings, run_id: str) -> None:
    from backend.app.repositories.governance_repo import GovernanceRepository
    from backend.app.services.agent_run_service import AGENT_RUN_STREAM

    for _ in range(200):
        records = [
            record
            for record in GovernanceRepository(base_dir=settings.governance_path).read_all(AGENT_RUN_STREAM)
            if str(record.get("run_id") or "") == run_id
        ]
        if records and str(records[-1].get("status") or "") in {"completed", "failed"}:
            return
        time.sleep(0.05)
    raise AssertionError(f"agent run did not finish: {run_id}")


def _create_conversation(client: TestClient) -> dict[str, object]:
    project_response = client.post(
        "/api/agent/projects",
        json={"name": "Rates review"},
    )
    assert project_response.status_code == 200
    project = project_response.json()
    conversation_response = client.post(
        f"/api/agent/projects/{project['project_id']}/conversations",
        json={"title": "June duration review"},
    )
    assert conversation_response.status_code == 200
    return conversation_response.json()


def test_agent_run_events_sends_terminal_snapshot_and_closes(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path, lambda *_args, **_kwargs: _sample_envelope())
    created = client.post("/api/agent/runs", json={"question": "ping"}).json()
    completed = _wait_for_terminal(client, created["run_id"])

    response = client.get(f"/api/agent/runs/{created['run_id']}/events")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-accel-buffering"] == "no"
    assert response.text.startswith("event: run_update\n")
    assert response.text.endswith("\n\n")
    assert response.text.count("event: run_update\n") == 1
    data_line = response.text.splitlines()[1]
    assert data_line.startswith("data: ")
    assert json.loads(data_line.removeprefix("data: ")) == completed


def test_agent_run_event_iterator_orders_updates_and_suppresses_duplicates(monkeypatch, tmp_path):
    service_module = load_module(
        "backend.app.services.agent_run_service",
        "backend/app/services/agent_run_service.py",
    )
    initial = AgentRunStatusResponse(
        run_id="agent_run:sse-sequence",
        status="running",
        provider="hermes",
    )
    completed = initial.model_copy(
        update={
            "status": "completed",
            "finished_at": "2026-07-20T12:00:00+00:00",
        }
    )
    status_updates = iter([initial, completed])
    sleep_calls = []

    def fake_get_agent_run_status(*, run_id, settings):
        assert run_id == initial.run_id
        return next(status_updates)

    async def fake_sleep(delay):
        sleep_calls.append(delay)

    monkeypatch.setattr(service_module, "get_agent_run_status", fake_get_agent_run_status)
    monkeypatch.setattr(service_module.asyncio, "sleep", fake_sleep)

    async def collect_events():
        return [
            event
            async for event in service_module.iter_agent_run_events(
                run_id=initial.run_id,
                settings=_settings(tmp_path),
                initial_status=initial,
                poll_interval_seconds=0.5,
            )
        ]

    events = asyncio.run(collect_events())

    assert [json.loads(event.split("data: ", 1)[1])["status"] for event in events] == [
        "running",
        "completed",
    ]
    assert all(event.startswith("event: run_update\n") and event.endswith("\n\n") for event in events)
    assert sleep_calls == [0.5, 0.5]


def test_agent_run_event_iterator_emits_keepalive_comment_between_updates(
    monkeypatch,
    tmp_path,
):
    service_module = load_module(
        "backend.app.services.agent_run_service",
        "backend/app/services/agent_run_service.py",
    )
    initial = AgentRunStatusResponse(
        run_id="agent_run:sse-heartbeat",
        status="running",
        provider="hermes",
    )
    completed = initial.model_copy(
        update={
            "status": "completed",
            "finished_at": "2026-07-20T12:00:00+00:00",
        }
    )
    status_updates = iter([initial, initial, completed])
    clock = {"now": 0.0}

    def fake_get_agent_run_status(*, run_id, settings):
        assert run_id == initial.run_id
        return next(status_updates)

    async def fake_sleep(_delay):
        clock["now"] += 10.0

    monkeypatch.setattr(service_module, "get_agent_run_status", fake_get_agent_run_status)
    monkeypatch.setattr(service_module, "_monotonic", lambda: clock["now"])
    monkeypatch.setattr(service_module.asyncio, "sleep", fake_sleep)

    async def collect_events():
        return [
            event
            async for event in service_module.iter_agent_run_events(
                run_id=initial.run_id,
                settings=_settings(tmp_path),
                initial_status=initial,
                poll_interval_seconds=0.5,
                heartbeat_interval_seconds=15.0,
            )
        ]

    events = asyncio.run(collect_events())

    assert len(events) == 3
    assert events[0].startswith("event: run_update\n")
    assert '"status":"running"' in events[0]
    # The heartbeat is a bare SSE comment frame: EventSource-style parsers
    # ignore comment lines natively, so no new event shape is introduced.
    assert events[1] == ": keepalive\n\n"
    assert "event:" not in events[1]
    assert "data:" not in events[1]
    assert events[2].startswith("event: run_update\n")
    assert '"status":"completed"' in events[2]


def test_agent_run_events_rejects_different_header_user(monkeypatch, tmp_path):
    monkeypatch.setenv("MOSS_AUTH_TRUST_X_USER_ROLE_FOR_DEV_TEST", "1")
    client, settings = _client(
        monkeypatch,
        tmp_path,
        lambda *_args, **_kwargs: _sample_envelope(),
    )
    created = client.post(
        "/api/agent/runs",
        json={"question": "ping"},
        headers={"X-User-Id": "run-owner", "X-User-Role": "reviewer"},
    ).json()
    _wait_for_terminal_record(settings, created["run_id"])

    response = client.get(
        f"/api/agent/runs/{created['run_id']}/events",
        headers={"X-User-Id": "other-user", "X-User-Role": "reviewer"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Agent run belongs to a different user."


def test_agent_run_events_returns_404_for_unknown_run(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path, lambda *_args, **_kwargs: _sample_envelope())

    response = client.get("/api/agent/runs/agent_run:nope/events")

    assert response.status_code == 404
    assert "Unknown agent run_id=agent_run:nope" in response.json()["detail"]


def test_agent_run_lifecycle_endpoints_fail_closed_when_agent_disabled(monkeypatch, tmp_path):
    route_module = load_module(
        "backend.app.api.routes.agent",
        "backend/app/api/routes/agent.py",
    )
    settings = SimpleNamespace(agent_enabled=False)
    monkeypatch.setattr(route_module, "get_settings", lambda: settings)
    calls: list[str] = []

    def unexpected_service(*_args, **_kwargs):
        calls.append("service")
        raise AssertionError("disabled lifecycle endpoint must not call a service")

    monkeypatch.setattr(route_module, "_ensure_agent_read_allowed", unexpected_service)
    monkeypatch.setattr(route_module, "_ensure_agent_execute_allowed", unexpected_service)
    monkeypatch.setattr(route_module, "get_agent_run_owner", unexpected_service)
    monkeypatch.setattr(route_module, "get_agent_run_status", unexpected_service)
    monkeypatch.setattr(route_module, "list_agent_runs", unexpected_service)
    monkeypatch.setattr(route_module, "iter_agent_run_events", unexpected_service)
    monkeypatch.setattr(route_module, "cancel_agent_run", unexpected_service)
    monkeypatch.setattr(route_module, "retry_agent_run", unexpected_service)

    app = FastAPI()
    app.include_router(route_module.router)
    client = TestClient(app)
    run_id = "agent_run:disabled"
    responses = [
        client.get("/api/agent/runs"),
        client.get(f"/api/agent/runs/{run_id}"),
        client.get(f"/api/agent/runs/{run_id}/events"),
        client.post(f"/api/agent/runs/{run_id}/cancel"),
        client.post(f"/api/agent/runs/{run_id}/retry"),
    ]

    assert [response.status_code for response in responses] == [503, 503, 503, 503, 503]
    assert calls == []


def test_agent_run_mutations_require_execute_scope_before_owner_lookup(
    monkeypatch,
    tmp_path,
) -> None:
    client, _settings_value = _client(
        monkeypatch,
        tmp_path,
        lambda *_args, **_kwargs: _sample_envelope(),
        grant_execute=False,
        grant_write=True,
        raise_server_exceptions=False,
    )
    route_module = __import__(
        "backend.app.api.routes.agent",
        fromlist=["get_agent_run_owner"],
    )
    owner_lookups: list[str] = []

    def unexpected_owner_lookup(*_args, **_kwargs):
        owner_lookups.append("called")
        raise AssertionError("run mutation reached owner lookup without agent/execute")

    monkeypatch.setattr(
        route_module,
        "get_agent_run_owner",
        unexpected_owner_lookup,
    )
    run_id = "agent_run:execute-scope-required"

    responses = [
        client.post(f"/api/agent/runs/{run_id}/cancel"),
        client.post(f"/api/agent/runs/{run_id}/retry"),
    ]

    assert [response.status_code for response in responses] == [403, 403]
    assert all(
        "execute agent" in response.json()["detail"]
        for response in responses
    )
    assert owner_lookups == []


def test_agent_run_create_returns_queued_and_status_completes(monkeypatch, tmp_path):
    calls = []

    def fake_execute(request, governance_dir, settings):
        calls.append((request, governance_dir, settings.agent_hermes_model))
        return _sample_envelope()

    client, settings = _client(monkeypatch, tmp_path, fake_execute)

    response = client.post("/api/agent/runs", json={"question": "ping"})

    assert response.status_code == 200
    created = response.json()
    assert created["status"] == "queued"
    assert created["run_id"].startswith("agent_run:")

    completed = _wait_for_terminal(client, created["run_id"])
    assert completed["status"] == "completed"
    assert completed["result"]["answer"] == "Hermes managed answer."
    assert completed["provider"] == "hermes"
    assert completed["model"] == "gpt-test"
    assert completed["transport"] == "bridge"
    assert calls and calls[0][2] == "gpt-test"

    records = [
        json.loads(line)
        for line in (tmp_path / "governance" / "agent_run.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [record["status"] for record in records if record["run_id"] == created["run_id"]] == [
        "queued",
        "starting",
        "running",
        "completed",
    ]


def test_agent_run_injects_run_id_into_executor_context(monkeypatch, tmp_path):
    requests = []

    def fake_execute(request, governance_dir, settings):
        requests.append(request)
        return _sample_envelope()

    client, _ = _client(monkeypatch, tmp_path, fake_execute)

    created = client.post("/api/agent/runs", json={"question": "ping"}).json()
    completed = _wait_for_terminal(client, created["run_id"])

    assert completed["status"] == "completed"
    assert len(requests) == 1
    assert requests[0].context["run_id"] == created["run_id"]


def test_agent_run_create_is_idempotent_for_duplicate_client_request_id(monkeypatch, tmp_path):
    calls: list[str] = []

    def fake_execute(request, governance_dir, settings):
        calls.append(str(request.context.get("run_id") or ""))
        return _sample_envelope()

    client, _ = _client(monkeypatch, tmp_path, fake_execute, grant_write=True)
    conversation = _create_conversation(client)
    payload = {
        "question": "ping",
        "context": {
            "conversation_id": conversation["conversation_id"],
            "client_request_id": "req-1",
        },
    }

    first = client.post("/api/agent/runs", json=payload)
    second = client.post("/api/agent/runs", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    first_body = first.json()
    second_body = second.json()
    assert first_body["run_id"] == second_body["run_id"]
    assert calls == [first_body["run_id"]]
    completed = _wait_for_terminal(client, first_body["run_id"])
    assert completed["status"] == "completed"
    records = [
        json.loads(line)
        for line in (tmp_path / "governance" / "agent_run.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [record["status"] for record in records if record["run_id"] == first_body["run_id"]] == [
        "queued",
        "starting",
        "running",
        "completed",
    ]


def test_archive_project_serializes_against_conversation_run_creation(monkeypatch, tmp_path):
    """归档 vs 带会话 run 创建必须互斥：归档进行中 run 创建阻塞，归档后拒绝。"""
    from backend.app.agent.schemas.agent_workspace import AgentProjectUpdateRequest
    from backend.app.repositories.agent_workspace_repo import AgentWorkspaceRepository
    from backend.app.services.agent_workspace_service import update_project

    client, settings = _client(
        monkeypatch,
        tmp_path,
        lambda *_args, **_kwargs: _sample_envelope(),
        grant_write=True,
    )
    conversation = _create_conversation(client)
    archive_append_started = threading.Event()
    allow_archive_append = threading.Event()
    archive_done = threading.Event()
    run_done = threading.Event()
    archive_errors: list[BaseException] = []
    run_result: dict[str, object] = {}
    original_append_project = AgentWorkspaceRepository.append_project

    def blocking_append_project(repository, payload):
        if payload.get("archived_at"):
            archive_append_started.set()
            if not allow_archive_append.wait(timeout=5.0):
                raise AssertionError("Timed out waiting to release archive append.")
        return original_append_project(repository, payload)

    monkeypatch.setattr(
        AgentWorkspaceRepository,
        "append_project",
        blocking_append_project,
    )

    def archive_project() -> None:
        try:
            update_project(
                settings=settings,
                owner_user_id=str(conversation["owner_user_id"]),
                project_id=str(conversation["project_id"]),
                request=AgentProjectUpdateRequest(archived=True),
            )
        except BaseException as exc:  # pragma: no cover - assertion reports below
            archive_errors.append(exc)
        finally:
            archive_done.set()

    def create_run_after_archive_starts() -> None:
        try:
            response = client.post(
                "/api/agent/runs",
                json={
                    "question": "race the archive",
                    "context": {
                        "conversation_id": conversation["conversation_id"],
                    },
                },
            )
            run_result["status_code"] = response.status_code
            run_result["body"] = response.json()
        finally:
            run_done.set()

    archive_thread = threading.Thread(target=archive_project)
    run_thread = threading.Thread(target=create_run_after_archive_starts)
    archive_thread.start()
    assert archive_append_started.wait(timeout=5.0)
    run_thread.start()
    # run 创建必须被 lifecycle 锁挡住，直到归档写盘完成。
    assert not run_done.wait(timeout=0.2)

    allow_archive_append.set()
    archive_thread.join(timeout=5.0)
    run_thread.join(timeout=10.0)

    assert archive_done.is_set()
    assert run_done.is_set()
    assert archive_errors == []
    assert run_result["status_code"] == 409
    assert "archived" in str(run_result["body"])
    run_stream = tmp_path / "governance" / "agent_run.jsonl"
    assert not run_stream.exists() or all(
        json.loads(line).get("conversation_id") != conversation["conversation_id"]
        for line in run_stream.read_text(encoding="utf-8").splitlines()
    )


def test_conversation_run_dispatch_happens_outside_workspace_lifecycle_lock(monkeypatch, tmp_path):
    """broker 派发必须在 lifecycle 锁外：锁内派发会把 5s 等待放大为全局 409/503。"""
    from backend.app.services.agent_workspace_service import (
        agent_workspace_lifecycle_lock,
    )

    client, settings = _client(
        monkeypatch,
        tmp_path,
        lambda *_args, **_kwargs: _sample_envelope(),
        grant_write=True,
    )
    conversation = _create_conversation(client)
    service_module = __import__(
        "backend.app.services.agent_run_service",
        fromlist=["execute_agent_run_task"],
    )
    probed: list[str] = []

    def dispatch_probe(*, run_id):
        # 若路由仍持有 lifecycle 锁，这里会在 5s 超时后抛
        # AgentWorkspaceStateConflict，进而以 dispatch 失败（503）暴露。
        with agent_workspace_lifecycle_lock(settings=settings):
            pass
        probed.append(run_id)

    monkeypatch.setattr(service_module.execute_agent_run_task, "send", dispatch_probe)

    response = client.post(
        "/api/agent/runs",
        json={
            "question": "dispatch outside the lock",
            "context": {"conversation_id": conversation["conversation_id"]},
        },
    )

    assert response.status_code == 200
    created = response.json()
    assert created["status"] == "queued"
    assert probed == [created["run_id"]]


def test_conversation_retry_dispatch_happens_outside_workspace_lifecycle_lock(
    monkeypatch, tmp_path
):
    """retry 路径与 create 同构：锁内只 stage，broker 派发（complete）在锁外。"""
    from backend.app.services.agent_workspace_service import (
        agent_workspace_lifecycle_lock,
    )

    def fail_provider(*_args, **_kwargs):
        raise RuntimeError("provider failed")

    client, settings = _client(monkeypatch, tmp_path, fail_provider, grant_write=True)
    conversation = _create_conversation(client)
    failed_run = client.post(
        "/api/agent/runs",
        json={
            "question": "retry dispatch outside the lock",
            "context": {"conversation_id": conversation["conversation_id"]},
        },
    ).json()
    assert _wait_for_terminal(client, failed_run["run_id"])["status"] == "failed"

    service_module = __import__(
        "backend.app.services.agent_run_service",
        fromlist=["execute_agent_run_task"],
    )
    probed: list[str] = []

    def dispatch_probe(*, run_id):
        # 若 retry 路由仍在 lifecycle 锁内派发，这里会在 5s 超时后抛
        # AgentWorkspaceStateConflict，进而以 dispatch 失败（503）暴露。
        with agent_workspace_lifecycle_lock(settings=settings):
            pass
        probed.append(run_id)

    monkeypatch.setattr(service_module.execute_agent_run_task, "send", dispatch_probe)

    response = client.post(f"/api/agent/runs/{failed_run['run_id']}/retry")

    assert response.status_code == 200
    retried = response.json()
    assert retried["status"] == "queued"
    assert retried["run_id"] != failed_run["run_id"]
    assert probed == [retried["run_id"]]


def test_auth_context_strips_client_supplied_run_id():
    route_module = load_module(
        "backend.app.api.routes.agent",
        "backend/app/api/routes/agent.py",
    )

    request = route_module._apply_auth_context(
        AgentQueryRequest(
            question="ping",
            context={"run_id": "agent_run:spoofed", "page": "agent-workbench"},
        ),
        SimpleNamespace(
            user_id="u_trusted",
            role="reader",
            identity_source="trusted_headers",
        ),
    )

    assert "run_id" not in request.context
    assert request.context["page"] == "agent-workbench"
    assert request.context["user_id"] == "u_trusted"


def test_agent_run_create_queues_cli_transport_without_blocking(monkeypatch, tmp_path):
    route_module = load_module(
        "backend.app.api.routes.agent",
        "backend/app/api/routes/agent.py",
    )
    _seed_agent_read_scope(tmp_path, monkeypatch)
    settings = _settings(tmp_path)
    settings.agent_hermes_transport = "cli"
    monkeypatch.setattr(route_module, "get_settings", lambda: settings)

    def fake_execute(*_args, **_kwargs):
        raise AssertionError("HTTP create must dispatch instead of executing the provider inline")

    monkeypatch.setattr(route_module, "execute_hermes_agent_query", fake_execute)
    service_module = __import__(
        "backend.app.services.agent_run_service",
        fromlist=["execute_agent_run_task"],
    )
    dispatched = []
    monkeypatch.setattr(
        service_module.execute_agent_run_task,
        "send",
        lambda **kwargs: dispatched.append(kwargs),
    )
    app = FastAPI()
    app.include_router(route_module.router)
    client = TestClient(app)

    response = client.post("/api/agent/runs", json={"question": "ping"})

    assert response.status_code == 200
    created = response.json()
    assert created["status"] == "queued"
    assert created["run_id"].startswith("agent_run:")
    assert dispatched == [{"run_id": created["run_id"]}]
    assert (tmp_path / "governance" / "agent_run.jsonl").exists()


def test_agent_run_cli_transport_records_failed_status_on_provider_failure(monkeypatch, tmp_path):
    route_module = load_module(
        "backend.app.api.routes.agent",
        "backend/app/api/routes/agent.py",
    )
    _seed_agent_read_scope(tmp_path, monkeypatch)
    settings = _settings(tmp_path)
    settings.agent_hermes_transport = "cli"
    monkeypatch.setattr(route_module, "get_settings", lambda: settings)

    service_module = __import__(
        "backend.app.services.agent_run_service",
        fromlist=["execute_agent_run_task"],
    )

    def fail_dispatch(**_kwargs):
        raise RuntimeError("broker unavailable")

    monkeypatch.setattr(service_module.execute_agent_run_task, "send", fail_dispatch)
    app = FastAPI()
    app.include_router(route_module.router)
    client = TestClient(app)

    response = client.post("/api/agent/runs", json={"question": "ping"})

    assert response.status_code == 503
    assert "Agent run dispatch failed" in response.json()["detail"]
    records = [
        json.loads(line)
        for line in (tmp_path / "governance" / "agent_run.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [record["status"] for record in records] == ["queued", "failed"]
    assert records[-1]["error_message"] == "Agent run dispatch failed."
    audit_rows = [
        json.loads(line)
        for line in (tmp_path / "governance" / "agent_audit.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert audit_rows[-1]["result_meta"]["error_code"] == "AGENT_RUN_DISPATCH_FAILED"


def test_agent_run_status_returns_404_for_unknown_run(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path, lambda *args, **kwargs: _sample_envelope())

    response = client.get("/api/agent/runs/agent_run:nope")

    assert response.status_code == 404
    assert "Unknown agent run_id=agent_run:nope" in response.json()["detail"]


def test_agent_run_status_rejects_different_header_user(monkeypatch, tmp_path):
    def fake_execute(request, governance_dir, settings):
        return _sample_envelope()

    monkeypatch.setenv("MOSS_AUTH_TRUST_X_USER_ROLE_FOR_DEV_TEST", "1")
    client, settings = _client(monkeypatch, tmp_path, fake_execute)

    created = client.post(
        "/api/agent/runs",
        json={"question": "ping"},
        headers={"X-User-Id": "run-owner", "X-User-Role": "reviewer"},
    ).json()
    owner_headers = {"X-User-Id": "run-owner", "X-User-Role": "reviewer"}
    _wait_for_terminal_record(settings, created["run_id"])

    denied = client.get(
        f"/api/agent/runs/{created['run_id']}",
        headers={"X-User-Id": "other-user", "X-User-Role": "reviewer"},
    )
    allowed = client.get(
        f"/api/agent/runs/{created['run_id']}",
        headers=owner_headers,
    )

    assert denied.status_code == 403
    assert allowed.status_code == 200


def test_agent_run_creation_uses_auth_context_instead_of_request_user_context(monkeypatch, tmp_path):
    def fake_execute(request, governance_dir, settings):
        return _sample_envelope()

    monkeypatch.setenv("MOSS_AUTH_TRUST_X_USER_ROLE_FOR_DEV_TEST", "1")
    client, settings = _client(monkeypatch, tmp_path, fake_execute)

    created = client.post(
        "/api/agent/runs",
        json={"question": "ping", "context": {"user_id": "spoofed-user", "user_role": "admin"}},
        headers={"X-User-Id": "run-owner", "X-User-Role": "reviewer"},
    ).json()
    owner_headers = {"X-User-Id": "run-owner", "X-User-Role": "reviewer"}
    _wait_for_terminal_record(settings, created["run_id"])

    denied = client.get(
        f"/api/agent/runs/{created['run_id']}",
        headers={"X-User-Id": "spoofed-user", "X-User-Role": "admin"},
    )
    allowed = client.get(
        f"/api/agent/runs/{created['run_id']}",
        headers=owner_headers,
    )

    assert denied.status_code == 403
    assert allowed.status_code == 200


def test_agent_run_list_returns_only_owner_latest_snapshots(monkeypatch, tmp_path):
    monkeypatch.setenv("MOSS_AUTH_TRUST_X_USER_ROLE_FOR_DEV_TEST", "1")
    client, _ = _client(
        monkeypatch,
        tmp_path,
        lambda *_args, **_kwargs: _sample_envelope(),
    )
    owner_headers = {"X-User-Id": "run-owner", "X-User-Role": "reviewer"}
    other_headers = {"X-User-Id": "other-user", "X-User-Role": "reviewer"}

    owner_runs = [
        client.post(
            "/api/agent/runs",
            json={"question": question},
            headers=owner_headers,
        ).json()
        for question in ("first", "second")
    ]
    other_run = client.post(
        "/api/agent/runs",
        json={"question": "private"},
        headers=other_headers,
    ).json()

    response = client.get("/api/agent/runs?limit=20", headers=owner_headers)

    assert response.status_code == 200
    items = response.json()["items"]
    assert {item["run_id"] for item in items} == {
        created["run_id"] for created in owner_runs
    }
    assert other_run["run_id"] not in {item["run_id"] for item in items}
    assert len(items) == 2
    assert all(item["status"] == "completed" for item in items)


def test_agent_run_cancel_enforces_owner_and_returns_cancelled(monkeypatch, tmp_path):
    monkeypatch.setenv("MOSS_AUTH_TRUST_X_USER_ROLE_FOR_DEV_TEST", "1")
    client, _ = _client(
        monkeypatch,
        tmp_path,
        lambda *_args, **_kwargs: _sample_envelope(),
    )
    service_module = __import__(
        "backend.app.services.agent_run_service",
        fromlist=["execute_agent_run_task"],
    )
    monkeypatch.setattr(
        service_module.execute_agent_run_task,
        "send",
        lambda **_kwargs: None,
    )
    owner_headers = {"X-User-Id": "run-owner", "X-User-Role": "reviewer"}
    other_headers = {"X-User-Id": "other-user", "X-User-Role": "reviewer"}
    created = client.post(
        "/api/agent/runs",
        json={"question": "wait"},
        headers=owner_headers,
    ).json()

    denied_cancel = client.post(
        f"/api/agent/runs/{created['run_id']}/cancel",
        headers=other_headers,
    )
    denied_retry = client.post(
        f"/api/agent/runs/{created['run_id']}/retry",
        headers=other_headers,
    )
    cancelled = client.post(
        f"/api/agent/runs/{created['run_id']}/cancel",
        headers=owner_headers,
    )

    assert denied_cancel.status_code == 403
    assert denied_retry.status_code == 403
    assert cancelled.status_code == 200
    assert cancelled.json()["run_id"] == created["run_id"]
    assert cancelled.json()["status"] == "cancelled"


def test_agent_run_ownerless_record_is_rejected_by_every_single_run_endpoint(
    monkeypatch,
    tmp_path,
):
    client, _ = _client(
        monkeypatch,
        tmp_path,
        lambda *_args, **_kwargs: _sample_envelope(),
    )
    run_id = "agent_run:ownerless"
    governance_dir = tmp_path / "governance"
    governance_dir.mkdir(parents=True)
    (governance_dir / "agent_run.jsonl").write_text(
        json.dumps(
            {
                "job_name": "agent_run",
                "run_id": run_id,
                "status": "cancelled",
                "question": "ownerless",
                "request": {"question": "ownerless", "context": {}},
                "provider": "hermes",
                "model": "gpt-test",
                "transport": "bridge",
                "toolsets": "evidence,query,research",
                "queued_at": "2026-07-25T08:00:00+00:00",
                "finished_at": "2026-07-25T08:00:01+00:00",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    responses = [
        client.get(f"/api/agent/runs/{run_id}"),
        client.get(f"/api/agent/runs/{run_id}/events"),
        client.post(f"/api/agent/runs/{run_id}/cancel"),
        client.post(f"/api/agent/runs/{run_id}/retry"),
    ]

    assert [response.status_code for response in responses] == [403, 403, 403, 403]
    assert all(
        response.json()["detail"] == "Agent run belongs to a different user."
        for response in responses
    )


def test_agent_run_list_rejects_limit_above_100(monkeypatch, tmp_path):
    client, _ = _client(
        monkeypatch,
        tmp_path,
        lambda *_args, **_kwargs: _sample_envelope(),
    )

    response = client.get("/api/agent/runs?limit=101")

    assert response.status_code == 422


def test_agent_run_retry_creates_new_run_for_failed_and_cancelled(monkeypatch, tmp_path):
    def fail_provider(*_args, **_kwargs):
        raise RuntimeError("provider failed")

    client, _ = _client(monkeypatch, tmp_path, fail_provider, grant_write=True)
    conversation = _create_conversation(client)
    failed_run = client.post(
        "/api/agent/runs",
        json={
            "question": "retry failed",
            "context": {
                "conversation_id": conversation["conversation_id"],
                "client_request_id": "create-key",
            },
        },
    ).json()
    assert _wait_for_terminal(client, failed_run["run_id"])["status"] == "failed"

    service_module = __import__(
        "backend.app.services.agent_run_service",
        fromlist=["execute_agent_run_task"],
    )
    monkeypatch.setattr(
        service_module.execute_agent_run_task,
        "send",
        lambda **_kwargs: None,
    )
    failed_retry = client.post(
        f"/api/agent/runs/{failed_run['run_id']}/retry",
    )
    duplicate_failed_retry = client.post(
        f"/api/agent/runs/{failed_run['run_id']}/retry",
    )

    cancellable_run = client.post(
        "/api/agent/runs",
        json={
            "question": "retry cancelled",
            "context": {
                "conversation_id": conversation["conversation_id"],
                "client_request_id": "create-cancelled",
            },
        },
    ).json()
    cancelled = client.post(
        f"/api/agent/runs/{cancellable_run['run_id']}/cancel",
    ).json()
    cancelled_retry = client.post(
        f"/api/agent/runs/{cancellable_run['run_id']}/retry",
    )

    assert failed_retry.status_code == 200
    assert failed_retry.json()["status"] == "queued"
    assert failed_retry.json()["run_id"] != failed_run["run_id"]
    assert duplicate_failed_retry.status_code == 200
    assert duplicate_failed_retry.json()["run_id"] == failed_retry.json()["run_id"]
    assert cancelled["status"] == "cancelled"
    assert cancelled_retry.status_code == 200
    assert cancelled_retry.json()["status"] == "queued"
    assert cancelled_retry.json()["run_id"] != cancellable_run["run_id"]


def test_agent_run_cancel_retry_map_conflict_and_unknown_statuses(monkeypatch, tmp_path):
    client, _ = _client(
        monkeypatch,
        tmp_path,
        lambda *_args, **_kwargs: _sample_envelope(),
    )
    completed = client.post(
        "/api/agent/runs",
        json={"question": "already complete"},
    ).json()
    _wait_for_terminal(client, completed["run_id"])

    conflict_cancel = client.post(
        f"/api/agent/runs/{completed['run_id']}/cancel",
    )
    conflict_retry = client.post(
        f"/api/agent/runs/{completed['run_id']}/retry",
    )
    unknown_cancel = client.post("/api/agent/runs/agent_run:nope/cancel")
    unknown_retry = client.post("/api/agent/runs/agent_run:nope/retry")

    assert conflict_cancel.status_code == 409
    assert conflict_retry.status_code == 409
    assert unknown_cancel.status_code == 404
    assert unknown_retry.status_code == 404


def test_agent_run_retry_maps_dispatch_failure_to_503(monkeypatch, tmp_path):
    def fail_provider(*_args, **_kwargs):
        raise RuntimeError("provider failed")

    client, _ = _client(monkeypatch, tmp_path, fail_provider)
    failed_run = client.post(
        "/api/agent/runs",
        json={"question": "retry after failure"},
    ).json()
    assert _wait_for_terminal(client, failed_run["run_id"])["status"] == "failed"

    service_module = __import__(
        "backend.app.services.agent_run_service",
        fromlist=["execute_agent_run_task"],
    )

    def fail_dispatch(**_kwargs):
        raise RuntimeError("broker unavailable")

    monkeypatch.setattr(service_module.execute_agent_run_task, "send", fail_dispatch)
    response = client.post(f"/api/agent/runs/{failed_run['run_id']}/retry")

    assert response.status_code == 503
    assert "Agent run dispatch failed" in response.json()["detail"]


def test_agent_run_status_prefers_jsonl_terminal_state_over_in_memory_running_cache(monkeypatch, tmp_path):
    service_module = load_module(
        "backend.app.services.agent_run_service",
        "backend/app/services/agent_run_service.py",
    )
    service_module._AGENT_RUN_LATEST_RECORDS.clear()
    settings = _settings(tmp_path)
    governance_dir = tmp_path / "governance"
    governance_dir.mkdir(parents=True)

    service_module._remember_run_record(
        {
            "run_id": "agent_run:finished",
            "status": "running",
            "question": "ping",
            "provider": "hermes",
            "model": "gpt-test",
            "transport": "bridge",
            "toolsets": "file",
            "queued_at": "2026-05-09T01:00:00+00:00",
            "started_at": "2026-05-09T01:00:01+00:00",
        }
    )
    (governance_dir / "agent_run.jsonl").write_text(
        json.dumps(
            {
                "job_name": "agent_run",
                "run_id": "agent_run:finished",
                "status": "completed",
                "question": "ping",
                "provider": "hermes",
                "model": "gpt-test",
                "transport": "bridge",
                "toolsets": "file",
                "queued_at": "2026-05-09T01:00:00+00:00",
                "started_at": "2026-05-09T01:00:01+00:00",
                "finished_at": "2026-05-09T01:00:02+00:00",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    status = service_module.get_agent_run_status(run_id="agent_run:finished", settings=settings)

    assert status.status == "completed"
    assert status.run_id == "agent_run:finished"
    assert status.model == "gpt-test"


def test_agent_run_status_reconciles_stale_running_record_to_failed(monkeypatch, tmp_path):
    service_module = load_module(
        "backend.app.services.agent_run_service",
        "backend/app/services/agent_run_service.py",
    )
    service_module._AGENT_RUN_LATEST_RECORDS.clear()
    settings = _settings(tmp_path)
    governance_dir = tmp_path / "governance"
    governance_dir.mkdir(parents=True)
    run_id = "agent_run:stale"
    (governance_dir / "agent_run.jsonl").write_text(
        json.dumps(
            {
                "job_name": "agent_run",
                "run_id": run_id,
                "status": "running",
                "question": "ping",
                "request": {"question": "ping"},
                "provider": "hermes",
                "model": "gpt-test",
                "transport": "bridge",
                "toolsets": "evidence,query,research",
                "queued_at": "2026-07-20T08:00:00+00:00",
                "started_at": "2026-07-20T08:00:01+00:00",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(service_module, "_utc_now", lambda: "2026-07-20T08:00:41+00:00")

    status = service_module.get_agent_run_status(run_id=run_id, settings=settings)

    assert status.status == "failed"
    assert status.finished_at == "2026-07-20T08:00:41+00:00"
    assert status.elapsed_seconds == 40.0
    assert status.error_message is not None
    assert "未在运行超时后进入终态" in status.error_message
    repeated = service_module.get_agent_run_status(run_id=run_id, settings=settings)
    assert repeated.status == "failed"
    records = [
        json.loads(line)
        for line in (governance_dir / "agent_run.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [record["status"] for record in records] == ["running", "failed"]
    audit = json.loads(
        (governance_dir / "agent_audit.jsonl").read_text(encoding="utf-8").splitlines()[-1]
    )
    assert audit["run_id"] == run_id
    assert audit["result_meta"]["error_type"] == "StaleAgentRun"


def test_stale_run_reconciliation_is_atomic_for_concurrent_readers(monkeypatch, tmp_path):
    service_module = load_module(
        "backend.app.services.agent_run_service",
        "backend/app/services/agent_run_service.py",
    )
    service_module._AGENT_RUN_LATEST_RECORDS.clear()
    settings = _settings(tmp_path)
    governance_dir = tmp_path / "governance"
    governance_dir.mkdir(parents=True)
    run_id = "agent_run:stale-concurrent"
    (governance_dir / "agent_run.jsonl").write_text(
        json.dumps(
            {
                "job_name": "agent_run",
                "run_id": run_id,
                "status": "running",
                "question": "ping",
                "request": {"question": "ping"},
                "provider": "hermes",
                "model": "gpt-test",
                "transport": "bridge",
                "toolsets": "evidence,query,research",
                "queued_at": "2026-07-20T08:00:00+00:00",
                "started_at": "2026-07-20T08:00:01+00:00",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(service_module, "_utc_now", lambda: "2026-07-20T08:00:41+00:00")
    original_append = service_module._append_record
    barrier = threading.Barrier(4)

    def delayed_append(settings_arg, record):
        if record.status == "failed":
            barrier.wait(timeout=5)
        original_append(settings_arg, record)

    monkeypatch.setattr(service_module, "_append_record", delayed_append)

    with ThreadPoolExecutor(max_workers=4) as pool:
        statuses = list(
            pool.map(
                lambda _: service_module.get_agent_run_status(
                    run_id=run_id,
                    settings=settings,
                ).status,
                range(4),
            )
        )

    assert statuses == ["failed"] * 4
    records = [
        json.loads(line)
        for line in (governance_dir / "agent_run.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [record["status"] for record in records] == ["running", "failed"]
    audits = [
        json.loads(line)
        for line in (governance_dir / "agent_audit.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(audits) == 1
    assert audits[0]["run_id"] == run_id


def test_reconciled_failure_is_not_overwritten_by_late_completion(monkeypatch, tmp_path):
    service_module = load_module(
        "backend.app.services.agent_run_service",
        "backend/app/services/agent_run_service.py",
    )
    service_module._AGENT_RUN_LATEST_RECORDS.clear()
    settings = _settings(tmp_path)
    run_id = "agent_run:late-completion"
    request = AgentQueryRequest(
        question="ping",
        context={"run_id": run_id, "user_id": "u_test"},
    )
    service_module._append_record(
        settings,
        AgentRunRecord(
            run_id=run_id,
            status="queued",
            question=request.question,
            request=request.model_dump(mode="json"),
            provider="hermes",
            model="gpt-test",
            transport="bridge",
            toolsets="evidence,query,research",
            queued_at=datetime.now(UTC).isoformat(),
        ),
    )
    executor_started = threading.Event()
    release_executor = threading.Event()

    def delayed_executor(_request, _governance_dir, _settings):
        executor_started.set()
        assert release_executor.wait(5)
        return _sample_envelope()

    worker = threading.Thread(
        target=service_module._execute_agent_run,
        kwargs={
            "run_id": run_id,
            "request": request,
            "settings": settings,
            "executor": delayed_executor,
        },
    )
    worker.start()
    assert executor_started.wait(2)
    running_records = [
        json.loads(line)
        for line in (tmp_path / "governance" / "agent_run.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    started_at = datetime.fromisoformat(str(running_records[-1]["started_at"]))
    stale_now = (started_at + timedelta(seconds=40)).isoformat()
    monkeypatch.setattr(service_module, "_utc_now", lambda: stale_now)

    stale_status = service_module.get_agent_run_status(run_id=run_id, settings=settings)
    assert stale_status.status == "failed"

    release_executor.set()
    worker.join(timeout=5)
    assert not worker.is_alive()
    final_status = service_module.get_agent_run_status(run_id=run_id, settings=settings)
    assert final_status.status == "failed"
    records = [
        json.loads(line)
        for line in (tmp_path / "governance" / "agent_run.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert "completed" not in [record["status"] for record in records]


def _seed_local_running_record(service_module, governance_dir, run_id: str) -> None:
    service_module._AGENT_RUN_LATEST_RECORDS.clear()
    governance_dir.mkdir(parents=True)
    (governance_dir / "agent_run.jsonl").write_text(
        json.dumps(
            {
                "job_name": "agent_run",
                "run_id": run_id,
                "status": "running",
                "question": "ping",
                "request": {"question": "ping"},
                "provider": "local",
                "model": "default",
                "transport": "inline",
                "toolsets": "evidence,query,research",
                "queued_at": "2026-07-19T08:00:00+00:00",
                "started_at": "2026-07-19T08:00:01+00:00",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def test_local_running_record_is_not_reconciled_by_external_provider_timeout(monkeypatch, tmp_path):
    service_module = load_module(
        "backend.app.services.agent_run_service",
        "backend/app/services/agent_run_service.py",
    )
    settings = _local_settings(tmp_path)
    governance_dir = tmp_path / "governance"
    run_id = "agent_run:local-running"
    _seed_local_running_record(service_module, governance_dir, run_id)
    # 640s elapsed: well beyond the hermes/dexter timeout + grace window, but
    # inside the local running stale limit (default 1800s + 30s grace).
    monkeypatch.setattr(service_module, "_utc_now", lambda: "2026-07-19T08:10:41+00:00")

    status = service_module.get_agent_run_status(run_id=run_id, settings=settings)

    assert status.status == "running"
    records = [
        json.loads(line)
        for line in (governance_dir / "agent_run.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [record["status"] for record in records] == ["running"]


def test_local_running_record_reconciles_to_failed_after_local_stale_limit(monkeypatch, tmp_path):
    """local run 也经 Dramatiq worker 执行：worker 崩溃后必须能收敛为 failed。"""
    service_module = load_module(
        "backend.app.services.agent_run_service",
        "backend/app/services/agent_run_service.py",
    )
    settings = _local_settings(tmp_path)
    governance_dir = tmp_path / "governance"
    run_id = "agent_run:local-stale"
    _seed_local_running_record(service_module, governance_dir, run_id)
    # 1832s elapsed > default 1800s local limit + 30s grace.
    monkeypatch.setattr(service_module, "_utc_now", lambda: "2026-07-19T08:30:33+00:00")

    status = service_module.get_agent_run_status(run_id=run_id, settings=settings)

    assert status.status == "failed"
    assert status.finished_at == "2026-07-19T08:30:33+00:00"
    assert status.error_message is not None
    assert "未在运行超时后进入终态" in status.error_message
    repeated = service_module.get_agent_run_status(run_id=run_id, settings=settings)
    assert repeated.status == "failed"
    records = [
        json.loads(line)
        for line in (governance_dir / "agent_run.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [record["status"] for record in records] == ["running", "failed"]
    audit = json.loads(
        (governance_dir / "agent_audit.jsonl").read_text(encoding="utf-8").splitlines()[-1]
    )
    assert audit["run_id"] == run_id
    assert audit["result_meta"]["error_type"] == "StaleAgentRun"


def test_local_running_stale_limit_honors_governance_setting_override(monkeypatch, tmp_path):
    service_module = load_module(
        "backend.app.services.agent_run_service",
        "backend/app/services/agent_run_service.py",
    )
    settings = _local_settings(tmp_path)
    settings.agent_run_local_timeout_seconds = 60.0
    governance_dir = tmp_path / "governance"
    run_id = "agent_run:local-stale-override"
    _seed_local_running_record(service_module, governance_dir, run_id)
    # 119s elapsed > overridden 60s limit + 30s grace.
    monkeypatch.setattr(service_module, "_utc_now", lambda: "2026-07-19T08:02:00+00:00")

    status = service_module.get_agent_run_status(run_id=run_id, settings=settings)

    assert status.status == "failed"
    records = [
        json.loads(line)
        for line in (governance_dir / "agent_run.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [record["status"] for record in records] == ["running", "failed"]


def test_agent_run_status_keeps_recent_running_record_active(monkeypatch, tmp_path):
    service_module = load_module(
        "backend.app.services.agent_run_service",
        "backend/app/services/agent_run_service.py",
    )
    service_module._AGENT_RUN_LATEST_RECORDS.clear()
    settings = _settings(tmp_path)
    governance_dir = tmp_path / "governance"
    governance_dir.mkdir(parents=True)
    run_id = "agent_run:recent"
    (governance_dir / "agent_run.jsonl").write_text(
        json.dumps(
            {
                "job_name": "agent_run",
                "run_id": run_id,
                "status": "running",
                "question": "ping",
                "request": {"question": "ping"},
                "provider": "hermes",
                "model": "gpt-test",
                "transport": "bridge",
                "toolsets": "evidence,query,research",
                "queued_at": "2026-07-20T08:00:00+00:00",
                "started_at": "2026-07-20T08:00:01+00:00",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(service_module, "_utc_now", lambda: "2026-07-20T08:00:39+00:00")

    status = service_module.get_agent_run_status(run_id=run_id, settings=settings)

    assert status.status == "running"
    records = [
        json.loads(line)
        for line in (governance_dir / "agent_run.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [record["status"] for record in records] == ["running"]


def test_agent_run_failure_records_error_message(monkeypatch, tmp_path, caplog):
    sensitive_markers = (
        "json-access-secret",
        "dict-password-secret",
        "opaque-provider-secret",
        "multi-at-password",
    )
    provider_error = (
        '{"access_token":"json-access-secret"} '
        "{'password': 'dict-password-secret'} "
        "opaque-provider-secret at "
        "https://user:multi-at-password@segment@provider.example/query"
    )

    def fake_execute(request, governance_dir, settings):
        raise RuntimeError(f"Hermes bridge unavailable: {provider_error}")

    client, _ = _client(monkeypatch, tmp_path, fake_execute)

    created = client.post("/api/agent/runs", json={"question": "ping"}).json()
    failed = _wait_for_terminal(client, created["run_id"])

    assert failed["status"] == "failed"
    assert failed["error_message"] == "Agent provider execution failed."
    assert "result" not in failed

    records = [
        json.loads(line)
        for line in (tmp_path / "governance" / "agent_run.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    latest = [record for record in records if record["run_id"] == created["run_id"]][-1]
    assert latest["status"] == "failed"
    assert latest["error_message"] == "Agent provider execution failed."
    audit_rows = [
        json.loads(line)
        for line in (tmp_path / "governance" / "agent_audit.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    audit = audit_rows[-1]
    assert audit["run_id"] == created["run_id"]
    assert audit["tools_used"] == ["agent_run", "provider:hermes", "status:failed"]
    assert audit["result_meta"]["result_kind"] == "agent.run_failed"
    assert audit["result_meta"]["error_type"] == "RuntimeError"
    assert audit["result_meta"]["error_code"] == "AGENT_RUN_EXECUTION_FAILED"
    public_material = json.dumps([failed, latest, audit], ensure_ascii=False)
    for marker in sensitive_markers:
        assert marker not in public_material
        assert marker not in caplog.text
    assert "error_code=AGENT_RUN_EXECUTION_FAILED" in caplog.text
    assert "error_type=RuntimeError" in caplog.text
    assert "detail=" not in caplog.text


def test_agent_run_accepts_local_provider_and_completes_lifecycle(monkeypatch, tmp_path):
    calls = []

    def fake_execute(request, duckdb_path, governance_dir):
        calls.append((request.question, duckdb_path, governance_dir))
        return _local_envelope()

    client, settings = _local_client(monkeypatch, tmp_path, fake_execute)

    response = client.post("/api/agent/runs", json={"question": "ping"})

    assert response.status_code == 200
    created = response.json()
    assert created["status"] == "queued"
    assert created["run_id"].startswith("agent_run:")
    assert created["provider"] == "local"

    completed = _wait_for_terminal(client, created["run_id"])
    assert completed["status"] == "completed"
    assert completed["provider"] == "local"
    assert completed["result"]["answer"] == "Local managed answer."
    assert completed["result"]["evidence"]["sql_executed"] == [
        "select * from fact_formal_bond_analytics_daily where report_date = ?"
    ]
    assert completed["result"]["evidence"]["tables_used"] == ["fact_formal_bond_analytics_daily"]
    assert AgentEnvelope.model_validate(completed["result"]).answer == "Local managed answer."
    assert calls == [("ping", str(tmp_path / "moss.duckdb"), str(tmp_path / "governance"))]

    records = [
        json.loads(line)
        for line in (tmp_path / "governance" / "agent_run.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    matching = [record for record in records if record["run_id"] == created["run_id"]]
    assert [record["status"] for record in matching] == [
        "queued",
        "starting",
        "running",
        "completed",
    ]
    assert all(record["provider"] == "local" for record in matching)


def test_agent_run_local_failure_records_failed_status(monkeypatch, tmp_path):
    def fake_execute(request, duckdb_path, governance_dir):
        raise RuntimeError("local toolchain failed")

    client, _ = _local_client(monkeypatch, tmp_path, fake_execute)

    created = client.post("/api/agent/runs", json={"question": "ping"}).json()
    failed = _wait_for_terminal(client, created["run_id"])

    assert failed["status"] == "failed"
    assert failed["provider"] == "local"
    assert failed["error_message"] == "local toolchain failed"
    assert "result" not in failed


def test_agent_run_follow_up_context_stays_local_even_with_dexter_provider(monkeypatch, tmp_path):
    route_module = load_module(
        "backend.app.api.routes.agent",
        "backend/app/api/routes/agent.py",
    )
    # load_module executes tasks/agent_run.py as a fresh module instance, and
    # register_actor_once permanently swaps the shared actor's fn to that fresh
    # function (whose globals bypass later monkeypatches, e.g. in
    # test_agent_run_worker.py). Snapshot the canonical sys.modules entry and
    # actor fn as no-op monkeypatches so teardown restores both.
    canonical_task_module = importlib.import_module("backend.app.tasks.agent_run")
    monkeypatch.setitem(sys.modules, "backend.app.tasks.agent_run", canonical_task_module)
    monkeypatch.setattr(
        canonical_task_module.execute_agent_run_task,
        "fn",
        canonical_task_module.execute_agent_run_task.fn,
    )
    task_module = load_module(
        "backend.app.tasks.agent_run",
        "backend/app/tasks/agent_run.py",
    )
    _seed_agent_read_scope(tmp_path, monkeypatch)
    settings = SimpleNamespace(
        agent_enabled=True,
        agent_provider="dexter",
        agent_dexter_model="dexter-test",
        agent_dexter_transport="cli",
        agent_dexter_toolsets="sql,files",
        duckdb_path=str(tmp_path / "moss.duckdb"),
        governance_path=str(tmp_path / "governance"),
        **_agent_auth_fields(tmp_path),
    )
    monkeypatch.setattr(route_module, "get_settings", lambda: settings)
    monkeypatch.setattr(task_module, "get_settings", lambda: settings)

    local_calls = []
    dexter_calls = []

    def fake_local_execute(*, request, duckdb_path, governance_dir):
        local_calls.append((request.question, duckdb_path, governance_dir))
        return _local_envelope()

    def fake_dexter_execute(request, governance_dir, runtime_settings):
        dexter_calls.append((request.question, governance_dir, runtime_settings.agent_dexter_model))
        return _sample_envelope()

    monkeypatch.setattr(task_module, "execute_agent_query", fake_local_execute)
    monkeypatch.setattr(task_module, "execute_dexter_agent_query", fake_dexter_execute)
    service_module = __import__(
        "backend.app.services.agent_run_service",
        fromlist=["execute_agent_run_task"],
    )
    monkeypatch.setattr(
        service_module.execute_agent_run_task,
        "send",
        lambda **kwargs: task_module._execute_agent_run_task(**kwargs),
    )

    app = FastAPI()
    app.include_router(route_module.router)
    client = TestClient(app)

    created = client.post(
        "/api/agent/runs",
        json={
            "question": "continue this",
            "context": {
                "conversation": {
                    "recent_turns": [
                        {
                            "result_kind": "agent.duration_risk",
                            "answer": "Previous local governed answer.",
                        }
                    ]
                }
            },
        },
    ).json()
    completed = _wait_for_terminal(client, created["run_id"])

    assert created["provider"] == "local"
    assert completed["status"] == "completed"
    assert completed["provider"] == "local"
    assert local_calls == [("continue this", str(tmp_path / "moss.duckdb"), str(tmp_path / "governance"))]
    assert not dexter_calls


@pytest.mark.parametrize("provider", ["hermes", "dexter"])
def test_explicit_provider_diagnostic_overrides_local_routing_for_query_and_runs(
    provider,
    monkeypatch,
    tmp_path,
):
    service_module = load_module(
        "backend.app.services.agent_run_service",
        "backend/app/services/agent_run_service.py",
    )
    service_module._AGENT_RUN_LATEST_RECORDS.clear()
    route_module = load_module(
        "backend.app.api.routes.agent",
        "backend/app/api/routes/agent.py",
    )
    _seed_agent_read_scope(tmp_path, monkeypatch)
    settings = SimpleNamespace(
        agent_enabled=True,
        agent_provider=provider,
        agent_hermes_model="hermes-test",
        agent_hermes_transport="cli",
        agent_hermes_toolsets="evidence",
        agent_dexter_model="dexter-test",
        agent_dexter_transport="cli",
        agent_dexter_toolsets="research",
        duckdb_path=str(tmp_path / "moss.duckdb"),
        governance_path=str(tmp_path / "governance"),
        **_agent_auth_fields(tmp_path),
    )
    monkeypatch.setattr(route_module, "get_settings", lambda: settings)
    provider_calls = []

    def unexpected_local_execute(*_args, **_kwargs):
        raise AssertionError("explicit provider diagnostic must not reach local executor")

    def fake_provider_execute(request, governance_dir, runtime_settings):
        provider_calls.append((request.question, governance_dir, runtime_settings.agent_provider))
        return _sample_envelope().model_copy(
            update={"answer": f"{provider} diagnostic answer"}
        )

    monkeypatch.setattr(route_module, "execute_agent_query", unexpected_local_execute)
    monkeypatch.setattr(
        route_module,
        "execute_hermes_agent_query" if provider == "hermes" else "execute_dexter_agent_query",
        fake_provider_execute,
    )

    def dispatch_inline(*, run_id):
        return service_module.execute_agent_run_by_id(
            run_id=run_id,
            settings=settings,
            executor=fake_provider_execute,
        )

    monkeypatch.setattr(service_module.execute_agent_run_task, "send", dispatch_inline)
    app = FastAPI()
    app.include_router(route_module.router)
    client = TestClient(app)
    body = {
        "question": (
            "explain external provider diagnostics for current page context "
            "processes duration market value"
        ),
        "context": {
            "conversation": {
                "recent_turns": [
                    {"result_kind": "agent.duration_risk", "answer": "prior governed result"}
                ]
            }
        },
        "page_context": {"page_id": "dashboard"},
    }

    query_response = client.post("/api/agent/query", json=body)
    create_response = client.post("/api/agent/runs", json=body)

    assert query_response.status_code == 200
    assert query_response.json()["answer"] == f"{provider} diagnostic answer"
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["provider"] == provider
    completed = _wait_for_terminal(client, created["run_id"])
    assert completed["status"] == "completed"
    assert completed["provider"] == provider
    assert completed["result"]["answer"] == f"{provider} diagnostic answer"
    assert [call[2] for call in provider_calls] == [provider, provider]


def test_actual_hermes_fallback_is_safe_for_query_run_record_and_audit(
    monkeypatch,
    tmp_path,
    caplog,
):
    from backend.app.services import hermes_agent_service

    sensitive_markers = (
        "json-access-secret",
        "dict-password-secret",
        "opaque-provider-secret",
        "multi-at-password",
    )
    provider_error = (
        '{"access_token":"json-access-secret"} '
        "{'password': 'dict-password-secret'} "
        "opaque-provider-secret at "
        "https://user:multi-at-password@segment@provider.example/query"
    )

    def fail_hermes_runtime(**_kwargs):
        raise RuntimeError(f"Hermes failed with stderr: {provider_error}")

    monkeypatch.setattr(hermes_agent_service, "run_hermes_agent", fail_hermes_runtime)
    client, settings = _client(
        monkeypatch,
        tmp_path,
        hermes_agent_service.execute_hermes_agent_query,
    )
    body = {"question": "external provider diagnostics"}

    query_response = client.post("/api/agent/query", json=body)
    create_response = client.post("/api/agent/runs", json=body)

    assert query_response.status_code == 200
    assert query_response.json()["result_meta"]["result_kind"] == "agent.hermes_fallback"
    assert create_response.status_code == 200
    completed = _wait_for_terminal(client, create_response.json()["run_id"])
    assert completed["status"] == "completed"
    assert completed["result"]["result_meta"]["result_kind"] == "agent.hermes_fallback"
    assert completed["result"]["evidence"]["filters_applied"]["fallback_reason"] == (
        "hermes_runtime_unavailable"
    )

    public_material = "\n".join(
        [
            query_response.text,
            create_response.text,
            json.dumps(completed, ensure_ascii=False),
            (Path(settings.governance_path) / "agent_run.jsonl").read_text(encoding="utf-8"),
            (Path(settings.governance_path) / "agent_audit.jsonl").read_text(encoding="utf-8"),
        ]
    )
    assert "Hermes failed with stderr" not in public_material
    for marker in sensitive_markers:
        assert marker not in public_material
        assert marker not in caplog.text
    assert "error_code=hermes_runtime_unavailable" in caplog.text
    assert "error_type=RuntimeError" in caplog.text
    assert "detail=" not in caplog.text


def test_actual_dexter_success_omits_provider_output_from_query_run_and_audit(
    monkeypatch,
    tmp_path,
):
    from backend.app.services import dexter_agent_service

    service_module = load_module(
        "backend.app.services.agent_run_service",
        "backend/app/services/agent_run_service.py",
    )
    service_module._AGENT_RUN_LATEST_RECORDS.clear()
    route_module = load_module(
        "backend.app.api.routes.agent",
        "backend/app/api/routes/agent.py",
    )
    _seed_agent_read_scope(tmp_path, monkeypatch)
    settings = SimpleNamespace(
        agent_enabled=True,
        agent_provider="dexter",
        agent_dexter_command="dexter",
        agent_dexter_transport="sidecar",
        agent_dexter_bridge_url="http://127.0.0.1:7892",
        agent_dexter_model="dexter-test",
        agent_dexter_toolsets="sql,files",
        agent_dexter_timeout_seconds=9.0,
        duckdb_path=str(tmp_path / "moss.duckdb"),
        governance_path=str(tmp_path / "governance"),
        **_agent_auth_fields(tmp_path),
    )
    sensitive_markers = (
        "json-access-secret",
        "dict-password-secret",
        "opaque-provider-secret",
        "multi-at-password",
    )
    provider_output = (
        '{"access_token":"json-access-secret"} '
        "{'password': 'dict-password-secret'} "
        "opaque-provider-secret at "
        "https://user:multi-at-password@segment@provider.example/query"
    )

    monkeypatch.setattr(route_module, "get_settings", lambda: settings)
    monkeypatch.setattr(
        dexter_agent_service,
        "build_dexter_research_context",
        lambda **_kwargs: {},
    )
    monkeypatch.setattr(
        dexter_agent_service,
        "run_dexter_agent",
        lambda **_kwargs: {
            "answer": "Dexter safe answer.",
            "stdout": provider_output,
            "stderr": provider_output,
            "command": "dexter",
            "tool_name": "portfolio.scan",
            "model": "dexter-test",
            "toolsets": "sql,files",
            "transport": "sidecar",
            "tables_used": ["dexter_sidecar"],
        },
    )
    monkeypatch.setattr(
        route_module,
        "execute_dexter_agent_query",
        dexter_agent_service.execute_dexter_agent_query,
    )

    def dispatch_inline(*, run_id):
        return service_module.execute_agent_run_by_id(
            run_id=run_id,
            settings=settings,
            executor=dexter_agent_service.execute_dexter_agent_query,
        )

    monkeypatch.setattr(service_module.execute_agent_run_task, "send", dispatch_inline)
    app = FastAPI()
    app.include_router(route_module.router)
    client = TestClient(app)
    body = {"question": "external provider diagnostics"}

    query_response = client.post("/api/agent/query", json=body)
    create_response = client.post("/api/agent/runs", json=body)
    completed = _wait_for_terminal(client, create_response.json()["run_id"])

    assert query_response.status_code == 200
    assert query_response.json()["answer"] == "Dexter safe answer."
    assert create_response.status_code == 200
    assert completed["status"] == "completed"
    assert completed["result"]["answer"] == "Dexter safe answer."

    governance_path = Path(settings.governance_path)
    audit_rows = [
        json.loads(line)
        for line in (governance_path / "agent_audit.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(audit_rows) == 2
    for audit in audit_rows:
        assert audit["result_meta"]["dexter_tool_name"] == "portfolio.scan"
        assert "stdout_excerpt" not in audit["result_meta"]
        assert "stderr_excerpt" not in audit["result_meta"]

    public_material = "\n".join(
        [
            query_response.text,
            create_response.text,
            json.dumps(completed, ensure_ascii=False),
            (governance_path / "agent_run.jsonl").read_text(encoding="utf-8"),
            (governance_path / "agent_audit.jsonl").read_text(encoding="utf-8"),
        ]
    )
    for marker in sensitive_markers:
        assert marker not in public_material


def test_agent_run_local_owner_isolation(monkeypatch, tmp_path):
    def fake_execute(request, duckdb_path, governance_dir):
        return _local_envelope()

    monkeypatch.setenv("MOSS_AUTH_TRUST_X_USER_ROLE_FOR_DEV_TEST", "1")
    client, settings = _local_client(monkeypatch, tmp_path, fake_execute)

    created = client.post(
        "/api/agent/runs",
        json={"question": "ping"},
        headers={"X-User-Id": "run-owner", "X-User-Role": "reviewer"},
    ).json()
    _wait_for_terminal_record(settings, created["run_id"])

    denied = client.get(
        f"/api/agent/runs/{created['run_id']}",
        headers={"X-User-Id": "other-user", "X-User-Role": "reviewer"},
    )
    allowed = client.get(
        f"/api/agent/runs/{created['run_id']}",
        headers={"X-User-Id": "run-owner", "X-User-Role": "reviewer"},
    )

    assert denied.status_code == 403
    assert allowed.status_code == 200


def test_agent_run_forced_local_context_uses_local_executor_even_with_hermes_provider(monkeypatch, tmp_path):
    """/runs 的 executor 分流应与 /query 一致：governed intent 强制走 local 工具链。"""
    route_module = load_module(
        "backend.app.api.routes.agent",
        "backend/app/api/routes/agent.py",
    )
    _seed_agent_read_scope(tmp_path, monkeypatch)
    settings = _settings(tmp_path)
    monkeypatch.setattr(route_module, "get_settings", lambda: settings)

    local_calls = []

    def fake_local_execute(request, duckdb_path, governance_dir):
        local_calls.append(request.question)
        return _local_envelope()

    def unexpected_hermes_execute(*_args, **_kwargs):
        raise AssertionError("governed intent must not reach hermes executor")

    monkeypatch.setattr(route_module, "execute_agent_query", fake_local_execute)
    monkeypatch.setattr(route_module, "execute_hermes_agent_query", unexpected_hermes_execute)
    service_module = __import__(
        "backend.app.services.agent_run_service",
        fromlist=["execute_agent_run_task"],
    )

    def dispatch_inline(*, run_id):
        def local_executor(request, governance_dir, _settings):
            return fake_local_execute(
                request,
                str(tmp_path / "moss.duckdb"),
                governance_dir,
            )

        return service_module.execute_agent_run_by_id(
            run_id=run_id,
            settings=settings,
            executor=local_executor,
        )

    monkeypatch.setattr(service_module.execute_agent_run_task, "send", dispatch_inline)
    app = FastAPI()
    app.include_router(route_module.router)
    client = TestClient(app)

    response = client.post(
        "/api/agent/runs",
        json={"question": "ping", "context": {"intent": "duration_risk"}},
    )

    assert response.status_code == 200
    created = response.json()
    assert created["provider"] == "local"

    completed = _wait_for_terminal(client, created["run_id"])
    assert completed["status"] == "completed"
    assert completed["provider"] == "local"
    assert completed["result"]["answer"] == "Local managed answer."
    assert local_calls == ["ping"]


def test_agent_runs_accept_dexter_provider_and_persist_provider_metadata(monkeypatch, tmp_path):
    service_module = load_module(
        "backend.app.services.agent_run_service",
        "backend/app/services/agent_run_service.py",
    )
    service_module._AGENT_RUN_LATEST_RECORDS.clear()

    route_module = load_module(
        "backend.app.api.routes.agent",
        "backend/app/api/routes/agent.py",
    )
    _seed_agent_read_scope(tmp_path, monkeypatch)
    settings = SimpleNamespace(
        agent_enabled=True,
        agent_provider="dexter",
        agent_dexter_command="dexter",
        agent_dexter_transport="sidecar",
        agent_dexter_bridge_url="http://127.0.0.1:7892",
        agent_dexter_model="dexter-test",
        agent_dexter_toolsets="sql,files",
        agent_dexter_timeout_seconds=9.0,
        duckdb_path=str(tmp_path / "moss.duckdb"),
        governance_path=str(tmp_path / "governance"),
        **_agent_auth_fields(tmp_path),
    )
    monkeypatch.setattr(route_module, "get_settings", lambda: settings)

    calls = []

    def fake_execute(request, governance_dir, settings):
        calls.append((request, governance_dir, settings.agent_dexter_model))
        sample = _sample_envelope()
        return sample.model_copy(
            update={
                "answer": "Dexter managed answer.",
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
                        "source_version": "sv_dexter_sidecar",
                        "vendor_version": "vv_dexter",
                        "rule_version": "rv_agent_dexter_v1",
                        "cache_version": "cv_agent_dexter_v1",
                        "tables_used": ["dexter_sidecar"],
                        "filters_applied": {"provider": "dexter"},
                    }
                ),
            }
        )

    monkeypatch.setattr(route_module, "execute_dexter_agent_query", fake_execute)

    def dispatch_inline(*, run_id):
        return service_module.execute_agent_run_by_id(
            run_id=run_id,
            settings=settings,
            executor=fake_execute,
        )

    monkeypatch.setattr(service_module.execute_agent_run_task, "send", dispatch_inline)
    app = FastAPI()
    app.include_router(route_module.router)
    client = TestClient(app)

    response = client.post("/api/agent/runs", json={"question": "ping"})

    assert response.status_code == 200
    created = response.json()
    assert created["provider"] == "dexter"
    assert created["model"] == "dexter-test"
    assert created["transport"] == "sidecar"
    assert created["toolsets"] == "evidence,query,research"

    records = [
        json.loads(line)
        for line in (tmp_path / "governance" / "agent_run.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    matching = [record for record in records if record["run_id"] == created["run_id"]]
    assert [record["status"] for record in matching] == [
        "queued",
        "starting",
        "running",
        "completed",
    ]
    completed = matching[-1]
    assert completed["provider"] == "dexter"
    assert completed["model"] == "dexter-test"
    assert completed["transport"] == "sidecar"
    assert completed["toolsets"] == "evidence,query,research"
    assert completed["result"]["answer"] == "Dexter managed answer."
    assert completed["result"]["result_meta"]["result_kind"] == "agent.dexter"
    assert calls and calls[0][2] == "dexter-test"
