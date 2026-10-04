"""Tests for market workbench home startup warmup."""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import date
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from backend.app.services import market_home_warmup_service as warmup
from backend.app.services.macro_toolkit_refresh_receipt_service import (
    MacroToolkitRefreshReceiptHealth,
)


DEFAULT_PAGE_READS = (
    ("home_summary", "bond_dashboard_service", "get_bond_dashboard_home_summary"),
    ("return_decomposition", "bond_analytics_service", "get_return_decomposition_summary"),
    ("volume_rate", "pnl_attribution_service", "volume_rate_attribution_envelope"),
    ("attribution_summary", "pnl_attribution_service", "attribution_analysis_summary_envelope"),
)
SUPPLEMENTAL_PAGE_READS = (
    ("yield_curve", "yield_curve_term_structure_service", "get_yield_curve_term_structure"),
    ("krd_risk", "bond_analytics_service", "get_krd_curve_risk"),
    ("top_holdings", "bond_analytics_service", "get_top_holdings"),
    ("portfolio_headlines", "bond_analytics_service", "get_portfolio_headlines"),
)


@pytest.fixture(autouse=True)
def default_page_read_calls(monkeypatch: pytest.MonkeyPatch):
    """Warmup tests never execute newly prewarmed business reads against live data."""
    calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []
    for step_name, module_name, function_name in DEFAULT_PAGE_READS + SUPPLEMENTAL_PAGE_READS:
        module = import_module(f"backend.app.services.{module_name}")

        def record(*args, _step_name=step_name, **kwargs):
            calls.append((_step_name, args, kwargs))
            return {}

        monkeypatch.setattr(module, function_name, record)
    balance = import_module("backend.app.services.balance_analysis_service")
    monkeypatch.setattr(balance, "balance_analysis_dates_envelope", lambda **_kwargs: {"result": {"report_dates": []}})
    monkeypatch.setattr(balance, "balance_analysis_decision_items_envelope", lambda **_kwargs: {})
    macro = import_module("backend.app.services.home_macro_release_context_service")
    monkeypatch.setattr(
        macro,
        "HomeMacroReleaseContextService",
        lambda **_kwargs: SimpleNamespace(build_envelope=lambda **_kwargs: {}),
    )
    return calls


