"""Startup guardrails must refuse repository-default weak credentials outside development.

Covers the validate_auth_startup_guardrails checks for the repo-shipped
postgres DSN (moss:moss) and MinIO credentials (minioadmin). Identity-source
and CORS guardrails are covered by tests/test_auth_context.py.
"""

from __future__ import annotations

import pytest

from backend.app.governance.settings import (
    DEFAULT_POSTGRES_DSN,
    DEV_POSTGRES_DSN,
    Settings,
)
from backend.app.security.auth_context import (
    ROLE_HEADER_TRUST_ENV,
    validate_auth_startup_guardrails,
)


@pytest.fixture(autouse=True)
def _clean_identity_env(monkeypatch):
    # Keep the earlier identity-source guardrails quiet so these tests only
    # exercise the default-credential checks.
    monkeypatch.delenv("MOSS_USER_ID", raising=False)
    monkeypatch.delenv("MOSS_USER_ROLE", raising=False)
    monkeypatch.delenv(ROLE_HEADER_TRUST_ENV, raising=False)


def _production_settings(**overrides) -> Settings:
    values: dict[str, object] = {
        "environment": "production",
        "cors_origins": "https://app.example",
        "postgres_dsn": "postgresql://svc-user:deployment-secret@db.internal:5432/moss",
        "governance_sql_dsn": "",
        "object_store_mode": "local",
        "minio_access_key": "deployment-access-key",
        "minio_secret_key": "deployment-secret-key",
        "_env_file": None,
    }
    values.update(overrides)
    return Settings(**values)


def test_startup_guardrails_reject_repo_default_postgres_dsn_outside_development():
    with pytest.raises(
        RuntimeError,
        match="production.*MOSS_POSTGRES_DSN|MOSS_POSTGRES_DSN.*production",
    ):
        validate_auth_startup_guardrails(
            _production_settings(postgres_dsn=DEFAULT_POSTGRES_DSN)
        )


def test_startup_guardrails_reject_repo_default_dev_postgres_dsn_outside_development():
    with pytest.raises(RuntimeError, match="MOSS_POSTGRES_DSN"):
        validate_auth_startup_guardrails(
            _production_settings(postgres_dsn=DEV_POSTGRES_DSN)
        )


def test_startup_guardrails_reject_repo_default_postgres_credentials_on_other_hosts():
    with pytest.raises(RuntimeError, match="MOSS_POSTGRES_DSN"):
        validate_auth_startup_guardrails(
            _production_settings(
                postgres_dsn=(
                    "postgresql+psycopg://moss:moss@db.internal:5432/production"
                    "?sslmode=require"
                )
            )
        )


def test_startup_guardrails_reject_repo_default_governance_sql_dsn_outside_development():
    with pytest.raises(RuntimeError, match="MOSS_GOVERNANCE_SQL_DSN"):
        validate_auth_startup_guardrails(
            _production_settings(governance_sql_dsn=DEFAULT_POSTGRES_DSN)
        )


def test_startup_guardrails_reject_repo_default_minio_credentials_outside_development():
    with pytest.raises(
        RuntimeError,
        match="production.*MOSS_MINIO_ACCESS_KEY|MOSS_MINIO_ACCESS_KEY.*production",
    ):
        validate_auth_startup_guardrails(
            _production_settings(object_store_mode="minio", minio_access_key="minioadmin")
        )

    with pytest.raises(RuntimeError, match="MOSS_MINIO_SECRET_KEY"):
        validate_auth_startup_guardrails(
            _production_settings(object_store_mode="minio", minio_secret_key="minioadmin")
        )


def test_startup_guardrails_allow_repo_default_minio_credentials_in_local_archive_mode():
    # local archive mode never presents MinIO credentials to any service, so the
    # repo default is inert there (existing production deployments use local mode).
    validate_auth_startup_guardrails(
        _production_settings(
            object_store_mode="local",
            minio_access_key="minioadmin",
            minio_secret_key="minioadmin",
        )
    )


def test_startup_guardrails_pass_with_deployment_specific_credentials_outside_development():
    validate_auth_startup_guardrails(_production_settings(object_store_mode="minio"))


def test_startup_guardrails_skip_repo_default_credential_checks_in_development():
    validate_auth_startup_guardrails(
        Settings(
            environment="development",
            postgres_dsn=DEFAULT_POSTGRES_DSN,
            object_store_mode="minio",
            minio_access_key="minioadmin",
            minio_secret_key="minioadmin",
            _env_file=None,
        )
    )
