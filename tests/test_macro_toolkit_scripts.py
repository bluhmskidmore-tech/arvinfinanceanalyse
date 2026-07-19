from __future__ import annotations

import importlib
import importlib.util
import inspect
import py_compile
import sys
import time
from datetime import UTC, date, datetime
from pathlib import Path
from threading import Event, Lock, get_ident
from types import SimpleNamespace

import duckdb
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.app.api.routes.macro_toolkit as macro_toolkit_route
import backend.app.core_finance.macro.toolkit.system_sources as system_sources
from backend.app.api.routes.macro_toolkit import router as macro_toolkit_router
from backend.app.core_finance.macro.crisis_score import (
    classify_crisis_score,
    compute_crisis_indicators,
    compute_crisis_score,
    compute_crisis_score_payload,
)
from backend.app.core_finance.macro.toolkit import (
    get_toolkit_script,
    iter_toolkit_scripts,
)
from backend.app.core_finance.macro.toolkit.runner import (
    OMITTED_SOURCE_SCRIPTS,
    SCRIPTS_DIR,
    TOOLKIT_ROOT,
)
from backend.app.core_finance.macro.toolkit.system_sources import (
    load_series_by_alias,
    load_system_macro_frame,
)
from backend.app.governance.settings import get_settings
from backend.app.repositories.cffex_member_rank_repo import (
    ensure_cffex_member_rank_schema,
)
from backend.app.repositories.governance_repo import GovernanceRepository
from backend.app.repositories.user_scope_repo import UserScopeRepository
from backend.app.security.auth_context import ROLE_HEADER_TRUST_ENV
from backend.app.services import cffex_member_rank_service, macro_toolkit_service

MACRO_TOOLKIT_READ_HEADERS = {"X-User-Id": "macro-toolkit-read-user", "X-User-Role": "viewer"}


def _configure_macro_toolkit_scope_store(tmp_path: Path, monkeypatch):
    sqlite_path = tmp_path / "macro-toolkit-read-scope.db"
    auth_dsn = f"sqlite:///{sqlite_path.as_posix()}"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", auth_dsn)
    monkeypatch.delenv("MOSS_GOVERNANCE_SQL_DSN", raising=False)
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    return UserScopeRepository(auth_dsn)


def _seed_macro_toolkit_read_scope(tmp_path: Path, monkeypatch) -> None:
    _configure_macro_toolkit_scope_store(tmp_path, monkeypatch).grant_scope(
        user_id="*",
        role=None,
        resource="macro_toolkit",
        action="read",
    )


@pytest.fixture(autouse=True)
def _seed_macro_toolkit_read_scope_for_existing_http_tests(request, tmp_path: Path, monkeypatch):
    if request.node.name.startswith("test_macro_toolkit_read_surfaces_require_explicit_read_scope"):
        yield
        return
    _seed_macro_toolkit_read_scope(tmp_path, monkeypatch)
    yield
    get_settings.cache_clear()


@pytest.mark.parametrize(
    ("path", "params"),
    [
        ("/ui/macro/toolkit/scripts", {}),
        ("/ui/macro/toolkit/analysis", {"detail": "core"}),
        ("/ui/macro/toolkit/analysis/strategy-summaries", {}),
        ("/ui/macro/toolkit/adversarial-signal", {}),
        ("/ui/macro/toolkit/choice-stock/refresh-status", {}),
    ],
)
def test_macro_toolkit_read_surfaces_require_explicit_read_scope(
    path: str,
    params: dict[str, object],
    tmp_path: Path,
    monkeypatch,
) -> None:
    _configure_macro_toolkit_scope_store(tmp_path, monkeypatch)
    macro_toolkit_route.market_home_response_cache.invalidate()

    def _unexpected_service_call(*_args, **_kwargs):
        raise AssertionError("Macro toolkit read service should not run without macro_toolkit/read.")

    monkeypatch.setattr(macro_toolkit_route, "_source_checks", _unexpected_service_call)
    monkeypatch.setattr(macro_toolkit_route, "_build_macro_toolkit_analysis", _unexpected_service_call)
    monkeypatch.setattr(macro_toolkit_route, "_build_macro_toolkit_strategy_summaries", _unexpected_service_call)
    monkeypatch.setattr(macro_toolkit_route, "_choice_stock_refresh_status", _unexpected_service_call)
    monkeypatch.setattr(
        macro_toolkit_route.macro_adversarial_signal_service,
        "load_macro_adversarial_signal_payload",
        _unexpected_service_call,
    )

    app = FastAPI()
    app.include_router(macro_toolkit_router)
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get(path, params=params, headers=MACRO_TOOLKIT_READ_HEADERS)

    assert response.status_code == 403, f"Expected 403 for {path}, got {response.status_code}: {response.text}"


def test_macro_toolkit_registry_points_to_migrated_scripts() -> None:
    scripts = {script.name: script for script in iter_toolkit_scripts()}

    assert "signal_aggregator" in scripts
    assert "generate_bond_macro_report" in scripts
    assert "credit_bond_portfolio.py" in OMITTED_SOURCE_SCRIPTS
    assert "credit_bond_portfolio" not in scripts
    assert all(script.path.exists() for script in scripts.values())
    assert all(not script.filename.startswith("_") for script in scripts.values())
    assert get_toolkit_script("signal-aggregator").filename == "signal_aggregator.py"
    assert get_toolkit_script("signal-aggregator").default_data_sources == ("choice", "tushare")
    assert not any(
        dep in {"akshare", "WindPy"}
        for script in scripts.values()
        for dep in script.optional_dependencies
    )


def test_migrated_macro_toolkit_scripts_compile() -> None:
    for path in sorted(SCRIPTS_DIR.glob("*.py")):
        py_compile.compile(str(path), doraise=True)


def test_crisis_score_payload_matches_migrated_script_formula(monkeypatch) -> None:
    monkeypatch.syspath_prepend(str(TOOLKIT_ROOT))
    script = get_toolkit_script("crisis_score_cn")
    spec = importlib.util.spec_from_file_location("_legacy_crisis_score_cn", script.path)
    assert spec is not None and spec.loader is not None
    legacy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(legacy)

    dates = pd.date_range("2025-09-01", periods=150, freq="D")
    hs300_values = []
    usdcny_values = []
    nanhua_values = []
    gov_5y_values = []
    aa_5y_values = []
    dr007_values = []
    repo_7d_values = []
    for idx, _sample_date in enumerate(dates):
        stress = max(0.0, (idx - 105) / 45)
        wave = -1 if idx % 2 else 1
        hs300_values.append(4100.0 + idx * 1.4 + wave * stress * 110.0)
        usdcny_values.append(7.05 + idx * 0.0006 + wave * stress * 0.06)
        nanhua_values.append(980.0 + idx * 0.9 + wave * stress * 44.0)
        gov_5y = 2.20 + idx * 0.0004
        gov_5y_values.append(gov_5y)
        aa_5y_values.append(gov_5y + 0.45 + stress * 0.75)
        dr007_values.append(1.75 + stress * 0.62)
        repo_7d_values.append(1.72)

    legacy_data = {
        "hs300": pd.Series(hs300_values, index=dates),
        "credit_spread": pd.Series([aa - gov for aa, gov in zip(aa_5y_values, gov_5y_values)], index=dates),
        "usdcny": pd.Series(usdcny_values, index=dates),
        "nanhua": pd.Series(nanhua_values, index=dates),
        "dr007": pd.Series(dr007_values, index=dates),
        "reverse_repo": pd.Series(repo_7d_values, index=dates),
    }
    series_data = {
        "hs300": [(sample_date.date(), value) for sample_date, value in zip(dates, hs300_values)],
        "aa_5y": [(sample_date.date(), value) for sample_date, value in zip(dates, aa_5y_values)],
        "gov_5y": [(sample_date.date(), value) for sample_date, value in zip(dates, gov_5y_values)],
        "usdcny": [(sample_date.date(), value) for sample_date, value in zip(dates, usdcny_values)],
        "nanhua": [(sample_date.date(), value) for sample_date, value in zip(dates, nanhua_values)],
        "dr007": [(sample_date.date(), value) for sample_date, value in zip(dates, dr007_values)],
        "reverse_repo_7d": [(sample_date.date(), value) for sample_date, value in zip(dates, repo_7d_values)],
    }

    legacy_indicators = legacy.compute_indicators(legacy_data, vol_window=20)
    indicators = compute_crisis_indicators(series_data, vol_window=20)
    pd.testing.assert_frame_equal(indicators, legacy_indicators, check_exact=False, check_freq=False, rtol=1e-12, atol=1e-12)

    legacy_score = legacy.compute_crisis_score(legacy_indicators, z_window=120)
    score = compute_crisis_score(indicators, z_window=120, min_z_observations=60)
    complete_component_rows = score[[column for column in score.columns if column.endswith("_z")]].notna().all(axis=1)
    pd.testing.assert_frame_equal(
        score.loc[complete_component_rows],
        legacy_score.loc[complete_component_rows],
        check_exact=False,
        check_freq=False,
        rtol=1e-12,
        atol=1e-12,
    )

    latest_score = float(legacy_score["crisis_score"].dropna().iloc[-1])
    payload = compute_crisis_score_payload(series_data, report_date=dates[-1].date())
    assert payload["data_status"] == "complete"
    assert payload["available_component_count"] == 5
    assert payload["warnings"] == []
    assert payload["crisis_score"] == round(latest_score, 4)
    assert payload["regime"] == legacy.classify_regime(latest_score)[0]
    for sample_score in (-0.1, 0.5, 1.5, 2.5, 3.5):
        assert classify_crisis_score(sample_score)[0] == legacy.classify_regime(sample_score)[0]


def test_crisis_score_renormalizes_available_component_weights() -> None:
    dates = pd.date_range("2026-01-01", periods=5, freq="D")
    indicators = pd.DataFrame(
        {
            "equity_vol": [1.0, 2.0, 3.0, 4.0, 5.0],
            "credit_spread": [10.0, 11.0, None, 13.0, 14.0],
        },
        index=dates,
    )

    score = compute_crisis_score(
        indicators,
        z_window=3,
        min_z_observations=2,
        weights={"equity_vol": 0.75, "credit_spread": 0.25},
    )

    missing_credit_date = dates[2]
    assert pd.isna(score.loc[missing_credit_date, "credit_spread_z"])
    assert score.loc[missing_credit_date, "crisis_score"] == pytest.approx(
        score.loc[missing_credit_date, "equity_vol_z"]
    )
    assert score.loc[missing_credit_date, "crisis_score"] != pytest.approx(
        0.75 * score.loc[missing_credit_date, "equity_vol_z"]
    )


def test_crisis_score_flags_stale_component_after_ffill_limit() -> None:
    dates = [sample_date.date() for sample_date in pd.date_range("2026-01-01", periods=30, freq="D")]
    aa_stop_index = 18

    series_data = {
        "hs300": [(sample_date, 4000.0 + idx * 2.0 + (idx % 2) * 8.0) for idx, sample_date in enumerate(dates)],
        "aa_5y": [(sample_date, 2.9 + idx * 0.01) for idx, sample_date in enumerate(dates[:aa_stop_index])],
        "gov_5y": [(sample_date, 2.2 + idx * 0.005) for idx, sample_date in enumerate(dates)],
        "usdcny": [(sample_date, 7.0 + idx * 0.002 + (idx % 2) * 0.01) for idx, sample_date in enumerate(dates)],
        "nanhua": [(sample_date, 1000.0 + idx * 3.0 + (idx % 2) * 10.0) for idx, sample_date in enumerate(dates)],
        "dr007": [(sample_date, 1.8 + idx * 0.01) for idx, sample_date in enumerate(dates)],
        "reverse_repo_7d": [(sample_date, 1.7) for sample_date in dates],
    }

    payload = compute_crisis_score_payload(
        series_data,
        report_date=dates[-1],
        vol_window=2,
        z_window=5,
        min_z_observations=3,
    )

    component_keys = {item["key"] for item in payload["components"]}
    assert "credit_spread" not in component_keys
    assert "CREDIT_SPREAD_STALE" in payload["warnings"]
    assert payload["crisis_score"] is not None


def test_merrill_clock_calculations_match_documented_formula(monkeypatch) -> None:
    monkeypatch.syspath_prepend(str(TOOLKIT_ROOT))
    script = get_toolkit_script("merrill_clock_cn")
    spec = importlib.util.spec_from_file_location("_legacy_merrill_clock_cn", script.path)
    assert spec is not None and spec.loader is not None
    legacy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(legacy)

    series = pd.Series([1, 2, 3, 4, 5, 6], dtype=float)
    momentum = legacy.compute_momentum(series, short_window=2, long_window=4)
    short_mean = pd.Series([5, 6], dtype=float).mean()
    long_window = pd.Series([3, 4, 5, 6], dtype=float)
    expected_momentum = legacy.np.tanh((short_mean - long_window.mean()) / long_window.std())
    assert momentum.iloc[-1] == pytest.approx(expected_momentum)

    liquidity_frame = pd.DataFrame(
        {
            "m2_yoy": [8, 8.1, 8.3, 8.6, 8.8, 9.0],
            "social_financing": [9, 9.1, 9.2, 9.4, 9.6, 9.7],
        },
        dtype=float,
    )
    liquidity = legacy.compute_liquidity_momentum(liquidity_frame)
    expected_liquidity = 0.5 * legacy.compute_momentum(liquidity_frame["m2_yoy"]) + 0.5 * legacy.compute_momentum(
        liquidity_frame["social_financing"]
    )
    assert liquidity.iloc[-1] == pytest.approx(expected_liquidity.iloc[-1])

    scores = legacy.compute_asset_scores(growth=0.8, inflation=0.7, liquidity=0.4)
    expected_stock = legacy.np.tanh(0.45 * 0.8 + 0.15 * 0.7 - 0.3 * (0.7 - 0.5) + 0.40 * 0.4)
    expected_bond = legacy.np.tanh(-0.35 * 0.8 - 0.35 * 0.7 + 0.30 * 0.4)
    assert scores["股票"] == pytest.approx(expected_stock)
    assert scores["债券"] == pytest.approx(expected_bond)
    assert legacy.get_regime_label(growth=0.8, inflation=0.7) == "过热"
    assert legacy.get_regime_label(growth=-0.1, inflation=-0.2) == "衰退"


def test_bond_futures_basis_calculations_match_documented_formula(monkeypatch) -> None:
    monkeypatch.syspath_prepend(str(TOOLKIT_ROOT))
    script = get_toolkit_script("bond_futures_data")
    spec = importlib.util.spec_from_file_location("_legacy_bond_futures_data", script.path)
    assert spec is not None and spec.loader is not None
    legacy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(legacy)

    assert legacy.calc_carry(ytm=0.025, dr007=0.018, maturity=7, coupon=0.03, days=90) == pytest.approx(
        round((0.03 - 0.018) * 90 / 365, 6)
    )
    assert legacy.calc_net_basis(spot_price=101.0, futures_price=100.0, cf=0.98, carry=0.002) == pytest.approx(2.998)
    expected_irr = round(((102.0 * 0.99 - 100.0) / 100.0 * 365 / 90) * 100, 4)
    assert legacy.calc_irr(spot_price=100.0, futures_price=102.0, cf=0.99, coupon=0.03, days_to_delivery=90) == pytest.approx(
        expected_irr
    )


def test_bond_futures_four_factor_vote_and_strength(monkeypatch) -> None:
    monkeypatch.syspath_prepend(str(TOOLKIT_ROOT))
    script = get_toolkit_script("bond_futures_signals")
    spec = importlib.util.spec_from_file_location("_legacy_bond_futures_signals", script.path)
    assert spec is not None and spec.loader is not None
    legacy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(legacy)

    signals = pd.DataFrame(
        {
            "ma": [1, -1, 1],
            "don": [1, -1, 0],
            "macd": [0, -1, 1],
            "bb": [-1, 0, 1],
        },
        index=pd.date_range("2026-06-01", periods=3),
    )

    assert legacy.vote_signal(signals, threshold=2).tolist() == [1, -1, 1]
    assert legacy.signal_strength(1, signals) == "强"
    price = pd.Series([10.0, 10.0, 20.0])
    assert legacy.signal_bollinger(price, window=3, num_std=1.0).iloc[-1] == -1.0


def test_crowding_calculation_matches_documented_formula(monkeypatch) -> None:
    monkeypatch.syspath_prepend(str(TOOLKIT_ROOT))
    script = get_toolkit_script("crowding_cn")
    spec = importlib.util.spec_from_file_location("_legacy_crowding_formula", script.path)
    assert spec is not None and spec.loader is not None
    legacy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(legacy)

    positions = pd.DataFrame(
        [
            {
                "member": legacy.HEDGER_KEYWORDS[0],
                "long_oi": 100,
                "short_oi": 50,
                "long_chg": 10,
                "short_chg": -5,
                "volume": 600,
            },
            {
                "member": "directional-alpha",
                "long_oi": 50,
                "short_oi": 100,
                "long_chg": -4,
                "short_chg": 8,
                "volume": 400,
            },
        ]
    )

    metrics = legacy.calc_crowding(positions)
    assert metrics["SC"] == pytest.approx(0.0)
    assert metrics["HC"] == pytest.approx(0.3333)
    assert metrics["C"] == pytest.approx(0.0333)
    assert metrics["tv_oi_ratio"] == pytest.approx(6.6667)
    assert metrics["hedge_ratio"] == pytest.approx(0.003)


