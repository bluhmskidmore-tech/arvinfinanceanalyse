from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from backend.app.agent.runtime.subprocess_env import (
    build_agent_subprocess_env,
    is_sensitive_env_name,
)
from backend.app.agent.schemas.agent_request import AgentQueryRequest
from backend.app.governance.settings import get_settings
from backend.app.services import hermes_agent_service as service

pytestmark = [
    pytest.mark.excluded_surface_acceptance,
    pytest.mark.surface_agent_mvp,
]


_BENIGN_MCP_SHUTDOWN_STDERR = (
    "w\x00s\x00l\x00:\x00 localhost forwarding warning\x00\n"
    "\n"
    "session_id: 20260725_052841_9e1a2a\n"
    "Exception ignored in: <coroutine object MCPServerTask.run at 0x76cfdda7d440>\n"
    "Traceback (most recent call last):\n"
    '  File "/home/hermes/hermes-agent/tools/mcp_tool.py", line 2783, in run\n'
    "    parked = await self._wait_for_reconnect_or_shutdown(\n"
    "             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n"
    '  File "/home/hermes/hermes-agent/tools/mcp_tool.py", line 1997, '
    "in _wait_for_reconnect_or_shutdown\n"
    "    t.cancel()\n"
    '  File "/home/hermes/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/'
    'lib/python3.11/asyncio/base_events.py", line 762, in call_soon\n'
    "    self._check_closed()\n"
    '  File "/home/hermes/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/'
    'lib/python3.11/asyncio/base_events.py", line 520, in _check_closed\n'
    "    raise RuntimeError('Event loop is closed')\n"
    "RuntimeError: Event loop is closed\n"
)


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


def test_run_hermes_agent_keeps_answer_when_hermes_mcp_shutdown_exits_one(monkeypatch):
    def fake_run(_args, **_kwargs):
        return SimpleNamespace(
            returncode=1,
            stdout="Warning: Unknown toolsets: evidence, query, research\nHermes answered.\n",
            stderr=_BENIGN_MCP_SHUTDOWN_STDERR,
        )

    monkeypatch.setattr(service.subprocess, "run", fake_run)

    result = service.run_hermes_agent(
        request=AgentQueryRequest(question="ping"),
        command="hermes",
        wsl_distro="",
        hermes_home="",
        model="",
        toolsets="evidence,query,research",
        max_turns=1,
        timeout_seconds=5,
    )

    assert result["answer"] == "Hermes answered."


def test_run_hermes_agent_rejects_provider_error_before_mcp_shutdown(monkeypatch):
    def fake_run(_args, **_kwargs):
        return SimpleNamespace(
            returncode=1,
            stdout="Hermes answered despite provider failure.\n",
            stderr=(
                "API call failed after 3 retries: "
                "HTTP 404: Invalid URL (POST /v1/chat/completions)\n"
                + _BENIGN_MCP_SHUTDOWN_STDERR
            ),
        )

    monkeypatch.setattr(service.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="HTTP 404"):
        service.run_hermes_agent(
            request=AgentQueryRequest(question="ping"),
            command="hermes",
            wsl_distro="",
            hermes_home="",
            model="",
            toolsets="evidence,query,research",
            max_turns=1,
            timeout_seconds=5,
        )


def test_run_hermes_agent_rejects_warning_only_stdout_on_mcp_shutdown(monkeypatch):
    def fake_run(_args, **_kwargs):
        return SimpleNamespace(
            returncode=1,
            stdout="Warning: Unknown toolsets: evidence, query, research\n",
            stderr=_BENIGN_MCP_SHUTDOWN_STDERR,
        )

    monkeypatch.setattr(service.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="Hermes failed with exit code 1"):
        service.run_hermes_agent(
            request=AgentQueryRequest(question="ping"),
            command="hermes",
            wsl_distro="",
            hermes_home="",
            model="",
            toolsets="evidence,query,research",
            max_turns=1,
            timeout_seconds=5,
        )


def test_run_hermes_agent_rejects_warning_only_stdout_on_zero_exit(monkeypatch):
    def fake_run(_args, **_kwargs):
        return SimpleNamespace(
            returncode=0,
            stdout="Warning: Unknown toolsets: evidence, query, research\n",
            stderr="",
        )

    monkeypatch.setattr(service.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="Hermes returned no answer"):
        service.run_hermes_agent(
            request=AgentQueryRequest(question="ping"),
            command="hermes",
            wsl_distro="",
            hermes_home="",
            model="",
            toolsets="evidence,query,research",
            max_turns=1,
            timeout_seconds=5,
        )


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


def test_build_hermes_bridge_command_python_path_is_configurable(monkeypatch):
    monkeypatch.setenv("MOSS_AGENT_HERMES_PYTHON_PATH", "/opt/hermes/venv/bin/python")
    get_settings.cache_clear()
    try:
        args = service._build_hermes_bridge_command(
            command="wsl.exe",
            wsl_distro="HermesUbuntu",
            hermes_home="",
            bridge_url="http://127.0.0.1:7891",
            model="",
            toolsets="file",
            max_turns=4,
        )
        assert "/opt/hermes/venv/bin/python" in args
        assert "/home/hermes/hermes-agent/venv/bin/python" not in args
    finally:
        get_settings.cache_clear()


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


def test_hermes_audit_carries_managed_run_id(tmp_path):
    request = AgentQueryRequest(
        question="ping",
        context={"user_id": "u_hermes", "run_id": "agent_run:hermes-audit"},
    )
    result = {
        "answer": "pong",
        "stdout": (
            '{"access_token":"json-access-secret"} '
            "{'password': 'dict-password-secret'}"
        ),
        "stderr": (
            "opaque-provider-secret at "
            "https://user:multi-at-password@segment@provider.example/query"
        ),
        "command": "hermes_bridge",
        "model": "default",
        "toolsets": "evidence,query,research",
        "transport": "bridge",
    }
    envelope = service.build_hermes_envelope(request=request, result=result)

    service._append_hermes_audit(request, str(tmp_path / "governance"), envelope, result)

    payload = json.loads(
        (tmp_path / "governance" / "agent_audit.jsonl").read_text(encoding="utf-8").splitlines()[-1]
    )
    assert payload["run_id"] == "agent_run:hermes-audit"
    assert "stdout_excerpt" not in payload["result_meta"]
    assert "stderr_excerpt" not in payload["result_meta"]
    persisted_audit = json.dumps(payload, ensure_ascii=False)
    for marker in (
        "json-access-secret",
        "dict-password-secret",
        "opaque-provider-secret",
        "multi-at-password",
    ):
        assert marker not in persisted_audit


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


def test_execute_hermes_agent_query_returns_local_fallback_when_runtime_fails(
    monkeypatch,
    tmp_path,
    caplog,
):
    audit_calls = []
    sensitive_markers = (
        "json-access-secret",
        "dict-password-secret",
        "opaque-provider-secret",
        "multi-at-password",
    )
    provider_error = (
        '{"access_token":"json-access-secret"} '
        "{'password': 'dict-password-secret'} "
        "opaque-provider-secret at "
        "https://user:multi-at-password@segment@provider.example/query"
    )

    def fake_run_hermes_agent(**_kwargs):
        raise RuntimeError(
            "Hermes failed with exit code 1: [Errno 32] Broken pipe: "
            f"{provider_error}"
        )

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
    assert envelope.evidence.filters_applied["fallback_reason"] == "hermes_runtime_unavailable"
    assert audit_calls
    serialized_public_payload = json.dumps(
        {
            "envelope": envelope.model_dump(mode="json"),
            "audit_result": audit_calls[0][3],
        },
        ensure_ascii=False,
    )
    assert "Broken pipe" not in serialized_public_payload
    for marker in sensitive_markers:
        assert marker not in serialized_public_payload
        assert marker not in caplog.text
    assert "error_code=hermes_runtime_unavailable" in caplog.text
    assert "error_type=RuntimeError" in caplog.text
    assert "detail=" not in caplog.text


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


