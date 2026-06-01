"""Contract tests for `resolve_tushare_token_with_settings_fallback` (env vs settings, no I/O)."""

from __future__ import annotations

import pytest

from backend.app.repositories.tushare_adapter import TUSHARE_TOKEN_ENV, resolve_tushare_token_with_settings_fallback


def test_env_token_wins_over_settings_tushare_token(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Cfg:
        tushare_token = "from_settings"

    monkeypatch.setenv(TUSHARE_TOKEN_ENV, "  from_env  ")
    assert resolve_tushare_token_with_settings_fallback(_Cfg()) == "from_env"


def test_settings_tushare_token_used_when_env_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Cfg:
        tushare_token = "only_settings"

    monkeypatch.delenv(TUSHARE_TOKEN_ENV, raising=False)
    assert resolve_tushare_token_with_settings_fallback(_Cfg()) == "only_settings"


def test_empty_when_no_env_and_no_settings_token(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Cfg:
        tushare_token = ""

    monkeypatch.delenv(TUSHARE_TOKEN_ENV, raising=False)
    assert resolve_tushare_token_with_settings_fallback(_Cfg()) == ""


def test_empty_env_string_falls_back_to_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Cfg:
        tushare_token = "settings_after_blank_env"

    monkeypatch.setenv(TUSHARE_TOKEN_ENV, "   ")
    assert resolve_tushare_token_with_settings_fallback(_Cfg()) == "settings_after_blank_env"
