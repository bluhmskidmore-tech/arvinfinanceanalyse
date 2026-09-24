from __future__ import annotations

import os
import subprocess
import sys

import pytest

from tests.helpers import ROOT


pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_livermore,
]


def test_livermore_route_support_imports_before_lazy_api_cache_dependency() -> None:
    script = """
import importlib
import sys

route_support = importlib.import_module("backend.app.services.market_data_livermore_route_support")
assert "backend.app.api" not in sys.modules
route_support._invalidate_livermore_response_cache()
assert "backend.app.api" in sys.modules
"""
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr


def test_livermore_route_support_invalidates_market_home_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.app.api import response_cache
    from backend.app.services import market_data_livermore_route_support

    invalidated = False

    def invalidate() -> None:
        nonlocal invalidated
        invalidated = True

    monkeypatch.setattr(response_cache.market_home_response_cache, "invalidate", invalidate)

    market_data_livermore_route_support._invalidate_livermore_response_cache()

    assert invalidated is True
