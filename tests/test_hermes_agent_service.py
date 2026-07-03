from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.app.agent.schemas.agent_request import AgentQueryRequest
from backend.app.services import hermes_agent_service as service


def test_build_hermes_command_passes_lite_home_and_read_only_toolsets_to_wsl():
    args = service._build_hermes_command(
        command="wsl.exe",
        wsl_distro="HermesUbuntu",
        hermes_home="/home/hermes/.hermes-moss",
        model="",
        toolsets=" file, terminal, evidence ",
        max_turns=3,
        prompt="ping",
    )

    assert args[:7] == [
        "wsl.exe",
        "-d",
        "HermesUbuntu",
        "-e",
        "env",
        "HERMES_HOME=/home/hermes/.hermes-moss",
        "/usr/local/bin/hermes",
    ]
    assert "--toolsets" in args
    assert args[args.index("--toolsets") + 1] == "evidence"


def test_build_hermes_command_restricts_toolsets_to_read_only_allowlist():
    args = service._build_hermes_command(
        command="wsl.exe",
        wsl_distro="HermesUbuntu",
        hermes_home="/home/hermes/.hermes-moss",
        model="",
        toolsets=" file, terminal, evidence, query, research, sql ",
        max_turns=3,
        prompt="ping",
    )

    assert "--toolsets" in args
    assert args[args.index("--toolsets") + 1] == "evidence,query,research"


def test_build_hermes_command_defaults_to_read_only_toolsets():
    args = service._build_hermes_command(
        command="hermes",
        wsl_distro="",
        hermes_home="",
        model="",
        toolsets="",
        max_turns=3,
        prompt="ping",
    )

    assert "--toolsets" in args
    assert args[args.index("--toolsets") + 1] == "evidence,query,research"


def test_run_hermes_agent_sets_home_in_process_env_for_non_wsl(monkeypatch):
    calls = []

    def fake_run(args, **kwargs):
        calls.append({"args": args, **kwargs})
        return SimpleNamespace(returncode=0, stdout="Warning: Unknown toolsets: evidence, query, research\npong\n", stderr="")

    monkeypatch.setattr(service.subprocess, "run", fake_run)

    result = service.run_hermes_agent(
        request=AgentQueryRequest(question="ping"),
        command="hermes",
        wsl_distro="",
        hermes_home="/tmp/moss-hermes",
        model="",
        toolsets="file",
        max_turns=1,
        timeout_seconds=5,
    )

    assert result["answer"] == "pong"
    assert result["toolsets"] == "evidence,query,research"
    assert calls[0]["env"]["HERMES_HOME"] == "/tmp/moss-hermes"
    assert "--toolsets" in calls[0]["args"]


def test_build_hermes_bridge_command_uses_wsl_env_and_repo_script():
    args = service._build_hermes_bridge_command(
        command="wsl.exe",
        wsl_distro="HermesUbuntu",
        hermes_home="/home/hermes/.hermes-moss",
        bridge_url="http://127.0.0.1:7891",
        model="",
        toolsets="file",
        max_turns=4,
    )

    assert args[:6] == [
        "wsl.exe",
        "-d",
        "HermesUbuntu",
        "-e",
        "env",
        "HERMES_HOME=/home/hermes/.hermes-moss",
    ]
    assert "/home/hermes/hermes-agent/venv/bin/python" in args
    assert "--port" in args
    assert args[args.index("--port") + 1] == "7891"
    assert "--toolsets" in args
    assert args[args.index("--toolsets") + 1] == "evidence,query,research"


def test_run_hermes_agent_uses_bridge_transport(monkeypatch):
    calls = []

    monkeypatch.setattr(service, "_ensure_hermes_bridge", lambda **kwargs: calls.append(("ensure", kwargs)))
    monkeypatch.setattr(
        service,
        "_post_hermes_bridge_query",
        lambda **kwargs: {
            "answer": "pong",
            "stdout": "pong",
            "stderr": "",
            "model": "default",
            "toolsets": "file",
            "transport": "bridge",
        },
    )
    monkeypatch.setattr(service.subprocess, "run", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("CLI should not run")))

    result = service.run_hermes_agent(
        request=AgentQueryRequest(question="ping"),
        command="wsl.exe",
        wsl_distro="HermesUbuntu",
        hermes_home="/home/hermes/.hermes-moss",
        transport="bridge",
        bridge_url="http://127.0.0.1:7891",
        model="",
        toolsets="file",
        max_turns=1,
        timeout_seconds=5,
    )

    assert result["answer"] == "pong"
    assert result["transport"] == "bridge"
    assert calls[0][0] == "ensure"


