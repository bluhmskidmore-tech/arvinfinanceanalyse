from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace

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
    async_calls = []

    async def fake_to_thread(fn, *args, **kwargs):
        async_calls.append((fn, args, kwargs))
        return fn(*args, **kwargs)

    monkeypatch.setattr(module.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(
        module,
        "warm_home_snapshot_cache_blocking_if_configured",
        lambda value: calls.append(("warm-home-blocking", value)),
    )
    monkeypatch.setattr(
        module,
        "warm_home_background_caches_if_configured",
        lambda value: calls.append(("warm-home-background", value)),
    )

    async def run_lifespan() -> None:
        async with module.lifespan(FastAPI()):
            calls.append("inside")

    asyncio.run(run_lifespan())

    assert calls == [
        "storage",
        ("warm-hermes", settings),
        ("warm-home-blocking", settings),
        ("warm-home-background", settings),
        "inside",
    ]
    assert async_calls[1][0] is module.warm_home_snapshot_cache_blocking_if_configured


def test_background_warmup_coordinator_runs_income_before_market(monkeypatch) -> None:
    module = load_module("backend.app.main", "backend/app/main.py")
    settings = object()
    calls: list[tuple[str, object]] = []

    monkeypatch.setattr(
        module,
        "warm_home_income_trend_cache_in_current_thread_if_configured",
        lambda value: calls.append(("income", value)),
    )
    monkeypatch.setattr(
        module,
        "warm_market_home_cache_in_current_thread_if_configured",
        lambda value: calls.append(("market", value)),
    )
    monkeypatch.setattr(module.time, "sleep", lambda *_args, **_kwargs: None)

    module._warm_home_background_caches_quietly(settings)

    assert calls == [("income", settings), ("market", settings)]


def test_background_warmup_waits_before_competing_with_readiness(monkeypatch) -> None:
    module = load_module("backend.app.main", "backend/app/main.py")
    settings = object()
    events: list[str] = []

    monkeypatch.setattr(
        module,
        "resolve_home_background_warmup_delay_seconds",
        lambda: 1.5,
    )
    monkeypatch.setattr(
        module.time,
        "sleep",
        lambda seconds: events.append(f"sleep:{seconds}"),
    )
    monkeypatch.setattr(
        module,
        "warm_home_income_trend_cache_in_current_thread_if_configured",
        lambda value: events.append(f"income:{id(value)}"),
    )
    monkeypatch.setattr(
        module,
        "warm_market_home_cache_in_current_thread_if_configured",
        lambda value: events.append(f"market:{id(value)}"),
    )

    module._warm_home_background_caches_quietly(settings)

    assert events == [
        "sleep:1.5",
        f"income:{id(settings)}",
        f"market:{id(settings)}",
    ]


def test_background_warmup_delay_defaults_conservatively(monkeypatch) -> None:
    module = load_module("backend.app.main", "backend/app/main.py")
    monkeypatch.delenv("MOSS_HOME_BACKGROUND_WARMUP_DELAY_SECONDS", raising=False)
    assert module.resolve_home_background_warmup_delay_seconds() == 2.0

    monkeypatch.setenv("MOSS_HOME_BACKGROUND_WARMUP_DELAY_SECONDS", "0")
    assert module.resolve_home_background_warmup_delay_seconds() == 0.0

    monkeypatch.setenv("MOSS_HOME_BACKGROUND_WARMUP_DELAY_SECONDS", "3.25")
    assert module.resolve_home_background_warmup_delay_seconds() == 3.25

    monkeypatch.setenv("MOSS_HOME_BACKGROUND_WARMUP_DELAY_SECONDS", "nope")
    assert module.resolve_home_background_warmup_delay_seconds() == 2.0


def test_background_warmup_coordinator_starts_one_daemon_thread(monkeypatch) -> None:
    module = load_module("backend.app.main", "backend/app/main.py")
    started: list[tuple[object, dict[str, object]]] = []

    class Settings:
        home_income_trend_prewarm_enabled = True
        market_home_prewarm_enabled = True

    class FakeThread:
        def __init__(self, *, target, args=(), daemon=False, name=""):
            started.append((target, {"args": args, "daemon": daemon, "name": name}))

        def start(self):
            started.append(("start", {}))

    settings = Settings()
    monkeypatch.setattr(module.threading, "Thread", FakeThread)

    assert module.warm_home_background_caches_if_configured(settings) is True
    assert started[0][0] is module._warm_home_background_caches_quietly
    assert started[0][1] == {
        "args": (settings,),
        "daemon": True,
        "name": "moss-home-background-warmup",
    }
    assert started[1] == ("start", {})
    assert len(started) == 2


def test_background_warmup_coordinator_starts_when_either_warmup_is_enabled(
    monkeypatch,
) -> None:
    module = load_module("backend.app.main", "backend/app/main.py")
    started: list[tuple[object, dict[str, object]]] = []

    class FakeThread:
        def __init__(self, *, target, args=(), daemon=False, name=""):
            started.append((target, {"args": args, "daemon": daemon, "name": name}))

        def start(self):
            started.append(("start", {}))

    monkeypatch.setattr(module.threading, "Thread", FakeThread)

    for settings in (
        SimpleNamespace(
            home_income_trend_prewarm_enabled=True,
            market_home_prewarm_enabled=False,
        ),
        SimpleNamespace(
            home_income_trend_prewarm_enabled=False,
            market_home_prewarm_enabled=True,
        ),
    ):
        started.clear()
        assert module.warm_home_background_caches_if_configured(settings) is True
        assert started[0][0] is module._warm_home_background_caches_quietly
        assert started[0][1]["args"] == (settings,)
        assert started[1] == ("start", {})
        assert len(started) == 2


def test_income_warmup_failure_is_logged_and_does_not_block_market(
    monkeypatch,
    caplog,
) -> None:
    from backend.app.services import executive_service

    module = load_module("backend.app.main", "backend/app/main.py")
    settings = SimpleNamespace(
        home_income_trend_prewarm_enabled=True,
        market_home_prewarm_enabled=True,
    )
    market_calls: list[object] = []

    monkeypatch.setattr(
        executive_service,
        "_latest_product_category_report_date",
        lambda: "2026-04-08",
    )

    def fail_income(*_args, **_kwargs):
        raise RuntimeError("income boom")

    monkeypatch.setattr(executive_service, "home_income_trend_envelope", fail_income)
    monkeypatch.setattr(
        module,
        "warm_market_home_cache_in_current_thread_if_configured",
        lambda value: market_calls.append(value),
    )

    with caplog.at_level(
        logging.ERROR,
        logger="backend.app.services.executive_service",
    ):
        monkeypatch.setattr(module.time, "sleep", lambda *_args, **_kwargs: None)
        module._warm_home_background_caches_quietly(settings)

    assert market_calls == [settings]
    assert "home_income_trend_prewarm_failed" in caplog.messages


def test_background_warmup_coordinator_skips_thread_when_all_warmups_disabled(monkeypatch) -> None:
    module = load_module("backend.app.main", "backend/app/main.py")

    class Settings:
        home_income_trend_prewarm_enabled = False
        market_home_prewarm_enabled = False

    def fail_thread(**_kwargs):
        raise AssertionError("thread should not start")

    monkeypatch.setattr(module.threading, "Thread", fail_thread)

    assert module.warm_home_background_caches_if_configured(Settings()) is False


def test_main_app_sets_disabled_otel_status_by_default() -> None:
    module = load_module("backend.app.main", "backend/app/main.py")

    assert module.app.state.moss_otel.status == "disabled"
