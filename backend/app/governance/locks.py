from dataclasses import dataclass


@dataclass(frozen=True)
class LockDefinition:
    """Named lock used to serialize critical background operations."""

    key: str
    ttl_seconds: int = 300


MATERIALIZE_LOCK = LockDefinition(key="lock:duckdb:materialize", ttl_seconds=900)
