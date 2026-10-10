"""Targeted scheduler queries for the data-center control plane."""

from __future__ import annotations

import subprocess

import pytest

from backend.app.services import data_health_service
from backend.app.services import data_update_service as service


SCHTASKS_HEADER = (
    '"主机名","任务名","下次运行时间","模式","登录模式","上次运行时间","上次结果","创建者","要运行的任务"\n'
)
TASK_NAMES = tuple(service.TASK_LABELS)
ERROR_DETAIL = "无法读取本机计划任务，请检查运行环境或查询权限。"


def _task_row(
    task_name: str,
    *,
    task_status: str = "就绪",
    last_result: str = "0",
    duplicate: bool = False,
) -> str:
    row = (
        f'"主机","\\{task_name}","2026-09-16 18:45:00",'
        f'"{task_status}","后台","2026-09-15 18:45:00","{last_result}","u","run"\n'
    )
    return row + row if duplicate else row


def _task_csv(
    task_name: str,
    *,
    task_status: str = "就绪",
    last_result: str = "0",
    duplicate: bool = False,
) -> str:
    return SCHTASKS_HEADER + _task_row(
        task_name,
        task_status=task_status,
        last_result=last_result,
        duplicate=duplicate,
    )


def _full_csv(*, last_result: str = "0") -> str:
    return SCHTASKS_HEADER + "".join(
        _task_row(task_name, last_result=last_result) for task_name in TASK_NAMES
    )


@pytest.mark.unit
def test_schtasks_query_preserves_default_and_scoped_argv_and_unicode_decoding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []
    csv_text = _task_csv("MOSS-DailyDataRefresh")

    def _run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout=csv_text.encode("utf-8-sig"))

    monkeypatch.setattr(data_health_service.subprocess, "run", _run)

    assert data_health_service._run_schtasks_query() == csv_text
    assert data_health_service._run_schtasks_query("MOSS-DailyDataRefresh") == csv_text

    assert calls[0][0] == ["schtasks", "/query", "/fo", "csv", "/v"]
    assert calls[1][0] == [
        "schtasks",
        "/query",
        "/tn",
        "MOSS-DailyDataRefresh",
        "/fo",
        "csv",
        "/v",
    ]
    for _, kwargs in calls:
        assert kwargs == {
            "capture_output": True,
            "timeout": data_health_service._SCHTASKS_TIMEOUT_SECONDS,
            "check": True,
        }


@pytest.mark.unit
def test_scheduled_updates_uses_all_fixed_tasks_and_preserves_parser_statuses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str | None] = []
    rows = {
        "MOSS-DataUpdateQueue": {"task_status": "就绪", "last_result": "0"},
        "MOSS-DailyDataRefresh": {"task_status": "就绪", "last_result": "2"},
        "MOSS-SupplyFreshnessSentry": {"task_status": "正在运行", "last_result": "267009"},
        "MOSS-BalanceMovementFreshness": {"task_status": "已禁用", "last_result": "0"},
        "MOSS-MonthlyWalkForward": {"task_status": "就绪", "last_result": "267011"},
    }

    def _query(task_name: str | None = None, **_kwargs: object) -> str:
        calls.append(task_name)
        assert task_name is not None
        values = rows[task_name]
        return _task_csv(task_name, **values, duplicate=task_name == "MOSS-DailyDataRefresh")

    monkeypatch.setattr(service, "_run_schtasks_query", _query)

    result = service.scheduled_updates()
    tasks = {str(row["task_name"]): row for row in result["tasks"]}

    assert result["status"] == "available"
    assert calls == list(TASK_NAMES)
    assert {name: tasks[name]["status"] for name in TASK_NAMES} == {
        "MOSS-DataUpdateQueue": "ready",
        "MOSS-DailyDataRefresh": "warning",
        "MOSS-SupplyFreshnessSentry": "running",
        "MOSS-BalanceMovementFreshness": "disabled",
        "MOSS-MonthlyWalkForward": "never_run",
    }
    assert len(tasks) == len(TASK_NAMES)
    assert tasks["MOSS-DailyDataRefresh"]["last_result"] == "2"


@pytest.mark.parametrize(
    "failure_mode",
    ["missing", "empty", "timeout", "permission", "not_found"],
)
@pytest.mark.unit
def test_targeted_query_failure_falls_back_once_to_full_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    failure_mode: str,
) -> None:
    calls: list[str | None] = []
    failing_task = TASK_NAMES[1]

    def _query(task_name: str | None = None, **_kwargs: object) -> str:
        calls.append(task_name)
        if task_name is None:
            return _full_csv()
        if task_name == failing_task:
            if failure_mode == "missing":
                return _task_csv("MOSS-UnknownTask")
            if failure_mode == "empty":
                return ""
            if failure_mode == "timeout":
                raise TimeoutError("targeted query timed out")
            if failure_mode == "permission":
                raise PermissionError("targeted query denied")
            raise FileNotFoundError("schtasks not found")
        return _task_csv(task_name, last_result="2")

    monkeypatch.setattr(service, "_run_schtasks_query", _query)

    result = service.scheduled_updates()
    tasks = {str(row["task_name"]): row for row in result["tasks"]}

    assert calls == [TASK_NAMES[0], failing_task, None]
    assert result["status"] == "available"
    assert len(tasks) == len(TASK_NAMES)
    # The partial targeted result is discarded; the full fallback says result 0.
    assert all(task["status"] == "ready" for task in tasks.values())


