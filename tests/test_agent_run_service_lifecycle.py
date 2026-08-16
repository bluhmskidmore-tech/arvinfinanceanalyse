from __future__ import annotations

import asyncio
import json
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

pytestmark = [
    pytest.mark.excluded_surface_acceptance,
    pytest.mark.surface_agent_mvp,
]


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
            source_version="sv_agent_run_lifecycle",
            rule_version="rv_agent_run_lifecycle",
            cache_version="cv_agent_run_lifecycle",
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


def _append_delta(
    *,
    settings: SimpleNamespace,
    run_id: str,
    owner_user_id: str,
    seq: int,
    text: str,
    created_at: str = "2026-07-25T10:00:00+00:00",
) -> None:
    GovernanceRepository(settings.governance_path).append(
        agent_run_service.AGENT_RUN_DELTA_STREAM,
        {
            "run_id": run_id,
            "owner_user_id": owner_user_id,
            "seq": seq,
            "channel": "answer",
            "text": text,
            "created_at": created_at,
        },
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


def test_create_dispatch_failure_is_persisted_as_failed(monkeypatch, tmp_path, caplog):
    settings = _settings(tmp_path)
    sensitive_markers = (
        "json-access-secret",
        "dict-password-secret",
        "opaque-provider-secret",
        "multi-at-password",
    )
    broker_error = (
        '{"access_token":"json-access-secret"} '
        "{'password': 'dict-password-secret'} "
        "opaque-provider-secret at "
        "redis://user:multi-at-password@segment@127.0.0.1:6379/0"
    )

    def fail_dispatch(*, run_id):
        raise ConnectionError(f"broker offline for {run_id}: {broker_error}")

    monkeypatch.setattr(agent_run_service.execute_agent_run_task, "send", fail_dispatch)

    with pytest.raises(agent_run_service.AgentRunDispatchError) as exc_info:
        agent_run_service.create_agent_run(
            request=_request("analyze"),
            settings=settings,
            provider="hermes",
        )

    assert str(exc_info.value) == "Agent run dispatch failed."

    repo = GovernanceRepository(settings.governance_path)
    records = repo.read_all(agent_run_service.AGENT_RUN_STREAM)
    assert [record["status"] for record in records] == ["queued", "failed"]
    assert records[-1]["finished_at"]
    assert records[-1]["error_message"] == "Agent run dispatch failed."

    audit_rows = repo.read_all(agent_run_service.AGENT_AUDIT_STREAM)
    assert audit_rows[-1]["result_meta"]["error_code"] == "AGENT_RUN_DISPATCH_FAILED"
    serialized_public_records = str([records, audit_rows, exc_info.value])
    for marker in sensitive_markers:
        assert marker not in serialized_public_records
        assert marker not in caplog.text
    assert "error_code=AGENT_RUN_DISPATCH_FAILED" in caplog.text
    assert "error_type=ConnectionError" in caplog.text
    assert "detail=" not in caplog.text


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


def test_create_dedupes_conversationless_duplicate_client_request_id(monkeypatch, tmp_path):
    """无会话 run 的幂等 scope 退化为 (user_id, client_request_id) 二元组。"""
    settings = _settings(tmp_path)
    dispatched: list[str] = []
    monkeypatch.setattr(
        agent_run_service.execute_agent_run_task,
        "send",
        lambda *, run_id: dispatched.append(run_id),
    )
    request = _request("analyze without conversation", client_request_id="req-no-conv")

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
    other_user = agent_run_service.create_agent_run(
        request=_request(
            "same key different user",
            owner="owner-2",
            client_request_id="req-no-conv",
        ),
        settings=settings,
        provider="hermes",
    )
    with_conversation = agent_run_service.create_agent_run(
        request=_request(
            "same key with conversation",
            conversation_id="conv-9",
            client_request_id="req-no-conv",
        ),
        settings=settings,
        provider="hermes",
    )

    assert second.run_id == first.run_id
    assert other_user.run_id != first.run_id
    assert with_conversation.run_id != first.run_id
    assert dispatched == [first.run_id, other_user.run_id, with_conversation.run_id]
    records = GovernanceRepository(settings.governance_path).read_all(
        agent_run_service.AGENT_RUN_STREAM
    )
    assert len(records) == 3


def test_retry_without_conversation_is_idempotent_for_double_click(monkeypatch, tmp_path):
    settings = _settings(tmp_path)
    source_request = _request("retry me without conversation")
    _append_status(
        settings=settings,
        run_id="agent_run:no-conv-failed",
        status="failed",
        request=source_request,
        queued_at="2026-07-25T10:00:00+00:00",
        finished_at="2026-07-25T10:01:00+00:00",
    )
    dispatched: list[str] = []
    monkeypatch.setattr(
        agent_run_service.execute_agent_run_task,
        "send",
        lambda *, run_id: dispatched.append(run_id),
    )

    retried = agent_run_service.retry_agent_run(
        run_id="agent_run:no-conv-failed",
        settings=settings,
    )
    duplicate = agent_run_service.retry_agent_run(
        run_id="agent_run:no-conv-failed",
        settings=settings,
    )

    assert retried.run_id != "agent_run:no-conv-failed"
    assert duplicate.run_id == retried.run_id
    assert dispatched == [retried.run_id]
    records = GovernanceRepository(settings.governance_path).read_all(
        agent_run_service.AGENT_RUN_STREAM
    )
    assert [record["run_id"] for record in records] == [
        "agent_run:no-conv-failed",
        retried.run_id,
    ]


def test_retry_after_failed_retry_creates_new_run(monkeypatch, tmp_path):
    """幂等键命中的记录若已终态 failed，再次 retry 必须新建 run 而非返回旧失败记录。"""
    settings = _settings(tmp_path)
    source_request = _request(
        "retry twice",
        conversation_id="conv-1",
        client_request_id="create-key",
    )
    _append_status(
        settings=settings,
        run_id="agent_run:source-failed",
        status="failed",
        request=source_request,
        queued_at="2026-07-25T10:00:00+00:00",
        finished_at="2026-07-25T10:01:00+00:00",
    )
    dispatched: list[str] = []
    monkeypatch.setattr(
        agent_run_service.execute_agent_run_task,
        "send",
        lambda *, run_id: dispatched.append(run_id),
    )

    first_retry = agent_run_service.retry_agent_run(
        run_id="agent_run:source-failed",
        settings=settings,
    )
    agent_run_service.fail_agent_run(
        run_id=first_retry.run_id,
        settings=settings,
        error=ValueError("worker died"),
    )

    second_retry = agent_run_service.retry_agent_run(
        run_id="agent_run:source-failed",
        settings=settings,
    )
    duplicate_second = agent_run_service.retry_agent_run(
        run_id="agent_run:source-failed",
        settings=settings,
    )

    assert first_retry.run_id != "agent_run:source-failed"
    assert second_retry.run_id != first_retry.run_id
    assert second_retry.status == "queued"
    assert duplicate_second.run_id == second_retry.run_id
    assert dispatched == [first_retry.run_id, second_retry.run_id]
    latest = GovernanceRepository(settings.governance_path).read_all(
        agent_run_service.AGENT_RUN_STREAM
    )[-1]
    assert latest["run_id"] == second_retry.run_id
    assert latest["request"]["context"]["retry_of_run_id"] == "agent_run:source-failed"


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


def test_cancel_tolerates_overlong_historical_question(tmp_path):
    """question 的 max_length=8000 约束落地前的历史 run 可能带超长 question；
    cancel 重建请求时必须经 _reconstructed_question 收敛而不是抛 RuntimeError。"""
    settings = _settings(tmp_path)
    overlong_question = "问" * 9000
    agent_run_service._append_record(
        settings,
        AgentRunRecord(
            run_id="agent_run:overlong",
            status="queued",
            question=overlong_question,
            request={
                "question": overlong_question,
                "context": {"user_id": "owner-1", "page": "agent-workbench"},
            },
            provider="hermes",
            model="gpt-test",
            transport="bridge",
            toolsets="evidence,query,research",
            queued_at="2026-07-25T10:00:00+00:00",
        ),
    )

    status = agent_run_service.cancel_agent_run(
        run_id="agent_run:overlong",
        settings=settings,
    )

    assert status.status == "cancelled"
    records = GovernanceRepository(settings.governance_path).read_all(
        agent_run_service.AGENT_RUN_STREAM
    )
    assert [record["status"] for record in records] == ["queued", "cancelled"]
    rebuilt_question = records[-1]["request"]["question"]
    assert rebuilt_question == overlong_question[:8000]


def test_list_returns_only_each_owners_latest_run_in_descending_time_order(monkeypatch, tmp_path):
    settings = _settings(tmp_path)
    # 固定时钟在 running 记录的 stale 窗口内，隔离本测试与 stale 收敛语义。
    monkeypatch.setattr(
        agent_run_service,
        "_utc_now",
        lambda: "2026-07-25T09:01:30+00:00",
    )
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


def test_list_agent_runs_applies_stale_judgment_without_writeback(monkeypatch, tmp_path):
    """列表与单条端点共用 stale 判定；列表只调整视图，不写回。"""
    settings = _settings(tmp_path)
    request = _request("stale in list", owner="owner-1")
    _append_status(
        settings=settings,
        run_id="agent_run:list-stale",
        status="running",
        request=request,
        queued_at="2026-07-25T10:00:00+00:00",
        started_at="2026-07-25T10:00:01+00:00",
    )
    # 59s elapsed > hermes timeout 9s + 30s grace.
    monkeypatch.setattr(
        agent_run_service,
        "_utc_now",
        lambda: "2026-07-25T10:01:00+00:00",
    )
    repo = GovernanceRepository(settings.governance_path)

    listed = agent_run_service.list_agent_runs(
        settings=settings,
        owner_user_id="owner-1",
        limit=20,
    )

    assert [item.status for item in listed.items] == ["failed"]
    assert listed.items[0].error_message is not None
    assert "未在运行超时后进入终态" in listed.items[0].error_message
    assert [
        record["status"]
        for record in repo.read_all(agent_run_service.AGENT_RUN_STREAM)
    ] == ["running"]

    status = agent_run_service.get_agent_run_status(
        run_id="agent_run:list-stale",
        settings=settings,
    )
    assert status.status == "failed"
    assert status.error_message == listed.items[0].error_message
    assert [
        record["status"]
        for record in repo.read_all(agent_run_service.AGENT_RUN_STREAM)
    ] == ["running", "failed"]


def _append_legacy_long_question_record(
    settings: SimpleNamespace,
    *,
    run_id: str,
    status: str,
    question: str,
    started_at: str | None = None,
) -> None:
    """约束（min/max_length）引入前的历史记录：绕过 AgentQueryRequest 直接落盘。"""
    agent_run_service._append_record(
        settings,
        AgentRunRecord(
            run_id=run_id,
            status=status,  # type: ignore[arg-type]
            question=question,
            request={
                "question": question,
                "context": {"user_id": "owner-1", "page": "agent-workbench"},
            },
            provider="hermes",
            model="gpt-test",
            transport="bridge",
            toolsets="evidence,query,research",
            queued_at="2026-07-25T10:00:00+00:00",
            started_at=started_at,
        ),
    )


def test_stale_status_read_tolerates_overlong_historical_question(monkeypatch, tmp_path):
    """question 约束晚于历史 run 引入：超长 question 的 stale 对账读取不抛错。"""
    settings = _settings(tmp_path)
    long_question = "长" * 9000
    _append_legacy_long_question_record(
        settings,
        run_id="agent_run:legacy-long",
        status="running",
        question=long_question,
        started_at="2026-07-25T10:00:01+00:00",
    )
    # 59s elapsed > hermes timeout 9s + 30s grace -> 触发 stale 对账重建 request。
    monkeypatch.setattr(
        agent_run_service,
        "_utc_now",
        lambda: "2026-07-25T10:01:00+00:00",
    )

    status = agent_run_service.get_agent_run_status(
        run_id="agent_run:legacy-long",
        settings=settings,
    )

    assert status.status == "failed"
    # run 记录与状态响应保留原文，仅审计用的重建 request 被截断。
    assert status.question == long_question


def test_fail_agent_run_tolerates_overlong_historical_question(tmp_path):
    """fail_agent_run 的回退 request 重建同样要能吞下超长历史 question。"""
    settings = _settings(tmp_path)
    long_question = "q" * 9000
    _append_legacy_long_question_record(
        settings,
        run_id="agent_run:legacy-long-fail",
        status="queued",
        question=long_question,
    )

    agent_run_service.fail_agent_run(
        run_id="agent_run:legacy-long-fail",
        settings=settings,
        error=RuntimeError("worker preparation failed"),
    )

    status = agent_run_service.get_agent_run_status(
        run_id="agent_run:legacy-long-fail",
        settings=settings,
    )
    assert status.status == "failed"


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


def test_fail_agent_run_marks_active_run_failed_with_sanitized_message_and_audit(
    tmp_path,
    caplog,
):
    settings = _settings(tmp_path)
    request = _request("prepare me")
    _append_status(
        settings=settings,
        run_id="agent_run:prep",
        status="queued",
        request=request,
        queued_at="2026-07-25T10:00:00+00:00",
    )

    agent_run_service.fail_agent_run(
        run_id="agent_run:prep",
        settings=settings,
        error=ValueError("secret-broker-detail"),
    )

    repo = GovernanceRepository(settings.governance_path)
    records = repo.read_all(agent_run_service.AGENT_RUN_STREAM)
    assert [record["status"] for record in records] == ["queued", "failed"]
    assert records[-1]["error_message"] == "Agent run preparation failed."
    assert records[-1]["finished_at"]
    audit = repo.read_all(agent_run_service.AGENT_AUDIT_STREAM)[-1]
    assert audit["run_id"] == "agent_run:prep"
    assert audit["result_meta"]["result_kind"] == "agent.run_failed"
    assert audit["result_meta"]["error_type"] == "ValueError"
    assert audit["result_meta"]["error_code"] == "AGENT_RUN_PREPARATION_FAILED"
    public_material = str([records, audit])
    assert "secret-broker-detail" not in public_material
    assert "secret-broker-detail" not in caplog.text
    assert "error_code=AGENT_RUN_PREPARATION_FAILED" in caplog.text

    agent_run_service.fail_agent_run(
        run_id="agent_run:prep",
        settings=settings,
        error=ValueError("again"),
    )
    agent_run_service.fail_agent_run(
        run_id="agent_run:missing",
        settings=settings,
        error=ValueError("unknown run is a no-op"),
    )
    assert len(repo.read_all(agent_run_service.AGENT_RUN_STREAM)) == 2


def test_stale_queued_run_reconciles_to_failed_with_audit(monkeypatch, tmp_path):
    settings = _settings(tmp_path)
    request = _request("stuck in queue")
    _append_status(
        settings=settings,
        run_id="agent_run:stuck",
        status="queued",
        request=request,
        queued_at="2026-07-20T08:00:00+00:00",
    )
    monkeypatch.setattr(
        agent_run_service,
        "_utc_now",
        lambda: "2026-07-20T08:10:01+00:00",
    )

    status = agent_run_service.get_agent_run_status(
        run_id="agent_run:stuck",
        settings=settings,
    )

    assert status.status == "failed"
    assert status.finished_at == "2026-07-20T08:10:01+00:00"
    assert status.elapsed_seconds is None
    assert status.error_message is not None
    assert "排队超过 600s" in status.error_message
    repo = GovernanceRepository(settings.governance_path)
    records = repo.read_all(agent_run_service.AGENT_RUN_STREAM)
    assert [record["status"] for record in records] == ["queued", "failed"]
    audit = repo.read_all(agent_run_service.AGENT_AUDIT_STREAM)[-1]
    assert audit["run_id"] == "agent_run:stuck"
    assert audit["result_meta"]["error_type"] == "StaleQueuedAgentRun"

    repeated = agent_run_service.get_agent_run_status(
        run_id="agent_run:stuck",
        settings=settings,
    )
    assert repeated.status == "failed"
    assert len(repo.read_all(agent_run_service.AGENT_RUN_STREAM)) == 2


def test_recent_queued_run_is_not_reconciled(monkeypatch, tmp_path):
    settings = _settings(tmp_path)
    request = _request("still waiting")
    _append_status(
        settings=settings,
        run_id="agent_run:waiting",
        status="queued",
        request=request,
        queued_at="2026-07-20T08:00:00+00:00",
    )
    monkeypatch.setattr(
        agent_run_service,
        "_utc_now",
        lambda: "2026-07-20T08:09:59+00:00",
    )

    status = agent_run_service.get_agent_run_status(
        run_id="agent_run:waiting",
        settings=settings,
    )

    assert status.status == "queued"
    records = GovernanceRepository(settings.governance_path).read_all(
        agent_run_service.AGENT_RUN_STREAM
    )
    assert [record["status"] for record in records] == ["queued"]


def test_cancel_during_execution_releases_worker_slot_without_waiting_for_provider(
    monkeypatch,
    tmp_path,
):
    settings = _settings(tmp_path)
    monkeypatch.setattr(agent_run_service, "AGENT_RUN_CANCEL_POLL_SECONDS", 0.05)
    monkeypatch.setattr(
        agent_run_service.execute_agent_run_task,
        "send",
        lambda *, run_id: None,
    )
    created = agent_run_service.create_agent_run(
        request=_request("cancel frees the slot"),
        settings=settings,
        provider="hermes",
    )
    executor_started = threading.Event()
    release_executor = threading.Event()
    executor_finished = threading.Event()

    def blocking_executor(_request, _governance_dir, _settings):
        executor_started.set()
        assert release_executor.wait(timeout=10)
        executor_finished.set()
        return _envelope("late provider result")

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            agent_run_service.execute_agent_run_by_id,
            run_id=created.run_id,
            settings=settings,
            executor=blocking_executor,
        )
        assert executor_started.wait(timeout=5)
        cancelled = agent_run_service.cancel_agent_run(
            run_id=created.run_id,
            settings=settings,
        )
        assert cancelled.status == "cancelled"
        # The worker slot must be released while the provider call is still
        # blocked (release_executor is intentionally not set yet).
        status = future.result(timeout=5)

    assert status.status == "cancelled"
    release_executor.set()
    assert executor_finished.wait(timeout=5)
    records = GovernanceRepository(settings.governance_path).read_all(
        agent_run_service.AGENT_RUN_STREAM
    )
    assert [record["status"] for record in records] == [
        "queued",
        "starting",
        "running",
        "cancelled",
    ]


