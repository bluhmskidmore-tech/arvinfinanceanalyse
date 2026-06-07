from __future__ import annotations

import hmac
import hashlib
import json
import os
import secrets
import time
from typing import Any

AGENT_ACTION_TOKEN_PREFIX = "agent_action:"
AGENT_ACTION_TOKEN_VERSION = "v1"
AGENT_ACTION_TOKEN_TTL_SECONDS = 15 * 60
_PROCESS_ACTION_TOKEN_SECRET = secrets.token_hex(32)


def agent_action_confirmation_token(
    *,
    action_type: str,
    label: str,
    payload: dict[str, Any],
    expires_at: int | None = None,
) -> str:
    resolved_expires_at = int(expires_at or (time.time() + AGENT_ACTION_TOKEN_TTL_SECONDS))
    digest = hmac.new(
        _action_token_secret().encode("utf-8"),
        _canonical_action_payload(
            action_type=action_type,
            label=label,
            payload=payload,
            expires_at=resolved_expires_at,
        ).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{AGENT_ACTION_TOKEN_PREFIX}{AGENT_ACTION_TOKEN_VERSION}:{resolved_expires_at}:{digest}"


def agent_action_confirmation_token_matches(
    *,
    token: str,
    action_type: str,
    label: str,
    payload: dict[str, Any],
    now: int | None = None,
) -> bool:
    parsed = _parse_action_confirmation_token(token)
    if parsed is None:
        return False
    expires_at, digest = parsed
    if expires_at < int(now or time.time()):
        return False
    expected = agent_action_confirmation_token(
        action_type=action_type,
        label=label,
        payload=payload,
        expires_at=expires_at,
    )
    return hmac.compare_digest(token, expected) and hmac.compare_digest(
        digest,
        expected.rsplit(":", maxsplit=1)[-1],
    )


def _parse_action_confirmation_token(token: str) -> tuple[int, str] | None:
    prefix = f"{AGENT_ACTION_TOKEN_PREFIX}{AGENT_ACTION_TOKEN_VERSION}:"
    if not token.startswith(prefix):
        return None
    try:
        expires_at_text, digest = token[len(prefix) :].split(":", maxsplit=1)
        expires_at = int(expires_at_text)
    except ValueError:
        return None
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        return None
    return expires_at, digest


def _action_token_secret() -> str:
    return os.environ.get("MOSS_AGENT_ACTION_TOKEN_SECRET", "").strip() or _PROCESS_ACTION_TOKEN_SECRET


def _canonical_action_payload(
    *,
    action_type: str,
    label: str,
    payload: dict[str, Any],
    expires_at: int,
) -> str:
    return json.dumps(
        {
            "type": action_type,
            "label": label,
            "payload": payload,
            "expires_at": expires_at,
        },
        default=str,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
