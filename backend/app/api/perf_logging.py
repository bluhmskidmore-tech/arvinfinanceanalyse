"""Lightweight API timing logs for page-level performance work."""
from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping
from typing import TypeVar

logger = logging.getLogger("backend.app.api.perf")

T = TypeVar("T")


def _mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return value

    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            dumped = model_dump(mode="json")
        except TypeError:
            dumped = model_dump()
        if isinstance(dumped, Mapping):
            return dumped

    return {}


def _result_meta(payload: object) -> Mapping[str, object]:
    if isinstance(payload, Mapping):
        return _mapping(payload.get("result_meta"))
    return _mapping(getattr(payload, "result_meta", None))


def log_api_perf(
    *,
    endpoint: str,
    started_at: float,
    payload: T,
    duckdb_statement_count: int | None = None,
) -> T:
    meta = _result_meta(payload)
    duration_ms = round((time.perf_counter() - started_at) * 1000, 3)
    logger.info(
        "moss_api_perf",
        extra={
            "endpoint": endpoint,
            "duration_ms": duration_ms,
            "trace_id": str(meta.get("trace_id") or ""),
            "result_kind": str(meta.get("result_kind") or ""),
            "duckdb_statement_count": duckdb_statement_count,
        },
    )
    return payload


def timed_api_call(
    endpoint: str,
    producer: Callable[[], T],
    *,
    duckdb_statement_count: int | None = None,
) -> T:
    started_at = time.perf_counter()
    payload = producer()
    return log_api_perf(
        endpoint=endpoint,
        started_at=started_at,
        payload=payload,
        duckdb_statement_count=duckdb_statement_count,
    )
