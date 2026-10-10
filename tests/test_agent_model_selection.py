from __future__ import annotations

import json
import sys
import threading
import time
from types import ModuleType, SimpleNamespace

import pytest

from backend.app.agent.schemas.agent_model import AgentModelCatalog, AgentModelOption
from backend.app.agent.schemas.agent_request import AgentQueryRequest
from backend.app.services import agent_model_catalog_service as catalog_service
from backend.app.services import hermes_agent_service as hermes
from scripts import hermes_stream_runner as runner
from scripts import hermes_model_catalog as model_catalog
from scripts.hermes_model_catalog import normalize_model_entries
from tests.test_agent_runs_api import _client, _sample_envelope, _wait_for_terminal

pytestmark = [pytest.mark.excluded_surface_acceptance, pytest.mark.surface_agent_mvp]


def _catalog():
    return AgentModelCatalog(provider="openai-codex", default_model="gpt-test", source="live", models=[
        AgentModelOption(id="gpt-test", label="Test", reasoning_efforts=["low", "high"], default_reasoning_effort="low"),
        AgentModelOption(id="gpt-other", label="Other", reasoning_efforts=["medium"], default_reasoning_effort="medium"),
    ])


def test_model_catalog_discards_hidden_entries_and_unknown_capabilities():
    models = normalize_model_entries([
        {"slug": "hidden-model", "visibility": "hide"},
        {"slug": "invalid model"},
        {"slug": "gpt-test", "api_key": "must-not-leak", "supported_reasoning_levels": [{"effort": "high"}, {"effort": "invented"}]},
        {"slug": "gpt-test"},
    ])
    assert models == [{"id": "gpt-test", "label": "gpt-test", "reasoning_efforts": ["high"], "default_reasoning_effort": "high"}]


def test_provider_catalog_only_exposes_configured_models_and_no_credentials(monkeypatch):
    auth = ModuleType("hermes_cli.auth")
    auth.resolve_api_key_provider_credentials = lambda provider: {
        "api_key": "secret-must-stay-in-hermes" if provider == "deepseek" else "",
        "base_url": "https://api.deepseek.com/v1",
    }
    monkeypatch.setitem(sys.modules, "hermes_cli", ModuleType("hermes_cli"))
    monkeypatch.setitem(sys.modules, "hermes_cli.auth", auth)
    models = model_catalog.configured_provider_models()
    assert [model["id"] for model in models] == ["deepseek-v4-flash", "deepseek-v4-pro"]
    assert all(model["reasoning_efforts"] == ["none", "low", "high", "max"] for model in models)
    assert "secret-must-stay-in-hermes" not in json.dumps(models)
    assert "base_url" not in json.dumps(models)


def test_provider_credential_failure_does_not_hide_other_models(monkeypatch, caplog):
    auth = ModuleType("hermes_cli.auth")
    def credentials(provider):
        if provider == "deepseek":
            raise ValueError("secret-credential-must-not-appear-in-logs")
        return {"api_key": "configured"}
    auth.resolve_api_key_provider_credentials = credentials
    monkeypatch.setitem(sys.modules, "hermes_cli", ModuleType("hermes_cli"))
    monkeypatch.setitem(sys.modules, "hermes_cli.auth", auth)
    assert model_catalog.configured_provider_models() == [
        {"id": "MiniMax-M3", "label": "MiniMax M3", "reasoning_efforts": [], "default_reasoning_effort": None},
    ]
    assert "deepseek" in caplog.text
    assert "ValueError" in caplog.text
    assert "secret-credential-must-not-appear-in-logs" not in caplog.text


def test_combined_catalog_respects_api_limit_without_losing_configured_providers(monkeypatch):
    config = ModuleType("hermes_cli.config")
    config.load_config_readonly = lambda: {"model": {"provider": "custom", "default": "gpt-0"}}
    monkeypatch.setitem(sys.modules, "hermes_cli", ModuleType("hermes_cli"))
    monkeypatch.setitem(sys.modules, "hermes_cli.config", config)
    monkeypatch.setattr(model_catalog, "normalize_model_entries", lambda _entries: [
        {"id": f"gpt-{index}", "label": f"GPT {index}"} for index in range(100)
    ])
    auth = ModuleType("hermes_cli.auth")
    auth.resolve_api_key_provider_credentials = lambda _provider: {"api_key": "configured"}
    monkeypatch.setitem(sys.modules, "hermes_cli.auth", auth)
    catalog = AgentModelCatalog.model_validate(model_catalog.load_model_catalog())
    assert len(catalog.models) == 100
    assert {"MiniMax-M3", "deepseek-v4-flash", "deepseek-v4-pro"} <= {model.id for model in catalog.models}