@pytest.mark.excluded_surface_regression
@pytest.mark.surface_macro_toolkit
def test_macro_toolkit_warmup_imports_read_service_without_http_composition() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    code = """
import builtins
import platform
import socket
import subprocess
import sys
import duckdb
platform.uname()

def forbidden(*args, **kwargs):
    raise AssertionError("warmup import must not access a database, network or subprocess")

duckdb.connect = forbidden
socket.socket.connect = forbidden
subprocess.Popen.__init__ = forbidden
original_import = builtins.__import__
def import_without_http(name, *args, **kwargs):
    if name.startswith("backend.app.api") or name == "backend.app.main":
        raise AssertionError("warmup must not import HTTP composition")
    return original_import(name, *args, **kwargs)
builtins.__import__ = import_without_http

from backend.app.services import macro_toolkit_read_service
from backend.app.services import market_home_warmup_service
assert market_home_warmup_service.build_macro_toolkit_analysis is macro_toolkit_read_service.build_macro_toolkit_analysis
assert market_home_warmup_service.build_macro_toolkit_strategy_summaries is macro_toolkit_read_service.build_macro_toolkit_strategy_summaries
assert not any(name.startswith("backend.app.api") for name in sys.modules)
"""
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=repo_root,
        env={**os.environ, "MOSS_ENV": "development"},
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr


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
    snapshot_calls: list[dict[str, object]] = []

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

    monkeypatch.setattr(
        warmup,
        "build_macro_toolkit_analysis",
        lambda _detail, **_kwargs: {"result_kind": "macro_toolkit.analysis"},
    )
    monkeypatch.setattr(
        warmup,
        "build_macro_toolkit_strategy_summaries",
        lambda: {"result_kind": "macro_toolkit.analysis.strategy_summaries"},
    )
    monkeypatch.setattr(
        warmup,
        "build_market_snapshot",
        lambda **kwargs: snapshot_calls.append(kwargs)
        or {"result_kind": "market.snapshot"},
    )

    import backend.app.services.executive_service as executive_service

    monkeypatch.setattr(warmup, "_dashboard_home_report_date", lambda _path: None)
    monkeypatch.setattr(
        executive_service,
        "home_research_reports_envelope",
        lambda **_kwargs: {"result_kind": "home.research_reports"},
    )

    warmup.warm_market_home_read_caches(duckdb_path="data/test.duckdb")

    assert len(built) == 8
    assert built[0].startswith("home/research-reports::")
    assert built[1].startswith("choice-series/latest::all::")
    assert "market-data/rates::" in built[2]
    assert "market-data/catalog::" in built[3]
    assert "macro-toolkit/analysis::core::" in built[4]
    assert "macro-toolkit/analysis::full::430::" in built[5]
    assert "macro-toolkit/strategy-summaries::" in built[6]
    assert built[7].startswith(
        "market-overview/snapshot::actions,charts,crisis,dates,funding_observation,gate,news,pulse,"
        "rates_observation,signals,tape::"
        "cv_market_overview_snapshot_v8::"
    )
    assert snapshot_calls[0]["include"] == warmup.DEFAULT_MARKET_OVERVIEW_INCLUDE
    assert snapshot_calls[0]["duckdb_path"] == "data/test.duckdb"


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

    monkeypatch.setattr(
        warmup,
        "build_macro_toolkit_analysis",
        lambda _detail, **_kwargs: {"result_kind": "macro_toolkit.analysis"},
    )
    monkeypatch.setattr(
        warmup,
        "build_macro_toolkit_strategy_summaries",
        lambda: {"result_kind": "macro_toolkit.analysis.strategy_summaries"},
    )
    monkeypatch.setattr(
        warmup,
        "build_market_snapshot",
        lambda **_kwargs: {"result_kind": "market.snapshot"},
    )

    monkeypatch.setattr(warmup, "_dashboard_home_report_date", lambda _path: None)
    monkeypatch.setattr(
        _live_executive_service(),
        "home_research_reports_envelope",
        lambda **_kwargs: {"result_kind": "home.research_reports"},
    )

    warmup.warm_market_home_read_caches(duckdb_path="data/test.duckdb", force_refresh=True)

    assert read_through == []
    assert len(overwritten) == 8
    assert overwritten[0].startswith("home/research-reports::")
    assert "macro-toolkit/analysis::full::430::" in overwritten[5]
    assert "macro-toolkit/strategy-summaries::" in overwritten[6]
    assert overwritten[7].startswith(
        "market-overview/snapshot::actions,charts,crisis,dates,funding_observation,gate,news,pulse,"
        "rates_observation,signals,tape::"
        "cv_market_overview_snapshot_v8::"
    )


