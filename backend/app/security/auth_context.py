from __future__ import annotations

import logging
import os
import sys
import time
from dataclasses import dataclass
from threading import Lock
from typing import Annotated
from urllib.parse import unquote, urlparse

from backend.app.governance.settings import Settings
from backend.app.repositories.user_scope_repo import UserScopeRepository
from backend.app.security.route_policy import (
    HIGH_RISK_SCOPE_ACTIONS,
    POLICY_SCOPE_SEMANTICS,
    role_meets_policy_class,
)
from backend.app.security.local_access import is_local_hostname, local_origin
from fastapi import Header, Request

logger = logging.getLogger(__name__)

DEFAULT_AUTH_USER_ID = "anonymous"
DEFAULT_AUTH_ROLE = "viewer"
ROLE_HEADER_TRUST_ENV = "MOSS_AUTH_TRUST_X_USER_ROLE_FOR_DEV_TEST"
# Repository-shipped weak credentials that must never survive into a
# non-development deployment (checked by validate_auth_startup_guardrails).
_REPO_DEFAULT_POSTGRES_CREDENTIALS = ("moss", "moss")
_REPO_DEFAULT_MINIO_CREDENTIAL = "minioadmin"
SCOPE_DECISION_CACHE_TTL_ENV = "MOSS_AUTH_SCOPE_CACHE_TTL_SECONDS"
_DEFAULT_SCOPE_DECISION_CACHE_TTL_SECONDS = 30.0
_SCOPE_DECISION_CACHE_MAX_ENTRIES = 4096
_USER_SCOPE_REPO_CACHE: dict[tuple[object, str], UserScopeRepository] = {}
_USER_SCOPE_REPO_CACHE_LOCK = Lock()
_SCOPE_DECISION_CACHE: dict[tuple[object, ...], float] = {}
_SCOPE_DECISION_CACHE_LOCK = Lock()


@dataclass(frozen=True)
class AuthContext:
    user_id: str = DEFAULT_AUTH_USER_ID
    role: str = DEFAULT_AUTH_ROLE
    identity_source: str = "fallback"
    # Populated from the inbound Request's client address (when available) so
    # that development-only fallback-read decisions in api/deps.py can require
    # a loopback caller. ``Request`` default is intentionally the bare class
    # (not ``Request | None``) with a ``None`` default: this is the pattern
    # FastAPI recognizes for auto-injecting the real request via Depends,
    # while still letting non-HTTP callers (unit tests, scripts) call this
    # function directly without a request.
    client_host: str | None = None


def get_auth_context(
    request: Request = None,  # type: ignore[assignment]
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_user_role: Annotated[str | None, Header(alias="X-User-Role")] = None,
) -> AuthContext:
    header_user_id = (x_user_id or "").strip()
    env_user_id = os.environ.get("MOSS_USER_ID", "").strip()

    if _header_trust_enabled() and header_user_id:
        user_id = header_user_id
        identity_source = "header"
    elif env_user_id:
        user_id = env_user_id
        identity_source = "env"
    else:
        user_id = DEFAULT_AUTH_USER_ID
        identity_source = "fallback"

    header_user_role = (x_user_role or "").strip()
    env_user_role = os.environ.get("MOSS_USER_ROLE", "").strip()

    if _header_trust_enabled() and header_user_role:
        role = header_user_role
    else:
        role = env_user_role or DEFAULT_AUTH_ROLE

    client_host = getattr(getattr(request, "client", None), "host", None)
    return AuthContext(user_id=user_id, role=role, identity_source=identity_source, client_host=client_host)


def ensure_user_allowed(
    *,
    auth: AuthContext,
    settings: Settings,
    resource: str,
    action: str,
    scope_key: str | None = None,
    scope_value: str | None = None,
) -> None:
    dsn = settings.governance_sql_dsn or settings.postgres_dsn
    cache_key = (
        str(dsn or "").strip(),
        auth.user_id,
        auth.role,
        resource,
        action,
        scope_key,
        scope_value,
    )
    cache_allowed = action.strip().casefold() not in HIGH_RISK_SCOPE_ACTIONS
    ttl_seconds = _scope_decision_cache_ttl_seconds()
    if cache_allowed and _scope_decision_cache_get(cache_key, ttl_seconds):
        _warn_on_admin_policy_role_mismatch(auth=auth, resource=resource, action=action)
        return
    try:
        repo = _get_user_scope_repository(dsn)
        allowed = bool(
            repo.has_permission(
                user_id=auth.user_id,
                role=auth.role,
                resource=resource,
                action=action,
                scope_key=scope_key,
                scope_value=scope_value,
            )
        )
    except Exception as exc:
        raise RuntimeError("User scope store is unavailable.") from exc
    if allowed:
        _warn_on_admin_policy_role_mismatch(auth=auth, resource=resource, action=action)
        # Only allow decisions are cached: a fresh grant takes effect immediately,
        # while a revoke is delayed by at most the TTL window. High-risk actions
        # bypass this cache so revocations take effect on the next check.
        if cache_allowed:
            _scope_decision_cache_set(cache_key, ttl_seconds)
        return
    raise PermissionError(f"User is not allowed to {action} {resource}.")


