import sys

from backend.app.governance.settings import get_settings
from tests.helpers import load_module


def test_get_settings_reuses_the_process_settings_instance() -> None:
    get_settings.cache_clear()

    try:
        assert get_settings() is get_settings()
    finally:
        get_settings.cache_clear()


def test_get_settings_cache_clear_rebuilds_from_current_environment(monkeypatch) -> None:
    monkeypatch.setenv("MOSS_ENVIRONMENT", "cache-before-clear")
    get_settings.cache_clear()
    try:
        before_clear = get_settings()

        monkeypatch.setenv("MOSS_ENVIRONMENT", "cache-after-clear")
        assert get_settings() is before_clear
        assert get_settings().environment == "cache-before-clear"

        get_settings.cache_clear()
        after_clear = get_settings()

        assert after_clear is not before_clear
        assert after_clear.environment == "cache-after-clear"
    finally:
        get_settings.cache_clear()


def test_reloaded_module_cache_clear_invalidates_existing_get_settings_reference(
    monkeypatch,
    tmp_path,
) -> None:
    original_settings = sys.modules["backend.app.governance.settings"]
    existing_settings_class = get_settings.__globals__["Settings"]
    reloaded_settings = None
    get_settings.cache_clear()

    try:
        monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "before-reload.duckdb"))
        before_reload = get_settings()
        assert isinstance(before_reload, existing_settings_class)

        reloaded_settings = load_module(
            "backend.app.governance.settings",
            "backend/app/governance/settings.py",
        )
        monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "after-reload.duckdb"))
        reloaded_settings.get_settings.cache_clear()

        after_reload_from_existing_reference = get_settings()
        after_reload_from_new_reference = reloaded_settings.get_settings()

        assert after_reload_from_existing_reference is not before_reload
        assert isinstance(after_reload_from_existing_reference, existing_settings_class)
        assert isinstance(after_reload_from_new_reference, reloaded_settings.Settings)
        assert after_reload_from_existing_reference is get_settings()
        assert after_reload_from_new_reference is reloaded_settings.get_settings()
        assert after_reload_from_existing_reference is not after_reload_from_new_reference
        assert after_reload_from_existing_reference.duckdb_path == str(
            tmp_path / "after-reload.duckdb"
        )
        assert after_reload_from_new_reference.duckdb_path == str(
            tmp_path / "after-reload.duckdb"
        )

        monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "after-existing-clear.duckdb"))
        get_settings.cache_clear()
        after_existing_clear_from_new_reference = reloaded_settings.get_settings()
        after_existing_clear_from_existing_reference = get_settings()

        assert after_existing_clear_from_new_reference is not after_reload_from_new_reference
        assert after_existing_clear_from_existing_reference is not after_reload_from_existing_reference
        assert isinstance(after_existing_clear_from_existing_reference, existing_settings_class)
        assert isinstance(after_existing_clear_from_new_reference, reloaded_settings.Settings)
        assert after_existing_clear_from_existing_reference is get_settings()
        assert after_existing_clear_from_new_reference is reloaded_settings.get_settings()
        assert after_existing_clear_from_new_reference is not after_existing_clear_from_existing_reference
        assert after_existing_clear_from_new_reference.duckdb_path == str(
            tmp_path / "after-existing-clear.duckdb"
        )
        assert after_existing_clear_from_existing_reference.duckdb_path == str(
            tmp_path / "after-existing-clear.duckdb"
        )
    finally:
        get_settings.cache_clear()
        if reloaded_settings is not None:
            reloaded_settings.get_settings.cache_clear()
        sys.modules["backend.app.governance.settings"] = original_settings
