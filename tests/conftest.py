"""Pytest hooks: skip storage migrations on app/worker startup during unit tests."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

os.environ.setdefault("MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS", "1")
os.environ.setdefault("MOSS_SKIP_POSTGRES_MIGRATIONS", "1")


import pytest


def _install_windows_readable_pytest_basetemp() -> None:
    """Keep pytest temp roots readable in this Windows sandbox.

    Pytest creates tmp_path basetemp with mode=0o700. Here that can translate to
    a directory the same process cannot enumerate, so use default mkdir ACLs.
    """

    if os.name != "nt":
        return

    from _pytest.tmpdir import TempPathFactory

    def _getbasetemp_windows_readable(self: TempPathFactory) -> Path:
        if self._basetemp is not None:
            return self._basetemp
        if self._given_basetemp is not None:
            basetemp = Path(self._given_basetemp)
            if basetemp.exists():
                shutil.rmtree(basetemp, ignore_errors=True)
                if basetemp.exists():
                    basetemp = basetemp.with_name(f"{basetemp.name}-readable")
            basetemp.mkdir(parents=True, exist_ok=True)
        else:
            basetemp = Path.cwd() / ".pytest-basetemp"
            basetemp.mkdir(exist_ok=True)
        self._basetemp = basetemp.resolve()
        return self._basetemp

    def _mktemp_windows_readable(
        self: TempPathFactory,
        basename: str,
        numbered: bool = True,
    ) -> Path:
        basename = self._ensure_relative_to_basetemp(basename)
        base = self.getbasetemp()
        if not numbered:
            path = base / basename
            path.mkdir(exist_ok=False)
            return path
        index = 0
        while True:
            path = base / f"{basename}{index}"
            try:
                path.mkdir()
                return path
            except FileExistsError:
                index += 1

    TempPathFactory.getbasetemp = _getbasetemp_windows_readable
    TempPathFactory.mktemp = _mktemp_windows_readable


_install_windows_readable_pytest_basetemp()


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
    repo.grant_scope(user_id="*", role=None, resource="product_category_pnl", action="read")
    repo.grant_scope(user_id="*", role=None, resource="product_category_pnl", action="refresh")
    repo.grant_scope(user_id="*", role=None, resource="product_category_pnl.adjustment", action="write")
    repo.grant_scope(user_id="*", role=None, resource="pnl_by_business.adjustment", action="write")
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def reset_choice_runtime_cache():
    yield

    runtime_module = sys.modules.get("backend.app.config.choice_runtime")
    if runtime_module is not None and hasattr(runtime_module, "_EM_C"):
        runtime_module._EM_C = None

    for module_name in list(sys.modules):
        if module_name == "EmQuantAPI" or module_name.startswith("EmQuantAPI."):
            sys.modules.pop(module_name, None)
