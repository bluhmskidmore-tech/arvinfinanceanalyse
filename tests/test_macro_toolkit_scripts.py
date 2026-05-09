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
from backend.app.repositories.governance_repo import GovernanceRepository
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
    assert payload["result"]["choice_stock_refresh"]["permission"]["mode"] == "identity_only"
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
        "choice_stock_daily_observation",
        "choice_stock_factor_snapshot",
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
    strategy_summaries = {item["key"]: item for item in payload["result"]["strategy_summaries"]}
    assert set(strategy_summaries) == {
        "moving_average",
        "mean_reversion_momentum",
        "multi_factor_selection",
    }
    assert strategy_summaries["moving_average"]["status"] == "sample_only"
    assert strategy_summaries["multi_factor_selection"]["primary_metric"]["label"] == "样例入选数量"


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
    assert "choice_stock_daily_observation" in payload["result_meta"]["tables_used"]


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
    assert multi_factor["result"]["factor_source"] == "choice_stock_factor_snapshot"
    assert multi_factor["result"]["selected_stock_codes"] == ["000001.SZ"]
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
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_path))
    get_settings.cache_clear()

    route_module = importlib.import_module("backend.app.api.routes.macro_toolkit")
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

    monkeypatch.setattr(route_module, "materialize_choice_stock_inputs", fake_materialize_choice_stock_inputs)
    monkeypatch.setattr(
        route_module,
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
        status_response = client.get(
            "/ui/macro/toolkit/choice-stock/refresh-status",
            params={"run_id": payload["result"]["refresh"]["run_id"]},
        )
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    refresh = payload["result"]["refresh"]
    assert refresh["status"] == "queued"
    assert refresh["trigger_mode"] == "async"
    assert refresh["permission"]["mode"] == "identity_only"
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


def test_macro_toolkit_choice_stock_refresh_rejects_inflight_run(tmp_path, monkeypatch) -> None:
    governance_path = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_path))
    get_settings.cache_clear()
    route_module = importlib.import_module("backend.app.api.routes.macro_toolkit")
    GovernanceRepository(base_dir=governance_path).append(
        route_module.CACHE_BUILD_RUN_STREAM,
        route_module._choice_stock_refresh_run_payload(
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
