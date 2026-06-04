from __future__ import annotations

import pytest

from backend.app.security.auth_context import ROLE_HEADER_TRUST_ENV
from tests.helpers import load_module


def test_production_startup_rejects_trusted_user_role_headers(monkeypatch):
    monkeypatch.setenv("MOSS_ENVIRONMENT", "production")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")

    with pytest.raises(RuntimeError, match="production.*X-User-Role|X-User-Role.*production"):
        load_module("backend.app.main", "backend/app/main.py")