@pytest.mark.parametrize(("model", "provider", "effort"), [
    ("MiniMax-M3", "minimax", "low"),
    ("deepseek-v4-flash", "deepseek", "none"),
    ("deepseek-v4-pro", "deepseek", "max"),
])
def test_selected_provider_is_explicit_and_cannot_fall_through(monkeypatch, tmp_path, model, provider, effort):
    captured = {}
    class CLI:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.provider = kwargs.get("provider")
            self.reasoning_config = {"effort": kwargs["reasoning"]}
            self._fallback_model = [{"provider": "other", "model": "wrong-model"}]
            self.agent = SimpleNamespace()
        def _ensure_runtime_credentials(self):
            assert self._fallback_model == []
            return True
        def _init_agent(self, **_kwargs):
            captured["reasoning_config"] = self.reasoning_config
            return True
    cli = ModuleType("cli")
    cli.HermesCLI = CLI
    monkeypatch.setitem(sys.modules, "cli", cli)
    monkeypatch.setattr(runner, "_prepare_hermes_runtime", lambda _root: None)
    runtime = runner._prepare_request_runtime(hermes_root=tmp_path, model=model, max_turns=3, persistent=True, reasoning_effort=effort)
    assert captured["provider"] == provider
    assert captured["model"] == model
    assert captured["toolsets"] == ["web"]
    assert runtime.model == model
    assert captured["reasoning_config"] == (None if provider == "minimax" else {"effort": effort})


def test_synchronous_model_selection_uses_the_same_provider_aware_runner(monkeypatch):
    captured = {}
    def stream(**kwargs):
        captured.update(kwargs)
        assert kwargs["stream_delta_callback"]("OK") is True
        return {"answer": "OK", "model": kwargs["model"]}
    monkeypatch.setattr(hermes, "_run_hermes_agent_streaming", stream)
    result = hermes.run_hermes_agent(
        request=AgentQueryRequest(question="Reply OK", model="MiniMax-M3"),
        command="hermes", wsl_distro="", hermes_home="", model="MiniMax-M3",
        toolsets="web", max_turns=3, timeout_seconds=20, prompt_override="Reply OK",
    )
    assert result["model"] == "MiniMax-M3"
    assert captured["model"] == "MiniMax-M3"


def test_synchronous_selection_consumes_stream_deltas_and_returns_final_answer(monkeypatch):
    from tests.test_hermes_agent_service import _FakeDaemonProcess

    process = _FakeDaemonProcess(responses=[[
        {"type": "delta", "request_id": "__REQUEST_ID__", "seq": 1, "text": "partial"},
        {"type": "final", "request_id": "__REQUEST_ID__", "answer": "complete", "session_id": "test-sync"},
    ]])
    monkeypatch.setattr(hermes.subprocess, "Popen", lambda *_args, **_kwargs: process)
    monkeypatch.setattr(hermes, "_cleanup_wsl_processes", lambda **_kwargs: None)
    try:
        result = hermes.run_hermes_agent(
            request=AgentQueryRequest(question="Reply OK", model="deepseek-v4-flash"),
            command="wsl.exe", wsl_distro="HermesUbuntu", hermes_home="/home/hermes/.hermes",
            model="deepseek-v4-flash", toolsets="web", max_turns=3, timeout_seconds=5,
            reasoning_effort="none", prompt_override="Reply OK",
        )
        assert result["answer"] == "complete"
        assert result["session_id"] == "test-sync"
        assert process.requests[0]["model"] == "deepseek-v4-flash"
        assert process.requests[0]["reasoning_effort"] == "none"
    finally:
        hermes.stop_managed_hermes_stream()


def test_model_catalog_endpoint_uses_existing_agent_gate(monkeypatch, tmp_path):
    client, settings = _client(monkeypatch, tmp_path, lambda *_args: _sample_envelope())
    _reset_catalog_cache()
    monkeypatch.setattr(catalog_service, "_read_hermes_model_catalog", lambda *_args: _catalog())
    response = client.get("/api/agent/models")
    assert response.status_code == 200
    assert response.json() == _catalog().model_dump()
    settings.agent_enabled = False
    disabled = client.get("/api/agent/models")
    assert disabled.status_code == 503
    assert disabled.json()["enabled"] is False