def test_build_hermes_envelope_exposes_hermes_runtime_evidence():
    envelope = service.build_hermes_envelope(
        request=AgentQueryRequest(question="ping"),
        result={
            "answer": "pong",
            "stdout": "pong",
            "stderr": "",
            "command": "hermes_bridge",
            "model": "default",
            "toolsets": "evidence,query,research",
            "transport": "bridge",
        },
    )

    assert envelope.evidence.filters_applied["provider"] == "hermes"
    assert envelope.evidence.filters_applied["model"] == "default"
    assert envelope.evidence.filters_applied["toolsets"] == "evidence,query,research"
    assert envelope.evidence.filters_applied["transport"] == "bridge"
    assert envelope.evidence.quality_flag == "warning"
    assert envelope.result_meta.quality_flag == "warning"
    assert envelope.evidence.evidence_rows == 0


def test_execute_hermes_agent_query_answers_short_open_chat_locally(monkeypatch, tmp_path):
    audit_calls = []

    monkeypatch.setattr(
        service,
        "run_hermes_agent",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("Hermes should not run for short open chat")),
    )
    monkeypatch.setattr(
        service,
        "_append_hermes_audit",
        lambda request, governance_dir, envelope, result: audit_calls.append(
            (request, governance_dir, envelope, result)
        ),
    )

    envelope = service.execute_hermes_agent_query(
        request=AgentQueryRequest(question="在吗"),
        governance_dir=str(tmp_path / "governance"),
        settings=SimpleNamespace(
            agent_hermes_command="hermes",
            agent_hermes_wsl_distro="",
            agent_hermes_home="",
            agent_hermes_transport="cli",
            agent_hermes_bridge_url="http://127.0.0.1:7891",
            agent_hermes_model="gpt-test",
            agent_hermes_toolsets="file",
            agent_hermes_max_turns=3,
            agent_hermes_timeout_seconds=9.0,
        ),
    )

    assert envelope.answer == "在，有什么可以帮你？"
    assert envelope.result_meta.result_kind == "agent.local_chat"
    assert envelope.result_meta.formal_use_allowed is False
    assert envelope.evidence.tables_used == ["agent_local_chat"]
    assert envelope.evidence.filters_applied["provider"] == "local"
    assert audit_calls


@pytest.mark.parametrize(
    ("question", "expected_text"),
    [
        ("你能做什么", "组合概览"),
        ("随便聊聊", "三类问题"),
        ("你是谁", "组合概览"),
        ("帮我想想", "三类问题"),
        ("今天该关注什么", "三类问题"),
    ],
)
def test_execute_hermes_agent_query_answers_open_chat_prompts_locally(
    question,
    expected_text,
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        service,
        "run_hermes_agent",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("Hermes should not run for open chat prompts")),
    )
    monkeypatch.setattr(service, "_append_hermes_audit", lambda *_args, **_kwargs: None)

    envelope = service.execute_hermes_agent_query(
        request=AgentQueryRequest(question=question),
        governance_dir=str(tmp_path / "governance"),
        settings=SimpleNamespace(
            agent_hermes_command="hermes",
            agent_hermes_wsl_distro="",
            agent_hermes_home="",
            agent_hermes_transport="cli",
            agent_hermes_bridge_url="http://127.0.0.1:7891",
            agent_hermes_model="gpt-test",
            agent_hermes_toolsets="file",
            agent_hermes_max_turns=3,
            agent_hermes_timeout_seconds=9.0,
        ),
    )

    assert expected_text in envelope.answer
    assert envelope.result_meta.result_kind == "agent.local_chat"
    assert envelope.result_meta.formal_use_allowed is False
    assert envelope.evidence.filters_applied["provider"] == "local"


