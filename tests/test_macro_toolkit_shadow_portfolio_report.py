from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.app.api.routes.macro_toolkit as macro_toolkit_route
from backend.app.api.routes.macro_toolkit import router as macro_toolkit_router
from backend.app.core_finance.macro import (
    equity_shadow_portfolio as shadow_portfolio_module,
)
from backend.app.core_finance.macro.equity_shadow_portfolio import (
    compute_equity_shadow_portfolio_report,
)
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
    assert shadow["admission"]["status"] == "needs_review"
    assert shadow["admission"]["label"] == "需复核"
    assert shadow["admission"]["summary"] == "保留观察，先补齐验证"
    criteria = {item["key"]: item for item in shadow["admission"]["criteria"]}
    assert criteria["history_length"]["passed"] is False
    assert criteria["history_length"]["actual"] == 2
    assert criteria["history_length"]["threshold"] == ">=12"
    assert criteria["diversification"]["passed"] is True
    assert criteria["diversification"]["threshold"] == ">=15"
    assert criteria["blocking_warnings"]["passed"] is False

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


def test_shadow_portfolio_batches_period_return_loads(
    tmp_path: Path,
    monkeypatch,
) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_shadow_report_db(duckdb_path)
    real_connect = duckdb.connect
    query_counts = {"daily_observation": 0}

    class CountingConnection:
        def __init__(self, inner: duckdb.DuckDBPyConnection) -> None:
            self._inner = inner

        def execute(self, query: str, parameters: object | None = None) -> duckdb.DuckDBPyConnection:
            if "choice_stock_daily_observation" in query:
                query_counts["daily_observation"] += 1
            if parameters is None:
                return self._inner.execute(query)
            return self._inner.execute(query, parameters)

        def close(self) -> None:
            self._inner.close()

        def __getattr__(self, name: str) -> object:
            return getattr(self._inner, name)

    def counting_connect(*args: object, **kwargs: object) -> CountingConnection:
        return CountingConnection(real_connect(*args, **kwargs))

    monkeypatch.setattr(duckdb, "connect", counting_connect)

    report = compute_equity_shadow_portfolio_report(duckdb_path)

    assert report["status"] == "complete"
    assert report["completed_periods"] > 1
    assert query_counts["daily_observation"] == 1


def test_shadow_portfolio_batches_factor_snapshot_history_loads(
    tmp_path: Path,
    monkeypatch,
) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_shadow_report_db(duckdb_path)
    real_connect = duckdb.connect
    query_counts = {"factor_snapshot_history": 0}

    class CountingConnection:
        def __init__(self, inner: duckdb.DuckDBPyConnection) -> None:
            self._inner = inner

        def execute(self, query: str, parameters: object | None = None) -> duckdb.DuckDBPyConnection:
            normalized = " ".join(query.casefold().split())
            if (
                "from choice_stock_factor_snapshot" in normalized
                and "stock_code" in normalized
                and "pe" in normalized
            ):
                query_counts["factor_snapshot_history"] += 1
            if parameters is None:
                return self._inner.execute(query)
            return self._inner.execute(query, parameters)

        def close(self) -> None:
            self._inner.close()

        def __getattr__(self, name: str) -> object:
            return getattr(self._inner, name)

    def counting_connect(*args: object, **kwargs: object) -> CountingConnection:
        return CountingConnection(real_connect(*args, **kwargs))

    monkeypatch.setattr(duckdb, "connect", counting_connect)

    report = compute_equity_shadow_portfolio_report(duckdb_path)

    assert report["status"] == "complete"
    assert query_counts["factor_snapshot_history"] == 1


def test_shadow_portfolio_reuses_preloaded_latest_factor_snapshot_without_changing_report(
    tmp_path: Path,
    monkeypatch,
) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_shadow_report_db(duckdb_path)
    expected = compute_equity_shadow_portfolio_report(duckdb_path)
    latest_snapshot = macro_toolkit_route._load_equity_strategy_factor_snapshot(duckdb_path, "2026-05-03")
    assert latest_snapshot is not None
    loaded_factor_dates: list[str] = []
    real_load_factor_snapshot = shadow_portfolio_module._load_factor_snapshot

    def counting_load_factor_snapshot(
        conn: duckdb.DuckDBPyConnection,
        as_of_date: str,
    ) -> pd.DataFrame:
        loaded_factor_dates.append(as_of_date)
        return real_load_factor_snapshot(conn, as_of_date)

    monkeypatch.setattr(shadow_portfolio_module, "_load_factor_snapshot", counting_load_factor_snapshot)

    report = compute_equity_shadow_portfolio_report(
        duckdb_path,
        latest_factor_snapshot=latest_snapshot,
    )

    assert report == expected
    assert "2026-05-03" not in loaded_factor_dates


