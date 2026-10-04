from __future__ import annotations

import io
import json
from types import SimpleNamespace

import pytest

from backend.app.agent.runtime.local_request_resolution import LocalRequestResolution
from backend.app.agent.schemas.agent_request import AgentQueryRequest
from backend.app.api.routes.agent import _resolve_agent_executor, _run_executor_for_provider
from backend.app.services.agent_run_service import (
    _agent_run_stale_after_seconds,
    _provider_runtime_fields,
)
from backend.app.services import jev_decision_service, pi_agent_service
from backend.app.services.jev_decision_service import decide_jev
from backend.app.tasks.agent_run import _executor_for_provider


pytestmark = [
    pytest.mark.excluded_surface_acceptance,
    pytest.mark.surface_agent_mvp,
]


def _settings(**overrides: object) -> SimpleNamespace:
    values = {
        "agent_provider": "pi",
        "agent_pi_command": "pi-test",
        "agent_pi_model": "pi-model",
        "agent_pi_max_turns": 1,
        "agent_pi_timeout_seconds": 5.0,
        "agent_pi_forward_api_key": False,
        "agent_jev_mode": "off",
        "agent_jev_api_url": "https://jev.invalid/systemone",
        "agent_jev_model": "jev-test",
        "agent_jev_timeout_seconds": 1.0,
        "agent_jev_min_confidence": 0.85,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_pi_provider_is_available_to_sync_and_worker_dispatch():
    assert _run_executor_for_provider(_settings()) is pi_agent_service.execute_pi_agent_query
    assert _executor_for_provider("pi") is pi_agent_service.execute_pi_agent_query

    provider, executor = _resolve_agent_executor(
        AgentQueryRequest(question="hello from the provider boundary"),
        _settings(),
    )
    assert provider == "pi"
    assert executor is pi_agent_service.execute_pi_agent_query


def test_pi_run_metadata_uses_rpc_and_pi_timeout():
    settings = _settings(agent_pi_model="gpt-local", agent_pi_timeout_seconds=17.0)
    assert _provider_runtime_fields(settings, "pi") == (
        "pi",
        "gpt-local",
        "rpc",
        "none",
    )
    stale_after = _agent_run_stale_after_seconds(
        record={"provider": "pi"},
        settings=settings,
    )
    assert stale_after == 47.0


def test_pi_provider_builds_read_only_envelope_and_audit(tmp_path, monkeypatch):
    monkeypatch.setattr(
        pi_agent_service,
        "run_pi_agent",
        lambda **_kwargs: {
            "answer": "Pi handled the bounded narrative request.",
            "model": "pi-model",
            "transport": "rpc",
            "toolsets": "none",
        },
    )
    envelope = pi_agent_service.execute_pi_agent_query(
        AgentQueryRequest(question="hello from the provider boundary"),
        str(tmp_path / "governance"),
        _settings(),
    )

    assert envelope.answer == "Pi handled the bounded narrative request."
    assert envelope.result_meta.result_kind == "agent.pi"
    assert envelope.result_meta.formal_use_allowed is False
    assert envelope.evidence.tables_used == ["pi_rpc"]
    assert envelope.evidence.filters_applied["tool_policy"] == "no_tools"
    assert envelope.evidence.filters_applied["jev_mode"] == "off"

    audit_path = tmp_path / "governance" / "agent_audit.jsonl"
    prompt_path = tmp_path / "governance" / "agent_prompt.jsonl"
    assert audit_path.exists()
    assert prompt_path.exists()
    assert "hello from the provider boundary" in prompt_path.read_text(encoding="utf-8")


def test_pi_provider_falls_back_when_rpc_is_unavailable(tmp_path, monkeypatch):
    def unavailable(**_kwargs):
        raise RuntimeError("Pi command not found: pi-test")

    monkeypatch.setattr(pi_agent_service, "run_pi_agent", unavailable)
    envelope = pi_agent_service.execute_pi_agent_query(
        AgentQueryRequest(question="hello from the provider boundary"),
        str(tmp_path / "governance"),
        _settings(),
    )

    assert envelope.result_meta.result_kind == "agent.pi_fallback"
    assert envelope.result_meta.vendor_status == "vendor_unavailable"
    assert envelope.result_meta.formal_use_allowed is False
    assert envelope.evidence.tables_used == ["pi_local_fallback"]


def test_run_pi_agent_parses_rpc_and_disables_pi_tools(monkeypatch):
    events = [
        json.dumps(
            {
                "type": "message_update",
                "assistantMessageEvent": {"type": "text_delta", "delta": "hello"},
            }
        ),
        json.dumps(
            {
                "type": "message_end",
                "message": {"role": "assistant", "content": [{"type": "text", "text": " hello"}]},
            }
        ),
        json.dumps({"type": "agent_end"}),
    ]
    calls: list[tuple[list[str], dict[str, object]]] = []
    processes: list[object] = []

    class FakeProcess:
        def __init__(self):
            self.stdin = io.StringIO()
            self.stdout = io.StringIO("\n".join(events) + "\n")
            self.stderr = io.StringIO("")
            self.returncode = 0
            self.terminated = False

        def poll(self):
            return self.returncode if self.terminated else None

        def terminate(self):
            self.terminated = True

        def kill(self):
            self.terminated = True

        def wait(self, timeout=None):
            self.terminated = True
            return self.returncode

    def fake_popen(args, **kwargs):
        process = FakeProcess()
        calls.append((args, kwargs))
        processes.append(process)
        return process

    monkeypatch.setattr(pi_agent_service.subprocess, "Popen", fake_popen)
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    result = pi_agent_service.run_pi_agent(
        command="pi-test",
        model="openai/pi-model",
        timeout_seconds=2.0,
        max_turns=1,
        prompt="say hello",
    )

    assert result["answer"] == "hello"
    args = calls[0][0]
    assert args[:3] == ["pi-test", "--mode", "rpc"]
    assert "--no-tools" in args
    assert "--no-extensions" in args
    assert "--no-skills" in args
    assert "--no-context-files" in args
    assert args[-2:] == ["--model", "openai/pi-model"]
    assert "OPENAI_API_KEY" not in calls[0][1]["env"]
    sent = json.loads(processes[0].stdin.getvalue())
    assert sent == {"type": "prompt", "message": "say hello"}

    forwarded = pi_agent_service.run_pi_agent(
        command="pi-test",
        model="openai/pi-model",
        timeout_seconds=2.0,
        max_turns=1,
        prompt="say hello",
        forward_api_key=True,
    )
    assert forwarded["answer"] == "hello"
    assert calls[1][1]["env"]["OPENAI_API_KEY"] == "test-openai-key"


def test_pi_forwarding_is_scoped_to_selected_provider(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-key")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "anthropic-test-token")
    monkeypatch.setenv("XAI_API_KEY", "xai-test-key")

    env = pi_agent_service._build_pi_subprocess_env(
        forward_api_key=True,
        model="anthropic/claude-haiku-4-5",
    )

    assert env["ANTHROPIC_AUTH_TOKEN"] == "anthropic-test-token"
    assert "OPENAI_API_KEY" not in env
    assert "XAI_API_KEY" not in env


def test_pi_rpc_ignores_user_echo_and_surfaces_provider_error():
    events = [
        {"type": "message_end", "message": {"role": "user", "content": [{"type": "text", "text": "prompt"}]}},
        {
            "type": "message_end",
            "message": {
                "role": "assistant",
                "content": [],
                "stopReason": "error",
                "errorMessage": "redacted provider error",
            },
        },
    ]

    assert pi_agent_service._extract_assistant_text(events) == ""
    assert pi_agent_service._rpc_value_has_error(events) is True


def test_jev_off_never_calls_network(monkeypatch):
    def unexpected_network(*_args, **_kwargs):
        raise AssertionError("off mode must not call Jev")

    monkeypatch.setattr(jev_decision_service.urllib.request, "urlopen", unexpected_network)
    decision = decide_jev(
        AgentQueryRequest(question="hello"),
        _settings(agent_jev_mode="off"),
        resolution=LocalRequestResolution(route="provider", reason="open_chat_or_unknown"),
    )

    assert decision.allowed is True
    assert decision.route == "allow_pi"
    assert decision.source == "local"


def test_jev_active_rejects_without_key(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    decision = decide_jev(
        AgentQueryRequest(question="hello"),
        _settings(agent_jev_mode="active"),
        resolution=LocalRequestResolution(route="provider", reason="open_chat_or_unknown"),
    )

    assert decision.allowed is False
    assert decision.route == "reject"
    assert decision.error_code == "jev_api_key_missing"


def test_jev_external_state_is_structural_and_shadow_does_not_change_route(monkeypatch):
    captured: dict[str, object] = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps(
                {
                    "answers": {
                        "route": {
                            "choice": "reject",
                            "confidence": 0.99,
                        }
                    }
                }
            ).encode("utf-8")

    def fake_urlopen(request, **_kwargs):
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    monkeypatch.setattr(jev_decision_service.urllib.request, "urlopen", fake_urlopen)
    decision = decide_jev(
        AgentQueryRequest(question="secret bank amount 123456"),
        _settings(agent_jev_mode="shadow"),
        resolution=LocalRequestResolution(route="provider", reason="open_chat_or_unknown"),
    )

    assert decision.allowed is True
    assert decision.route == "allow_pi"
    assert decision.external_route == "reject"
    assert "secret bank amount" not in json.dumps(captured["body"])
