from __future__ import annotations

import threading
import time

import pytest

from backend.app.observability.response_cache import TTLResponseCache

from backend.app.services.runtime_cache import (
    CacheBuildTimeoutError,
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


@pytest.mark.parametrize("kind", ["runtime", "response", "response_status"])
@pytest.mark.parametrize("error_type", [RuntimeError, BaseException])
def test_single_flight_broadcasts_one_failure_wave(kind, error_type, monkeypatch) -> None:
    cache, read = _cache_reader(kind, wait_timeout_seconds=0.5)
    entered, release, waiting = (threading.Event() for _ in range(3))
    failure = error_type("synthetic dependency failure")
    calls, errors = [], []

    def build():
        calls.append(1)
        entered.set()
        assert release.wait(2)
        raise failure

    def worker():
        try:
            read("k", build)
        except BaseException as exc:
            errors.append(exc)

    first = threading.Thread(target=worker)
    first.start()
    assert entered.wait(1)
    flight = cache._inflight["k"]
    event = getattr(flight, "event", flight)
    original_wait = event.wait
    waiter_count = 0
    count_lock = threading.Lock()

    def track_wait(timeout=None):
        nonlocal waiter_count
        with count_lock:
            waiter_count += 1
            if waiter_count == 7:
                waiting.set()
        return original_wait(timeout)

    monkeypatch.setattr(event, "wait", track_wait)
    threads = [first, *(threading.Thread(target=worker) for _ in range(7))]
    for thread in threads[1:]:
        thread.start()
    try:
        assert waiting.wait(1)
    finally:
        release.set()
        for thread in threads:
            thread.join(2)
    assert all(not thread.is_alive() for thread in threads)
    assert calls == [1]
    assert len(errors) == 8
    assert all(error is failure for error in errors)
    assert read("k", lambda: "recovered") == "recovered"


def _cache_reader(kind, **kwargs):
    if kind == "runtime":
        cache = InMemoryTTLCache(ttl_seconds=30, **kwargs)
        return cache, cache.get_or_set
    cache = TTLResponseCache(default_ttl_seconds=30, **kwargs)
    if kind == "response_status":
        return cache, lambda key, build: cache.get_or_build_with_status(key, build)[0]
    return cache, cache.get_or_build


@pytest.mark.parametrize("kind", ["runtime", "response", "response_status"])
@pytest.mark.parametrize("operation", ["invalidate", "clear", "matching"])
@pytest.mark.parametrize("old_fails", [False, True])
def test_new_generation_never_joins_or_loses_flight_to_old_producer(kind, operation, old_fails):
    cache, read = _cache_reader(kind, wait_timeout_seconds=0.01)
    old_entered, new_entered, old_release, new_release = (threading.Event() for _ in range(4))
    results, errors = [], []

    def build(entered, release, value):
        entered.set()
        assert release.wait(2)
        if value == "old" and old_fails:
            raise RuntimeError("old failure")
        return value

    def worker(entered, release, value):
        try:
            results.append(read("k", lambda: build(entered, release, value)))
        except BaseException as exc:
            errors.append(exc)

    old = threading.Thread(target=worker, args=(old_entered, old_release, "old"))
    new = threading.Thread(target=worker, args=(new_entered, new_release, "new"))
    old.start()
    assert old_entered.wait(1)
    if operation == "clear":
        cache.clear() if kind == "runtime" else cache.invalidate()
    elif operation == "matching" and kind == "runtime":
        cache.invalidate_matching(lambda key: key == "k")
    else:
        cache.invalidate("k")
    new.start()
    try:
        assert new_entered.wait(0.5), "new request joined a pre-invalidation build"
        fresh_flight = cache._inflight["k"]
        old_release.set()
        old.join(1)
        assert cache._inflight["k"] is fresh_flight
        with pytest.raises(TimeoutError):
            read("k", lambda: pytest.fail("timeout removed the active producer"))
    finally:
        old_release.set()
        new_release.set()
        old.join(2)
        new.join(2)
    assert not old.is_alive() and not new.is_alive()
    assert read("k", lambda: "unexpected rebuild") == "new"
    assert len(errors) == int(old_fails)


@pytest.mark.parametrize("kind", ["runtime", "response"])
def test_capacity_expiry_and_inspection_metadata_are_bounded(kind):
    from collections import OrderedDict

    now = [0.0]
    cache, read = _cache_reader(kind, clock=lambda: now[0], max_entries=64, sweep_budget=4)
    for version in range(10000):
        read(f"database-version:{version}", lambda: bytes(1024))
        assert len(cache._store) <= 64
        assert len(cache._expiry_scan) <= 64
    assert set(cache._store) == set(cache._expiry_scan)
    for index in range(200):
        assert read("hot", lambda: "hot value") == "hot value"
        read(f"noise:{index}", lambda: "noise")
    assert "hot" in cache._store

    class NoFullScan(OrderedDict):
        def __iter__(self):
            raise AssertionError("request traversed the complete cache")

        keys = items = values = __iter__

    cache._store = NoFullScan(cache._store)
    cache._expiry_scan = NoFullScan(cache._expiry_scan)
    now[0] = 86400.0
    before = len(cache._store)
    read("new", lambda: "fresh")
    assert before - 8 <= len(cache._store) <= before - 3
    for _ in range(64):
        assert read("new", lambda: pytest.fail("fresh value was lost")) == "fresh"
    assert len(cache._store) == len(cache._expiry_scan) == 1


@pytest.mark.parametrize("kind", ["runtime", "response"])
def test_capacity_eviction_preserves_active_producer(kind):
    cache, read = _cache_reader(kind, max_entries=2, sweep_budget=1, wait_timeout_seconds=0.01)
    entered, release = threading.Event(), threading.Event()

    def build():
        entered.set()
        assert release.wait(2)
        return "active result"

    thread = threading.Thread(target=lambda: read("active", build))
    thread.start()
    assert entered.wait(1)
    flight = cache._inflight["active"]
    try:
        for index in range(100):
            read(str(index), lambda: "other value")
        assert cache._inflight["active"] is flight
        with pytest.raises(TimeoutError):
            read("active", lambda: pytest.fail("active producer was evicted"))
    finally:
        release.set()
        thread.join(2)
    assert read("active", lambda: "unexpected rebuild") == "active result"


@pytest.mark.parametrize("kind", ["runtime", "response", "response_status"])
def test_existing_waiters_keep_their_own_result_after_invalidation(kind, monkeypatch):
    cache, read = _cache_reader(kind)
    entered, release, waiting = (threading.Event() for _ in range(3))
    results = []

    def build():
        entered.set()
        assert release.wait(2)
        return "old result"

    first = threading.Thread(target=lambda: results.append(read("k", build)))
    second = threading.Thread(target=lambda: results.append(read("k", build)))
    first.start()
    assert entered.wait(1)
    event = cache._inflight["k"].event
    original_wait = event.wait

    def observe_wait(timeout=None):
        waiting.set()
        return original_wait(timeout)

    monkeypatch.setattr(event, "wait", observe_wait)
    second.start()
    try:
        assert waiting.wait(1)
        cache.invalidate("k")
        assert read("k", lambda: "new result") == "new result"
    finally:
        release.set()
        first.join(2)
        second.join(2)
    assert results == ["old result", "old result"]
    assert read("k", lambda: "unexpected rebuild") == "new result"


@pytest.mark.parametrize("kind", ["runtime", "response"])
def test_hot_key_overwrites_do_not_accumulate_expiry_metadata(kind):
    now = [0.0]
    cache, read = _cache_reader(kind, clock=lambda: now[0], max_entries=8, sweep_budget=1)
    for version in range(10000):
        now[0] += 0.01
        cache.set("hot", version)
    assert len(cache._store) == len(cache._expiry_scan) == 1
    assert read("hot", lambda: "unexpected rebuild") == 9999
    now[0] += 31
    assert read("hot", lambda: "new value") == "new value"
    assert len(cache._store) == len(cache._expiry_scan) == 1


def test_same_key_waiter_times_out_when_producer_is_stuck() -> None:
    cache: InMemoryTTLCache[tuple[str], str] = InMemoryTTLCache(
        ttl_seconds=30,
        wait_timeout_seconds=0.01,
    )
    producer_entered = threading.Event()
    release_producer = threading.Event()
    waiter_finished = threading.Event()
    third_finished = threading.Event()
    calls = {"count": 0}
    producer_results: list[str] = []
    waiter_errors: list[BaseException] = []
    third_errors: list[BaseException] = []

    def build() -> str:
        calls["count"] += 1
        producer_entered.set()
        assert release_producer.wait(timeout=1.0)
        return "built"

    def producer() -> None:
        producer_results.append(cache.get_or_set(("k",), build))

    def waiter(errors: list[BaseException], finished: threading.Event) -> None:
        try:
            cache.get_or_set(("k",), build)
        except BaseException as exc:  # pragma: no cover - surfaced by assertion below
            errors.append(exc)
        finally:
            finished.set()

    producer_thread = threading.Thread(target=producer)
    waiter_thread = threading.Thread(target=waiter, args=(waiter_errors, waiter_finished))
    third_thread = threading.Thread(target=waiter, args=(third_errors, third_finished))
    producer_thread.start()
    assert producer_entered.wait(timeout=1.0)
    waiter_thread.start()

    try:
        assert waiter_finished.wait(timeout=1.0)
        assert len(waiter_errors) == 1
        assert isinstance(waiter_errors[0], CacheBuildTimeoutError)
        assert "('k',)" in str(waiter_errors[0])
        assert "timed out after 0.01s" in str(waiter_errors[0])

        third_thread.start()
        assert third_finished.wait(timeout=1.0)
        assert len(third_errors) == 1
        assert isinstance(third_errors[0], CacheBuildTimeoutError)
        assert calls["count"] == 1
    finally:
        release_producer.set()
        producer_thread.join(timeout=1.0)
        waiter_thread.join(timeout=1.0)
        third_thread.join(timeout=1.0)

    assert not producer_thread.is_alive()
    assert not waiter_thread.is_alive()
    assert not third_thread.is_alive()
    assert producer_results == ["built"]
    assert cache.get_or_set(("k",), build) == "built"
    assert calls["count"] == 1


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
