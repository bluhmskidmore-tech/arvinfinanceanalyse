from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.app.services import data_health_service


@pytest.mark.unit
def test_schtasks_query_scopes_task_and_timeout_without_changing_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    def run(command: list[str], **kwargs: object) -> SimpleNamespace:
        calls.append((command, kwargs))
        return SimpleNamespace(stdout=b"sample")

    monkeypatch.setattr(data_health_service.subprocess, "run", run)

    assert data_health_service._run_schtasks_query() == "sample"
    assert (
        data_health_service._run_schtasks_query("MOSS-DataUpdateQueue", timeout=2.5)
        == "sample"
    )
    assert calls[0][0] == ["schtasks", "/query", "/fo", "csv", "/v"]
    assert calls[0][1]["timeout"] == data_health_service._SCHTASKS_TIMEOUT_SECONDS
    assert calls[1][0] == [
        "schtasks",
        "/query",
        "/tn",
        "MOSS-DataUpdateQueue",
        "/fo",
        "csv",
        "/v",
    ]
    assert calls[1][1]["timeout"] == 2.5
    assert all(kwargs["capture_output"] and kwargs["check"] for _, kwargs in calls)