def test_system_choice_tushare_source_layer_reads_default_duckdb(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_choice_tushare_macro_db(duckdb_path)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()

    frame = load_system_macro_frame()
    hs300 = load_series_by_alias("sh000300")
    csi500 = load_series_by_alias("sh000905")
    copper = load_series_by_alias("CU0")
    usdcny = load_series_by_alias("M0067855")
    treasury_5y = load_series_by_alias("S0059747")
    credit_aa_5y = load_series_by_alias("S0059760")
    policy_rate = load_series_by_alias("M0041653")
    ppi = load_series_by_alias("M0001227")
    m2 = load_series_by_alias("M0001385")

    assert {"choice", "tushare"}.issubset(set(frame["vendor_name"]))
    assert hs300["value"].tolist() == [4102.25]
    assert csi500["series_id"].tolist() == ["CA.CSI500"]
    assert csi500["value"].tolist() == [6155.8]
    assert copper["value"].tolist() == [81234.5]
    assert usdcny["value"].tolist() == [7.1234]
    assert treasury_5y["value"].tolist() == [2.34]
    assert credit_aa_5y["value"].tolist() == [2.91]
    assert policy_rate["series_id"].tolist() == ["M001"]
    assert policy_rate["value"].tolist() == [1.75]
    assert ppi["series_id"].tolist() == ["tushare.macro.cn_ppi.monthly"]
    assert ppi["value"].tolist() == [-2.3]
    assert m2["series_id"].tolist() == ["tushare.macro.cn_money.monthly"]
    assert m2["value"].tolist() == [8.1]
    get_settings.cache_clear()


def test_public_cross_asset_refresh_lands_csi500_idempotently_and_shim_resolves(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()

    from backend.app.tasks import choice_macro as task_module

    fixture_rows = [
        {
            "series_id": "CA.CSI300",
            "trade_date": "2026-04-08",
            "value_numeric": 4080.0,
            "vendor_version": "vv_tushare_index_daily_000300SH_20260410",
            "source_version": "sv_tushare_index_daily_fixture",
        },
        {
            "series_id": "CA.CSI500",
            "trade_date": "2026-04-08",
            "value_numeric": 6100.0,
            "vendor_version": "vv_tushare_index_daily_000905SH_20260410",
            "source_version": "sv_tushare_index_daily_000905_fixture",
        },
        {
            "series_id": "CA.CSI500",
            "trade_date": "2026-04-09",
            "value_numeric": 6120.5,
            "vendor_version": "vv_tushare_index_daily_000905SH_20260410",
            "source_version": "sv_tushare_index_daily_000905_fixture",
        },
        {
            "series_id": "CA.CSI500",
            "trade_date": "2026-04-10",
            "value_numeric": 6155.8,
            "vendor_version": "vv_tushare_index_daily_000905SH_20260410",
            "source_version": "sv_tushare_index_daily_000905_fixture",
        },
    ]
    monkeypatch.setattr(task_module, "_load_public_cross_asset_history_rows", lambda **_: list(fixture_rows))

    first = task_module.refresh_public_cross_asset_headlines(
        duckdb_path=str(duckdb_path),
        report_date="2026-04-10",
        lookback_days=90,
    )
    second = task_module.refresh_public_cross_asset_headlines(
        duckdb_path=str(duckdb_path),
        report_date="2026-04-10",
        lookback_days=90,
    )

    assert first["row_count"] == 4
    assert second["row_count"] == 4

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        fact_summary = conn.execute(
            """
            select series_id, count(*), min(trade_date), max(trade_date)
            from fact_choice_macro_daily
            where series_id = 'CA.CSI500'
            group by series_id
            """
        ).fetchone()
        latest = conn.execute(
            """
            select series_id, trade_date, value_numeric, vendor_series_code, vendor_name
            from choice_market_snapshot
            where series_id = 'CA.CSI500'
            """
        ).fetchone()
    finally:
        conn.close()

    assert fact_summary == ("CA.CSI500", 3, "2026-04-08", "2026-04-10")
    assert latest == ("CA.CSI500", "2026-04-10", 6155.8, "index_daily:000905.SH.close", "tushare")

    system_sources.clear_system_macro_source_cache()
    csi500 = load_series_by_alias("sh000905", duckdb_path=duckdb_path)
    assert csi500["series_id"].tolist() == ["CA.CSI500", "CA.CSI500", "CA.CSI500"]
    assert csi500["value"].tolist() == [6100.0, 6120.5, 6155.8]
    get_settings.cache_clear()


def test_series_alias_lookup_reuses_cached_frames_until_duckdb_file_changes(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_choice_tushare_macro_db(duckdb_path)
    original_load_system_macro_frame = system_sources.load_system_macro_frame
    calls: list[object] = []

    def spy_load_system_macro_frame(duckdb_path_arg=None, **kwargs):
        calls.append((duckdb_path_arg, kwargs.get("series_ids")))
        return original_load_system_macro_frame(duckdb_path_arg, **kwargs)

    monkeypatch.setattr(system_sources, "load_system_macro_frame", spy_load_system_macro_frame)

    hs300 = load_series_by_alias("sh000300", duckdb_path=duckdb_path)
    hs300_repeat = load_series_by_alias("sh000300", duckdb_path=duckdb_path)

    assert hs300["value"].tolist() == [4102.25]
    assert hs300_repeat["value"].tolist() == [4102.25]
    # Repeated lookups reuse the cached subset frame: exactly one pushdown load.
    assert len(calls) == 1
    assert calls[0][1] is not None and "CA.CSI300" in calls[0][1]

    copper = load_series_by_alias("CU0", duckdb_path=duckdb_path)
    assert copper["value"].tolist() == [81234.5]
    assert len(calls) == 2

    time.sleep(0.01)
    duckdb_path.touch()
    hs300_after_touch = load_series_by_alias("sh000300", duckdb_path=duckdb_path)
    usdcny = load_series_by_alias("M0067855", duckdb_path=duckdb_path)

    # A file change (mtime) invalidates cached frames for every alias.
    assert hs300_after_touch["value"].tolist() == [4102.25]
    assert usdcny["value"].tolist() == [7.1234]
    assert len(calls) == 4

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            insert into fact_choice_macro_daily values
              ('M0099999', 'Cache invalidation sample', '2026-06-01', 50.5, 'monthly', 'index',
               'sv_cache_test', 'vv_choice', 'rv_cache_test', 'ok', 'run-cache-test')
            """
        )
    finally:
        conn.close()

    cache_invalidation_sample = load_series_by_alias("M0099999", duckdb_path=duckdb_path)

    assert cache_invalidation_sample["series_id"].tolist() == ["M0099999"]
    assert cache_invalidation_sample["value"].tolist() == [50.5]
    assert len(calls) == 5


def test_series_alias_lookup_does_not_rely_on_frame_index_labels(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_choice_tushare_macro_db(duckdb_path)
    original_load_system_macro_frame = system_sources.load_system_macro_frame

    def load_system_macro_frame_with_shifted_index(duckdb_path_arg=None, **kwargs):
        frame = original_load_system_macro_frame(duckdb_path_arg, **kwargs)
        frame.index = pd.RangeIndex(start=10, stop=10 + len(frame))
        return frame

    monkeypatch.setattr(system_sources, "load_system_macro_frame", load_system_macro_frame_with_shifted_index)

    hs300 = load_series_by_alias("sh000300", duckdb_path=duckdb_path)
    copper = load_series_by_alias("CU0", duckdb_path=duckdb_path)

    assert hs300["value"].tolist() == [4102.25]
    assert copper["value"].tolist() == [81234.5]


def test_system_source_layer_reads_merrill_clock_stable_macro_aliases(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_choice_tushare_macro_db(duckdb_path)
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            insert into fact_choice_macro_daily values
              ('M0017126', 'Manufacturing PMI', '2026-05-01', 50.0, 'monthly', 'index',
               'sv_tushare_pmi', 'vv_tushare', 'rv_backfill_macro_v1', 'ok', 'run-pmi'),
              ('M0017127', 'PMI new orders', '2026-05-01', 48.5, 'monthly', 'index',
               'sv_tushare_pmi', 'vv_tushare', 'rv_backfill_macro_v1', 'ok', 'run-pmi'),
              ('M5525763', 'Social financing stock YoY', '2026-04-01', 8.49, 'monthly', '%',
               'sv_tushare_sf', 'vv_tushare', 'rv_backfill_macro_v1', 'ok', 'run-sf')
            """
        )
    finally:
        conn.close()
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()

    pmi = load_series_by_alias("M0017126")
    pmi_new_orders = load_series_by_alias("M0017127")
    ppi = load_series_by_alias("M0001227")
    m2 = load_series_by_alias("M0001385")
    social_financing = load_series_by_alias("M5525763")

    assert pmi["series_id"].tolist() == ["M0017126"]
    assert pmi["value"].tolist() == [50.0]
    assert pmi_new_orders["series_id"].tolist() == ["M0017127"]
    assert pmi_new_orders["value"].tolist() == [48.5]
    assert ppi["series_id"].tolist() == ["tushare.macro.cn_ppi.monthly"]
    assert ppi["value"].tolist() == [-2.3]
    assert m2["series_id"].tolist() == ["tushare.macro.cn_money.monthly"]
    assert m2["value"].tolist() == [8.1]
    assert social_financing["series_id"].tolist() == ["M5525763"]
    assert social_financing["value"].tolist() == [8.49]
    get_settings.cache_clear()


def test_system_source_layer_reads_crisis_external_backfill_aliases(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_choice_tushare_macro_db(duckdb_path)
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            insert into std_external_macro_daily values
              ('NHCI.NH', 'tushare', 'macro', '2026-04-10',
               3099.99, 'daily', 'index', 'sv_tushare_crisis',
               'vv_tushare_index_daily', 'rv_macro_crisis_external_backfill_v1',
               'crisis-backfill-test', 'data/raw/tushare/crisis-backfill/NHCI.NH.json',
               current_timestamp),
          ('legacy.wind_market_db.reverse_repo_7d', 'moss_derived', 'macro', '2026-04-11',
               1.72, 'daily', '%', 'sv_legacy_market_db_crisis',
               'vv_legacy_market_db', 'rv_macro_crisis_external_backfill_v1',
               'crisis-backfill-test', 'D:/MOSS-SYSTEM-V1/data_warehouse/market.db',
               current_timestamp)
            """
        )
        conn.execute(
            """
            insert into external_data_catalog values
              ('NHCI.NH', 'Nanhua commodity index (Tushare)', 'tushare',
               'tushare_index_daily', 'macro', 'daily', 'index', 'on_demand',
               'live_backfill', 'data/raw/tushare/crisis-backfill/NHCI.NH.json',
               'std_external_macro_daily', 'vw_external_macro_daily',
               'select * from std_external_macro_daily where series_id = ''NHCI.NH''',
               'crisis-score-backfill-test', current_timestamp),
              ('legacy.wind_market_db.reverse_repo_7d', 'Open market reverse repo 7D (legacy market DB)', 'wind_legacy_market_db',
               'legacy_market_db', 'macro', 'daily', '%', 'legacy_backfill',
               'local_snapshot', 'D:/MOSS-SYSTEM-V1/data_warehouse/market.db',
               'std_external_macro_daily', 'vw_external_macro_daily',
               'select * from std_external_macro_daily where series_id = ''legacy.wind_market_db.reverse_repo_7d''',
               'crisis-score-backfill-test', current_timestamp)
            """
        )
    finally:
        conn.close()
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()

    nanhua = load_series_by_alias("NH0100.NHF")
    reverse_repo = load_series_by_alias("M0041653", start="2026-04-11")

    assert nanhua["series_id"].tolist() == ["NHCI.NH"]
    assert nanhua["vendor_name"].tolist() == ["tushare"]
    assert nanhua["value"].tolist() == [3099.99]
    assert reverse_repo["series_id"].tolist() == ["legacy.wind_market_db.reverse_repo_7d"]
    assert reverse_repo["vendor_name"].tolist() == ["moss_derived"]
    assert reverse_repo["value"].tolist() == [1.72]
    get_settings.cache_clear()


def test_system_source_layer_reads_nanhua_from_commodity_daily_table(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_choice_tushare_macro_db(duckdb_path)
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_commodity_futures_daily (
              trade_date varchar not null,
              product_code varchar not null,
              contract_code varchar,
              exchange varchar,
              open_value double,
              high_value double,
              low_value double,
              close_value double,
              settle_value double,
              volume double,
              open_interest double,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar default 'rv_commodity_daily_v1',
              created_at timestamp default current_timestamp,
              primary key (trade_date, product_code)
            )
            """
        )
        conn.execute(
            """
            insert into fact_commodity_futures_daily (
              trade_date, product_code, contract_code, exchange,
              open_value, high_value, low_value, close_value, settle_value,
              volume, open_interest, source_version, vendor_version, rule_version
            ) values
              ('2026-05-29', 'NHCI', 'NHCI.NH', 'NH',
               2980.0, 3005.0, 2970.0, 2989.18, null,
               null, null, 'sv_tushare_index_daily_nhci', 'vv_tushare_index_daily_NHCI_20260602',
               'rv_commodity_daily_v1')
            """
        )
    finally:
        conn.close()
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()

    nanhua = load_series_by_alias("NH0100.NHF", start="2026-05-01", end="2026-05-31")

    assert nanhua["series_id"].tolist() == ["NHCI.NH"]
    assert nanhua["vendor_name"].tolist() == ["tushare"]
    assert nanhua["value"].tolist() == [2989.18]
    get_settings.cache_clear()


def test_system_windpy_reads_bond_futures_price_oi_volume_from_daily_table(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_choice_tushare_macro_db(duckdb_path)
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_commodity_futures_daily (
              trade_date varchar not null,
              product_code varchar not null,
              contract_code varchar,
              exchange varchar,
              open_value double,
              high_value double,
              low_value double,
              close_value double,
              settle_value double,
              volume double,
              open_interest double,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar default 'rv_commodity_daily_v1',
              created_at timestamp default current_timestamp,
              primary key (trade_date, product_code)
            )
            """
        )
        conn.execute(
            """
            insert into fact_commodity_futures_daily (
              trade_date, product_code, contract_code, exchange,
              open_value, high_value, low_value, close_value, settle_value,
              volume, open_interest, source_version, vendor_version, rule_version
            ) values
              ('2026-05-28', 'T', 'T2609.CFX', 'CFX',
               102.0, 102.8, 101.9, 102.5, 102.4,
               12345, 67890, 'sv_tushare_fut_daily_t', 'vv_tushare_fut_daily_T_CFX_20260529',
               'rv_commodity_daily_v1'),
              ('2026-05-29', 'T', 'T2609.CFX', 'CFX',
               102.6, 103.0, 102.1, 102.75, 102.7,
               22345, 77890, 'sv_tushare_fut_daily_t', 'vv_tushare_fut_daily_T_CFX_20260529',
               'rv_commodity_daily_v1')
            """
        )
    finally:
        conn.close()
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.syspath_prepend(str(TOOLKIT_ROOT))
    get_settings.cache_clear()

    previous_windpy = sys.modules.pop("WindPy", None)
    try:
        windpy = importlib.import_module("WindPy")
        windpy.w.start()
        result = windpy.w.wsd("T.CFE", "close,oi,volume", "2026-05-28", "2026-05-29")
    finally:
        if previous_windpy is not None:
            sys.modules["WindPy"] = previous_windpy
        else:
            sys.modules.pop("WindPy", None)
        get_settings.cache_clear()

    assert result.ErrorCode == 0
    assert result.Codes == ["T.CFE"]
    assert result.Fields == ["close", "oi", "volume"]
    assert [item.strftime("%Y-%m-%d") for item in result.Times] == ["2026-05-28", "2026-05-29"]
    assert result.Data == [[102.5, 102.75], [67890.0, 77890.0], [12345.0, 22345.0]]


def test_system_sources_read_akshare_formal_treasury_curve_aliases(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_choice_tushare_macro_db(duckdb_path)
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            insert into fact_formal_yield_curve_daily values
              ('2026-06-26', 'treasury', '2Y', 1.2345, 'akshare',
               'vv_akshare_treasury_20260626', 'sv_akshare_treasury_20260626',
               'rv_yield_curve_formal_materialize_v1'),
              ('2026-06-26', 'treasury', '30Y', 2.3456, 'akshare',
               'vv_akshare_treasury_20260626', 'sv_akshare_treasury_20260626',
               'rv_yield_curve_formal_materialize_v1')
            """
        )
    finally:
        conn.close()
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()
    system_sources.clear_system_macro_source_cache()

    two_year = load_series_by_alias("S0059745", start="2026-06-26", end="2026-06-26")
    thirty_year = load_series_by_alias("S0059752", start="2026-06-26", end="2026-06-26")

    assert two_year[["series_id", "vendor_name", "value"]].to_dict("records") == [
        {"series_id": "legacy.yield.akshare.treasury.2Y", "vendor_name": "akshare", "value": 1.2345}
    ]
    assert thirty_year[["series_id", "vendor_name", "value"]].to_dict("records") == [
        {"series_id": "legacy.yield.akshare.treasury.30Y", "vendor_name": "akshare", "value": 2.3456}
    ]
    get_settings.cache_clear()
    system_sources.clear_system_macro_source_cache()


def test_legacy_vendor_imports_resolve_to_system_choice_tushare(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_choice_tushare_macro_db(duckdb_path)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.syspath_prepend(str(TOOLKIT_ROOT))
    get_settings.cache_clear()

    previous_akshare = sys.modules.pop("akshare", None)
    previous_windpy = sys.modules.pop("WindPy", None)
    try:
        akshare = importlib.import_module("akshare")
        windpy = importlib.import_module("WindPy")

        stock = akshare.stock_zh_index_daily("sh000300")
        futures = akshare.futures_main_sina("CU0")
        windpy.w.start()
        result = windpy.w.edb("EDB_CPI_YOY", "2026-04-01", "2026-04-30")
        spread_inputs = windpy.w.wsd("S0059760,M0067855", "close", "2026-04-01", "2026-04-30")
        member_rank = windpy.w.wset("cffexmemberrank", "date=2026-04-10;windcode=T.CFE;rankby=volume")
    finally:
        if previous_akshare is not None:
            sys.modules["akshare"] = previous_akshare
        else:
            sys.modules.pop("akshare", None)
        if previous_windpy is not None:
            sys.modules["WindPy"] = previous_windpy
        else:
            sys.modules.pop("WindPy", None)
        get_settings.cache_clear()

    assert stock["close"].tolist() == [4102.25]
    assert futures["close"].tolist() == [81234.5]
    assert result.ErrorCode == 0
    assert result.Data == [[0.7]]
    assert spread_inputs.ErrorCode == 0
    assert spread_inputs.Data == [[2.91], [7.1234]]
    assert member_rank.ErrorCode == 0
    assert member_rank.Fields == ["membername", "volume"]
    assert member_rank.Data == [["中信期货", "国泰君安"], [12345.0, 8901.0]]


def test_windpy_cffex_member_rank_missing_rows_remain_read_only(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_choice_tushare_macro_db(duckdb_path)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.syspath_prepend(str(TOOLKIT_ROOT))
    get_settings.cache_clear()

    previous_windpy = sys.modules.pop("WindPy", None)
    refresh_calls: list[dict[str, object]] = []
    try:
        windpy = importlib.import_module("WindPy")

        def fail_refresh(**kwargs: object) -> dict[str, object]:
            refresh_calls.append(dict(kwargs))
            raise AssertionError("cffexmemberrank read should not trigger DuckDB writes")

        monkeypatch.setattr(windpy, "ensure_cffex_member_rank_for_request", fail_refresh, raising=False)
        windpy.w.start()
        member_rank = windpy.w.wset("cffexmemberrank", "date=2026-04-11;windcode=T.CFE;rankby=volume")
    finally:
        if previous_windpy is not None:
            sys.modules["WindPy"] = previous_windpy
        else:
            sys.modules.pop("WindPy", None)
        get_settings.cache_clear()

    assert member_rank.ErrorCode == 404
    assert member_rank.Fields == []
    assert refresh_calls == []


def test_crowding_script_reads_system_cffex_cache_for_latest_snapshot(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_choice_tushare_macro_db(duckdb_path)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()

    script = get_toolkit_script("crowding_cn")
    spec = importlib.util.spec_from_file_location("_legacy_crowding_cn", script.path)
    assert spec is not None and spec.loader is not None
    legacy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(legacy)

    try:
        history = legacy.fetch_system_cffex_history(lookback_days=365)
        latest = legacy.generate_crowding_signal(history, window=243)
    finally:
        get_settings.cache_clear()

    assert history[["date", "品种"]].to_dict("records") == [{"date": "2026-04-10", "品种": "T"}]
    assert latest[["品种", "日期", "拥挤度信号"]].to_dict("records") == [
        {"品种": "T", "日期": "2026-04-10", "拥挤度信号": "数据不足"}
    ]
    assert "历史样本不足" in str(latest.iloc[0]["说明"])


def test_signal_aggregator_dates_final_signal_to_latest_input_snapshot(monkeypatch) -> None:
    script = get_toolkit_script("signal_aggregator")
    spec = importlib.util.spec_from_file_location("_legacy_signal_aggregator", script.path)
    assert spec is not None and spec.loader is not None
    legacy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(legacy)

    class _FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 6, 2, 15, 30, tzinfo=tz)

    monkeypatch.setattr(legacy, "datetime", _FrozenDateTime)

    basis_df = pd.DataFrame(
        [
            {
                "品种": "TF",
                "日期": "2026-06-01",
                "安全边际_空": True,
                "安全边际说明": "net basis high",
            }
        ]
    )
    crowding_df = pd.DataFrame(
        [
            {
                "品种": "TF",
                "日期": "2026-06-01",
                "拥挤度信号": "中性",
                "C分位数": 0.5,
                "说明": "neutral",
            }
        ]
    )

    result = legacy.run_three_layer_filter(
        "TF",
        {"bond_direction": "空", "regime": "hot"},
        basis_df,
        crowding_df,
        {"score": 0.0, "status": "normal"},
    )

    assert result["日期"] == "2026-06-01"


def test_risk_monitor_main_writes_risk_state_and_risk_log_when_final_signal_exists(tmp_path, monkeypatch) -> None:
    script = get_toolkit_script("risk_monitor")
    spec = importlib.util.spec_from_file_location("_legacy_risk_monitor", script.path)
    assert spec is not None and spec.loader is not None
    legacy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(legacy)

    output_dir = tmp_path / "macro_toolkit_output"
    output_dir.mkdir()
    state_path = output_dir / "risk_state.csv"
    log_path = output_dir / "risk_log.csv"
    (output_dir / "final_signal.csv").write_text(
        "品种,日期,最终信号,仓位比例\nT,2026-06-01,多,0.25\n",
        encoding="utf-8-sig",
    )
    monkeypatch.setattr(legacy, "ROOT", output_dir)
    monkeypatch.setattr(legacy, "STATE_FILE", state_path)
    monkeypatch.setattr(legacy, "LOG_FILE", log_path)

    legacy.main()

    assert state_path.exists()
    assert log_path.exists()
    state = pd.read_csv(state_path, encoding="utf-8-sig")
    log = pd.read_csv(log_path, encoding="utf-8-sig")
    assert state["peak_value"].iloc[-1] == 1_000_000.0
    assert log["event_type"].iloc[-1] == "DAILY_CHECK"
    assert log["symbol"].iloc[-1] == "ALL"
    assert "active_positions=1" in log["detail"].iloc[-1]


def test_risk_monitor_log_event_appends_without_rewriting_existing_log(tmp_path, monkeypatch) -> None:
    script = get_toolkit_script("risk_monitor")
    spec = importlib.util.spec_from_file_location("_legacy_risk_monitor_append", script.path)
    assert spec is not None and spec.loader is not None
    legacy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(legacy)

    log_path = tmp_path / "risk_log.csv"
    log_path.write_text(
        "datetime,event_type,symbol,detail,current_value,drawdown_pct\n"
        "2026-06-01 15:00:00,DAILY_CHECK,ALL,existing,0.0,0.0\n",
        encoding="utf-8-sig",
    )
    monkeypatch.setattr(legacy, "STATE_FILE", tmp_path / "risk_state.csv")
    monkeypatch.setattr(legacy, "LOG_FILE", log_path)

    original_read_csv = legacy.pd.read_csv

    def fail_if_log_read(path, *args, **kwargs):
        if Path(path) == log_path:
            raise AssertionError("risk log append should not read and rewrite the existing log")
        return original_read_csv(path, *args, **kwargs)

    monkeypatch.setattr(legacy.pd, "read_csv", fail_if_log_read)

    monitor = legacy.RiskMonitor()
    monitor._log_event("DAILY_CHECK", "ALL", "appended")

    log = original_read_csv(log_path, encoding="utf-8-sig")
    assert log["detail"].tolist() == ["existing", "appended"]


def test_cta_trend_main_writes_cta_results_csv_to_output_dir(tmp_path, monkeypatch) -> None:
    script = get_toolkit_script("cta_trend_cn")
    spec = importlib.util.spec_from_file_location("_legacy_cta_trend_cn", script.path)
    assert spec is not None and spec.loader is not None
    legacy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(legacy)

    output_dir = tmp_path / "macro_toolkit_output"
    asset_dir = output_dir / "bond_macro_report_assets"
    output_dir.mkdir()
    asset_dir.mkdir()
    dates = pd.date_range("2026-01-01", periods=90, freq="D")
    prices = pd.DataFrame(
        {
            "hs300": [4000 + idx for idx in range(len(dates))],
            "gold": [500 - idx * 0.5 for idx in range(len(dates))],
        },
        index=dates,
    )
    monkeypatch.setattr(legacy, "ROOT", output_dir)
    monkeypatch.setattr(legacy, "ASSET_DIR", asset_dir)
    monkeypatch.setattr(legacy, "load_prices", lambda: prices)
    monkeypatch.setattr(legacy, "plot_signals", lambda _prices, _signals: asset_dir / "cta_signals.png")

    legacy.main()

    result_path = output_dir / "cta_results.csv"
    assert result_path.exists()
    result = pd.read_csv(result_path, encoding="utf-8-sig")
    assert result["资产"].tolist() == ["沪深300", "黄金"]
    assert "合成信号" in result.columns


def test_signal_aggregator_uses_merrill_snapshot_date_when_filters_are_missing(monkeypatch) -> None:
    script = get_toolkit_script("signal_aggregator")
    spec = importlib.util.spec_from_file_location("_legacy_signal_aggregator_merrill_date", script.path)
    assert spec is not None and spec.loader is not None
    legacy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(legacy)

    class _FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 6, 2, 15, 30, tzinfo=tz)

    monkeypatch.setattr(legacy, "datetime", _FrozenDateTime)

    result = legacy.run_three_layer_filter(
        "TF",
        {"日期": "2026-05", "bond_direction": "空", "regime": "hot"},
        pd.DataFrame(),
        pd.DataFrame(),
        {"score": 0.0, "status": "normal"},
    )

    assert result["日期"] == "2026-05-01"


def test_macro_toolkit_api_exposes_frontend_payload() -> None:
    app = FastAPI()
    app.include_router(macro_toolkit_router)
    client = TestClient(app)

    response = client.get("/ui/macro/toolkit/scripts", headers=MACRO_TOOLKIT_READ_HEADERS)

    assert response.status_code == 200
    payload = response.json()
    scripts = {item["name"]: item for item in payload["result"]["scripts"]}
    assert payload["result"]["default_data_sources"] == ["choice", "tushare"]
    assert all("no formal DuckDB table" not in item for item in payload["result"]["warnings"])
    assert payload["result"]["cffex_member_rank"]["status"] in {
        "ok",
        "missing_database",
        "unreadable_database",
        "missing_table",
        "empty_table",
    }
    assert payload["result"]["choice_stock_refresh"]["permission"]["mode"] == "scoped_refresh"
    commodity_permission = payload["result"]["commodity_futures_refresh"]["permission"]
    assert commodity_permission["mode"] == "scoped_refresh"
    assert commodity_permission["resource"] == "macro_toolkit.commodity_futures"
    assert commodity_permission["actions"] == ["dry_run", "refresh"]
    assert "signal_aggregator" in scripts
    assert scripts["signal_aggregator"]["available"] is True
    assert payload["result_meta"]["tables_used"] == [
        "fact_choice_macro_daily",
        "choice_market_snapshot",
        "fx_daily_mid",
        "fact_formal_yield_curve_daily",
        "std_external_macro_daily",
        "fact_commodity_futures_daily",
        "fact_cffex_member_rank_daily",
        "vw_cffex_member_rank_daily",
        "choice_stock_daily_observation",
        "choice_stock_factor_snapshot",
    ]


def test_macro_toolkit_scripts_surfaces_granted_commodity_futures_permission_for_fallback_user(
    tmp_path, monkeypatch
) -> None:
    sqlite_path = tmp_path / "auth-scope.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.delenv(ROLE_HEADER_TRUST_ENV, raising=False)
    get_settings.cache_clear()
    repo = UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}")
    repo.grant_scope(
        user_id="anonymous",
        role=None,
        resource="macro_toolkit",
        action="read",
    )
    repo.grant_scope(
        user_id="anonymous",
        role=None,
        resource="macro_toolkit.commodity_futures",
        action="refresh",
    )
    app = FastAPI()
    app.include_router(macro_toolkit_router)
    client = TestClient(app)

    response = client.get("/ui/macro/toolkit/scripts")

    assert response.status_code == 200, response.text
    permission = response.json()["result"]["commodity_futures_refresh"]["permission"]
    assert permission["allowed"] is True
    assert permission["identity_source"] == "fallback"
    assert permission["user_id"] == "anonymous"
    assert permission["resource"] == "macro_toolkit.commodity_futures"


def test_macro_toolkit_scripts_surfaces_empty_commodity_futures_status(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()
    app = FastAPI()
    app.include_router(macro_toolkit_router)
    client = TestClient(app)

    missing_response = client.get("/ui/macro/toolkit/scripts", headers=MACRO_TOOLKIT_READ_HEADERS)
    assert missing_response.status_code == 200, missing_response.text
    missing_status = missing_response.json()["result"]["commodity_futures_refresh"]["status"]
    assert missing_status["status"] == "missing_table"
    assert missing_status["row_count"] is None
    assert missing_status["latest_trade_date"] is None
    assert missing_status["nanhua_input"]["status"] == "missing_table"
    assert missing_status["nanhua_input"]["series_id"] == "NH0100.NHF"

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_commodity_futures_daily (
              trade_date varchar not null,
              product_code varchar not null,
              contract_code varchar,
              exchange varchar,
              open_value double,
              high_value double,
              low_value double,
              close_value double,
              settle_value double,
              volume double,
              open_interest double,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar default 'rv_commodity_daily_v1',
              created_at timestamp default current_timestamp,
              primary key (trade_date, product_code)
            )
            """
        )
    finally:
        conn.close()

    empty_response = client.get("/ui/macro/toolkit/scripts", headers=MACRO_TOOLKIT_READ_HEADERS)
    assert empty_response.status_code == 200, empty_response.text
    empty_status = empty_response.json()["result"]["commodity_futures_refresh"]["status"]
    assert empty_status["status"] == "empty_table"
    assert empty_status["row_count"] == 0
    assert empty_status["latest_trade_date"] is None
    assert empty_status["coverage"]["available_product_count"] == 0
    assert empty_status["nanhua_input"]["status"] == "missing"
    get_settings.cache_clear()


def test_macro_toolkit_scripts_surfaces_commodity_futures_health_from_daily_table(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_commodity_futures_daily (
              trade_date varchar not null,
              product_code varchar not null,
              contract_code varchar,
              exchange varchar,
              open_value double,
              high_value double,
              low_value double,
              close_value double,
              settle_value double,
              volume double,
              open_interest double,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar default 'rv_commodity_daily_v1',
              created_at timestamp default current_timestamp,
              primary key (trade_date, product_code)
            )
            """
        )
        conn.execute(
            """
            insert into fact_commodity_futures_daily (
              trade_date, product_code, contract_code, exchange,
              open_value, high_value, low_value, close_value, settle_value,
              volume, open_interest, source_version, vendor_version, rule_version
            ) values
              ('20260429', 'CU', 'CU2606.SHF', 'SHF',
               72000.0, 72400.0, 71800.0, 72200.0, 72100.0,
               12000, 88000, 'sv_tushare_fut_daily_cu', 'vv_tushare_fut_daily_CU_SHF_20260430',
               'rv_commodity_daily_v1'),
              ('20260430', 'CU', 'CU2606.SHF', 'SHF',
               72200.0, 72900.0, 72100.0, 72800.0, 72700.0,
               13000, 89000, 'sv_tushare_fut_daily_cu', 'vv_tushare_fut_daily_CU_SHF_20260430',
               'rv_commodity_daily_v1'),
              ('2026-04-30', 'NHCI', 'NHCI.NH', 'NH',
               3180.0, 3190.0, 3170.0, 3187.42, null,
               null, null, 'sv_tushare_index_daily_nhci', 'vv_tushare_index_daily_NHCI_20260430',
               'rv_commodity_daily_v1')
            """
        )
    finally:
        conn.close()
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()
    app = FastAPI()
    app.include_router(macro_toolkit_router)
    client = TestClient(app)

    response = client.get("/ui/macro/toolkit/scripts")

    assert response.status_code == 200, response.text
    status = response.json()["result"]["commodity_futures_refresh"]["status"]
    assert status["status"] == "ok"
    assert status["row_count"] == 3
    assert status["latest_trade_date"] == "2026-04-30"
    assert status["coverage"]["available_product_count"] == 2
    assert status["coverage"]["target_product_count"] == 7
    assert status["coverage"]["available_products"] == ["CU", "NHCI"]
    assert status["coverage"]["products"][0]["latest_trade_date"] == "2026-04-30"
    assert status["source_vendors"] == ["tushare"]
    assert status["nanhua_input"] == {
        "status": "hit",
        "product_code": "NHCI",
        "series_id": "NH0100.NHF",
        "system_series_id": "NHCI.NH",
        "latest_trade_date": "2026-04-30",
        "latest_value": 3187.42,
        "row_count": 1,
        "source_version": "sv_tushare_index_daily_nhci",
        "vendor_version": "vv_tushare_index_daily_NHCI_20260430",
        "rule_version": "rv_commodity_daily_v1",
    }
    get_settings.cache_clear()


def test_macro_toolkit_scripts_normalizes_mixed_commodity_dates_before_latest_selection(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_commodity_futures_daily (
              trade_date varchar not null,
              product_code varchar not null,
              contract_code varchar,
              exchange varchar,
              open_value double,
              high_value double,
              low_value double,
              close_value double,
              settle_value double,
              volume double,
              open_interest double,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar default 'rv_commodity_daily_v1',
              created_at timestamp default current_timestamp,
              primary key (trade_date, product_code)
            )
            """
        )
        conn.execute(
            """
            insert into fact_commodity_futures_daily (
              trade_date, product_code, contract_code, exchange,
              open_value, high_value, low_value, close_value, settle_value,
              volume, open_interest, source_version, vendor_version, rule_version
            ) values
              ('20260520', 'CU', 'CU2606.SHF', 'SHF',
               72000.0, 72400.0, 71800.0, 72200.0, 72100.0,
               12000, 88000, 'sv_tushare_fut_daily_cu', 'vv_tushare_fut_daily_CU_SHF_20260520',
               'rv_commodity_daily_v1'),
              ('20260520', 'NHCI', 'NHCI.NH', 'NH',
               3000.0, 3010.0, 2990.0, 3007.05, null,
               null, null, 'sv_tushare_index_daily_nhci_old', 'vv_tushare_index_daily_NHCI_20260520',
               'rv_commodity_daily_v1'),
              ('2026-06-01', 'NHCI', 'NHCI.NH', 'NH',
               3180.0, 3190.0, 3170.0, 3187.42, null,
               null, null, 'sv_tushare_index_daily_nhci_new', 'vv_tushare_index_daily_NHCI_20260601',
               'rv_commodity_daily_v1')
            """
        )
    finally:
        conn.close()
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()
    app = FastAPI()
    app.include_router(macro_toolkit_router)
    client = TestClient(app)

    response = client.get("/ui/macro/toolkit/scripts")

    assert response.status_code == 200, response.text
    status = response.json()["result"]["commodity_futures_refresh"]["status"]
    assert status["latest_trade_date"] == "2026-06-01"
    nanhua_product = next(
        item for item in status["coverage"]["products"] if item["product_code"] == "NHCI"
    )
    assert nanhua_product["latest_trade_date"] == "2026-06-01"
    assert status["nanhua_input"]["latest_trade_date"] == "2026-06-01"
    assert status["nanhua_input"]["latest_value"] == 3187.42
    assert status["nanhua_input"]["source_version"] == "sv_tushare_index_daily_nhci_new"
    get_settings.cache_clear()


def test_cffex_member_rank_refresh_materializes_tushare_rows(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    monkeypatch.setattr(
        cffex_member_rank_service,
        "resolve_tushare_token_with_settings_fallback",
        lambda _settings: "token",
    )
    monkeypatch.setattr(cffex_member_rank_service, "import_tushare_pro", lambda: _FakeTushareModule())

    result = cffex_member_rank_service.materialize_cffex_member_rank(
        duckdb_path=duckdb_path,
        trade_date="2026-04-10",
        contracts=("T.CFE",),
        sources=("tushare",),
    )

    assert result["row_count"] == 2
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        rows = conn.execute(
            """
            select trade_date, contract, member_name, source_vendor, volume, long_holding, short_holding
            from fact_cffex_member_rank_daily
            order by source_row_no
            """
        ).fetchall()
    finally:
        conn.close()
    assert rows == [
        ("2026-04-10", "T.CFE", "中信期货", "tushare", 12345.0, 23456.0, 21000.0),
        ("2026-04-10", "T.CFE", "国泰君安", "tushare", 8901.0, 10000.0, 14000.0),
    ]


def test_cffex_member_rank_refresh_materializes_choice_rows(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    monkeypatch.setattr(cffex_member_rank_service, "ChoiceClient", lambda: _FakeChoiceClient())

    result = cffex_member_rank_service.materialize_cffex_member_rank(
        duckdb_path=duckdb_path,
        trade_date="2026-04-10",
        contracts=("T.CFE",),
        sources=("choice",),
    )

    assert result["row_count"] == 1
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        row = conn.execute(
            """
            select trade_date, contract, member_name, source_vendor, volume, long_holding, short_holding
            from fact_cffex_member_rank_daily
            """
        ).fetchone()
    finally:
        conn.close()
    assert row == ("2026-04-10", "T.CFE", "中信期货", "choice", 12345.0, 23456.0, 21000.0)


def test_macro_toolkit_api_exposes_analysis_payload(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_choice_tushare_macro_db(duckdb_path)
    # 补齐国债 1Y/3Y/7Y 正式曲线节点：M8/M13/M15 的 data_aliases 修正为实际
    # 消费的曲线输入（S0059743/S0059746/S0059748）后，能力矩阵在输入齐备时
    # 应保持 ready；这些节点经 legacy.yield.choice.treasury.* 解析命中。
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            insert into fact_formal_yield_curve_daily values
              ('2026-04-10', 'treasury', '1Y', 1.62, 'choice',
               'vv_choice_curve', 'sv_choice_curve', 'rv_yield_curve_formal_materialize_v1'),
              ('2026-04-10', 'treasury', '3Y', 1.98, 'choice',
               'vv_choice_curve', 'sv_choice_curve', 'rv_yield_curve_formal_materialize_v1'),
              ('2026-04-10', 'treasury', '7Y', 2.41, 'choice',
               'vv_choice_curve', 'sv_choice_curve', 'rv_yield_curve_formal_materialize_v1')
            """
        )
    finally:
        conn.close()
    output_dir = tmp_path / "macro_toolkit_output"
    output_dir.mkdir()
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setattr(macro_toolkit_route, "OUTPUT_DIR", output_dir)
    get_settings.cache_clear()
    app = FastAPI()
    app.include_router(macro_toolkit_router)
    client = TestClient(app)

    try:
        response = client.get("/ui/macro/toolkit/analysis")
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["default_data_sources"] == ["choice", "tushare"]
    assert payload["result"]["conclusion"]["stance"]
    assert payload["result"]["coverage"]["hit_count"] >= 6
    data_health = payload["result"]["data_health"]
    assert data_health["analysis_scope"] == "full"
    assert data_health["indicator_coverage"] == {
        "hit_count": 7,
        "total_count": 8,
        "hit_rate": 0.875,
        "missing_count": 1,
        "missing": [
            {
                "key": "ncd_3m",
                "alias": "M0041813",
                "label": "3M NCD",
            }
        ],
    }
    assert data_health["source_coverage"] == {
        "hit_count": 8,
        "total_count": 9,
        "hit_rate": 0.8889,
        "latest_date": "2026-04-10",
        "deferred": False,
        "missing_aliases": ["M0041813"],
    }
    # 种子补齐国债 1Y/3Y/7Y 后，M8 曲线形态由 unavailable 变为 complete。
    assert data_health["capability_results"] == {
        "complete": 1,
        "degraded": 5,
        "unavailable": 5,
        "total_count": 11,
        "deferred": False,
    }
    # ready=6：种子补齐国债 1Y/3Y/7Y 后，除原有 2 个 ready 能力外，
    # M7（原声明即含 S0059743）、M8、M13、M15 的声明输入全部命中。
    assert data_health["capability_plan"] == {
        "ready_count": 6,
        "wired_count": 11,
        "total_count": 11,
        "deferred": False,
    }
    assert data_health["warnings"] == []
    model_readiness = payload["result"]["model_readiness"]
    readiness_by_id = {item["id"]: item for item in model_readiness}
    assert readiness_by_id["dcc_garch"]["readiness"] == "missing_output"
    assert readiness_by_id["dcc_garch"]["missing_outputs"] == ["dcc_latest.csv", "dcc_results.csv"]
    assert readiness_by_id["dcc_garch"]["observation_only"] is True
    assert readiness_by_id["dcc_garch"]["formal_use_allowed"] is False
    assert readiness_by_id["cta_trend"]["readiness"] == "missing_output"
    assert readiness_by_id["cta_trend"]["missing_outputs"] == ["cta_results.csv"]
    assert readiness_by_id["final_signal"]["readiness"] == "missing_output"
    assert payload["result"]["readiness_summary"]["observation_only"] is True
    assert payload["result"]["readiness_summary"]["formal_use_allowed"] is False
    repair_items = data_health["repair_items"]
    ncd_repair = next(item for item in repair_items if item["key"] == "indicator:ncd_3m")
    assert ncd_repair == {
        "type": "missing",
        "scope": "full",
        "priority": "high",
        "key": "indicator:ncd_3m",
        "alias": "M0041813",
        "label": "3M NCD",
        "source_table": None,
        "latest_date": None,
        "reference_date": "2026-04-10",
        "stale_days": None,
        "suggested_action": "补齐 M0041813 后重新运行完整宏观分析；缺失项不能按 0 处理。",
        "action": {
            "kind": "source_backfill_required",
            "label": "需要补齐来源数据",
            "enabled": True,
            "reason": "可触发宏观来源补齐；完成后重新运行完整分析确认。",
            "analysis_detail": "full",
        },
        "tags": ["indicator"],
    }
    leading_repair = next(item for item in repair_items if item["key"] == "capability:leading_indicator")
    assert leading_repair["type"] == "degraded"
    assert leading_repair["scope"] == "full"
    assert leading_repair["priority"] == "medium"
    assert leading_repair["label"] == "宏观领先指标"
    assert "宏观领先指标 当前 degraded" in leading_repair["suggested_action"]
    assert "PMI_MISSING" in leading_repair["suggested_action"]
    assert leading_repair["action"] == {
        "kind": "load_full_analysis",
        "label": "重新完整分析",
        "enabled": True,
        "reason": "补齐输入证据后重新运行完整分析确认状态。",
        "analysis_detail": "full",
    }
    assert {item["key"] for item in payload["result"]["signal_cards"]} == {
        "crisis_score_cn",
        "a_share_stampede_risk",
        "liquidity",
        "risk_appetite",
        "credit",
        "outputs",
    }
    a_share_risk = payload["result"]["a_share_risk"]
    assert a_share_risk["status"] == "unavailable"
    assert a_share_risk["risk_level"] == "unknown"
    assert a_share_risk["risk_score"] is None
    risk_card = next(item for item in payload["result"]["signal_cards"] if item["key"] == "a_share_stampede_risk")
    assert risk_card["tone"] == "missing"
    capability_results = {item["key"]: item for item in payload["result"]["capability_results"]}
    assert set(capability_results) == {
        "monetary_policy_stance",
        "yield_curve_shape",
        "credit_spread_risk",
        "leading_indicator",
        "liquidity_stress",
        "crisis_score_cn",
        "cross_market_linkage",
        "rate_turning_point",
        "economic_cycle",
        "macro_portfolio_impact",
        "decision_summary",
    }
    assert capability_results["decision_summary"]["headline"]
    assert capability_results["decision_summary"]["status"] in {"complete", "degraded"}
    monetary_policy = capability_results["monetary_policy_stance"]
    policy_inputs = {
        item["field"]: item
        for item in monetary_policy["result"]["input_evidence"]["inputs"]
    }
    assert "POLICY_RATE_7D_MISSING" not in monetary_policy["warnings"]
    assert policy_inputs["policy_rate_7d"]["series_id"] == "M001"
    assert policy_inputs["policy_rate_7d"]["latest_date"] == "2026-04-10"
    assert monetary_policy["result"]["key_metrics"]["policy_rate_curve_id"] == "CN_RRP"
    assert monetary_policy["result"]["key_metrics"]["dr007"] == 1.82

    leading_indicator = capability_results["leading_indicator"]
    leading_missing = set(leading_indicator["result"]["input_evidence"]["missing_inputs"])
    assert leading_indicator["status"] == "degraded"
    assert {"PMI_MISSING", "SOCIAL_FINANCING_YOY_MISSING", "CREDIT_SPREAD_AAA_MISSING"}.issubset(leading_missing)
    assert "M2_YOY_MISSING" in leading_missing

    economic_cycle = capability_results["economic_cycle"]
    cycle_missing = set(economic_cycle["result"]["input_evidence"]["missing_inputs"])
    assert economic_cycle["status"] == "degraded"
    assert {"PMI_MISSING", "SOCIAL_FINANCING_YOY_MISSING"}.issubset(cycle_missing)
    assert "PPI_YOY_MISSING" in cycle_missing
    assert "M2_YOY_MISSING" in cycle_missing
    indicators = {item["alias"]: item for item in payload["result"]["indicators"]}
    assert indicators["DR007.IB"]["latest_value"] == 1.82
    assert indicators["S0059749"]["latest_value"] == 2.48
    hason_strategy = payload["result"]["hason_strategy"]
    assert hason_strategy["key"] == "hason_macro_strategy"
    assert hason_strategy["basis"] == "analytical"
    assert hason_strategy["observation_only"] is True
    assert hason_strategy["formal_use_allowed"] is False
    assert hason_strategy["formal_metric_id"] is None
    assert hason_strategy["display_status"] == "visible"
    assert {item["key"] for item in hason_strategy["modules"]} == {
        "market_state",
        "allocation",
        "strategy_selection",
        "risk_management",
        "performance_review",
    }
    assert all(item["status"] == "integrated" for item in hason_strategy["modules"])
    assert all(item["missing_scripts"] == [] for item in hason_strategy["modules"])
    assert hason_strategy["readiness"] == {
        "ready_modules": 5,
        "partial_modules": 0,
        "missing_modules": 0,
        "missing_script_count": 0,
        "total_modules": 5,
        "ratio": 1.0,
    }
    assert {"final_signal.csv", "crowding_latest.csv"}.issubset(
        set(hason_strategy["missing_runtime_outputs"])
    )
    assert all("freshness_basis" in item for item in hason_strategy["runtime_outputs"])
    assert all("content_date" in item for item in hason_strategy["runtime_outputs"])
    assert all(item["freshness_basis"] == "missing" for item in hason_strategy["runtime_outputs"])
    assert all(item["content_date"] is None for item in hason_strategy["runtime_outputs"])
    assert any(
        item["script"] == "signal_aggregator" and item["available"]
        for item in hason_strategy["source_trace"]
    )
    strategy_summaries = {item["key"]: item for item in payload["result"]["strategy_summaries"]}
    assert set(strategy_summaries) == {
        "moving_average",
        "mean_reversion_momentum",
        "multi_factor_selection",
        "low_crowding_regime_multifactor",
    }
    assert strategy_summaries["moving_average"]["status"] == "sample_only"
    assert strategy_summaries["low_crowding_regime_multifactor"]["status"] == "sample_only"
    assert strategy_summaries["low_crowding_regime_multifactor"]["result"]["regime"]
    assert strategy_summaries["multi_factor_selection"]["primary_metric"]["label"] == "样例入选数量"


def test_hason_module_payload_marks_partially_available_script_chain(tmp_path) -> None:
    available_script = tmp_path / "signal_aggregator.py"
    available_script.write_text("# available", encoding="utf-8")
    missing_script = tmp_path / "crowding_cn.py"

    payload = macro_toolkit_route._hason_module_payload(
        {
            "key": "strategy_selection",
            "label": "Strategy selection",
            "scripts": ("signal_aggregator", "crowding_cn"),
            "evidence": ("final signal", "crowding filter"),
        },
        {
            "signal_aggregator": SimpleNamespace(path=available_script),
            "crowding_cn": SimpleNamespace(path=missing_script),
        },
    )

    assert payload["status"] == "partial"
    assert payload["available_scripts"] == ["signal_aggregator"]
    assert payload["missing_scripts"] == ["crowding_cn"]


def test_hason_summary_counts_partial_modules_and_missing_scripts(tmp_path, monkeypatch) -> None:
    script_names = {
        str(script_name)
        for module in macro_toolkit_route._HASON_MODULES
        for script_name in module["scripts"]
    }
    scripts = []
    for name in script_names:
        path = tmp_path / f"{name}.py"
        if name != "rebalance_cn":
            path.write_text("# available", encoding="utf-8")
        scripts.append(
            SimpleNamespace(
                name=name,
                path=path,
                filename=f"{name}.py",
                group="macro",
            )
        )
    monkeypatch.setattr(macro_toolkit_route, "iter_toolkit_scripts", lambda: iter(scripts))

    payload = macro_toolkit_route._hason_macro_strategy_summary(
        [{"name": "final_signal.csv"}, {"name": "crowding_latest.csv"}]
    )

    assert payload["status"] == "degraded"
    assert payload["readiness"] == {
        "ready_modules": 4,
        "partial_modules": 1,
        "missing_modules": 0,
        "missing_script_count": 1,
        "total_modules": 5,
        "ratio": 0.8,
    }


def test_hason_summary_counts_shared_missing_script_once(tmp_path, monkeypatch) -> None:
    script_names = {
        str(script_name)
        for module in macro_toolkit_route._HASON_MODULES
        for script_name in module["scripts"]
    }
    scripts = []
    for name in script_names:
        path = tmp_path / f"{name}.py"
        if name != "dcc_garch_cn":
            path.write_text("# available", encoding="utf-8")
        scripts.append(
            SimpleNamespace(
                name=name,
                path=path,
                filename=f"{name}.py",
                group="macro",
            )
        )
    monkeypatch.setattr(macro_toolkit_route, "iter_toolkit_scripts", lambda: iter(scripts))

    payload = macro_toolkit_route._hason_macro_strategy_summary(
        [{"name": "final_signal.csv"}, {"name": "crowding_latest.csv"}]
    )

    assert payload["readiness"]["partial_modules"] == 2
    assert payload["readiness"]["missing_script_count"] == 1


def test_hason_source_trace_keeps_shared_script_module_context(tmp_path, monkeypatch) -> None:
    script_names = {
        str(script_name)
        for module in macro_toolkit_route._HASON_MODULES
        for script_name in module["scripts"]
    }
    scripts = []
    for name in script_names:
        path = tmp_path / f"{name}.py"
        path.write_text("# available", encoding="utf-8")
        scripts.append(
            SimpleNamespace(
                name=name,
                path=path,
                filename=f"{name}.py",
                group="macro",
            )
        )
    monkeypatch.setattr(macro_toolkit_route, "iter_toolkit_scripts", lambda: iter(scripts))

    payload = macro_toolkit_route._hason_macro_strategy_summary(
        [{"name": "final_signal.csv"}, {"name": "crowding_latest.csv"}]
    )

    trace_by_script = {item["script"]: item for item in payload["source_trace"]}
    assert trace_by_script["dcc_garch_cn"]["modules"] == ["market_state", "risk_management"]
    assert trace_by_script["risk_parity_cn"]["modules"] == ["allocation"]


def test_hason_summary_marks_existing_outputs_stale_against_analysis_date(tmp_path, monkeypatch) -> None:
    scripts = []
    for module in macro_toolkit_route._HASON_MODULES:
        for name in module["scripts"]:
            script_name = str(name)
            path = tmp_path / f"{script_name}.py"
            path.write_text("# available", encoding="utf-8")
            scripts.append(
                SimpleNamespace(
                    name=script_name,
                    path=path,
                    filename=f"{script_name}.py",
                    group="macro",
                )
            )
    monkeypatch.setattr(macro_toolkit_route, "iter_toolkit_scripts", lambda: iter(scripts))

    stale_modified_at = datetime(2026, 4, 29, 15, 0, tzinfo=UTC).isoformat()
    payload = macro_toolkit_route._hason_macro_strategy_summary(
        [
            {"name": "final_signal.csv", "modified_at": stale_modified_at},
            {"name": "crowding_latest.csv", "modified_at": stale_modified_at},
        ],
        analysis_date="2026-04-30",
    )

    assert payload["status"] == "degraded"
    assert payload["runtime_output_status"] == "stale"
    assert payload["stale_runtime_outputs"] == ["final_signal.csv", "crowding_latest.csv"]
    assert all(item["freshness_status"] == "stale" for item in payload["runtime_outputs"])


def test_hason_summary_compares_output_freshness_in_cn_business_date(tmp_path, monkeypatch) -> None:
    scripts = []
    for module in macro_toolkit_route._HASON_MODULES:
        for name in module["scripts"]:
            script_name = str(name)
            path = tmp_path / f"{script_name}.py"
            path.write_text("# available", encoding="utf-8")
            scripts.append(
                SimpleNamespace(
                    name=script_name,
                    path=path,
                    filename=f"{script_name}.py",
                    group="macro",
                )
            )
    monkeypatch.setattr(macro_toolkit_route, "iter_toolkit_scripts", lambda: iter(scripts))

    generated_after_cn_midnight = datetime(2026, 4, 29, 16, 30, tzinfo=UTC).isoformat()
    payload = macro_toolkit_route._hason_macro_strategy_summary(
        [
            {"name": "final_signal.csv", "modified_at": generated_after_cn_midnight},
            {"name": "crowding_latest.csv", "modified_at": generated_after_cn_midnight},
        ],
        analysis_date="2026-04-30",
    )

    assert payload["status"] == "observation_ready"
    assert payload["runtime_output_status"] == "current"
    assert payload["stale_runtime_outputs"] == []
    assert all(item["modified_date"] == "2026-04-30" for item in payload["runtime_outputs"])
    assert payload["observation_only"] is True
    assert payload["formal_use_allowed"] is False


def test_hason_summary_prefers_csv_content_date_over_file_modified_date(tmp_path, monkeypatch) -> None:
    scripts = []
    for module in macro_toolkit_route._HASON_MODULES:
        for name in module["scripts"]:
            script_name = str(name)
            path = tmp_path / f"{script_name}.py"
            path.write_text("# available", encoding="utf-8")
            scripts.append(
                SimpleNamespace(
                    name=script_name,
                    path=path,
                    filename=f"{script_name}.py",
                    group="macro",
                )
            )
    monkeypatch.setattr(macro_toolkit_route, "iter_toolkit_scripts", lambda: iter(scripts))

    final_signal_path = tmp_path / "final_signal.csv"
    crowding_path = tmp_path / "crowding_latest.csv"
    final_signal_path.write_text("品种,日期,最终信号\nT,2026-04-29,空仓\n", encoding="utf-8-sig")
    crowding_path.write_text("品种,日期,C\nT,2026-04-29,0.5\n", encoding="utf-8-sig")
    current_modified_at = datetime(2026, 4, 29, 16, 30, tzinfo=UTC).isoformat()

    payload = macro_toolkit_route._hason_macro_strategy_summary(
        [
            {"name": "final_signal.csv", "path": str(final_signal_path), "modified_at": current_modified_at},
            {"name": "crowding_latest.csv", "path": str(crowding_path), "modified_at": current_modified_at},
        ],
        analysis_date="2026-04-30",
    )

    assert payload["status"] == "degraded"
    assert payload["runtime_output_status"] == "stale"
    assert payload["stale_runtime_outputs"] == ["final_signal.csv", "crowding_latest.csv"]
    assert all(item["content_date"] == "2026-04-29" for item in payload["runtime_outputs"])
    assert all(item["freshness_basis"] == "csv_content" for item in payload["runtime_outputs"])


def test_hason_summary_marks_future_csv_content_date_unknown(tmp_path, monkeypatch) -> None:
    scripts = []
    for module in macro_toolkit_route._HASON_MODULES:
        for name in module["scripts"]:
            script_name = str(name)
            path = tmp_path / f"{script_name}.py"
            path.write_text("# available", encoding="utf-8")
            scripts.append(
                SimpleNamespace(
                    name=script_name,
                    path=path,
                    filename=f"{script_name}.py",
                    group="macro",
                )
            )
    monkeypatch.setattr(macro_toolkit_route, "iter_toolkit_scripts", lambda: iter(scripts))

    final_signal_path = tmp_path / "final_signal.csv"
    crowding_path = tmp_path / "crowding_latest.csv"
    final_signal_path.write_text("品种,日期,最终信号\nT,2026-05-02,空仓\n", encoding="utf-8-sig")
    crowding_path.write_text("品种,日期,C\nT,2026-05-02,0.5\n", encoding="utf-8-sig")
    current_modified_at = datetime(2026, 4, 30, 10, 0, tzinfo=UTC).isoformat()

    payload = macro_toolkit_route._hason_macro_strategy_summary(
        [
            {"name": "final_signal.csv", "path": str(final_signal_path), "modified_at": current_modified_at},
            {"name": "crowding_latest.csv", "path": str(crowding_path), "modified_at": current_modified_at},
        ],
        analysis_date="2026-04-30",
    )

    assert payload["status"] == "degraded"
    assert payload["runtime_output_status"] == "unknown"
    assert payload["runtime_output_gaps"] == ["final_signal.csv", "crowding_latest.csv"]
    assert [item["freshness_status"] for item in payload["runtime_outputs"]] == ["future", "future"]
    assert all(item["content_date"] == "2026-05-02" for item in payload["runtime_outputs"])


def test_hason_summary_marks_mixed_csv_content_dates_unknown(tmp_path, monkeypatch) -> None:
    scripts = []
    for module in macro_toolkit_route._HASON_MODULES:
        for name in module["scripts"]:
            script_name = str(name)
            path = tmp_path / f"{script_name}.py"
            path.write_text("# available", encoding="utf-8")
            scripts.append(
                SimpleNamespace(
                    name=script_name,
                    path=path,
                    filename=f"{script_name}.py",
                    group="macro",
                )
            )
    monkeypatch.setattr(macro_toolkit_route, "iter_toolkit_scripts", lambda: iter(scripts))

    final_signal_path = tmp_path / "final_signal.csv"
    crowding_path = tmp_path / "crowding_latest.csv"
    final_signal_path.write_text(
        "品种,日期,最终信号\nT,2026-04-29,空仓\nTL,2026-04-30,空仓\n",
        encoding="utf-8-sig",
    )
    crowding_path.write_text("品种,日期,C\nT,2026-04-30,0.5\nTL,2026-04-30,0.6\n", encoding="utf-8-sig")
    current_modified_at = datetime(2026, 4, 30, 10, 0, tzinfo=UTC).isoformat()

    payload = macro_toolkit_route._hason_macro_strategy_summary(
        [
            {"name": "final_signal.csv", "path": str(final_signal_path), "modified_at": current_modified_at},
            {"name": "crowding_latest.csv", "path": str(crowding_path), "modified_at": current_modified_at},
        ],
        analysis_date="2026-04-30",
    )

    assert payload["status"] == "degraded"
    assert payload["runtime_output_status"] == "unknown"
    assert payload["runtime_output_gaps"] == ["final_signal.csv"]
    final_signal = payload["runtime_outputs"][0]
    assert final_signal["freshness_status"] == "mixed"
    assert final_signal["content_date"] == "2026-04-30"
    assert final_signal["content_date_min"] == "2026-04-29"
    assert final_signal["content_date_max"] == "2026-04-30"


def test_hason_output_content_dates_reads_latest_row_beyond_preview_window(tmp_path) -> None:
    output_path = tmp_path / "final_signal.csv"
    rows = ["品种,日期,最终信号"]
    rows.extend(f"T{index},2026-04-29,空仓" for index in range(500))
    rows.append("T500,2026-04-30,空仓")
    output_path.write_text("\n".join(rows) + "\n", encoding="utf-8-sig")

    content_dates = macro_toolkit_route._hason_output_content_dates({"path": str(output_path)})

    assert content_dates["min"] == "2026-04-29"
    assert content_dates["max"] == "2026-04-30"
    assert content_dates["invalid_count"] == 0
    assert content_dates["date_column"] in macro_toolkit_route._HASON_OUTPUT_DATE_COLUMNS


def test_hason_summary_marks_invalid_csv_content_dates_unknown(tmp_path, monkeypatch) -> None:
    scripts = []
    for module in macro_toolkit_route._HASON_MODULES:
        for name in module["scripts"]:
            script_name = str(name)
            path = tmp_path / f"{script_name}.py"
            path.write_text("# available", encoding="utf-8")
            scripts.append(
                SimpleNamespace(
                    name=script_name,
                    path=path,
                    filename=f"{script_name}.py",
                    group="macro",
                )
            )
    monkeypatch.setattr(macro_toolkit_route, "iter_toolkit_scripts", lambda: iter(scripts))

    final_signal_path = tmp_path / "final_signal.csv"
    crowding_path = tmp_path / "crowding_latest.csv"
    final_signal_path.write_text(
        "品种,日期,最终信号\nT,2026-04-30,空仓\nTL,not-a-date,空仓\n",
        encoding="utf-8-sig",
    )
    crowding_path.write_text("品种,日期,C\nT,2026-04-30,0.5\nTL,2026-04-30,0.6\n", encoding="utf-8-sig")
    current_modified_at = datetime(2026, 4, 30, 10, 0, tzinfo=UTC).isoformat()

    payload = macro_toolkit_route._hason_macro_strategy_summary(
        [
            {"name": "final_signal.csv", "path": str(final_signal_path), "modified_at": current_modified_at},
            {"name": "crowding_latest.csv", "path": str(crowding_path), "modified_at": current_modified_at},
        ],
        analysis_date="2026-04-30",
    )

    assert payload["status"] == "degraded"
    assert payload["runtime_output_status"] == "unknown"
    assert payload["runtime_output_gaps"] == ["final_signal.csv"]
    final_signal = payload["runtime_outputs"][0]
    assert final_signal["freshness_status"] == "invalid_date"
    assert final_signal["freshness_basis"] == "csv_content"
    assert final_signal["content_date_invalid_count"] == 1


def test_hason_summary_does_not_treat_empty_csv_date_column_as_current(tmp_path, monkeypatch) -> None:
    scripts = []
    for module in macro_toolkit_route._HASON_MODULES:
        for name in module["scripts"]:
            script_name = str(name)
            path = tmp_path / f"{script_name}.py"
            path.write_text("# available", encoding="utf-8")
            scripts.append(
                SimpleNamespace(
                    name=script_name,
                    path=path,
                    filename=f"{script_name}.py",
                    group="macro",
                )
            )
    monkeypatch.setattr(macro_toolkit_route, "iter_toolkit_scripts", lambda: iter(scripts))

    final_signal_path = tmp_path / "final_signal.csv"
    crowding_path = tmp_path / "crowding_latest.csv"
    final_signal_path.write_text("asset,date,signal\nT,,short\nTL,,flat\n", encoding="utf-8")
    crowding_path.write_text("asset,date,crowding\nT,2026-04-30,0.5\nTL,2026-04-30,0.6\n", encoding="utf-8")
    current_modified_at = datetime(2026, 4, 30, 10, 0, tzinfo=UTC).isoformat()

    payload = macro_toolkit_route._hason_macro_strategy_summary(
        [
            {"name": "final_signal.csv", "path": str(final_signal_path), "modified_at": current_modified_at},
            {"name": "crowding_latest.csv", "path": str(crowding_path), "modified_at": current_modified_at},
        ],
        analysis_date="2026-04-30",
    )

    assert payload["status"] == "degraded"
    assert payload["runtime_output_status"] == "unknown"
    assert payload["runtime_output_gaps"] == ["final_signal.csv"]
    final_signal = payload["runtime_outputs"][0]
    assert final_signal["freshness_status"] == "unknown"
    assert final_signal["freshness_basis"] == "csv_content"
    assert final_signal["content_date"] is None
    assert final_signal["content_date_invalid_count"] == 0


def test_macro_toolkit_analysis_core_scope_defers_slow_sections(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_choice_tushare_macro_db(duckdb_path)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()

    def fail_if_called(*_args: object, **_kwargs: object) -> list[dict[str, object]]:
        raise AssertionError("core analysis should not compute deferred macro toolkit sections")

    monkeypatch.setattr(macro_toolkit_route, "_macro_capability_results", fail_if_called)
    monkeypatch.setattr(macro_toolkit_route, "_equity_strategy_summaries", fail_if_called)
    monkeypatch.setattr(macro_toolkit_route, "_source_checks", fail_if_called)
    monkeypatch.setattr(macro_toolkit_route, "_capability_plan", fail_if_called)
    monkeypatch.setattr(macro_toolkit_route, "_a_share_stampede_risk", fail_if_called)

    app = FastAPI()
    app.include_router(macro_toolkit_router)
    client = TestClient(app)

    try:
        response = client.get("/ui/macro/toolkit/analysis?detail=core")
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["runtime_status"]["analysis_scope"] == "core"
    assert {
        item["key"] for item in result["runtime_status"]["deferred_sections"]
    } == {"capability_results", "strategy_summaries", "a_share_risk", "source_checks", "capabilities"}
    assert result["capability_results"] == []
    assert result["strategy_summaries"] == []
    assert result["source_checks"] == []
    assert result["capabilities"] == []
    assert result["data_health"]["analysis_scope"] == "core"
    assert result["data_health"]["indicator_coverage"]["hit_count"] == 7
    assert result["data_health"]["indicator_coverage"]["total_count"] == 8
    assert result["data_health"]["indicator_coverage"]["missing"][0]["alias"] == "M0041813"
    assert result["data_health"]["source_coverage"] == {
        "hit_count": 0,
        "total_count": 0,
        "hit_rate": None,
        "latest_date": None,
        "deferred": True,
        "missing_aliases": [],
    }
    assert result["data_health"]["capability_results"]["deferred"] is True
    assert result["data_health"]["capability_plan"]["deferred"] is True
    assert "source_checks" in result["data_health"]["deferred_sections"]
    repair_items = result["data_health"]["repair_items"]
    assert any(
        item["type"] == "deferred"
        and item["key"] == "deferred:source_checks"
        and item["scope"] == "core"
        and item["suggested_action"] == "打开完整分析后确认 source_checks，不把首屏延后加载当作缺失。"
        for item in repair_items
    )
    assert not any(item["key"].startswith("source:") for item in repair_items)
    assert result["a_share_risk"] is None
    assert {item["key"] for item in result["signal_cards"]} == {
        "crisis_score_cn",
        "a_share_stampede_risk",
        "liquidity",
        "risk_appetite",
        "credit",
        "outputs",
    }
    crisis_card = next(item for item in result["signal_cards"] if item["key"] == "crisis_score_cn")
    assert crisis_card["stance"] == "完整结果待加载"
    assert crisis_card["tone"] == "neutral"
    assert crisis_card["score"] is None
    assert crisis_card["evidence"] == ["首屏未运行完整 Crisis Score，打开完整分析后显示分数"]
    risk_card = next(item for item in result["signal_cards"] if item["key"] == "a_share_stampede_risk")
    assert risk_card["tone"] == "missing"


def test_macro_toolkit_data_health_marks_stale_sources_as_repair_items() -> None:
    data_health = macro_toolkit_route._analysis_data_health(
        indicators=[
            {
                "key": "hs300",
                "alias": "sh000300",
                "label": "沪深300",
                "latest_value": 4100.0,
            }
        ],
        source_checks=[
            {
                "alias": "CU0",
                "row_count": 120,
                "latest": {
                    "date": "2026-04-01",
                    "series_id": "CA.COPPER",
                    "vendor_name": "tushare",
                    "value": 81234.5,
                },
            },
            {
                "alias": "M0000612",
                "row_count": 12,
                "latest": {
                    "date": "2026-03-01",
                    "series_id": "cn_cpi_yoy",
                    "vendor_name": "choice",
                    "value": 0.7,
                },
            }
        ],
        capability_results=[],
        capabilities=[],
        runtime_status={"analysis_scope": "full", "deferred_sections": []},
        warnings=[],
        reference_date="2026-04-10",
    )

    assert data_health["repair_items"] == [
        {
            "type": "stale",
            "scope": "full",
            "priority": "medium",
            "key": "source:CU0",
            "alias": "CU0",
            "label": "CU0",
            "source_table": "system_macro_sources",
            "latest_date": "2026-04-01",
            "reference_date": "2026-04-10",
            "stale_days": 9,
            "suggested_action": "CU0 最新 2026-04-01，落后分析日 2026-04-10 9 天；刷新 Choice/Tushare 后再确认。",
            "action": {
                "kind": "source_backfill_required",
                "label": "需要刷新来源",
                "enabled": False,
                "reason": "当前没有已接入的一键宏观序列刷新接口。",
                "analysis_detail": "full",
            },
            "tags": ["source"],
        }
    ]


def test_macro_toolkit_strategy_summaries_endpoint_returns_deferred_strategy_payload(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_choice_tushare_macro_db(duckdb_path)
    _seed_choice_stock_strategy_db(duckdb_path)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()
    app = FastAPI()
    app.include_router(macro_toolkit_router)
    client = TestClient(app)

    try:
        response = client.get("/ui/macro/toolkit/analysis/strategy-summaries")
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    payload = response.json()
    strategies = {item["key"]: item for item in payload["result"]["strategy_summaries"]}
    assert strategies["moving_average"]["status"] == "complete"
    assert strategies["moving_average"]["result"]["price_source"] == "choice_stock_daily_observation"
    assert payload["result"]["choice_stock_refresh"]["daily_observation"]["latest_trade_date"] == "2026-04-30"
    assert "choice_stock_daily_observation" in payload["result_meta"]["tables_used"]


def test_macro_toolkit_strategy_summaries_reuses_loaded_factor_snapshot_for_shadow(
    tmp_path,
    monkeypatch,
) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    duckdb.connect(str(duckdb_path), read_only=False).close()
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()
    dates = pd.date_range("2026-01-01", periods=90, freq="D")
    prices = pd.DataFrame(
        {
            "000001.SZ": [10.0 + idx * 0.03 for idx in range(len(dates))],
            "000002.SZ": [12.0 + idx * 0.02 for idx in range(len(dates))],
        },
        index=dates,
    )
    observations = macro_toolkit_route._sample_strategy_observations(prices)
    financials = pd.DataFrame(
        {
            "stock_code": ["000001.SZ", "000002.SZ"],
            "pe": [8.0, 18.0],
            "pb": [0.8, 2.2],
            "ps": [1.0, 3.0],
            "roe": [0.22, 0.12],
            "gross_margin": [0.45, 0.30],
            "three_month_return": [0.18, 0.08],
            "twelve_month_return": [0.42, 0.10],
            "volatility": [0.16, 0.25],
            "dividend_yield": [0.06, 0.03],
            "industry": ["technology", "consumer"],
        }
    ).set_index("stock_code")
    financials.attrs["factor_as_of_date"] = "2026-04-30"
    price_context = {
        "prices": prices,
        "observations": observations,
        "financials": financials,
        "as_of_date": "2026-04-30",
        "tables_used": ["choice_stock_daily_observation", "choice_stock_factor_snapshot"],
        "source_versions": ["sv_stock"],
        "vendor_versions": ["vv_stock"],
    }
    context_loads = 0
    shadow_calls: list[pd.DataFrame | None] = []

    def fake_load_price_context(duckdb_path_arg: object) -> dict[str, object]:
        nonlocal context_loads
        assert Path(duckdb_path_arg) == duckdb_path
        context_loads += 1
        return price_context

    def fake_shadow_report(
        duckdb_path_arg: object,
        *,
        latest_factor_snapshot: pd.DataFrame | None = None,
    ) -> dict[str, object]:
        assert Path(duckdb_path_arg) == duckdb_path
        shadow_calls.append(latest_factor_snapshot)
        return {"status": "complete", "tables_used": ["choice_stock_factor_snapshot"]}

    monkeypatch.setattr(macro_toolkit_route, "_load_equity_strategy_price_context", fake_load_price_context)
    monkeypatch.setattr(macro_toolkit_route, "compute_equity_shadow_portfolio_report", fake_shadow_report)
    monkeypatch.setattr(
        macro_toolkit_route,
        "_choice_stock_refresh_overview",
        lambda *_args, **_kwargs: {"daily_observation": {"latest_trade_date": "2026-04-30"}},
    )

    try:
        payload = macro_toolkit_route._build_macro_toolkit_strategy_summaries()
    finally:
        get_settings.cache_clear()

    assert context_loads == 1
    assert len(shadow_calls) == 1
    assert shadow_calls[0] is financials
    assert payload["result"]["strategy_summaries"][0]["status"] == "complete"
    assert payload["result"]["shadow_portfolio_report"]["status"] == "complete"


class _TrackedMacroToolkitConnection:
    def __init__(self, connection: object, *, fail_query_contains: str | None = None) -> None:
        self._connection = connection
        self._fail_query_contains = fail_query_contains
        self.queries: list[str] = []
        self.close_count = 0
        self.thread_id = get_ident()
        self.use_thread_ids: set[int] = set()

    def execute(self, query: str, parameters: object | None = None):
        current_thread_id = get_ident()
        self.use_thread_ids.add(current_thread_id)
        assert current_thread_id == self.thread_id, "DuckDB connection crossed worker threads"
        normalized = " ".join(query.casefold().split())
        self.queries.append(normalized)
        if self._fail_query_contains and self._fail_query_contains in normalized:
            raise duckdb.IOException("forced factor snapshot read failure")
        if parameters is None:
            return self._connection.execute(query)
        return self._connection.execute(query, parameters)

    def close(self) -> None:
        assert get_ident() == self.thread_id, "DuckDB connection closed from a different worker thread"
        self.close_count += 1
        self._connection.close()


def _track_macro_toolkit_connections(
    monkeypatch,
    *,
    fail_query_contains: str | None = None,
) -> list[_TrackedMacroToolkitConnection]:
    real_connect = macro_toolkit_service.duckdb.connect
    connections: list[_TrackedMacroToolkitConnection] = []

    def tracked_connect(*args, **kwargs) -> _TrackedMacroToolkitConnection:
        tracked = _TrackedMacroToolkitConnection(
            real_connect(*args, **kwargs),
            fail_query_contains=fail_query_contains,
        )
        connections.append(tracked)
        return tracked

    monkeypatch.setattr(macro_toolkit_service.duckdb, "connect", tracked_connect)
    return connections


def test_equity_strategy_price_context_loads_price_rows_as_dataframe(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    duckdb_path.write_bytes(b"placeholder")
    dates = pd.date_range("2026-01-01", periods=90, freq="D")
    price_rows = pd.DataFrame(
        [
            {
                "trade_date": trade_date.date(),
                "stock_code": stock_code,
                "close_value": 10.0 + row_no * 0.1 + stock_no,
                "amount": 1000.0 + stock_no,
                "pctchange": 0.1,
                "turn": 1.0,
                "amplitude": 2.0,
                "highlimit": 20.0,
                "lowlimit": 5.0,
                "source_version": "sv_stock",
                "vendor_version": "vv_stock",
            }
            for row_no, trade_date in enumerate(dates)
            for stock_no, stock_code in enumerate(("000001.SZ", "000002.SZ"), start=1)
        ]
    )
    price_query_used_df = False

    class FakeResult:
        def __init__(self, *, row: tuple[object, ...] | None = None, rows: list[tuple[object, ...]] | None = None, frame: pd.DataFrame | None = None) -> None:
            self._row = row
            self._rows = rows or []
            self._frame = frame

        def fetchone(self) -> tuple[object, ...] | None:
            return self._row

        def fetchall(self) -> list[tuple[object, ...]]:
            if self._frame is not None:
                raise AssertionError("price rows should be loaded through DuckDB .df(), not fetchall()")
            return self._rows

        def df(self) -> pd.DataFrame:
            nonlocal price_query_used_df
            price_query_used_df = True
            if self._frame is None:
                raise AssertionError("unexpected df() call")
            return self._frame.copy()

    class FakeConnection:
        def execute(self, query: str, parameters: object | None = None) -> FakeResult:
            normalized = " ".join(query.casefold().split())
            if normalized == "show tables":
                return FakeResult(rows=[("choice_stock_daily_observation",)])
            if "max(trade_date)" in normalized:
                assert "max(try_cast(trade_date as date))" not in normalized
                assert "try_cast(max(trade_date) as date)" in normalized
                return FakeResult(row=(dates[-1].date(),))
            if "latest_sample" in normalized and "choice_stock_daily_observation" in normalized:
                assert "where trade_date = ?" in normalized
                assert "where daily.trade_date > ? and daily.trade_date <= ?" in normalized
                assert "order by daily.trade_date asc, daily.stock_code asc" in normalized
                assert "try_cast(daily.trade_date as date) as trade_date" in normalized
                assert "where try_cast" not in normalized
                assert parameters == ["2026-03-31", "2025-07-14", "2026-03-31"]
                return FakeResult(frame=price_rows)
            raise AssertionError(f"unexpected query: {query}")

        def close(self) -> None:
            pass

    monkeypatch.setattr(macro_toolkit_service.duckdb, "connect", lambda *_args, **_kwargs: FakeConnection())
    monkeypatch.setattr(
        macro_toolkit_service,
        "_duckdb_date_column_is_canonical_iso",
        lambda *_args, **_kwargs: True,
        raising=False,
    )
    monkeypatch.setattr(macro_toolkit_service, "load_equity_strategy_factor_snapshot", lambda *_args, **_kwargs: None)

    context = macro_toolkit_service.load_equity_strategy_price_context(duckdb_path)

    assert context is not None
    assert price_query_used_df is True
    assert context["prices"].shape == (90, 2)
    assert len(context["observations"]) == len(price_rows)


def test_equity_strategy_price_and_factor_share_one_connection(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_choice_stock_strategy_db(duckdb_path)
    _seed_choice_stock_factor_snapshot(duckdb_path)
    connections = _track_macro_toolkit_connections(monkeypatch)

    context = macro_toolkit_service.load_equity_strategy_price_context(duckdb_path)

    assert context is not None
    assert isinstance(context["financials"], pd.DataFrame)
    assert len(connections) == 1
    assert connections[0].close_count == 1
    assert any("from choice_stock_daily_observation" in query for query in connections[0].queries)
    assert any("from choice_stock_factor_snapshot" in query for query in connections[0].queries)


def test_equity_strategy_factor_failure_keeps_price_context_and_closes_once(
    tmp_path,
    monkeypatch,
) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_choice_stock_strategy_db(duckdb_path)
    _seed_choice_stock_factor_snapshot(duckdb_path)
    connections = _track_macro_toolkit_connections(
        monkeypatch,
        fail_query_contains="from choice_stock_factor_snapshot",
    )

    context = macro_toolkit_service.load_equity_strategy_price_context(duckdb_path)

    assert context is not None
    assert context["financials"] is None
    assert context["tables_used"] == ["choice_stock_daily_observation"]
    assert len(connections) == 1
    assert connections[0].close_count == 1


def test_equity_strategy_price_context_delegates_to_service(tmp_path, monkeypatch) -> None:
    expected_context = {
        "prices": pd.DataFrame({"000001.SZ": [10.0, 10.2]}),
        "observations": pd.DataFrame({"stock_code": ["000001.SZ"]}),
        "as_of_date": "2026-04-30",
        "tables_used": ["choice_stock_daily_observation"],
        "source_versions": ["sv_stock"],
        "vendor_versions": ["vv_stock"],
    }
    calls: list[object] = []

    def fake_load_equity_strategy_price_context(duckdb_path: object) -> dict[str, object]:
        calls.append(duckdb_path)
        return expected_context

    monkeypatch.setattr(
        macro_toolkit_service,
        "load_equity_strategy_price_context",
        fake_load_equity_strategy_price_context,
        raising=False,
    )

    duckdb_path = tmp_path / "moss.duckdb"

    assert macro_toolkit_route._load_equity_strategy_price_context(duckdb_path) is expected_context
    assert calls == [duckdb_path]
    assert "duckdb.connect" not in inspect.getsource(macro_toolkit_route._load_equity_strategy_price_context)


def test_a_share_stampede_risk_context_loads_observations_as_dataframe(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    duckdb_path.write_bytes(b"placeholder")
    dates = pd.date_range("2026-04-01", periods=40, freq="D")
    observation_rows = pd.DataFrame(
        [
            {
                "trade_date": trade_date.date(),
                "stock_code": stock_code,
                "open_value": 10.0 + stock_no,
                "high_value": 10.5 + stock_no,
                "low_value": 9.5 + stock_no,
                "close_value": 10.2 + stock_no,
                "amount": 1000.0 + stock_no,
                "pctchange": 0.1,
                "turn": 1.0,
                "amplitude": 2.0,
                "tradestatus": "Trading",
                "highlimit": 20.0,
                "lowlimit": 5.0,
                "source_version": "sv_stock",
                "vendor_version": "vv_stock",
            }
            for trade_date in dates
            for stock_no, stock_code in enumerate(("000001.SZ", "000002.SZ"), start=1)
        ]
    )
    observation_query_used_df = False

    class FakeResult:
        def __init__(
            self,
            *,
            row: tuple[object, ...] | None = None,
            frame: pd.DataFrame | None = None,
        ) -> None:
            self._row = row
            self._frame = frame

        def fetchone(self) -> tuple[object, ...] | None:
            return self._row

        def fetchall(self) -> list[tuple[object, ...]]:
            if self._frame is not None:
                raise AssertionError("A-share observations should be loaded through DuckDB .df(), not fetchall()")
            return []

        def df(self) -> pd.DataFrame:
            nonlocal observation_query_used_df
            observation_query_used_df = True
            if self._frame is None:
                raise AssertionError("unexpected df() call")
            return self._frame.copy()

    class FakeConnection:
        def execute(self, query: str, parameters: object | None = None) -> FakeResult:
            normalized = " ".join(query.casefold().split())
            if "max(trade_date)" in normalized:
                assert "max(try_cast(trade_date as date))" not in normalized
                assert "try_cast(max(trade_date) as date)" in normalized
                return FakeResult(row=(dates[-1].date(),))
            if "latest_sample" in normalized and "choice_stock_daily_observation" in normalized:
                assert "where trade_date = ?" in normalized
                assert "where daily.trade_date > ? and daily.trade_date <= ?" in normalized
                assert "order by daily.trade_date asc, daily.stock_code asc" in normalized
                assert "try_cast(daily.trade_date as date) as trade_date" in normalized
                assert "where try_cast" not in normalized
                assert parameters == ["2026-05-10", "2026-04-05", "2026-05-10"]
                return FakeResult(frame=observation_rows)
            raise AssertionError(f"unexpected query: {query}")

        def close(self) -> None:
            pass

    monkeypatch.setattr(macro_toolkit_service.duckdb, "connect", lambda *_args, **_kwargs: FakeConnection())
    monkeypatch.setattr(
        macro_toolkit_service,
        "_duckdb_date_column_is_canonical_iso",
        lambda *_args, **_kwargs: True,
        raising=False,
    )
    monkeypatch.setattr(
        macro_toolkit_service,
        "_duckdb_table_exists",
        lambda _conn, table_name: table_name == "choice_stock_daily_observation",
    )

    context = macro_toolkit_service.load_a_share_stampede_risk_context(duckdb_path)

    assert context is not None
    assert observation_query_used_df is True
    assert context["observations"].shape == (len(observation_rows), len(observation_rows.columns))
    assert context["tables_used"] == ["choice_stock_daily_observation"]


def test_macro_toolkit_hotpath_iso_dates_keep_boundary_and_date_output_types(
    tmp_path,
    monkeypatch,
) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    daily_dates = pd.date_range("2026-02-09", "2026-04-30", freq="D")
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar, stock_code varchar, open_value double, high_value double,
              low_value double, close_value double, amount double, pctchange double,
              turn double, amplitude double, tradestatus varchar, highlimit varchar,
              lowlimit varchar, source_version varchar, vendor_version varchar
            )
            """
        )
        daily_rows = [
            (
                trade_date.date().isoformat(),
                stock_code,
                10.0 + stock_number,
                10.5 + stock_number,
                9.5 + stock_number,
                10.2 + stock_number + row_number * 0.01,
                1000.0 + stock_number,
                0.1,
                1.0,
                2.0,
                "Trading",
                "20.0",
                "5.0",
                "sv_stock",
                "vv_stock",
            )
            for row_number, trade_date in enumerate(daily_dates)
            for stock_number, stock_code in enumerate(
                ("000001.SZ", "000002.SZ"),
                start=1,
            )
        ]
        conn.executemany(
            "insert into choice_stock_daily_observation values "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                *reversed(daily_rows),
                (
                    "2026-2-01",
                    "999999.SZ",
                    1.0,
                    1.0,
                    1.0,
                    1.0,
                    1.0,
                    0.0,
                    0.0,
                    0.0,
                    "Trading",
                    "2.0",
                    "0.5",
                    "sv_dirty",
                    "vv_dirty",
                ),
                (
                    "not-a-date",
                    "888888.SZ",
                    1.0,
                    1.0,
                    1.0,
                    1.0,
                    1.0,
                    0.0,
                    0.0,
                    0.0,
                    "Trading",
                    "2.0",
                    "0.5",
                    "sv_dirty",
                    "vv_dirty",
                ),
            ],
        )
        conn.execute(
            """
            create table fact_formal_risk_tensor_daily (
              report_date varchar, total_market_value double, issuer_top5_weight double,
              portfolio_dv01 double, bond_count integer, asset_cashflow_30d double,
              asset_cashflow_90d double, liability_cashflow_30d double,
              liability_cashflow_90d double, liquidity_gap_30d double,
              liquidity_gap_90d double, liquidity_gap_30d_ratio double, ignored_payload varchar
            )
            """
        )
        conn.executemany(
            "insert into fact_formal_risk_tensor_daily values "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("2026-05-01", 300.0, 0.3, 3.0, 3, 30.0, 90.0, 15.0, 45.0, 15.0, 45.0, 0.05, "future"),
                ("2026-04-29", 100.0, 0.1, 1.0, 1, 10.0, 30.0, 5.0, 15.0, 5.0, 15.0, 0.05, "prior"),
                ("2026-04-30", 200.0, 0.2, 2.0, 2, 20.0, 60.0, 10.0, 30.0, 10.0, 30.0, 0.05, "boundary"),
            ],
        )
    finally:
        conn.close()

    monkeypatch.setattr(
        macro_toolkit_service,
        "load_equity_strategy_factor_snapshot",
        lambda *_args, **_kwargs: None,
    )

    price_context = macro_toolkit_service.load_equity_strategy_price_context(duckdb_path)
    risk_row = macro_toolkit_service.load_latest_risk_tensor_row(
        duckdb_path,
        date(2026, 4, 30),
    )

    assert price_context is not None
    assert price_context["as_of_date"] == "2026-04-30"
    assert price_context["observations"]["trade_date"].iloc[0] == pd.Timestamp("2026-02-09")
    assert isinstance(price_context["observations"]["trade_date"].iloc[0], pd.Timestamp)
    assert price_context["observations"]["trade_date"].iloc[-1] == pd.Timestamp("2026-04-30")
    assert risk_row is not None
    assert risk_row["total_market_value"] == 200.0
    assert "ignored_payload" not in risk_row


def test_latest_risk_tensor_row_falls_back_for_noncanonical_date_storage(
    tmp_path,
) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_formal_risk_tensor_daily (
              report_date varchar, total_market_value double, issuer_top5_weight double,
              portfolio_dv01 double, bond_count integer, asset_cashflow_30d double,
              asset_cashflow_90d double, liability_cashflow_30d double,
              liability_cashflow_90d double, liquidity_gap_30d double,
              liquidity_gap_90d double, liquidity_gap_30d_ratio double
            )
            """
        )
        conn.executemany(
            "insert into fact_formal_risk_tensor_daily values "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("2026-01-31", 100.0, 0.1, 1.0, 1, 10.0, 30.0, 5.0, 15.0, 5.0, 15.0, 0.05),
                ("2026-2-01", 200.0, 0.2, 2.0, 2, 20.0, 60.0, 10.0, 30.0, 10.0, 30.0, 0.05),
            ],
        )
    finally:
        conn.close()

    row = macro_toolkit_service.load_latest_risk_tensor_row(
        duckdb_path,
        date(2026, 4, 30),
    )

    assert row is not None
    assert row["total_market_value"] == 200.0


def test_canonical_date_probe_is_cached_by_duckdb_file_version(tmp_path) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    writer = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        writer.execute(
            "create table choice_stock_daily_observation (trade_date varchar)"
        )
        writer.execute(
            "insert into choice_stock_daily_observation values ('2026-04-30')"
        )
    finally:
        writer.close()

    def probe_with_new_connection() -> tuple[bool, int]:
        raw = duckdb.connect(str(duckdb_path), read_only=True)
        probe_queries = 0

        class CountingConnection:
            def execute(
                self,
                query: str,
                parameters: object | None = None,
            ) -> object:
                nonlocal probe_queries
                normalized = " ".join(query.casefold().split())
                if "parsed_date is null" in normalized:
                    probe_queries += 1
                if parameters is None:
                    return raw.execute(query)
                return raw.execute(query, parameters)

        try:
            result = macro_toolkit_service._duckdb_date_column_is_canonical_iso(
                CountingConnection(),  # type: ignore[arg-type]
                "choice_stock_daily_observation",
                "trade_date",
                database_path=duckdb_path,
            )
        finally:
            raw.close()
        return result, probe_queries

    assert probe_with_new_connection() == (True, 1)
    assert probe_with_new_connection() == (True, 0)

    writer = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        writer.execute(
            "insert into choice_stock_daily_observation values ('2026-4-30')"
        )
    finally:
        writer.close()

    assert probe_with_new_connection() == (False, 1)


def test_latest_risk_tensor_row_uses_pushdown_safe_projected_query(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    duckdb_path.write_bytes(b"placeholder")
    expected_columns = {
        "total_market_value",
        "issuer_top5_weight",
        "portfolio_dv01",
        "bond_count",
        "asset_cashflow_30d",
        "asset_cashflow_90d",
        "liability_cashflow_30d",
        "liability_cashflow_90d",
        "liquidity_gap_30d",
        "liquidity_gap_90d",
        "liquidity_gap_30d_ratio",
    }

    class FakeResult:
        def fetchdf(self) -> pd.DataFrame:
            return pd.DataFrame(
                [
                    {
                        column: row_number
                        for row_number, column in enumerate(sorted(expected_columns), start=1)
                    }
                ]
            )

    class FakeConnection:
        def execute(self, query: str, parameters: object | None = None) -> FakeResult:
            normalized = " ".join(query.casefold().split())
            assert "select *" not in normalized
            assert "try_cast(report_date as date)" not in normalized
            assert "where report_date <= ?" in normalized
            assert "order by report_date desc" in normalized
            assert parameters == ["2026-04-30"]
            selected_columns = {
                column.strip()
                for column in normalized.partition("from")[0].removeprefix("select").split(",")
            }
            assert selected_columns == expected_columns
            return FakeResult()

        def close(self) -> None:
            pass

    monkeypatch.setattr(
        macro_toolkit_service.duckdb,
        "connect",
        lambda *_args, **_kwargs: FakeConnection(),
    )
    monkeypatch.setattr(
        macro_toolkit_service,
        "_duckdb_date_column_is_canonical_iso",
        lambda *_args, **_kwargs: True,
        raising=False,
    )
    monkeypatch.setattr(
        macro_toolkit_service,
        "_duckdb_table_exists",
        lambda *_args, **_kwargs: True,
    )

    row = macro_toolkit_service.load_latest_risk_tensor_row(
        duckdb_path,
        date(2026, 4, 30),
    )

    assert row is not None
    assert set(row) == expected_columns


def test_a_share_stampede_risk_context_delegates_to_service(tmp_path, monkeypatch) -> None:
    expected_context = {
        "observations": pd.DataFrame({"stock_code": ["000001.SZ"]}),
        "theme_frame": pd.DataFrame({"stock_code": ["000001.SZ"], "industry": ["Bank"]}),
        "tables_used": ["choice_stock_daily_observation"],
        "warnings": [],
    }
    calls: list[object] = []

    def fake_load_a_share_stampede_risk_context(duckdb_path: object) -> dict[str, object]:
        calls.append(duckdb_path)
        return expected_context

    monkeypatch.setattr(
        macro_toolkit_service,
        "load_a_share_stampede_risk_context",
        fake_load_a_share_stampede_risk_context,
        raising=False,
    )

    duckdb_path = tmp_path / "moss.duckdb"

    assert macro_toolkit_route._load_a_share_stampede_risk_context(duckdb_path) is expected_context
    assert calls == [duckdb_path]
    assert "duckdb.connect" not in inspect.getsource(macro_toolkit_route._load_a_share_stampede_risk_context)


def test_macro_curve_rows_delegate_to_service(tmp_path, monkeypatch) -> None:
    report_date = date(2026, 4, 30)
    expected_rows = [
        {
            "biz_date": "2026-04-30",
            "curve_id": "CN_GOVT",
            "tenor": "10Y",
            "rate_value": 2.35,
        }
    ]
    calls: list[tuple[object, date]] = []

    def fake_load_macro_curve_rows(duckdb_path: object, report_date_arg: date) -> list[dict[str, object]]:
        calls.append((duckdb_path, report_date_arg))
        return expected_rows

    monkeypatch.setattr(
        macro_toolkit_service,
        "load_macro_curve_rows",
        fake_load_macro_curve_rows,
        raising=False,
    )

    duckdb_path = tmp_path / "moss.duckdb"

    assert macro_toolkit_route._load_macro_curve_rows(duckdb_path, report_date) is expected_rows
    assert calls == [(duckdb_path, report_date)]
    assert "duckdb.connect" not in inspect.getsource(macro_toolkit_route._load_macro_curve_rows)


def test_macro_curve_rows_include_reverse_repo_legacy_alias(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_choice_tushare_macro_db(duckdb_path)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()

    try:
        rows = macro_toolkit_service.load_macro_curve_rows(duckdb_path, date(2026, 4, 10))
    finally:
        get_settings.cache_clear()

    reverse_repo = [
        row
        for row in rows
        if row["curve_id"] == "CN_RRP" and row["tenor"] == "7D"
    ]

    assert reverse_repo == [
        {
            "biz_date": "2026-04-10",
            "curve_id": "CN_RRP",
            "tenor": "7D",
            "rate_value": 1.75,
        }
    ]


def test_crisis_score_capability_batches_formula_and_commodity_aliases(tmp_path, monkeypatch) -> None:
    calls: list[dict[str, object]] = []
    empty_frame = pd.DataFrame(columns=["date", "value", "series_id", "vendor_name"])

    def fake_load_series_by_aliases(
        aliases: tuple[str, ...],
        *,
        start: str | None = None,
        end: str | None = None,
        duckdb_path: object | None = None,
    ) -> dict[str, pd.DataFrame]:
        requested_aliases = tuple(dict.fromkeys(str(alias) for alias in aliases))
        calls.append(
            {
                "aliases": requested_aliases,
                "start": start,
                "end": end,
                "duckdb_path": duckdb_path,
            }
        )
        return {alias: empty_frame.copy() for alias in requested_aliases}

    monkeypatch.setattr(macro_toolkit_route, "load_series_by_aliases", fake_load_series_by_aliases)
    monkeypatch.setattr(
        macro_toolkit_route,
        "compute_crisis_score_payload",
        lambda _series_data, *, report_date: {
            "data_status": "unavailable",
            "warnings": [],
            "crisis_score": None,
        },
    )
    monkeypatch.setattr(
        macro_toolkit_route,
        "_crisis_score_history",
        lambda _series_data, _report_date: pd.DataFrame(columns=["crisis_score"]),
    )

    report_date = date(2026, 4, 10)
    payload = macro_toolkit_route._compute_crisis_score_capability(
        tmp_path / "moss.duckdb",
        report_date,
        history_limit=5,
    )

    assert len(calls) == 1
    batched_aliases = set(calls[0]["aliases"])
    assert {str(config["alias"]) for config in macro_toolkit_route._CRISIS_SCORE_INPUTS}.issubset(batched_aliases)
    assert {
        str(alias)
        for config in macro_toolkit_route._CRISIS_COMMODITY_COVERAGE_INPUTS
        for alias in config["aliases"]
    }.issubset(batched_aliases)
    assert calls[0]["end"] == report_date.isoformat()
    assert payload["commodity_coverage"]["tracked_count"] == len(macro_toolkit_route._CRISIS_COMMODITY_COVERAGE_INPUTS)


def test_source_checks_for_aliases_reuses_supplied_frames(tmp_path, monkeypatch) -> None:
    def fail_load_series_by_aliases(*_args: object, **_kwargs: object) -> dict[str, pd.DataFrame]:
        raise AssertionError("source checks should reuse supplied alias frames")

    monkeypatch.setattr(macro_toolkit_route, "load_series_by_aliases", fail_load_series_by_aliases)
    frame = pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2026-04-10"),
                "value": 2.5,
                "series_id": "M001",
                "vendor_name": "choice",
            }
        ]
    )

    checks = macro_toolkit_route._source_checks_for_aliases(
        ("M001",),
        tmp_path / "moss.duckdb",
        end="2026-04-10",
        frames_by_alias={"M001": frame},
    )

    assert checks == [
        {
            "alias": "M001",
            "row_count": 1,
            "latest": {
                "date": "2026-04-10",
                "series_id": "M001",
                "vendor_name": "choice",
                "value": 2.5,
            },
        }
    ]


def test_latest_risk_tensor_row_delegates_to_service(tmp_path, monkeypatch) -> None:
    report_date = date(2026, 4, 30)
    expected_row = {"report_date": "2026-04-30", "total_market_value": 100.0}
    calls: list[tuple[object, date]] = []

    def fake_load_latest_risk_tensor_row(duckdb_path: object, report_date_arg: date) -> dict[str, object]:
        calls.append((duckdb_path, report_date_arg))
        return expected_row

    monkeypatch.setattr(
        macro_toolkit_service,
        "load_latest_risk_tensor_row",
        fake_load_latest_risk_tensor_row,
        raising=False,
    )

    duckdb_path = tmp_path / "moss.duckdb"

    assert macro_toolkit_route._load_latest_risk_tensor_row(duckdb_path, report_date) is expected_row
    assert calls == [(duckdb_path, report_date)]
    assert "duckdb.connect" not in inspect.getsource(macro_toolkit_route._load_latest_risk_tensor_row)


def test_latest_bond_positions_delegate_to_service(tmp_path, monkeypatch) -> None:
    report_date = date(2026, 4, 30)
    expected_positions = [{"market_value": 100.0, "maturity_date": "2027-04-30", "coupon_rate": 2.4}]
    calls: list[tuple[object, date]] = []

    def fake_load_latest_bond_positions(duckdb_path: object, report_date_arg: date) -> list[dict[str, object]]:
        calls.append((duckdb_path, report_date_arg))
        return expected_positions

    monkeypatch.setattr(
        macro_toolkit_service,
        "load_latest_bond_positions",
        fake_load_latest_bond_positions,
        raising=False,
    )

    duckdb_path = tmp_path / "moss.duckdb"

    assert macro_toolkit_route._load_latest_bond_positions(duckdb_path, report_date) is expected_positions
    assert calls == [(duckdb_path, report_date)]
    assert "duckdb.connect" not in inspect.getsource(macro_toolkit_route._load_latest_bond_positions)


def test_macro_capability_context_reuses_one_connection_for_curve_risk_and_bonds(
    tmp_path,
    monkeypatch,
) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    duckdb_path.write_bytes(b"placeholder")
    connection_ids: dict[str, int] = {}

    class FakeConnection:
        def __init__(self) -> None:
            self.close_count = 0

        def close(self) -> None:
            self.close_count += 1

    connections: list[FakeConnection] = []

    def fake_connect(*_args, **_kwargs) -> FakeConnection:
        connection = FakeConnection()
        connections.append(connection)
        return connection

    def fake_curve(conn: object, path: object, report_date: date) -> list[dict[str, object]]:
        connection_ids["curve"] = id(conn)
        assert path == duckdb_path
        return [{"biz_date": report_date.isoformat(), "curve_id": "CN_GOVT", "tenor": "10Y", "rate_value": 2.2}]

    def fake_risk(
        conn: object,
        report_date: date,
        duckdb_path_arg: object,
    ) -> dict[str, object]:
        connection_ids["risk"] = id(conn)
        assert duckdb_path_arg == duckdb_path
        return {"report_date": report_date.isoformat(), "total_market_value": 100.0}

    def fake_bonds(conn: object, report_date: date) -> list[dict[str, object]]:
        connection_ids["bond"] = id(conn)
        return [{"market_value": 50.0, "maturity_date": report_date, "coupon_rate": 2.4}]

    monkeypatch.setattr(macro_toolkit_service.duckdb, "connect", fake_connect)
    monkeypatch.setattr(macro_toolkit_service, "_load_macro_curve_rows_from_conn", fake_curve, raising=False)
    monkeypatch.setattr(macro_toolkit_service, "_load_latest_risk_tensor_row_from_conn", fake_risk, raising=False)
    monkeypatch.setattr(macro_toolkit_service, "_load_latest_bond_positions_from_conn", fake_bonds, raising=False)

    curve_rows, risk_tensor, positions = macro_toolkit_service.load_macro_capability_context(
        duckdb_path,
        date(2026, 4, 30),
    )

    assert curve_rows[0]["curve_id"] == "CN_GOVT"
    assert risk_tensor is not None and risk_tensor["total_market_value"] == 100.0
    assert positions[0]["market_value"] == 50.0
    assert len(connections) == 1
    assert connections[0].close_count == 1
    assert set(connection_ids.values()) == {id(connections[0])}


def test_macro_capability_results_uses_page_local_aggregate_loader() -> None:
    source = inspect.getsource(macro_toolkit_route._macro_capability_results)

    assert "_load_macro_capability_context(" in source
    assert "_load_macro_curve_rows(" not in source
    assert "_load_latest_risk_tensor_row(" not in source
    assert "_load_latest_bond_positions(" not in source


def test_macro_toolkit_analysis_surfaces_m2_and_ppi_missing_inputs(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_choice_tushare_macro_db(duckdb_path)
    _delete_external_macro_series(duckdb_path, "tushare.macro.cn_ppi.monthly")
    _delete_external_macro_series(duckdb_path, "tushare.macro.cn_money.monthly")
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()
    app = FastAPI()
    app.include_router(macro_toolkit_router)
    client = TestClient(app)

    try:
        response = client.get("/ui/macro/toolkit/analysis")
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    cards = {item["key"]: item for item in response.json()["result"]["capability_results"]}
    leading = cards["leading_indicator"]
    cycle = cards["economic_cycle"]

    leading_missing = set(leading["input_evidence"]["missing_inputs"])
    cycle_missing = set(cycle["input_evidence"]["missing_inputs"])
    assert leading["status"] == "degraded"
    assert cycle["status"] == "degraded"
    assert "M2_YOY_MISSING" in leading_missing
    assert "M2_YOY_MISSING" in cycle_missing
    assert "PPI_YOY_MISSING" in cycle_missing


def test_macro_toolkit_analysis_uses_landed_choice_stock_for_strategy_summaries(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_choice_tushare_macro_db(duckdb_path)
    _seed_choice_stock_strategy_db(duckdb_path)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()
    app = FastAPI()
    app.include_router(macro_toolkit_router)
    client = TestClient(app)

    try:
        response = client.get("/ui/macro/toolkit/analysis")
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    payload = response.json()
    strategies = {item["key"]: item for item in payload["result"]["strategy_summaries"]}
    assert strategies["moving_average"]["status"] == "complete"
    assert strategies["moving_average"]["warnings"] == []
    assert strategies["moving_average"]["primary_metric"]["label"] == "真实累计净值"
    assert strategies["moving_average"]["result"]["data_status"] == "complete"
    assert strategies["moving_average"]["result"]["price_source"] == "choice_stock_daily_observation"
    assert strategies["moving_average"]["result"]["as_of_date"] == "2026-04-30"
    assert strategies["moving_average"]["result"]["stock_count"] == 3
    assert strategies["mean_reversion_momentum"]["status"] == "complete"
    assert strategies["multi_factor_selection"]["status"] == "degraded"
    assert "FUNDAMENTAL_FACTORS_NOT_MATERIALIZED" in strategies["multi_factor_selection"]["warnings"]
    assert strategies["multi_factor_selection"]["result"]["price_source"] == "choice_stock_daily_observation"
    assert strategies["multi_factor_selection"]["result"]["source_versions"] == ["sv_stock"]
    assert strategies["multi_factor_selection"]["result"]["vendor_versions"] == ["vv_stock"]
    low_crowding = strategies["low_crowding_regime_multifactor"]
    assert low_crowding["status"] == "degraded"
    assert low_crowding["result"]["price_source"] == "choice_stock_daily_observation"
    assert low_crowding["result"]["regime"] in {
        "liquidity_shock",
        "crowded_quant",
        "fast_down",
        "range",
        "weak_up",
        "strong_up",
    }
    assert "FACTOR_SNAPSHOT_REQUIRED_FOR_LOW_CROWDING_MULTIFACTOR" in low_crowding["warnings"]
    a_share_risk = payload["result"]["a_share_risk"]
    assert a_share_risk["trade_date"] == "2026-04-30"
    assert a_share_risk["status"] in {"complete", "degraded"}
    assert a_share_risk["risk_level"] in {"green", "yellow", "orange", "red"}
    assert isinstance(a_share_risk["metrics"]["up_count"], (int, float))
    assert "choice_stock_daily_observation" in a_share_risk["tables_used"]
    assert "choice_stock_limit_quality" in a_share_risk["tables_used"]
    signal_cards = {item["key"]: item for item in payload["result"]["signal_cards"]}
    assert signal_cards["a_share_stampede_risk"]["title"] == "市场踩踏风险"
    assert "choice_stock_daily_observation" in payload["result_meta"]["tables_used"]
    assert "choice_stock_limit_quality" in payload["result_meta"]["tables_used"]


def test_macro_toolkit_full_analysis_blocks_run_heavy_sections_concurrently(monkeypatch) -> None:
    duckdb_path = Path("macro-analysis.duckdb")
    report_date = date(2026, 7, 7)
    started: list[str] = []
    started_lock = Lock()
    all_started = Event()

    def wait_for_peer_blocks(name: str, value: object) -> object:
        with started_lock:
            started.append(name)
            if len(started) == 3:
                all_started.set()
        assert all_started.wait(1.0), f"{name} ran before the other heavy analysis blocks started"
        return value

    def fake_a_share_risk(path: object) -> dict[str, object]:
        assert path == duckdb_path
        return wait_for_peer_blocks("a_share_risk", {"status": "complete"})  # type: ignore[return-value]

    def fake_capability_results(
        path: object,
        *,
        report_date: date,
        history_limit: int,
    ) -> list[dict[str, object]]:
        assert path == duckdb_path
        assert report_date == date(2026, 7, 7)
        assert history_limit == 19
        return wait_for_peer_blocks("capability_results", [{"key": "capability"}])  # type: ignore[return-value]

    def fake_strategy_summaries(path: object) -> list[dict[str, object]]:
        assert path == duckdb_path
        return wait_for_peer_blocks("strategy_summaries", [{"key": "strategy"}])  # type: ignore[return-value]

    monkeypatch.setattr(macro_toolkit_route, "_a_share_stampede_risk", fake_a_share_risk)
    monkeypatch.setattr(macro_toolkit_route, "_macro_capability_results", fake_capability_results)
    monkeypatch.setattr(macro_toolkit_route, "_equity_strategy_summaries", fake_strategy_summaries)

    a_share_risk, capability_results, strategy_summaries = (
        macro_toolkit_route._build_macro_toolkit_full_analysis_blocks(
            duckdb_path,
            report_date,
            history_limit=19,
        )
    )

    assert set(started) == {"a_share_risk", "capability_results", "strategy_summaries"}
    assert a_share_risk == {"status": "complete"}
    assert capability_results == [{"key": "capability"}]
    assert strategy_summaries == [{"key": "strategy"}]


def test_macro_toolkit_full_analysis_uses_three_worker_local_connections(
    tmp_path,
    monkeypatch,
) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    duckdb.connect(str(duckdb_path), read_only=False).close()
    connections = _track_macro_toolkit_connections(monkeypatch)
    started: list[str] = []
    started_lock = Lock()
    all_started = Event()
    empty_frame = pd.DataFrame(columns=["date", "value", "series_id", "vendor_name"])

    def synchronize(name: str) -> None:
        with started_lock:
            started.append(name)
            if len(started) == 3:
                all_started.set()
        assert all_started.wait(1.0), f"{name} did not overlap the other full-analysis workers"

    def load_a_share(path: object) -> dict[str, object]:
        synchronize("a_share")
        return macro_toolkit_service.load_a_share_stampede_risk_context(path) or {}

    def load_capabilities(
        path: object,
        *,
        report_date: date,
        history_limit: int,
    ) -> list[dict[str, object]]:
        assert history_limit == 19
        synchronize("capabilities")
        macro_toolkit_service.load_macro_capability_context(path, report_date)
        return []

    def load_strategies(path: object) -> list[dict[str, object]]:
        synchronize("strategies")
        macro_toolkit_service.load_equity_strategy_price_context(path)
        return []

    monkeypatch.setattr(
        macro_toolkit_service,
        "load_series_by_aliases",
        lambda aliases, **_kwargs: {alias: empty_frame.copy() for alias in aliases},
    )
    monkeypatch.setattr(macro_toolkit_route, "_a_share_stampede_risk", load_a_share)
    monkeypatch.setattr(macro_toolkit_route, "_macro_capability_results", load_capabilities)
    monkeypatch.setattr(macro_toolkit_route, "_equity_strategy_summaries", load_strategies)

    result = macro_toolkit_route._build_macro_toolkit_full_analysis_blocks(
        duckdb_path,
        date(2026, 4, 30),
        history_limit=19,
    )

    assert result == ({}, [], [])
    assert set(started) == {"a_share", "capabilities", "strategies"}
    assert len(connections) == 3
    assert len({connection.thread_id for connection in connections}) == 3
    assert all(connection.close_count == 1 for connection in connections)
    assert all(connection.use_thread_ids == {connection.thread_id} for connection in connections)


def test_macro_toolkit_analysis_surfaces_crisis_score_from_system_sources(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_choice_tushare_macro_db(duckdb_path)
    _seed_crisis_score_history(duckdb_path)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()
    app = FastAPI()
    app.include_router(macro_toolkit_router)
    client = TestClient(app)

    try:
        response = client.get("/ui/macro/toolkit/analysis")
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    payload = response.json()["result"]
    crisis = next(item for item in payload["capability_results"] if item["key"] == "crisis_score_cn")
    assert crisis["status"] == "complete"
    assert crisis["primary_metric"]["label"] == "Crisis Score"
    assert crisis["result"]["available_component_count"] == 5
    assert crisis["result"]["crisis_score"] >= 1
    assert crisis["input_evidence"] == crisis["result"]["input_evidence"]
    crisis_inputs = {item["field"]: item for item in crisis["input_evidence"]["inputs"]}
    nanhua_input = crisis_inputs["nanhua"]
    assert nanhua_input["label"] == "Nanhua commodity index"
    assert nanhua_input["aliases"] == ["NH0100.NHF"]
    assert nanhua_input["available"] is True
    assert nanhua_input["row_count"] >= 120
    assert nanhua_input["latest_date"] == "2026-04-10"
    assert nanhua_input["series_id"] == "NH0100.NHF"
    assert nanhua_input["source"] == "choice"
    assert nanhua_input["value"] is not None
    assert "fact_choice_macro_daily" in response.json()["result_meta"]["tables_used"]
    assert "fact_commodity_futures_daily" in response.json()["result_meta"]["tables_used"]

    signal = next(item for item in payload["signal_cards"] if item["key"] == "crisis_score_cn")
    assert signal["tone"] == "negative"


def test_macro_toolkit_analysis_surfaces_crisis_score_nanhua_from_commodity_table(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_choice_tushare_macro_db(duckdb_path)
    _seed_crisis_score_history(duckdb_path)
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_commodity_futures_daily (
              trade_date varchar not null,
              product_code varchar not null,
              contract_code varchar,
              exchange varchar,
              open_value double,
              high_value double,
              low_value double,
              close_value double,
              settle_value double,
              volume double,
              open_interest double,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar default 'rv_commodity_daily_v1',
              created_at timestamp default current_timestamp,
              primary key (trade_date, product_code)
            )
            """
        )
        conn.execute("delete from fact_choice_macro_daily where series_id = 'NH0100.NHF'")
        conn.execute(
            """
            insert into fact_commodity_futures_daily (
              trade_date, product_code, contract_code, exchange,
              open_value, high_value, low_value, close_value, settle_value,
              volume, open_interest, source_version, vendor_version, rule_version
            )
            select
              trade_date, 'NHCI', 'NHCI.NH', 'NH',
              null, null, null, max(value_numeric), null,
              null, null, 'sv_tushare_index_daily_nhci',
              'vv_tushare_index_daily_NHCI_20260410', 'rv_commodity_daily_v1'
            from fact_choice_macro_daily
            where series_id = 'CA.CSI300'
            group by trade_date
            """
        )
    finally:
        conn.close()
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()
    app = FastAPI()
    app.include_router(macro_toolkit_router)
    client = TestClient(app)

    try:
        response = client.get("/ui/macro/toolkit/analysis")
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    payload = response.json()["result"]
    crisis = next(item for item in payload["capability_results"] if item["key"] == "crisis_score_cn")
    crisis_inputs = {item["field"]: item for item in crisis["input_evidence"]["inputs"]}
    nanhua_input = crisis_inputs["nanhua"]
    assert nanhua_input["available"] is True
    assert nanhua_input["latest_date"] == "2026-04-10"
    assert nanhua_input["series_id"] == "NHCI.NH"
    assert nanhua_input["source"] == "tushare"
    assert nanhua_input["value"] is not None


def test_macro_toolkit_analysis_surfaces_multi_commodity_coverage_without_changing_crisis_formula(
    tmp_path,
    monkeypatch,
) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_choice_tushare_macro_db(duckdb_path)
    _seed_crisis_score_history(duckdb_path)
    baseline_crisis = macro_toolkit_route._compute_crisis_score_capability(duckdb_path, date(2026, 4, 10))
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_commodity_futures_daily (
              trade_date varchar not null,
              product_code varchar not null,
              contract_code varchar,
              exchange varchar,
              open_value double,
              high_value double,
              low_value double,
              close_value double,
              settle_value double,
              volume double,
              open_interest double,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar default 'rv_commodity_daily_v1',
              created_at timestamp default current_timestamp,
              primary key (trade_date, product_code)
            )
            """
        )
        commodity_rows: list[tuple[object, ...]] = []
        start_date = date(2025, 12, 12)
        product_specs = {
            "RB": ("RB2605.SHF", "SHF", 3200.0, 3.2),
            "I": ("I2605.DCE", "DCE", 700.0, 0.9),
            "CU": ("CU2605.SHF", "SHF", 78000.0, 27.18),
            "AL": ("AL2605.SHF", "SHF", 18800.0, 9.046),
            "SC": ("SC2605.INE", "INE", 560.0, 0.44),
            "AU": ("AU2605.SHF", "SHF", 510.0, 0.318),
        }
        for offset in range(120):
            trade_date = (start_date + pd.Timedelta(days=offset)).strftime("%Y-%m-%d")
            stress = max(0.0, (offset - 89) / 30)
            alternating = -1 if offset % 2 else 1
            for product_code, (contract_code, exchange, base_value, daily_step) in product_specs.items():
                price = base_value + offset * daily_step + alternating * stress * daily_step * 18
                commodity_rows.append(
                    (
                        trade_date,
                        product_code,
                        contract_code,
                        exchange,
                        None,
                        None,
                        None,
                        price,
                        None,
                        1000,
                        2000,
                        f"sv_tushare_fut_daily_{product_code.lower()}",
                        f"vv_tushare_fut_daily_{product_code}_{exchange}_20260410",
                        "rv_commodity_daily_v1",
                    )
                )
        conn.executemany(
            """
            insert into fact_commodity_futures_daily (
              trade_date, product_code, contract_code, exchange,
              open_value, high_value, low_value, close_value, settle_value,
              volume, open_interest, source_version, vendor_version, rule_version
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            commodity_rows,
        )
    finally:
        conn.close()
    enriched_crisis = macro_toolkit_route._compute_crisis_score_capability(duckdb_path, date(2026, 4, 10))
    assert baseline_crisis["crisis_score"] == enriched_crisis["crisis_score"]
    assert baseline_crisis["commodity_coverage"]["available_count"] < enriched_crisis["commodity_coverage"]["available_count"]
    assert enriched_crisis["commodity_coverage"]["available_count"] == 6
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()
    app = FastAPI()
    app.include_router(macro_toolkit_router)
    client = TestClient(app)

    try:
        response = client.get("/ui/macro/toolkit/analysis")
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    payload = response.json()["result"]
    crisis = next(item for item in payload["capability_results"] if item["key"] == "crisis_score_cn")
    coverage = crisis["result"]["commodity_coverage"]
    assert coverage["role"] == "supplemental_observation"
    assert coverage["available_count"] == 6
    assert coverage["tracked_count"] == 6
    assert coverage["used_in_crisis_score"] == ["nanhua"]
    items = {item["field"]: item for item in coverage["items"]}
    assert set(items) == {"rebar", "iron_ore", "copper", "aluminum", "crude_oil", "gold"}
    crude_series = load_series_by_alias("SC0.INE", duckdb_path=duckdb_path)
    assert crude_series["series_id"].drop_duplicates().tolist() == ["COMMODITY.SC"]
    assert len(crude_series) == 120
    assert items["copper"]["available"] is True
    assert items["copper"]["aliases"] == ["CU0", "CU0.SHF"]
    assert items["copper"]["matched_alias"] == "CU0"
    assert items["copper"]["role"] == "supplemental_observation"
    assert items["copper"]["used_in_formula"] is False
    assert items["copper"]["candidate_decision"] == {
        "status": "shadow_review_ready",
        "label": "影子评估就绪",
        "reason": "数据已命中且与分析日同日；当前仍作为 supplemental_observation，不改变 Crisis Score 公式。",
        "next_step": "完成历史回测、相关性检验、权重审批后，才能作为公式候选提交。",
    }
    assert items["copper"]["report_date"] == "2026-04-10"
    assert items["copper"]["date_alignment_status"] == "aligned"
    assert items["copper"]["series_id"] == "CA.COPPER"
    assert items["copper"]["source"] == "tushare"
    assert items["copper"]["latest_date"] == "2026-04-10"
    assert items["copper"]["row_count"] == 120
    assert items["copper"]["value"] == pytest.approx(81234.5)
    copper_shadow = items["copper"]["shadow_evaluation"]
    assert copper_shadow["status"] == "review_ready"
    assert copper_shadow["label"] == "影子评估可读"
    assert copper_shadow["sample_count"] == 41
    assert copper_shadow["window_start"] == "2026-03-01"
    assert copper_shadow["window_end"] == "2026-04-10"
    assert copper_shadow["target"] == "crisis_score"
    assert copper_shadow["candidate_metric"] == "daily_return"
    assert copper_shadow["same_day_correlation"] == pytest.approx(0.0)
    assert copper_shadow["lead_1d_correlation"] == pytest.approx(0.0)
    assert copper_shadow["lag_1d_correlation"] == pytest.approx(0.0)
    assert copper_shadow["crisis_hit_rate"] == pytest.approx(0.55)
    assert copper_shadow["crisis_sample_count"] == 11
    assert "样本 41" in copper_shadow["summary"]
    assert copper_shadow["next_step"] == "进入公式前仍需历史回测、相关性检验、权重审批和版本记录。"
    assert items["crude_oil"]["series_id"] == "COMMODITY.SC"
    assert items["gold"]["series_id"] == "COMMODITY.AU"
    assert coverage["candidate_summary"] == {
        "shadow_review_ready_count": 6,
        "needs_current_data_count": 0,
        "missing_data_count": 0,
        "shadow_evaluation_ready_count": 6,
        "shadow_evaluation_short_count": 0,
        "shadow_evaluation_status_counts": {"review_ready": 6},
        "shadow_evaluation_short_items": [],
        "suggested_refresh_products": [],
        "shadow_evaluation_next_step": "6 个商品候选可进入人工复核；进入公式前仍需历史回测、相关性检验、权重审批和版本记录。",
        "formula_change_required": True,
        "approval_required": True,
        "next_step": "商品旁证进入 Crisis Score 公式前，需要先完成历史回测、相关性检验、权重审批和版本记录。",
    }
    shadow_impact = crisis["result"]["shadow_impact"]
    assert shadow_impact["formula_version"] == "rv_macro_crisis_score_shadow_commodity_v1"
    assert shadow_impact["scope"] == "commodity_shadow_v2_read_only"
    assert shadow_impact["current_score"] == crisis["result"]["crisis_score"]
    assert shadow_impact["shadow_score"] == pytest.approx(
        shadow_impact["current_score"] + shadow_impact["delta"],
    )
    assert shadow_impact["included_candidates"] == [
        "rebar",
        "iron_ore",
        "copper",
        "aluminum",
        "crude_oil",
        "gold",
    ]
    assert shadow_impact["candidate_count"] == 6
    assert shadow_impact["approval_required"] is True
    assert shadow_impact["official_score_unchanged"] is True
    assert shadow_impact["weights"]["commodity_shadow"] == pytest.approx(0.05)
    assert shadow_impact["weights"]["official_crisis_score"] == pytest.approx(1.0)
    assert shadow_impact["warnings"] == ["SHADOW_SCORE_READ_ONLY", "APPROVAL_REQUIRED_BEFORE_FORMULA_USE"]
    assert shadow_impact["direction"] in {"higher_stress", "lower_stress", "unchanged"}
    assert shadow_impact["candidate_contributions"]
    copper_contribution = next(item for item in shadow_impact["candidate_contributions"] if item["field"] == "copper")
    assert copper_contribution["label"] == "Copper futures"
    assert copper_contribution["series_id"] == "CA.COPPER"
    assert copper_contribution["source"] == "tushare"
    assert copper_contribution["sample_count"] == 41
    assert copper_contribution["weight"] == pytest.approx(0.05)
    assert copper_contribution["candidate_metric"] == "daily_return_z"
    assert copper_contribution["used_in_official_score"] is False
    assert copper_contribution["status"] == "shadow_only"
    admission = crisis["result"]["commodity_candidate_admission"]
    assert admission["rule_version"] == "rv_macro_crisis_commodity_admission_v1"
    assert admission["scope"] == "commodity_candidate_admission_read_only"
    assert admission["official_score_unchanged"] is True
    assert admission["approval_required"] is True
    assert admission["decision_counts"] == {
        "recommend_include": 0,
        "watch": 6,
        "do_not_include": 0,
    }
    assert admission["warnings"] == ["CANDIDATE_ADMISSION_READ_ONLY", "APPROVAL_REQUIRED_BEFORE_FORMULA_USE"]
    assert admission["next_step"] == "6 个商品候选继续观察；先复核相关性、危机期命中率和异常点，再提交 v2 权重审批。"
    admission_items = {item["field"]: item for item in admission["items"]}
    assert set(admission_items) == {"rebar", "iron_ore", "copper", "aluminum", "crude_oil", "gold"}
    assert admission_items["copper"]["decision"] == "watch"
    assert admission_items["copper"]["decision_label"] == "继续观察"
    assert admission_items["copper"]["reason"] == "相关性偏弱，需人工复核。"
    assert admission_items["copper"]["sample_count"] == 41
    assert admission_items["copper"]["minimum_sample_count"] == 20
    assert admission_items["copper"]["crisis_sample_count"] == 11
    assert admission_items["copper"]["crisis_hit_rate"] == pytest.approx(0.55)
    assert admission_items["copper"]["max_abs_correlation"] == pytest.approx(0.0)
    assert admission_items["copper"]["source"] == "tushare"
    assert admission_items["copper"]["series_id"] == "CA.COPPER"
    assert admission_items["copper"]["used_in_official_score"] is False
    approval_pack = crisis["result"]["commodity_candidate_approval_pack"]
    assert approval_pack["pack_version"] == "rv_macro_crisis_commodity_approval_pack_v1"
    assert approval_pack["scope"] == "commodity_candidate_approval_read_only"
    assert approval_pack["source_rule_version"] == "rv_macro_crisis_commodity_admission_v1"
    assert approval_pack["shadow_formula_version"] == "rv_macro_crisis_score_shadow_commodity_v1"
    assert approval_pack["official_score_unchanged"] is True
    assert approval_pack["approval_required"] is True
    assert approval_pack["decision_counts"] == admission["decision_counts"]
    assert approval_pack["recommended_fields"] == []
    assert approval_pack["watch_fields"] == ["rebar", "iron_ore", "copper", "aluminum", "crude_oil", "gold"]
    assert approval_pack["summary"] == "审批材料：建议纳入 0，继续观察 6，暂不纳入 0；审批前不改变正式 Crisis Score。"
    assert approval_pack["copy_text"].startswith("Crisis Score 商品候选审批材料")
    assert "规则版本 rv_macro_crisis_commodity_admission_v1" in approval_pack["copy_text"]
    assert "影子公式 rv_macro_crisis_score_shadow_commodity_v1" in approval_pack["copy_text"]
    assert "正式 Crisis Score" in approval_pack["copy_text"]
    assert "shadow delta" in approval_pack["copy_text"]
    assert "Copper futures · 继续观察 · 相关性偏弱，需人工复核。" in approval_pack["copy_text"]
    assert "样本 41/20" in approval_pack["copy_text"]
    assert "危机样本 11/5" in approval_pack["copy_text"]
    assert "命中率 55.0%" in approval_pack["copy_text"]
    assert "最大相关 0.00/0.20" in approval_pack["copy_text"]
    assert "审批前不改变正式 Crisis Score" in approval_pack["copy_text"]
    assert crisis["result"]["available_component_count"] == 5
    assert crisis["result"]["component_count"] == 5


def test_macro_toolkit_analysis_surfaces_actionable_commodity_shadow_shortfalls(tmp_path) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_choice_tushare_macro_db(duckdb_path)
    _seed_crisis_score_history(duckdb_path)
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_commodity_futures_daily (
              trade_date varchar not null,
              product_code varchar not null,
              contract_code varchar,
              exchange varchar,
              open_value double,
              high_value double,
              low_value double,
              close_value double,
              settle_value double,
              volume double,
              open_interest double,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar default 'rv_commodity_daily_v1',
              created_at timestamp default current_timestamp,
              primary key (trade_date, product_code)
            )
            """
        )
        commodity_rows: list[tuple[object, ...]] = []
        short_start = date(2026, 3, 24)
        for offset in range(18):
            trade_date = (short_start + pd.Timedelta(days=offset)).strftime("%Y-%m-%d")
            commodity_rows.extend(
                [
                    (
                        trade_date,
                        "RB",
                        "RB2605.SHF",
                        "SHF",
                        None,
                        None,
                        None,
                        3500 + offset * 2.5,
                        None,
                        1000,
                        2000,
                        "sv_tushare_fut_daily_rb",
                        "vv_tushare_fut_daily_RB_SHF_20260410",
                        "rv_commodity_daily_v1",
                    ),
                    (
                        trade_date,
                        "I",
                        "I2605.DCE",
                        "DCE",
                        None,
                        None,
                        None,
                        760 + offset * 0.8,
                        None,
                        1000,
                        2000,
                        "sv_tushare_fut_daily_i",
                        "vv_tushare_fut_daily_I_DCE_20260410",
                        "rv_commodity_daily_v1",
                    ),
                ]
            )
        ready_specs = {
            "CU": ("CU2605.SHF", "SHF", 78000.0, 25.0),
            "AL": ("AL2605.SHF", "SHF", 18800.0, 8.0),
            "SC": ("SC2605.INE", "INE", 560.0, 0.5),
            "AU": ("AU2605.SHF", "SHF", 510.0, 0.3),
        }
        ready_start = date(2026, 2, 1)
        for offset in range(70):
            trade_date = (ready_start + pd.Timedelta(days=offset)).strftime("%Y-%m-%d")
            for product_code, (contract_code, exchange, base_value, daily_step) in ready_specs.items():
                commodity_rows.append(
                    (
                        trade_date,
                        product_code,
                        contract_code,
                        exchange,
                        None,
                        None,
                        None,
                        base_value + offset * daily_step,
                        None,
                        1000,
                        2000,
                        f"sv_tushare_fut_daily_{product_code.lower()}",
                        f"vv_tushare_fut_daily_{product_code}_{exchange}_20260410",
                        "rv_commodity_daily_v1",
                    )
                )
        conn.executemany(
            """
            insert into fact_commodity_futures_daily (
              trade_date, product_code, contract_code, exchange,
              open_value, high_value, low_value, close_value, settle_value,
              volume, open_interest, source_version, vendor_version, rule_version
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            commodity_rows,
        )
    finally:
        conn.close()

    crisis = macro_toolkit_route._compute_crisis_score_capability(duckdb_path, date(2026, 4, 10))

    coverage = crisis["commodity_coverage"]
    items = {item["field"]: item for item in coverage["items"]}
    rebar_shadow = items["rebar"]["shadow_evaluation"]
    assert rebar_shadow["status"] == "history_short"
    assert rebar_shadow["sample_count"] == 17
    assert rebar_shadow["minimum_sample_count"] == 20
    assert rebar_shadow["sample_gap"] == 3
    assert items["copper"]["shadow_evaluation"]["status"] == "review_ready"
    assert coverage["candidate_summary"]["shadow_evaluation_ready_count"] == 4
    assert coverage["candidate_summary"]["shadow_evaluation_short_count"] == 2
    assert coverage["candidate_summary"]["shadow_evaluation_status_counts"] == {
        "history_short": 2,
        "review_ready": 4,
    }
    assert coverage["candidate_summary"]["suggested_refresh_products"] == ["RB", "I"]
    assert coverage["candidate_summary"]["shadow_evaluation_short_items"] == [
        {
            "field": "rebar",
            "label": "Rebar futures",
            "sample_count": 17,
            "minimum_sample_count": 20,
            "sample_gap": 3,
            "latest_date": "2026-04-10",
        },
        {
            "field": "iron_ore",
            "label": "Iron ore futures",
            "sample_count": 17,
            "minimum_sample_count": 20,
            "sample_gap": 3,
            "latest_date": "2026-04-10",
        },
    ]


def test_macro_toolkit_analysis_uses_landed_stock_factor_snapshot_for_multi_factor(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_choice_tushare_macro_db(duckdb_path)
    _seed_choice_stock_strategy_db(duckdb_path)
    _seed_choice_stock_factor_snapshot(duckdb_path)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()
    app = FastAPI()
    app.include_router(macro_toolkit_router)
    client = TestClient(app)

    try:
        response = client.get("/ui/macro/toolkit/analysis")
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    payload = response.json()
    strategies = {item["key"]: item for item in payload["result"]["strategy_summaries"]}
    multi_factor = strategies["multi_factor_selection"]
    assert multi_factor["status"] == "complete"
    assert multi_factor["warnings"] == []
    assert multi_factor["primary_metric"]["label"] == "真实入选数量"
    assert multi_factor["primary_metric"]["value"] == 1
    assert multi_factor["result"]["price_source"] == "choice_stock_daily_observation"
    assert multi_factor["result"]["source_versions"] == ["sv_stock"]
    assert multi_factor["result"]["vendor_versions"] == ["vv_stock"]
    assert multi_factor["result"]["factor_source"] == "choice_stock_factor_snapshot"
    assert multi_factor["result"]["factor_source_versions"] == ["sv_factor"]
    assert multi_factor["result"]["factor_vendor_versions"] == ["vv_factor"]
    assert multi_factor["result"]["factor_rule_versions"] == ["rv_factor"]
    assert multi_factor["result"]["factor_run_ids"] == ["run-factor"]
    assert multi_factor["result"]["selected_stock_codes"] == ["000001.SZ"]
    low_crowding = strategies["low_crowding_regime_multifactor"]
    assert low_crowding["status"] == "complete"
    assert low_crowding["warnings"] == []
    assert low_crowding["result"]["factor_source"] == "choice_stock_factor_snapshot"
    assert low_crowding["result"]["factor_source_versions"] == ["sv_factor"]
    assert low_crowding["result"]["factor_vendor_versions"] == ["vv_factor"]
    assert low_crowding["result"]["factor_rule_versions"] == ["rv_factor"]
    assert low_crowding["result"]["factor_run_ids"] == ["run-factor"]
    assert low_crowding["result"]["selected_stock_codes"]
    assert "target_position" in low_crowding["result"]
    assert low_crowding["result"]["crowding_excluded_count"] == 0
    assert "choice_stock_factor_snapshot" in payload["result_meta"]["tables_used"]


def test_macro_toolkit_multi_factor_uses_full_landed_factor_snapshot(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_choice_tushare_macro_db(duckdb_path)
    _seed_choice_stock_strategy_db(duckdb_path)
    _seed_choice_stock_factor_snapshot(duckdb_path)
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            insert into choice_stock_factor_snapshot values (
              '2026-04-30', '999999.SH',
              4.0, 0.4, 0.6,
              0.35, 0.60,
              0.40, 0.80,
              0.08, 0.10,
              'technology',
              'sv_factor', 'vv_factor', 'rv_factor', 'run-factor'
            )
            """
        )
    finally:
        conn.close()
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()
    app = FastAPI()
    app.include_router(macro_toolkit_router)
    client = TestClient(app)

    try:
        response = client.get("/ui/macro/toolkit/analysis")
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    payload = response.json()
    strategies = {item["key"]: item for item in payload["result"]["strategy_summaries"]}
    multi_factor = strategies["multi_factor_selection"]
    assert multi_factor["status"] == "complete"
    assert multi_factor["result"]["factor_row_count"] == 4
    assert multi_factor["result"]["selected_stock_codes"] == ["999999.SH"]


def test_macro_toolkit_choice_stock_refresh_runs_history_and_full_factor_snapshot(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    governance_path = tmp_path / "governance"
    sqlite_path = tmp_path / "auth-scope.db"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_path))
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv("MOSS_AUTH_TRUST_X_USER_ROLE_FOR_DEV_TEST", "1")
    get_settings.cache_clear()
    scope_repo = UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}")
    scope_repo.grant_scope(
        user_id="stock-refresh-user",
        role=None,
        resource="macro_toolkit",
        action="read",
    )
    scope_repo.grant_scope(
        user_id="stock-refresh-user",
        role=None,
        resource="macro_toolkit.choice_stock",
        action="refresh",
    )
    calls: list[tuple[str, dict[str, object]]] = []

    def fake_materialize_choice_stock_inputs(**kwargs: object) -> dict[str, object]:
        calls.append(("history", dict(kwargs)))
        return {
            "status": "completed",
            "run_id": "choice_stock_materialize:2026-04-30:fixture",
            "as_of_date": "2026-04-30",
            "row_count": 111,
            "stock_code_count": 5,
            "source_version": "sv_history",
            "vendor_version": "vv_history",
        }

    def fake_materialize_choice_stock_factor_snapshot(**kwargs: object) -> dict[str, object]:
        calls.append(("factor", dict(kwargs)))
        return {
            "status": "completed",
            "row_count": 222,
            "stock_code_count": 5,
            "source_version": "sv_factor",
            "vendor_version": "vv_factor",
        }

    monkeypatch.setattr(macro_toolkit_service, "materialize_choice_stock_inputs", fake_materialize_choice_stock_inputs)
    monkeypatch.setattr(
        macro_toolkit_service,
        "materialize_choice_stock_factor_snapshot",
        fake_materialize_choice_stock_factor_snapshot,
    )
    monkeypatch.setattr(
        macro_toolkit_service,
        "verify_choice_stock_daily_observation_landing",
        lambda **_kwargs: 5,
    )
    app = FastAPI()
    app.include_router(macro_toolkit_router)
    client = TestClient(app)
    headers = {"X-User-Id": "stock-refresh-user", "X-User-Role": "viewer"}

    try:
        response = client.post(
            "/ui/macro/toolkit/choice-stock/refresh",
            json={
                "as_of_date": "2026-04-30",
                "refresh_history": True,
                "refresh_factors": True,
                "factor_max_stock_count": None,
            },
            headers=headers,
        )
        payload = response.json()
        status_response = _wait_for_choice_stock_refresh_status(
            client,
            run_id=payload["result"]["refresh"]["run_id"],
            headers=headers,
        )
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    refresh = payload["result"]["refresh"]
    assert refresh["status"] == "queued"
    assert refresh["trigger_mode"] == "async"
    assert refresh["permission"]["mode"] == "scoped_refresh"
    assert refresh["permission"]["user_id"] == "stock-refresh-user"
    assert calls == [
        (
            "history",
            {
                "as_of_date": "2026-04-30",
                "duckdb_path": str(duckdb_path),
                "catalog_path": str(get_settings().choice_stock_catalog_file),
            },
        ),
        (
            "factor",
            {
                "as_of_date": "2026-04-30",
                "duckdb_path": str(duckdb_path),
                "max_stock_count": None,
            },
        ),
    ]
    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["result"]["refresh"]["status"] == "completed"
    assert status_payload["result"]["refresh"]["history_row_count"] == 111
    assert status_payload["result"]["refresh"]["factor_row_count"] == 222
    assert status_payload["result"]["refresh"]["trigger_mode"] == "terminal"
    assert status_payload["result"]["refresh"]["source_version"] == "sv_factor"
    assert status_payload["result"]["refresh"]["vendor_version"] == "vv_factor"
    assert status_payload["result"]["refresh"]["rule_version"] == "rv_choice_stock_materialization_front_layer_v1"
    assert status_payload["result"]["refresh"]["cache_version"] == "choice_stock_refresh_v1"
    observation_manifest = GovernanceRepository(base_dir=governance_path).read_latest_manifest(
        macro_toolkit_service.CHOICE_STOCK_REFRESH_CACHE_KEY
    )
    assert observation_manifest is not None
    assert observation_manifest["report_date"] == "2026-04-30"
    assert observation_manifest["source_version"] == "sv_history"
    assert observation_manifest["vendor_version"] == "vv_history"
    assert observation_manifest["lineage"]["materialization_run_id"] == (
        "choice_stock_materialize:2026-04-30:fixture"
    )


def test_macro_toolkit_choice_stock_refresh_reuses_run_for_same_idempotency_key(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    governance_path = tmp_path / "governance"
    sqlite_path = tmp_path / "auth-scope.db"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_path))
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv("MOSS_AUTH_TRUST_X_USER_ROLE_FOR_DEV_TEST", "1")
    get_settings.cache_clear()
    scope_repo = UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}")
    scope_repo.grant_scope(
        user_id="stock-refresh-user",
        role=None,
        resource="macro_toolkit",
        action="read",
    )
    scope_repo.grant_scope(
        user_id="stock-refresh-user",
        role=None,
        resource="macro_toolkit.choice_stock",
        action="refresh",
    )
    calls: list[tuple[str, dict[str, object]]] = []

    monkeypatch.setattr(
        macro_toolkit_service,
        "materialize_choice_stock_inputs",
        lambda **kwargs: calls.append(("history", dict(kwargs)))
        or {
            "status": "completed",
            "run_id": "choice_stock_materialize:2026-04-30:idempotency-fixture",
            "as_of_date": "2026-04-30",
            "row_count": 111,
            "stock_code_count": 5,
            "source_version": "sv_history",
            "vendor_version": "vv_history",
        },
    )
    monkeypatch.setattr(
        macro_toolkit_service,
        "materialize_choice_stock_factor_snapshot",
        lambda **kwargs: calls.append(("factor", dict(kwargs)))
        or {"status": "completed", "row_count": 222, "source_version": "sv_factor"},
    )
    monkeypatch.setattr(
        macro_toolkit_service,
        "verify_choice_stock_daily_observation_landing",
        lambda **_kwargs: 5,
    )

    app = FastAPI()
    app.include_router(macro_toolkit_router)
    client = TestClient(app)
    headers = {
        "X-User-Id": "stock-refresh-user",
        "X-User-Role": "viewer",
        "Idempotency-Key": "choice-stock-refresh-2026-04-30",
    }
    body = {
        "as_of_date": "2026-04-30",
        "refresh_history": True,
        "refresh_factors": True,
        "factor_max_stock_count": None,
    }

    try:
        first_response = client.post(
            "/ui/macro/toolkit/choice-stock/refresh",
            json=body,
            headers=headers,
        )
        second_response = client.post(
            "/ui/macro/toolkit/choice-stock/refresh",
            json=body,
            headers=headers,
        )
    finally:
        get_settings.cache_clear()

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    first_refresh = first_response.json()["result"]["refresh"]
    second_refresh = second_response.json()["result"]["refresh"]
    assert second_refresh["run_id"] == first_refresh["run_id"]
    assert second_refresh["idempotency_key"] == "choice-stock-refresh-2026-04-30"
    assert second_refresh["idempotency_replay"] is True
    assert [name for name, _kwargs in calls] == ["history", "factor"]

    records = [
        record
        for record in GovernanceRepository(base_dir=governance_path).read_all(
            macro_toolkit_service.CACHE_BUILD_RUN_STREAM
        )
        if record.get("job_name") == "choice_stock_refresh"
        and record.get("run_id") == first_refresh["run_id"]
        and record.get("status") == "queued"
    ]
    assert len(records) == 1


def test_macro_toolkit_choice_stock_refresh_requires_explicit_refresh_scope_grant(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    governance_path = tmp_path / "governance"
    sqlite_path = tmp_path / "auth-scope.db"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_path))
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    calls: list[dict[str, object]] = []

    def fake_queue_choice_stock_refresh(**kwargs: object) -> macro_toolkit_service.MacroToolkitActionResult:
        calls.append(dict(kwargs))
        return macro_toolkit_service.MacroToolkitActionResult(
            payload={
                "status": "queued",
                "run_id": "choice-stock-refresh-auth-test",
                "permission": kwargs["permission"],
            },
            quality_flag="ok",
            fallback_mode="none",
            as_of_date="2026-04-30",
        )

    monkeypatch.setattr(macro_toolkit_service, "queue_choice_stock_refresh", fake_queue_choice_stock_refresh)
    app = FastAPI()
    app.include_router(macro_toolkit_router)
    client = TestClient(app, raise_server_exceptions=False)
    payload = {
        "as_of_date": "2026-04-30",
        "refresh_history": True,
        "refresh_factors": True,
        "factor_max_stock_count": None,
    }

    denied = client.post(
        "/ui/macro/toolkit/choice-stock/refresh",
        json=payload,
        headers={"X-User-Id": "choice-stock-refresh-user", "X-User-Role": "viewer"},
    )
    assert denied.status_code == 403, denied.text
    assert calls == []

    UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}").grant_scope(
        user_id="choice-stock-refresh-user",
        role=None,
        resource="macro_toolkit.choice_stock",
        action="refresh",
    )
    allowed = client.post(
        "/ui/macro/toolkit/choice-stock/refresh",
        json=payload,
        headers={"X-User-Id": "choice-stock-refresh-user", "X-User-Role": "viewer"},
    )
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["result"]["refresh"]["run_id"] == "choice-stock-refresh-auth-test"
    assert len(calls) == 1
    assert calls[0]["permission"]["resource"] == "macro_toolkit.choice_stock"
    get_settings.cache_clear()


