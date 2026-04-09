import dramatiq

from backend.app.governance.locks import MATERIALIZE_LOCK


@dramatiq.actor
def materialize_cache_view() -> dict[str, object]:
    """Single write entrypoint for future DuckDB materialize work."""
    return {"status": "scheduled", "lock": MATERIALIZE_LOCK.key}