def test_warm_market_home_read_caches_uses_one_receipt_snapshot_for_macro_analysis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    health = MacroToolkitRefreshReceiptHealth(
        status="ready",
        ready=True,
        cache_fingerprint="ready:warmup",
        generated_at="2026-08-09T10:30:00+00:00",
        run_status="success",
        source_version="macro_toolkit_freshness_refresh_v4",
        missing_fields=(),
        warnings=(),
        latest_observation_dates={
            "CA.CSI300": "2026-08-08",
            "EMM00166683": "2026-08-08",
        },
    )
    built: list[str] = []
    captured: list[tuple[str, dict[str, object]]] = []
    snapshot_calls: list[dict[str, object]] = []

    def fake_get_or_build(key: str, builder):
        built.append(key)
        if "macro-toolkit/analysis::" in key or "market-overview/snapshot::" in key:
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

    monkeypatch.setattr(
        warmup,
        "build_macro_toolkit_analysis",
        lambda detail, **kwargs: captured.append((detail, kwargs))
        or {"result_kind": "macro_toolkit.analysis"},
    )
    monkeypatch.setattr(
        warmup,
        "build_macro_toolkit_strategy_summaries",
        lambda: {"result_kind": "macro_toolkit.analysis.strategy_summaries"},
    )
    monkeypatch.setattr(
        warmup,
        "build_market_snapshot",
        lambda **kwargs: snapshot_calls.append(kwargs)
        or {"result_kind": "market.snapshot"},
    )

    warmup.warm_market_home_read_caches(duckdb_path="data/test.duckdb")

    macro_analysis_keys = [key for key in built if "macro-toolkit/analysis::" in key]
    assert macro_analysis_keys == [
        "macro-toolkit/analysis::core::ready:warmup::data/test.duckdb",
        "macro-toolkit/analysis::full::430::ready:warmup::data/test.duckdb",
    ]
    assert captured == [
        ("core", {"refresh_receipt_health": health}),
        (
            "full",
            {
                "history_limit": warmup.DEFAULT_CRISIS_SCORE_HISTORY_LIMIT,
                "refresh_receipt_health": health,
            },
        ),
    ]
    assert snapshot_calls == [
        {
            "include": warmup.DEFAULT_MARKET_OVERVIEW_INCLUDE,
            "duckdb_path": "data/test.duckdb",
            "refresh_receipt_health": health,
        }
    ]


def test_dashboard_home_formal_steps_warm_live_page_request_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """预热键必须与首页实际请求参数一致，否则预热不会被首屏命中。"""
    class MockDate(date):
        @classmethod
        def today(cls):
            return date(2026, 4, 20)

    monkeypatch.setattr(warmup, "date", MockDate)

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
            "home/research-reports::2026-04-20::5::data/test.duckdb"
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
    assert research_kwargs == {"report_date": "2026-04-20", "limit": 5}
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

    assert len(calls) == 9
    # Homepage entries must be ready before the long stock workbench rebuild.
    assert calls[0][0].startswith("home/research-reports::")
    stock_key, stock_options = calls[1]
    assert stock_key.startswith("livermore/workbench::")
    assert "::as_of=::include=evidence_summary,main::sector_window_days=20::top_k=10" in stock_key
    assert "::catalog_version=" in stock_key
    assert stock_options == {"ttl_seconds": route.STOCK_ANALYSIS_WORKBENCH_CACHE_TTL_SECONDS}
    assert calls[-1][0].startswith(
        "market-overview/snapshot::actions,charts,crisis,dates,funding_observation,gate,news,pulse,"
        "rates_observation,signals,tape::"
        "cv_market_overview_snapshot_v8::"
    )
    assert any(
        "market_home_prewarm_step ok step=stock_analysis_workbench" in record.message
        and "cache_status=produce" in record.message
        and "compute_ms=" in record.message
        and "wait_ms=0" in record.message
        for record in caplog.records
    )


@pytest.mark.parametrize("report_date,parse_failed", [("2026-08-31", False), ("2026-08-31", True), (None, False)])
def test_home_candidate_prewarm_uses_snapshot_month_before_stock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, report_date: str | None, parse_failed: bool,
) -> None:
    from backend.app.services import candidate_financial_indicator_service as candidate
    from backend.app.services import market_data_livermore_route_support as stock

    order = []
    candidate_calls = []

    def build_candidate(**kwargs):
        order.append("candidate")
        candidate_calls.append(kwargs)
        if parse_failed:
            raise ValueError("source unavailable")
        return {"result": {}}

    def build_stock(**kwargs):
        order.append("stock")
        return {}, "produce", 0, 0, 0

    monkeypatch.setattr(candidate, "candidate_financial_indicator_envelope", build_candidate)
    monkeypatch.setattr(stock, "_cached_stock_analysis_workbench", build_stock)
    monkeypatch.setattr(warmup, "_dashboard_home_report_date", lambda _path: report_date)
    monkeypatch.setattr(warmup, "_dashboard_home_formal_steps", lambda _path: [])
    monkeypatch.setattr(warmup.market_home_response_cache, "get_or_build", lambda _key, _builder: {})
    monkeypatch.setattr(warmup, "_warm_macro_bond_linkage", lambda *_args: None)
    monkeypatch.setattr(warmup, "_warm_livermore_signal_confluence", lambda **_kwargs: None)
    settings = SimpleNamespace(
        duckdb_path=str(tmp_path / "test.duckdb"), product_category_source_dir=str(tmp_path / "source"),
    )
    warmup.warm_market_home_read_caches(duckdb_path=settings.duckdb_path, settings=settings)
    assert order == (["candidate", "stock"] if report_date else ["stock"])
    assert candidate_calls == ([{
        "source_dir": settings.product_category_source_dir, "report_month": "202608",
        "include_lineage": False, "metric_id": "income.operating.mother_bank",
    }] if report_date else [])


