"""Tests for market workbench home startup warmup."""

from __future__ import annotations

import sys
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from backend.app.services import market_home_warmup_service as warmup
from backend.app.services.macro_toolkit_refresh_receipt_service import (
    MacroToolkitRefreshReceiptHealth,
)


def _live_executive_service():
    """Return the executive_service module the warmup will actually call.

    ``tests.helpers.load_module`` replaces the ``sys.modules`` entry without
    refreshing the parent package attribute, so a plain ``import ... as`` can hand
    back a stale module object while the code under test resolves the new one. A
    patch applied to the stale object would then silently do nothing.
    """
    import backend.app.services.executive_service  # noqa: F401

    return sys.modules["backend.app.services.executive_service"]


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


def test_market_home_current_thread_entry_preserves_flag_and_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    disabled = SimpleNamespace(
        market_home_prewarm_enabled=False,
        duckdb_path="data/disabled.duckdb",
    )
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        warmup,
        "_warm_market_home_cache_quietly",
        lambda **kwargs: calls.append(kwargs),
    )

    assert warmup.warm_market_home_cache_in_current_thread_if_configured(disabled) is False
    assert calls == []

    enabled = SimpleNamespace(
        market_home_prewarm_enabled=True,
        duckdb_path="data/enabled.duckdb",
    )
    assert warmup.warm_market_home_cache_in_current_thread_if_configured(enabled) is True
    assert calls == [
        {"duckdb_path": "data/enabled.duckdb", "settings": enabled, "force_refresh": False}
    ]

    calls.clear()
    assert (
        warmup.warm_market_home_cache_in_current_thread_if_configured(
            enabled,
            force_refresh=True,
        )
        is True
    )
    assert calls == [
        {"duckdb_path": "data/enabled.duckdb", "settings": enabled, "force_refresh": True}
    ]


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
        lambda _detail, **_kwargs: {"result_kind": "macro_toolkit.analysis"},
    )
    monkeypatch.setattr(
        macro_toolkit_routes,
        "_build_macro_toolkit_strategy_summaries",
        lambda: {"result_kind": "macro_toolkit.analysis.strategy_summaries"},
    )

    import backend.app.services.executive_service as executive_service

    monkeypatch.setattr(warmup, "_dashboard_home_report_date", lambda _path: None)
    monkeypatch.setattr(
        executive_service,
        "home_research_reports_envelope",
        lambda **_kwargs: {"result_kind": "home.research_reports"},
    )

    warmup.warm_market_home_read_caches(duckdb_path="data/test.duckdb")

    assert len(built) == 6
    assert built[0].startswith("choice-series/latest::all::")
    assert "market-data/rates::" in built[1]
    assert "market-data/catalog::" in built[2]
    assert "macro-toolkit/analysis::core::" in built[3]
    assert "macro-toolkit/strategy-summaries::" in built[4]
    assert built[5].startswith("home/research-reports::")


def test_dashboard_home_report_date_prefers_snapshot_unified_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The page requests carry the snapshot's unified report_date, so the warmup
    must key on it; the bond-domain maximum is only a fallback."""
    executive_service = _live_executive_service()

    monkeypatch.setattr(
        executive_service,
        "home_snapshot_unified_report_date",
        lambda: "2026-07-31",
    )
    monkeypatch.setattr(warmup, "_latest_bond_report_date", lambda _path: "2026-08-05")
    assert warmup._dashboard_home_report_date("data/test.duckdb") == "2026-07-31"

    monkeypatch.setattr(executive_service, "home_snapshot_unified_report_date", lambda: None)
    assert warmup._dashboard_home_report_date("data/test.duckdb") == "2026-08-05"

    monkeypatch.setattr(warmup, "_latest_bond_report_date", lambda _path: None)
    assert warmup._dashboard_home_report_date("data/test.duckdb") is None


def test_warm_market_home_read_caches_force_refresh_overwrites_live_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A read-through warm leaves a live entry (and its expiry) untouched.

    That made the periodic refresh a no-op: every step logged a cache hit and the
    entry still lapsed at its original deadline, so the next page load paid the
    full cold recompute.
    """
    overwritten: list[str] = []
    read_through: list[str] = []

    monkeypatch.setattr(
        warmup.market_home_response_cache,
        "set",
        lambda key, value, **_kwargs: overwritten.append(key),
    )

    def fake_get_or_build(key: str, builder):
        read_through.append(key)
        return builder()

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
        lambda _detail, **_kwargs: {"result_kind": "macro_toolkit.analysis"},
    )
    monkeypatch.setattr(
        macro_toolkit_routes,
        "_build_macro_toolkit_strategy_summaries",
        lambda: {"result_kind": "macro_toolkit.analysis.strategy_summaries"},
    )

    monkeypatch.setattr(warmup, "_dashboard_home_report_date", lambda _path: None)
    monkeypatch.setattr(
        _live_executive_service(),
        "home_research_reports_envelope",
        lambda **_kwargs: {"result_kind": "home.research_reports"},
    )

    warmup.warm_market_home_read_caches(duckdb_path="data/test.duckdb", force_refresh=True)

    assert read_through == []
    assert len(overwritten) == 6
    assert overwritten[0].startswith("choice-series/latest::all::")
    assert overwritten[5].startswith("home/research-reports::")


