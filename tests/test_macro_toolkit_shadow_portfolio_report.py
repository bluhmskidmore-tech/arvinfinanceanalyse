from __future__ import annotations

from pathlib import Path

import duckdb
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.routes.macro_toolkit import router as macro_toolkit_router
from backend.app.core_finance.macro.equity_shadow_portfolio import compute_equity_shadow_portfolio_report
from backend.app.governance.settings import get_settings


def test_shadow_portfolio_report_marks_duckdb_busy_when_file_is_locked(
    tmp_path: Path,
    monkeypatch,
) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    duckdb_path.write_bytes(b"placeholder")

    def raise_busy_open(*args: object, **kwargs: object) -> duckdb.DuckDBPyConnection:
        raise duckdb.IOException("IO Error: Cannot open file because another program is using it")

    monkeypatch.setattr(duckdb, "connect", raise_busy_open)

    report = compute_equity_shadow_portfolio_report(duckdb_path)

    assert report["status"] == "unavailable"
    assert "DUCKDB_BUSY" in report["warnings"]
    assert "DUCKDB_OPEN_FAILED: IOException" in report["warnings"]


def test_macro_toolkit_strategy_endpoint_exposes_read_only_shadow_portfolio_report(
    tmp_path: Path,
    monkeypatch,
) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_shadow_report_db(duckdb_path)
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
    body = response.json()
    report = body["result"]["shadow_portfolio_report"]
    assert report["status"] == "complete"
    assert report["basis"] == "read_only_shadow"
    assert report["rule_version"] == "rv_macro_toolkit_shadow_portfolio_v1"
    assert report["completed_periods"] == 2
    assert report["cost_model"]["cost_bps"] == [0, 10, 20, 50]
    assert report["cost_model"]["initial_build_included"] is True
    assert report["cost_model"]["final_liquidation_included"] is False
    assert "READ_ONLY_SHADOW_NOT_PRODUCTION" in report["warnings"]
    assert "SHORT_HISTORY" in report["warnings"]
    assert set(report["tables_used"]) == {
        "choice_stock_daily_observation",
        "choice_stock_factor_snapshot",
    }

    portfolios = {item["key"]: item for item in report["portfolios"]}
    assert set(portfolios) == {
        "current_baseline",
        "deep_value_quality_pe80",
    }
    shadow = portfolios["deep_value_quality_pe80"]
    assert shadow["role"] == "shadow_candidate"
    assert shadow["weights"] == {
        "value": 0.45,
        "quality": 0.25,
        "momentum": 0.05,
        "low_vol": 0.1,
        "dividend": 0.15,
    }
    assert shadow["constraints"]["pe_max"] == 80
    assert shadow["constraints"]["pb_max"] is None
    assert shadow["constraints"]["turnover_cap"] is None
    assert {row["cost_bps"] for row in shadow["cost_results"]} == {0, 10, 20, 50}
    assert all(item["pe"] <= 80 for item in shadow["latest_holdings"])

    assert body["result_meta"]["formal_use_allowed"] is False
    assert "choice_stock_daily_observation" in body["result_meta"]["tables_used"]
    assert "choice_stock_factor_snapshot" in body["result_meta"]["tables_used"]


def test_macro_toolkit_strategy_endpoint_exposes_unavailable_shadow_portfolio_report(
    tmp_path: Path,
    monkeypatch,
) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    duckdb.connect(str(duckdb_path), read_only=False).close()
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
    body = response.json()
    report = body["result"]["shadow_portfolio_report"]
    assert report["status"] == "unavailable"
    assert report["rule_version"] == "rv_macro_toolkit_shadow_portfolio_v1"
    assert "MISSING_TABLES: choice_stock_daily_observation, choice_stock_factor_snapshot" in report["warnings"]
    assert set(report["tables_used"]) == {
        "choice_stock_daily_observation",
        "choice_stock_factor_snapshot",
    }
    assert report["portfolios"] == []


def _seed_shadow_report_db(path: Path) -> None:
    conn = duckdb.connect(str(path), read_only=False)
    try:
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar,
              stock_code varchar,
              close_value double
            )
            """
        )
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
        prices = {
            "2026-05-01": {
                "000001.SZ": 10.0,
                "000002.SZ": 10.0,
                "000003.SZ": 10.0,
                "000004.SZ": 10.0,
            },
            "2026-05-02": {
                "000001.SZ": 11.0,
                "000002.SZ": 9.5,
                "000003.SZ": 10.4,
                "000004.SZ": 9.8,
            },
            "2026-05-03": {
                "000001.SZ": 12.0,
                "000002.SZ": 9.0,
                "000003.SZ": 10.6,
                "000004.SZ": 9.7,
            },
        }
        conn.executemany(
            "insert into choice_stock_daily_observation values (?, ?, ?)",
            [
                (trade_date, stock_code, close_value)
                for trade_date, closes in prices.items()
                for stock_code, close_value in closes.items()
            ],
        )
        factor_rows = []
        for as_of_date in ("2026-05-01", "2026-05-02", "2026-05-03"):
            factor_rows.extend(
                [
                    (
                        as_of_date,
                        "000001.SZ",
                        42.0,
                        4.2,
                        4.0,
                        0.16,
                        0.36,
                        0.42,
                        0.68,
                        0.22,
                        0.02,
                        "Technology",
                        "sv_factor",
                        "vv_factor",
                        "rv_factor",
                        "run-factor",
                    ),
                    (
                        as_of_date,
                        "000002.SZ",
                        9.0,
                        0.8,
                        1.1,
                        0.19,
                        0.42,
                        -0.08,
                        -0.02,
                        0.16,
                        0.05,
                        "Financials",
                        "sv_factor",
                        "vv_factor",
                        "rv_factor",
                        "run-factor",
                    ),
                    (
                        as_of_date,
                        "000003.SZ",
                        130.0,
                        12.0,
                        14.0,
                        0.08,
                        0.32,
                        0.55,
                        0.80,
                        0.35,
                        0.01,
                        "Health Care",
                        "sv_factor",
                        "vv_factor",
                        "rv_factor",
                        "run-factor",
                    ),
                    (
                        as_of_date,
                        "000004.SZ",
                        28.0,
                        3.2,
                        3.0,
                        0.10,
                        0.30,
                        0.12,
                        0.22,
                        0.18,
                        0.03,
                        "Industrials",
                        "sv_factor",
                        "vv_factor",
                        "rv_factor",
                        "run-factor",
                    ),
                ]
            )
        conn.executemany(
            "insert into choice_stock_factor_snapshot values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            factor_rows,
        )
    finally:
        conn.close()