def _prepare_default_page_warmup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    report_date: str | None = "2026-08-31",
    failing_step: str | None = None,
):
    order: list[str] = []
    page_calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []
    date_paths: list[str] = []
    for step_name, module_name, function_name in DEFAULT_PAGE_READS:
        module = import_module(f"backend.app.services.{module_name}")

        def record(*args, _step_name=step_name, **kwargs):
            order.append(_step_name)
            page_calls.append((_step_name, args, kwargs))
            if _step_name == failing_step:
                raise RuntimeError(f"synthetic {_step_name} unavailable")
            return {}

        monkeypatch.setattr(module, function_name, record)

    def record_date(path: str):
        date_paths.append(path)
        return report_date

    monkeypatch.setattr(warmup, "_dashboard_home_report_date", record_date)
    monkeypatch.setattr(
        warmup,
        "_dashboard_home_formal_steps",
        lambda _path: [("existing_home", "home/test", lambda: order.append("home") or {})],
    )
    monkeypatch.setattr(
        warmup.market_home_response_cache, "get_or_build", lambda _key, builder: builder(),
    )
    monkeypatch.setattr(warmup.market_home_response_cache, "set", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(warmup.market_home_response_cache, "generation", lambda: 0)
    monkeypatch.setattr(
        warmup,
        "load_macro_toolkit_refresh_receipt_health",
        lambda: SimpleNamespace(cache_fingerprint="synthetic:ready"),
    )
    for function_name in (
        "choice_macro_latest_envelope",
        "choice_macro_formal_envelope",
        "macro_foundation_formal_envelope",
        "build_macro_toolkit_analysis",
        "build_macro_toolkit_strategy_summaries",
        "build_market_snapshot",
    ):
        monkeypatch.setattr(
            warmup, function_name, lambda *_args, **_kwargs: order.append("macro") or {},
        )

    candidate = import_module("backend.app.services.candidate_financial_indicator_service")
    stock = import_module("backend.app.services.market_data_livermore_route_support")
    monkeypatch.setattr(
        candidate,
        "candidate_financial_indicator_envelope",
        lambda **_kwargs: order.append("candidate") or {},
    )
    monkeypatch.setattr(
        stock,
        "_cached_stock_analysis_workbench",
        lambda **_kwargs: (order.append("stock") or {}, "produce", 0, 0, 0),
    )
    monkeypatch.setattr(warmup, "_warm_macro_bond_linkage", lambda *_args: None)
    monkeypatch.setattr(warmup, "_warm_livermore_signal_confluence", lambda **_kwargs: None)
    settings = SimpleNamespace(
        duckdb_path=str(tmp_path / "test.duckdb"),
        product_category_source_dir=str(tmp_path / "source"),
    )
    return settings, order, page_calls, date_paths


@pytest.mark.parametrize("force_refresh", [False, True])
def test_default_page_prewarm_uses_snapshot_date_and_request_defaults_before_stock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    force_refresh: bool,
) -> None:
    settings, order, page_calls, date_paths = _prepare_default_page_warmup(tmp_path, monkeypatch)

    warmup.warm_market_home_read_caches(
        duckdb_path=settings.duckdb_path, settings=settings, force_refresh=force_refresh,
    )

    assert order[:7] == [
        "home", "candidate", "home_summary", "return_decomposition", "volume_rate",
        "attribution_summary", "stock",
    ]
    assert order[7:] == ["macro"] * 7
    assert date_paths and set(date_paths) == {settings.duckdb_path}
    assert page_calls == [
        ("home_summary", (date(2026, 8, 31),), {"force_refresh": force_refresh}),
        ("return_decomposition", (date(2026, 8, 31),), {"force_refresh": force_refresh}),
        ("volume_rate", (), {
            "report_date": "2026-08-31", "compare_type": "mom", "force_refresh": force_refresh,
        }),
        ("attribution_summary", (), {
            "report_date": "2026-08-31", "force_refresh": force_refresh,
        }),
    ]