def _legacy_hermes_prompt(request: AgentQueryRequest) -> str:
    context = {
        "basis": request.basis,
        "filters": request.filters,
        "position_scope": request.position_scope,
        "currency_basis": request.currency_basis,
        "context": request.context,
        "page_context": request.page_context.model_dump(mode="json") if request.page_context else None,
    }
    return (
        "You are Hermes Agent connected to the MOSS business analytics system. "
        "Answer the user's question directly. If you use tools or evidence, summarize the evidence and limitations. "
        "Do not claim formal financial correctness unless the provided evidence proves it.\n\n"
        f"User question:\n{request.question}\n\n"
        f"MOSS request context:\n{context}"
    )


def _make_knowledge_vault_available(monkeypatch) -> None:
    from backend.app.services import knowledge_index_service

    monkeypatch.setattr(knowledge_index_service, "knowledge_vault_available", lambda: True)


def test_prompt_unchanged_when_ontology_unavailable(monkeypatch):
    from backend.app.ontology import loader as ontology_loader

    request = AgentQueryRequest(
        question="formal PnL",
        basis="analytical",
        filters={"report_date": "2026-06-30"},
        context={"source": "test"},
    )
    monkeypatch.setattr(
        ontology_loader,
        "load_ontology_index",
        lambda: (_ for _ in ()).throw(RuntimeError("ontology offline")),
    )

    assert service._build_hermes_prompt(request) == _legacy_hermes_prompt(request)


def test_prompt_unchanged_when_vault_unavailable(tmp_path, monkeypatch):
    from backend.app.ontology import loader as ontology_loader

    request = AgentQueryRequest(
        question="formal PnL",
        basis="analytical",
        filters={"report_date": "2026-06-30"},
        context={"source": "test"},
    )
    entity = SimpleNamespace(
        entity_id="MTR-PNL-001",
        name="正式PnL",
        unit="yuan",
        basis="formal",
        time_semantics="report_date",
        status="approved",
        authority=["docs/metric_dictionary.md#mtr-pnl-001"],
    )
    monkeypatch.setattr(
        ontology_loader,
        "load_ontology_index",
        lambda: SimpleNamespace(resolve_from_text=lambda _question: [entity]),
    )
    monkeypatch.setenv("MOSS_OBSIDIAN_VAULT_PATH", str(tmp_path / "missing-vault"))

    assert service._build_hermes_prompt(request) == _legacy_hermes_prompt(request)


def test_prompt_injects_ontology_when_vault_is_available_without_bound_notes(
    tmp_path,
    monkeypatch,
):
    from backend.app.ontology import loader as ontology_loader

    entity = SimpleNamespace(
        entity_id="MTR-PNL-001",
        name="正式PnL",
        unit="yuan",
        basis="formal",
        time_semantics="report_date",
        status="approved",
        authority=["docs/metric_dictionary.md#mtr-pnl-001"],
    )
    monkeypatch.setattr(
        ontology_loader,
        "load_ontology_index",
        lambda: SimpleNamespace(resolve_from_text=lambda _question: [entity]),
    )
    monkeypatch.setenv("MOSS_OBSIDIAN_VAULT_PATH", str(tmp_path))

    prompt = service._build_hermes_prompt(AgentQueryRequest(question="解释正式PnL"))

    assert "MOSS ontology context" in prompt
    assert "MTR-PNL-001" in prompt
    assert "- note:" not in prompt


def test_prompt_injects_entity_and_authority(monkeypatch):
    from backend.app.ontology import loader as ontology_loader
    from backend.app.services import knowledge_index_service

    entity = SimpleNamespace(
        entity_id="MTR-PNL-001",
        name="正式PnL",
        unit="yuan",
        basis="formal",
        time_semantics="report_date",
        status="approved",
        authority=["docs/metric_dictionary.md#mtr-pnl-001"],
    )
    monkeypatch.setattr(
        ontology_loader,
        "load_ontology_index",
        lambda: SimpleNamespace(resolve_from_text=lambda _question: [entity]),
    )
    monkeypatch.setattr(
        knowledge_index_service,
        "knowledge_summaries_for_entities",
        lambda _entity_ids: ["[MTR-PNL-001] note title: note summary (source: n.md, status: narrative)"],
    )
    _make_knowledge_vault_available(monkeypatch)

    prompt = service._build_hermes_prompt(AgentQueryRequest(question="解释正式PnL"))

    assert "MOSS ontology context" in prompt
    assert "MTR-PNL-001" in prompt
    assert "authority=docs/metric_dictionary.md#mtr-pnl-001" in prompt


def test_prompt_injects_note_summaries(monkeypatch):
    from backend.app.ontology import loader as ontology_loader
    from backend.app.services import knowledge_index_service

    entity = SimpleNamespace(
        entity_id="MTR-PNL-001",
        name="正式PnL",
        unit="yuan",
        basis="formal",
        time_semantics="report_date",
        status="approved",
        authority=["docs/metric_dictionary.md#mtr-pnl-001"],
    )
    monkeypatch.setattr(
        ontology_loader,
        "load_ontology_index",
        lambda: SimpleNamespace(resolve_from_text=lambda _question: [entity]),
    )
    monkeypatch.setattr(
        knowledge_index_service,
        "knowledge_summaries_for_entities",
        lambda _entity_ids: ["[MTR-PNL-001] note title: note summary (source: n.md, status: narrative)"],
    )
    _make_knowledge_vault_available(monkeypatch)

    prompt = service._build_hermes_prompt(AgentQueryRequest(question="解释正式PnL"))

    assert "- note: [MTR-PNL-001] note title: note summary" in prompt


def test_prompt_injects_entities_with_and_without_note_summaries(monkeypatch):
    from backend.app.ontology import loader as ontology_loader
    from backend.app.services import knowledge_index_service

    matched_entities = [
        SimpleNamespace(
            entity_id="MTR-PNL-001",
            name="正式PnL",
            unit="yuan",
            basis="formal",
            time_semantics="report_date",
            status="approved",
            authority=["docs/metric_dictionary.md#mtr-pnl-001"],
        ),
        SimpleNamespace(
            entity_id="MTR-PNL-002",
            name="公允价值变动",
            unit="yuan",
            basis="formal",
            time_semantics="report_date",
            status="approved",
            authority=["docs/metric_dictionary.md#mtr-pnl-002"],
        ),
    ]
    monkeypatch.setattr(
        ontology_loader,
        "load_ontology_index",
        lambda: SimpleNamespace(resolve_from_text=lambda _question: matched_entities),
    )
    monkeypatch.setattr(
        knowledge_index_service,
        "knowledge_summaries_for_entities",
        lambda _entity_ids: ["[MTR-PNL-001] note title: note summary"],
    )
    _make_knowledge_vault_available(monkeypatch)

    prompt = service._build_hermes_prompt(AgentQueryRequest(question="解释PnL"))

    assert "MTR-PNL-001" in prompt
    assert "authority=docs/metric_dictionary.md#mtr-pnl-001" in prompt
    assert "- note: [MTR-PNL-001] note title: note summary" in prompt
    assert "MTR-PNL-002" in prompt
    assert "authority=docs/metric_dictionary.md#mtr-pnl-002" in prompt


