"""Startup security banner: makes a silently-misconfigured `environment` loud.

Covers the audit-driven visibility fix in `validate_auth_startup_guardrails`:
a `logger.warning` banner in development listing the local entrance policy,
and a short `logger.info` confirmation once guardrails are enforced. The
guardrail pass/fail behavior is covered by
`tests/test_auth_context.py` and
`tests/test_auth_startup_guardrails_default_credentials.py`.
"""

from __future__ import annotations

import logging

import pytest

from backend.app.governance.settings import Settings
from backend.app.security.auth_context import (
    ROLE_HEADER_TRUST_ENV,
    validate_auth_startup_guardrails,
)


@pytest.fixture(autouse=True)
def _clean_identity_env(monkeypatch):
    monkeypatch.delenv("MOSS_USER_ID", raising=False)
    monkeypatch.delenv("MOSS_USER_ROLE", raising=False)
    monkeypatch.delenv(ROLE_HEADER_TRUST_ENV, raising=False)


def _production_settings(**overrides) -> Settings:
    values: dict[str, object] = {
        "environment": "production",
        "cors_origins": "https://app.example",
        "postgres_dsn": "postgresql://svc-user:deployment-secret@db.internal:5432/moss",
        "governance_sql_dsn": "",
        "object_store_mode": "local",
        "minio_access_key": "deployment-access-key",
        "minio_secret_key": "deployment-secret-key",
        "_env_file": None,
    }
    values.update(overrides)
    return Settings(**values)


def test_development_environment_logs_warning_banner_with_guardrail_names(caplog):
    with caplog.at_level(logging.WARNING, logger="backend.app.security.auth_context"):
        validate_auth_startup_guardrails(Settings(environment="development", local_only_api=True, _env_file=None))

    warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert len(warnings) == 1
    banner = warnings[0].getMessage()
    assert "environment=development" in banner
    assert "header trust" in banner
    assert "env 身份源拦截" in banner
    assert "CORS 白名单强制" in banner
    assert "弱默认凭据拦截" in banner
    assert "dev fallback 匿名读" in banner
    assert "agent dev scope bypass" in banner
    assert "MOSS_ENVIRONMENT=production" in banner
    assert "本机入口政策已启用" in banner
    assert "应用启动禁止开启" in banner


def test_development_banner_reports_guarded_local_agent_bypass(caplog):
    with caplog.at_level(logging.WARNING, logger="backend.app.security.auth_context"):
        validate_auth_startup_guardrails(
            Settings(
                environment="development",
                local_only_api=True,
                cors_origins="http://localhost:5888",
                agent_dev_scope_bypass=True,
                _env_file=None,
            )
        )

    banner = caplog.records[0].getMessage()
    assert "来源限本机" in banner
    assert "不代表登录认证" in banner
    assert "agent dev scope bypass (agent_dev_scope_bypass): 开启" in banner


def test_general_development_banner_reports_local_policy_disabled(caplog, monkeypatch):
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    with caplog.at_level(logging.WARNING, logger="backend.app.security.auth_context"):
        validate_auth_startup_guardrails(
            Settings(environment="development", local_only_api=False, cors_origins="*", _env_file=None)
        )
    banner = caplog.records[0].getMessage()
    assert "本机入口政策未启用" in banner
    assert "header trust" in banner
    assert "应用启动禁止开启" not in banner
    assert "普通开发入口未启用本机来源校验" in banner


def test_non_development_environment_does_not_log_warning_banner(caplog):
    with caplog.at_level(logging.WARNING, logger="backend.app.security.auth_context"):
        validate_auth_startup_guardrails(_production_settings())

    assert [r for r in caplog.records if r.levelno == logging.WARNING] == []


def test_non_development_environment_logs_short_info_confirmation(caplog):
    with caplog.at_level(logging.INFO, logger="backend.app.security.auth_context"):
        validate_auth_startup_guardrails(_production_settings())

    infos = [record for record in caplog.records if record.levelno == logging.INFO]
    assert len(infos) == 1
    message = infos[0].getMessage()
    assert "environment=production" in message
    assert "护栏已启用" in message


def test_non_development_environment_still_raises_before_logging_banner(caplog):
    with caplog.at_level(logging.INFO, logger="backend.app.security.auth_context"):
        with pytest.raises(RuntimeError, match="production.*CORS|CORS.*production"):
            validate_auth_startup_guardrails(_production_settings(cors_origins="https://app.example,*"))

    assert caplog.records == []
