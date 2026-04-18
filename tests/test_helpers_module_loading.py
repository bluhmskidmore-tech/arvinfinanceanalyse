from __future__ import annotations

import sys

from tests.helpers import load_module


def _purge_backend_modules() -> None:
    for loaded_name in list(sys.modules):
        if loaded_name.startswith("backend.app"):
            sys.modules.pop(loaded_name, None)


def test_load_main_reuses_cached_api_module(monkeypatch):
    _purge_backend_modules()
    monkeypatch.setenv("MOSS_CORS_ORIGINS", "http://first.example")

    first_main = load_module("backend.app.main", "backend/app/main.py")
    first_api = sys.modules["backend.app.api"]

    second_main = load_module("backend.app.main", "backend/app/main.py")

    assert second_main is not first_main
    assert sys.modules["backend.app.api"] is first_api


def test_load_main_picks_up_env_change_without_reloading_api(monkeypatch):
    _purge_backend_modules()
    monkeypatch.setenv("MOSS_CORS_ORIGINS", "http://first.example")

    load_module("backend.app.main", "backend/app/main.py")
    cached_api = sys.modules["backend.app.api"]

    monkeypatch.setenv("MOSS_CORS_ORIGINS", "http://second.example")
    second_main = load_module("backend.app.main", "backend/app/main.py")

    assert sys.modules["backend.app.api"] is cached_api
    assert second_main._settings.cors_origins == "http://second.example"
