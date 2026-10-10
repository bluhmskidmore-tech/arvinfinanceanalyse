from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.app.tasks import agent_run as agent_run_task_module

pytestmark = [
    pytest.mark.excluded_surface_acceptance,
    pytest.mark.surface_agent_mvp,
]


@pytest.mark.parametrize(
    ("provider", "executor_name"),
    (
        ("local", "_execute_local_agent_query"),
        ("hermes", "execute_hermes_agent_query"),
        ("dexter", "execute_dexter_agent_query"),
    ),
)
def test_execute_agent_run_task_maps_persisted_provider_to_executor(
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
    executor_name: str,
) -> None:
    settings = SimpleNamespace()
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(agent_run_task_module, "get_settings", lambda: settings)
    monkeypatch.setattr(
        agent_run_task_module.agent_run_service,
        "get_agent_run_status",
        lambda *, run_id, settings: SimpleNamespace(
            run_id=run_id,
            status="queued",
            provider=provider,
        ),
    )

    def execute_agent_run_by_id(*, run_id, settings, executor):
        calls.append(
            {
                "run_id": run_id,
                "settings": settings,
                "executor": executor,
            }
        )
        return "executed"

    monkeypatch.setattr(
        agent_run_task_module.agent_run_service,
        "execute_agent_run_by_id",
        execute_agent_run_by_id,
        raising=False,
    )

    result = agent_run_task_module.execute_agent_run_task.fn(run_id="agent_run:test")

    assert result is None
    assert calls == [
        {
            "run_id": "agent_run:test",
            "settings": settings,
            "executor": getattr(agent_run_task_module, executor_name),
        }
    ]


def test_execute_agent_run_task_does_not_restart_cancelled_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace()
    monkeypatch.setattr(agent_run_task_module, "get_settings", lambda: settings)
    monkeypatch.setattr(
        agent_run_task_module.agent_run_service,
        "get_agent_run_status",
        lambda *, run_id, settings: SimpleNamespace(
            run_id=run_id,
            status="cancelled",
            provider="hermes",
        ),
    )

    def fail_if_executed(**_kwargs):
        raise AssertionError("cancelled run must not invoke an external agent")

    monkeypatch.setattr(
        agent_run_task_module.agent_run_service,
        "execute_agent_run_by_id",
        fail_if_executed,
        raising=False,
    )

    assert agent_run_task_module.execute_agent_run_task.fn(run_id="agent_run:cancelled") is None


def test_execute_agent_run_task_marks_run_failed_for_unsupported_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace()
    monkeypatch.setattr(agent_run_task_module, "get_settings", lambda: settings)
    monkeypatch.setattr(
        agent_run_task_module.agent_run_service,
        "get_agent_run_status",
        lambda *, run_id, settings: SimpleNamespace(
            run_id=run_id,
            status="queued",
            provider="bogus",
        ),
    )
    executed: list[dict[str, object]] = []
    monkeypatch.setattr(
        agent_run_task_module.agent_run_service,
        "execute_agent_run_by_id",
        lambda **kwargs: executed.append(kwargs),
        raising=False,
    )
    failures: list[tuple[str, Exception]] = []
    monkeypatch.setattr(
        agent_run_task_module.agent_run_service,
        "fail_agent_run",
        lambda *, run_id, settings, error: failures.append((run_id, error)),
    )

    assert agent_run_task_module.execute_agent_run_task.fn(run_id="agent_run:bogus") is None

    assert executed == []
    assert len(failures) == 1
    assert failures[0][0] == "agent_run:bogus"
    assert isinstance(failures[0][1], ValueError)


def test_execute_agent_run_task_marks_run_failed_when_execution_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace()
    monkeypatch.setattr(agent_run_task_module, "get_settings", lambda: settings)
    monkeypatch.setattr(
        agent_run_task_module.agent_run_service,
        "get_agent_run_status",
        lambda *, run_id, settings: SimpleNamespace(
            run_id=run_id,
            status="queued",
            provider="hermes",
        ),
    )

    def broken_execution(**_kwargs):
        raise RuntimeError("invalid persisted request payload")

    monkeypatch.setattr(
        agent_run_task_module.agent_run_service,
        "execute_agent_run_by_id",
        broken_execution,
        raising=False,
    )
    failures: list[tuple[str, Exception]] = []
    monkeypatch.setattr(
        agent_run_task_module.agent_run_service,
        "fail_agent_run",
        lambda *, run_id, settings, error: failures.append((run_id, error)),
    )

    assert agent_run_task_module.execute_agent_run_task.fn(run_id="agent_run:broken") is None

    assert len(failures) == 1
    assert failures[0][0] == "agent_run:broken"
    assert isinstance(failures[0][1], RuntimeError)


def test_execute_agent_run_task_marks_run_failed_and_reraises_on_time_limit_interrupt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dramatiq TimeLimitExceeded 是 BaseException 子类：必须先收敛 run 再重抛。"""
    from dramatiq.middleware import TimeLimitExceeded

    settings = SimpleNamespace()
    monkeypatch.setattr(agent_run_task_module, "get_settings", lambda: settings)
    monkeypatch.setattr(
        agent_run_task_module.agent_run_service,
        "get_agent_run_status",
        lambda *, run_id, settings: SimpleNamespace(
            run_id=run_id,
            status="running",
            provider="hermes",
        ),
    )

    def interrupted_execution(**_kwargs):
        raise TimeLimitExceeded("time limit exceeded")

    monkeypatch.setattr(
        agent_run_task_module.agent_run_service,
        "execute_agent_run_by_id",
        interrupted_execution,
        raising=False,
    )
    failures: list[tuple[str, BaseException]] = []
    monkeypatch.setattr(
        agent_run_task_module.agent_run_service,
        "fail_agent_run",
        lambda *, run_id, settings, error: failures.append((run_id, error)),
    )

    with pytest.raises(TimeLimitExceeded):
        agent_run_task_module.execute_agent_run_task.fn(run_id="agent_run:time-limit")

    assert len(failures) == 1
    assert failures[0][0] == "agent_run:time-limit"
    assert isinstance(failures[0][1], TimeLimitExceeded)


def test_execute_agent_run_task_is_registered_without_external_call_retries() -> None:
    actor = agent_run_task_module.execute_agent_run_task

    assert actor.actor_name == "execute_agent_run"
    assert actor.options["max_retries"] == 0
    assert actor.options["time_limit"] == 3_600_000


def test_local_executor_matches_agent_route_executor_signature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = SimpleNamespace(question="portfolio review")
    settings = SimpleNamespace(duckdb_path="moss.duckdb")
    calls: list[dict[str, object]] = []

    def execute_agent_query(*, request, duckdb_path, governance_dir):
        calls.append(
            {
                "request": request,
                "duckdb_path": duckdb_path,
                "governance_dir": governance_dir,
            }
        )
        return "local-result"

    monkeypatch.setattr(agent_run_task_module, "execute_agent_query", execute_agent_query)

    result = agent_run_task_module._execute_local_agent_query(
        request,
        "governance",
        settings,
    )

    assert result == "local-result"
    assert calls == [
        {
            "request": request,
            "duckdb_path": "moss.duckdb",
            "governance_dir": "governance",
        }
    ]
