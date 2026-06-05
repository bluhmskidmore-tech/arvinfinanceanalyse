from __future__ import annotations

import time
from collections.abc import Callable
from threading import Event, Lock
from typing import Generic, TypeVar, cast

K = TypeVar("K")
V = TypeVar("V")
_T = TypeVar("_T")
_U = TypeVar("_U")

_RUNTIME_CACHES: dict[str, InMemoryTTLCache[object, object]] = {}
_RUNTIME_CACHES_LOCK = Lock()


class InMemoryTTLCache(Generic[K, V]):
    """Small process-local TTL cache for read-only service results."""

    def __init__(
        self,
        *,
        ttl_seconds: float,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._store: dict[K, tuple[float, V]] = {}
        self._inflight: dict[K, Event] = {}
        self._lock = Lock()
        self._ttl_seconds = ttl_seconds
        self._clock = clock or time.monotonic
        self._generation = 0

    def get(self, key: K) -> tuple[bool, V | None]:
        now = self._clock()
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return False, None
            cached_at, value = entry
            if now - cached_at < self._ttl_seconds:
                return True, value
            self._store.pop(key, None)
            return False, None

    def set(self, key: K, value: V) -> None:
        with self._lock:
            self._store[key] = (self._clock(), value)

    def get_or_set(self, key: K, producer: Callable[[], V]) -> V:
        producer_generation = 0
        while True:
            now = self._clock()
            with self._lock:
                entry = self._store.get(key)
                if entry is not None:
                    cached_at, value = entry
                    if now - cached_at < self._ttl_seconds:
                        return value
                    self._store.pop(key, None)

                inflight = self._inflight.get(key)
                if inflight is None:
                    inflight = Event()
                    self._inflight[key] = inflight
                    producer_generation = self._generation
                    break

            inflight.wait()

        try:
            value = producer()
        except Exception:
            with self._lock:
                self._inflight.pop(key, None)
                inflight.set()
            raise

        with self._lock:
            if self._generation == producer_generation:
                self._store[key] = (self._clock(), value)
            self._inflight.pop(key, None)
            inflight.set()
        return value

    def invalidate(self, key: K) -> None:
        with self._lock:
            self._generation += 1
            self._store.pop(key, None)

    def invalidate_matching(self, predicate: Callable[[K], bool]) -> None:
        with self._lock:
            invalidated = False
            for key in list(self._store):
                if predicate(key):
                    self._store.pop(key, None)
                    invalidated = True
            if not invalidated:
                invalidated = any(predicate(key) for key in self._inflight)
            if invalidated:
                self._generation += 1

    def clear(self) -> None:
        with self._lock:
            self._generation += 1
            self._store.clear()


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
