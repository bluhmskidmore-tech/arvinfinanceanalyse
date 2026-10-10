"""Cross-process consistency contract for the suggested-action HMAC token secret.

两个独立加载的 action_token 模块实例模拟两个进程（各自持有独立的
进程本地随机 secret）：未配置 secret 时跨实例校验必须失败（记录现状
限制），通过 governance settings 或环境变量配置同一 secret 后必须恢复
跨实例一致性。
"""

from __future__ import annotations

import importlib.util
import logging
import traceback
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
    "payload": {
        "intent": "portfolio_overview",
        "confirmation_scope": {"user_id": "user_a"},
    },
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


def _stub_settings(
    monkeypatch,
    secret: str,
    *,
    environment: str = "development",
) -> None:
    from backend.app.governance import settings as settings_module

    monkeypatch.setattr(
        settings_module,
        "get_settings",
        lambda: SimpleNamespace(
            agent_action_token_secret=secret,
            environment=environment,
        ),
    )


def test_production_missing_secret_fails_closed_on_issue_and_match(monkeypatch):
    monkeypatch.delenv("MOSS_AGENT_ACTION_TOKEN_SECRET", raising=False)
    _stub_settings(monkeypatch, "", environment="production")
    instance = _load_action_token_instance("proc_production_fail_closed")

    with pytest.raises(RuntimeError, match="MOSS_AGENT_ACTION_TOKEN_SECRET"):
        instance.agent_action_confirmation_token(**_ACTION)

    with pytest.raises(PermissionError, match="MOSS_AGENT_ACTION_TOKEN_SECRET"):
        instance.agent_action_confirmation_token_matches(token="bad-token", **_ACTION)


def test_development_process_local_secret_warns_and_falls_back(monkeypatch, caplog):
    monkeypatch.delenv("MOSS_AGENT_ACTION_TOKEN_SECRET", raising=False)
    _stub_settings(monkeypatch, "", environment="development")
    instance = _load_action_token_instance("proc_development_warning")

    with caplog.at_level(logging.WARNING):
        secret = instance._action_token_secret()
        assert instance._action_token_secret() == secret

    warnings = [
        record.getMessage()
        for record in caplog.records
        if "MOSS_AGENT_ACTION_TOKEN_SECRET" in record.getMessage()
    ]
    assert len(warnings) == 1
    assert "development" in warnings[0]


def test_production_configured_secret_does_not_warn(monkeypatch, caplog):
    monkeypatch.delenv("MOSS_AGENT_ACTION_TOKEN_SECRET", raising=False)
    _stub_settings(
        monkeypatch,
        "configured-production-secret",
        environment="production",
    )
    instance = _load_action_token_instance("proc_configured_no_warning")

    with caplog.at_level(logging.WARNING):
        assert instance._action_token_secret() == "configured-production-secret"

    assert not [
        record
        for record in caplog.records
        if "MOSS_AGENT_ACTION_TOKEN_SECRET" in record.getMessage()
    ]


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


def test_settings_failure_fails_closed_without_exposing_configuration(monkeypatch, caplog):
    """未知运行环境不得当成 development，配置故障也不得泄露原始内容。"""
    monkeypatch.delenv("MOSS_AGENT_ACTION_TOKEN_SECRET", raising=False)
    from backend.app.governance import settings as settings_module

    def _broken_settings():
        raise RuntimeError("sensitive-config-value must not appear in public errors")

    monkeypatch.setattr(settings_module, "get_settings", _broken_settings)
    instance = _load_action_token_instance("proc_fallback")

    with pytest.raises(RuntimeError) as issue_error:
        instance.agent_action_confirmation_token(**_ACTION)
    with pytest.raises(PermissionError) as match_error:
        instance.agent_action_confirmation_token_matches(token="bad-token", **_ACTION)

    assert "sensitive-config-value" not in str(issue_error.value)
    assert "sensitive-config-value" not in str(match_error.value)
    assert "sensitive-config-value" not in "".join(traceback.format_exception(issue_error.value))
    assert "sensitive-config-value" not in "".join(traceback.format_exception(match_error.value))
    assert "sensitive-config-value" not in caplog.text
    assert not instance._PROCESS_LOCAL_SECRET_WARNING_EMITTED


@pytest.mark.parametrize("environment", ["", None, "unrecognized"])
def test_unknown_environment_without_secret_fails_closed(monkeypatch, environment):
    monkeypatch.delenv("MOSS_AGENT_ACTION_TOKEN_SECRET", raising=False)
    _stub_settings(monkeypatch, "", environment=environment)
    instance = _load_action_token_instance("proc_unknown_environment")

    with pytest.raises(RuntimeError, match="MOSS_AGENT_ACTION_TOKEN_SECRET"):
        instance.agent_action_confirmation_token(**_ACTION)
    with pytest.raises(PermissionError, match="MOSS_AGENT_ACTION_TOKEN_SECRET"):
        instance.agent_action_confirmation_token_matches(token="bad-token", **_ACTION)


def test_explicit_env_secret_survives_settings_failure_across_instances(monkeypatch):
    from backend.app.governance import settings as settings_module

    monkeypatch.setenv("MOSS_AGENT_ACTION_TOKEN_SECRET", "explicit-env-only-secret")

    def broken_settings():
        raise RuntimeError("settings unavailable")

    monkeypatch.setattr(settings_module, "get_settings", broken_settings)
    issuer = _load_action_token_instance("proc_env_failure_a")
    verifier = _load_action_token_instance("proc_env_failure_b")
    token = issuer.agent_action_confirmation_token(**_ACTION)
    assert verifier.agent_action_confirmation_token_matches(token=token, **_ACTION)