@pytest.mark.unit
def test_fallback_error_does_not_merge_partial_targeted_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str | None] = []

    def _query(task_name: str | None = None, **_kwargs: object) -> str:
        calls.append(task_name)
        if task_name is None:
            raise PermissionError("full query denied")
        if task_name == TASK_NAMES[1]:
            return ""
        return _task_csv(task_name, last_result="0")

    monkeypatch.setattr(service, "_run_schtasks_query", _query)

    assert service.scheduled_updates() == {
        "status": "error",
        "detail": ERROR_DETAIL,
        "tasks": [],
    }
    assert calls == [TASK_NAMES[0], TASK_NAMES[1], None]


@pytest.mark.unit
def test_empty_full_fallback_preserves_missing_task_semantics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str | None] = []

    def _query(task_name: str | None = None, **_kwargs: object) -> str:
        calls.append(task_name)
        if task_name is None:
            return SCHTASKS_HEADER
        return ""

    monkeypatch.setattr(service, "_run_schtasks_query", _query)

    result = service.scheduled_updates()
    assert result["status"] == "available"
    assert calls == [TASK_NAMES[0], None]
    assert [row["status"] for row in result["tasks"]] == ["missing"] * len(TASK_NAMES)


@pytest.mark.unit
def test_scheduler_programming_error_is_not_reported_as_query_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken_query(*_args: object, **_kwargs: object) -> str:
        raise TypeError("scheduler implementation defect")

    monkeypatch.setattr(service, "_run_schtasks_query", broken_query)
    with pytest.raises(TypeError, match="scheduler implementation defect"):
        service.scheduled_updates()


@pytest.mark.unit
def test_targeted_queries_share_one_fifteen_second_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = [100.0]
    timeouts: list[float] = []

    def _monotonic() -> float:
        return clock[0]

    def _query(task_name: str | None = None, **kwargs: object) -> str:
        assert task_name is not None
        timeout = kwargs.get("timeout")
        assert isinstance(timeout, float)
        timeouts.append(timeout)
        clock[0] += {
            TASK_NAMES[0]: 1.0,
            TASK_NAMES[1]: 3.0,
            TASK_NAMES[2]: 4.0,
            TASK_NAMES[3]: 3.0,
            TASK_NAMES[4]: 1.0,
        }[task_name]
        return _task_csv(task_name)

    monkeypatch.setattr(service.time, "monotonic", _monotonic)
    monkeypatch.setattr(service, "_run_schtasks_query", _query)

    result = service.scheduled_updates()

    assert result["status"] == "available"
    assert len(timeouts) == len(TASK_NAMES)
    assert timeouts == pytest.approx([15.0, 14.0, 11.0, 7.0, 4.0])
    assert all(later < earlier for earlier, later in zip(timeouts, timeouts[1:]))


@pytest.mark.unit
def test_exhausted_target_budget_calls_one_full_fallback_and_discards_partial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = [0.0]
    calls: list[tuple[str | None, float | None]] = []

    def _monotonic() -> float:
        return clock[0]

    def _query(task_name: str | None = None, **kwargs: object) -> str:
        timeout = kwargs.get("timeout")
        calls.append((task_name, timeout if isinstance(timeout, float) else None))
        if task_name is None:
            return _full_csv()
        clock[0] = 16.0
        return _task_csv(task_name, last_result="2")

    monkeypatch.setattr(service.time, "monotonic", _monotonic)
    monkeypatch.setattr(service, "_run_schtasks_query", _query)

    result = service.scheduled_updates()
    tasks = {str(row["task_name"]): row for row in result["tasks"]}

    assert calls == [(TASK_NAMES[0], 15.0), (None, None)]
    assert result["status"] == "available"
    assert all(task["status"] == "ready" for task in tasks.values())


@pytest.mark.unit
def test_multiple_distinct_target_rows_trigger_one_full_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str | None] = []

    def _query(task_name: str | None = None, **_kwargs: object) -> str:
        calls.append(task_name)
        if task_name is None:
            return _full_csv()
        if task_name == TASK_NAMES[0]:
            return SCHTASKS_HEADER + _task_row(task_name) + _task_row(TASK_NAMES[1])
        return _task_csv(task_name)

    monkeypatch.setattr(service, "_run_schtasks_query", _query)

    result = service.scheduled_updates()

    assert calls == [TASK_NAMES[0], None]
    assert result["status"] == "available"
    assert len(result["tasks"]) == len(TASK_NAMES)


@pytest.mark.unit
def test_schtasks_query_propagates_nonzero_and_timeout_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    errors: list[BaseException] = [
        subprocess.CalledProcessError(2, ["schtasks", "/query"]),
        subprocess.TimeoutExpired(["schtasks", "/query"], 15),
    ]

    for error in errors:
        def _raise(*_args: object, _error: BaseException = error, **_kwargs: object) -> None:
            raise _error

        monkeypatch.setattr(data_health_service.subprocess, "run", _raise)
        with pytest.raises(type(error)):
            data_health_service._run_schtasks_query()


@pytest.mark.unit
def test_require_scheduler_reads_a_fresh_snapshot_for_each_precondition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshots = [
        {"status": "available", "tasks": [{"task_name": service.MARKET_TASK_NAME, "status": "ready"}]},
        {"status": "available", "tasks": [{"task_name": service.MARKET_TASK_NAME, "status": "missing"}]},
    ]
    calls: list[None] = []

    def _snapshot() -> dict[str, object]:
        calls.append(None)
        return snapshots.pop(0)

    monkeypatch.setattr(service, "scheduled_updates", _snapshot)

    service.require_scheduler(service.MARKET_TASK_NAME)
    with pytest.raises(RuntimeError, match="尚未启用"):
        service.require_scheduler(service.MARKET_TASK_NAME)

    assert len(calls) == 2
