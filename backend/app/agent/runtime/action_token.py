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

# 服务端确认目录：命中的 suggested-action type 一律要求有效确认 token，
# 不再依赖客户端提交的 requires_confirmation 声明。当前覆盖全部签发点：
# - analysis_view_tool: execute_intent / inspect_drill
# - research_radar_service: inspect_news_events
# 目录只允许收紧（新增条目）；移除条目需给出评审记录。
CONFIRMATION_REQUIRED_ACTION_TYPES: frozenset[str] = frozenset(
    {
        "execute_intent",
        "inspect_drill",
        "inspect_news_events",
    }
)


def action_requires_server_confirmation(action_type: str) -> bool:
    return str(action_type or "").strip().lower() in CONFIRMATION_REQUIRED_ACTION_TYPES


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
    """HMAC secret 解析顺序：governance settings -> 环境变量 -> 进程本地随机值。

    settings 字段 agent_action_token_secret 本身经 MOSS_ 前缀读取同名环境变量，
    直接读 env 的分支保留给 settings 缓存早于环境注入的场景（保持既有行为）。
    未配置任何 secret 时回退进程本地随机值——仅单进程可用，跨进程
    （API 进程签发、worker 进程校验或反之）必须显式配置同一 secret。
    """
    return (
        _configured_action_token_secret()
        or os.environ.get("MOSS_AGENT_ACTION_TOKEN_SECRET", "").strip()
        or _PROCESS_ACTION_TOKEN_SECRET
    )


def _configured_action_token_secret() -> str:
    try:
        from backend.app.governance.settings import get_settings

        return str(getattr(get_settings(), "agent_action_token_secret", "") or "").strip()
    except Exception:
        # 治理配置不可用时回退 env/进程本地链路，token 签发与校验保持可用。
        return ""


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
