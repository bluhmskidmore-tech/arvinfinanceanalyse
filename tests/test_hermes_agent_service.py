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


class _FakeBridgeProcess:
    def __init__(self, *, poll_result=None):
        self.poll_result = poll_result
        self.events = []

    def poll(self):
        return self.poll_result

    def terminate(self):
        self.events.append("terminate")

    def wait(self, timeout):
        self.events.append(("wait", timeout))
        return self.poll_result

    def kill(self):
        self.events.append("kill")


def _bridge_config(**overrides):
    values = {
        "command": "wsl.exe",
        "wsl_distro": "HermesUbuntu",
        "hermes_home": "/home/hermes/.hermes-moss",
        "bridge_url": "http://127.0.0.1:7891",
        "model": "gpt-test",
        "toolsets": "evidence,query,research",
        "max_turns": 20,
    }
    values.update(overrides)
    return service.HermesBridgeConfig(**values)


def _ensure_bridge(config):
    service._ensure_hermes_bridge(
        command=config.command,
        wsl_distro=config.wsl_distro,
        hermes_home=config.hermes_home,
        bridge_url=config.bridge_url,
        model=config.model,
        toolsets=config.toolsets,
        max_turns=config.max_turns,
        timeout_seconds=1.0,
    )


def test_ensure_hermes_bridge_reuses_healthy_managed_process_with_same_config(monkeypatch):
    config = _bridge_config()
    process = _FakeBridgeProcess()
    monkeypatch.setattr(service, "_HERMES_BRIDGE_PROCESS", process)
    monkeypatch.setattr(service, "_HERMES_BRIDGE_CONFIG", config)
    monkeypatch.setattr(service, "_hermes_bridge_healthy", lambda _url: True)
    monkeypatch.setattr(
        service.subprocess,
        "Popen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("managed bridge should be reused")
        ),
    )

    _ensure_bridge(config)

    assert process.events == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("bridge_url", "http://127.0.0.1:7999"),
        ("model", "gpt-next"),
        ("toolsets", "evidence"),
        ("max_turns", 30),
    ],
)
def test_ensure_hermes_bridge_restarts_managed_process_when_config_changes(
    field,
    value,
    monkeypatch,
    tmp_path,
):
    previous_config = _bridge_config()
    next_config = _bridge_config(**{field: value})
    previous_process = _FakeBridgeProcess()
    next_process = _FakeBridgeProcess()
    popen_calls = []

    def fake_popen(args, **kwargs):
        popen_calls.append((args, kwargs))
        return next_process

    monkeypatch.setattr(service, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(service, "_HERMES_BRIDGE_PROCESS", previous_process)
    monkeypatch.setattr(service, "_HERMES_BRIDGE_CONFIG", previous_config)
    monkeypatch.setattr(service, "_hermes_bridge_healthy", lambda _url: True)
    monkeypatch.setattr(service.subprocess, "Popen", fake_popen)

    _ensure_bridge(next_config)

    assert previous_process.events == ["terminate", ("wait", 2)]
    assert len(popen_calls) == 1
    assert service._HERMES_BRIDGE_PROCESS is next_process
    assert service._HERMES_BRIDGE_CONFIG == next_config


def test_ensure_hermes_bridge_does_not_manage_external_healthy_bridge(monkeypatch):
    config = _bridge_config()
    monkeypatch.setattr(service, "_HERMES_BRIDGE_PROCESS", None)
    monkeypatch.setattr(service, "_HERMES_BRIDGE_CONFIG", None, raising=False)
    monkeypatch.setattr(service, "_hermes_bridge_healthy", lambda _url: True)
    monkeypatch.setattr(
        service.subprocess,
        "Popen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("external bridge should not be replaced")
        ),
    )

    _ensure_bridge(config)

    assert service._HERMES_BRIDGE_PROCESS is None
    assert service._HERMES_BRIDGE_CONFIG is None


def test_ensure_hermes_bridge_clears_config_for_exited_managed_process(monkeypatch):
    config = _bridge_config()
    process = _FakeBridgeProcess(poll_result=0)
    monkeypatch.setattr(service, "_HERMES_BRIDGE_PROCESS", process)
    monkeypatch.setattr(service, "_HERMES_BRIDGE_CONFIG", config)
    monkeypatch.setattr(service, "_hermes_bridge_healthy", lambda _url: True)
    monkeypatch.setattr(
        service.subprocess,
        "Popen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("healthy external bridge should be reused")
        ),
    )

    _ensure_bridge(config)

    assert process.events == []
    assert service._HERMES_BRIDGE_PROCESS is None
    assert service._HERMES_BRIDGE_CONFIG is None


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