def test_macro_toolkit_source_backfill_refresh_maps_alias_and_requires_scope(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    sqlite_path = tmp_path / "auth-scope.db"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    calls: list[dict[str, object]] = []
    source_cache_clears: list[str] = []

    def fake_backfill_macro_series(**kwargs: object) -> dict[str, object]:
        calls.append(dict(kwargs))
        return {
            "dry_run": False,
            "processed_count": 1,
            "total_added": 42,
            "results": {"SHIBOR:3M": 42},
            "errors": {},
            "run_id": "backfill_macro_v1:20260712T120000Z",
            "source_by_series": {"NCD.SHIBOR.3M": "tushare_macro"},
            "vendor_versions": {
                "NCD.SHIBOR.3M": "vv_backfill_macro_tushare_macro_20260430_deadbeefdeadbeef",
            },
        }

    monkeypatch.setattr(macro_toolkit_route, "backfill_macro_series", fake_backfill_macro_series)
    monkeypatch.setattr(
        macro_toolkit_route,
        "clear_system_macro_source_cache",
        lambda: source_cache_clears.append("cleared"),
        raising=False,
    )
    app = FastAPI()
    app.include_router(macro_toolkit_router)
    client = TestClient(app, raise_server_exceptions=False)
    request = {
        "alias": "M0041813",
        "start_date": "2026-04-01",
        "end_date": "2026-04-30",
        "sources": ["tushare_macro"],
    }

    denied = client.post(
        "/ui/macro/toolkit/source-backfill/refresh",
        json=request,
        headers={"X-User-Id": "macro-source-user", "X-User-Role": "viewer"},
    )
    assert denied.status_code == 403, denied.text
    assert calls == []
    assert source_cache_clears == []

    UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}").grant_scope(
        user_id="macro-source-user",
        role=None,
        resource="macro_toolkit.source_backfill",
        action="refresh",
    )
    unsupported = client.post(
        "/ui/macro/toolkit/source-backfill/refresh",
        json={**request, "alias": "CU0"},
        headers={"X-User-Id": "macro-source-user", "X-User-Role": "viewer"},
    )
    assert unsupported.status_code == 400, unsupported.text
    assert "Unsupported macro source backfill alias" in unsupported.text
    assert calls == []
    assert source_cache_clears == []

    allowed = client.post(
        "/ui/macro/toolkit/source-backfill/refresh",
        json=request,
        headers={"X-User-Id": "macro-source-user", "X-User-Role": "viewer"},
    )

    assert allowed.status_code == 200, allowed.text
    payload = allowed.json()
    refresh = payload["result"]["refresh"]
    assert refresh["status"] == "completed"
    assert refresh["alias"] == "M0041813"
    assert refresh["series_ids"] == ["NCD.SHIBOR.3M"]
    assert refresh["total_added"] == 42
    assert refresh["run_id"] == "backfill_macro_v1:20260712T120000Z"
    assert refresh["source_by_series"] == {"NCD.SHIBOR.3M": "tushare_macro"}
    assert refresh["vendor_versions"] == {
        "NCD.SHIBOR.3M": "vv_backfill_macro_tushare_macro_20260430_deadbeefdeadbeef",
    }
    assert calls == [
        {
            "duckdb_path": str(duckdb_path),
            "series_names": ["SHIBOR:3M"],
            "start_date": "2026-04-01",
            "end_date": "2026-04-30",
            "dry_run": False,
            "sources_filter": ["tushare_macro"],
        }
    ]
    assert source_cache_clears == ["cleared"]
    get_settings.cache_clear()


