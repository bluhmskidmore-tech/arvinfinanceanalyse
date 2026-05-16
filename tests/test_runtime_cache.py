from __future__ import annotations

import threading
import time

from backend.app.services.runtime_cache import (
    InMemoryTTLCache,
    clear_runtime_cache,
    clear_runtime_caches,
    get_runtime_cache,
)


def test_ttl_cache_hits_same_key_and_skips_recompute() -> None:
    calls = 0
    cache: InMemoryTTLCache[tuple[str], str] = InMemoryTTLCache(ttl_seconds=30)

    def build() -> str:
        nonlocal calls
        calls += 1
        return f"value-{calls}"

    assert cache.get_or_set(("k",), build) == "value-1"
    assert cache.get_or_set(("k",), build) == "value-1"
    assert calls == 1


def test_ttl_cache_separates_keys_and_can_invalidate() -> None:
    cache: InMemoryTTLCache[tuple[str], str] = InMemoryTTLCache(ttl_seconds=30)
    cache.set(("a",), "A")
    cache.set(("b",), "B")

    assert cache.get(("a",)) == (True, "A")
    assert cache.get(("b",)) == (True, "B")

    cache.invalidate(("a",))
    assert cache.get(("a",)) == (False, None)
    assert cache.get(("b",)) == (True, "B")


def test_ttl_cache_expires_by_clock() -> None:
    clock = {"now": 100.0}
    calls = 0
    cache: InMemoryTTLCache[tuple[str], str] = InMemoryTTLCache(
        ttl_seconds=5,
        clock=lambda: clock["now"],
    )

    def build() -> str:
        nonlocal calls
        calls += 1
        return f"value-{calls}"

    assert cache.get_or_set(("k",), build) == "value-1"
    clock["now"] += 4.9
    assert cache.get_or_set(("k",), build) == "value-1"
    clock["now"] += 0.2
    assert cache.get_or_set(("k",), build) == "value-2"
    assert calls == 2


def test_named_runtime_cache_is_shared_across_callers() -> None:
    clear_runtime_cache("unit.shared")
    first: InMemoryTTLCache[tuple[str], str] = get_runtime_cache("unit.shared", ttl_seconds=30)
    second: InMemoryTTLCache[tuple[str], str] = get_runtime_cache("unit.shared", ttl_seconds=30)

    first.set(("k",), "v")

    assert second.get(("k",)) == (True, "v")


def test_clear_runtime_caches_clears_named_caches() -> None:
    cache: InMemoryTTLCache[tuple[str], str] = get_runtime_cache("unit.clear-all", ttl_seconds=30)
    cache.set(("k",), "v")

    clear_runtime_caches()

    assert cache.get(("k",)) == (False, None)


def test_same_key_concurrent_callers_share_one_producer() -> None:
    cache: InMemoryTTLCache[tuple[str], str] = InMemoryTTLCache(ttl_seconds=30)
    start = threading.Barrier(6)
    calls = 0
    calls_lock = threading.Lock()

    def build() -> str:
        nonlocal calls
        with calls_lock:
            calls += 1
        time.sleep(0.05)
        return "shared"

    def worker(results: list[str]) -> None:
        start.wait()
        results.append(cache.get_or_set(("k",), build))

    results: list[str] = []
    threads = [threading.Thread(target=worker, args=(results,)) for _ in range(5)]
    for thread in threads:
        thread.start()
    start.wait()
    for thread in threads:
        thread.join()

    assert results == ["shared"] * 5
    assert calls == 1


def test_single_flight_releases_waiters_when_producer_fails() -> None:
    cache: InMemoryTTLCache[tuple[str], str] = InMemoryTTLCache(ttl_seconds=30)
    producer_entered = threading.Event()
    retry_started = threading.Event()
    errors: list[str] = []
    results: list[str] = []

    def failing_build() -> str:
        producer_entered.set()
        time.sleep(0.05)
        raise RuntimeError("boom")

    def retry_build() -> str:
        retry_started.set()
        return "recovered"

    def failing_worker() -> None:
        try:
            cache.get_or_set(("k",), failing_build)
        except RuntimeError as exc:
            errors.append(str(exc))

    def retry_worker() -> None:
        producer_entered.wait(timeout=1)
        results.append(cache.get_or_set(("k",), retry_build))

    first = threading.Thread(target=failing_worker)
    second = threading.Thread(target=retry_worker)
    first.start()
    second.start()
    first.join(timeout=1)
    second.join(timeout=1)

    assert not first.is_alive()
    assert not second.is_alive()
    assert errors == ["boom"]
    assert retry_started.is_set()
    assert results == ["recovered"]


def test_clear_during_inflight_prevents_stale_writeback() -> None:
    cache: InMemoryTTLCache[tuple[str], str] = InMemoryTTLCache(ttl_seconds=30)
    producer_entered = threading.Event()
    allow_return = threading.Event()

    def build() -> str:
        producer_entered.set()
        allow_return.wait(timeout=1)
        return "stale"

    thread = threading.Thread(target=lambda: cache.get_or_set(("k",), build))
    thread.start()
    assert producer_entered.wait(timeout=1)

    cache.clear()
    allow_return.set()
    thread.join(timeout=1)

    assert not thread.is_alive()
    assert cache.get(("k",)) == (False, None)


def test_invalidate_matching_during_inflight_prevents_stale_writeback() -> None:
    cache: InMemoryTTLCache[tuple[str], str] = InMemoryTTLCache(ttl_seconds=30)
    producer_entered = threading.Event()
    allow_return = threading.Event()

    def build() -> str:
        producer_entered.set()
        allow_return.wait(timeout=1)
        return "stale"

    thread = threading.Thread(target=lambda: cache.get_or_set(("prefix", "k"), build))
    thread.start()
    assert producer_entered.wait(timeout=1)

    cache.invalidate_matching(lambda key: key[0] == "prefix")
    allow_return.set()
    thread.join(timeout=1)

    assert not thread.is_alive()
    assert cache.get(("prefix", "k")) == (False, None)
