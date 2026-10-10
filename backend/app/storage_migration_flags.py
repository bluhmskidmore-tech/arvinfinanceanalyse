"""Independent migration and readiness flags for API/worker startup."""

from __future__ import annotations

import os

_TRUTHY_VALUES = frozenset({"1", "true", "yes"})
_READINESS_SKIP_ENV = "MOSS_SKIP_STORAGE_READINESS_CHECKS"
_READINESS_SKIP_ALLOWED_ENVIRONMENTS = frozenset({"development", "test"})


def _env_flag_enabled(key: str) -> bool:
    return os.environ.get(key, "").strip().lower() in _TRUTHY_VALUES


def skip_auto_storage_migrations() -> bool:
    """Return whether all automatic startup storage migrations are disabled."""

    return _env_flag_enabled("MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS")


def skip_postgres_migrations() -> bool:
    """Return whether automatic PostgreSQL migrations are disabled."""

    return skip_auto_storage_migrations() or _env_flag_enabled(
        "MOSS_SKIP_POSTGRES_MIGRATIONS"
    )


def skip_storage_readiness_checks(*, environment: str) -> bool:
    """Allow explicit readiness bypasses only in development and test environments."""

    if not _env_flag_enabled(_READINESS_SKIP_ENV):
        return False

    normalized_environment = str(environment or "").strip().lower()
    if normalized_environment not in _READINESS_SKIP_ALLOWED_ENVIRONMENTS:
        raise RuntimeError(
            f"{_READINESS_SKIP_ENV} may only be enabled in development or test; "
            f"got environment={normalized_environment or '<empty>'!r}"
        )
    return True