def test_shadow_ranked_candidate_pool_matches_full_selection() -> None:
    frame = _shadow_factor_frame(row_count=120)

    full_ranked = shadow_portfolio_module._ranked_frame(
        frame,
        shadow_portfolio_module.DEFAULT_FACTOR_WEIGHTS,
    )
    full_selected = shadow_portfolio_module._select_with_caps(
        full_ranked,
        previous_codes=None,
        turnover_cap=None,
    )

    pooled_ranked = shadow_portfolio_module._ranked_frame(
        frame,
        shadow_portfolio_module.DEFAULT_FACTOR_WEIGHTS,
        candidate_pool_only=True,
    )
    pooled_selected = shadow_portfolio_module._select_with_caps(
        pooled_ranked,
        previous_codes=None,
        turnover_cap=None,
    )

    assert len(pooled_ranked) == max(int(len(frame) * shadow_portfolio_module.TOP_PCT), 1)
    assert pooled_selected.index.tolist() == full_selected.index.tolist()


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
        stock_codes = [f"{idx:06d}.SZ" for idx in range(1, 181)]
        trade_dates = ("2026-05-01", "2026-05-02", "2026-05-03")
        prices = {
            trade_date: {
                stock_code: round((10.0 + (idx % 40) * 0.2) * (1 + date_idx * (0.004 + (idx % 7) * 0.001)), 6)
                for idx, stock_code in enumerate(stock_codes, start=1)
            }
            for date_idx, trade_date in enumerate(trade_dates)
        }
        conn.executemany(
            "insert into choice_stock_daily_observation values (?, ?, ?)",
            [
                (trade_date, stock_code, close_value)
                for trade_date, closes in prices.items()
                for stock_code, close_value in closes.items()
            ],
        )
        industries = (
            "Technology",
            "Financials",
            "Health Care",
            "Industrials",
            "Consumer",
            "Materials",
            "Energy",
            "Utilities",
            "Telecom",
            "Real Estate",
            "Media",
            "Transport",
            "Agriculture",
            "Defense",
            "Pharma",
            "Retail",
            "Auto",
            "Semiconductor",
        )
        factor_rows = []
        for as_of_date in trade_dates:
            for idx, stock_code in enumerate(stock_codes, start=1):
                factor_rows.append(
                    (
                        as_of_date,
                        stock_code,
                        8.0 + (idx % 60),
                        0.8 + (idx % 30) * 0.05,
                        1.0 + (idx % 25) * 0.08,
                        0.08 + (idx % 25) * 0.005,
                        0.25 + (idx % 20) * 0.006,
                        -0.05 + (idx % 40) * 0.006,
                        -0.10 + (idx % 60) * 0.008,
                        0.12 + (idx % 15) * 0.01,
                        0.01 + (idx % 10) * 0.004,
                        industries[idx % len(industries)],
                        "sv_factor",
                        "vv_factor",
                        "rv_factor",
                        "run-factor",
                    )
                )
        conn.executemany(
            "insert into choice_stock_factor_snapshot values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            factor_rows,
        )
    finally:
        conn.close()


def _shadow_factor_frame(*, row_count: int) -> pd.DataFrame:
    industries = ["Technology", "Financials", "Health Care", "Industrials", "Consumer", "Materials"]
    rows = []
    for idx in range(row_count):
        rows.append(
            {
                "stock_code": f"{idx + 1:06d}.SZ",
                "pe": 8.0 + (idx % 37) * 0.7,
                "pb": 0.8 + (idx % 29) * 0.03,
                "ps": 1.0 + (idx % 31) * 0.04,
                "roe": 0.05 + (idx % 23) * 0.006,
                "gross_margin": 0.20 + (idx % 19) * 0.009,
                "three_month_return": -0.08 + idx * 0.0017,
                "twelve_month_return": -0.15 + idx * 0.0023,
                "volatility": 0.12 + (idx % 17) * 0.007,
                "dividend_yield": 0.01 + (idx % 13) * 0.002,
                "industry": industries[idx % len(industries)],
            }
        )
    return pd.DataFrame(rows).set_index("stock_code")
