"""Run read-path and dispatch-window guards.

Covers two regressions:

- the status/events/retry endpoints must authorize and answer from a single
  pass over the append-only ``agent_run`` stream;
- a crash between the broker ``send`` and the acceptance row must not make a
  repeated client request report a dispatch failure for a queued run.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from backend.app.agent.schemas.agent_request import AgentQueryRequest
from backend.app.repositories.governance_repo import GovernanceRepository
from backend.app.services import agent_run_service
from tests.test_agent_runs_api import (
    _client,
    _sample_envelope,
    _settings,
    _wait_for_terminal,
)

pytestmark = [
    pytest.mark.excluded_surface_acceptance,
    pytest.mark.surface_agent_mvp,
]


def _count_run_stream_reads(monkeypatch, client) -> list[str]:
    endpoint = next(
        route.endpoint
        for route in client.app.routes
        if route.path == "/api/agent/runs/{run_id}" and "GET" in route.methods
    )
    # Other suites reload agent_run_service. Resolve the repository from the
    # route's bound service, which can outlive the sys.modules replacement.
    bound_service_globals = endpoint.__globals__["get_agent_run_owner_and_status"].__globals__
    repository = bound_service_globals["GovernanceRepository"]
    run_stream = bound_service_globals["AGENT_RUN_STREAM"]
    original = repository.read_by_run_id
    reads: list[str] = []

    def counting_read(repo, stream, run_id, **kwargs):
        if stream == run_stream:
            reads.append(run_id)
            assert kwargs.get("latest_only") is True
        return original(repo, stream, run_id, **kwargs)

    monkeypatch.setattr(repository, "read_by_run_id", counting_read)
    return reads


def _owned_request(
    *,
    owner: str = "owner-1",
    client_request_id: str = "req-1",
) -> AgentQueryRequest:
    return AgentQueryRequest(
        question="dispatch crash window",
        context={"user_id": owner, "client_request_id": client_request_id},
    )


def _dispatch_rows(settings) -> list[dict[str, object]]:
    return GovernanceRepository(base_dir=settings.governance_path).read_all(
        agent_run_service.AGENT_RUN_DISPATCH_STREAM
    )


def test_run_status_endpoint_reads_the_run_stream_once(monkeypatch, tmp_path: Path):
    client, _settings_value = _client(
        monkeypatch,
        tmp_path,
        lambda *_args, **_kwargs: _sample_envelope(),
    )
    created = client.post("/api/agent/runs", json={"question": "ping"}).json()
    _wait_for_terminal(client, created["run_id"])

    reads = _count_run_stream_reads(monkeypatch, client)
    response = client.get(f"/api/agent/runs/{created['run_id']}")

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert reads == [created["run_id"]]


def test_run_status_endpoint_still_rejects_a_foreign_owner_with_one_read(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.setenv("MOSS_AUTH_TRUST_X_USER_ROLE_FOR_DEV_TEST", "1")
    client, settings = _client(
        monkeypatch,
        tmp_path,
        lambda *_args, **_kwargs: _sample_envelope(),
    )
    owner_headers = {"X-User-Id": "run-owner", "X-User-Role": "reviewer"}
    created = client.post(
        "/api/agent/runs",
        json={"question": "ping"},
        headers=owner_headers,
    ).json()
    _wait_for_terminal(client, created["run_id"], headers=owner_headers)
    del settings

    reads = _count_run_stream_reads(monkeypatch, client)
    denied = client.get(
        f"/api/agent/runs/{created['run_id']}",
        headers={"X-User-Id": "other-user", "X-User-Role": "reviewer"},
    )

    assert denied.status_code == 403
    assert denied.json()["detail"] == "Agent run belongs to a different user."
    assert reads == [created["run_id"]]


def test_run_events_endpoint_reads_the_run_stream_once_before_streaming(
    monkeypatch,
    tmp_path: Path,
):
    client, _settings_value = _client(
        monkeypatch,
        tmp_path,
        lambda *_args, **_kwargs: _sample_envelope(),
    )
    created = client.post("/api/agent/runs", json={"question": "ping"}).json()
    _wait_for_terminal(client, created["run_id"])

    reads = _count_run_stream_reads(monkeypatch, client)
    response = client.get(f"/api/agent/runs/{created['run_id']}/events")

    assert response.status_code == 200
    # 终态 run 的 SSE 只发一帧初始快照，因此授权+首帧共用一次流读取。
    assert reads == [created["run_id"]]


def test_dispatch_request_is_recorded_before_the_broker_send(
    monkeypatch,
    tmp_path: Path,
):
    settings = _settings(tmp_path)
    observed_phases: list[list[str]] = []

    def capture_send(*, run_id):
        del run_id
        observed_phases.append(
            [str(row.get("phase") or "") for row in _dispatch_rows(settings)]
        )

    monkeypatch.setattr(
        agent_run_service.execute_agent_run_task,
        "send",
        capture_send,
    )

    created = agent_run_service.create_agent_run(
        request=_owned_request(),
        settings=settings,
        provider="hermes",
    )

    assert created.status == "queued"
    assert observed_phases == [["requested"]]
    assert [str(row.get("phase") or "") for row in _dispatch_rows(settings)] == [
        "requested",
        "accepted",
    ]
    assert {str(row.get("run_id") or "") for row in _dispatch_rows(settings)} == {
        created.run_id
    }


def test_repeated_request_reuses_a_queued_run_when_acceptance_is_lost(
    monkeypatch,
    tmp_path: Path,
):
    """崩溃窗口：send 已发出但 acceptance 未落盘时，重复请求不得报派发失败。"""
    settings = _settings(tmp_path)
    monkeypatch.setattr(agent_run_service, "AGENT_RUN_DISPATCH_WAIT_SECONDS", 0.2)
    request = _owned_request(client_request_id="req-crash-window")

    staged = agent_run_service.stage_agent_run_creation(
        request=request,
        settings=settings,
        provider="hermes",
    )
    assert staged.queued_record is not None
    agent_run_service._append_dispatch_request(
        repo=GovernanceRepository(base_dir=settings.governance_path),
        run_id=staged.queued_record.run_id,
    )

    def unexpected_send(*, run_id):
        raise AssertionError(f"duplicate must not re-dispatch run_id={run_id}")

    monkeypatch.setattr(
        agent_run_service.execute_agent_run_task,
        "send",
        unexpected_send,
    )
    repeated = agent_run_service.create_agent_run(
        request=request,
        settings=settings,
        provider="hermes",
    )

    assert repeated.run_id == staged.queued_record.run_id
    assert repeated.status == "queued"
    records = GovernanceRepository(base_dir=settings.governance_path).read_all(
        agent_run_service.AGENT_RUN_STREAM
    )
    assert [str(record.get("status") or "") for record in records] == ["queued"]


def test_repeated_request_still_fails_when_no_dispatch_was_ever_requested(
    monkeypatch,
    tmp_path: Path,
):
    settings = _settings(tmp_path)
    monkeypatch.setattr(agent_run_service, "AGENT_RUN_DISPATCH_WAIT_SECONDS", 0.2)
    request = _owned_request(client_request_id="req-never-dispatched")

    staged = agent_run_service.stage_agent_run_creation(
        request=request,
        settings=settings,
        provider="hermes",
    )
    assert staged.queued_record is not None
    assert _dispatch_rows(settings) == []

    with pytest.raises(agent_run_service.AgentRunDispatchError):
        agent_run_service.create_agent_run(
            request=request,
            settings=settings,
            provider="hermes",
        )


def test_lifecycle_transition_counts_as_implicit_dispatch_acceptance(tmp_path: Path):
    settings = _settings(tmp_path)
    repo = GovernanceRepository(base_dir=settings.governance_path)
    queued = {"run_id": "agent_run:implicit", "status": "queued"}

    assert agent_run_service._is_dispatch_pending_record(repo=repo, record=queued) is True
    for status in ("starting", "running", "completed", "failed", "cancelled"):
        assert (
            agent_run_service._is_dispatch_pending_record(
                repo=repo,
                record={**queued, "status": status},
            )
            is False
        )

    repo.append(
        agent_run_service.AGENT_RUN_STREAM,
        {
            **queued,
            "status": "running",
            "question": "implicit acceptance",
            "request": {
                "question": "implicit acceptance",
                "context": {
                    "user_id": "owner-1",
                    "client_request_id": "req-implicit",
                },
            },
            "provider": "hermes",
            "queued_at": "2026-01-01T00:00:00+00:00",
        },
    )
    started = time.monotonic()
    resolved = agent_run_service._wait_for_idempotent_dispatch_resolution(
        repo=repo,
        owner_user_id="owner-1",
        conversation_id=None,
        client_request_id="req-implicit",
    )
    elapsed = time.monotonic() - started

    assert resolved is not None
    assert resolved["run_id"] == "agent_run:implicit"
    # 没有 acceptance 行也不等满 AGENT_RUN_DISPATCH_WAIT_SECONDS。
    assert elapsed < 1.0


def test_legacy_acceptance_rows_without_phase_stay_accepted(tmp_path: Path):
    settings = _settings(tmp_path)
    repo = GovernanceRepository(base_dir=settings.governance_path)
    repo.append(
        agent_run_service.AGENT_RUN_DISPATCH_STREAM,
        {"run_id": "agent_run:legacy", "accepted_at": "2026-01-01T00:00:00+00:00"},
    )

    assert (
        agent_run_service._is_dispatch_accepted(repo=repo, run_id="agent_run:legacy")
        is True
    )
    assert (
        agent_run_service._is_dispatch_pending_record(
            repo=repo,
            record={"run_id": "agent_run:legacy", "status": "queued"},
        )
        is False
    )