def test_macro_toolkit_source_backfill_preserves_blocked_status_without_cache_clear(
    tmp_path,
    monkeypatch,
) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    sqlite_path = tmp_path / "auth-scope.db"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    source_cache_clears: list[str] = []
    response_cache_invalidations: list[str] = []

    monkeypatch.setattr(
        macro_toolkit_route,
        "backfill_macro_series",
        lambda **_kwargs: {
            "status": "blocked",
            "dry_run": False,
            "fetch_preview": False,
            "processed_count": 1,
            "total_fetched": 0,
            "total_added": 0,
            "results": {"制造业PMI": 0},
            "errors": {"制造业PMI": "no rows fetched for series_id=M0017126"},
            "source_by_series": {},
            "vendor_versions": {},
        },
    )
    monkeypatch.setattr(
        macro_toolkit_route,
        "clear_system_macro_source_cache",
        lambda: source_cache_clears.append("cleared"),
        raising=False,
    )
    monkeypatch.setattr(
        macro_toolkit_route.market_home_response_cache,
        "invalidate",
        lambda: response_cache_invalidations.append("invalidated"),
    )
    UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}").grant_scope(
        user_id="macro-source-user",
        role=None,
        resource="macro_toolkit.source_backfill",
        action="refresh",
    )
    app = FastAPI()
    app.include_router(macro_toolkit_router)
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post(
        "/ui/macro/toolkit/source-backfill/refresh",
        json={
            "alias": "M0017126",
            "start_date": "2026-04-01",
            "end_date": "2026-04-30",
            "sources": ["tushare_macro"],
        },
        headers={"X-User-Id": "macro-source-user", "X-User-Role": "viewer"},
    )

    assert response.status_code == 200, response.text
    refresh = response.json()["result"]["refresh"]
    assert refresh["status"] == "blocked"
    assert refresh["total_added"] == 0
    assert refresh["errors"] == {"制造业PMI": "no rows fetched for series_id=M0017126"}
    assert source_cache_clears == []
    assert response_cache_invalidations == []
    get_settings.cache_clear()


