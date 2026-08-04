from __future__ import annotations

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.app.agent.schemas.agent_request import AgentQueryRequest
from backend.app.agent.schemas.agent_response import (
    AgentEnvelope,
    AgentEvidence,
    AgentResultMeta,
)
from backend.app.agent.schemas.agent_run import AgentRunRecord, AgentRunStatusResponse
from backend.app.repositories.governance_repo import GovernanceRepository
from backend.app.services import agent_run_service


def _settings(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        agent_provider="hermes",
        agent_hermes_model="gpt-test",
        agent_hermes_transport="bridge",
        agent_hermes_toolsets="file",
        agent_hermes_timeout_seconds=9.0,
        governance_path=str(tmp_path / "governance"),
    )


def _request(
    question: str,
    owner: str = "owner-1",
    conversation_id: str | None = None,
    client_request_id: str | None = None,
) -> AgentQueryRequest:
    context: dict[str, str] = {"user_id": owner, "page": "agent-workbench"}
    if conversation_id is not None:
        context["conversation_id"] = conversation_id
    if client_request_id is not None:
        context["client_request_id"] = client_request_id
    return AgentQueryRequest(
        question=question,
        context=context,
    )


def _envelope(answer: str = "done") -> AgentEnvelope:
    return AgentEnvelope(
        answer=answer,
        cards=[],
        evidence=AgentEvidence(
            tables_used=["governed_agent_test"],
            filters_applied={},
            evidence_rows=1,
            quality_flag="ok",
        ),
        result_meta=AgentResultMeta(
            trace_id="tr_agent_run_lifecycle",
            basis="formal",
            result_kind="agent.lifecycle_test",
            formal_use_allowed=False,
            quality_flag="ok",
            scenario_flag=False,
            tables_used=["governed_agent_test"],
            filters_applied={},
            evidence_rows=1,
        ),
    )


def _append_status(
    *,
    settings: SimpleNamespace,
    run_id: str,
    status: str,
    request: AgentQueryRequest,
    queued_at: str,
    started_at: str | None = None,
    finished_at: str | None = None,
    provider: str = "hermes",
) -> None:
    agent_run_service._append_record(
        settings,
        AgentRunRecord(
            run_id=run_id,
            status=status,  # type: ignore[arg-type]
            question=request.question,
            request=request.model_dump(mode="json"),
            provider=provider,
            model="gpt-test",
            transport="bridge",
            toolsets="evidence,query,research",
            queued_at=queued_at,
            started_at=started_at,
            finished_at=finished_at,
        ),
    )


@pytest.fixture(autouse=True)
def _clear_agent_run_cache() -> None:
    agent_run_service._AGENT_RUN_LATEST_RECORDS.clear()


def test_create_dispatches_lazy_task_with_only_run_id(monkeypatch, tmp_path):
    settings = _settings(tmp_path)
    dispatched: list[str] = []
    monkeypatch.setattr(
        agent_run_service.execute_agent_run_task,
        "send",
        lambda *, run_id: dispatched.append(run_id),
    )

    created = agent_run_service.create_agent_run(
        request=_request("analyze"),
        settings=settings,
        provider="hermes",
    )

    assert dispatched == [created.run_id]
    record = GovernanceRepository(settings.governance_path).read_all(
        agent_run_service.AGENT_RUN_STREAM
    )[-1]
    assert record["status"] == "queued"
    assert record["request"]["context"]["run_id"] == created.run_id


def test_create_dispatch_failure_is_persisted_as_failed(monkeypatch, tmp_path):
    settings = _settings(tmp_path)

    def fail_dispatch(*, run_id):
        raise ConnectionError(f"broker offline for {run_id}")

    monkeypatch.setattr(agent_run_service.execute_agent_run_task, "send", fail_dispatch)

    with pytest.raises(
        agent_run_service.AgentRunDispatchError,
        match=r"^Agent run dispatch failed for agent_run:",
    ):
        agent_run_service.create_agent_run(
            request=_request("analyze"),
            settings=settings,
            provider="hermes",
        )

    records = GovernanceRepository(settings.governance_path).read_all(
        agent_run_service.AGENT_RUN_STREAM
    )
    assert [record["status"] for record in records] == ["queued", "failed"]
    assert records[-1]["finished_at"]
    assert "broker offline" in records[-1]["error_message"]


