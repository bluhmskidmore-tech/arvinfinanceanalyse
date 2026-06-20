from __future__ import annotations

import pytest

from backend.app.security.auth_context import ROLE_HEADER_TRUST_ENV
from tests.helpers import load_module


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
