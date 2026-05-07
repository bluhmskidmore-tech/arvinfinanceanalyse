"""Pytest hooks: skip storage migrations on app/worker startup during unit tests."""

from __future__ import annotations

import os

os.environ.setdefault("MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS", "1")
os.environ.setdefault("MOSS_SKIP_POSTGRES_MIGRATIONS", "1")


import pytest


@pytest.fixture()
def seed_wildcard_scope(tmp_path, monkeypatch):
    """Grant wildcard permissions so existing functional tests pass with auth enforcement."""
    from backend.app.governance.settings import get_settings

    sqlite_path = tmp_path / "auth-scope-wildcard.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    get_settings.cache_clear()

    from backend.app.repositories.user_scope_repo import UserScopeRepository

    repo = UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}")
    repo.grant_scope(user_id="*", role=None, resource="*", action="*")
    repo.grant_scope(user_id="*", role=None, resource="product_category_pnl.adjustment", action="write")
    repo.grant_scope(user_id="*", role=None, resource="pnl_by_business.adjustment", action="write")
    yield
    get_settings.cache_clear()