def test_execution_is_not_globally_serialized_across_runs(monkeypatch, tmp_path):
    settings = _settings(tmp_path)
    monkeypatch.setattr(
        agent_run_service.execute_agent_run_task,
        "send",
        lambda *, run_id: None,
    )
    created = [
        agent_run_service.create_agent_run(
            request=_request(
                f"parallel {index}",
                conversation_id="conv-parallel",
                client_request_id=f"parallel-{index}",
            ),
            settings=settings,
            provider="hermes",
        )
        for index in range(2)
    ]
    barrier = threading.Barrier(2)

    def synchronized_executor(request, _governance_dir, _settings):
        # Both executors must be in flight at the same time; a globally
        # serialized execution path would deadlock this barrier until timeout.
        barrier.wait(timeout=5)
        return _envelope(f"done: {request.question}")

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(
            pool.map(
                lambda run_id: agent_run_service.execute_agent_run_by_id(
                    run_id=run_id,
                    settings=settings,
                    executor=synchronized_executor,
                ),
                [item.run_id for item in created],
            )
        )

    assert [status.status for status in statuses] == ["completed", "completed"]


def test_delta_publisher_persists_separate_stream_with_seq_owner_and_caps(
    monkeypatch,
    tmp_path,
):
    settings = _settings(tmp_path)
    request = _request("stream me")
    _append_status(
        settings=settings,
        run_id="agent_run:delta",
        status="running",
        request=request.model_copy(
            update={
                "context": {
                    **request.context,
                    "run_id": "agent_run:delta",
                    "agent_stream_protocol": "run_delta_v1",
                    "agent_stream_surface": "lab",
                }
            }
        ),
        queued_at="2026-07-25T10:00:00+00:00",
        started_at="2026-07-25T10:00:01+00:00",
    )
    monkeypatch.setattr(agent_run_service, "AGENT_RUN_DELTA_MAX_FRAMES", 2)
    monkeypatch.setattr(agent_run_service, "AGENT_RUN_DELTA_MAX_TOTAL_BYTES", 32)
    publisher = agent_run_service.build_agent_run_delta_publisher(
        run_id="agent_run:delta",
        settings=settings,
    )

    assert publisher.publish("第一段") is True
    assert publisher.publish("第二段") is True
    assert publisher.publish("第三段超过上限后不再落盘") is True

    repo = GovernanceRepository(settings.governance_path)
    deltas = repo.read_all(agent_run_service.AGENT_RUN_DELTA_STREAM)
    assert [
        (record["seq"], record["owner_user_id"], record["text"])
        for record in deltas
    ] == [
        (1, "owner-1", "第一段"),
        (2, "owner-1", "第二段"),
    ]
    latest = agent_run_service._latest_run_record(
        run_id="agent_run:delta",
        settings=settings,
    )
    assert latest is not None
    assert latest["status"] == "running"
    assert "partial_answer" not in latest