def test_macro_toolkit_commodity_futures_refresh_requires_scope_and_queues_ingest(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    sqlite_path = tmp_path / "auth-scope.db"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    calls: list[dict[str, object]] = []
    source_cache_clears: list[str] = []

    def fail_run_commodity_daily_ingest(**kwargs: object) -> dict[str, object]:
        calls.append(dict(kwargs))
        raise AssertionError("Commodity futures API refresh should queue the ingest task instead of running it inline.")

    queued_messages: list[dict[str, object]] = []

    class FakeCommodityIngestActor:
        @staticmethod
        def send(**kwargs: object) -> None:
            queued_messages.append(dict(kwargs))

    monkeypatch.setattr(
        macro_toolkit_service,
        "run_commodity_daily_ingest",
        fail_run_commodity_daily_ingest,
        raising=False,
    )
    monkeypatch.setattr(
        macro_toolkit_service,
        "run_commodity_daily_ingest_task",
        FakeCommodityIngestActor,
        raising=False,
    )
    monkeypatch.setattr(
        macro_toolkit_route,
        "clear_system_macro_source_cache",
        lambda: source_cache_clears.append("cleared"),
        raising=False,
    )
    app = FastAPI()
    app.include_router(macro_toolkit_router)
    client = TestClient(app, raise_server_exceptions=False)
    request = {
        "start_date": "2026-05-01",
        "end_date": "2026-06-01",
        "products": ["RB", "CU", "SC"],
        "dry_run": False,
    }

    denied = client.post(
        "/ui/macro/toolkit/commodity-futures/refresh",
        json=request,
        headers={"X-User-Id": "commodity-refresh-user", "X-User-Role": "viewer"},
    )
    assert denied.status_code == 403, denied.text
    assert calls == []
    assert source_cache_clears == []

    UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}").grant_scope(
        user_id="commodity-refresh-user",
        role=None,
        resource="macro_toolkit.commodity_futures",
        action="refresh",
    )
    allowed = client.post(
        "/ui/macro/toolkit/commodity-futures/refresh",
        json=request,
        headers={"X-User-Id": "commodity-refresh-user", "X-User-Role": "viewer"},
    )

    assert allowed.status_code == 200, allowed.text
    payload = allowed.json()
    refresh = payload["result"]["refresh"]
    assert refresh["status"] == "queued"
    assert refresh["row_count"] is None
    assert refresh["product_count"] == 3
    assert refresh["products"] == ["RB", "CU", "SC"]
    assert refresh["table"] == "fact_commodity_futures_daily"
    assert refresh["permission"]["resource"] == "macro_toolkit.commodity_futures"
    assert refresh["permission"]["actions"] == ["dry_run", "refresh"]
    assert payload["result"]["commodity_futures_refresh"]["permission"] == refresh["permission"]
    assert payload["result_meta"]["result_kind"] == "macro_toolkit.commodity_futures_refresh"
    assert calls == []
    assert queued_messages == [
        {
            "start_date": "2026-05-01",
            "end_date": "2026-06-01",
            "duckdb_path": str(duckdb_path),
            "products": ("RB", "CU", "SC"),
            "dry_run": False,
        }
    ]
    assert source_cache_clears == []
    get_settings.cache_clear()


