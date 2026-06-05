from __future__ import annotations

import asyncio

from fastapi import FastAPI

from tests.helpers import load_module


def test_lifespan_warms_hermes_bridge_after_storage_startup(monkeypatch):
    module = load_module("backend.app.main", "backend/app/main.py")
    calls = []
    settings = object()

    monkeypatch.setattr(module, "run_startup_storage_migrations", lambda: calls.append("storage"))
    monkeypatch.setattr(module, "get_settings", lambda: settings)
    monkeypatch.setattr(
        module,
        "warm_hermes_bridge_if_configured",
        lambda value: calls.append(("warm-hermes", value)),
    )
    monkeypatch.setattr(
        module,
        "warm_home_snapshot_cache_if_configured",
        lambda value: calls.append(("warm-home", value)),
    )

    async def run_lifespan() -> None:
        async with module.lifespan(FastAPI()):
            calls.append("inside")

    asyncio.run(run_lifespan())

    assert calls == ["storage", ("warm-hermes", settings), ("warm-home", settings), "inside"]


def test_main_app_sets_disabled_otel_status_by_default() -> None:
    module = load_module("backend.app.main", "backend/app/main.py")

    assert module.app.state.moss_otel.status == "disabled"