@pytest.mark.parametrize("failing_step", [step[0] for step in DEFAULT_PAGE_READS])
def test_default_page_prewarm_failure_continues_remaining_reads_and_stock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    failing_step: str,
) -> None:
    settings, order, page_calls, _date_paths = _prepare_default_page_warmup(
        tmp_path, monkeypatch, failing_step=failing_step,
    )

    warmup.warm_market_home_read_caches(duckdb_path=settings.duckdb_path, settings=settings)

    assert [name for name, _args, _kwargs in page_calls] == [step[0] for step in DEFAULT_PAGE_READS]
    assert order.index("stock") > order.index("attribution_summary")
    assert order[-1] == "macro"
    assert any(
        record.exc_info and str(record.exc_info[1]) == f"synthetic {failing_step} unavailable"
        for record in caplog.records
    )


@pytest.mark.parametrize("report_date", [None, "invalid-date"])
def test_default_page_prewarm_skips_reads_without_valid_snapshot_date(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    report_date: str | None,
) -> None:
    settings, order, page_calls, _date_paths = _prepare_default_page_warmup(
        tmp_path, monkeypatch, report_date=report_date,
    )

    warmup.warm_market_home_read_caches(duckdb_path=settings.duckdb_path, settings=settings)

    assert page_calls == []
    assert order == ["home", "stock"] + ["macro"] * 7


def _prepare_supplemental_page_warmup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    bond_date: str | None = "2026-08-31",
    balance_dates: object = ("2026-09-30", "2026-08-31"),
    failing_step: str | None = None,
):
    settings, order, _core_calls, _date_paths = _prepare_default_page_warmup(
        tmp_path, monkeypatch, report_date=bond_date,
    )
    settings.governance_path = str(tmp_path / "governance")
    calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    for step_name, module_name, function_name in SUPPLEMENTAL_PAGE_READS:
        module = import_module(f"backend.app.services.{module_name}")

        def record(*args, _step_name=step_name, **kwargs):
            order.append(_step_name)
            calls.append((_step_name, args, kwargs))
            if failing_step == _step_name:
                raise RuntimeError(f"synthetic {_step_name} unavailable")
            return {}

        monkeypatch.setattr(module, function_name, record)

    def record_balance_dates(**kwargs):
        order.append("balance_dates")
        calls.append(("balance_dates", (), kwargs))
        if failing_step == "balance_dates":
            raise RuntimeError("synthetic balance_dates unavailable")
        payload_dates = list(balance_dates) if isinstance(balance_dates, tuple) else balance_dates
        return {"result": {"report_dates": payload_dates}}

    def record_decisions(**kwargs):
        order.append("balance_decisions")
        calls.append(("balance_decisions", (), kwargs))
        if failing_step == "balance_decisions":
            raise RuntimeError("synthetic balance_decisions unavailable")
        return {}

    balance = import_module("backend.app.services.balance_analysis_service")
    monkeypatch.setattr(balance, "balance_analysis_dates_envelope", record_balance_dates)
    monkeypatch.setattr(balance, "balance_analysis_decision_items_envelope", record_decisions)

    macro_repo_module = import_module("backend.app.repositories.home_macro_release_context_repo")
    macro_service_module = import_module("backend.app.services.home_macro_release_context_service")
    macro_configuration: dict[str, object] = {}

    class FakeMacroRepository:
        def __init__(self, duckdb_path):
            macro_configuration["duckdb_path"] = duckdb_path

    class FakeMacroService:
        def __init__(self, *, repository, bindings_path):
            assert isinstance(repository, FakeMacroRepository)
            macro_configuration["bindings_path"] = bindings_path

        def build_envelope(self, **kwargs):
            order.append("macro_release")
            calls.append(("macro_release", (), kwargs))
            if failing_step == "macro_release":
                raise RuntimeError("synthetic macro_release unavailable")
            return {}

    monkeypatch.setattr(macro_repo_module, "HomeMacroReleaseContextRepository", FakeMacroRepository)
    monkeypatch.setattr(macro_service_module, "HomeMacroReleaseContextService", FakeMacroService)

    class FixedDate(date):
        @classmethod
        def today(cls):
            return date(2026, 9, 30)

    monkeypatch.setattr(warmup, "date", FixedDate)
    return settings, order, calls, macro_configuration


