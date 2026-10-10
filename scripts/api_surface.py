"""Shared definition of the backend API "surface" for contract tooling.

A surface pins the feature flags that decide which routers get registered, so
that `backend_api_inventory.py` and `api_contract_check.py` describe the same
API on every machine regardless of the developer's local `config/.env`.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager

# 'current' deliberately keeps the ambient environment: it is the only surface
# that answers "what does *this* box serve right now", and it is never used for
# committed artifacts.
SURFACE_AGENT_OVERRIDES: dict[str, str | None] = {
    "default": "false",
    "current": None,
    "full": "true",
}
SURFACE_CHOICES: tuple[str, ...] = tuple(SURFACE_AGENT_OVERRIDES)
REGISTRY_FEATURE_FLAGS: dict[str, str] = {
    "agent": "MOSS_AGENT_ENABLED",
}
SURFACE_HELP = (
    "Route surface to inspect: 'default' forces the release-default Agent-off surface, "
    "'current' honors the current environment, and 'full' enables all known "
    "registration feature flags."
)


def reset_backend_api_import_state() -> None:
    """Drop cached settings and router modules so the next import re-reads the flags."""
    settings_module = sys.modules.get("backend.app.governance.settings")
    get_settings = getattr(settings_module, "get_settings", None)
    cache_clear = getattr(get_settings, "cache_clear", None)
    if callable(cache_clear):
        cache_clear()

    for module_name in tuple(sys.modules):
        if (
            module_name == "backend.app.main"
            or module_name == "backend.app.api"
            or module_name.startswith("backend.app.api.")
        ):
            sys.modules.pop(module_name, None)


@contextmanager
def surface_environment(surface: str) -> Iterator[None]:
    """Pin the feature-flag environment for `surface` and restore it afterwards."""
    if surface not in SURFACE_AGENT_OVERRIDES:
        raise ValueError(f"Unknown surface: {surface}")

    original_agent_enabled = os.environ.get("MOSS_AGENT_ENABLED")
    override = SURFACE_AGENT_OVERRIDES[surface]
    if override is not None:
        os.environ["MOSS_AGENT_ENABLED"] = override
    reset_backend_api_import_state()
    try:
        yield
    finally:
        if original_agent_enabled is None:
            os.environ.pop("MOSS_AGENT_ENABLED", None)
        else:
            os.environ["MOSS_AGENT_ENABLED"] = original_agent_enabled
        reset_backend_api_import_state()
