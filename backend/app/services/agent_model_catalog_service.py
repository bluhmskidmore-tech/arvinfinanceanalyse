from __future__ import annotations

import json
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Any

from backend.app.agent.schemas.agent_model import AgentModelCatalog, AgentModelOption
from backend.app.agent.schemas.agent_request import AgentQueryRequest
from backend.app.services.hermes_agent_service import (
    _build_hermes_stream_command,
    _build_hermes_stream_env,
)

# Live discovery spawns an external command, so /models must never wait on it
# while a usable answer already exists: a fresh entry is served directly, a
# stale entry is served while a single background refresh runs, and only a
# completely cold cache waits — bounded well below the subprocess timeout.
CATALOG_CACHE_TTL_SECONDS = 60.0
CATALOG_COLD_WAIT_SECONDS = 3.0
_CATALOG_DISCOVERY_TIMEOUT_SECONDS = 12
_CATALOG_LOCK = threading.Lock()


@dataclass(frozen=True)
class _CatalogEntry:
    catalog: AgentModelCatalog
    cached_at: float


_CATALOG_ENTRIES: dict[tuple[str, str, str], _CatalogEntry] = {}
_CATALOG_REFRESHES: dict[tuple[str, str, str], threading.Event] = {}


def _read_hermes_model_catalog(command: str, distro: str, hermes_home: str, cache_minute: int) -> AgentModelCatalog:
    args = _build_hermes_stream_command(command=command, wsl_distro=distro, hermes_home=hermes_home)
    result = subprocess.run(
        [*args, "--catalog"], check=True, capture_output=True, text=True,
        encoding="utf-8", timeout=_CATALOG_DISCOVERY_TIMEOUT_SECONDS,
        env=_build_hermes_stream_env(command=command, hermes_home=hermes_home),
    )
    return AgentModelCatalog.model_validate(json.loads(result.stdout))


def _cached_catalog_entry(key: tuple[str, str, str]) -> _CatalogEntry | None:
    with _CATALOG_LOCK:
        return _CATALOG_ENTRIES.get(key)


def _start_catalog_refresh(key: tuple[str, str, str]) -> threading.Event:
    """Single-flight background discovery; concurrent callers share one run."""
    with _CATALOG_LOCK:
        running = _CATALOG_REFRESHES.get(key)
        if running is not None:
            return running
        event = threading.Event()
        _CATALOG_REFRESHES[key] = event
    threading.Thread(
        target=_refresh_catalog_entry,
        args=(key, event),
        name="agent-model-catalog-refresh",
        daemon=True,
    ).start()
    return event


def _refresh_catalog_entry(key: tuple[str, str, str], event: threading.Event) -> None:
    command, distro, hermes_home = key
    try:
        catalog = _read_hermes_model_catalog(
            command, distro, hermes_home, int(time.monotonic() // 60),
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        # Keep any previous entry: a transient discovery failure must not drop
        # a catalog that is still the best available answer.
        catalog = None
    with _CATALOG_LOCK:
        if catalog is not None:
            _CATALOG_ENTRIES[key] = _CatalogEntry(catalog=catalog, cached_at=time.monotonic())
        _CATALOG_REFRESHES.pop(key, None)
    event.set()


def get_agent_model_catalog(settings: Any) -> AgentModelCatalog:
    provider = str(getattr(settings, "agent_provider", "local") or "local")
    default = str(getattr(settings, f"agent_{provider}_model", "") or "default")
    if provider != "hermes":
        return AgentModelCatalog(provider=provider, default_model=default)
    key = (
        str(settings.agent_hermes_command),
        str(settings.agent_hermes_wsl_distro or ""),
        str(getattr(settings, "agent_hermes_home", "") or ""),
    )
    entry = _cached_catalog_entry(key)
    if entry is None or time.monotonic() - entry.cached_at >= CATALOG_CACHE_TTL_SECONDS:
        refreshed = _start_catalog_refresh(key)
        if entry is None:
            refreshed.wait(CATALOG_COLD_WAIT_SECONDS)
            entry = _cached_catalog_entry(key)
    catalog = (
        entry.catalog.model_copy(deep=True)
        if entry is not None
        else AgentModelCatalog(provider="hermes", default_model=default)
    )
    # The configured model remains usable when discovery is unavailable. Do not
    # invent additional model capabilities or expose provider credential fields.
    if default not in {model.id for model in catalog.models}:
        catalog.models.insert(0, AgentModelOption(id=default, label=default))
    catalog.default_model = default
    return catalog


def validate_agent_model_selection(request: AgentQueryRequest, settings: Any, provider: str) -> AgentQueryRequest:
    if request.model is None and request.reasoning_effort is None:
        return request
    if provider != "hermes" or request.routing_surface != "standalone_workbench":
        raise ValueError("当前入口不支持切换模型或思考程度。")
    catalog = get_agent_model_catalog(settings)
    model_id = request.model or catalog.default_model
    model = next((item for item in catalog.models if item.id == model_id), None)
    if model is None:
        raise ValueError("所选模型当前不可用，请刷新模型列表后重试。")
    effort = request.reasoning_effort
    if effort is not None and effort not in model.reasoning_efforts:
        raise ValueError("所选模型不支持该思考程度，请重新选择。")
    return request.model_copy(update={"model": model.id, "reasoning_effort": effort})