@pytest.mark.parametrize("force_refresh", [False, True])
def test_supplemental_page_prewarm_uses_each_page_date_and_defaults_before_stock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    force_refresh: bool,
) -> None:
    settings, order, calls, macro_configuration = _prepare_supplemental_page_warmup(tmp_path, monkeypatch)
    effective_path = str(tmp_path / "effective.duckdb")

    warmup.warm_market_home_read_caches(
        duckdb_path=effective_path, settings=settings, force_refresh=force_refresh,
    )

    by_name = {name: (args, kwargs) for name, args, kwargs in calls}
    assert by_name == {
        "yield_curve": ((), {
            "report_date": date(2026, 8, 31), "curve_types": ("treasury", "cdb", "aaa_credit"),
            "force_refresh": force_refresh,
        }),
        "krd_risk": ((date(2026, 8, 31),), {
            "scenario_set": "standard", "force_refresh": force_refresh,
        }),
        "top_holdings": ((date(2026, 8, 31),), {"top_n": 14}),
        "portfolio_headlines": ((date(2026, 8, 31),), {"force_refresh": force_refresh}),
        "balance_dates": ((), {
            "duckdb_path": effective_path, "governance_dir": settings.governance_path,
        }),
        "balance_decisions": ((), {
            "duckdb_path": effective_path, "governance_dir": settings.governance_path,
            "report_date": "2026-09-30", "position_scope": "all", "currency_basis": "CNY",
            "force_refresh": force_refresh,
        }),
        "macro_release": ((), {
            "window_start_date": date(2026, 9, 30), "window_end_date": date(2026, 11, 14),
            "history_limit": 8, "force_refresh": force_refresh,
        }),
    }
    assert order.index("yield_curve") > order.index("attribution_summary")
    assert [name for name in order if name in dict.fromkeys(step[0] for step in SUPPLEMENTAL_PAGE_READS)] == [
        step[0] for step in SUPPLEMENTAL_PAGE_READS
    ]
    assert all(order.index(name) < order.index("stock") for name in by_name)
    assert order[-7:] == ["macro"] * 7
    assert macro_configuration["duckdb_path"] == effective_path
    assert Path(macro_configuration["bindings_path"]) == (
        Path(__file__).resolve().parents[1] / "config" / "home_macro_release_bindings.json"
    )


