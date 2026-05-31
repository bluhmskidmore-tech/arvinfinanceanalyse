from __future__ import annotations

import duckdb
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.routes.macro_toolkit import router as macro_toolkit_router
from backend.app.governance.settings import get_settings
from tests.test_macro_toolkit_scripts import (
    _seed_choice_stock_factor_snapshot,
    _seed_choice_stock_strategy_db,
    _seed_choice_tushare_macro_db,
)


def test_macro_toolkit_uses_latest_factor_snapshot_not_newer_than_price_date(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_choice_tushare_macro_db(duckdb_path)
    _seed_choice_stock_strategy_db(duckdb_path)
    _seed_choice_stock_factor_snapshot(duckdb_path)
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.executemany(
            """
            insert into choice_stock_daily_observation values (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                (
                    "2026-05-06",
                    stock_code,
                    close * 0.995,
                    close * 1.01,
                    close * 0.99,
                    close,
                    100000.0,
                    close * 100000.0,
                    0.5,
                    1.1,
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
                for stock_code, close in {
                    "000001.SZ": 20.0,
                    "000002.SZ": 25.0,
                    "600000.SH": 30.0,
                }.items()
            ],
        )
    finally:
        conn.close()
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
    multi_factor = strategies["multi_factor_selection"]
    assert multi_factor["status"] == "complete"
    assert multi_factor["result"]["as_of_date"] == "2026-05-06"
    assert multi_factor["result"]["factor_as_of_date"] == "2026-04-30"
    assert multi_factor["result"]["factor_date_status"] == "fallback"
    assert "FACTOR_SNAPSHOT_DATE_FALLBACK" in multi_factor["warnings"]
    refresh = payload["result"]["choice_stock_refresh"]
    assert refresh["factor_snapshot"]["reference_date"] == "2026-05-06"
    assert refresh["factor_snapshot"]["stale_days"] == 6
    assert refresh["factor_snapshot"]["fallback_date"] == "2026-04-30"
    assert "choice_stock_factor_snapshot" in payload["result_meta"]["tables_used"]