def test_prompt_applies_entity_cap_before_loading_summaries(monkeypatch):
    from backend.app.ontology import loader as ontology_loader
    from backend.app.services import knowledge_index_service

    matched_entities = [
        SimpleNamespace(
            entity_id=f"MTR-PNL-00{index}",
            name=f"metric {index}",
            unit="yuan",
            basis="formal",
            time_semantics="report_date",
            status="approved",
            authority=[f"docs/metric_dictionary.md#mtr-pnl-00{index}"],
        )
        for index in range(1, 5)
    ]
    monkeypatch.setattr(
        ontology_loader,
        "load_ontology_index",
        lambda: SimpleNamespace(resolve_from_text=lambda _question: matched_entities),
    )
    requested_entity_ids = []

    def _summaries(entity_ids):
        requested_entity_ids.extend(entity_ids)
        return ["[MTR-PNL-004] late note: summary"]

    monkeypatch.setattr(knowledge_index_service, "knowledge_summaries_for_entities", _summaries)
    _make_knowledge_vault_available(monkeypatch)

    prompt = service._build_hermes_prompt(AgentQueryRequest(question="解释PnL"))

    assert requested_entity_ids == ["MTR-PNL-001", "MTR-PNL-002", "MTR-PNL-003"]
    assert "MTR-PNL-001" in prompt
    assert "MTR-PNL-002" in prompt
    assert "MTR-PNL-003" in prompt
    assert "MTR-PNL-004" not in prompt


def test_prompt_block_respects_char_cap(monkeypatch):
    from backend.app.ontology import loader as ontology_loader
    from backend.app.services import knowledge_index_service

    entity = SimpleNamespace(
        entity_id="MTR-PNL-001",
        name="正" * 3000,
        unit="yuan",
        basis="formal",
        time_semantics="report_date",
        status="approved",
        authority=["docs/metric_dictionary.md#mtr-pnl-001"],
    )
    monkeypatch.setattr(
        ontology_loader,
        "load_ontology_index",
        lambda: SimpleNamespace(resolve_from_text=lambda _question: [entity]),
    )
    monkeypatch.setattr(
        knowledge_index_service,
        "knowledge_summaries_for_entities",
        lambda _entity_ids: ["[MTR-PNL-001] note title: note summary"],
    )
    _make_knowledge_vault_available(monkeypatch)

    block = service._build_ontology_context_block("正式PnL")

    assert len(block) <= service._ONTOLOGY_CONTEXT_MAX_CHARS


def test_prompt_block_char_cap_keeps_complete_lines(monkeypatch):
    first_line = "- MTR-PNL-001 | formal PnL | authority=docs/metric_dictionary.md#mtr-pnl-001"
    second_line = "- note: [MTR-PNL-001] " + ("summary " * 20)
    monkeypatch.setattr(service, "_ONTOLOGY_CONTEXT_MAX_CHARS", len(first_line))

    block = service._join_ontology_context_lines([first_line, second_line])

    assert block == first_line
    assert "\n" not in block
    assert "summary" not in block


def test_no_alias_hit_means_no_block():
    prompt = service._build_hermes_prompt(AgentQueryRequest(question="What is today's meeting agenda?"))

    assert "MOSS ontology context" not in prompt

def _reset_hermes_bridge_state():
    service._HERMES_BRIDGE_PROCESS = None
    service._HERMES_BRIDGE_CONFIG = None


def _bridge_kwargs(**overrides):
    base = {
        "command": "wsl.exe",
        "wsl_distro": "HermesUbuntu",
        "hermes_home": "/home/hermes/.hermes",
        "bridge_url": "http://127.0.0.1:7891",
        "model": "gpt-test",
        "toolsets": "evidence",
        "max_turns": 3,
        "timeout_seconds": 1.0,
    }
    base.update(overrides)
    return base


def test_ensure_hermes_bridge_reuses_healthy_managed_process_with_same_config(monkeypatch):
    _reset_hermes_bridge_state()
    managed = SimpleNamespace(poll=lambda: None, terminate=lambda: None, wait=lambda timeout=None: 0, kill=lambda: None)
    service._HERMES_BRIDGE_PROCESS = managed
    service._HERMES_BRIDGE_CONFIG = service.HermesBridgeConfig(
        command="wsl.exe",
        wsl_distro="HermesUbuntu",
        hermes_home="/home/hermes/.hermes",
        bridge_url="http://127.0.0.1:7891",
        model="gpt-test",
        toolsets="evidence",
        max_turns=3,
    )
    popen_calls = []

    monkeypatch.setattr(service, "_hermes_bridge_healthy", lambda _url: True)
    monkeypatch.setattr(service.subprocess, "Popen", lambda *args, **kwargs: popen_calls.append((args, kwargs)) or managed)

    service._ensure_hermes_bridge(**_bridge_kwargs())

    assert popen_calls == []
    assert service._HERMES_BRIDGE_PROCESS is managed


