from tests.helpers import load_module


def test_get_settings_cache_clear_is_shared_across_module_reloads(monkeypatch, tmp_path):
    first_module = load_module(
        "backend.app.governance.settings",
        "backend/app/governance/settings.py",
    )
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "first.duckdb"))
    first_module.get_settings.cache_clear()
    assert str(first_module.get_settings().duckdb_path) == str(tmp_path / "first.duckdb")

    second_module = load_module(
        "backend.app.governance.settings",
        "backend/app/governance/settings.py",
    )
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "second.duckdb"))
    second_module.get_settings.cache_clear()

    assert str(first_module.get_settings().duckdb_path) == str(tmp_path / "second.duckdb")
    assert str(second_module.get_settings().duckdb_path) == str(tmp_path / "second.duckdb")