def test_macro_toolkit_commodity_futures_refresh_reports_queue_failure(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    sqlite_path = tmp_path / "auth-scope.db"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()

    class BrokenCommodityIngestActor:
        @staticmethod
        def send(**_kwargs: object) -> None:
            raise RuntimeError("queue broker unavailable")

    monkeypatch.setattr(
        macro_toolkit_service,
        "run_commodity_daily_ingest_task",
        BrokenCommodityIngestActor,
        raising=False,
    )
    UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}").grant_scope(
        user_id="commodity-refresh-user",
        role=None,
        resource="macro_toolkit.commodity_futures",
        action="refresh",
    )
    app = FastAPI()
    app.include_router(macro_toolkit_router)
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post(
        "/ui/macro/toolkit/commodity-futures/refresh",
        json={"end_date": "2026-06-01", "products": ["NHCI"], "dry_run": False},
        headers={"X-User-Id": "commodity-refresh-user", "X-User-Role": "viewer"},
    )

    assert response.status_code == 503, response.text
    assert "queue broker unavailable" in response.text
    get_settings.cache_clear()


def test_macro_toolkit_commodity_futures_refresh_returns_queued_baseline_health_summary(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    sqlite_path = tmp_path / "auth-scope.db"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    baseline_status = {
        "materialized": True,
        "status": "ok",
        "table": "fact_commodity_futures_daily",
        "row_count": 120,
        "latest_trade_date": "2026-05-20",
        "source_vendors": ["tushare"],
        "coverage": {
            "target_product_count": 7,
            "available_product_count": 5,
            "available_products": ["CU", "AL", "SC", "AU", "NHCI"],
            "missing_products": ["RB", "I"],
        },
        "nanhua_input": {
            "status": "hit",
            "product_code": "NHCI",
            "series_id": "NH0100.NHF",
            "system_series_id": "NHCI.NH",
            "latest_trade_date": "2026-05-20",
            "latest_value": 3007.05,
            "row_count": 18,
            "source_version": "sv_tushare_index_daily_nhci_old",
            "vendor_version": "vv_tushare_index_daily_NHCI_20260520",
            "rule_version": "rv_commodity_daily_v1",
        },
    }
    queued_messages: list[dict[str, object]] = []

    def fake_commodity_status(_duckdb_path: object) -> dict[str, object]:
        return baseline_status

    class FakeCommodityIngestActor:
        @staticmethod
        def send(**kwargs: object) -> None:
            queued_messages.append(dict(kwargs))

    monkeypatch.setattr(macro_toolkit_route, "_commodity_futures_status", fake_commodity_status)
    monkeypatch.setattr(
        macro_toolkit_service,
        "run_commodity_daily_ingest_task",
        FakeCommodityIngestActor,
        raising=False,
    )
    app = FastAPI()
    app.include_router(macro_toolkit_router)
    client = TestClient(app)
    UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}").grant_scope(
        user_id="commodity-refresh-user",
        role=None,
        resource="macro_toolkit.commodity_futures",
        action="refresh",
    )

    response = client.post(
        "/ui/macro/toolkit/commodity-futures/refresh",
        json={"start_date": "2026-05-01", "end_date": "2026-06-01", "dry_run": False},
        headers={"X-User-Id": "commodity-refresh-user", "X-User-Role": "viewer"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()["result"]
    refresh = payload["refresh"]
    assert refresh["status"] == "queued"
    assert refresh["row_count"] is None
    assert refresh["before_status"]["latest_trade_date"] == "2026-05-20"
    assert refresh["after_status"]["latest_trade_date"] == "2026-05-20"
    assert refresh["summary"] == {
        "table": "fact_commodity_futures_daily",
        "row_count_before": 120,
        "row_count_after": 120,
        "row_count_delta": 0,
        "latest_trade_date_before": "2026-05-20",
        "latest_trade_date_after": "2026-05-20",
        "available_product_count_before": 5,
        "available_product_count_after": 5,
        "target_product_count": 7,
        "newly_available_products": [],
        "missing_products_after": ["RB", "I"],
        "nanhua_status_before": "hit",
        "nanhua_status_after": "hit",
        "nanhua_latest_date_before": "2026-05-20",
        "nanhua_latest_date_after": "2026-05-20",
        "nanhua_latest_value_after": 3007.05,
        "source_vendors_after": ["tushare"],
        "dry_run": False,
    }
    assert payload["commodity_futures_refresh"]["status"]["latest_trade_date"] == "2026-05-20"
    assert payload["commodity_futures_refresh"]["refresh"]["summary"]["row_count_delta"] == 0
    assert queued_messages == [
        {
            "start_date": "2026-05-01",
            "end_date": "2026-06-01",
            "duckdb_path": str(duckdb_path),
            "products": ("RB", "I", "CU", "AL", "SC", "AU", "NHCI"),
            "dry_run": False,
        }
    ]
    get_settings.cache_clear()


def test_macro_toolkit_commodity_futures_dry_run_returns_baseline_health_summary(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    sqlite_path = tmp_path / "auth-scope.db"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    baseline_status = {
        "materialized": True,
        "status": "ok",
        "table": "fact_commodity_futures_daily",
        "row_count": 120,
        "latest_trade_date": "2026-05-20",
        "source_vendors": ["tushare"],
        "coverage": {
            "target_product_count": 7,
            "available_product_count": 5,
            "available_products": ["CU", "AL", "SC", "AU", "NHCI"],
            "missing_products": ["RB", "I"],
        },
        "nanhua_input": {
            "status": "hit",
            "product_code": "NHCI",
            "series_id": "NH0100.NHF",
            "system_series_id": "NHCI.NH",
            "latest_trade_date": "2026-05-20",
            "latest_value": 3007.05,
            "row_count": 18,
            "source_version": "sv_tushare_index_daily_nhci_old",
            "vendor_version": "vv_tushare_index_daily_NHCI_20260520",
            "rule_version": "rv_commodity_daily_v1",
        },
    }

    def fake_commodity_status(_duckdb_path: object) -> dict[str, object]:
        return baseline_status

    def fake_run_commodity_daily_ingest(**kwargs: object) -> dict[str, object]:
        assert kwargs["dry_run"] is True
        return {
            "status": "dry_run",
            "dry_run": True,
            "start_date": "2026-05-01",
            "end_date": "2026-06-01",
            "product_count": 4,
            "estimated_total_rows": 88,
            "estimated_trading_days": 22,
            "products": [
                {"product_code": "CU", "estimated_rows": 22, "vendor": "estimate_only", "series_id": "CA.COPPER"},
                {"product_code": "SC", "estimated_rows": 22, "vendor": "estimate_only", "series_id": "COMMODITY.SC"},
                {"product_code": "AU", "estimated_rows": 22, "vendor": "estimate_only", "series_id": "COMMODITY.AU"},
                {"product_code": "NHCI", "estimated_rows": 22, "vendor": "estimate_only", "series_id": "NHCI.NH"},
            ],
            "rule_version": "rv_commodity_daily_v1",
            "table": "fact_commodity_futures_daily",
        }

    monkeypatch.setattr(macro_toolkit_route, "_commodity_futures_status", fake_commodity_status)
    monkeypatch.setattr(macro_toolkit_service, "run_commodity_daily_ingest", fake_run_commodity_daily_ingest)
    app = FastAPI()
    app.include_router(macro_toolkit_router)
    client = TestClient(app)
    UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}").grant_scope(
        user_id="commodity-refresh-user",
        role=None,
        resource="macro_toolkit.commodity_futures",
        action="refresh",
    )

    response = client.post(
        "/ui/macro/toolkit/commodity-futures/refresh",
        json={
            "start_date": "2026-05-01",
            "end_date": "2026-06-01",
            "products": ["CU", "SC", "AU", "NHCI"],
            "dry_run": True,
        },
        headers={"X-User-Id": "commodity-refresh-user", "X-User-Role": "viewer"},
    )

    assert response.status_code == 200, response.text
    refresh = response.json()["result"]["refresh"]
    assert refresh["status"] == "dry_run"
    assert refresh["before_status"] == baseline_status
    assert refresh["after_status"] == baseline_status
    assert refresh["summary"]["dry_run"] is True
    assert refresh["summary"]["row_count_before"] == 120
    assert refresh["summary"]["row_count_after"] == 120
    assert refresh["summary"]["row_count_delta"] == 0
    assert refresh["summary"]["latest_trade_date_before"] == "2026-05-20"
    assert refresh["summary"]["latest_trade_date_after"] == "2026-05-20"
    assert refresh["summary"]["available_product_count_before"] == 5
    assert refresh["summary"]["available_product_count_after"] == 5
    assert refresh["summary"]["missing_products_after"] == ["RB", "I"]
    assert refresh["summary"]["nanhua_latest_value_after"] == 3007.05
    assert response.json()["result"]["commodity_futures_refresh"]["status"] == baseline_status
    get_settings.cache_clear()


def test_macro_toolkit_commodity_futures_status_delegates_to_service(tmp_path, monkeypatch) -> None:
    expected_status = {
        "materialized": True,
        "status": "ok",
        "table": "fact_commodity_futures_daily",
        "row_count": 1,
    }
    calls: list[object] = []

    def fake_commodity_futures_status(duckdb_path: object) -> dict[str, object]:
        calls.append(duckdb_path)
        return expected_status

    monkeypatch.setattr(
        macro_toolkit_service,
        "commodity_futures_status",
        fake_commodity_futures_status,
        raising=False,
    )

    duckdb_path = tmp_path / "moss.duckdb"

    assert macro_toolkit_route._commodity_futures_status(duckdb_path) == expected_status
    assert calls == [duckdb_path]
    assert "duckdb.connect" not in inspect.getsource(macro_toolkit_route._commodity_futures_status)


def test_macro_toolkit_commodity_futures_refresh_rejects_unknown_products(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    sqlite_path = tmp_path / "auth-scope.db"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    calls: list[dict[str, object]] = []

    def fake_run_commodity_daily_ingest(**kwargs: object) -> dict[str, object]:
        calls.append(dict(kwargs))
        return {"status": "completed", "products": [], "row_count": 0}

    monkeypatch.setattr(macro_toolkit_service, "refresh_commodity_futures", fake_run_commodity_daily_ingest)
    UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}").grant_scope(
        user_id="commodity-refresh-user",
        role=None,
        resource="macro_toolkit.commodity_futures",
        action="refresh",
    )
    app = FastAPI()
    app.include_router(macro_toolkit_router)
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post(
        "/ui/macro/toolkit/commodity-futures/refresh",
        json={
            "start_date": "2026-05-01",
            "end_date": "2026-06-01",
            "products": ["UNKNOWN"],
            "dry_run": False,
        },
        headers={"X-User-Id": "commodity-refresh-user", "X-User-Role": "viewer"},
    )

    assert response.status_code == 400, response.text
    assert "Unknown commodity futures product" in response.text
    assert calls == []
    get_settings.cache_clear()


