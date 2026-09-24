"""Cross-process consistency contract for the suggested-action HMAC token secret.

两个独立加载的 action_token 模块实例模拟两个进程（各自持有独立的
进程本地随机 secret）：未配置 secret 时跨实例校验必须失败（记录现状
限制），通过 governance settings 或环境变量配置同一 secret 后必须恢复
跨实例一致性。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_agent_mvp,
]

_ACTION_TOKEN_PATH = (
    Path(__file__).resolve().parents[1]
    / "backend"
    / "app"
    / "agent"
    / "runtime"
    / "action_token.py"
)

_ACTION = {
    "action_type": "execute_intent",
    "label": "Portfolio overview",
    "payload": {"intent": "portfolio_overview"},
}


def _load_action_token_instance(alias: str):
    """独立加载一份 action_token 模块，模拟一个独立进程的 secret 状态。"""
    spec = importlib.util.spec_from_file_location(
        f"tests_agent_action_token_{alias}",
        _ACTION_TOKEN_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _stub_settings(monkeypatch, secret: str) -> None:
    from backend.app.governance import settings as settings_module

    monkeypatch.setattr(
        settings_module,
        "get_settings",
        lambda: SimpleNamespace(agent_action_token_secret=secret),
    )


def test_process_local_secret_does_not_validate_across_instances(monkeypatch):
    """无配置时回退进程本地随机 secret：同实例可校验，跨实例必须失败。"""
    monkeypatch.delenv("MOSS_AGENT_ACTION_TOKEN_SECRET", raising=False)
    _stub_settings(monkeypatch, "")
    issuer = _load_action_token_instance("proc_a")
    verifier = _load_action_token_instance("proc_b")

    token = issuer.agent_action_confirmation_token(**_ACTION)

    assert issuer.agent_action_confirmation_token_matches(token=token, **_ACTION)
    assert not verifier.agent_action_confirmation_token_matches(token=token, **_ACTION)


def test_env_secret_restores_cross_instance_consistency(monkeypatch):
    monkeypatch.setenv("MOSS_AGENT_ACTION_TOKEN_SECRET", "cross-process-env-secret")
    _stub_settings(monkeypatch, "")
    issuer = _load_action_token_instance("proc_env_a")
    verifier = _load_action_token_instance("proc_env_b")

    token = issuer.agent_action_confirmation_token(**_ACTION)

    assert verifier.agent_action_confirmation_token_matches(token=token, **_ACTION)


def test_settings_secret_restores_cross_instance_consistency_without_env(monkeypatch):
    """secret 由 governance settings 提供（无环境变量）也必须跨实例一致。"""
    monkeypatch.delenv("MOSS_AGENT_ACTION_TOKEN_SECRET", raising=False)
    _stub_settings(monkeypatch, "cross-process-settings-secret")
    issuer = _load_action_token_instance("proc_settings_a")
    verifier = _load_action_token_instance("proc_settings_b")

    token = issuer.agent_action_confirmation_token(**_ACTION)

    assert verifier.agent_action_confirmation_token_matches(token=token, **_ACTION)

    forged = token[:-1] + ("0" if token[-1] != "0" else "1")
    assert not verifier.agent_action_confirmation_token_matches(token=forged, **_ACTION)


def test_settings_failure_falls_back_to_process_local_secret(monkeypatch):
    """治理配置不可用时降级为既有行为：同实例签发/校验保持可用。"""
    monkeypatch.delenv("MOSS_AGENT_ACTION_TOKEN_SECRET", raising=False)
    from backend.app.governance import settings as settings_module

    def _broken_settings():
        raise RuntimeError("governance settings unavailable")

    monkeypatch.setattr(settings_module, "get_settings", _broken_settings)
    instance = _load_action_token_instance("proc_fallback")

    token = instance.agent_action_confirmation_token(**_ACTION)

    assert instance.agent_action_confirmation_token_matches(token=token, **_ACTION)