def test_delta_publisher_stops_after_cancel_and_is_active_false(tmp_path):
    settings = _settings(tmp_path)
    request = _request("cancel my stream")
    _append_status(
        settings=settings,
        run_id="agent_run:delta-cancel",
        status="running",
        request=request.model_copy(
            update={
                "context": {
                    **request.context,
                    "run_id": "agent_run:delta-cancel",
                    "agent_stream_protocol": "run_delta_v1",
                    "agent_stream_surface": "lab",
                }
            }
        ),
        queued_at="2026-07-25T10:00:00+00:00",
        started_at="2026-07-25T10:00:01+00:00",
    )
    publisher = agent_run_service.build_agent_run_delta_publisher(
        run_id="agent_run:delta-cancel",
        settings=settings,
    )

    assert publisher.publish("before cancel") is True
    cancelled = agent_run_service.cancel_agent_run(
        run_id="agent_run:delta-cancel",
        settings=settings,
    )

    assert cancelled.status == "cancelled"
    assert publisher.is_active() is False
    assert publisher.publish("after cancel") is False
    deltas = GovernanceRepository(settings.governance_path).read_all(
        agent_run_service.AGENT_RUN_DELTA_STREAM
    )
    assert [record["text"] for record in deltas] == ["before cancel"]


def test_iter_agent_run_events_keeps_default_contract_and_opt_in_deltas_order(tmp_path):
    settings = _settings(tmp_path)
    request = _request("completed stream")
    _append_status(
        settings=settings,
        run_id="agent_run:delta-events",
        status="completed",
        request=request.model_copy(
            update={
                "context": {
                    **request.context,
                    "run_id": "agent_run:delta-events",
                    "agent_stream_protocol": "run_delta_v1",
                    "agent_stream_surface": "lab",
                }
            }
        ),
        queued_at="2026-07-25T10:00:00+00:00",
        started_at="2026-07-25T10:00:01+00:00",
        finished_at="2026-07-25T10:00:02+00:00",
    )
    _append_delta(
        settings=settings,
        run_id="agent_run:delta-events",
        owner_user_id="owner-1",
        seq=1,
        text="第一段",
    )
    _append_delta(
        settings=settings,
        run_id="agent_run:delta-events",
        owner_user_id="owner-1",
        seq=2,
        text="第二段",
    )
    _append_delta(
        settings=settings,
        run_id="agent_run:delta-events",
        owner_user_id="other-user",
        seq=3,
        text="越权数据",
    )
    completed = agent_run_service.get_agent_run_status(
        run_id="agent_run:delta-events",
        settings=settings,
    )

    async def collect_default() -> list[str]:
        return [
            event
            async for event in agent_run_service.iter_agent_run_events(
                run_id="agent_run:delta-events",
                settings=settings,
                initial_status=completed,
            )
        ]

    async def collect_opted_in() -> list[str]:
        return [
            event
            async for event in agent_run_service.iter_agent_run_events(
                run_id="agent_run:delta-events",
                settings=settings,
                initial_status=completed,
                include_deltas=True,
                after_seq=1,
                poll_interval_seconds=0,
            )
        ]

    default_events = asyncio.run(collect_default())
    opted_in_events = asyncio.run(collect_opted_in())

    assert len(default_events) == 1
    assert default_events[0].startswith("event: run_update\n")
    assert [event.splitlines()[0] for event in opted_in_events] == [
        "event: run_delta",
        "event: run_update",
    ]
    delta_payload = json.loads(opted_in_events[0].split("data: ", 1)[1])
    assert delta_payload["seq"] == 2
    assert "owner_user_id" not in delta_payload
    assert "越权数据" not in opted_in_events[0]