def test_macro_toolkit_commodity_futures_refresh_rejects_empty_product_list(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    sqlite_path = tmp_path / "auth-scope.db"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    calls: list[dict[str, object]] = []

    def fake_run_commodity_daily_ingest(**kwargs: object) -> dict[str, object]:
        calls.append(dict(kwargs))
        return {"status": "completed", "products": [], "row_count": 0}

    monkeypatch.setattr(macro_toolkit_service, "refresh_commodity_futures", fake_run_commodity_daily_ingest)
    UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}").grant_scope(
        user_id="commodity-refresh-user",
        role=None,
        resource="macro_toolkit.commodity_futures",
        action="refresh",
    )
    app = FastAPI()
    app.include_router(macro_toolkit_router)
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post(
        "/ui/macro/toolkit/commodity-futures/refresh",
        json={
            "start_date": "2026-05-01",
            "end_date": "2026-06-01",
            "products": [],
            "dry_run": False,
        },
        headers={"X-User-Id": "commodity-refresh-user", "X-User-Role": "viewer"},
    )

    assert response.status_code == 400, response.text
    assert "At least one commodity futures product is required" in response.text
    assert calls == []
    get_settings.cache_clear()


def test_macro_toolkit_choice_stock_refresh_rejects_inflight_run(tmp_path, monkeypatch) -> None:
    governance_path = tmp_path / "governance"
    sqlite_path = tmp_path / "auth-scope.db"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_path))
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    get_settings.cache_clear()
    UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}").grant_scope(
        user_id="*",
        role=None,
        resource="macro_toolkit.choice_stock",
        action="refresh",
    )
    GovernanceRepository(base_dir=governance_path).append(
        macro_toolkit_service.CACHE_BUILD_RUN_STREAM,
        macro_toolkit_service.build_choice_stock_refresh_run_payload(
            run_id="choice_stock_refresh:2026-04-30:existing",
            status="running",
            as_of_date="2026-04-30",
            queued_at="2026-05-06T00:00:00+00:00",
        ),
    )
    app = FastAPI()
    app.include_router(macro_toolkit_router)
    client = TestClient(app)

    try:
        response = client.post(
            "/ui/macro/toolkit/choice-stock/refresh",
            json={
                "as_of_date": "2026-04-30",
                "refresh_history": True,
                "refresh_factors": True,
            },
        )
    finally:
        get_settings.cache_clear()

    assert response.status_code == 409
    assert response.json()["detail"] == "Choice stock refresh already in progress for as_of_date=2026-04-30."


def test_macro_toolkit_routes_delegate_high_risk_orchestration() -> None:
    source_expectations = {
        "macro_toolkit_run": ["subprocess.run", "run_toolkit_script(", "sys.executable"],
        "macro_toolkit_refresh_cffex_member_rank": ["materialize_cffex_member_rank("],
        "macro_toolkit_refresh_choice_stock": ["acquire_lock(", "add_task(", "materialize_choice_stock"],
        "macro_toolkit_refresh_commodity_futures": [
            "run_commodity_daily_ingest(",
            "run_commodity_daily_ingest_task",
        ],
    }
    for endpoint in macro_toolkit_router.routes:
        name = getattr(endpoint.endpoint, "__name__", "")
        if name not in source_expectations:
            continue
        source = inspect.getsource(endpoint.endpoint)
        for forbidden in source_expectations[name]:
            assert forbidden not in source, f"{name} should delegate {forbidden}"


