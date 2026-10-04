"""Shared API-layer guards.

Keeps the governed read-scope check and its 403/503 HTTP mapping in one place so
route modules only declare *which* resource they read.
"""
from __future__ import annotations

import ipaddress
from collections.abc import Callable

from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import AuthContext, ensure_user_allowed
from fastapi import HTTPException


def ensure_read_allowed(
    auth: AuthContext,
    resource: str,
    *,
    settings: object | None = None,
    allow_dev_fallback: bool = False,
    allow_dev_fallback_on_unavailable: bool = False,
    authorize: Callable[..., None] | None = None,
) -> None:
    """Authorize a governed read and translate scope failures into API errors.

    Callers pass their own ``settings``/``authorize`` symbols so route-module test
    doubles that replace ``get_settings`` or ``ensure_user_allowed`` in the route
    namespace still intercept the check.
    """
    resolved_settings = get_settings() if settings is None else settings
    resolved_authorize = ensure_user_allowed if authorize is None else authorize
    try:
        resolved_authorize(
            auth=auth,
            settings=resolved_settings,
            resource=resource,
            action="read",
        )
    except PermissionError as exc:
        if allow_dev_fallback and _allows_development_fallback_read(
            auth=auth, environment=getattr(resolved_settings, "environment", "")
        ):
            return
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        if allow_dev_fallback_on_unavailable and _allows_development_fallback_read(
            auth=auth, environment=getattr(resolved_settings, "environment", "")
        ):
            return
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _allows_development_fallback_read(*, auth: AuthContext, environment: object) -> bool:
    """Allow the anonymous/viewer dev fallback read only for a loopback caller.

    Known residual risk (not fixed by this check, registered rather than
    resolved): a reverse proxy or gateway running on the same host as the API
    process makes every proxied request appear to originate from
    127.0.0.1/::1 to this process, which defeats this loopback test. Do not
    place a same-host proxy in front of a development-mode deployment that
    relies on this guard to keep dev fallback local-only.
    """
    return (
        str(environment).strip().lower() == "development"
        and auth.identity_source == "fallback"
        and auth.user_id == "anonymous"
        and auth.role == "viewer"
        and _client_host_is_loopback(auth.client_host)
    )


def _client_host_is_loopback(host: object) -> bool:
    normalized = str(host or "").strip()
    if normalized.startswith("[") and normalized.endswith("]"):
        normalized = normalized[1:-1]
    if not normalized:
        return False
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False