def test_execute_agent_run_task_wraps_hermes_only_for_delta_protocol(monkeypatch):
    from backend.app.tasks import agent_run as task_module

    settings = SimpleNamespace()
    monkeypatch.setattr(task_module, "get_settings", lambda: settings)
    observed_calls: list[dict[str, object]] = []

    def fake_execute_hermes_agent_query(request, governance_dir, settings, **kwargs):
        observed_calls.append(
            {
                "request": request,
                "governance_dir": governance_dir,
                "settings": settings,
                "kwargs": kwargs,
            }
        )
        return _envelope("wrapped")

    class FakePublisher:
        def publish(self, _text: str) -> bool:
            return True

        def is_active(self) -> bool:
            return True

    monkeypatch.setattr(
        task_module,
        "_execute_hermes_agent_query_direct",
        fake_execute_hermes_agent_query,
    )
    monkeypatch.setattr(
        task_module.agent_run_service,
        "build_agent_run_delta_publisher",
        lambda *, run_id, settings: FakePublisher(),
    )
    monkeypatch.setattr(
        task_module.agent_run_service,
        "get_agent_run_status",
        lambda *, run_id, settings: SimpleNamespace(
            run_id=run_id,
            status="queued",
            provider="hermes",
        ),
    )

    def execute_with_protocol(*, run_id, settings, executor):
        request = _request("delta protocol").model_copy(
            update={
                "context": {
                    "user_id": "owner-1",
                    "page": "agent-workbench",
                    "run_id": run_id,
                    "agent_stream_protocol": "run_delta_v1",
                    "agent_stream_surface": "lab",
                }
            }
        )
        executor(request, "governance", settings)
        plain_request = _request("plain protocol").model_copy(
            update={
                "context": {
                    "user_id": "owner-1",
                    "page": "agent-workbench",
                    "run_id": run_id,
                }
            }
        )
        executor(plain_request, "governance", settings)
        return "executed"

    monkeypatch.setattr(
        task_module.agent_run_service,
        "execute_agent_run_by_id",
        execute_with_protocol,
        raising=False,
    )

    assert task_module.execute_agent_run_task.fn(run_id="agent_run:task-delta") is None
    assert callable(observed_calls[0]["kwargs"]["stream_delta_callback"])
    assert callable(observed_calls[0]["kwargs"]["stream_should_continue"])
    assert observed_calls[1]["kwargs"] == {}