def test_execute_hermes_agent_query_keeps_business_questions_on_hermes_path(monkeypatch, tmp_path):
    run_calls = []

    def fake_run_hermes_agent(**kwargs):
        run_calls.append(kwargs)
        return {
            "answer": "formal business path",
            "stdout": "formal business path",
            "stderr": "",
            "command": "hermes",
            "model": "gpt-test",
            "toolsets": "evidence,query,research",
            "transport": "cli",
        }

    monkeypatch.setattr(service, "run_hermes_agent", fake_run_hermes_agent)
    monkeypatch.setattr(service, "_append_hermes_audit", lambda *_args, **_kwargs: None)

    envelope = service.execute_hermes_agent_query(
        request=AgentQueryRequest(question="组合风险今天该关注什么"),
        governance_dir=str(tmp_path / "governance"),
        settings=SimpleNamespace(
            agent_hermes_command="hermes",
            agent_hermes_wsl_distro="",
            agent_hermes_home="",
            agent_hermes_transport="cli",
            agent_hermes_bridge_url="http://127.0.0.1:7891",
            agent_hermes_model="gpt-test",
            agent_hermes_toolsets="file",
            agent_hermes_max_turns=3,
            agent_hermes_timeout_seconds=9.0,
        ),
    )

    assert run_calls
    assert envelope.answer == "formal business path"
    assert envelope.result_meta.result_kind == "agent.hermes"


def test_execute_hermes_agent_query_returns_local_fallback_when_runtime_fails(monkeypatch, tmp_path):
    audit_calls = []

    def fake_run_hermes_agent(**_kwargs):
        raise RuntimeError("Hermes failed with exit code 1: [Errno 32] Broken pipe")

    def fake_append_audit(request, governance_dir, envelope, result):
        audit_calls.append((request, governance_dir, envelope, result))

    monkeypatch.setattr(service, "run_hermes_agent", fake_run_hermes_agent)
    monkeypatch.setattr(service, "_append_hermes_audit", fake_append_audit)

    envelope = service.execute_hermes_agent_query(
        request=AgentQueryRequest(question="summarize this open ended question"),
        governance_dir=str(tmp_path / "governance"),
        settings=SimpleNamespace(
            agent_hermes_command="hermes",
            agent_hermes_wsl_distro="",
            agent_hermes_home="",
            agent_hermes_transport="cli",
            agent_hermes_bridge_url="http://127.0.0.1:7891",
            agent_hermes_model="gpt-test",
            agent_hermes_toolsets="file",
            agent_hermes_max_turns=3,
            agent_hermes_timeout_seconds=9.0,
        ),
    )

    assert "local stable fallback" in envelope.answer
    assert envelope.result_meta.result_kind == "agent.hermes_fallback"
    assert envelope.result_meta.vendor_status == "vendor_unavailable"
    assert envelope.result_meta.formal_use_allowed is False
    assert envelope.evidence.tables_used == ["hermes_local_fallback"]
    assert envelope.evidence.filters_applied["fallback_provider"] == "local"
    assert "Broken pipe" in envelope.evidence.filters_applied["fallback_reason"]
    assert audit_calls


def test_warm_hermes_bridge_if_configured_starts_daemon_thread(monkeypatch):
    calls = []

    class FakeThread:
        def __init__(self, *, target, kwargs, daemon, name):
            calls.append(
                {
                    "target": target,
                    "kwargs": kwargs,
                    "daemon": daemon,
                    "name": name,
                }
            )

        def start(self):
            calls.append("started")

    monkeypatch.setattr(service.threading, "Thread", FakeThread)

    started = service.warm_hermes_bridge_if_configured(
        SimpleNamespace(
            agent_enabled=True,
            agent_provider="hermes",
            agent_hermes_transport="bridge",
            agent_hermes_command="wsl.exe",
            agent_hermes_wsl_distro="HermesUbuntu",
            agent_hermes_home="/home/hermes/.hermes-moss",
            agent_hermes_bridge_url="http://127.0.0.1:7891",
            agent_hermes_model="",
            agent_hermes_toolsets="file",
            agent_hermes_max_turns=20,
            agent_hermes_timeout_seconds=180.0,
        )
    )

    assert started is True
    assert calls[0]["daemon"] is True
    assert calls[0]["name"] == "moss-hermes-bridge-warmup"
    assert calls[0]["kwargs"]["toolsets"] == "evidence,query,research"
    assert calls[1] == "started"


def test_warm_hermes_bridge_if_configured_skips_non_bridge_settings(monkeypatch):
    monkeypatch.setattr(
        service.threading,
        "Thread",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("warmup should not start")),
    )

    started = service.warm_hermes_bridge_if_configured(
        SimpleNamespace(
            agent_enabled=True,
            agent_provider="local",
            agent_hermes_transport="cli",
        )
    )

    assert started is False