def _warn_on_admin_policy_role_mismatch(*, auth: AuthContext, resource: str, action: str) -> None:
    policy = POLICY_SCOPE_SEMANTICS.get((resource.strip(), action.strip()))
    if policy is None or policy.policy_class != "admin":
        return
    if role_meets_policy_class(auth.role, policy.policy_class):
        return
    # 告警模式：保留存量例外，观察一个周期后再升级为拒绝。
    logger.warning(
        "Authorization policy warning: low role matched admin scope "
        "user=%s role=%s resource=%s action=%s",
        auth.user_id,
        auth.role,
        resource,
        action,
        extra={
            "user_id": auth.user_id,
            "role": auth.role,
            "resource": resource,
            "action": action,
        },
    )


def _scope_decision_cache_ttl_seconds() -> float:
    raw = os.environ.get(SCOPE_DECISION_CACHE_TTL_ENV, "").strip()
    if not raw:
        return _DEFAULT_SCOPE_DECISION_CACHE_TTL_SECONDS
    try:
        return max(float(raw), 0.0)
    except ValueError:
        return _DEFAULT_SCOPE_DECISION_CACHE_TTL_SECONDS


def _scope_decision_cache_get(key: tuple[object, ...], ttl_seconds: float) -> bool:
    if ttl_seconds <= 0:
        return False
    now = time.monotonic()
    with _SCOPE_DECISION_CACHE_LOCK:
        expires_at = _SCOPE_DECISION_CACHE.get(key)
        if expires_at is None:
            return False
        if now >= expires_at:
            _SCOPE_DECISION_CACHE.pop(key, None)
            return False
        return True


def _scope_decision_cache_set(key: tuple[object, ...], ttl_seconds: float) -> None:
    if ttl_seconds <= 0:
        return
    with _SCOPE_DECISION_CACHE_LOCK:
        if len(_SCOPE_DECISION_CACHE) >= _SCOPE_DECISION_CACHE_MAX_ENTRIES:
            _SCOPE_DECISION_CACHE.clear()
        _SCOPE_DECISION_CACHE[key] = time.monotonic() + ttl_seconds


def reset_scope_decision_cache() -> None:
    """Clear cached allow/deny decisions (used by tests and grant workflows)."""
    with _SCOPE_DECISION_CACHE_LOCK:
        _SCOPE_DECISION_CACHE.clear()


def _get_user_scope_repository(dsn: str) -> UserScopeRepository:
    repo_cls = UserScopeRepository
    key = (repo_cls, str(dsn or "").strip())
    with _USER_SCOPE_REPO_CACHE_LOCK:
        cached = _USER_SCOPE_REPO_CACHE.get(key)
        if cached is not None:
            return cached

    repo = repo_cls(key[1])

    with _USER_SCOPE_REPO_CACHE_LOCK:
        return _USER_SCOPE_REPO_CACHE.setdefault(key, repo)


