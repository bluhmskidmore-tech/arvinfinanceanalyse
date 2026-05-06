from __future__ import annotations

import importlib
import py_compile
import sys

import duckdb
import pandas as pd
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.app.api.routes.macro_toolkit import router as macro_toolkit_router
from backend.app.core_finance.macro.toolkit import get_toolkit_script, iter_toolkit_scripts
from backend.app.core_finance.macro.toolkit.runner import OMITTED_SOURCE_SCRIPTS, SCRIPTS_DIR, TOOLKIT_ROOT
from backend.app.core_finance.macro.toolkit.system_sources import load_series_by_alias, load_system_macro_frame
from backend.app.governance.settings import get_settings
from backend.app.repositories.cffex_member_rank_repo import ensure_cffex_member_rank_schema
from backend.app.services import cffex_member_rank_service


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

    assert {"choice", "tushare"}.issubset(set(frame["vendor_name"]))
    assert hs300["value"].tolist() == [4102.25]
    assert copper["value"].tolist() == [81234.5]
    assert usdcny["value"].tolist() == [7.1234]
    assert treasury_5y["value"].tolist() == [2.34]
    assert credit_aa_5y["value"].tolist() == [2.91]
    get_settings.cache_clear()


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
    assert "signal_aggregator" in scripts
    assert scripts["signal_aggregator"]["available"] is True
    assert payload["result_meta"]["tables_used"] == [
        "fact_choice_macro_daily",
        "choice_market_snapshot",
        "fx_daily_mid",
        "fact_formal_yield_curve_daily",
        "std_external_macro_daily",
        "fact_cffex_member_rank_daily",
        "vw_cffex_member_rank_daily",
    ]


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
    assert payload["result"]["default_data_sources"] == ["choice", "tushare"]
    assert payload["result"]["conclusion"]["stance"]
    assert payload["result"]["coverage"]["hit_count"] >= 6
    assert {item["key"] for item in payload["result"]["signal_cards"]} == {
        "liquidity",
        "risk_appetite",
        "credit",
        "outputs",
    }
    capability_results = {item["key"]: item for item in payload["result"]["capability_results"]}
    assert set(capability_results) == {
        "monetary_policy_stance",
        "yield_curve_shape",
        "credit_spread_risk",
        "leading_indicator",
        "liquidity_stress",
        "cross_market_linkage",
        "rate_turning_point",
        "economic_cycle",
        "macro_portfolio_impact",
        "decision_summary",
    }
    assert capability_results["decision_summary"]["headline"]
    assert capability_results["decision_summary"]["status"] in {"complete", "degraded"}
    indicators = {item["alias"]: item for item in payload["result"]["indicators"]}
    assert indicators["DR007.IB"]["latest_value"] == 1.82
    assert indicators["S0059749"]["latest_value"] == 2.48


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


def test_macro_toolkit_api_runs_scripts_with_project_import_path(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_choice_tushare_macro_db(duckdb_path)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()
    app = FastAPI()
    app.include_router(macro_toolkit_router)
    client = TestClient(app)

    try:
        response = client.post(
            "/ui/macro/toolkit/scripts/debug_wind/run",
            json={"timeout_seconds": 30},
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
               'm2b.tushare_macro.v1', current_timestamp)
            """
        )
    finally:
        conn.close()
