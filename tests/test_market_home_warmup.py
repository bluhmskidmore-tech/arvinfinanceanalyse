"""Tests for market workbench home startup warmup."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from backend.app.services import market_home_warmup_service as warmup


def test_market_home_prewarm_can_be_disabled() -> None:
    class Settings:
        market_home_prewarm_enabled = False
        duckdb_path = "data/moss.duckdb"

    with patch.object(warmup, "warm_market_home_read_caches") as mock_warm:
        assert warmup.warm_market_home_cache_if_configured(Settings()) is False

    mock_warm.assert_not_called()


def test_market_home_prewarm_starts_background_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    started: list[tuple[object, dict[str, object]]] = []

    class Settings:
        market_home_prewarm_enabled = True
        duckdb_path = "data/moss.duckdb"

    class FakeThread:
        def __init__(self, *, target, kwargs=None, daemon=False, name=""):
            started.append((target, {"kwargs": kwargs or {}, "daemon": daemon, "name": name}))

        def start(self):
            started.append(("start", {}))

    monkeypatch.setattr(warmup.threading, "Thread", FakeThread)

    assert warmup.warm_market_home_cache_if_configured(Settings()) is True
    assert started[0][1] == {
        "kwargs": {"duckdb_path": "data/moss.duckdb"},
        "daemon": True,
        "name": "moss-market-home-warmup",
    }
    assert started[1] == ("start", {})


def test_warm_market_home_read_caches_populates_all_steps(monkeypatch: pytest.MonkeyPatch) -> None:
    built: list[str] = []

    def fake_get_or_build(key: str, builder):
        built.append(key)
        builder()
        return {"cache_key": key}

    monkeypatch.setattr(warmup.market_home_response_cache, "get_or_build", fake_get_or_build)
    monkeypatch.setattr(
        warmup,
        "choice_macro_latest_envelope",
        lambda *_args, **_kwargs: {"result_kind": "macro.choice.latest"},
    )
    monkeypatch.setattr(
        warmup,
        "choice_macro_formal_envelope",
        lambda *_args, **_kwargs: {"result_kind": "market_data.rates"},
    )
    monkeypatch.setattr(
        warmup,
        "macro_foundation_formal_envelope",
        lambda *_args, **_kwargs: {"result_kind": "market_data.catalog"},
    )

    import backend.app.api.routes.macro_toolkit as macro_toolkit_routes

    monkeypatch.setattr(
        macro_toolkit_routes,
        "_build_macro_toolkit_analysis",
        lambda: {"result_kind": "macro_toolkit.analysis"},
    )

    warmup.warm_market_home_read_caches(duckdb_path="data/test.duckdb")

    assert len(built) == 4
    assert built[0].startswith("choice-series/latest::all::")
    assert "market-data/rates::" in built[1]
    assert "market-data/catalog::" in built[2]
    assert "macro-toolkit/analysis::full::" in built[3]


def test_market_vendor_routes_read_from_market_home_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    import backend.app.api.routes.macro_vendor as route

    calls: list[str] = []

    class Settings:
        duckdb_path = "data/test.duckdb"

    def fake_get_or_build(key: str, builder):
        calls.append(key)
        return builder()

    monkeypatch.setattr(route, "get_settings", lambda: Settings())
    monkeypatch.setattr(route.market_home_response_cache, "get_or_build", fake_get_or_build)
    monkeypatch.setattr(
        route,
        "choice_macro_formal_envelope",
        lambda *_args, **_kwargs: {"result_kind": "market_data.rates"},
    )
    monkeypatch.setattr(
        route,
        "macro_foundation_formal_envelope",
        lambda *_args, **_kwargs: {"result_kind": "market_data.catalog"},
    )
    monkeypatch.setattr(
        route,
        "choice_macro_latest_envelope",
        lambda *_args, **_kwargs: {"result_kind": "macro.choice.latest"},
    )

    assert route.market_data_rates()["result_kind"] == "market_data.rates"
    assert route.market_data_catalog()["result_kind"] == "market_data.catalog"
    assert route.choice_series_latest()["result_kind"] == "macro.choice.latest"

    assert calls == [
        "market-data/rates::data/test.duckdb",
        "market-data/catalog::data/test.duckdb",
        "choice-series/latest::all::data/test.duckdb",
    ]


def test_choice_series_refresh_invalidates_market_home_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    import backend.app.api.routes.macro_vendor as route

    invalidated: list[object] = []

    class Settings:
        duckdb_path = "data/test.duckdb"

    class ChoiceRefresh:
        @staticmethod
        def fn(backfill_days: int = 0) -> dict[str, object]:
            return {"status": "completed", "run_id": f"choice-refresh-{backfill_days}"}

    monkeypatch.setattr(route, "get_settings", lambda: Settings())
    monkeypatch.setattr(route, "ensure_user_allowed", lambda **_kwargs: None)
    monkeypatch.setattr(route, "refresh_choice_macro_snapshot", ChoiceRefresh())
    monkeypatch.setattr(route, "refresh_public_cross_asset_headlines", lambda: {"status": "completed"})
    monkeypatch.setattr(route.market_home_response_cache, "invalidate", lambda key=None: invalidated.append(key))

    payload = route.choice_series_refresh(auth=route.AuthContext(), backfill_days=3)

    assert payload["status"] == "completed"
    assert invalidated == [None]


def test_macro_toolkit_analysis_route_reads_from_market_home_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    import backend.app.api.routes.macro_toolkit as route

    calls: list[str] = []

    class Settings:
        duckdb_path = "data/test.duckdb"

    def fake_get_or_build(key: str, builder):
        calls.append(key)
        return builder()

    monkeypatch.setattr(route, "get_settings", lambda: Settings())
    monkeypatch.setattr(route.market_home_response_cache, "get_or_build", fake_get_or_build)
    monkeypatch.setattr(
        route,
        "_build_macro_toolkit_analysis",
        lambda: {"result_kind": "macro_toolkit.analysis"},
    )

    assert route.macro_toolkit_analysis()["result_kind"] == "macro_toolkit.analysis"
    assert calls == ["macro-toolkit/analysis::full::data/test.duckdb"]