def test_macro_toolkit_cffex_refresh_uses_service_meta_overrides(monkeypatch) -> None:
    monkeypatch.setattr(macro_toolkit_route, "_ensure_cffex_member_rank_refresh_allowed", lambda *_args, **_kwargs: None)

    def fake_refresh_cffex_member_rank(**_kwargs: object) -> macro_toolkit_service.MacroToolkitActionResult:
        return macro_toolkit_service.MacroToolkitActionResult(
            payload={"trade_date": "2026-04-10", "row_count": 0, "sources": ["choice"]},
            quality_flag="warning",
            fallback_mode="latest_snapshot",
            as_of_date="2026-04-10",
        )

    monkeypatch.setattr(macro_toolkit_service, "refresh_cffex_member_rank", fake_refresh_cffex_member_rank)
    monkeypatch.setattr(
        macro_toolkit_route,
        "_cffex_member_rank_status",
        lambda *_args, **_kwargs: {"status": "stale", "latest_trade_date": "2026-04-10"},
    )

    app = FastAPI()
    app.include_router(macro_toolkit_router)
    client = TestClient(app)
    response = client.post(
        "/ui/macro/toolkit/cffex-member-rank/refresh",
        json={"trade_date": "2026-04-10", "contracts": ["T.CFE"], "sources": ["choice"]},
        headers={"X-User-Id": "macro-refresh-user"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["quality_flag"] == "warning"
    assert payload["result_meta"]["fallback_mode"] == "latest_snapshot"
    assert payload["result_meta"]["as_of_date"] == "2026-04-10"


def _wait_for_choice_stock_refresh_status(
    client: TestClient,
    *,
    run_id: str,
    headers: dict[str, str] | None = None,
    timeout_seconds: float = 5.0,
):
    deadline = time.monotonic() + timeout_seconds
    last_response = None
    while time.monotonic() < deadline:
        last_response = client.get(
            "/ui/macro/toolkit/choice-stock/refresh-status",
            params={"run_id": run_id},
            headers=headers,
        )
        if last_response.status_code == 200:
            status = last_response.json()["result"]["refresh"]["status"]
            if status in {"completed", "failed"}:
                return last_response
        time.sleep(0.05)
    assert last_response is not None
    return last_response


def test_macro_toolkit_api_surfaces_capability_plan_and_stale_cffex_status(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_choice_tushare_macro_db(duckdb_path)
    output_dir = tmp_path / "macro_toolkit_output"
    output_dir.mkdir()
    (output_dir / "cta_results.csv").write_text("date,value\n2026-04-29,1\n", encoding="utf-8")
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            insert into choice_market_snapshot values (
              'CA.CSI300', 'CSI 300 close', 'index_daily:000300.SH.close', 'tushare', '2026-04-30',
              4200.0, 'daily', 'index', 'sv_tushare_index', 'vv_tushare_index',
              'rv_public_cross_asset_headline_v1', 'tushare-run-latest'
            )
            """
        )
    finally:
        conn.close()
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setattr(macro_toolkit_route, "OUTPUT_DIR", output_dir)
    get_settings.cache_clear()
    app = FastAPI()
    app.include_router(macro_toolkit_router)
    client = TestClient(app)

    try:
        response = client.get("/ui/macro/toolkit/scripts")
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    payload = response.json()
    capabilities = {item["key"]: item for item in payload["result"]["capabilities"]}
    assert capabilities["monetary_policy_stance"]["legacy_module"] == "M7"
    assert all(item["route_status"] == "wired" for item in capabilities.values())
    assert all(item["frontend_status"] == "visible" for item in capabilities.values())
    assert capabilities["yield_curve_shape"]["implementation_status"] == "library_ready"
    assert payload["result"]["cffex_member_rank"]["freshness_status"] == "stale"
    assert payload["result"]["cffex_member_rank"]["reference_date"] == "2026-04-30"
    assert payload["result"]["cffex_member_rank"]["stale_days"] == 20
    readiness_by_id = {item["id"]: item for item in payload["result"]["model_readiness"]}
    assert readiness_by_id["cta_trend"]["readiness"] == "stale"
    assert readiness_by_id["cta_trend"]["stale_outputs"] == ["cta_results.csv"]
    assert readiness_by_id["cta_trend"]["outputs"][0]["reference_date"] == "2026-04-30"
    assert any("中金所席位排名已落库但最新交易日 2026-04-10" in item for item in payload["result"]["warnings"])


def test_macro_toolkit_capability_plan_reuses_source_check_cache(monkeypatch) -> None:
    def source_check_payload(alias: str) -> dict[str, object]:
        return {
            "alias": alias,
            "row_count": 1,
            "latest": {
                "date": "2026-04-30",
                "series_id": alias,
                "vendor_name": "choice",
                "value": 1.0,
            },
        }

    calls: list[str] = []

    def fake_source_check(alias: str, duckdb_path: object, *, end: str | None = None) -> dict[str, object]:
        assert end is None
        calls.append(alias)
        return source_check_payload(alias)

    monkeypatch.setattr(macro_toolkit_route, "_source_check", fake_source_check)

    macro_toolkit_route._capability_plan(
        "dummy.duckdb",
        source_check_cache={
            "DR007.IB": source_check_payload("DR007.IB"),
            "S0059749": source_check_payload("S0059749"),
        },
    )

    assert "DR007.IB" not in calls
    assert "S0059749" not in calls
    assert len(calls) == len(set(calls))


def test_capability_definitions_declare_actual_curve_inputs_via_data_tables() -> None:
    definitions = {item["key"]: item for item in macro_toolkit_route._CAPABILITY_DEFINITIONS}

    # M8/M9/M13/M15 的实际计算经 load_macro_capability_context 走正式曲线表。
    for key in ("yield_curve_shape", "credit_spread_risk", "rate_turning_point", "macro_portfolio_impact"):
        assert "fact_formal_yield_curve_daily" in definitions[key]["data_tables"], key

    # M15 组合概况来自正式债券持仓表。
    assert "fact_formal_bond_analytics_daily" in definitions["macro_portfolio_impact"]["data_tables"]

    # 未被 compute 函数消费的别名不得再声明。
    assert "S0059670" not in definitions["credit_spread_risk"]["data_aliases"]
    assert set(definitions["rate_turning_point"]["data_aliases"]) == {"S0059743", "S0059749"}
    assert "S0059760" not in definitions["macro_portfolio_impact"]["data_aliases"]
    assert "M0067855" not in definitions["macro_portfolio_impact"]["data_aliases"]
    # 仍作为曲线回退点真实消费的别名保持声明。
    assert set(definitions["yield_curve_shape"]["data_aliases"]) == {"S0059743", "S0059747", "S0059749"}
    assert set(definitions["macro_portfolio_impact"]["data_aliases"]) == {
        "S0059743",
        "S0059746",
        "S0059747",
        "S0059748",
        "S0059749",
    }


def test_capability_payload_passes_through_data_tables() -> None:
    definitions = {item["key"]: item for item in macro_toolkit_route._CAPABILITY_DEFINITIONS}
    definition = definitions["macro_portfolio_impact"]
    cache = {
        str(alias): {
            "alias": str(alias),
            "row_count": 1,
            "latest": {
                "date": "2026-04-30",
                "series_id": str(alias),
                "vendor_name": "choice",
                "value": 1.0,
            },
        }
        for alias in definition["data_aliases"]
    }

    payload = macro_toolkit_route._capability_payload(
        definition,
        "dummy.duckdb",
        source_check_cache=cache,
    )

    assert payload["data_tables"] == [
        "fact_formal_yield_curve_daily",
        "fact_formal_bond_analytics_daily",
    ]
    assert payload["data_status"] == "ready"

    # 没有声明 data_tables 的能力透传为空列表。
    monetary = definitions["monetary_policy_stance"]
    monetary_cache = {
        str(alias): {"alias": str(alias), "row_count": 0, "latest": None}
        for alias in monetary["data_aliases"]
    }
    monetary_payload = macro_toolkit_route._capability_payload(
        monetary,
        "dummy.duckdb",
        source_check_cache=monetary_cache,
    )
    assert monetary_payload["data_tables"] == []


def test_macro_toolkit_api_runs_scripts_with_project_import_path(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_choice_tushare_macro_db(duckdb_path)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setattr(macro_toolkit_route, "_ensure_macro_toolkit_script_execute_allowed", lambda *_args, **_kwargs: None)
    get_settings.cache_clear()
    app = FastAPI()
    app.include_router(macro_toolkit_router)
    client = TestClient(app)

    try:
        response = client.post(
            "/ui/macro/toolkit/scripts/debug_wind/run",
            json={"timeout_seconds": 30},
            headers={"X-User-Id": "macro-script-user"},
        )
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["exit_code"] == 0
    assert "ErrorCode" in payload["stdout"]


def test_macro_toolkit_run_script_passes_configured_output_dir_to_subprocess(tmp_path, monkeypatch) -> None:
    requested_output_dir = tmp_path / "requested_output"
    inherited_output_dir = tmp_path / "inherited_output"
    requested_output_dir.mkdir()
    inherited_output_dir.mkdir()
    probe_script = tmp_path / "probe_cta_script.py"
    probe_script.write_text("", encoding="utf-8")
    fake_script = SimpleNamespace(
        name="cta_trend_cn",
        filename="cta_trend_cn.py",
        group="allocation",
        default_data_sources=(),
        optional_dependencies=(),
        notes="",
        path=probe_script,
    )
    calls: list[str] = []

    def fake_get_toolkit_script(name: str):
        calls.append(name)
        return fake_script

    monkeypatch.setenv("MOSS_MACRO_TOOLKIT_OUTPUT_DIR", str(inherited_output_dir))
    monkeypatch.setattr(macro_toolkit_service, "get_toolkit_script", fake_get_toolkit_script)
    monkeypatch.setattr(
        macro_toolkit_service,
        "_script_payload",
        lambda *_args, **_kwargs: {"name": "cta_trend_cn"},
    )
    captured_env: dict[str, str] = {}

    def fake_subprocess_run(_command, *, cwd, env, capture_output, text, timeout, check):
        assert cwd == str(macro_toolkit_service.TOOLKIT_ROOT)
        assert capture_output is True
        assert text is True
        assert timeout == 5
        assert check is False
        captured_env.update(env)
        Path(env["MOSS_MACRO_TOOLKIT_OUTPUT_DIR"], "cta_results.csv").write_text(
            "date,value\n2026-06-01,1\n",
            encoding="utf-8",
        )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(macro_toolkit_service.subprocess, "run", fake_subprocess_run)

    result = macro_toolkit_service.run_macro_toolkit_script(
        name="cta_trend_cn",
        argv=[],
        timeout_seconds=5,
        output_dir=requested_output_dir,
    )

    assert result["status"] == "completed", result["stderr"]
    assert calls == ["cta_trend_cn"]
    assert captured_env["MOSS_MACRO_TOOLKIT_OUTPUT_DIR"] == str(requested_output_dir.resolve())
    assert (requested_output_dir / "cta_results.csv").read_text(encoding="utf-8") == "date,value\n2026-06-01,1\n"
    assert not (inherited_output_dir / "cta_results.csv").exists()
    assert [item["name"] for item in result["output_files"]] == ["cta_results.csv"]


def test_macro_toolkit_run_script_inline_fallback_uses_configured_output_dir(tmp_path, monkeypatch) -> None:
    requested_output_dir = tmp_path / "requested_output"
    inherited_output_dir = tmp_path / "inherited_output"
    requested_output_dir.mkdir()
    inherited_output_dir.mkdir()
    fake_script = SimpleNamespace(
        name="cta_trend_cn",
        filename="cta_trend_cn.py",
        group="allocation",
        default_data_sources=(),
        optional_dependencies=(),
        notes="",
        path=tmp_path / "probe_cta_script.py",
    )

    def fake_run_toolkit_script(_name: str, _argv: list[str]):
        paths = importlib.import_module("paths")
        paths.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        (paths.OUTPUT_DIR / "cta_results.csv").write_text(
            "date,value\n2026-06-01,1\n",
            encoding="utf-8",
        )

    monkeypatch.syspath_prepend(str(TOOLKIT_ROOT))
    monkeypatch.delitem(sys.modules, "paths", raising=False)
    monkeypatch.setenv("MOSS_MACRO_TOOLKIT_OUTPUT_DIR", str(inherited_output_dir))
    monkeypatch.setattr(macro_toolkit_service, "get_toolkit_script", lambda _name: fake_script)
    monkeypatch.setattr(macro_toolkit_service, "run_toolkit_script", fake_run_toolkit_script)
    monkeypatch.setattr(
        macro_toolkit_service,
        "_script_payload",
        lambda *_args, **_kwargs: {"name": "cta_trend_cn"},
    )
    monkeypatch.setattr(
        macro_toolkit_service.subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("subprocess unavailable")),
    )

    result = macro_toolkit_service.run_macro_toolkit_script(
        name="cta_trend_cn",
        argv=[],
        timeout_seconds=5,
        output_dir=requested_output_dir,
    )

    assert result["status"] == "completed", result["stderr"]
    assert (requested_output_dir / "cta_results.csv").read_text(encoding="utf-8") == "date,value\n2026-06-01,1\n"
    assert not (inherited_output_dir / "cta_results.csv").exists()
    assert [item["name"] for item in result["output_files"]] == ["cta_results.csv"]


def test_macro_toolkit_script_chain_dry_run_reports_manifest_without_executing(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_choice_tushare_macro_db(duckdb_path)
    output_dir = tmp_path / "macro_toolkit_output"
    output_dir.mkdir()
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setattr(macro_toolkit_route, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(macro_toolkit_route, "_ensure_macro_toolkit_script_execute_allowed", lambda *_args, **_kwargs: None)

    def fail_if_executed(**_kwargs: object) -> dict[str, object]:
        raise AssertionError("dry-run must not execute macro toolkit scripts")

    monkeypatch.setattr(macro_toolkit_service, "run_macro_toolkit_script", fail_if_executed)
    get_settings.cache_clear()
    app = FastAPI()
    app.include_router(macro_toolkit_router)
    client = TestClient(app)

    try:
        response = client.post(
            "/ui/macro/toolkit/scripts/run-chain",
            json={"dry_run": True, "timeout_seconds": 30},
            headers={"X-User-Id": "macro-script-user"},
        )
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    payload = response.json()["result"]["run"]
    assert payload["status"] == "dry_run"
    assert payload["dry_run"] is True
    assert payload["observation_only"] is True
    assert payload["formal_use_allowed"] is False
    assert [step["script_name"] for step in payload["manifest"]] == [
        "merrill_clock_cn",
        "crisis_score_cn",
        "bond_futures_data",
        "bond_futures_signals",
        "crowding_cn",
        "dcc_garch_cn",
        "cta_trend_cn",
        "signal_aggregator",
        "risk_monitor",
    ]
    dcc_receipt = next(item for item in payload["receipts"] if item["script_name"] == "dcc_garch_cn")
    assert dcc_receipt["status"] == "dry_run"
    assert dcc_receipt["expected_outputs"] == ["dcc_latest.csv", "dcc_results.csv"]
    assert dcc_receipt["missing_outputs_after"] == ["dcc_latest.csv", "dcc_results.csv"]
    assert all(item["status"] == "dry_run" for item in payload["receipts"])
    assert all(isinstance(item["expected_outputs"], list) and item["expected_outputs"] for item in payload["receipts"])
    assert all(item["produced_outputs"] == [] for item in payload["receipts"])


def test_macro_toolkit_script_chain_manual_run_requires_each_manifest_script_scope(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_choice_tushare_macro_db(duckdb_path)
    output_dir = tmp_path / "macro_toolkit_output"
    output_dir.mkdir()
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setattr(macro_toolkit_route, "OUTPUT_DIR", output_dir)
    checked_scripts: list[str] = []
    executed_scripts: list[str] = []

    def fake_ensure(_auth: object, _settings: object, *, script_name: str) -> None:
        checked_scripts.append(script_name)
        if script_name == "dcc_garch_cn":
            raise macro_toolkit_route.HTTPException(status_code=403, detail="dcc denied")

    def fake_run_macro_toolkit_script(**kwargs: object) -> dict[str, object]:
        executed_scripts.append(str(kwargs["name"]))
        return {
            "status": "completed",
            "script": {"name": str(kwargs["name"])},
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
            "output_files": [],
        }

    monkeypatch.setattr(macro_toolkit_route, "_ensure_macro_toolkit_script_execute_allowed", fake_ensure)
    monkeypatch.setattr(macro_toolkit_service, "run_macro_toolkit_script", fake_run_macro_toolkit_script)
    get_settings.cache_clear()
    app = FastAPI()
    app.include_router(macro_toolkit_router)
    client = TestClient(app, raise_server_exceptions=False)

    try:
        response = client.post(
            "/ui/macro/toolkit/scripts/run-chain",
            json={"dry_run": False, "timeout_seconds": 30},
            headers={"X-User-Id": "macro-script-user"},
        )
    finally:
        get_settings.cache_clear()

    assert response.status_code == 403
    assert checked_scripts[:2] == ["macro_toolkit_chain", "merrill_clock_cn"]
    assert "dcc_garch_cn" in checked_scripts
    assert executed_scripts == []


def test_macro_toolkit_script_chain_manual_run_rejects_concurrent_run(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    governance_path = tmp_path / "governance"
    _seed_choice_tushare_macro_db(duckdb_path)
    output_dir = tmp_path / "macro_toolkit_output"
    output_dir.mkdir()
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_path))
    monkeypatch.setattr(macro_toolkit_route, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(macro_toolkit_route, "_ensure_macro_toolkit_script_execute_allowed", lambda *_args, **_kwargs: None)
    executed_scripts: list[str] = []

    def fake_run_macro_toolkit_script(**kwargs: object) -> dict[str, object]:
        executed_scripts.append(str(kwargs["name"]))
        return {
            "status": "completed",
            "script": {"name": str(kwargs["name"])},
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
            "output_files": [],
        }

    monkeypatch.setattr(macro_toolkit_service, "run_macro_toolkit_script", fake_run_macro_toolkit_script)
    get_settings.cache_clear()
    app = FastAPI()
    app.include_router(macro_toolkit_router)
    client = TestClient(app, raise_server_exceptions=False)

    try:
        with macro_toolkit_service.acquire_lock(
            macro_toolkit_service.MACRO_TOOLKIT_CHAIN_LOCK,
            base_dir=governance_path,
            timeout_seconds=0.1,
        ):
            response = client.post(
                "/ui/macro/toolkit/scripts/run-chain",
                json={"dry_run": False, "timeout_seconds": 30},
                headers={"X-User-Id": "macro-script-user"},
            )
    finally:
        get_settings.cache_clear()

    assert response.status_code == 409
    assert "macro toolkit script chain" in response.json()["detail"].lower()
    assert executed_scripts == []


def test_macro_toolkit_script_chain_manual_run_reconciles_expected_outputs(tmp_path, monkeypatch) -> None:
    output_dir = tmp_path / "macro_toolkit_output"
    output_dir.mkdir()
    executed: list[str] = []

    def fake_run_macro_toolkit_script(**kwargs: object) -> dict[str, object]:
        name = str(kwargs["name"])
        executed.append(name)
        if name == "merrill_clock_cn":
            (output_dir / "merrill_clock_latest.csv").write_text("日期,value\n2026-04-10,1\n", encoding="utf-8")
            (output_dir / "merrill_clock_history.csv").write_text("日期,value\n2026-04-10,1\n", encoding="utf-8")
        return {
            "status": "completed",
            "script": {"name": name},
            "exit_code": 0,
            "stdout": f"ran {name}",
            "stderr": "",
            "output_files": macro_toolkit_service.output_files(output_dir),
        }

    monkeypatch.setattr(macro_toolkit_service, "run_macro_toolkit_script", fake_run_macro_toolkit_script)

    payload = macro_toolkit_service.run_macro_toolkit_chain(
        dry_run=False,
        timeout_seconds=30,
        output_dir=output_dir,
    )

    assert payload["status"] == "degraded"
    assert executed == [
        "merrill_clock_cn",
        "crisis_score_cn",
        "bond_futures_data",
        "bond_futures_signals",
        "crowding_cn",
        "dcc_garch_cn",
        "cta_trend_cn",
        "signal_aggregator",
        "risk_monitor",
    ]
    merrill_receipt = next(item for item in payload["receipts"] if item["script_name"] == "merrill_clock_cn")
    assert merrill_receipt["produced_outputs"] == ["merrill_clock_history.csv", "merrill_clock_latest.csv"]
    dcc_receipt = next(item for item in payload["receipts"] if item["script_name"] == "dcc_garch_cn")
    assert dcc_receipt["chain_id"] == payload["chain_id"]
    assert dcc_receipt["status"] == "completed"
    assert dcc_receipt["missing_outputs_after"] == ["dcc_latest.csv", "dcc_results.csv"]
    assert dcc_receipt["degraded_reason"] == "missing_expected_outputs_after_run"
    assert dcc_receipt["blocker"] == {
        "type": "missing_expected_outputs_after_run",
        "script_name": "dcc_garch_cn",
        "missing_outputs": ["dcc_latest.csv", "dcc_results.csv"],
    }
    assert dcc_receipt["data_asof"] is None
    assert dcc_receipt["generated_at"]
    assert dcc_receipt["runtime_endpoint"] == "/ui/macro/toolkit/scripts/run-chain"
    assert dcc_receipt["page_surface"] == "/macro-toolkit#macro-toolkit-script-artifact-detail"
    assert dcc_receipt["formal_use_allowed"] is False
    assert dcc_receipt["observation_only"] is True
    dcc_readiness = next(item for item in payload["model_readiness"] if item["id"] == "dcc_garch")
    assert dcc_readiness["readiness"] == "missing_output"


def test_macro_model_readiness_exposes_machine_readable_artifact_receipts_for_missing_outputs(tmp_path) -> None:
    payload = macro_toolkit_service.macro_model_readiness(output_dir=tmp_path, reference_date="2026-06-01")
    readiness_by_id = {item["id"]: item for item in payload["model_readiness"]}

    expected_missing = {
        "dcc_garch": ["dcc_latest.csv", "dcc_results.csv"],
        "cta_trend": ["cta_results.csv"],
        "risk_monitor": ["risk_log.csv", "risk_state.csv"],
    }
    for model_id, missing_outputs in expected_missing.items():
        item = readiness_by_id[model_id]
        receipt = item["artifact_receipt"]

        assert item["readiness"] == "missing_output"
        assert item["degraded_reason"] == "missing_expected_outputs"
        assert item["evidence_level"] == "registered_script_only"
        assert item["date_basis"] == "missing"
        assert receipt["status"] == "missing_output"
        assert receipt["model_id"] == model_id
        assert receipt["script_name"] == item["script_name"]
        assert receipt["artifact_paths"] == []
        assert receipt["missing_artifacts"] == missing_outputs
        assert receipt["degraded_reason"] == "missing_expected_outputs"
        assert receipt["data_asof"] is None
        assert receipt["generated_at"]
        assert receipt["runtime_endpoint"] == "/ui/macro/toolkit/scripts/run-chain"
        assert receipt["page_surface"] == "/macro-toolkit#macro-toolkit-model-readiness-detail"
        assert receipt["formal_use_allowed"] is False
        assert receipt["observation_only"] is True


def _write_macro_readiness_artifact(output_dir: Path, name: str, *, report_date: str) -> None:
    pd.DataFrame([{"date": report_date, "value": 1.0}]).to_csv(output_dir / name, index=False)


def test_macro_model_readiness_artifact_backed_acceptance_for_observation_models(tmp_path) -> None:
    report_date = "2026-06-01"
    expected_outputs_by_model = {
        "merrill_clock": ["merrill_clock_latest.csv", "merrill_clock_history.csv"],
        "crisis_score": ["crisis_score_latest.csv", "crisis_score_history.csv"],
        "bond_futures_basis": ["bond_futures_latest.csv", "bond_futures_history.csv"],
        "bond_futures_four_factor": ["bond_signals_latest.csv"],
        "funding_conditions": ["merrill_clock_latest.csv"],
        "crowding": ["crowding_latest.csv", "crowding_history.csv"],
    }
    for artifact_name in sorted({name for names in expected_outputs_by_model.values() for name in names}):
        _write_macro_readiness_artifact(tmp_path, artifact_name, report_date=report_date)

    payload = macro_toolkit_service.macro_model_readiness(output_dir=tmp_path, reference_date=report_date)
    readiness_by_id = {item["id"]: item for item in payload["model_readiness"]}

    for model_id, expected_outputs in expected_outputs_by_model.items():
        item = readiness_by_id[model_id]
        receipt = item["artifact_receipt"]

        assert item["readiness"] == "artifact_backed"
        assert item["missing_outputs"] == []
        assert item["stale_outputs"] == []
        assert item["degraded_outputs"] == []
        assert item["degraded_reason"] is None
        assert item["evidence_level"] == "fresh_artifacts"
        assert item["date_basis"] == "csv_content"
        assert item["latest_content_date"] == report_date
        assert item["formal_use_allowed"] is False
        assert item["observation_only"] is True

        assert receipt["status"] == "artifact_backed"
        assert receipt["model_id"] == model_id
        assert receipt["script_name"] == item["script_name"]
        assert receipt["artifact_paths"] == sorted(expected_outputs)
        assert receipt["missing_artifacts"] == []
        assert receipt["degraded_reason"] is None
        assert receipt["data_asof"] == report_date
        assert receipt["generated_at"]
        assert receipt["runtime_endpoint"] == "/ui/macro/toolkit/scripts/run-chain"
        assert receipt["page_surface"] == "/macro-toolkit#macro-toolkit-model-readiness-detail"
        assert receipt["formal_use_allowed"] is False
        assert receipt["observation_only"] is True

    funding_item = readiness_by_id["funding_conditions"]
    assert funding_item["script_name"] == "merrill_clock_cn"
    assert funding_item["expected_outputs"] == ["merrill_clock_latest.csv"]

    funding_notes = " ".join(funding_item["notes"])
    assert "DR007/NCD" in funding_notes
    assert "Merrill liquidity momentum" in funding_notes
    assert "not a standalone formal metric" in funding_notes


def test_macro_toolkit_script_chain_receipts_include_contract_fields_for_dry_run(tmp_path) -> None:
    payload = macro_toolkit_service.run_macro_toolkit_chain(
        dry_run=True,
        timeout_seconds=30,
        output_dir=tmp_path,
        reference_date="2026-06-01",
    )

    assert payload["chain_id"]
    dcc_receipt = next(item for item in payload["receipts"] if item["script_name"] == "dcc_garch_cn")
    assert dcc_receipt["chain_id"] == payload["chain_id"]
    assert dcc_receipt["status"] == "dry_run"
    assert dcc_receipt["degraded_reason"] == "dry_run_not_executed"
    assert dcc_receipt["data_asof"] is None
    assert dcc_receipt["generated_at"]
    assert dcc_receipt["runtime_endpoint"] == "/ui/macro/toolkit/scripts/run-chain"
    assert dcc_receipt["page_surface"] == "/macro-toolkit#macro-toolkit-script-artifact-detail"
    assert dcc_receipt["formal_use_allowed"] is False
    assert dcc_receipt["observation_only"] is True
    assert dcc_receipt["missing_outputs_after"] == ["dcc_latest.csv", "dcc_results.csv"]


def test_macro_model_readiness_status_returns_registered_only_when_no_outputs_are_expected() -> None:
    readiness = macro_toolkit_service._model_readiness_status(
        script_available=True,
        expected_count=0,
        missing_outputs=[],
        stale_outputs=[],
        degraded_outputs=[],
        present_count=0,
    )

    assert readiness == "registered_only"


def test_macro_model_readiness_status_returns_artifact_backed_when_expected_outputs_are_current() -> None:
    readiness = macro_toolkit_service._model_readiness_status(
        script_available=True,
        expected_count=2,
        missing_outputs=[],
        stale_outputs=[],
        degraded_outputs=[],
        present_count=2,
    )

    assert readiness == "artifact_backed"


def test_macro_model_readiness_status_returns_stale_when_expected_outputs_are_present_but_stale() -> None:
    readiness = macro_toolkit_service._model_readiness_status(
        script_available=True,
        expected_count=2,
        missing_outputs=[],
        stale_outputs=["dcc_latest.csv"],
        degraded_outputs=[],
        present_count=2,
    )

    assert readiness == "stale"


class _FakeTushareModule:
    def pro_api(self, token: str):
        assert token == "token"
        return _FakeTusharePro()


class _FakeTusharePro:
    def fut_holding(self, **kwargs):
        assert kwargs["trade_date"] == "20260410"
        return pd.DataFrame(
            [
                {
                    "trade_date": "20260410",
                    "symbol": "T2606",
                    "broker": "中信期货",
                    "vol": 12000,
                    "vol_chg": 100,
                    "long_hld": 23000,
                    "long_chg": 200,
                    "short_hld": 20000,
                    "short_chg": -60,
                },
                {
                    "trade_date": "20260410",
                    "symbol": "T2609",
                    "broker": "中信期货",
                    "vol": 345,
                    "vol_chg": 101,
                    "long_hld": 456,
                    "long_chg": 2,
                    "short_hld": 1000,
                    "short_chg": 10,
                },
                {
                    "trade_date": "20260410",
                    "symbol": "T2606",
                    "broker": "国泰君安",
                    "vol": 8901,
                    "vol_chg": -20,
                    "long_hld": 10000,
                    "long_chg": 15,
                    "short_hld": 14000,
                    "short_chg": 30,
                },
                {
                    "trade_date": "20260410",
                    "symbol": "TF2606",
                    "broker": "不应命中",
                    "vol": 99999,
                    "vol_chg": 0,
                    "long_hld": 99999,
                    "long_chg": 0,
                    "short_hld": 99999,
                    "short_chg": 0,
                },
            ]
        )


class _FakeChoiceClient:
    def fut_transaction_rankings(self, symbols: str, trade_date: str, indicators: str):
        assert symbols == "CFFEX.T"
        assert trade_date == "2026-04-10"
        assert indicators == "volume,long,short"
        return pd.DataFrame(
            [
                {
                    "trade_date": "2026-04-10",
                    "contract": "T.CFE",
                    "member_name": "中信期货",
                    "volume": 12345,
                    "volume_change": 101,
                    "long_holding": 23456,
                    "long_change": 202,
                    "short_holding": 21000,
                    "short_change": -50,
                }
            ]
        )


def _seed_choice_tushare_macro_db(path) -> None:
    conn = duckdb.connect(str(path), read_only=False)
    try:
        ensure_cffex_member_rank_schema(conn)
        conn.execute(
            """
            insert into fact_cffex_member_rank_daily (
              trade_date, contract, product_code, exchange, member_name, source_vendor,
              source_row_no, volume, volume_change, long_holding, long_change,
              short_holding, short_change, source_version, vendor_version, rule_version,
              ingest_batch_id, raw_payload_json
            )
            values
              ('2026-04-10', 'T.CFE', 'T', 'CFFEX', '中信期货', 'tushare',
               1, 12345, 101, 23456, 202, 21000, -50,
               'sv_test_cffex_rank', 'vv_test_tushare', 'rv_cffex_member_rank_choice_tushare_v1',
               'batch-test', null),
              ('2026-04-10', 'T.CFE', 'T', 'CFFEX', '国泰君安', 'tushare',
               2, 8901, -20, 10000, 15, 14000, 30,
               'sv_test_cffex_rank', 'vv_test_tushare', 'rv_cffex_member_rank_choice_tushare_v1',
               'batch-test', null)
            """
        )
        conn.execute(
            """
            create table fact_choice_macro_daily (
              series_id varchar,
              series_name varchar,
              trade_date varchar,
              value_numeric double,
              frequency varchar,
              unit varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              quality_flag varchar,
              run_id varchar
            )
            """
        )
        conn.execute(
            """
            create table phase1_macro_vendor_catalog (
              series_id varchar,
              series_name varchar,
              vendor_name varchar,
              vendor_version varchar,
              frequency varchar,
              unit varchar,
              vendor_series_code varchar,
              batch_id varchar,
              catalog_version varchar,
              theme varchar,
              is_core boolean,
              tags_json varchar,
              request_options varchar,
              fetch_mode varchar,
              fetch_granularity varchar,
              refresh_tier varchar,
              policy_note varchar
            )
            """
        )
        conn.execute(
            """
            create table choice_market_snapshot (
              series_id varchar,
              series_name varchar,
              vendor_series_code varchar,
              vendor_name varchar,
              trade_date varchar,
              value_numeric double,
              frequency varchar,
              unit varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              run_id varchar
            )
            """
        )
        conn.execute(
            """
            insert into fact_choice_macro_daily values
              ('cn_cpi_yoy', 'CN CPI YoY', '2026-04-09', 0.7, 'monthly', 'pct',
               'sv_choice', 'vv_choice', 'rv_choice_macro_thin_slice_v1', 'ok', 'choice-run'),
              ('CA.CSI300', 'CSI 300 close', '2026-04-10', 4102.25, 'daily', 'index',
               'sv_tushare_index', 'vv_tushare_index', 'rv_public_cross_asset_headline_v1', 'ok', 'tushare-run'),
              ('CA.CSI500', 'CSI 500 close', '2026-04-10', 6155.8, 'daily', 'index',
               'sv_tushare_csi500_index', 'vv_tushare_csi500_index', 'rv_public_cross_asset_headline_v1', 'ok',
               'tushare-run')
            """
        )
        conn.execute(
            """
            insert into phase1_macro_vendor_catalog values
              ('cn_cpi_yoy', 'CN CPI YoY', 'choice', 'vv_choice', 'monthly', 'pct',
               'EDB_CPI_YOY', 'stable', 'test.choice', 'inflation', true, '[]',
               '{}', 'latest', 'single', 'stable', ''),
              ('CA.CSI300', 'CSI 300 close', 'tushare', 'vv_tushare_index', 'daily', 'index',
               'index_daily:000300.SH.close', 'supplemental', 'test.tushare', 'equity', true, '[]',
               '{}', 'materialized', 'daily', 'supplemental', ''),
              ('CA.CSI500', 'CSI 500 close', 'tushare', 'vv_tushare_csi500_index', 'daily', 'index',
               'index_daily:000905.SH.close', 'supplemental', 'test.tushare', 'equity', true, '[]',
               '{}', 'materialized', 'daily', 'supplemental', '')
            """
        )
        conn.execute(
            """
            insert into choice_market_snapshot values
              ('cn_cpi_yoy', 'CN CPI YoY', 'EDB_CPI_YOY', 'choice', '2026-04-09',
               0.7, 'monthly', 'pct', 'sv_choice', 'vv_choice', 'rv_choice_macro_thin_slice_v1', 'choice-run'),
              ('M001', '公开市场7天逆回购利率', 'M001', 'choice', '2026-04-10',
               1.75, 'daily', '%', 'sv_choice_repo_policy', 'vv_choice_repo_policy',
               'rv_choice_macro_thin_slice_v1', 'choice-run'),
              ('CA.CSI300', 'CSI 300 close', 'index_daily:000300.SH.close', 'tushare', '2026-04-10',
               4102.25, 'daily', 'index', 'sv_tushare_index', 'vv_tushare_index',
               'rv_public_cross_asset_headline_v1', 'tushare-run'),
              ('CA.CSI500', 'CSI 500 close', 'index_daily:000905.SH.close', 'tushare', '2026-04-10',
               6155.8, 'daily', 'index', 'sv_tushare_csi500_index', 'vv_tushare_csi500_index',
               'rv_public_cross_asset_headline_v1', 'tushare-run'),
              ('CA.COPPER', 'Copper main futures close', 'fut_daily:CU.SHF.close', 'tushare', '2026-04-10',
               81234.5, 'daily', 'CNY/t', 'sv_tushare_fut', 'vv_tushare_fut',
               'rv_public_cross_asset_headline_v1', 'tushare-run'),
              ('EMM00166462', 'China treasury yield 5Y', 'EMM00166462', 'choice', '2026-04-10',
               2.34, 'daily', '%', 'sv_choice_yield', 'vv_choice_yield',
               'rv_choice_macro_thin_slice_v1', 'choice-run'),
              ('EMM00166466', 'China treasury yield 10Y', 'E1000180', 'choice', '2026-04-10',
               2.48, 'daily', '%', 'sv_choice_yield', 'vv_choice_yield',
               'rv_choice_macro_thin_slice_v1', 'choice-run'),
              ('CA.DR007', 'DR007', 'repo_rate_query:FDR007', 'choice', '2026-04-10',
               1.82, 'daily', '%', 'sv_choice_repo', 'vv_choice_repo',
               'rv_choice_macro_thin_slice_v1', 'choice-run')
            """
        )
        conn.execute(
            """
            create table fx_daily_mid (
              trade_date date,
              base_currency varchar,
              quote_currency varchar,
              mid_rate decimal(24, 8),
              source_name varchar,
              is_business_day boolean,
              is_carry_forward boolean,
              source_version varchar,
              vendor_name varchar,
              vendor_version varchar,
              vendor_series_code varchar,
              observed_trade_date date
            )
            """
        )
        conn.execute(
            """
            insert into fx_daily_mid values (
              '2026-04-10', 'USD', 'CNY', 7.1234, 'CFETS', true, false,
              'sv_fx_choice', 'choice', 'vv_fx_choice', 'EMM00058124', '2026-04-10'
            )
            """
        )
        conn.execute(
            """
            create table fact_formal_yield_curve_daily (
              trade_date varchar,
              curve_type varchar,
              tenor varchar,
              rate_pct decimal(18, 8),
              vendor_name varchar,
              vendor_version varchar,
              source_version varchar,
              rule_version varchar
            )
            """
        )
        conn.execute(
            """
            insert into fact_formal_yield_curve_daily values (
              '2026-04-10', 'aa_credit', '5Y', 2.91, 'choice',
              'vv_choice_curve', 'sv_choice_curve', 'rv_yield_curve_formal_materialize_v1'
            )
            """
        )
        conn.execute(
            """
            create table std_external_macro_daily (
              series_id varchar not null,
              vendor_name varchar not null,
              domain varchar not null,
              trade_date varchar not null,
              value_numeric double,
              frequency varchar,
              unit varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              ingest_batch_id varchar not null,
              raw_zone_path varchar,
              created_at timestamp not null
            )
            """
        )
        conn.execute(
            """
            create table external_data_catalog (
              series_id varchar primary key,
              series_name varchar not null,
              vendor_name varchar not null,
              source_family varchar not null,
              domain varchar not null,
              frequency varchar,
              unit varchar,
              refresh_tier varchar,
              fetch_mode varchar,
              raw_zone_path varchar,
              standardized_table varchar,
              view_name varchar,
              access_path varchar,
              catalog_version varchar not null,
              created_at timestamp not null
            )
            """
        )
        conn.execute(
            """
            insert into std_external_macro_daily values
              ('tushare.macro.cn_cpi.monthly', 'tushare', 'macro', '2026-04-09',
               0.8, 'monthly', 'pct', 'sv_tushare', 'vv_tushare',
               'm2b.external_std_macro_etl.v1', 'batch-1', 'data/raw/tushare/batch-1/cn_cpi_monthly.json',
               current_timestamp),
              ('tushare.macro.cn_ppi.monthly', 'tushare', 'macro', '2026-04-30',
               -2.3, 'monthly', 'pct', 'sv_tushare', 'vv_tushare',
               'm2b.external_std_macro_etl.v1', 'batch-1', 'data/raw/tushare/batch-1/cn_ppi_monthly.json',
               current_timestamp),
              ('tushare.macro.cn_money.monthly', 'tushare', 'macro', '2026-04-30',
               8.1, 'monthly', 'pct', 'sv_tushare', 'vv_tushare',
               'm2b.external_std_macro_etl.v1', 'batch-1', 'data/raw/tushare/batch-1/cn_money_monthly.json',
               current_timestamp)
            """
        )
        conn.execute(
            """
            insert into external_data_catalog values
              ('tushare.macro.cn_cpi.monthly', 'China CPI YoY (Tushare)', 'tushare',
               'tushare_macro', 'macro', 'monthly', 'pct', 'on_demand', 'seed_register',
               'data/raw/tushare/{ingest_batch_id}/cn_cpi_monthly.json', 'std_external_macro_daily',
               'vw_external_macro_daily',
               'select * from vw_external_macro_daily where series_id = ''tushare.macro.cn_cpi.monthly''',
               'm2b.tushare_macro.v1', current_timestamp),
              ('tushare.macro.cn_ppi.monthly', 'China PPI YoY (Tushare)', 'tushare',
               'tushare_macro', 'macro', 'monthly', 'pct', 'on_demand', 'seed_register',
               'data/raw/tushare/{ingest_batch_id}/cn_ppi_monthly.json', 'std_external_macro_daily',
               'vw_external_macro_daily',
               'select * from vw_external_macro_daily where series_id = ''tushare.macro.cn_ppi.monthly''',
               'm2b.tushare_macro.v1', current_timestamp),
              ('tushare.macro.cn_money.monthly', 'China M2 YoY (Tushare)', 'tushare',
               'tushare_macro', 'macro', 'monthly', 'pct', 'on_demand', 'seed_register',
               'data/raw/tushare/{ingest_batch_id}/cn_money_monthly.json', 'std_external_macro_daily',
               'vw_external_macro_daily',
               'select * from vw_external_macro_daily where series_id = ''tushare.macro.cn_money.monthly''',
               'm2b.tushare_macro.v1', current_timestamp)
            """
        )
    finally:
        conn.close()


def _seed_crisis_score_history(path) -> None:
    conn = duckdb.connect(str(path), read_only=False)
    try:
        start_date = date(2025, 12, 12)
        rows: list[tuple[object, ...]] = []
        for offset in range(120):
            trade_date = (start_date + pd.Timedelta(days=offset)).strftime("%Y-%m-%d")
            stress = max(0.0, (offset - 89) / 30)
            alternating = -1 if offset % 2 else 1
            hs300 = 4100 + offset * 1.5 + alternating * stress * 140
            usdcny = 7.05 + offset * 0.0005 + alternating * stress * 0.08
            nanhua = 980 + offset * 0.8 + alternating * stress * 50
            gov_5y = 2.20 + offset * 0.0005
            aa_5y = gov_5y + 0.48 + stress * 0.80
            dr007 = 1.75 + stress * 0.70
            repo_7d = 1.72
            rows.extend(
                [
                    ("CA.CSI300", "CSI 300 close", trade_date, hs300, "daily", "index"),
                    ("EMM00058124", "USD/CNY spot", trade_date, usdcny, "daily", "CNY/USD"),
                    ("NH0100.NHF", "Nanhua commodity index", trade_date, nanhua, "daily", "index"),
                    ("legacy.yield.choice.treasury.5Y", "China treasury yield 5Y", trade_date, gov_5y, "daily", "%"),
                    ("legacy.yield.choice.aa_credit.5Y", "China AA credit yield 5Y", trade_date, aa_5y, "daily", "%"),
                    ("CA.DR007", "DR007", trade_date, dr007, "daily", "%"),
                    ("M001", "Open market reverse repo 7D", trade_date, repo_7d, "daily", "%"),
                ]
            )
        conn.executemany(
            """
            insert into fact_choice_macro_daily values (
              ?, ?, ?, ?, ?, ?,
              'sv_crisis_score_test', 'vv_choice_crisis_score_test',
              'rv_choice_macro_thin_slice_v1', 'ok', 'crisis-score-test'
            )
            """,
            rows,
        )
    finally:
        conn.close()


def _delete_external_macro_series(path, series_id: str) -> None:
    conn = duckdb.connect(str(path), read_only=False)
    try:
        conn.execute("delete from std_external_macro_daily where series_id = ?", [series_id])
        conn.execute("delete from external_data_catalog where series_id = ?", [series_id])
    finally:
        conn.close()


def _seed_choice_stock_strategy_db(path) -> None:
    conn = duckdb.connect(str(path), read_only=False)
    try:
        conn.execute(
            """
            create table choice_stock_universe (
              as_of_date varchar,
              stock_code varchar,
              stock_name varchar,
              field_key varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              run_id varchar
            )
            """
        )
        conn.execute(
            """
            create table choice_stock_sector_membership (
              as_of_date varchar,
              stock_code varchar,
              sw2021 varchar,
              sw2021code varchar,
              field_key varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              run_id varchar
            )
            """
        )
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar,
              stock_code varchar,
              open_value double,
              high_value double,
              low_value double,
              close_value double,
              volume double,
              amount double,
              pctchange double,
              turn double,
              amplitude double,
              tradestatus varchar,
              highlimit varchar,
              lowlimit varchar,
              field_keys_json varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              run_id varchar
            )
            """
        )
        conn.execute(
            """
            create table choice_stock_limit_quality (
              as_of_date varchar,
              stock_code varchar,
              issurgedlimit varchar,
              isdeclinelimit varchar,
              hlimitedays integer,
              llimitedays integer,
              field_key varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              run_id varchar
            )
            """
        )
        conn.executemany(
            "insert into choice_stock_universe values (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("2026-04-30", "000001.SZ", "Alpha Bank", "a_share_universe_sector_001004", "sv_stock", "vv_stock", "rv_stock", "run-stock"),
                ("2026-04-30", "000002.SZ", "Beta Tech", "a_share_universe_sector_001004", "sv_stock", "vv_stock", "rv_stock", "run-stock"),
                ("2026-04-30", "600000.SH", "Gamma Consumer", "a_share_universe_sector_001004", "sv_stock", "vv_stock", "rv_stock", "run-stock"),
            ],
        )
        conn.executemany(
            "insert into choice_stock_sector_membership values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("2026-04-30", "000001.SZ", "Bank", "801780", "sw2021_industry_membership", "sv_stock", "vv_stock", "rv_stock", "run-stock"),
                ("2026-04-30", "000002.SZ", "Technology", "801750", "sw2021_industry_membership", "sv_stock", "vv_stock", "rv_stock", "run-stock"),
                ("2026-04-30", "600000.SH", "Consumer", "801120", "sw2021_industry_membership", "sv_stock", "vv_stock", "rv_stock", "run-stock"),
            ],
        )
        dates = pd.date_range("2026-01-01", "2026-04-30", freq="D")
        rows = []
        for row_no, trade_date in enumerate(dates):
            for stock_no, stock_code in enumerate(("000001.SZ", "000002.SZ", "600000.SH")):
                close = 10.0 + stock_no * 5.0 + row_no * (0.08 + stock_no * 0.01)
                open_value = close * 0.995
                high_value = close * 1.01
                low_value = close * 0.99
                rows.append(
                    (
                        trade_date.date().isoformat(),
                        stock_code,
                        open_value,
                        high_value,
                        low_value,
                        close,
                        100000.0 + stock_no * 1000,
                        close * 100000.0,
                        0.8 + stock_no * 0.1,
                        1.2 + stock_no * 0.1,
                        2.0,
                        "Trading",
                        str(round(close * 1.1, 4)),
                        str(round(close * 0.9, 4)),
                        "{}",
                        "sv_stock",
                        "vv_stock",
                        "rv_stock",
                        "run-stock",
                    )
                )
        conn.executemany(
            """
            insert into choice_stock_daily_observation values (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            rows,
        )
        conn.executemany(
            "insert into choice_stock_limit_quality values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("2026-04-30", "000001.SZ", "否", "否", 0, 0, "limit_quality", "sv_stock", "vv_stock", "rv_stock", "run-stock"),
                ("2026-04-30", "000002.SZ", "否", "否", 0, 0, "limit_quality", "sv_stock", "vv_stock", "rv_stock", "run-stock"),
                ("2026-04-30", "600000.SH", "否", "否", 0, 0, "limit_quality", "sv_stock", "vv_stock", "rv_stock", "run-stock"),
            ],
        )
    finally:
        conn.close()


def _seed_choice_stock_factor_snapshot(path) -> None:
    conn = duckdb.connect(str(path), read_only=False)
    try:
        conn.execute(
            """
            create table choice_stock_factor_snapshot (
              as_of_date varchar,
              stock_code varchar,
              pe double,
              pb double,
              ps double,
              roe double,
              gross_margin double,
              three_month_return double,
              twelve_month_return double,
              volatility double,
              dividend_yield double,
              industry varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              run_id varchar
            )
            """
        )
        conn.executemany(
            "insert into choice_stock_factor_snapshot values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "2026-04-30",
                    "000001.SZ",
                    8.0,
                    0.8,
                    1.0,
                    0.22,
                    0.45,
                    0.18,
                    0.42,
                    0.16,
                    0.06,
                    "technology",
                    "sv_factor",
                    "vv_factor",
                    "rv_factor",
                    "run-factor",
                ),
                (
                    "2026-04-30",
                    "000002.SZ",
                    18.0,
                    2.2,
                    3.0,
                    0.12,
                    0.30,
                    0.08,
                    0.10,
                    0.25,
                    0.03,
                    "consumer",
                    "sv_factor",
                    "vv_factor",
                    "rv_factor",
                    "run-factor",
                ),
                (
                    "2026-04-30",
                    "600000.SH",
                    12.0,
                    1.5,
                    2.0,
                    0.18,
                    0.38,
                    0.12,
                    0.24,
                    0.20,
                    0.04,
                    "technology",
                    "sv_factor",
                    "vv_factor",
                    "rv_factor",
                    "run-factor",
                ),
            ],
        )
    finally:
        conn.close()
