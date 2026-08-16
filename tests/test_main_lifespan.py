from __future__ import annotations

import asyncio
import logging
import sys
from types import SimpleNamespace

import pytest
from fastapi import FastAPI

from tests.helpers import load_module


class _StopWarmupLoop(Exception):
    """Breaks out of the otherwise endless background warmup loop under test."""


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
        "warm_home_snapshot_cache_if_configured",
        lambda value: calls.append(("warm-home-snapshot-background", value)),
    )
    monkeypatch.setattr(
        module,
        "warm_home_snapshot_cache_blocking_if_configured",
        lambda *_args, **_kwargs: pytest.fail("startup must not block on home snapshot prewarm"),
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
        ("warm-home-snapshot-background", settings),
        ("warm-home-background", settings),
        "inside",
    ]
    assert len(async_calls) == 1
    assert async_calls[0][0] is module.run_startup_storage_migrations


def test_background_warmup_coordinator_runs_income_before_market(monkeypatch) -> None:
    module = load_module("backend.app.main", "backend/app/main.py")
    settings = object()
    calls: list[tuple[str, object]] = []

    monkeypatch.setattr(
        module,
        "warm_home_income_trend_cache_in_current_thread_if_configured",
        lambda value, **_kwargs: calls.append(("income", value)),
    )
    monkeypatch.setattr(
        module,
        "warm_market_home_cache_in_current_thread_if_configured",
        lambda value, **_kwargs: calls.append(("market", value)),
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
        lambda value, **_kwargs: events.append(f"income:{id(value)}"),
    )
    monkeypatch.setattr(
        module,
        "warm_market_home_cache_in_current_thread_if_configured",
        lambda value, **_kwargs: events.append(f"market:{id(value)}"),
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


def test_background_warmup_interval_stays_inside_response_cache_ttl(monkeypatch) -> None:
    module = load_module("backend.app.main", "backend/app/main.py")
    monkeypatch.delenv("MOSS_HOME_BACKGROUND_WARMUP_INTERVAL_SECONDS", raising=False)
    monkeypatch.delenv("MOSS_MARKET_HOME_CACHE_TTL_SECONDS", raising=False)

    interval = module.resolve_home_background_warmup_interval_seconds()
    assert interval == pytest.approx(240.0)
    # A refresh that lands after the TTL would leave the page paying a cold recompute.
    assert interval < module.resolve_default_ttl()

    monkeypatch.setenv("MOSS_MARKET_HOME_CACHE_TTL_SECONDS", "60")
    assert module.resolve_home_background_warmup_interval_seconds() == pytest.approx(48.0)

    monkeypatch.setenv("MOSS_HOME_BACKGROUND_WARMUP_INTERVAL_SECONDS", "12.5")
    assert module.resolve_home_background_warmup_interval_seconds() == 12.5

    monkeypatch.setenv("MOSS_HOME_BACKGROUND_WARMUP_INTERVAL_SECONDS", "nope")
    assert module.resolve_home_background_warmup_interval_seconds() == pytest.approx(48.0)

    monkeypatch.setenv("MOSS_HOME_BACKGROUND_WARMUP_INTERVAL_SECONDS", "0")
    assert module.resolve_home_background_warmup_interval_seconds() == 0.0


def test_background_warmup_refreshes_caches_on_the_interval(monkeypatch) -> None:
    module = load_module("backend.app.main", "backend/app/main.py")
    settings = object()
    events: list[str] = []
    clock = {"now": 0.0}

    monkeypatch.setattr(module.time, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(module, "resolve_home_background_warmup_delay_seconds", lambda: 0.0)
    monkeypatch.setattr(module, "resolve_home_background_warmup_interval_seconds", lambda: 240.0)
    monkeypatch.setattr(
        module,
        "warm_home_income_trend_cache_in_current_thread_if_configured",
        lambda _value, *, force_refresh=False: events.append(f"income:{force_refresh}"),
    )
    monkeypatch.setattr(
        module,
        "warm_market_home_cache_in_current_thread_if_configured",
        lambda _value, *, force_refresh=False: events.append(f"market:{force_refresh}"),
    )

    def fake_sleep(seconds: float) -> None:
        events.append(f"sleep:{seconds}")
        clock["now"] += seconds
        if len([event for event in events if event.startswith("market:")]) >= 2:
            raise _StopWarmupLoop

    monkeypatch.setattr(module.time, "sleep", fake_sleep)

    with pytest.raises(_StopWarmupLoop):
        module._warm_home_background_caches_periodically(settings)

    # The startup delay applies once; every later pass must force a rebuild, because
    # a read-through warm would leave the original expiry in place.
    assert events == [
        "income:False",
        "market:False",
        "sleep:240.0",
        "income:True",
        "market:True",
        "sleep:240.0",
    ]


def test_background_warmup_keeps_cadence_when_passes_are_slow(monkeypatch) -> None:
    """A slow pass must not stretch the effective period past the cache TTL: the
    next sleep shrinks by however long the pass took."""
    module = load_module("backend.app.main", "backend/app/main.py")
    settings = object()
    sleeps: list[float] = []
    clock = {"now": 0.0}

    monkeypatch.setattr(module.time, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(module, "resolve_home_background_warmup_delay_seconds", lambda: 0.0)
    monkeypatch.setattr(module, "resolve_home_background_warmup_interval_seconds", lambda: 240.0)

    def slow_pass(_value: object, **_kwargs: object) -> None:
        clock["now"] += 30.0

    monkeypatch.setattr(module, "_run_home_background_warmup_pass", slow_pass)

    def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock["now"] += seconds
        if len(sleeps) >= 3:
            raise _StopWarmupLoop

    monkeypatch.setattr(module.time, "sleep", fake_sleep)

    with pytest.raises(_StopWarmupLoop):
        module._warm_home_background_caches_periodically(settings)

    # The cadence anchor is set right after the initial pass (t=30), so the first
    # sleep is a full interval; every later sleep shrinks by the 30s the previous
    # pass consumed instead of stacking on top of it.
    assert sleeps == [240.0, 210.0, 210.0]


def test_background_warmup_periodically_refreshes_home_snapshot(monkeypatch) -> None:
    module = load_module("backend.app.main", "backend/app/main.py")
    settings = object()
    snapshot_calls: list[object] = []
    market_passes: list[int] = []
    clock = {"now": 0.0}

    monkeypatch.setattr(module.time, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(module, "resolve_home_background_warmup_delay_seconds", lambda: 0.0)
    monkeypatch.setattr(module, "resolve_home_background_warmup_interval_seconds", lambda: 240.0)
    monkeypatch.setattr(module, "HOME_SNAPSHOT_REFRESH_INTERVAL_SECONDS", 400.0)
    monkeypatch.setattr(
        module,
        "_run_home_background_warmup_pass",
        lambda _value, **_kwargs: market_passes.append(len(market_passes) + 1),
    )
    monkeypatch.setattr(
        module,
        "warm_home_snapshot_cache_blocking_if_configured",
        lambda value, *, force_refresh=False: snapshot_calls.append((value, force_refresh)),
    )

    def fake_sleep(seconds: float) -> None:
        clock["now"] += seconds
        if len(market_passes) >= 3:
            raise _StopWarmupLoop

    monkeypatch.setattr(module.time, "sleep", fake_sleep)

    with pytest.raises(_StopWarmupLoop):
        module._warm_home_background_caches_periodically(settings)

    # Snapshot TTL window (mocked to 400s) is crossed at the second refresh pass
    # (t=480), not the first (t=240).
    assert snapshot_calls == [(settings, True)]


def test_background_warmup_single_pass_when_interval_disabled(monkeypatch) -> None:
    module = load_module("backend.app.main", "backend/app/main.py")
    settings = object()
    events: list[str] = []

    monkeypatch.setattr(module, "resolve_home_background_warmup_delay_seconds", lambda: 0.0)
    monkeypatch.setattr(module, "resolve_home_background_warmup_interval_seconds", lambda: 0.0)
    monkeypatch.setattr(
        module,
        "warm_home_income_trend_cache_in_current_thread_if_configured",
        lambda _value, **_kwargs: events.append("income"),
    )
    monkeypatch.setattr(
        module,
        "warm_market_home_cache_in_current_thread_if_configured",
        lambda _value, **_kwargs: events.append("market"),
    )
    monkeypatch.setattr(
        module.time,
        "sleep",
        lambda *_args, **_kwargs: pytest.fail("disabled interval must not sleep"),
    )

    module._warm_home_background_caches_periodically(settings)

    assert events == ["income", "market"]


def test_background_warmup_refresh_failure_is_logged_and_loop_survives(
    monkeypatch,
    caplog,
) -> None:
    module = load_module("backend.app.main", "backend/app/main.py")
    settings = object()
    passes: list[int] = []

    def fake_pass(value: object, **_kwargs: object) -> None:
        assert value is settings
        passes.append(len(passes) + 1)
        if len(passes) == 2:
            raise RuntimeError("refresh boom")

    monkeypatch.setattr(module, "resolve_home_background_warmup_delay_seconds", lambda: 0.0)
    monkeypatch.setattr(module, "resolve_home_background_warmup_interval_seconds", lambda: 5.0)
    monkeypatch.setattr(module, "_run_home_background_warmup_pass", fake_pass)

    def fake_sleep(_seconds: float) -> None:
        if len(passes) >= 3:
            raise _StopWarmupLoop

    monkeypatch.setattr(module.time, "sleep", fake_sleep)

    with caplog.at_level(logging.ERROR, logger="backend.app.main"):
        with pytest.raises(_StopWarmupLoop):
            module._warm_home_background_caches_periodically(settings)

    assert passes == [1, 2, 3]
    assert "home_background_warmup_refresh_failed" in caplog.text


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
    assert started[0][0] is module._warm_home_background_caches_periodically
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
        assert started[0][0] is module._warm_home_background_caches_periodically
        assert started[0][1]["args"] == (settings,)
        assert started[1] == ("start", {})
        assert len(started) == 2


def test_income_warmup_failure_is_logged_and_does_not_block_market(
    monkeypatch,
    caplog,
) -> None:
    import backend.app.services.executive_service  # noqa: F401

    module = load_module("backend.app.main", "backend/app/main.py")
    # `load_module` swaps the sys.modules entry without refreshing the parent package
    # attribute, so `from backend.app.services import executive_service` can return a
    # stale module while `module` calls into the current one. Patch what it calls.
    executive_service = sys.modules["backend.app.services.executive_service"]
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
    # Keep the unit test off the real snapshot pipeline; force the fallback path.
    monkeypatch.setattr(
        executive_service,
        "home_snapshot_unified_report_date",
        lambda: None,
    )

    def fail_income(*_args, **_kwargs):
        raise RuntimeError("income boom")

    monkeypatch.setattr(executive_service, "home_income_trend_envelope", fail_income)
    monkeypatch.setattr(
        module,
        "warm_market_home_cache_in_current_thread_if_configured",
        lambda value, **_kwargs: market_calls.append(value),
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
