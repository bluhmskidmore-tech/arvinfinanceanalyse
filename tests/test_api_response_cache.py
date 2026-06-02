"""Unit tests for the market/macro home TTL response cache."""

from __future__ import annotations

import threading
import time

from backend.app.api.response_cache import TTLResponseCache, resolve_default_ttl


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_get_or_build_caches_until_ttl_expires() -> None:
    clock = FakeClock()
    cache = TTLResponseCache(default_ttl_seconds=300.0, clock=clock)
    calls = {"count": 0}

    def builder() -> dict[str, int]:
        calls["count"] += 1
        return {"value": calls["count"]}

    first = cache.get_or_build("k", builder)
    second = cache.get_or_build("k", builder)
    assert first == {"value": 1}
    assert second == {"value": 1}
    assert calls["count"] == 1

    clock.now = 301.0
    third = cache.get_or_build("k", builder)
    assert third == {"value": 2}
    assert calls["count"] == 2


def test_distinct_keys_do_not_collide() -> None:
    clock = FakeClock()
    cache = TTLResponseCache(default_ttl_seconds=300.0, clock=clock)

    a = cache.get_or_build("a", lambda: "alpha")
    b = cache.get_or_build("b", lambda: "beta")
    assert a == "alpha"
    assert b == "beta"


def test_invalidate_specific_key_then_all() -> None:
    clock = FakeClock()
    cache = TTLResponseCache(default_ttl_seconds=300.0, clock=clock)
    calls = {"a": 0, "b": 0}

    def make(label: str):
        def builder() -> str:
            calls[label] += 1
            return f"{label}-{calls[label]}"

        return builder

    assert cache.get_or_build("a", make("a")) == "a-1"
    assert cache.get_or_build("b", make("b")) == "b-1"

    cache.invalidate("a")
    assert cache.get_or_build("a", make("a")) == "a-2"
    assert cache.get_or_build("b", make("b")) == "b-1"  # b untouched

    cache.invalidate()
    assert cache.get_or_build("b", make("b")) == "b-2"


def test_zero_ttl_disables_caching() -> None:
    cache = TTLResponseCache(default_ttl_seconds=0.0)
    calls = {"count": 0}

    def builder() -> int:
        calls["count"] += 1
        return calls["count"]

    assert cache.get_or_build("k", builder) == 1
    assert cache.get_or_build("k", builder) == 2
    assert calls["count"] == 2


def test_get_or_build_deduplicates_concurrent_builds_for_same_key() -> None:
    cache = TTLResponseCache(default_ttl_seconds=300.0)
    builder_started = threading.Event()
    release_builder = threading.Event()
    calls = {"count": 0}
    calls_lock = threading.Lock()
    results: list[dict[str, int]] = []
    errors: list[BaseException] = []

    def builder() -> dict[str, int]:
        with calls_lock:
            calls["count"] += 1
            value = calls["count"]
        builder_started.set()
        assert release_builder.wait(timeout=2.0)
        return {"value": value}

    def read_cache() -> None:
        try:
            results.append(cache.get_or_build("k", builder))
        except BaseException as exc:  # pragma: no cover - surfaced by assertion below
            errors.append(exc)

    first = threading.Thread(target=read_cache)
    second = threading.Thread(target=read_cache)
    first.start()
    assert builder_started.wait(timeout=1.0)

    try:
        second.start()
        for _ in range(50):
            with calls_lock:
                if calls["count"] > 1:
                    break
            time.sleep(0.01)

        with calls_lock:
            assert calls["count"] == 1
    finally:
        release_builder.set()
        first.join(timeout=2.0)
        second.join(timeout=2.0)

    assert not first.is_alive()
    assert not second.is_alive()
    assert errors == []
    assert results == [{"value": 1}, {"value": 1}]


def test_get_or_build_propagates_inflight_error_and_allows_rebuild() -> None:
    cache = TTLResponseCache(default_ttl_seconds=300.0)
    builder_started = threading.Event()
    release_builder = threading.Event()
    calls = {"count": 0}
    calls_lock = threading.Lock()
    errors: list[BaseException] = []

    def builder() -> dict[str, int]:
        with calls_lock:
            calls["count"] += 1
            value = calls["count"]
        if value == 1:
            builder_started.set()
            assert release_builder.wait(timeout=2.0)
            raise RuntimeError("first build failed")
        return {"value": value}

    def read_cache() -> None:
        try:
            cache.get_or_build("k", builder)
        except BaseException as exc:  # pragma: no cover - surfaced by assertion below
            errors.append(exc)

    first = threading.Thread(target=read_cache)
    second = threading.Thread(target=read_cache)
    first.start()
    assert builder_started.wait(timeout=1.0)
    second.start()
    release_builder.set()
    first.join(timeout=2.0)
    second.join(timeout=2.0)

    assert not first.is_alive()
    assert not second.is_alive()
    assert len(errors) == 2
    assert all(isinstance(error, RuntimeError) for error in errors)
    assert {str(error) for error in errors} == {"first build failed"}
    assert cache.get_or_build("k", builder) == {"value": 2}


def test_resolve_default_ttl_reads_env(monkeypatch) -> None:
    monkeypatch.delenv("MOSS_MARKET_HOME_CACHE_TTL_SECONDS", raising=False)
    assert resolve_default_ttl(123.0) == 123.0

    monkeypatch.setenv("MOSS_MARKET_HOME_CACHE_TTL_SECONDS", "45")
    assert resolve_default_ttl(123.0) == 45.0

    monkeypatch.setenv("MOSS_MARKET_HOME_CACHE_TTL_SECONDS", "not-a-number")
    assert resolve_default_ttl(123.0) == 123.0