def test_create_returns_existing_run_for_duplicate_owner_conversation_and_client_request_id(
    monkeypatch,
    tmp_path,
):
    settings = _settings(tmp_path)
    dispatched: list[str] = []
    monkeypatch.setattr(
        agent_run_service.execute_agent_run_task,
        "send",
        lambda *, run_id: dispatched.append(run_id),
    )
    request = _request(
        "analyze",
        conversation_id="conv-1",
        client_request_id="req-1",
    )

    first = agent_run_service.create_agent_run(
        request=request,
        settings=settings,
        provider="hermes",
    )
    second = agent_run_service.create_agent_run(
        request=request,
        settings=settings,
        provider="hermes",
    )

    assert second.run_id == first.run_id
    assert dispatched == [first.run_id]
    records = GovernanceRepository(settings.governance_path).read_all(
        agent_run_service.AGENT_RUN_STREAM
    )
    assert len(records) == 1
    assert records[0]["run_id"] == first.run_id
    assert records[0]["request"]["context"]["client_request_id"] == "req-1"


def test_create_is_concurrent_idempotent_for_same_owner_conversation_and_client_request_id(
    monkeypatch,
    tmp_path,
):
    settings = _settings(tmp_path)
    dispatched: list[str] = []
    monkeypatch.setattr(
        agent_run_service.execute_agent_run_task,
        "send",
        lambda *, run_id: dispatched.append(run_id),
    )
    barrier = threading.Barrier(2)
    request = _request(
        "analyze concurrently",
        conversation_id="conv-1",
        client_request_id="req-concurrent",
    )

    def create_once(_: int):
        barrier.wait(timeout=5)
        return agent_run_service.create_agent_run(
            request=request,
            settings=settings,
            provider="hermes",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        created = list(pool.map(create_once, range(2)))

    run_ids = {item.run_id for item in created}
    assert len(run_ids) == 1
    run_id = created[0].run_id
    assert dispatched == [run_id]
    records = GovernanceRepository(settings.governance_path).read_all(
        agent_run_service.AGENT_RUN_STREAM
    )
    assert len(records) == 1
    assert records[0]["run_id"] == run_id


def test_concurrent_duplicate_does_not_report_success_when_dispatch_fails(
    monkeypatch,
    tmp_path,
):
    settings = _settings(tmp_path)
    dispatch_started = threading.Event()
    release_dispatch = threading.Event()
    duplicate_waiting = threading.Event()

    def fail_dispatch(*, run_id):
        dispatch_started.set()
        assert release_dispatch.wait(timeout=5)
        raise RuntimeError(f"broker offline for {run_id}")

    original_wait = agent_run_service._wait_for_idempotent_dispatch_resolution

    def observe_duplicate_wait(**kwargs):
        duplicate_waiting.set()
        return original_wait(**kwargs)

    monkeypatch.setattr(
        agent_run_service.execute_agent_run_task,
        "send",
        fail_dispatch,
    )
    monkeypatch.setattr(
        agent_run_service,
        "_wait_for_idempotent_dispatch_resolution",
        observe_duplicate_wait,
    )
    request = _request(
        "analyze once",
        conversation_id="conv-1",
        client_request_id="req-dispatch-failure",
    )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(
            agent_run_service.create_agent_run,
            request=request,
            settings=settings,
            provider="hermes",
        )
        assert dispatch_started.wait(timeout=5)
        duplicate = pool.submit(
            agent_run_service.create_agent_run,
            request=request,
            settings=settings,
            provider="hermes",
        )
        assert duplicate_waiting.wait(timeout=5)
        release_dispatch.set()

        with pytest.raises(agent_run_service.AgentRunDispatchError):
            first.result(timeout=5)
        with pytest.raises(agent_run_service.AgentRunDispatchError):
            duplicate.result(timeout=5)

    repo = GovernanceRepository(settings.governance_path)
    records = repo.read_all(agent_run_service.AGENT_RUN_STREAM)
    assert [record["status"] for record in records] == ["queued", "failed"]
    assert repo.read_all(agent_run_service.AGENT_RUN_DISPATCH_STREAM) == []


def test_create_does_not_dedupe_different_owner_conversation_or_client_request_id(
    monkeypatch,
    tmp_path,
):
    settings = _settings(tmp_path)
    dispatched: list[str] = []
    monkeypatch.setattr(
        agent_run_service.execute_agent_run_task,
        "send",
        lambda *, run_id: dispatched.append(run_id),
    )

    created = [
        agent_run_service.create_agent_run(
            request=_request(
                "owner-1/conv-1/key-1",
                owner="owner-1",
                conversation_id="conv-1",
                client_request_id="key-1",
            ),
            settings=settings,
            provider="hermes",
        ),
        agent_run_service.create_agent_run(
            request=_request(
                "owner-2/conv-1/key-1",
                owner="owner-2",
                conversation_id="conv-1",
                client_request_id="key-1",
            ),
            settings=settings,
            provider="hermes",
        ),
        agent_run_service.create_agent_run(
            request=_request(
                "owner-1/conv-2/key-1",
                owner="owner-1",
                conversation_id="conv-2",
                client_request_id="key-1",
            ),
            settings=settings,
            provider="hermes",
        ),
        agent_run_service.create_agent_run(
            request=_request(
                "owner-1/conv-1/key-2",
                owner="owner-1",
                conversation_id="conv-1",
                client_request_id="key-2",
            ),
            settings=settings,
            provider="hermes",
        ),
    ]

    assert len({item.run_id for item in created}) == 4
    assert len(dispatched) == 4


def test_execute_by_id_restores_governed_request_and_preserves_cancelled(monkeypatch, tmp_path):
    settings = _settings(tmp_path)
    dispatched: list[str] = []
    monkeypatch.setattr(
        agent_run_service.execute_agent_run_task,
        "send",
        lambda *, run_id: dispatched.append(run_id),
    )
    created = agent_run_service.create_agent_run(
        request=_request("restore me"),
        settings=settings,
        provider="hermes",
    )
    calls: list[AgentQueryRequest] = []

    def cancel_during_execution(request, _governance_path, _settings):
        calls.append(request)
        agent_run_service.cancel_agent_run(run_id=created.run_id, settings=settings)
        return _envelope("too late")

    status = agent_run_service.execute_agent_run_by_id(
        run_id=created.run_id,
        settings=settings,
        executor=cancel_during_execution,
    )

    assert dispatched == [created.run_id]
    assert calls[0].question == "restore me"
    assert calls[0].context["run_id"] == created.run_id
    assert status.status == "cancelled"
    statuses = [
        record["status"]
        for record in GovernanceRepository(settings.governance_path).read_all(
            agent_run_service.AGENT_RUN_STREAM
        )
    ]
    assert statuses == ["queued", "starting", "running", "cancelled"]

    agent_run_service.execute_agent_run_by_id(
        run_id=created.run_id,
        settings=settings,
        executor=lambda *_args: pytest.fail("cancelled run must not execute"),
    )


def test_cancel_is_cooperative_idempotent_and_rejects_illegal_terminal_state(
    tmp_path,
):
    settings = _settings(tmp_path)
    request = _request("cancel me")
    _append_status(
        settings=settings,
        run_id="agent_run:cancel",
        status="queued",
        request=request,
        queued_at="2026-07-25T10:00:00+00:00",
    )

    first = agent_run_service.cancel_agent_run(
        run_id="agent_run:cancel",
        settings=settings,
    )
    second = agent_run_service.cancel_agent_run(
        run_id="agent_run:cancel",
        settings=settings,
    )

    assert first.status == second.status == "cancelled"
    records = GovernanceRepository(settings.governance_path).read_all(
        agent_run_service.AGENT_RUN_STREAM
    )
    assert [record["status"] for record in records] == ["queued", "cancelled"]

    _append_status(
        settings=settings,
        run_id="agent_run:complete",
        status="completed",
        request=request,
        queued_at="2026-07-25T11:00:00+00:00",
        finished_at="2026-07-25T11:01:00+00:00",
    )
    with pytest.raises(agent_run_service.AgentRunStateConflict, match="completed"):
        agent_run_service.cancel_agent_run(
            run_id="agent_run:complete",
            settings=settings,
        )
    with pytest.raises(ValueError, match="Unknown agent run_id=agent_run:missing"):
        agent_run_service.cancel_agent_run(
            run_id="agent_run:missing",
            settings=settings,
        )


def test_list_returns_only_each_owners_latest_run_in_descending_time_order(tmp_path):
    settings = _settings(tmp_path)
    owner_request = _request("older", owner="owner-1")
    other_request = _request("private", owner="owner-2")
    _append_status(
        settings=settings,
        run_id="agent_run:older",
        status="queued",
        request=owner_request,
        queued_at="2026-07-25T09:00:00+00:00",
    )
    _append_status(
        settings=settings,
        run_id="agent_run:older",
        status="running",
        request=owner_request,
        queued_at="2026-07-25T09:00:00+00:00",
        started_at="2026-07-25T09:01:00+00:00",
    )
    _append_status(
        settings=settings,
        run_id="agent_run:newer",
        status="failed",
        request=_request("newer", owner="owner-1"),
        queued_at="2026-07-25T10:00:00+00:00",
        finished_at="2026-07-25T10:02:00+00:00",
    )
    _append_status(
        settings=settings,
        run_id="agent_run:other",
        status="failed",
        request=other_request,
        queued_at="2026-07-25T12:00:00+00:00",
        finished_at="2026-07-25T12:01:00+00:00",
    )

    response = agent_run_service.list_agent_runs(
        settings=settings,
        owner_user_id="owner-1",
        limit=20,
    )

    assert [item.run_id for item in response.items] == [
        "agent_run:newer",
        "agent_run:older",
    ]
    assert response.items[1].status == "running"
    assert all(item.question != "private" for item in response.items)


@pytest.mark.parametrize("source_status", ["failed", "cancelled"])
def test_retry_reuses_request_provider_and_records_source_run(
    monkeypatch,
    tmp_path,
    source_status,
):
    settings = _settings(tmp_path)
    source_request = _request(
        "retry this",
        conversation_id="conv-1",
        client_request_id="create-key",
    )
    _append_status(
        settings=settings,
        run_id=f"agent_run:{source_status}",
        status=source_status,
        request=source_request,
        queued_at="2026-07-25T10:00:00+00:00",
        finished_at="2026-07-25T10:01:00+00:00",
        provider="dexter",
    )
    dispatched: list[str] = []
    monkeypatch.setattr(
        agent_run_service.execute_agent_run_task,
        "send",
        lambda *, run_id: dispatched.append(run_id),
    )

    retried = agent_run_service.retry_agent_run(
        run_id=f"agent_run:{source_status}",
        settings=settings,
    )
    duplicate = agent_run_service.retry_agent_run(
        run_id=f"agent_run:{source_status}",
        settings=settings,
    )

    assert duplicate.run_id == retried.run_id
    assert retried.run_id != f"agent_run:{source_status}"
    assert dispatched == [retried.run_id]
    latest = GovernanceRepository(settings.governance_path).read_all(
        agent_run_service.AGENT_RUN_STREAM
    )[-1]
    assert latest["run_id"] == retried.run_id
    assert latest["provider"] == "dexter"
    assert latest["request"]["context"]["retry_of_run_id"] == f"agent_run:{source_status}"
    assert latest["request"]["context"]["client_request_id"] == f"retry:agent_run:{source_status}"


def test_retry_is_concurrent_idempotent_for_same_source_run(monkeypatch, tmp_path):
    settings = _settings(tmp_path)
    source_request = _request(
        "retry this concurrently",
        conversation_id="conv-1",
        client_request_id="create-key",
    )
    _append_status(
        settings=settings,
        run_id="agent_run:failed-source",
        status="failed",
        request=source_request,
        queued_at="2026-07-25T10:00:00+00:00",
        finished_at="2026-07-25T10:01:00+00:00",
        provider="dexter",
    )
    dispatched: list[str] = []
    monkeypatch.setattr(
        agent_run_service.execute_agent_run_task,
        "send",
        lambda *, run_id: dispatched.append(run_id),
    )
    barrier = threading.Barrier(2)

    def retry_once(_: int):
        barrier.wait(timeout=5)
        return agent_run_service.retry_agent_run(
            run_id="agent_run:failed-source",
            settings=settings,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        retried = list(pool.map(retry_once, range(2)))

    assert len({item.run_id for item in retried}) == 1
    retry_run_id = retried[0].run_id
    assert retry_run_id != "agent_run:failed-source"
    assert dispatched == [retry_run_id]
    records = GovernanceRepository(settings.governance_path).read_all(
        agent_run_service.AGENT_RUN_STREAM
    )
    assert [record["run_id"] for record in records] == [
        "agent_run:failed-source",
        retry_run_id,
    ]


def test_retry_rejects_non_retryable_status_and_cancelled_sse_is_terminal(tmp_path):
    settings = _settings(tmp_path)
    request = _request("still queued")
    _append_status(
        settings=settings,
        run_id="agent_run:queued",
        status="queued",
        request=request,
        queued_at="2026-07-25T10:00:00+00:00",
    )

    with pytest.raises(agent_run_service.AgentRunStateConflict, match="queued"):
        agent_run_service.retry_agent_run(
            run_id="agent_run:queued",
            settings=settings,
        )
    with pytest.raises(ValueError, match="Unknown agent run_id=agent_run:missing"):
        agent_run_service.retry_agent_run(
            run_id="agent_run:missing",
            settings=settings,
        )

    cancelled = AgentRunStatusResponse(
        run_id="agent_run:cancelled-sse",
        status="cancelled",
    )

    async def collect_events() -> list[str]:
        return [
            event
            async for event in agent_run_service.iter_agent_run_events(
                run_id=cancelled.run_id,
                settings=settings,
                initial_status=cancelled,
                poll_interval_seconds=0,
            )
        ]

    events = asyncio.run(collect_events())
    assert len(events) == 1
    assert '"status":"cancelled"' in events[0]