@pytest.mark.parametrize("environment", ["development", "staging", "test"])
def test_known_nonproduction_environment_preserves_local_secret(monkeypatch, environment):
    monkeypatch.delenv("MOSS_AGENT_ACTION_TOKEN_SECRET", raising=False)
    _stub_settings(monkeypatch, "", environment=environment)
    instance = _load_action_token_instance("proc_known_environment")
    token = instance.agent_action_confirmation_token(**_ACTION)
    assert instance.agent_action_confirmation_token_matches(token=token, **_ACTION)


def test_settings_secret_keeps_precedence_over_environment_secret(monkeypatch):
    monkeypatch.setenv("MOSS_AGENT_ACTION_TOKEN_SECRET", "environment-secret")
    _stub_settings(monkeypatch, "settings-secret", environment="production")
    instance = _load_action_token_instance("proc_secret_precedence")
    assert instance._action_token_secret() == "settings-secret"


def test_configuration_failure_rejects_previously_valid_local_token(monkeypatch):
    from backend.app.governance import settings as settings_module

    monkeypatch.delenv("MOSS_AGENT_ACTION_TOKEN_SECRET", raising=False)
    _stub_settings(monkeypatch, "", environment="development")
    instance = _load_action_token_instance("proc_config_changed")
    token = instance.agent_action_confirmation_token(**_ACTION)

    def broken_settings():
        raise RuntimeError("configuration no longer available")

    monkeypatch.setattr(settings_module, "get_settings", broken_settings)
    with pytest.raises(PermissionError):
        instance.agent_action_confirmation_token_matches(token=token, **_ACTION)


def test_each_issue_and_match_uses_one_configuration_snapshot(monkeypatch):
    from backend.app.governance import settings as settings_module

    calls = []

    def settings():
        calls.append(None)
        return SimpleNamespace(agent_action_token_secret="snapshot-secret", environment="production")

    monkeypatch.setattr(settings_module, "get_settings", settings)
    instance = _load_action_token_instance("proc_configuration_snapshot")
    token = instance.agent_action_confirmation_token(**_ACTION)
    assert len(calls) == 1
    assert instance.agent_action_confirmation_token_matches(token=token, **_ACTION)
    assert len(calls) == 2


def test_configured_secret_preserves_expiry_and_payload_user_binding(monkeypatch):
    _stub_settings(monkeypatch, "configured-boundary-secret", environment="production")
    instance = _load_action_token_instance("proc_expiry_scope")
    token = instance.agent_action_confirmation_token(expires_at=2000, **_ACTION)
    assert instance.agent_action_confirmation_token_matches(token=token, now=1999, **_ACTION)
    assert not instance.agent_action_confirmation_token_matches(token=token, now=2001, **_ACTION)
    changed_action = {**_ACTION, "payload": {**_ACTION["payload"], "confirmation_scope": {"user_id": "user_b"}}}
    assert not instance.agent_action_confirmation_token_matches(token=token, now=1999, **changed_action)


@pytest.mark.parametrize(
    "payload",
    [
        {"intent": "portfolio_overview"},
        {"intent": "portfolio_overview", "confirmation_scope": "user_a"},
        {"intent": "portfolio_overview", "confirmation_scope": {}},
        {"intent": "portfolio_overview", "confirmation_scope": {"user_id": "  "}},
        {"intent": "portfolio_overview", "confirmation_scope": {"run_id": "run_001"}},
    ],
)
def test_issuance_fails_closed_without_scope_user_id(monkeypatch, payload):
    """签发侧 fail-closed：payload 缺 confirmation_scope.user_id 时拒绝签发。"""
    monkeypatch.delenv("MOSS_AGENT_ACTION_TOKEN_SECRET", raising=False)
    _stub_settings(monkeypatch, "")
    instance = _load_action_token_instance("proc_issue_guard")

    with pytest.raises(RuntimeError, match="confirmation_scope.user_id"):
        instance.agent_action_confirmation_token(
            action_type="execute_intent",
            label="Portfolio overview",
            payload=payload,
        )


def test_matcher_rejects_unbound_payload_even_with_correct_secret_token(monkeypatch):
    """校验侧移除无 scope 兼容放行：即使 HMAC 出自同一 secret 也判不匹配。

    模拟收紧前签发的旧格式 token：绕过签发入口、直接用模块内部原语
    对无 scope payload 计算合法 HMAC，校验必须拒绝。
    """
    import hashlib
    import hmac as hmac_module
    import time as time_module

    monkeypatch.delenv("MOSS_AGENT_ACTION_TOKEN_SECRET", raising=False)
    _stub_settings(monkeypatch, "")
    instance = _load_action_token_instance("proc_unbound_guard")
    unbound_payload = {"intent": "portfolio_overview"}
    expires_at = int(time_module.time()) + 300
    digest = hmac_module.new(
        instance._action_token_secret().encode("utf-8"),
        instance._canonical_action_payload(
            action_type="execute_intent",
            label="Portfolio overview",
            payload=unbound_payload,
            expires_at=expires_at,
        ).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    legacy_token = f"agent_action:v1:{expires_at}:{digest}"

    assert not instance.agent_action_confirmation_token_matches(
        token=legacy_token,
        action_type="execute_intent",
        label="Portfolio overview",
        payload=unbound_payload,
    )


def test_confirmation_scope_user_id_extraction():
    instance = _load_action_token_instance("proc_scope_extract")

    assert instance.confirmation_scope_user_id(
        {"confirmation_scope": {"user_id": " user_a "}}
    ) == "user_a"
    assert instance.confirmation_scope_user_id({}) == ""
    assert instance.confirmation_scope_user_id({"confirmation_scope": None}) == ""
    assert instance.confirmation_scope_user_id({"confirmation_scope": {"user_id": ""}}) == ""