def test_warm_market_home_read_caches_uses_one_receipt_snapshot_for_macro_analysis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    health = MacroToolkitRefreshReceiptHealth(
        status="ready",
        ready=True,
        cache_fingerprint="ready:warmup",
        generated_at="2026-08-09T10:30:00+00:00",
        run_status="success",
        source_version="macro_toolkit_freshness_refresh_v3",
        missing_fields=(),
        warnings=(),
        latest_observation_dates={"CA.CSI300": "2026-08-08"},
    )
    built: list[str] = []
    captured: dict[str, object] = {}

    def fake_get_or_build(key: str, builder):
        built.append(key)
        if "macro-toolkit/analysis::core::" in key:
            return builder()
        return {"cache_key": key}

    monkeypatch.setattr(warmup, "load_macro_toolkit_refresh_receipt_health", lambda: health)
    monkeypatch.setattr(warmup, "_dashboard_home_report_date", lambda _path: None)
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
        lambda _detail, **kwargs: captured.update(kwargs) or {"result_kind": "macro_toolkit.analysis"},
    )
    monkeypatch.setattr(
        macro_toolkit_routes,
        "_build_macro_toolkit_strategy_summaries",
        lambda: {"result_kind": "macro_toolkit.analysis.strategy_summaries"},
    )

    warmup.warm_market_home_read_caches(duckdb_path="data/test.duckdb")

    macro_analysis_keys = [key for key in built if "macro-toolkit/analysis::core::" in key]
    assert macro_analysis_keys == [
        "macro-toolkit/analysis::core::ready:warmup::data/test.duckdb"
    ]
    assert captured["refresh_receipt_health"] is health


def test_dashboard_home_formal_steps_warm_live_page_request_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """预热键必须与首页实际请求参数一致，否则预热不会被首屏命中。"""
    # Resolve via sys.modules like _live_executive_service: the warmup builders
    # lazily `from backend.app.services.X import fn` at call time, which binds the
    # current sys.modules entry, while `import ... as` can return a stale parent
    # package attribute after tests.helpers.load_module replaced the module.
    import backend.app.services.bond_analytics_service  # noqa: F401
    import backend.app.services.campisi_attribution_service  # noqa: F401

    bond_analytics_service = sys.modules["backend.app.services.bond_analytics_service"]
    campisi_service = sys.modules["backend.app.services.campisi_attribution_service"]

    executive_service = _live_executive_service()

    monkeypatch.setattr(warmup, "_dashboard_home_report_date", lambda _path: "2026-07-31")
    research_kwargs: dict[str, object] = {}
    credit_args: list[object] = []
    position_args: dict[str, object] = {}
    campisi_kwargs: dict[str, object] = {}

    monkeypatch.setattr(
        executive_service,
        "home_research_reports_envelope",
        lambda **kwargs: research_kwargs.update(kwargs) or {},
    )
    monkeypatch.setattr(
        bond_analytics_service,
        "get_credit_spread_migration",
        lambda report_date, scenarios: credit_args.extend([report_date, scenarios]) or {},
    )
    monkeypatch.setattr(
        bond_analytics_service,
        "get_position_changes",
        lambda report_date, **kwargs: position_args.update(
            {"report_date": report_date, **kwargs}
        )
        or {},
    )
    monkeypatch.setattr(
        campisi_service,
        "campisi_four_effects_summary_envelope",
        lambda **kwargs: campisi_kwargs.update(kwargs) or {},
    )

    steps = warmup._dashboard_home_formal_steps("data/test.duckdb")
    keys_by_name = {name: key for name, key, _builder in steps}
    for _name, _key, builder in steps:
        builder()

    assert keys_by_name == {
        "home_research_reports": (
            f"home/research-reports::{date.today().isoformat()}::5::data/test.duckdb"
        ),
        "credit_spread_migration": (
            "bond-analytics/credit-spread-migration"
            "::2026-07-31::10,25,50::data/test.duckdb"
        ),
        "position_changes": "bond-analytics/position-changes::2026-07-31::5::data/test.duckdb",
        "campisi_four_effects_summary": (
            "pnl-attribution/campisi/four-effects"
            "::summary::auto::2026-07-31::30::data/test.duckdb"
        ),
    }
    assert research_kwargs == {"report_date": date.today().isoformat(), "limit": 5}
    assert credit_args == [date(2026, 7, 31), "10,25,50"]
    assert position_args == {"report_date": date(2026, 7, 31), "top_n": 5}
    assert campisi_kwargs == {
        "start_date": None,
        "end_date": "2026-07-31",
        "lookback_days": 30,
    }


