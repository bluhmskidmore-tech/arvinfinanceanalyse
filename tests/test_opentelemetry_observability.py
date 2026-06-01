from __future__ import annotations

from fastapi import FastAPI

from tests.helpers import load_module


def test_setup_opentelemetry_is_disabled_by_default() -> None:
    module = load_module(
        "backend.app.observability.opentelemetry",
        "backend/app/observability/opentelemetry.py",
    )
    app = FastAPI()

    def fail_import(module_name: str):
        raise AssertionError(f"unexpected import: {module_name}")

    result = module.setup_opentelemetry(app, env={}, import_module=fail_import)

    assert result.requested is False
    assert result.active is False
    assert result.status == "disabled"
    assert result.missing_packages == ()
    assert app.state.moss_otel.status == "disabled"


def test_setup_opentelemetry_reports_missing_packages_when_enabled() -> None:
    module = load_module(
        "backend.app.observability.opentelemetry",
        "backend/app/observability/opentelemetry.py",
    )
    app = FastAPI()

    def missing_import(module_name: str):
        raise ImportError(f"missing {module_name}")

    result = module.setup_opentelemetry(
        app,
        env={"MOSS_OTEL_ENABLED": "1"},
        import_module=missing_import,
    )

    assert result.requested is True
    assert result.active is False
    assert result.status == "missing-packages"
    assert "opentelemetry.trace" in result.missing_packages
    assert app.state.moss_otel.status == "missing-packages"