def _reset_catalog_cache():
    with catalog_service._CATALOG_LOCK:
        catalog_service._CATALOG_ENTRIES.clear()
        catalog_service._CATALOG_REFRESHES.clear()


def _drain_catalog_refresh():
    for _ in range(250):
        if not catalog_service._CATALOG_REFRESHES:
            return
        time.sleep(0.02)


def _hermes_settings(tmp_path):
    return SimpleNamespace(
        agent_provider="hermes",
        agent_hermes_command="hermes-test-catalog",
        agent_hermes_wsl_distro="",
        agent_hermes_home=str(tmp_path),
        agent_hermes_model="gpt-test",
    )


def test_cold_model_catalog_falls_back_instead_of_blocking_on_discovery(monkeypatch, tmp_path):
    """冷缓存首次调用受限等待，超时返回配置默认模型而不是长时间阻塞。"""
    release = threading.Event()
    _reset_catalog_cache()

    def blocking_discovery(*_args):
        assert release.wait(timeout=5)
        return _catalog()

    monkeypatch.setattr(catalog_service, "CATALOG_COLD_WAIT_SECONDS", 0.05)
    monkeypatch.setattr(catalog_service, "_read_hermes_model_catalog", blocking_discovery)
    try:
        started = time.monotonic()
        catalog = catalog_service.get_agent_model_catalog(_hermes_settings(tmp_path))
        elapsed = time.monotonic() - started
        assert elapsed < 1.0
        assert catalog.default_model == "gpt-test"
        assert [model.id for model in catalog.models] == ["gpt-test"]
    finally:
        release.set()
        _drain_catalog_refresh()
        _reset_catalog_cache()


def test_stale_model_catalog_is_served_while_one_refresh_runs(monkeypatch, tmp_path):
    """stale-while-revalidate：过期缓存立即返回，后台单飞刷新，不阻塞请求。"""
    release = threading.Event()
    discovery_calls = []
    _reset_catalog_cache()
    settings = _hermes_settings(tmp_path)
    key = (
        settings.agent_hermes_command,
        settings.agent_hermes_wsl_distro,
        settings.agent_hermes_home,
    )
    stale = _catalog().model_copy(update={"source": "cached"})
    with catalog_service._CATALOG_LOCK:
        catalog_service._CATALOG_ENTRIES[key] = catalog_service._CatalogEntry(
            catalog=stale,
            cached_at=time.monotonic() - catalog_service.CATALOG_CACHE_TTL_SECONDS - 1.0,
        )

    def blocking_discovery(*_args):
        discovery_calls.append(_args)
        assert release.wait(timeout=5)
        return _catalog()

    monkeypatch.setattr(catalog_service, "_read_hermes_model_catalog", blocking_discovery)
    try:
        started = time.monotonic()
        first = catalog_service.get_agent_model_catalog(settings)
        second = catalog_service.get_agent_model_catalog(settings)
        elapsed = time.monotonic() - started
        assert elapsed < 1.0
        assert first.source == "cached"
        assert second.source == "cached"
        assert [model.id for model in first.models] == ["gpt-test", "gpt-other"]
        assert len(discovery_calls) == 1
    finally:
        release.set()
        _drain_catalog_refresh()
        _reset_catalog_cache()


def test_fresh_model_catalog_is_served_without_any_discovery(monkeypatch, tmp_path):
    _reset_catalog_cache()
    settings = _hermes_settings(tmp_path)
    key = (
        settings.agent_hermes_command,
        settings.agent_hermes_wsl_distro,
        settings.agent_hermes_home,
    )
    with catalog_service._CATALOG_LOCK:
        catalog_service._CATALOG_ENTRIES[key] = catalog_service._CatalogEntry(
            catalog=_catalog(),
            cached_at=time.monotonic(),
        )

    def unexpected_discovery(*_args):
        raise AssertionError("fresh cache must not trigger discovery")

    monkeypatch.setattr(catalog_service, "_read_hermes_model_catalog", unexpected_discovery)
    try:
        catalog = catalog_service.get_agent_model_catalog(settings)
        assert [model.id for model in catalog.models] == ["gpt-test", "gpt-other"]
        assert catalog_service._CATALOG_REFRESHES == {}
    finally:
        _reset_catalog_cache()


