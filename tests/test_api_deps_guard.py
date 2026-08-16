"""Direct unit tests for ``backend.app.api.deps.ensure_read_allowed``."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.app.api.deps import ensure_read_allowed
from backend.app.security.auth_context import AuthContext


def _dev_fallback_auth() -> AuthContext:
    return AuthContext(user_id="anonymous", role="viewer", identity_source="fallback")


def _dev_settings() -> SimpleNamespace:
    return SimpleNamespace(environment="development")


def test_permission_error_maps_to_403():
    def deny(**_kwargs) -> None:
        raise PermissionError("scope denied")

    with pytest.raises(HTTPException) as exc_info:
        ensure_read_allowed(
            AuthContext(user_id="u1", role="viewer", identity_source="header"),
            "formal.balance",
            settings=SimpleNamespace(environment="production"),
            authorize=deny,
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "scope denied"


def test_runtime_error_maps_to_503():
    def unavailable(**_kwargs) -> None:
        raise RuntimeError("auth store down")

    with pytest.raises(HTTPException) as exc_info:
        ensure_read_allowed(
            AuthContext(user_id="u1", role="viewer", identity_source="header"),
            "formal.balance",
            settings=SimpleNamespace(environment="production"),
            authorize=unavailable,
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "auth store down"


def test_allow_dev_fallback_only_passes_permission_error():
    def deny(**_kwargs) -> None:
        raise PermissionError("scope denied")

    ensure_read_allowed(
        _dev_fallback_auth(),
        "formal.balance",
        settings=_dev_settings(),
        allow_dev_fallback=True,
        authorize=deny,
    )

    def unavailable(**_kwargs) -> None:
        raise RuntimeError("auth store down")

    with pytest.raises(HTTPException) as exc_info:
        ensure_read_allowed(
            _dev_fallback_auth(),
            "formal.balance",
            settings=_dev_settings(),
            allow_dev_fallback=True,
            authorize=unavailable,
        )

    assert exc_info.value.status_code == 503


def test_allow_dev_fallback_on_unavailable_passes_runtime_error():
    def unavailable(**_kwargs) -> None:
        raise RuntimeError("auth store down")

    ensure_read_allowed(
        _dev_fallback_auth(),
        "formal.balance",
        settings=_dev_settings(),
        allow_dev_fallback_on_unavailable=True,
        authorize=unavailable,
    )


@pytest.mark.parametrize(
    ("auth", "environment"),
    [
        (
            AuthContext(user_id="anonymous", role="viewer", identity_source="fallback"),
            "production",
        ),
        (
            AuthContext(user_id="anonymous", role="viewer", identity_source="header"),
            "development",
        ),
        (
            AuthContext(user_id="u1", role="viewer", identity_source="fallback"),
            "development",
        ),
        (
            AuthContext(user_id="anonymous", role="ops", identity_source="fallback"),
            "development",
        ),
    ],
)
def test_dev_fallback_rejects_when_any_of_four_conditions_fail(
    auth: AuthContext,
    environment: str,
):
    def deny(**_kwargs) -> None:
        raise PermissionError("scope denied")

    with pytest.raises(HTTPException) as exc_info:
        ensure_read_allowed(
            auth,
            "formal.balance",
            settings=SimpleNamespace(environment=environment),
            allow_dev_fallback=True,
            authorize=deny,
        )

    assert exc_info.value.status_code == 403
