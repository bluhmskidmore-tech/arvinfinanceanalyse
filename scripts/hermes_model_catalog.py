"""Read model capabilities inside the configured Hermes runtime; emit no credentials."""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

REASONING_EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra")

# Official text API models, checked 2026-09-06. Only expose providers whose
# credentials are configured in the same Hermes profile used for inference.
# https://platform.minimax.io/docs/api-reference/text-openai-api
# https://api-docs.deepseek.com/guides/thinking_mode/
PROVIDER_CHAT_MODELS = {
    "minimax": (
        {"id": "MiniMax-M3", "label": "MiniMax M3", "reasoning_efforts": [], "default_reasoning_effort": None},
    ),
    "deepseek": (
        {"id": "deepseek-v4-flash", "label": "DeepSeek V4 Flash", "reasoning_efforts": ["none", "low", "high", "max"], "default_reasoning_effort": "low"},
        {"id": "deepseek-v4-pro", "label": "DeepSeek V4 Pro", "reasoning_efforts": ["none", "low", "high", "max"], "default_reasoning_effort": "low"},
    ),
}


def provider_for_chat_model(model: str) -> str | None:
    return next((provider for provider, models in PROVIDER_CHAT_MODELS.items()
                 if any(item["id"] == model for item in models)), None)


def configured_provider_models() -> list[dict[str, Any]]:
    from hermes_cli.auth import resolve_api_key_provider_credentials

    models = []
    for provider, entries in PROVIDER_CHAT_MODELS.items():
        try:
            credentials = resolve_api_key_provider_credentials(provider)
        except Exception as exc:
            # A provider credential error must not hide the other providers.
            # Exception messages can contain credentials; record only the class.
            logging.getLogger(__name__).warning(
                "Provider model catalog unavailable for %s (%s)",
                provider,
                type(exc).__name__,
            )
            continue
        if credentials.get("api_key"):
            models.extend({**entry, "reasoning_efforts": list(entry["reasoning_efforts"])} for entry in entries)
    return models


def normalize_model_entries(entries: list[Any]) -> list[dict[str, Any]]:
    models = []
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("visibility") in {"hide", "hidden"}:
            continue
        model = str(entry.get("slug") or "").strip()
        if model in seen or len(model) > 256 or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._:/-]*", model):
            continue
        seen.add(model)
        supported = {
            item.get("effort") for item in entry.get("supported_reasoning_levels", [])
            if isinstance(item, dict)
        }
        efforts = [effort for effort in REASONING_EFFORTS if effort in supported]
        default = entry.get("default_reasoning_level")
        models.append({
            "id": model,
            "label": str(entry.get("display_name") or model)[:128],
            "reasoning_efforts": efforts,
            "default_reasoning_effort": default if default in efforts else (efforts[0] if efforts else None),
        })
        if len(models) == 100:
            break
    return models


def load_model_catalog() -> dict[str, Any]:
    from hermes_cli.config import load_config_readonly

    config = load_config_readonly()
    model_config = config.get("model") or {}
    provider = str(model_config.get("provider") or "") if isinstance(model_config, dict) else ""
    default = str(model_config.get("default") or "") if isinstance(model_config, dict) else str(model_config)
    entries: list[Any] = []
    source = "configured"
    if provider == "openai-codex":
        try:
            import httpx
            from hermes_cli.auth import resolve_codex_runtime_credentials
            from hermes_cli.codex_models import _extract_chatgpt_account_id

            credentials = resolve_codex_runtime_credentials(refresh_if_expiring=True)
            token = credentials.get("api_key")
            if token:
                headers = {"Authorization": f"Bearer {token}"}
                account_id = _extract_chatgpt_account_id(token)
                if account_id:
                    headers["ChatGPT-Account-Id"] = account_id
                response = httpx.get(
                    "https://chatgpt.com/backend-api/codex/models?client_version=1.0.0",
                    headers=headers, timeout=5,
                )
                response.raise_for_status()
                entries = response.json().get("models", [])
                source = "live"
        except Exception:
            # Runtime credentials and upstream errors stay inside this process.
            entries = []
        if not entries:
            try:
                codex_dir = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
                entries = json.loads((codex_dir / "models_cache.json").read_text(encoding="utf-8")).get("models", [])
                source = "cache"
            except (OSError, ValueError):
                entries = []
    models = normalize_model_entries(entries)
    if not models and default:
        models = [{"id": default, "label": default, "reasoning_efforts": [], "default_reasoning_effort": None}]
        source = "configured"
    existing_ids = {model["id"] for model in models}
    provider_models = [model for model in configured_provider_models() if model["id"] not in existing_ids]
    models = models[:100 - len(provider_models)] + provider_models
    return {"provider": provider or "hermes", "default_model": default, "models": models, "source": source}