@pytest.mark.parametrize(
    "failing_step", [step[0] for step in SUPPLEMENTAL_PAGE_READS] + ["balance_decisions", "macro_release"],
)
def test_supplemental_page_prewarm_failure_does_not_block_remaining_steps(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    failing_step: str,
) -> None:
    settings, order, calls, _configuration = _prepare_supplemental_page_warmup(
        tmp_path, monkeypatch, failing_step=failing_step,
    )

    warmup.warm_market_home_read_caches(duckdb_path=settings.duckdb_path, settings=settings)

    assert {name for name, _args, _kwargs in calls} == {
        *[step[0] for step in SUPPLEMENTAL_PAGE_READS], "balance_dates", "balance_decisions", "macro_release",
    }
    assert order.index("stock") > order.index("macro_release")
    assert order[-1] == "macro"
    assert any(
        record.exc_info and str(record.exc_info[1]) == f"synthetic {failing_step} unavailable"
        for record in caplog.records
    )


@pytest.mark.parametrize(
    "balance_dates,failing_step,governance_path",
    [([], None, "configured"), (["invalid-date"], None, "configured"),
     ([], "balance_dates", "configured"), (["2026-09-30"], None, "")],
)
def test_balance_prewarm_skips_unavailable_date_and_keeps_macro_and_stock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    balance_dates: object,
    failing_step: str | None,
    governance_path: str,
) -> None:
    settings, order, calls, _configuration = _prepare_supplemental_page_warmup(
        tmp_path, monkeypatch, balance_dates=balance_dates, failing_step=failing_step,
    )
    if not governance_path:
        settings.governance_path = ""

    warmup.warm_market_home_read_caches(duckdb_path=settings.duckdb_path, settings=settings)

    assert "balance_decisions" not in [name for name, _args, _kwargs in calls]
    assert ("balance_dates" in order) is bool(governance_path)
    assert "macro_release" in order
    assert "stock" in order


@pytest.mark.parametrize("bond_date", [None, "invalid-date"])
def test_balance_and_macro_prewarm_do_not_require_bond_snapshot_date(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    bond_date: str | None,
) -> None:
    settings, order, calls, _configuration = _prepare_supplemental_page_warmup(
        tmp_path, monkeypatch, bond_date=bond_date,
    )

    warmup.warm_market_home_read_caches(duckdb_path=settings.duckdb_path, settings=settings)

    assert [name for name, _args, _kwargs in calls] == ["balance_dates", "balance_decisions", "macro_release"]
    assert all(step[0] not in order for step in SUPPLEMENTAL_PAGE_READS)
    assert order.index("balance_decisions") < order.index("stock")
    assert order.index("macro_release") < order.index("stock")