@pytest.mark.parametrize("path", ["/api/agent/query", "/api/agent/lab/runs"])
def test_other_agent_endpoints_cannot_bypass_model_validation(monkeypatch, tmp_path, path):
    client, _settings = _client(monkeypatch, tmp_path, lambda *_args: _sample_envelope())
    monkeypatch.setattr(catalog_service, "get_agent_model_catalog", lambda _settings: _catalog())
    response = client.post(path, json={"question": "hello", "model": "unavailable", "routing_surface": "standalone_workbench"})
    assert response.status_code == 422


@pytest.mark.parametrize("extra", [
    {"model": "unavailable"}, {"model": "gpt-other", "reasoning_effort": "high"},
    {"model": "gpt-test", "reasoning_effort": "invalid"},
])
def test_run_rejects_unavailable_model_or_effort_before_dispatch(monkeypatch, tmp_path, extra):
    calls = []
    client, _settings = _client(monkeypatch, tmp_path, lambda *args: calls.append(args) or _sample_envelope())
    monkeypatch.setattr(catalog_service, "get_agent_model_catalog", lambda _settings: _catalog())
    response = client.post("/api/agent/runs", json={"question": "explain a rainbow", "routing_surface": "standalone_workbench", **extra})
    assert response.status_code == 422
    assert calls == []


def test_run_preserves_selected_model_and_effort_through_worker_and_status(monkeypatch, tmp_path):
    captured = []
    client, _settings = _client(monkeypatch, tmp_path, lambda request, *_args: captured.append(request) or _sample_envelope())
    monkeypatch.setattr(catalog_service, "get_agent_model_catalog", lambda _settings: _catalog())
    response = client.post("/api/agent/runs", json={
        "question": "explain a rainbow", "routing_surface": "standalone_workbench",
        "model": "gpt-other", "reasoning_effort": "medium",
    })
    assert response.status_code == 200
    assert response.json()["model"] == "gpt-other"
    status = _wait_for_terminal(client, response.json()["run_id"])
    assert status["model"] == "gpt-other"
    assert captured[0].model == "gpt-other"
    assert captured[0].reasoning_effort == "medium"


def test_selected_greeting_uses_model_and_records_effective_reasoning(monkeypatch, tmp_path):
    captured = {}
    def execute(**kwargs):
        captured.update(kwargs)
        return {"answer": "Hello from the selected model", "model": kwargs["model"], "toolsets": "web", "transport": "cli"}
    monkeypatch.setattr(hermes, "run_hermes_agent", execute)
    settings = SimpleNamespace(agent_hermes_command="hermes", agent_hermes_wsl_distro="", agent_hermes_model="default-model", agent_hermes_max_turns=3, agent_hermes_timeout_seconds=10)
    response = hermes.execute_hermes_agent_query(
        AgentQueryRequest(question="你好", model="gpt-other", reasoning_effort="high"), str(tmp_path), settings,
    )
    assert captured["model"] == "gpt-other"
    assert captured["reasoning_effort"] == "high"
    assert response.evidence.filters_applied["reasoning_effort"] == "high"


def test_reasoning_change_replaces_prepared_runtime_before_running(monkeypatch, tmp_path):
    events = []
    old_cli = SimpleNamespace()
    old = runner.PreparedRequestRuntime(cli=old_cli, finalize_single_query=lambda _: events.append("old-finalized"), model="gpt-test", max_turns=3)
    class Agent:
        def run_conversation(self, **_kwargs):
            events.append("new-run")
            return {"final_response": "done"}
    new_cli = SimpleNamespace(agent=Agent(), _claim_active_session=lambda *_args, **_kwargs: True)
    def prepare(**kwargs):
        assert events == ["old-finalized"]
        assert kwargs["reasoning_effort"] == "high"
        return runner.PreparedRequestRuntime(cli=new_cli, finalize_single_query=lambda _: events.append("new-finalized"), model="gpt-test", max_turns=3, reasoning_effort="high")
    monkeypatch.setattr(runner, "_prepare_request_runtime", prepare)
    result = runner._run_single_request(request={"prompt": "test", "model": "gpt-test", "max_turns": 3, "reasoning_effort": "high"}, emit=lambda _frame: None, hermes_root=tmp_path, prepared_runtime=old)
    assert result == 0
    assert events == ["old-finalized", "new-run", "new-finalized"]


def test_cli_selection_reaches_real_command_flags():
    args = hermes._build_hermes_command(command="hermes", wsl_distro="", hermes_home="", model="gpt-other", toolsets="web", max_turns=3, prompt="test", reasoning_effort="xhigh")
    assert args[args.index("--model") + 1] == "gpt-other"
    assert args[args.index("--reasoning") + 1] == "xhigh"