def test_ensure_hermes_bridge_restarts_managed_process_when_config_changes(monkeypatch):
    _reset_hermes_bridge_state()
    stops = []
    started = []

    old = SimpleNamespace(
        poll=lambda: None,
        terminate=lambda: stops.append("terminate"),
        wait=lambda timeout=None: 0,
        kill=lambda: None,
    )
    new = SimpleNamespace(poll=lambda: None, terminate=lambda: None, wait=lambda timeout=None: 0, kill=lambda: None)
    service._HERMES_BRIDGE_PROCESS = old
    service._HERMES_BRIDGE_CONFIG = service.HermesBridgeConfig(
        command="wsl.exe",
        wsl_distro="HermesUbuntu",
        hermes_home="/home/hermes/.hermes",
        bridge_url="http://127.0.0.1:7891",
        model="old-model",
        toolsets="evidence",
        max_turns=3,
    )

    health_state = {"healthy": False}

    def fake_healthy(_url):
        return health_state["healthy"]

    def fake_popen(*args, **kwargs):
        started.append(args)
        health_state["healthy"] = True
        return new

    monkeypatch.setattr(service, "_hermes_bridge_healthy", fake_healthy)
    monkeypatch.setattr(service.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(service, "_build_hermes_bridge_command", lambda **kwargs: ["hermes-bridge"])
    monkeypatch.setattr(service, "_build_hermes_subprocess_env", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        service,
        "_cleanup_wsl_processes",
        lambda **kwargs: stops.append(("wsl_cleanup", kwargs["pattern"])),
    )

    service._ensure_hermes_bridge(**_bridge_kwargs(model="new-model"))

    assert stops[0] == "terminate"
    assert ("wsl_cleanup", "hermes_bridge_server.py") in stops
    assert len(started) == 1
    assert service._HERMES_BRIDGE_PROCESS is new
    assert service._HERMES_BRIDGE_CONFIG.model == "new-model"


def test_ensure_hermes_bridge_does_not_kill_external_healthy_bridge(monkeypatch):
    _reset_hermes_bridge_state()
    popen_calls = []
    monkeypatch.setattr(service, "_hermes_bridge_healthy", lambda _url: True)
    monkeypatch.setattr(service.subprocess, "Popen", lambda *args, **kwargs: popen_calls.append(1) or SimpleNamespace(poll=lambda: None))

    service._ensure_hermes_bridge(**_bridge_kwargs())

    assert popen_calls == []
    assert service._HERMES_BRIDGE_PROCESS is None
    assert service._HERMES_BRIDGE_CONFIG is None


def test_ensure_hermes_bridge_refuses_external_bridge_that_rejects_our_token(monkeypatch):
    """A stale bridge would otherwise 403 every query while looking healthy."""
    _reset_hermes_bridge_state()
    popen_calls = []
    monkeypatch.setattr(service, "_hermes_bridge_healthy", lambda _url: True)
    monkeypatch.setattr(service, "_hermes_bridge_authorized", lambda _url: False)
    monkeypatch.setattr(
        service.subprocess,
        "Popen",
        lambda *args, **kwargs: popen_calls.append(1) or SimpleNamespace(poll=lambda: None),
    )

    with pytest.raises(RuntimeError, match="rejects this process's token"):
        service._ensure_hermes_bridge(**_bridge_kwargs())

    assert popen_calls == []


def test_ensure_hermes_bridge_accepts_external_bridge_without_token_support(monkeypatch):
    """A bridge predating token auth reports no verdict and still serves queries."""
    _reset_hermes_bridge_state()
    monkeypatch.setattr(service, "_hermes_bridge_healthy", lambda _url: True)
    monkeypatch.setattr(service, "_hermes_bridge_authorized", lambda _url: None)

    service._ensure_hermes_bridge(**_bridge_kwargs())

    assert service._HERMES_BRIDGE_PROCESS is None


def test_ensure_hermes_bridge_clears_config_when_managed_process_exits(monkeypatch):
    _reset_hermes_bridge_state()
    exited = SimpleNamespace(poll=lambda: 1, terminate=lambda: None, wait=lambda timeout=None: 0, kill=lambda: None)
    service._HERMES_BRIDGE_PROCESS = exited
    service._HERMES_BRIDGE_CONFIG = service.HermesBridgeConfig(
        command="wsl.exe",
        wsl_distro="HermesUbuntu",
        hermes_home="/home/hermes/.hermes",
        bridge_url="http://127.0.0.1:7891",
        model="gpt-test",
        toolsets="evidence",
        max_turns=3,
    )
    monkeypatch.setattr(service, "_hermes_bridge_healthy", lambda _url: True)

    service._ensure_hermes_bridge(**_bridge_kwargs())

    assert service._HERMES_BRIDGE_PROCESS is None
    assert service._HERMES_BRIDGE_CONFIG is None


def _hermes_settings(**overrides):
    base = {
        "agent_hermes_command": "hermes",
        "agent_hermes_wsl_distro": "",
        "agent_hermes_home": "",
        "agent_hermes_transport": "cli",
        "agent_hermes_bridge_url": "http://127.0.0.1:7891",
        "agent_hermes_model": "gpt-test",
        "agent_hermes_toolsets": "file",
        "agent_hermes_max_turns": 3,
        "agent_hermes_timeout_seconds": 9.0,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_execute_hermes_agent_query_falls_back_when_cli_spawn_raises_os_error(monkeypatch, tmp_path):
    def fake_run(*_args, **_kwargs):
        raise PermissionError("wsl.exe access denied")

    monkeypatch.setattr(service.subprocess, "run", fake_run)
    monkeypatch.setattr(service, "_append_hermes_audit", lambda *_args, **_kwargs: None)

    envelope = service.execute_hermes_agent_query(
        request=AgentQueryRequest(question="summarize this open ended question"),
        governance_dir=str(tmp_path / "governance"),
        settings=_hermes_settings(),
    )

    assert envelope.result_meta.result_kind == "agent.hermes_fallback"
    assert envelope.result_meta.vendor_status == "vendor_unavailable"
    assert envelope.evidence.filters_applied["fallback_reason"] == "hermes_runtime_unavailable"


def test_execute_hermes_agent_query_falls_back_when_runtime_raises_json_decode_error(
    monkeypatch,
    tmp_path,
):
    def fake_run_hermes_agent(**_kwargs):
        raise json.JSONDecodeError("Expecting value", "not-json", 0)

    monkeypatch.setattr(service, "run_hermes_agent", fake_run_hermes_agent)
    monkeypatch.setattr(service, "_append_hermes_audit", lambda *_args, **_kwargs: None)

    envelope = service.execute_hermes_agent_query(
        request=AgentQueryRequest(question="summarize this open ended question"),
        governance_dir=str(tmp_path / "governance"),
        settings=_hermes_settings(),
    )

    assert envelope.result_meta.result_kind == "agent.hermes_fallback"
    assert envelope.evidence.filters_applied["fallback_reason"] == "hermes_runtime_unavailable"


class _FakeBridgeResponse:
    def __init__(self, body: bytes):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *_exc_info):
        return False

    def read(self) -> bytes:
        return self._body


def test_post_hermes_bridge_query_converts_invalid_json_to_runtime_error(monkeypatch):
    monkeypatch.setattr(
        service.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: _FakeBridgeResponse(b"<html>bad gateway</html>"),
    )

    with pytest.raises(RuntimeError, match="invalid JSON"):
        service._post_hermes_bridge_query(
            bridge_url="http://127.0.0.1:7891",
            prompt="ping",
            model="",
            toolsets="evidence",
            max_turns=1,
            timeout_seconds=1.0,
        )


def test_post_hermes_bridge_query_tolerates_invalid_utf8_payload(monkeypatch):
    body = b'{"ok": true, "answer": "p\xffng", "model": "m", "toolsets": "evidence"}'
    monkeypatch.setattr(
        service.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: _FakeBridgeResponse(body),
    )

    result = service._post_hermes_bridge_query(
        bridge_url="http://127.0.0.1:7891",
        prompt="ping",
        model="",
        toolsets="evidence",
        max_turns=1,
        timeout_seconds=1.0,
    )

    assert result["answer"] == "p\ufffdng"
    assert result["transport"] == "bridge"


def test_ensure_hermes_bridge_converts_spawn_os_error_to_runtime_error(monkeypatch, tmp_path):
    _reset_hermes_bridge_state()
    monkeypatch.setattr(service, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(service, "_hermes_bridge_healthy", lambda _url: False)
    monkeypatch.setattr(service, "_build_hermes_bridge_command", lambda **_kwargs: ["missing-bridge"])
    monkeypatch.setattr(service, "_build_hermes_subprocess_env", lambda *_args, **_kwargs: {})

    def fake_popen(*_args, **_kwargs):
        raise FileNotFoundError("missing-bridge")

    monkeypatch.setattr(service.subprocess, "Popen", fake_popen)

    with pytest.raises(RuntimeError, match="failed to start"):
        service._ensure_hermes_bridge(**_bridge_kwargs())

    assert service._HERMES_BRIDGE_PROCESS is None
    assert service._HERMES_BRIDGE_CONFIG is None


def test_stop_managed_hermes_bridge_survives_kill_timeout():
    _reset_hermes_bridge_state()
    calls = []

    def fake_wait(timeout=None):
        calls.append(("wait", timeout))
        raise service.subprocess.TimeoutExpired(cmd="bridge", timeout=timeout or 0)

    stubborn = SimpleNamespace(
        poll=lambda: None,
        terminate=lambda: calls.append("terminate"),
        kill=lambda: calls.append("kill"),
        wait=fake_wait,
    )
    service._HERMES_BRIDGE_PROCESS = stubborn

    service._stop_managed_hermes_bridge_locked()

    assert "terminate" in calls
    assert "kill" in calls
    assert service._HERMES_BRIDGE_PROCESS is None
    assert service._HERMES_BRIDGE_CONFIG is None


def test_execute_hermes_agent_query_returns_envelope_when_audit_write_fails(
    monkeypatch,
    tmp_path,
    caplog,
):
    def fake_append_agent_audit(*_args, **_kwargs):
        raise OSError("governance dir is read-only")

    monkeypatch.setattr(service, "append_agent_audit", fake_append_agent_audit)

    envelope = service.execute_hermes_agent_query(
        request=AgentQueryRequest(question="在吗"),
        governance_dir=str(tmp_path / "governance"),
        settings=_hermes_settings(),
    )

    assert envelope.result_meta.result_kind == "agent.local_chat"
    assert envelope.answer == "在，有什么可以帮你？"
    assert "error_code=hermes_audit_append_failed" in caplog.text
    assert "read-only" not in caplog.text


def test_build_agent_subprocess_env_strips_pat_cookie_session_and_passfile_names(monkeypatch):
    monkeypatch.setenv("GITHUB_PAT", "ghp_secret")
    monkeypatch.setenv("GH_PAT", "ghp_secret_2")
    monkeypatch.setenv("PGPASSFILE", "/home/user/.pgpass")
    monkeypatch.setenv("BROWSER_COOKIE_JAR", "cookie-value")
    monkeypatch.setenv("APP_SESSION_ID", "session-value")
    monkeypatch.setenv("CARGO_TARGET_PATH", "/tmp/cargo-target")

    env = build_agent_subprocess_env()

    for blocked in ("GITHUB_PAT", "GH_PAT", "PGPASSFILE", "BROWSER_COOKIE_JAR", "APP_SESSION_ID"):
        assert blocked not in env
    assert env["CARGO_TARGET_PATH"] == "/tmp/cargo-target"


def test_build_agent_subprocess_env_strips_values_with_embedded_url_credentials(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://svc:sekret@db.internal:5432/moss")
    monkeypatch.setenv("REDIS_URL", "redis://:cache-pass@cache.internal:6379/0")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy-user:proxy-pass@proxy.internal:8080")
    monkeypatch.setenv("SERVICE_BASE_URL", "https://api.example.com:8443/v1")

    env = build_agent_subprocess_env()

    for blocked in ("DATABASE_URL", "REDIS_URL", "HTTPS_PROXY"):
        assert blocked not in env
    assert env["SERVICE_BASE_URL"] == "https://api.example.com:8443/v1"


def test_run_hermes_agent_cli_env_excludes_sensitive_variables(monkeypatch):
    monkeypatch.setenv("GITHUB_PAT", "ghp_secret")
    monkeypatch.setenv("DATABASE_URL", "postgres://svc:sekret@db.internal:5432/moss")
    calls = []

    def fake_run(args, **kwargs):
        calls.append({"args": args, **kwargs})
        return SimpleNamespace(returncode=0, stdout="pong\n", stderr="")

    monkeypatch.setattr(service.subprocess, "run", fake_run)

    service.run_hermes_agent(
        request=AgentQueryRequest(question="ping"),
        command="hermes",
        wsl_distro="",
        hermes_home="",
        model="",
        toolsets="evidence",
        max_turns=1,
        timeout_seconds=5,
    )

    env = calls[0]["env"]
    assert "GITHUB_PAT" not in env
    assert "DATABASE_URL" not in env
    assert not [name for name in env if is_sensitive_env_name(name)]


def test_stop_managed_hermes_bridge_is_idempotent_without_managed_process():
    _reset_hermes_bridge_state()

    service.stop_managed_hermes_bridge()
    service.stop_managed_hermes_bridge()

    assert service._HERMES_BRIDGE_PROCESS is None
    assert service._HERMES_BRIDGE_CONFIG is None


def test_stop_managed_hermes_bridge_terminates_managed_process_then_ensure_restarts(
    monkeypatch,
    tmp_path,
):
    _reset_hermes_bridge_state()
    calls = []
    managed = SimpleNamespace(
        poll=lambda: None,
        terminate=lambda: calls.append("terminate"),
        wait=lambda timeout=None: calls.append(("wait", timeout)) or 0,
        kill=lambda: calls.append("kill"),
    )
    service._HERMES_BRIDGE_PROCESS = managed
    service._HERMES_BRIDGE_CONFIG = service.HermesBridgeConfig(
        command="wsl.exe",
        wsl_distro="HermesUbuntu",
        hermes_home="/home/hermes/.hermes",
        bridge_url="http://127.0.0.1:7891",
        model="gpt-test",
        toolsets="evidence",
        max_turns=3,
    )
    monkeypatch.setattr(
        service,
        "_cleanup_wsl_processes",
        lambda **kwargs: calls.append(("wsl_cleanup", kwargs["pattern"])),
    )

    service.stop_managed_hermes_bridge()

    assert "terminate" in calls
    assert service._HERMES_BRIDGE_PROCESS is None
    assert service._HERMES_BRIDGE_CONFIG is None

    restarted = SimpleNamespace(
        poll=lambda: None,
        terminate=lambda: None,
        wait=lambda timeout=None: 0,
        kill=lambda: None,
    )
    health_state = {"healthy": False}

    def fake_popen(*_args, **_kwargs):
        health_state["healthy"] = True
        return restarted

    monkeypatch.setattr(service, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(service, "_hermes_bridge_healthy", lambda _url: health_state["healthy"])
    monkeypatch.setattr(service, "_build_hermes_bridge_command", lambda **_kwargs: ["hermes-bridge"])
    monkeypatch.setattr(service, "_build_hermes_subprocess_env", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(service.subprocess, "Popen", fake_popen)

    service._ensure_hermes_bridge(**_bridge_kwargs())

    assert service._HERMES_BRIDGE_PROCESS is restarted
    assert service._HERMES_BRIDGE_CONFIG is not None


def test_stop_managed_hermes_bridge_never_touches_external_bridge(monkeypatch):
    _reset_hermes_bridge_state()
    popen_calls = []
    monkeypatch.setattr(service, "_hermes_bridge_healthy", lambda _url: True)
    monkeypatch.setattr(
        service.subprocess,
        "Popen",
        lambda *args, **kwargs: popen_calls.append(1) or SimpleNamespace(poll=lambda: None),
    )

    # ensure 采认外部健康 bridge 但不接管；随后 stop 不应有任何进程可终止。
    service._ensure_hermes_bridge(**_bridge_kwargs())
    service.stop_managed_hermes_bridge()

    assert popen_calls == []
    assert service._HERMES_BRIDGE_PROCESS is None
    assert service._HERMES_BRIDGE_CONFIG is None


# ---------------------------------------------------------------------------
# B3 审计修复回归：WSL 穿透清理 / 错误分类 / extract 统一 / 凭据正则 /
# token 传递 / 超时联动 / 审计通道 / 请求上限 / open-chat 收紧
# ---------------------------------------------------------------------------


def _load_bridge_module():
    from tests.helpers import load_module

    return load_module("hermes_bridge_server", "scripts/hermes_bridge_server.py")


def test_stop_managed_hermes_bridge_kills_wsl_resident_bridge_process(monkeypatch):
    _reset_hermes_bridge_state()
    run_calls = []
    monkeypatch.setattr(
        service.subprocess,
        "run",
        lambda args, **kwargs: run_calls.append({"args": args, **kwargs})
        or SimpleNamespace(returncode=0, stdout="", stderr=""),
    )
    service._HERMES_BRIDGE_PROCESS = SimpleNamespace(
        poll=lambda: None,
        terminate=lambda: None,
        wait=lambda timeout=None: 0,
        kill=lambda: None,
    )
    service._HERMES_BRIDGE_CONFIG = service.HermesBridgeConfig(
        command="wsl.exe",
        wsl_distro="HermesUbuntu",
        hermes_home="/home/hermes/.hermes",
        bridge_url="http://127.0.0.1:7891",
        model="gpt-test",
        toolsets="evidence",
        max_turns=3,
    )

    service.stop_managed_hermes_bridge()

    assert len(run_calls) == 1
    assert run_calls[0]["args"] == [
        "wsl.exe",
        "-d",
        "HermesUbuntu",
        "--exec",
        "pkill",
        "-f",
        "hermes_bridge_server.py",
    ]
    assert service._HERMES_BRIDGE_PROCESS is None
    assert service._HERMES_BRIDGE_CONFIG is None


def test_stop_managed_hermes_bridge_runs_wsl_cleanup_even_when_kill_times_out(monkeypatch):
    _reset_hermes_bridge_state()
    run_calls = []
    monkeypatch.setattr(
        service.subprocess,
        "run",
        lambda args, **kwargs: run_calls.append(list(args))
        or SimpleNamespace(returncode=0, stdout="", stderr=""),
    )

    def fake_wait(timeout=None):
        raise service.subprocess.TimeoutExpired(cmd="bridge", timeout=timeout or 0)

    service._HERMES_BRIDGE_PROCESS = SimpleNamespace(
        poll=lambda: None,
        terminate=lambda: None,
        kill=lambda: None,
        wait=fake_wait,
    )
    service._HERMES_BRIDGE_CONFIG = service.HermesBridgeConfig(
        command="wsl.exe",
        wsl_distro="HermesUbuntu",
        hermes_home="/home/hermes/.hermes",
        bridge_url="http://127.0.0.1:7891",
        model="gpt-test",
        toolsets="evidence",
        max_turns=3,
    )

    service.stop_managed_hermes_bridge()

    assert run_calls and run_calls[0][-1] == "hermes_bridge_server.py"


def test_cleanup_wsl_processes_is_noop_for_non_wsl_command(monkeypatch):
    monkeypatch.setattr(
        service.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("non-wsl command must not spawn cleanup")
        ),
    )

    service._cleanup_wsl_processes(command="hermes", wsl_distro="", pattern="x")


def test_cleanup_wsl_processes_failure_is_logged_not_raised(monkeypatch, caplog):
    def fake_run(*_args, **_kwargs):
        raise service.subprocess.TimeoutExpired(cmd="wsl.exe", timeout=15.0)

    monkeypatch.setattr(service.subprocess, "run", fake_run)

    service._cleanup_wsl_processes(
        command="wsl.exe", wsl_distro="HermesUbuntu", pattern="hermes_bridge_server.py"
    )

    assert "error_code=hermes_wsl_cleanup_failed" in caplog.text


def test_run_hermes_agent_cli_timeout_kills_wsl_resident_hermes_and_classifies(monkeypatch):
    calls = []

    def fake_run(args, **kwargs):
        calls.append({"args": list(args), **kwargs})
        if len(calls) == 1:
            raise service.subprocess.TimeoutExpired(cmd=args, timeout=kwargs.get("timeout") or 0)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(service.subprocess, "run", fake_run)

    with pytest.raises(service.HermesRuntimeError, match="timed out") as excinfo:
        service.run_hermes_agent(
            request=AgentQueryRequest(question="ping"),
            command="wsl.exe",
            wsl_distro="HermesUbuntu",
            hermes_home="/home/hermes/.hermes-moss",
            model="",
            toolsets="evidence",
            max_turns=1,
            timeout_seconds=5,
        )

    assert excinfo.value.error_code == "hermes_timeout"
    assert len(calls) == 2
    assert calls[1]["args"] == [
        "wsl.exe",
        "-d",
        "HermesUbuntu",
        "--exec",
        "pkill",
        "-f",
        "/usr/local/bin/hermes chat -Q",
    ]


def test_run_hermes_agent_cli_timeout_skips_cleanup_for_non_wsl_command(monkeypatch):
    calls = []

    def fake_run(args, **kwargs):
        calls.append(list(args))
        raise service.subprocess.TimeoutExpired(cmd=args, timeout=kwargs.get("timeout") or 0)

    monkeypatch.setattr(service.subprocess, "run", fake_run)

    with pytest.raises(service.HermesRuntimeError) as excinfo:
        service.run_hermes_agent(
            request=AgentQueryRequest(question="ping"),
            command="hermes",
            wsl_distro="",
            hermes_home="",
            model="",
            toolsets="evidence",
            max_turns=1,
            timeout_seconds=5,
        )

    assert excinfo.value.error_code == "hermes_timeout"
    assert len(calls) == 1


def test_ensure_hermes_bridge_token_mismatch_uses_distinct_error_code(monkeypatch):
    _reset_hermes_bridge_state()
    monkeypatch.setattr(service, "_hermes_bridge_healthy", lambda _url: True)
    monkeypatch.setattr(service, "_hermes_bridge_authorized", lambda _url: False)

    with pytest.raises(service.HermesRuntimeError) as excinfo:
        service._ensure_hermes_bridge(**_bridge_kwargs())

    assert excinfo.value.error_code == "hermes_bridge_unauthorized"


@pytest.mark.parametrize(
    ("error_code", "expected_log_code"),
    [
        ("hermes_timeout", "hermes_timeout"),
        ("hermes_spawn_failed", "hermes_spawn_failed"),
        ("hermes_exit_failed", "hermes_exit_failed"),
        ("hermes_bridge_unauthorized", "hermes_bridge_unauthorized"),
        (None, "hermes_runtime_unavailable"),
    ],
)
def test_execute_hermes_agent_query_logs_classified_error_codes(
    error_code,
    expected_log_code,
    monkeypatch,
    tmp_path,
    caplog,
):
    def fake_run_hermes_agent(**_kwargs):
        if error_code is None:
            raise RuntimeError("plain failure with secret-detail-marker")
        raise service.HermesRuntimeError(
            "classified failure with secret-detail-marker", error_code=error_code
        )

    monkeypatch.setattr(service, "run_hermes_agent", fake_run_hermes_agent)
    monkeypatch.setattr(service, "_append_hermes_audit", lambda *_args, **_kwargs: None)

    envelope = service.execute_hermes_agent_query(
        request=AgentQueryRequest(question="summarize this open ended question"),
        governance_dir=str(tmp_path / "governance"),
        settings=_hermes_settings(),
    )

    assert f"error_code={expected_log_code}" in caplog.text
    assert "secret-detail-marker" not in caplog.text
    assert "detail=" not in caplog.text
    # 对外 envelope 契约保持粗粒度 fallback_reason 不变。
    assert envelope.evidence.filters_applied["fallback_reason"] == "hermes_runtime_unavailable"
    assert envelope.result_meta.result_kind == "agent.hermes_fallback"


def test_hermes_fallback_audit_carries_error_code_and_actual_channel(monkeypatch, tmp_path):
    def fake_run_hermes_agent(**_kwargs):
        raise service.HermesRuntimeError(
            "bridge probe with secret-detail-marker", error_code="hermes_timeout"
        )

    monkeypatch.setattr(service, "run_hermes_agent", fake_run_hermes_agent)

    envelope = service.execute_hermes_agent_query(
        request=AgentQueryRequest(
            question="summarize this open ended question",
            context={"user_id": "u_audit"},
        ),
        governance_dir=str(tmp_path / "governance"),
        settings=_hermes_settings(),
    )

    payload = json.loads(
        (tmp_path / "governance" / "agent_audit.jsonl").read_text(encoding="utf-8").splitlines()[-1]
    )
    assert payload["tools_used"] == ["hermes_local_fallback"]
    assert payload["result_meta"]["error_code"] == "hermes_timeout"
    assert "secret-detail-marker" not in json.dumps(payload, ensure_ascii=False)
    assert envelope.result_meta.result_kind == "agent.hermes_fallback"


def test_local_open_chat_audit_records_local_channel(tmp_path):
    service.execute_hermes_agent_query(
        request=AgentQueryRequest(question="在吗", context={"user_id": "u_chat"}),
        governance_dir=str(tmp_path / "governance"),
        settings=_hermes_settings(),
    )

    payload = json.loads(
        (tmp_path / "governance" / "agent_audit.jsonl").read_text(encoding="utf-8").splitlines()[-1]
    )
    assert payload["tools_used"] == ["local_open_chat"]
    assert "error_code" not in payload["result_meta"]


def test_hermes_audit_tools_used_reflects_actual_channel():
    assert service._hermes_audit_tools_used(
        {"command": "local_open_chat", "transport": "sync"}
    ) == ["local_open_chat"]
    assert service._hermes_audit_tools_used(
        {"command": "hermes_bridge", "transport": "bridge"}
    ) == ["hermes_bridge"]
    assert service._hermes_audit_tools_used(
        {"command": "hermes", "transport": "cli"}
    ) == ["hermes_cli"]
    assert service._hermes_audit_tools_used(
        {"command": "wsl.exe", "transport": "bridge", "error_code": "hermes_timeout"}
    ) == ["hermes_local_fallback"]


def test_extract_final_answer_truncates_session_trailer_and_skips_banners():
    stdout = (
        "Warning: Unknown toolsets: evidence, query, research\n"
        "session_id: 20260814_000000_abc\n"
        "Real answer line 1\n"
        "\n"
        "Real answer line 2\n"
        "Resume this session with: hermes chat --resume abc\n"
        "Session: abc\n"
        "Duration: 12s\n"
        "Messages: 4\n"
    )

    assert service._extract_final_answer(stdout) == "Real answer line 1\n\nReal answer line 2"


def test_extract_final_answer_returns_empty_for_banner_only_stdout():
    stdout = (
        "Secure MCP Filesystem Server running on stdio\n"
        "session_id: 20260814_000000_abc\n"
        "Session: abc\n"
        "Duration: 1s\n"
    )
    bridge_module = _load_bridge_module()

    assert service._extract_final_answer(stdout) == ""
    # bridge 版收紧后不再 `or stdout.strip()` 回退原始 banner。
    assert bridge_module._extract_final_answer(stdout) == ""


def test_extract_final_answer_implementations_are_verbatim_identical():
    import inspect

    bridge_module = _load_bridge_module()

    assert inspect.getsource(bridge_module._extract_final_answer) == inspect.getsource(
        service._extract_final_answer
    )


def test_embedded_credential_value_pattern_catches_slash_password():
    from backend.app.agent.runtime.subprocess_env import is_sensitive_env_value

    bridge_module = _load_bridge_module()

    for value in (
        "postgresql://user:pa/ss@host/db",
        "postgres://svc:sekret@db.internal:5432/moss",
        "redis://:cache-pass@cache.internal:6379/0",
        "https://user:multi-at-password@segment@provider.example/query",
    ):
        assert is_sensitive_env_value(value) is True, value
        assert bridge_module._is_sensitive_env_value(value) is True, value

    for value in (
        "https://api.example.com:8443/v1",
        "https://api.example.com/v1?q=a:b",
        "plain text without url",
    ):
        assert is_sensitive_env_value(value) is False, value
        assert bridge_module._is_sensitive_env_value(value) is False, value


def test_embedded_credential_value_patterns_stay_in_sync():
    from backend.app.agent.runtime import subprocess_env

    bridge_module = _load_bridge_module()

    assert (
        bridge_module._EMBEDDED_CREDENTIAL_VALUE_PATTERN.pattern
        == subprocess_env._EMBEDDED_CREDENTIAL_VALUE_PATTERN.pattern
    )


def test_build_agent_subprocess_env_strips_slash_password_dsn(monkeypatch):
    monkeypatch.setenv("PG_MAIN_URL", "postgresql://user:pa/ss@host/db")

    env = build_agent_subprocess_env()

    assert "PG_MAIN_URL" not in env


def test_build_hermes_bridge_command_keeps_token_off_wsl_command_line():
    args = service._build_hermes_bridge_command(
        command="wsl.exe",
        wsl_distro="HermesUbuntu",
        hermes_home="/home/hermes/.hermes-moss",
        bridge_url="http://127.0.0.1:7891",
        model="",
        toolsets="evidence",
        max_turns=4,
    )

    joined = " ".join(args)
    assert service._PROCESS_BRIDGE_TOKEN not in joined
    assert "HERMES_BRIDGE_TOKEN" not in joined


def test_build_hermes_subprocess_env_forwards_token_via_wslenv(monkeypatch):
    monkeypatch.delenv("WSLENV", raising=False)

    env = service._build_hermes_subprocess_env("/home/hermes/.hermes")

    assert env["HERMES_BRIDGE_TOKEN"] == service._PROCESS_BRIDGE_TOKEN
    assert "HERMES_BRIDGE_TOKEN/u" in env["WSLENV"].split(":")


def test_build_hermes_subprocess_env_preserves_existing_wslenv_entries(monkeypatch):
    monkeypatch.setenv("WSLENV", "WT_SESSION/u:FOO/p")

    env = service._build_hermes_subprocess_env("")

    entries = env["WSLENV"].split(":")
    assert "WT_SESSION/u" in entries
    assert "FOO/p" in entries
    assert entries.count("HERMES_BRIDGE_TOKEN/u") == 1


def test_post_hermes_bridge_query_passes_caller_timeout_budget(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout=None):
        captured["timeout"] = timeout
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _FakeBridgeResponse(
            b'{"ok": true, "answer": "pong", "model": "m", "toolsets": "evidence"}'
        )

    monkeypatch.setattr(service.urllib.request, "urlopen", fake_urlopen)

    result = service._post_hermes_bridge_query(
        bridge_url="http://127.0.0.1:7891",
        prompt="ping",
        model="",
        toolsets="evidence",
        max_turns=20,
        timeout_seconds=180.0,
    )

    assert result["answer"] == "pong"
    assert captured["timeout"] == 180.0
    assert captured["body"]["timeout_seconds"] == 180.0


def test_post_hermes_bridge_query_raises_on_empty_answer(monkeypatch):
    monkeypatch.setattr(
        service.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: _FakeBridgeResponse(
            b'{"ok": true, "answer": "", "model": "m", "toolsets": "evidence"}'
        ),
    )

    with pytest.raises(RuntimeError, match="no answer"):
        service._post_hermes_bridge_query(
            bridge_url="http://127.0.0.1:7891",
            prompt="ping",
            model="",
            toolsets="evidence",
            max_turns=1,
            timeout_seconds=1.0,
        )


def test_post_hermes_bridge_query_classifies_403_as_bridge_unauthorized(monkeypatch):
    import io

    def fake_urlopen(*_args, **_kwargs):
        raise service.urllib.error.HTTPError(
            url="http://127.0.0.1:7891/query",
            code=403,
            msg="Forbidden",
            hdrs=None,
            fp=io.BytesIO(b'{"ok": false, "error": "invalid bridge token"}'),
        )

    monkeypatch.setattr(service.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(service.HermesRuntimeError) as excinfo:
        service._post_hermes_bridge_query(
            bridge_url="http://127.0.0.1:7891",
            prompt="ping",
            model="",
            toolsets="evidence",
            max_turns=1,
            timeout_seconds=1.0,
        )

    assert excinfo.value.error_code == "hermes_bridge_unauthorized"


def test_post_hermes_bridge_query_classifies_socket_timeout(monkeypatch):
    def fake_urlopen(*_args, **_kwargs):
        raise TimeoutError("timed out")

    monkeypatch.setattr(service.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(service.HermesRuntimeError) as excinfo:
        service._post_hermes_bridge_query(
            bridge_url="http://127.0.0.1:7891",
            prompt="ping",
            model="",
            toolsets="evidence",
            max_turns=1,
            timeout_seconds=2.0,
        )

    assert excinfo.value.error_code == "hermes_timeout"


def test_bridge_query_uses_min_of_own_cap_and_caller_budget(monkeypatch):
    bridge_module = _load_bridge_module()
    captured = []

    def fake_run(args, **kwargs):
        captured.append(kwargs)
        return SimpleNamespace(returncode=0, stdout="pong\n", stderr="")

    monkeypatch.setattr(bridge_module.subprocess, "run", fake_run)
    bridge = bridge_module.HermesBridge(
        model="", toolsets="evidence", max_turns=20, hermes_root="/tmp"
    )

    result = bridge.query(
        "ping", model="", toolsets="evidence", max_turns=20, timeout_seconds=180.0
    )
    assert result["ok"] is True
    # min(20*15=300, 180-5=175)：赶在调用方 urlopen 超时前结束子进程。
    assert captured[0]["timeout"] == 175.0

    bridge.query("ping", model="", toolsets="evidence", max_turns=20, timeout_seconds=0.0)
    # 未透传预算的旧调用方保持自身上限。
    assert captured[1]["timeout"] == 300.0

    bridge.query("ping", model="", toolsets="evidence", max_turns=1, timeout_seconds=600.0)
    # 自身上限小于调用方预算时不放大。
    assert captured[2]["timeout"] == 30.0


def test_bridge_do_post_forwards_timeout_budget_to_query():
    import io

    bridge_module = _load_bridge_module()
    recorded = {}

    class BridgeStub:
        def query(self, prompt, *, model, toolsets, max_turns, timeout_seconds=0.0):
            recorded.update(
                prompt=prompt,
                max_turns=max_turns,
                timeout_seconds=timeout_seconds,
            )
            return {"ok": True, "answer": "pong", "model": "m", "toolsets": "evidence"}

    handler_cls = bridge_module.make_handler(BridgeStub(), "tok")
    handler = object.__new__(handler_cls)
    body = json.dumps({"prompt": "ping", "max_turns": 20, "timeout_seconds": 180.0}).encode("utf-8")
    handler.headers = {
        "Content-Length": str(len(body)),
        bridge_module.TOKEN_HEADER: "tok",
        "Host": "127.0.0.1:7891",
    }
    handler.rfile = io.BytesIO(body)
    handler.client_address = ("127.0.0.1", 50321)
    handler.path = "/query"
    responses = []
    handler._send_json = lambda status, payload: responses.append((status, payload))

    handler.do_POST()

    assert responses and responses[0][0] == 200
    assert recorded["timeout_seconds"] == 180.0
    assert recorded["max_turns"] == 20


def test_agent_query_request_enforces_question_max_length():
    from pydantic import ValidationError

    assert AgentQueryRequest(question="q" * 8000).question == "q" * 8000
    with pytest.raises(ValidationError):
        AgentQueryRequest(question="q" * 8001)


def test_build_hermes_prompt_truncates_oversized_page_context(monkeypatch):
    monkeypatch.setattr(service, "_build_ontology_context_block", lambda _question: "")
    request = AgentQueryRequest(
        question="解释当前页面",
        page_context={
            "page_id": "reconciliation",
            "selected_rows": [
                {"instrument_id": f"BOND-{index}", "note": "x" * 40} for index in range(400)
            ],
        },
    )

    prompt = service._build_hermes_prompt(request)

    context_part = prompt.split("MOSS request context:\n", 1)[1]
    assert len(context_part) <= service._PROMPT_CONTEXT_MAX_CHARS + len(
        service._PROMPT_CONTEXT_TRUNCATION_NOTE
    )
    assert "request context truncated" in prompt
    assert "解释当前页面" in prompt


def test_build_hermes_prompt_keeps_small_context_untruncated(monkeypatch):
    monkeypatch.setattr(service, "_build_ontology_context_block", lambda _question: "")
    request = AgentQueryRequest(
        question="formal PnL",
        filters={"report_date": "2026-06-30"},
    )

    prompt = service._build_hermes_prompt(request)

    assert "request context truncated" not in prompt


@pytest.mark.parametrize(
    "question",
    [
        "wechat integration status",
        "chatham house summary",
        "how do i user data export",
    ],
)
def test_open_chat_short_circuit_ignores_embedded_chat_substrings(question):
    assert service._should_answer_open_chat_locally(question) is False


@pytest.mark.parametrize(
    "question",
    [
        "chat",
        "can we chat",
        "Chat?",
        "how do i use this app",
    ],
)
def test_open_chat_short_circuit_keeps_whole_word_chat_prompts(question):
    assert service._should_answer_open_chat_locally(question) is True


def test_open_chat_misfire_questions_stay_on_hermes_path(monkeypatch, tmp_path):
    run_calls = []

    def fake_run_hermes_agent(**kwargs):
        run_calls.append(kwargs)
        return {
            "answer": "hermes handled",
            "stdout": "hermes handled",
            "stderr": "",
            "command": "hermes",
            "model": "gpt-test",
            "toolsets": "evidence,query,research",
            "transport": "cli",
        }

    monkeypatch.setattr(service, "run_hermes_agent", fake_run_hermes_agent)
    monkeypatch.setattr(service, "_append_hermes_audit", lambda *_args, **_kwargs: None)

    envelope = service.execute_hermes_agent_query(
        request=AgentQueryRequest(question="wechat integration status"),
        governance_dir=str(tmp_path / "governance"),
        settings=_hermes_settings(),
    )

    assert run_calls
    assert envelope.result_meta.result_kind == "agent.hermes"