def test_balance_decision_prewarm_reads_current_status_on_each_pass(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings, _order, calls, _configuration = _prepare_supplemental_page_warmup(tmp_path, monkeypatch)
    response_entries: dict[str, object] = {}

    def get_or_build(key, builder):
        if key not in response_entries:
            response_entries[key] = builder()
        return response_entries[key]

    monkeypatch.setattr(warmup.market_home_response_cache, "get_or_build", get_or_build)

    for _pass in range(2):
        warmup.warm_market_home_read_caches(duckdb_path=settings.duckdb_path, settings=settings)

    assert len([name for name, _args, _kwargs in calls if name == "balance_decisions"]) == 2


def test_stock_analysis_prewarm_wait_log_uses_cache_duration(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    from backend.app.services import market_data_livermore_route_support as route_support

    class Settings:
        duckdb_path = tmp_path / "moss.duckdb"
        choice_stock_catalog_file = tmp_path / "choice-stock.json"
        governance_path = None
        local_archive_path = None

    # Warmup imports `_cached_stock_analysis_workbench` from route_support
    # directly (not through the route module), so the patch target must be
    # route_support for this to take effect.
    monkeypatch.setattr(
        route_support,
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

    assert len(built) == 8
    assert built[0].startswith("home/research-reports::")
    assert built[-1].startswith(
        "market-overview/snapshot::actions,charts,crisis,dates,funding_observation,gate,news,pulse,"
        "rates_observation,signals,tape::"
        "cv_market_overview_snapshot_v8::"
    )


def test_cross_asset_headline_report_date_matches_frontend_slot_selection() -> None:
    payload = {
        "result": {
            "series": [
                {
                    "series_id": "E1000180",
                    "trade_date": "2026-09-04",
                    "quality_flag": "stale",
                },
                {
                    "series_id": "EMM00166466",
                    "trade_date": "2026-09-02",
                    "quality_flag": "ok",
                },
                {
                    "series_id": "CA.BRENT",
                    "trade_date": "2026-09-01",
                    "quality_flag": "ok",
                },
                {
                    "series_id": "CA.COPPER",
                    "trade_date": "2026-09-03",
                    "quality_flag": "ok",
                },
            ]
        }
    }

    assert warmup._cross_asset_headline_report_date(payload) == "2026-09-03"
    assert warmup._cross_asset_headline_report_date({"result": {"series": []}}) is None


def test_signal_confluence_warmup_uses_route_key_and_resolved_strategy_date(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from importlib import import_module

    route = import_module("backend.app.api.routes.market_data_livermore")
    support = import_module("backend.app.services.market_data_livermore_route_support")
    market_data_livermore_service = import_module("backend.app.services.market_data_livermore_service")
    livermore_signal_confluence_service = import_module(
        "backend.app.services.livermore_signal_confluence_service"
    )

    keys: list[str] = []
    signal_calls: list[dict[str, object]] = []
    overlay_reader = object()

    def fake_get_or_build(key: str, builder):
        keys.append(key)
        return builder()

    class Settings:
        duckdb_path = tmp_path / "moss.duckdb"
        choice_stock_catalog_file = tmp_path / "choice-stock.json"

    monkeypatch.setattr(warmup.market_home_response_cache, "get_or_build", fake_get_or_build)
    monkeypatch.setattr(support, "_theme_overlay_reader_from_settings", lambda _settings: overlay_reader)
    monkeypatch.setattr(support, "_theme_overlay_fingerprint", lambda _reader: "overlay-v1")
    monkeypatch.setattr(
        support,
        "_selected_pretrade_external_read",
        lambda **_kwargs: (
            {"status": "unavailable", "reason": "synthetic_unavailable"},
            None,
            "2026-09-02",
            "pretrade=synthetic-unavailable",
        ),
    )
    monkeypatch.setattr(
        market_data_livermore_service,
        "livermore_strategy_envelope_from_catalog",
        lambda **_kwargs: {"result": {"as_of_date": "2026-09-02"}},
    )
    monkeypatch.setattr(
        livermore_signal_confluence_service,
        "livermore_signal_confluence_envelope",
        lambda **kwargs: signal_calls.append(kwargs) or {"result": {}},
    )

    warmup._warm_livermore_signal_confluence(
        settings=Settings(),
        requested_as_of_date="2026-09-03",
        force_refresh=False,
    )

    expected_key = route._livermore_signal_confluence_cache_key(
        duckdb_path=str(Settings.duckdb_path),
        catalog_file=Settings.choice_stock_catalog_file,
        as_of_date="2026-09-02",
        theme_overlay_fingerprint="overlay-v1",
        pretrade_authority_fingerprint="pretrade=synthetic-unavailable",
    )
    assert keys[-1] == expected_key
    assert signal_calls == [
        {
            "duckdb_path": str(Settings.duckdb_path),
            "as_of_date": "2026-09-02",
            "choice_stock_catalog_file": Settings.choice_stock_catalog_file,
            "theme_overlay_reader": overlay_reader,
            "_strategy_calculation_mode": None,
            "_captured_external_inputs": None,
        }
    ]


def test_macro_bond_linkage_warmup_passes_exact_report_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.services import macro_bond_linkage_service

    calls: list[date] = []
    monkeypatch.setattr(
        macro_bond_linkage_service,
        "get_macro_bond_linkage",
        lambda report_date: calls.append(report_date) or {},
    )

    warmup._warm_macro_bond_linkage("2026-09-03")

    assert calls == [date(2026, 9, 3)]
