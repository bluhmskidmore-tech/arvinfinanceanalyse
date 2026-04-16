import pytest

from tests.helpers import load_module


def test_fastapi_application_exposes_live_and_ready_health_routes():
    module = load_module("backend.app.main", "backend/app/main.py")
    app = getattr(module, "app", None)
    if app is None:
        pytest.fail("backend.app.main must expose a module-level 'app'")

    paths = {route.path for route in app.routes}
    assert "/health" in paths
    assert "/health/live" in paths
    assert "/health/ready" in paths
