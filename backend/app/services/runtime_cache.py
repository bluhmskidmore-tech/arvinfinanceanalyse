from __future__ import annotations

import time
from collections import OrderedDict
from collections.abc import Callable
from threading import Event, Lock
from typing import Generic, TypeVar, cast

from backend.app.repositories.system_read_publication_repo import (
    system_read_cache_identity,
    system_read_original_cache_key,
)

K = TypeVar("K")
V = TypeVar("V")
_T = TypeVar("_T")
_U = TypeVar("_U")

_RUNTIME_CACHES: dict[str, InMemoryTTLCache[object, object]] = {}
_RUNTIME_CACHES_LOCK = Lock()

DEFAULT_WAIT_TIMEOUT_SECONDS = 120.0
DEFAULT_MAX_ENTRIES = 256
DEFAULT_SWEEP_BUDGET = 16


class CacheBuildTimeoutError(TimeoutError):
    """Raised when a caller waits too long for an in-flight cache build."""

    def __init__(self, key: object, wait_timeout_seconds: float) -> None:
        super().__init__(
            f"timed out after {wait_timeout_seconds:g}s waiting for cache build: {key!r}"
        )


class _InFlightBuild:
    def __init__(self, generation: int) -> None:
        self.event = Event()
        self.generation = generation
        self.value: object = None
        self.error: BaseException | None = None


class InMemoryTTLCache(Generic[K, V]):
    """Small process-local TTL cache for read-only service results."""

    def __init__(
        self,
        *,
        ttl_seconds: float,
        clock: Callable[[], float] | None = None,
        wait_timeout_seconds: float = DEFAULT_WAIT_TIMEOUT_SECONDS,
        max_entries: int = DEFAULT_MAX_ENTRIES,
        sweep_budget: int = DEFAULT_SWEEP_BUDGET,
    ) -> None:
        if max_entries < 1 or sweep_budget < 1:
            raise ValueError("max_entries and sweep_budget must be positive")
        self._store: OrderedDict[K, tuple[float, V]] = OrderedDict()
        self._expiry_scan: OrderedDict[K, None] = OrderedDict()
        self._inflight: dict[K, _InFlightBuild] = {}
        self._max_entries = max_entries
        self._sweep_budget = sweep_budget
        self._lock = Lock()
        self._ttl_seconds = ttl_seconds
        self._clock = clock or time.monotonic
        self._wait_timeout_seconds = wait_timeout_seconds
        self._generation = 0

    def _sweep_locked(self, now: float) -> None:
        # A unique-key rotation stays bounded even when a hot entry is replaced
        # repeatedly; reads never walk every cached response to find expiry.
        for _ in range(min(self._sweep_budget, len(self._expiry_scan))):
            key, _ = self._expiry_scan.popitem(last=False)
            entry = self._store.get(key)
            if entry is not None and now - entry[0] < self._ttl_seconds:
                self._expiry_scan[key] = None
            else:
                self._store.pop(key, None)

    def _store_locked(self, key: K, value: V, now: float) -> None:
        self._store[key] = (now, value)
        self._store.move_to_end(key)
        self._expiry_scan[key] = None
        if len(self._store) > self._max_entries:
            evicted, _ = self._store.popitem(last=False)
            self._expiry_scan.pop(evicted, None)

    def get(self, key: K) -> tuple[bool, V | None]:
        key = cast(K, system_read_cache_identity(key))
        now = self._clock()
        with self._lock:
            self._sweep_locked(now)
            entry = self._store.get(key)
            if entry is None:
                return False, None
            cached_at, value = entry
            if now - cached_at < self._ttl_seconds:
                self._store.move_to_end(key)
                return True, value
            self._store.pop(key, None)
            self._expiry_scan.pop(key, None)
            return False, None

    def generation(self) -> int:
        with self._lock:
            return self._generation

    def set(self, key: K, value: V, *, generation: int | None = None) -> None:
        key = cast(K, system_read_cache_identity(key))
        with self._lock:
            now = self._clock()
            self._sweep_locked(now)
            if generation is None or generation == self._generation:
                self._store_locked(key, value, now)

    def get_or_set(self, key: K, producer: Callable[[], V]) -> V:
        key = cast(K, system_read_cache_identity(key))
        now = self._clock()
        with self._lock:
            self._sweep_locked(now)
            entry = self._store.get(key)
            if entry is not None:
                cached_at, value = entry
                if now - cached_at < self._ttl_seconds:
                    self._store.move_to_end(key)
                    return value
                self._store.pop(key, None)
                self._expiry_scan.pop(key, None)

            inflight = self._inflight.get(key)
            should_build = inflight is None or inflight.generation != self._generation
            if should_build:
                inflight = _InFlightBuild(self._generation)
                self._inflight[key] = inflight

        assert inflight is not None
        if not should_build:
            if not inflight.event.wait(timeout=self._wait_timeout_seconds):
                raise CacheBuildTimeoutError(key, self._wait_timeout_seconds)
            if inflight.error is not None:
                raise inflight.error
            return cast(V, inflight.value)

        try:
            value = producer()
        except BaseException as exc:
            with self._lock:
                inflight.error = exc
                if self._inflight.get(key) is inflight:
                    self._inflight.pop(key, None)
                inflight.event.set()
            raise

        with self._lock:
            now = self._clock()
            self._sweep_locked(now)
            if self._inflight.get(key) is inflight:
                if self._generation == inflight.generation:
                    self._store_locked(key, value, now)
                self._inflight.pop(key, None)
            inflight.value = value
            inflight.event.set()
        return value

    def invalidate(self, key: K) -> None:
        key = cast(K, system_read_cache_identity(key))
        with self._lock:
            self._generation += 1
            self._store.pop(key, None)
            self._expiry_scan.pop(key, None)
            self._inflight.pop(key, None)

    def invalidate_matching(self, predicate: Callable[[K], bool]) -> None:
        def matches(stored_key: K) -> bool:
            original_key = system_read_original_cache_key(stored_key)
            return predicate(cast(K, original_key))

        with self._lock:
            invalidated = False
            for key in list(self._store):
                if matches(key):
                    self._store.pop(key, None)
                    self._expiry_scan.pop(key, None)
                    invalidated = True
            if not invalidated:
                invalidated = any(matches(key) for key in self._inflight)
            if invalidated:
                self._generation += 1

    def clear(self) -> None:
        with self._lock:
            self._generation += 1
            self._store.clear()
            self._expiry_scan.clear()
            # Existing waiters retain their build object and receive its result;
            # callers arriving after clear must create a new generation.
            self._inflight.clear()


def get_runtime_cache(
    name: str,
    *,
    ttl_seconds: float,
    clock: Callable[[], float] | None = None,
) -> InMemoryTTLCache[_T, _U]:
    normalized = str(name or "").strip()
    if not normalized:
        raise ValueError("runtime cache name must be non-empty")

    with _RUNTIME_CACHES_LOCK:
        cache = _RUNTIME_CACHES.get(normalized)
        if cache is None:
            cache = InMemoryTTLCache[object, object](
                ttl_seconds=ttl_seconds,
                clock=clock,
            )
            _RUNTIME_CACHES[normalized] = cache
        return cast(InMemoryTTLCache[_T, _U], cache)


def clear_runtime_cache(name: str) -> None:
    with _RUNTIME_CACHES_LOCK:
        cache = _RUNTIME_CACHES.get(str(name or "").strip())
    if cache is not None:
        cache.clear()


def clear_runtime_caches() -> None:
    with _RUNTIME_CACHES_LOCK:
        caches = list(_RUNTIME_CACHES.values())
    for cache in caches:
        cache.clear()
