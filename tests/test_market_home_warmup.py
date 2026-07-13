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

    settings = Settings()
    monkeypatch.setattr(warmup.threading, "Thread", FakeThread)

    assert warmup.warm_market_home_cache_if_configured(settings) is True
    assert started[0][1] == {
        "kwargs": {"duckdb_path": "data/moss.duckdb", "settings": settings},
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
        lambda _detail: {"result_kind": "macro_toolkit.analysis"},
    )
    monkeypatch.setattr(
        macro_toolkit_routes,
        "_build_macro_toolkit_strategy_summaries",
        lambda: {"result_kind": "macro_toolkit.analysis.strategy_summaries"},
    )

    warmup.warm_market_home_read_caches(duckdb_path="data/test.duckdb")

    assert len(built) == 5
    assert built[0].startswith("choice-series/latest::all::")
    assert "market-data/rates::" in built[1]
    assert "market-data/catalog::" in built[2]
    assert "macro-toolkit/analysis::core::" in built[3]
    assert "macro-toolkit/strategy-summaries::" in built[4]


def test_stock_analysis_prewarm_uses_live_page_request_key(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from backend.app.api.routes import market_data_livermore as route

    calls: list[tuple[str, dict[str, object]]] = []

    def fake_get_or_build(key: str, _builder, **kwargs: object):
        calls.append((key, kwargs))
        return {"cache_key": key}

    class Settings:
        duckdb_path = tmp_path / "moss.duckdb"
        choice_stock_catalog_file = tmp_path / "choice-stock.json"
        governance_path = None
        local_archive_path = None

    monkeypatch.setattr(warmup.market_home_response_cache, "get_or_build", fake_get_or_build)
    monkeypatch.setattr(route.market_home_response_cache, "get_or_build", fake_get_or_build)

    settings = Settings()
    warmup.warm_market_home_read_caches(
        duckdb_path=str(settings.duckdb_path),
        settings=settings,
    )

    assert len(calls) == 6
    stock_key, stock_options = calls[0]
    assert stock_key.startswith("livermore/workbench::")
    assert "::as_of=::include=::sector_window_days=20::top_k=3" in stock_key
    assert "::catalog_version=" in stock_key
    assert stock_options == {"ttl_seconds": route.STOCK_ANALYSIS_WORKBENCH_CACHE_TTL_SECONDS}


def test_stock_analysis_prewarm_failure_does_not_block_other_steps(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from backend.app.api.routes import market_data_livermore as route

    built: list[str] = []

    def fake_get_or_build(key: str, _builder, **_kwargs: object):
        if key.startswith("livermore/workbench::"):
            raise RuntimeError("workbench warmup failed")
        built.append(key)
        return {"cache_key": key}

    class Settings:
        duckdb_path = tmp_path / "moss.duckdb"
        choice_stock_catalog_file = tmp_path / "choice-stock.json"
        governance_path = None
        local_archive_path = None

    monkeypatch.setattr(warmup.market_home_response_cache, "get_or_build", fake_get_or_build)
    monkeypatch.setattr(route.market_home_response_cache, "get_or_build", fake_get_or_build)

    warmup.warm_market_home_read_caches(
        duckdb_path=str(Settings.duckdb_path),
        settings=Settings(),
    )

    assert len(built) == 5
    assert built[0].startswith("choice-series/latest::all::")
