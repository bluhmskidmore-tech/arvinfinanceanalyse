from __future__ import annotations

from types import SimpleNamespace
import json

from backend.app.agent.runtime.toolset_policy import normalize_read_only_toolsets
from backend.app.agent.schemas.agent_request import AgentQueryRequest
from backend.app.services import dexter_agent_service, hermes_agent_service

import pytest

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_agent_mvp,
]


def _toolsets_arg(args: list[str]) -> str:
    assert "--toolsets" in args
    return args[args.index("--toolsets") + 1]


def test_agent_toolset_policy_keeps_only_read_only_toolsets() -> None:
    assert normalize_read_only_toolsets("") == "evidence,query,research"
    assert normalize_read_only_toolsets("terminal,file,sql") == "evidence,query,research"
    assert normalize_read_only_toolsets("file,terminal,query,sql,research,evidence,files") == (
        "query,research,evidence"
    )
    assert normalize_read_only_toolsets("Evidence,query,query") == "evidence,query"


def test_hermes_cli_invocation_does_not_forward_mutating_toolsets(monkeypatch) -> None:
    captured: dict[str, list[str]] = {}

    def fake_run(args: list[str], **_kwargs: object) -> SimpleNamespace:
        captured["args"] = args
        return SimpleNamespace(returncode=0, stdout="Hermes answered.", stderr="")

    monkeypatch.setattr(hermes_agent_service.subprocess, "run", fake_run)

    result = hermes_agent_service.run_hermes_agent(
        request=AgentQueryRequest(question="external provider health check"),
        command="hermes",
        wsl_distro="",
        hermes_home="",
        transport="cli",
        bridge_url="",
        model="",
        toolsets="file,terminal,query",
        max_turns=1,
        timeout_seconds=1,
    )

    assert result["toolsets"] == "query"
    assert _toolsets_arg(captured["args"]) == "query"


def test_dexter_cli_invocation_does_not_forward_mutating_toolsets(monkeypatch) -> None:
    captured: dict[str, list[str]] = {}

    def fake_run(args: list[str], **_kwargs: object) -> SimpleNamespace:
        captured["args"] = args
        return SimpleNamespace(returncode=0, stdout='{"answer":"Dexter answered."}', stderr="")

    monkeypatch.setattr(dexter_agent_service.subprocess, "run", fake_run)

    dexter_agent_service.run_dexter_agent(
        request=AgentQueryRequest(question="external provider health check"),
        command="dexter",
        transport="cli",
        bridge_url="",
        model="",
        toolsets="sql,files,research",
        timeout_seconds=1,
    )

    assert _toolsets_arg(captured["args"]) == "research"


def test_external_provider_bridge_requests_do_not_forward_mutating_toolsets(monkeypatch) -> None:
    captured: dict[str, dict[str, object]] = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(self.payload).encode("utf-8")

    def fake_urlopen(request, **_kwargs: object):
        body = json.loads(request.data.decode("utf-8"))
        url = str(request.full_url)
        captured[url] = body
        response = FakeResponse()
        response.payload = {
            "ok": True,
            "answer": "Bridge answered.",
            "toolsets": "terminal,file,query" if "7891" in url else "sql,files,research",
        }
        return response

    monkeypatch.setattr(hermes_agent_service.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(hermes_agent_service, "_ensure_hermes_bridge", lambda **_kwargs: None)
    monkeypatch.setattr(dexter_agent_service.urllib.request, "urlopen", fake_urlopen)

    hermes = hermes_agent_service.run_hermes_agent(
        request=AgentQueryRequest(question="external provider health check"),
        command="hermes",
        wsl_distro="",
        hermes_home="",
        transport="bridge",
        bridge_url="http://127.0.0.1:7891",
        model="",
        toolsets="terminal,file,query",
        max_turns=1,
        timeout_seconds=1,
    )
    dexter = dexter_agent_service.run_dexter_agent(
        request=AgentQueryRequest(question="external provider health check"),
        command="dexter",
        transport="sidecar",
        bridge_url="http://127.0.0.1:7892",
        model="",
        toolsets="sql,files,research",
        timeout_seconds=1,
    )

    assert captured["http://127.0.0.1:7891/query"]["toolsets"] == "query"
    assert captured["http://127.0.0.1:7892/query"]["toolsets"] == "research"
    assert hermes["toolsets"] == "query"
    assert dexter["toolsets"] == "research"
