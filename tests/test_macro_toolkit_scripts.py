from __future__ import annotations

import importlib
import importlib.util
import inspect
import py_compile
import sys
import time
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pandas as pd
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
    pd.testing.assert_frame_equal(score, legacy_score, check_exact=False, check_freq=False, rtol=1e-12, atol=1e-12)

    latest_score = float(legacy_score["crisis_score"].dropna().iloc[-1])
    payload = compute_crisis_score_payload(series_data, report_date=dates[-1].date())
    assert payload["data_status"] == "complete"
    assert payload["available_component_count"] == 5
    assert payload["warnings"] == []
    assert payload["crisis_score"] == round(latest_score, 4)
    assert payload["regime"] == legacy.classify_regime(latest_score)[0]
    for sample_score in (-0.1, 0.5, 1.5, 2.5, 3.5):
        assert classify_crisis_score(sample_score)[0] == legacy.classify_regime(sample_score)[0]


def test_system_choice_tushare_source_layer_reads_default_duckdb(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_choice_tushare_macro_db(duckdb_path)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()

    frame = load_system_macro_frame()
    hs300 = load_series_by_alias("sh000300")
    copper = load_series_by_alias("CU0")
    usdcny = load_series_by_alias("M0067855")
    treasury_5y = load_series_by_alias("S0059747")
    credit_aa_5y = load_series_by_alias("S0059760")
    policy_rate = load_series_by_alias("M0041653")
    ppi = load_series_by_alias("M0001227")
    m2 = load_series_by_alias("M0001385")

    assert {"choice", "tushare"}.issubset(set(frame["vendor_name"]))
    assert hs300["value"].tolist() == [4102.25]
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


def test_series_alias_lookup_reuses_system_frame_until_duckdb_file_changes(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_choice_tushare_macro_db(duckdb_path)
    original_load_system_macro_frame = system_sources.load_system_macro_frame
    calls: list[object] = []

    def spy_load_system_macro_frame(duckdb_path_arg=None):
        calls.append(duckdb_path_arg)
        return original_load_system_macro_frame(duckdb_path_arg)

    monkeypatch.setattr(system_sources, "load_system_macro_frame", spy_load_system_macro_frame)

    hs300 = load_series_by_alias("sh000300", duckdb_path=duckdb_path)
    copper = load_series_by_alias("CU0", duckdb_path=duckdb_path)

    assert hs300["value"].tolist() == [4102.25]
    assert copper["value"].tolist() == [81234.5]
    assert len(calls) == 1

    time.sleep(0.01)
    duckdb_path.touch()
    usdcny = load_series_by_alias("M0067855", duckdb_path=duckdb_path)

    assert usdcny["value"].tolist() == [7.1234]
    assert len(calls) == 2

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
    assert len(calls) == 3


def test_series_alias_lookup_uses_positional_rows_for_cached_alias_index(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_choice_tushare_macro_db(duckdb_path)
    original_load_system_macro_frame = system_sources.load_system_macro_frame
    calls: list[object] = []

    def load_system_macro_frame_with_shifted_index(duckdb_path_arg=None):
        calls.append(duckdb_path_arg)
        frame = original_load_system_macro_frame(duckdb_path_arg)
        frame.index = pd.RangeIndex(start=10, stop=10 + len(frame))
        return frame

    monkeypatch.setattr(system_sources, "load_system_macro_frame", load_system_macro_frame_with_shifted_index)

    hs300 = load_series_by_alias("sh000300", duckdb_path=duckdb_path)
    copper = load_series_by_alias("CU0", duckdb_path=duckdb_path)

    assert hs300["value"].tolist() == [4102.25]
    assert copper["value"].tolist() == [81234.5]
    assert len(calls) == 1


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

    response = client.get("/ui/macro/toolkit/scripts")

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


def test_macro_toolkit_scripts_surfaces_empty_commodity_futures_status(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()
    app = FastAPI()
    app.include_router(macro_toolkit_router)
    client = TestClient(app)

    missing_response = client.get("/ui/macro/toolkit/scripts")
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

    empty_response = client.get("/ui/macro/toolkit/scripts")
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
    assert data_health["capability_results"] == {
        "complete": 0,
        "degraded": 5,
        "unavailable": 6,
        "total_count": 11,
        "deferred": False,
    }
    assert data_health["capability_plan"] == {
        "ready_count": 4,
        "wired_count": 11,
        "total_count": 11,
        "deferred": False,
    }
    assert data_health["warnings"] == []
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
            if "max(try_cast(trade_date as date))" in normalized:
                return FakeResult(row=(dates[-1].date(),))
            if "latest_sample" in normalized and "choice_stock_daily_observation" in normalized:
                return FakeResult(frame=price_rows)
            raise AssertionError(f"unexpected query: {query}")

        def close(self) -> None:
            pass

    monkeypatch.setattr(macro_toolkit_route.duckdb, "connect", lambda *_args, **_kwargs: FakeConnection())
    monkeypatch.setattr(macro_toolkit_route, "_load_equity_strategy_factor_snapshot", lambda *_args, **_kwargs: None)

    context = macro_toolkit_route._load_equity_strategy_price_context(duckdb_path)

    assert context is not None
    assert price_query_used_df is True
    assert context["prices"].shape == (90, 2)
    assert len(context["observations"]) == len(price_rows)


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
        conn.execute(
            """
            insert into fact_commodity_futures_daily (
              trade_date, product_code, contract_code, exchange,
              open_value, high_value, low_value, close_value, settle_value,
              volume, open_interest, source_version, vendor_version, rule_version
            ) values
              ('2026-04-10', 'RB', 'RB2605.SHF', 'SHF',
               null, null, null, 3588.0, null,
               1000, 2000, 'sv_tushare_fut_daily_rb', 'vv_tushare_fut_daily_RB_SHF_20260410',
               'rv_commodity_daily_v1'),
              ('2026-04-10', 'I', 'I2605.DCE', 'DCE',
               null, null, null, 812.5, null,
               1000, 2000, 'sv_tushare_fut_daily_i', 'vv_tushare_fut_daily_I_DCE_20260410',
               'rv_commodity_daily_v1'),
              ('2026-04-10', 'CU', 'CU2605.SHF', 'SHF',
               null, null, null, 81234.5, null,
               1000, 2000, 'sv_tushare_fut_daily_cu', 'vv_tushare_fut_daily_CU_SHF_20260410',
               'rv_commodity_daily_v1'),
              ('2026-04-10', 'AL', 'AL2605.SHF', 'SHF',
               null, null, null, 19876.0, null,
               1000, 2000, 'sv_tushare_fut_daily_al', 'vv_tushare_fut_daily_AL_SHF_20260410',
               'rv_commodity_daily_v1'),
              ('2026-04-10', 'SC', 'SC2605.INE', 'INE',
               null, null, null, 612.3, null,
               1000, 2000, 'sv_tushare_fut_daily_sc', 'vv_tushare_fut_daily_SC_INE_20260410',
               'rv_commodity_daily_v1'),
              ('2026-04-10', 'AU', 'AU2605.SHF', 'SHF',
               null, null, null, 548.2, null,
               1000, 2000, 'sv_tushare_fut_daily_au', 'vv_tushare_fut_daily_AU_SHF_20260410',
               'rv_commodity_daily_v1')
            """
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
    assert load_series_by_alias("SC0.INE", duckdb_path=duckdb_path)["series_id"].tolist() == ["COMMODITY.SC"]
    assert items["copper"]["available"] is True
    assert items["copper"]["aliases"] == ["CU0", "CU0.SHF"]
    assert items["copper"]["matched_alias"] == "CU0"
    assert items["copper"]["role"] == "supplemental_observation"
    assert items["copper"]["used_in_formula"] is False
    assert items["copper"]["report_date"] == "2026-04-10"
    assert items["copper"]["date_alignment_status"] == "aligned"
    assert items["copper"]["series_id"] == "CA.COPPER"
    assert items["copper"]["source"] == "tushare"
    assert items["copper"]["latest_date"] == "2026-04-10"
    assert items["copper"]["row_count"] == 1
    assert items["copper"]["value"] == 81234.5
    assert items["crude_oil"]["series_id"] == "COMMODITY.SC"
    assert items["gold"]["series_id"] == "COMMODITY.AU"
    assert crisis["result"]["available_component_count"] == 5
    assert crisis["result"]["component_count"] == 5


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
    UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}").grant_scope(
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
                "factor_max_stock_count": None,
            },
            headers={"X-User-Id": "stock-refresh-user"},
        )
        payload = response.json()
        status_response = _wait_for_choice_stock_refresh_status(
            client,
            run_id=payload["result"]["refresh"]["run_id"],
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

    def fake_backfill_macro_series(**kwargs: object) -> dict[str, object]:
        calls.append(dict(kwargs))
        return {
            "dry_run": False,
            "processed_count": 1,
            "total_added": 42,
            "results": {"SHIBOR:3M": 42},
            "errors": {},
        }

    monkeypatch.setattr(macro_toolkit_route, "backfill_macro_series", fake_backfill_macro_series)
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
    get_settings.cache_clear()


def test_macro_toolkit_commodity_futures_refresh_requires_scope_and_runs_ingest(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    sqlite_path = tmp_path / "auth-scope.db"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    calls: list[dict[str, object]] = []

    def fake_run_commodity_daily_ingest(**kwargs: object) -> dict[str, object]:
        calls.append(dict(kwargs))
        return {
            "status": "completed",
            "dry_run": False,
            "start_date": "2026-05-01",
            "end_date": "2026-06-01",
            "product_count": 3,
            "row_count": 66,
            "products": [
                {"product_code": "RB", "row_count": 22, "vendor": "tushare"},
                {"product_code": "CU", "row_count": 22, "vendor": "tushare"},
                {"product_code": "SC", "row_count": 22, "vendor": "tushare"},
            ],
            "rule_version": "rv_commodity_daily_v1",
            "table": "fact_commodity_futures_daily",
        }

    monkeypatch.setattr(macro_toolkit_route, "run_commodity_daily_ingest", fake_run_commodity_daily_ingest)
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
    assert refresh["status"] == "completed"
    assert refresh["row_count"] == 66
    assert refresh["product_count"] == 3
    assert refresh["products"][0]["product_code"] == "RB"
    assert refresh["table"] == "fact_commodity_futures_daily"
    assert refresh["permission"]["resource"] == "macro_toolkit.commodity_futures"
    assert refresh["permission"]["actions"] == ["dry_run", "refresh"]
    assert payload["result"]["commodity_futures_refresh"]["permission"] == refresh["permission"]
    assert payload["result_meta"]["result_kind"] == "macro_toolkit.commodity_futures_refresh"
    assert calls == [
        {
            "start_date": "2026-05-01",
            "end_date": "2026-06-01",
            "duckdb_path": str(duckdb_path),
            "products": ("RB", "CU", "SC"),
            "dry_run": False,
        }
    ]
    get_settings.cache_clear()


def test_macro_toolkit_commodity_futures_refresh_returns_after_refresh_health_summary(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    sqlite_path = tmp_path / "auth-scope.db"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    observed_statuses = [
        {
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
        },
        {
            "materialized": True,
            "status": "ok",
            "table": "fact_commodity_futures_daily",
            "row_count": 154,
            "latest_trade_date": "2026-06-01",
            "source_vendors": ["tushare"],
            "coverage": {
                "target_product_count": 7,
                "available_product_count": 7,
                "available_products": ["RB", "I", "CU", "AL", "SC", "AU", "NHCI"],
                "missing_products": [],
            },
            "nanhua_input": {
                "status": "hit",
                "product_code": "NHCI",
                "series_id": "NH0100.NHF",
                "system_series_id": "NHCI.NH",
                "latest_trade_date": "2026-06-01",
                "latest_value": 3187.42,
                "row_count": 22,
                "source_version": "sv_tushare_index_daily_nhci_new",
                "vendor_version": "vv_tushare_index_daily_NHCI_20260601",
                "rule_version": "rv_commodity_daily_v1",
            },
        },
    ]

    def fake_commodity_status(_duckdb_path: object) -> dict[str, object]:
        return observed_statuses.pop(0)

    def fake_run_commodity_daily_ingest(**kwargs: object) -> dict[str, object]:
        assert kwargs["dry_run"] is False
        return {
            "status": "completed",
            "dry_run": False,
            "start_date": "2026-05-01",
            "end_date": "2026-06-01",
            "product_count": 7,
            "row_count": 154,
            "products": [
                {"product_code": "RB", "row_count": 22, "vendor": "tushare", "latest_date": "2026-06-01"},
                {"product_code": "I", "row_count": 22, "vendor": "tushare", "latest_date": "2026-06-01"},
                {"product_code": "NHCI", "row_count": 22, "vendor": "tushare", "latest_date": "2026-06-01", "latest_value": 3187.42, "series_id": "NHCI.NH"},
            ],
            "rule_version": "rv_commodity_daily_v1",
            "table": "fact_commodity_futures_daily",
        }

    monkeypatch.setattr(macro_toolkit_route, "_commodity_futures_status", fake_commodity_status)
    monkeypatch.setattr(macro_toolkit_route, "run_commodity_daily_ingest", fake_run_commodity_daily_ingest)
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
    assert refresh["before_status"]["latest_trade_date"] == "2026-05-20"
    assert refresh["after_status"]["latest_trade_date"] == "2026-06-01"
    assert refresh["summary"] == {
        "table": "fact_commodity_futures_daily",
        "row_count_before": 120,
        "row_count_after": 154,
        "row_count_delta": 34,
        "latest_trade_date_before": "2026-05-20",
        "latest_trade_date_after": "2026-06-01",
        "available_product_count_before": 5,
        "available_product_count_after": 7,
        "target_product_count": 7,
        "newly_available_products": ["RB", "I"],
        "missing_products_after": [],
        "nanhua_status_before": "hit",
        "nanhua_status_after": "hit",
        "nanhua_latest_date_before": "2026-05-20",
        "nanhua_latest_date_after": "2026-06-01",
        "nanhua_latest_value_after": 3187.42,
        "source_vendors_after": ["tushare"],
        "dry_run": False,
    }
    assert payload["commodity_futures_refresh"]["status"]["latest_trade_date"] == "2026-06-01"
    assert payload["commodity_futures_refresh"]["refresh"]["summary"]["row_count_delta"] == 34
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
    monkeypatch.setattr(macro_toolkit_route, "run_commodity_daily_ingest", fake_run_commodity_daily_ingest)
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

    monkeypatch.setattr(macro_toolkit_route, "run_commodity_daily_ingest", fake_run_commodity_daily_ingest)
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

    monkeypatch.setattr(macro_toolkit_route, "run_commodity_daily_ingest", fake_run_commodity_daily_ingest)
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
    timeout_seconds: float = 5.0,
):
    deadline = time.monotonic() + timeout_seconds
    last_response = None
    while time.monotonic() < deadline:
        last_response = client.get(
            "/ui/macro/toolkit/choice-stock/refresh-status",
            params={"run_id": run_id},
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
               'sv_tushare_index', 'vv_tushare_index', 'rv_public_cross_asset_headline_v1', 'ok', 'tushare-run')
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
