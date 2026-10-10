"""Run cancellation must reach the provider instead of only the run record.

The supervisor hands a ``threading.Event`` to providers that declare the
optional ``cancel_event`` keyword and sets it as soon as the run becomes
terminal, so abandoned Hermes and Dexter CLI calls stop their child processes.
Providers that keep the historical three-argument protocol (local) are unchanged,
and a provider result arriving after the cancel must never overwrite the
``cancelled`` terminal state or add a failed-run audit row.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from backend.app.agent.schemas.agent_request import AgentQueryRequest
from backend.app.governance.agent_audit import AGENT_AUDIT_STREAM
from backend.app.repositories.governance_repo import GovernanceRepository
from backend.app.services import agent_run_service
from backend.app.tasks import agent_run as agent_run_task_module
from tests.test_agent_runs_api import _settings

pytestmark = [
    pytest.mark.excluded_surface_acceptance,
    pytest.mark.surface_agent_mvp,
]


def _request(client_request_id: str) -> AgentQueryRequest:
    return AgentQueryRequest(
        question="cancel the provider call",
        context={"user_id": "owner-1", "client_request_id": client_request_id},
    )


def _run_rows(settings) -> list[dict[str, object]]:
    return GovernanceRepository(base_dir=settings.governance_path).read_all(
        agent_run_service.AGENT_RUN_STREAM
    )


def _audit_rows(settings) -> list[dict[str, object]]:
    return GovernanceRepository(base_dir=settings.governance_path).read_all(
        AGENT_AUDIT_STREAM
    )


def _wait_for_status(settings, run_id: str, status: str) -> None:
    for _ in range(300):
        rows = [row for row in _run_rows(settings) if row.get("run_id") == run_id]
        if rows and str(rows[-1].get("status") or "") == status:
            return
        time.sleep(0.02)
    raise AssertionError(f"run {run_id} never reached status={status}")


def test_cancelling_a_run_sets_the_provider_cancel_event_and_releases_the_slot(
    monkeypatch,
    tmp_path: Path,
):
    settings = _settings(tmp_path)
    monkeypatch.setattr(agent_run_service, "AGENT_RUN_CANCEL_POLL_SECONDS", 0.02)
    received: list[threading.Event | None] = []
    executor_entered = threading.Event()
    executor_unblocked = threading.Event()
    worker_released = threading.Event()

    def blocking_executor(
        request,
        governance_dir,
        runtime_settings,
        *,
        cancel_event: threading.Event | None = None,
    ):
        del request, governance_dir, runtime_settings
        received.append(cancel_event)
        executor_entered.set()
        assert cancel_event is not None
        assert cancel_event.wait(timeout=20)
        executor_unblocked.set()
        # Hermes 观察到置位后终止子进程并以取消错误码抛出。
        raise RuntimeError("hermes run cancelled")

    def dispatch_on_worker_thread(*, run_id):
        def _work() -> None:
            try:
                agent_run_service.execute_agent_run_by_id(
                    run_id=run_id,
                    settings=settings,
                    executor=blocking_executor,
                )
            finally:
                worker_released.set()

        threading.Thread(target=_work, name="fake-agent-worker", daemon=True).start()

    monkeypatch.setattr(
        agent_run_service.execute_agent_run_task,
        "send",
        dispatch_on_worker_thread,
    )
    created = agent_run_service.create_agent_run(
        request=_request("req-cancel-hook"),
        settings=settings,
        provider="hermes",
    )
    assert executor_entered.wait(timeout=20)
    _wait_for_status(settings, created.run_id, "running")

    cancelled = agent_run_service.cancel_agent_run(
        run_id=created.run_id,
        settings=settings,
    )

    assert cancelled.status == "cancelled"
    # provider 收到置位的事件并解除阻塞，worker 槽随监督循环返回而释放。
    assert executor_unblocked.wait(timeout=20)
    assert worker_released.wait(timeout=20)
    assert len(received) == 1
    assert isinstance(received[0], threading.Event)
    assert received[0].is_set()
    # 取消后 provider 抛出的取消错误不得写入新的终态或失败审计。
    statuses = [
        str(row.get("status") or "")
        for row in _run_rows(settings)
        if row.get("run_id") == created.run_id
    ]
    assert statuses == ["queued", "starting", "running", "cancelled"]
    assert statuses[-1] == "cancelled"
    result_kinds = [
        str((row.get("result_meta") or {}).get("result_kind") or "")
        for row in _audit_rows(settings)
    ]
    assert "agent.run_failed" not in result_kinds
    assert result_kinds == ["agent.run_cancelled"]


def test_provider_failure_after_a_cancel_cannot_overwrite_the_cancelled_state(
    monkeypatch,
    tmp_path: Path,
):
    """守卫确认：provider 线程晚到的失败记录与失败审计一起被丢弃。"""
    settings = _settings(tmp_path)
    request = _request("req-late-failure")

    def never_dispatch(*, run_id):
        del run_id

    monkeypatch.setattr(
        agent_run_service.execute_agent_run_task,
        "send",
        never_dispatch,
    )
    created = agent_run_service.create_agent_run(
        request=request,
        settings=settings,
        provider="hermes",
    )
    agent_run_service.cancel_agent_run(run_id=created.run_id, settings=settings)
    audit_rows_before = len(_audit_rows(settings))

    appended = agent_run_service._append_record_if_latest_status(
        settings=settings,
        record=agent_run_service._transition_record(
            settings=settings,
            run_id=created.run_id,
            request=request,
            status="failed",
            error_message="late provider cancel error",
            stop_reason="provider_error",
        ),
        allowed_statuses={"starting", "running"},
        audit_payload=agent_run_service._build_failed_run_audit_payload(
            run_id=created.run_id,
            request=request,
            provider="hermes",
            error_type="RuntimeError",
        ),
    )

    assert appended is False
    assert len(_audit_rows(settings)) == audit_rows_before
    statuses = [
        str(row.get("status") or "")
        for row in _run_rows(settings)
        if row.get("run_id") == created.run_id
    ]
    assert statuses[-1] == "cancelled"
    assert "failed" not in statuses
    assert (
        agent_run_service.get_agent_run_status(
            run_id=created.run_id,
            settings=settings,
        ).status
        == "cancelled"
    )


def test_only_providers_declaring_the_keyword_receive_the_cancel_event():
    assert (
        agent_run_service._executor_accepts_cancel_event(
            agent_run_task_module.execute_hermes_agent_query
        )
        is True
    )
    for executor in (
        agent_run_task_module._execute_local_agent_query,
        lambda request, governance_dir, settings: None,
        # 只有显式声明才算加入：**kwargs 透传的测试替身保持三参数行为。
        lambda *args, **kwargs: None,
    ):
        assert agent_run_service._executor_accepts_cancel_event(executor) is False
    assert agent_run_service._executor_accepts_cancel_event(agent_run_task_module.execute_dexter_agent_query) is True


def test_legacy_three_argument_executors_are_called_unchanged(
    monkeypatch,
    tmp_path: Path,
):
    settings = _settings(tmp_path)
    calls: list[tuple[object, ...]] = []

    def legacy_executor(request, governance_dir, runtime_settings):
        calls.append((request.question, governance_dir, runtime_settings))
        raise RuntimeError("legacy provider failure")

    monkeypatch.setattr(
        agent_run_service.execute_agent_run_task,
        "send",
        lambda *, run_id: agent_run_service.execute_agent_run_by_id(
            run_id=run_id,
            settings=settings,
            executor=legacy_executor,
        ),
    )
    created = agent_run_service.create_agent_run(
        request=_request("req-legacy-executor"),
        settings=settings,
        provider="hermes",
    )

    assert len(calls) == 1
    assert calls[0][0] == "cancel the provider call"
    assert (
        agent_run_service.get_agent_run_status(
            run_id=created.run_id,
            settings=settings,
        ).status
        == "failed"
    )


@pytest.mark.parametrize(
    "context",
    (
        {},
        {
            "agent_stream_protocol": "run_delta_v1",
            "agent_stream_surface": "lab",
            "run_id": "agent_run:stream",
        },
    ),
)
def test_task_hermes_wrapper_forwards_the_cancel_event(monkeypatch, tmp_path: Path, context):
    settings = _settings(tmp_path)
    forwarded: list[object] = []

    def fake_direct(request, governance_dir, runtime_settings, **kwargs):
        del request, governance_dir, runtime_settings
        forwarded.append(kwargs.get("cancel_event"))
        return None

    monkeypatch.setattr(
        agent_run_task_module,
        "_execute_hermes_agent_query_direct",
        fake_direct,
    )
    cancel_event = threading.Event()
    request = AgentQueryRequest(question="forward the cancel hook", context=context)

    agent_run_task_module.execute_hermes_agent_query(
        request,
        str(settings.governance_path),
        settings,
        cancel_event=cancel_event,
    )

    assert forwarded == [cancel_event]