def test_dashboard_home_formal_steps_skip_dated_steps_without_report_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(warmup, "_dashboard_home_report_date", lambda _path: None)

    steps = warmup._dashboard_home_formal_steps("data/test.duckdb")

    assert [name for name, _key, _builder in steps] == ["home_research_reports"]


def test_stock_analysis_prewarm_uses_live_page_request_key(
    tmp_path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    from backend.app.api.routes import market_data_livermore as route

    calls: list[tuple[str, dict[str, object]]] = []
    caplog.set_level("INFO", logger=warmup.__name__)

    def fake_get_or_build(key: str, _builder, **kwargs: object):
        calls.append((key, kwargs))
        return {"cache_key": key}

    def fake_get_or_build_with_status(key: str, _builder, **kwargs: object):
        calls.append((key, kwargs))
        return {"cache_key": key}, "produce"

    class Settings:
        duckdb_path = tmp_path / "moss.duckdb"
        choice_stock_catalog_file = tmp_path / "choice-stock.json"
        governance_path = None
        local_archive_path = None

    monkeypatch.setattr(warmup, "_dashboard_home_report_date", lambda _path: None)
    monkeypatch.setattr(warmup.market_home_response_cache, "get_or_build", fake_get_or_build)
    monkeypatch.setattr(
        route.market_home_response_cache,
        "get_or_build_with_status",
        fake_get_or_build_with_status,
        raising=False,
    )

    settings = Settings()
    warmup.warm_market_home_read_caches(
        duckdb_path=str(settings.duckdb_path),
        settings=settings,
    )

    assert len(calls) == 7
    stock_key, stock_options = calls[0]
    assert stock_key.startswith("livermore/workbench::")
    assert "::as_of=::include=evidence_summary,main::sector_window_days=20::top_k=10" in stock_key
    assert "::catalog_version=" in stock_key
    assert stock_options == {"ttl_seconds": route.STOCK_ANALYSIS_WORKBENCH_CACHE_TTL_SECONDS}
    assert any(
        "market_home_prewarm_step ok step=stock_analysis_workbench" in record.message
        and "cache_status=produce" in record.message
        and "compute_ms=" in record.message
        and "wait_ms=0" in record.message
        for record in caplog.records
    )


def test_stock_analysis_prewarm_wait_log_uses_cache_duration(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    from backend.app.api.routes import market_data_livermore as route

    class Settings:
        duckdb_path = tmp_path / "moss.duckdb"
        choice_stock_catalog_file = tmp_path / "choice-stock.json"
        governance_path = None
        local_archive_path = None

    monkeypatch.setattr(
        route,
        "_cached_stock_analysis_workbench",
        lambda **_kwargs: ({}, "wait", 1.0, 12.0, 7.9),
    )
    monkeypatch.setattr(warmup, "_dashboard_home_report_date", lambda _path: None)
    monkeypatch.setattr(
        warmup.market_home_response_cache,
        "get_or_build",
        lambda *_args, **_kwargs: {},
    )
    caplog.set_level("INFO", logger=warmup.__name__)

    settings = Settings()
    warmup.warm_market_home_read_caches(
        duckdb_path=str(settings.duckdb_path),
        settings=settings,
    )

    assert any(
        "market_home_prewarm_step ok step=stock_analysis_workbench" in record.message
        and "cache_status=wait" in record.message
        and "cache_ms=7" in record.message
        and "wait_ms=7" in record.message
        for record in caplog.records
    )


def test_stock_analysis_prewarm_failure_does_not_block_other_steps(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from backend.app.api.routes import market_data_livermore as route

    built: list[str] = []

    def fake_get_or_build(key: str, _builder, **_kwargs: object):
        built.append(key)
        return {"cache_key": key}

    def fake_get_or_build_with_status(key: str, _builder, **_kwargs: object):
        raise RuntimeError(f"workbench warmup failed: {key}")

    class Settings:
        duckdb_path = tmp_path / "moss.duckdb"
        choice_stock_catalog_file = tmp_path / "choice-stock.json"
        governance_path = None
        local_archive_path = None

    monkeypatch.setattr(warmup, "_dashboard_home_report_date", lambda _path: None)
    monkeypatch.setattr(warmup.market_home_response_cache, "get_or_build", fake_get_or_build)
    monkeypatch.setattr(
        route.market_home_response_cache,
        "get_or_build_with_status",
        fake_get_or_build_with_status,
        raising=False,
    )

    warmup.warm_market_home_read_caches(
        duckdb_path=str(Settings.duckdb_path),
        settings=Settings(),
    )

    assert len(built) == 6
    assert built[0].startswith("choice-series/latest::all::")
