"""Contract tests for backend.app.governance.settings (defaults, env overrides, helpers)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from backend.app.governance.settings import Settings, get_settings


def test_settings_defaults():
    s = Settings()
    assert s.environment == "development"
    assert s.agent_enabled is False
    assert s.object_store_mode == "local"
    assert s.ftp_rate_pct == Decimal("1.75")
    assert isinstance(s.governance_path, Path)
    assert isinstance(s.data_input_root, Path)
    assert isinstance(s.local_archive_path, Path)


def test_settings_env_overrides(monkeypatch):
    monkeypatch.setenv("MOSS_ENVIRONMENT", "staging")
    monkeypatch.setenv("MOSS_AGENT_ENABLED", "true")
    monkeypatch.setenv("MOSS_OBJECT_STORE_MODE", "minio")
    monkeypatch.setenv("MOSS_FTP_RATE_PCT", "2.5")
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", "custom/gov")
    monkeypatch.setenv("MOSS_DATA_INPUT_ROOT", "custom/in")
    monkeypatch.setenv("MOSS_LOCAL_ARCHIVE_PATH", "custom/archive")

    s = Settings()
    assert s.environment == "staging"
    assert s.agent_enabled is True
    assert s.object_store_mode == "minio"
    assert s.ftp_rate_pct == Decimal("2.5")
    assert s.governance_path == Path("custom/gov")
    assert s.data_input_root == Path("custom/in")
    assert s.local_archive_path == Path("custom/archive")


def test_get_settings_returns_settings_instance():
    assert isinstance(get_settings(), Settings)


def test_get_settings_cache_clear_callable_and_safe():
    clear = getattr(get_settings, "cache_clear", None)
    assert callable(clear)
    clear()
    clear()


def test_settings_extra_ignore_unknown_env(monkeypatch):
    monkeypatch.setenv("MOSS_TOTALLY_UNKNOWN_FUTURE_FIELD_XYZ", "should-be-ignored")
    # Must not raise; model has extra="ignore"
    s = Settings()
    assert not hasattr(s, "totally_unknown_future_field_xyz")