def _header_trust_enabled() -> bool:
    return os.environ.get(ROLE_HEADER_TRUST_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def _uses_repo_default_postgres_credentials(dsn: object) -> bool:
    parsed = urlparse(str(dsn or "").strip())
    if parsed.scheme.split("+", maxsplit=1)[0].lower() not in {"postgres", "postgresql"}:
        return False
    credentials = (unquote(parsed.username or ""), unquote(parsed.password or ""))
    return credentials == _REPO_DEFAULT_POSTGRES_CREDENTIALS


def _cors_has_wildcard_origin(settings: Settings) -> bool:
    cors_origins = [origin.strip() for origin in str(settings.cors_origins or "").split(",") if origin.strip()]
    return "*" in cors_origins


def _postgres_dsn_uses_weak_credentials(settings: Settings) -> bool:
    dsn_candidates = {
        str(settings.postgres_dsn or "").strip(),
        str(settings.governance_sql_dsn or "").strip(),
    }
    return any(_uses_repo_default_postgres_credentials(dsn) for dsn in dsn_candidates)


def _minio_uses_weak_credentials(settings: Settings) -> bool:
    # minioadmin is only material when the object store actually talks to MinIO;
    # local archive mode never presents these credentials to any service.
    object_store_mode = str(settings.object_store_mode or "").strip().lower()
    if object_store_mode == "local":
        return False
    minio_credentials = {
        str(settings.minio_access_key or "").strip(),
        str(settings.minio_secret_key or "").strip(),
    }
    return _REPO_DEFAULT_MINIO_CREDENTIAL in minio_credentials


def _env_identity_source_configured() -> bool:
    return bool(os.environ.get("MOSS_USER_ID", "").strip() or os.environ.get("MOSS_USER_ROLE", "").strip())


def _log_development_security_banner(settings: Settings) -> None:
    header_trust_active = _header_trust_enabled()
    env_identity_active = _env_identity_source_configured()
    wildcard_cors_configured = _cors_has_wildcard_origin(settings)
    weak_postgres_credentials = _postgres_dsn_uses_weak_credentials(settings)
    weak_minio_credentials = _minio_uses_weak_credentials(settings)
    agent_dev_bypass = bool(getattr(settings, "agent_dev_scope_bypass", False))
    local_only_api = settings.local_only_api

    lines = [
        "=" * 78,
        "MOSS 启动安全横幅 | environment=development | "
        f"本机入口政策{'已启用' if local_only_api else '未启用'}：",
        "  - header trust 拦截 (X-User-Id/X-User-Role 头信任开关校验): "
        f"{'应用启动禁止开启' if local_only_api else '关闭'}"
        f"（当前 {ROLE_HEADER_TRUST_ENV}={'已启用' if header_trust_active else '未启用'}）",
        "  - env 身份源拦截 (MOSS_USER_ID/MOSS_USER_ROLE 禁用校验): 关闭"
        f"（当前{'已设置' if env_identity_active else '未设置'}）",
        "  - CORS 白名单强制 (禁止通配符 *): "
        f"{'来源限本机，跨源响应沿用白名单' if local_only_api else '关闭'}"
        f"（当前 cors_origins {'包含通配符 *' if wildcard_cors_configured else '未包含通配符'}）",
        "  - 弱默认凭据拦截 (postgres moss:moss / minio minioadmin): 关闭"
        f"（当前 postgres: {'疑似使用默认凭据' if weak_postgres_credentials else '非默认凭据'}，"
        f"minio: {'疑似使用默认凭据' if weak_minio_credentials else '非默认凭据或未生效'}）",
        "  - dev fallback 匿名读 (无身份来源时回退 anonymous/viewer): "
        f"{'仅限受信任本机请求，' if local_only_api else ''}不代表登录认证",
        f"  - agent dev scope bypass (agent_dev_scope_bypass): {'开启' if agent_dev_bypass else '关闭'}",
        "  生产部署必须显式设置 MOSS_ENVIRONMENT=production（或其他非 development 取值），"
        + ("本机入口不支持外网或透明代理访问，不能替代生产身份认证。" if local_only_api else
         "普通开发入口未启用本机来源校验，不能替代生产身份认证。"),
        "=" * 78,
    ]
    logger.warning("\n".join(lines))


def _log_guardrails_enabled_banner(environment: str) -> None:
    logger.info(
        "MOSS 启动安全横幅 | environment=%s -> 生产安全护栏已启用"
        "（header trust / env 身份源 / CORS 白名单 / 弱默认凭据校验均已通过）",
        environment,
    )


def validate_auth_startup_guardrails(settings: Settings) -> None:
    environment = str(settings.environment).strip().lower()
    if environment == "development":
        if settings.local_only_api:
            if _header_trust_enabled():
                raise RuntimeError(
                    "development application cannot trust X-User-Id/X-User-Role headers; "
                    "header injection is reserved for isolated tests"
                )
            origins = [origin.strip() for origin in str(settings.cors_origins or "").split(",") if origin.strip()]
            if any(local_origin(origin) is None for origin in origins):
                raise RuntimeError("development application CORS origins must be explicit local origins")
            # Uvicorn CLI imports this module before binding. Check only its host
            # argument, without interpreting unrelated command-line fields.
            hosts = []
            if "backend.app.main:app" in sys.argv:
                for index, argument in enumerate(sys.argv):
                    if argument == "--host":
                        hosts.append(sys.argv[index + 1] if index + 1 < len(sys.argv) else "")
                    elif argument.startswith("--host="):
                        hosts.append(argument.partition("=")[2])
            if not hosts:
                hosts.append(os.environ.get("UVICORN_HOST", "127.0.0.1"))
            if any(not is_local_hostname(host) for host in hosts):
                raise RuntimeError("development application must bind Uvicorn to a loopback host")
        _log_development_security_banner(settings)
        return

    if _header_trust_enabled():
        raise RuntimeError(
            f"{environment} environment cannot trust X-User-Id/X-User-Role headers "
            f"via {ROLE_HEADER_TRUST_ENV}; only development can enable this trust switch"
        )
    if _env_identity_source_configured():
        raise RuntimeError(
            f"{environment} environment cannot use MOSS_USER_ID/MOSS_USER_ROLE as an identity source; "
            "configure a verified gateway, session, token, or API-key identity provider instead"
        )
    if _cors_has_wildcard_origin(settings):
        raise RuntimeError(
            f"{environment} environment cannot use wildcard CORS origins with credentialed API responses"
        )
    if _postgres_dsn_uses_weak_credentials(settings):
        raise RuntimeError(
            f"{environment} environment cannot start with the repository default postgres "
            "credentials (moss:moss); override MOSS_POSTGRES_DSN (and MOSS_GOVERNANCE_SQL_DSN "
            "when set) with deployment-specific credentials"
        )
    if _minio_uses_weak_credentials(settings):
        raise RuntimeError(
            f"{environment} environment cannot start with the repository default MinIO "
            "credentials (minioadmin); override MOSS_MINIO_ACCESS_KEY and MOSS_MINIO_SECRET_KEY "
            "with deployment-specific credentials"
        )
    _log_guardrails_enabled_banner(environment)


def _role_header_trust_enabled() -> bool:
    return _header_trust_enabled()
