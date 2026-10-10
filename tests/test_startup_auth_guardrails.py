from __future__ import annotations

import pytest

from backend.app.security.auth_context import ROLE_HEADER_TRUST_ENV
from tests.helpers import load_module


@pytest.fixture(autouse=True)
def _select_native_local_policy(monkeypatch):
    monkeypatch.setenv("MOSS_LOCAL_ONLY_API", "1")


def test_development_application_rejects_live_trusted_identity_headers(monkeypatch):
    monkeypatch.setenv("MOSS_ENVIRONMENT", "development")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    with pytest.raises(RuntimeError, match="development.*X-User-Role"):
        load_module("backend.app.main", "backend/app/main.py")


@pytest.mark.parametrize("origins", ["*", "https://malicious.example", "http://user@localhost:5888"])
def test_development_application_rejects_non_local_cors_configuration(monkeypatch, origins):
    monkeypatch.setenv("MOSS_ENVIRONMENT", "development")
    monkeypatch.delenv(ROLE_HEADER_TRUST_ENV, raising=False)
    monkeypatch.setenv("MOSS_CORS_ORIGINS", origins)
    with pytest.raises(RuntimeError, match="development.*CORS"):
        load_module("backend.app.main", "backend/app/main.py")


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "10.0.0.5", "attacker.example"])
def test_development_application_rejects_remote_uvicorn_bind(monkeypatch, host):
    import sys
    monkeypatch.setenv("MOSS_ENVIRONMENT", "development")
    monkeypatch.delenv(ROLE_HEADER_TRUST_ENV, raising=False)
    monkeypatch.setattr(sys, "argv", ["uvicorn", "backend.app.main:app", "--host", host])
    with pytest.raises(RuntimeError, match="development.*loopback host"):
        load_module("backend.app.main", "backend/app/main.py")


def test_general_development_startup_keeps_container_and_test_contract(monkeypatch):
    import sys
    monkeypatch.setenv("MOSS_ENVIRONMENT", "development")
    monkeypatch.setenv("MOSS_LOCAL_ONLY_API", "0")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    monkeypatch.setenv("MOSS_CORS_ORIGINS", "*")
    monkeypatch.setattr(sys, "argv", ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0"])
    module = load_module("backend.app.main", "backend/app/main.py")
    assert module._settings.local_only_api is False


def test_unknown_local_policy_configuration_is_rejected(monkeypatch):
    from pydantic import ValidationError
    monkeypatch.setenv("MOSS_LOCAL_ONLY_API", "invalid")
    with pytest.raises(ValidationError, match="local_only_api"):
        load_module("backend.app.main", "backend/app/main.py")


def test_production_startup_rejects_trusted_user_role_headers(monkeypatch):
    monkeypatch.setenv("MOSS_ENVIRONMENT", "production")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")

    with pytest.raises(RuntimeError, match="production.*X-User-Role|X-User-Role.*production"):
        load_module("backend.app.main", "backend/app/main.py")


def test_production_startup_rejects_env_user_identity(monkeypatch):
    monkeypatch.setenv("MOSS_ENVIRONMENT", "production")
    monkeypatch.delenv(ROLE_HEADER_TRUST_ENV, raising=False)
    monkeypatch.setenv("MOSS_USER_ID", "prod-spoof-user")
    monkeypatch.setenv("MOSS_USER_ROLE", "admin")

    with pytest.raises(RuntimeError, match="production.*MOSS_USER_ID|MOSS_USER_ID.*production"):
        load_module("backend.app.main", "backend/app/main.py")


def test_production_startup_rejects_wildcard_cors_with_credentials(monkeypatch):
    monkeypatch.setenv("MOSS_ENVIRONMENT", "production")
    monkeypatch.delenv(ROLE_HEADER_TRUST_ENV, raising=False)
    monkeypatch.delenv("MOSS_USER_ID", raising=False)
    monkeypatch.delenv("MOSS_USER_ROLE", raising=False)
    monkeypatch.setenv("MOSS_CORS_ORIGINS", "https://app.example,*")

    with pytest.raises(RuntimeError, match="production.*CORS|CORS.*production"):
        load_module("backend.app.main", "backend/app/main.py")
