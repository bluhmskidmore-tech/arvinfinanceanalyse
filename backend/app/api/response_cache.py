"""Process-local TTL cache for slow read-only page endpoints.

Market/macro home endpoints scan large DuckDB tables on every request, so the
first request can take 30-90s and repeats stay slow. These reads are
observation-basis (not formal MTR writes), so serving a short-lived cached copy
is acceptable. The cache only stores already-built response envelopes; it never
changes how a metric is computed.
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable
from typing import Literal, TypeVar, cast

T = TypeVar("T")
CacheBuildStatus = Literal["produce", "wait", "hit"]

DEFAULT_TTL_SECONDS = 300.0
DEFAULT_WAIT_TIMEOUT_SECONDS = 120.0
_TTL_ENV_VAR = "MOSS_MARKET_HOME_CACHE_TTL_SECONDS"


class CacheBuildTimeoutError(TimeoutError):
    """Raised when a caller waits too long for an in-flight cache build."""

    def __init__(self, key: object, wait_timeout_seconds: float) -> None:
        super().__init__(
            f"timed out after {wait_timeout_seconds:g}s waiting for cache build: {key!r}"
        )


class _InFlightBuild:
    def __init__(self) -> None:
        self.event = threading.Event()
        self.value: object = None
        self.error: BaseException | None = None


def resolve_default_ttl(default: float = DEFAULT_TTL_SECONDS) -> float:
    raw = os.getenv(_TTL_ENV_VAR)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value >= 0 else default


class TTLResponseCache:
    """Thread-safe TTL cache. Builds are run outside the lock so a slow query
    never blocks readers serving other keys."""

    def __init__(
        self,
        *,
        default_ttl_seconds: float = DEFAULT_TTL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
        wait_timeout_seconds: float = DEFAULT_WAIT_TIMEOUT_SECONDS,
    ) -> None:
        self._default_ttl = default_ttl_seconds
        self._clock = clock
        self._wait_timeout_seconds = wait_timeout_seconds
        self._lock = threading.Lock()
        self._store: dict[str, tuple[float, object]] = {}
        self._inflight: dict[str, _InFlightBuild] = {}

    def get_or_build(
        self,
        key: str,
        builder: Callable[[], T],
        *,
        ttl_seconds: float | None = None,
    ) -> T:
        ttl = self._default_ttl if ttl_seconds is None else ttl_seconds
        if ttl <= 0:
            return builder()

        now = self._clock()
        with self._lock:
            entry = self._store.get(key)
            if entry is not None and entry[0] > now:
                return entry[1]  # type: ignore[return-value]
            inflight = self._inflight.get(key)
            if inflight is None:
                inflight = _InFlightBuild()
                self._inflight[key] = inflight
                should_build = True
            else:
                should_build = False

        if not should_build:
            if not inflight.event.wait(timeout=self._wait_timeout_seconds):
                raise CacheBuildTimeoutError(key, self._wait_timeout_seconds)
            if inflight.error is not None:
                raise inflight.error
            return cast(T, inflight.value)

        try:
            value = builder()
        except BaseException as exc:
            with self._lock:
                inflight.error = exc
                self._inflight.pop(key, None)
                inflight.event.set()
            raise

        expires_at = self._clock() + ttl
        with self._lock:
            self._store[key] = (expires_at, value)
            inflight.value = value
            self._inflight.pop(key, None)
            inflight.event.set()
        return value

    def get_or_build_with_status(
        self,
        key: str,
        builder: Callable[[], T],
        *,
        ttl_seconds: float | None = None,
    ) -> tuple[T, CacheBuildStatus]:
        """Return the cached value and the caller's actual cache path.

        This additive API keeps ``get_or_build`` unchanged for existing routes
        while allowing slow endpoints to distinguish a producer from a caller
        waiting on the same in-flight build.
        """
        ttl = self._default_ttl if ttl_seconds is None else ttl_seconds
        if ttl <= 0:
            return builder(), "produce"

        now = self._clock()
        with self._lock:
            entry = self._store.get(key)
            if entry is not None and entry[0] > now:
                return cast(T, entry[1]), "hit"
            inflight = self._inflight.get(key)
            if inflight is None:
                inflight = _InFlightBuild()
                self._inflight[key] = inflight
                should_build = True
            else:
                should_build = False

        if not should_build:
            if not inflight.event.wait(timeout=self._wait_timeout_seconds):
                raise CacheBuildTimeoutError(key, self._wait_timeout_seconds)
            if inflight.error is not None:
                raise inflight.error
            return cast(T, inflight.value), "wait"

        try:
            value = builder()
        except BaseException as exc:
            with self._lock:
                inflight.error = exc
                self._inflight.pop(key, None)
                inflight.event.set()
            raise

        expires_at = self._clock() + ttl
        with self._lock:
            self._store[key] = (expires_at, value)
            inflight.value = value
            self._inflight.pop(key, None)
            inflight.event.set()
        return value, "produce"

    def invalidate(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._store.clear()
            else:
                self._store.pop(key, None)


market_home_response_cache = TTLResponseCache(default_ttl_seconds=resolve_default_ttl())


def market_home_rates_cache_key(duckdb_path: str) -> str:
    return f"market-data/rates::{duckdb_path}"


def market_home_catalog_cache_key(duckdb_path: str) -> str:
    return f"market-data/catalog::{duckdb_path}"


def market_home_choice_latest_cache_key(
    duckdb_path: str,
    category: str | None = None,
) -> str:
    return f"choice-series/latest::{category or 'all'}::{duckdb_path}"


def market_home_macro_analysis_cache_key(
    duckdb_path: str,
    detail: str = "full",
    *,
    history_limit: int | None = None,
) -> str:
    if detail == "full" and history_limit is not None:
        return f"macro-toolkit/analysis::{detail}::{history_limit}::{duckdb_path}"
    return f"macro-toolkit/analysis::{detail}::{duckdb_path}"


def market_home_strategy_summaries_cache_key(duckdb_path: str) -> str:
    return f"macro-toolkit/strategy-summaries::{duckdb_path}"
