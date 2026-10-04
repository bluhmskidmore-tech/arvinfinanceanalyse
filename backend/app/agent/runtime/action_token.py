from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from typing import Any

logger = logging.getLogger(__name__)

AGENT_ACTION_TOKEN_PREFIX = "agent_action:"
AGENT_ACTION_TOKEN_VERSION = "v1"
AGENT_ACTION_TOKEN_TTL_SECONDS = 15 * 60
_PROCESS_ACTION_TOKEN_SECRET = secrets.token_hex(32)
_PROCESS_LOCAL_SECRET_WARNING_EMITTED = False

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


def confirmation_scope_user_id(payload: dict[str, Any]) -> str:
    """提取 payload 内受 HMAC 保护的签发用户（confirmation_scope.user_id）。

    scope 缺失、非 dict 或 user_id 为空时返回空串；调用方一律按
    "未绑定用户的 payload" 处理（签发拒发、校验判不匹配）。
    """
    scope = payload.get("confirmation_scope")
    if not isinstance(scope, dict):
        return ""
    return str(scope.get("user_id") or "").strip()


def agent_action_confirmation_token(
    *,
    action_type: str,
    label: str,
    payload: dict[str, Any],
    expires_at: int | None = None,
) -> str:
    # fail-closed：无用户绑定的 token 可被任何用户在 TTL 内重放冒用，拒绝签发。
    # user_id 位于 payload 内，随既有摘要一起被 HMAC 覆盖，无需改摘要算法。
    if not confirmation_scope_user_id(payload):
        raise RuntimeError(
            "agent action confirmation token requires a non-empty "
            "payload.confirmation_scope.user_id; refusing to issue an unbound "
            "token (fail-closed). Ensure the request context carries the "
            "authenticated user_id."
        )
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
    try:
        secret = _action_token_secret()
    except RuntimeError:
        raise PermissionError(
            "MOSS_AGENT_ACTION_TOKEN_SECRET or a known non-production environment is required; "
            "refusing to validate action confirmation tokens."
        ) from None
    parsed = _parse_action_confirmation_token(token)
    if parsed is None:
        return False
    expires_at, digest = parsed
    if expires_at < int(now or time.time()):
        return False
    # 无用户绑定的 payload 不存在合法 token（签发侧 fail-closed 拒发），
    # 直接判不匹配；旧无 scope token 的兼容放行随之移除（TTL 15 分钟内自然到期）。
    if not confirmation_scope_user_id(payload):
        return False
    expected_digest = hmac.new(
        secret.encode("utf-8"),
        _canonical_action_payload(
            action_type=action_type,
            label=label,
            payload=payload,
            expires_at=expires_at,
        ).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    expected = f"{AGENT_ACTION_TOKEN_PREFIX}{AGENT_ACTION_TOKEN_VERSION}:{expires_at}:{expected_digest}"
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
    未配置任何 secret 时：production 或未知环境 fail-closed；已知非生产
    环境保留进程本地随机值（仅单进程可用）。配置读取失败仅允许显式 env secret。
    """
    environment_secret = os.environ.get("MOSS_AGENT_ACTION_TOKEN_SECRET", "").strip()
    try:
        from backend.app.governance.settings import get_settings

        settings = get_settings()
        configured_secret = str(getattr(settings, "agent_action_token_secret", "") or "").strip()
        environment = str(getattr(settings, "environment", "") or "").strip().lower()
    except Exception:  # noqa: BLE001 -- configuration failures must reject safely without exposing secret-bearing exception details.
        # Configuration errors may contain secret values. Preserve no original
        # exception text and allow only an explicitly configured environment key.
        if environment_secret:
            return environment_secret
        raise RuntimeError(
            "Action token configuration is unavailable; configure "
            "MOSS_AGENT_ACTION_TOKEN_SECRET before issuing confirmation tokens."
        ) from None
    if configured_secret:
        return configured_secret
    if environment_secret:
        return environment_secret
    if environment not in {"development", "staging", "test"}:
        raise RuntimeError(
            "MOSS_AGENT_ACTION_TOKEN_SECRET must be configured in production or an unknown environment; "
            "refusing to use a process-local action token secret."
        )
    _warn_process_local_secret_once()
    return _PROCESS_ACTION_TOKEN_SECRET


def _warn_process_local_secret_once() -> None:
    global _PROCESS_LOCAL_SECRET_WARNING_EMITTED

    if _PROCESS_LOCAL_SECRET_WARNING_EMITTED:
        return
    _PROCESS_LOCAL_SECRET_WARNING_EMITTED = True
    logger.warning(
        "未配置 MOSS_AGENT_ACTION_TOKEN_SECRET，development 正在使用进程本地随机 secret；"
        "多进程部署将导致确认 token 跨进程校验失败，production 必须配置 "
        "MOSS_AGENT_ACTION_TOKEN_SECRET"
    )


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
