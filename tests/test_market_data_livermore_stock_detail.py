from __future__ import annotations

import sys
from datetime import date, timedelta

import duckdb
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from tests.helpers import load_module


def _seed_stock_detail_tables(
    duckdb_path: str,
    *,
    stock_code: str = "000001.SZ",
    end: date = date(2026, 4, 10),
    n_days: int = 5,
) -> None:
    conn = duckdb.connect(duckdb_path, read_only=False)
    try:
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
              source_version varchar,
              vendor_version varchar
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
              roe double,
              dividend_yield double,
              source_version varchar,
              vendor_version varchar
            )
            """
        )
        obs_rows = []
        for i in range(n_days):
            d = (end - timedelta(days=n_days - 1 - i)).isoformat()
            base = 10.0 + i * 0.1
            obs_rows.append(
                (
                    d,
                    stock_code,
                    base,
                    base + 0.2,
                    base - 0.1,
                    base + 0.05,
                    1_000_000.0 + i,
                    10_000_000.0 + i,
                    "sv_choice_stock_obs_test",
                    "vv_choice_stock_test",
                )
            )
        conn.executemany(
            """
            insert into choice_stock_daily_observation
            (trade_date, stock_code, open_value, high_value, low_value, close_value, volume, amount, source_version, vendor_version)
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            obs_rows,
        )
        conn.execute(
            """
            insert into choice_stock_factor_snapshot
            (as_of_date, stock_code, pe, pb, roe, dividend_yield, source_version, vendor_version)
            values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                end.isoformat(),
                stock_code,
                12.5,
                1.8,
                0.11,
                0.025,
                "sv_choice_factor_test",
                "vv_choice_factor_test",
            ),
        )
    finally:
        conn.close()


def _build_client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    monkeypatch.setenv("MOSS_DATA_INPUT_ROOT", str(tmp_path / "data_input"))
    sqlite_path = tmp_path / "auth-scope.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv("MOSS_CHOICE_STOCK_CATALOG_FILE", str(tmp_path / "missing-choice-stock-catalog.json"))
    get_settings.cache_clear()
    for mod in ("backend.app.main", "backend.app.api"):
        sys.modules.pop(mod, None)
    return TestClient(load_module("backend.app.main", "backend/app/main.py").app)


def test_stock_detail_happy_path_sorted_candles_and_factor(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "moss.duckdb"
    _seed_stock_detail_tables(str(db_path))
    client = _build_client(tmp_path, monkeypatch)

    response = client.get(
        "/ui/market-data/livermore/stock-detail",
        params={"stock_code": "000001.SZ", "as_of_date": "2026-04-12", "lookback": 60},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["basis"] == "analytical"
    assert payload["result_meta"]["result_kind"] == "market_data.livermore.stock_detail"
    assert payload["result_meta"]["quality_flag"] == "ok"
    assert "choice_stock_daily_observation" in payload["result_meta"]["tables_used"]

    result = payload["result"]
    assert result["stock_code"] == "000001.SZ"
    candles = result["candles"]
    assert len(candles) == 5
    dates = [c["trade_date"] for c in candles]
    assert dates == sorted(dates)
    assert dates[0] == "2026-04-06"
    assert dates[-1] == "2026-04-10"

    factor = result["factor"]
    assert factor["pe"] == 12.5
    assert factor["pb"] == 1.8
    assert factor["roe"] == 0.11
    assert factor["dividend_yield"] == 0.025
    get_settings.cache_clear()


def test_stock_detail_missing_returns_empty_candles_and_quality_flag(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "moss.duckdb"
    _seed_stock_detail_tables(str(db_path))
    client = _build_client(tmp_path, monkeypatch)

    response = client.get("/ui/market-data/livermore/stock-detail", params={"stock_code": "999999.SZ"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["quality_flag"] == "warning"
    result = payload["result"]
    assert result["state"] == "missing"
    assert result["candles"] == []
    factor = result["factor"]
    assert factor["pe"] is None
    assert factor["pb"] is None
    assert factor["roe"] is None
    assert factor["dividend_yield"] is None
    get_settings.cache_clear()


def test_stock_detail_param_validation(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "moss.duckdb"
    _seed_stock_detail_tables(str(db_path))
    client = _build_client(tmp_path, monkeypatch)

    assert client.get("/ui/market-data/livermore/stock-detail").status_code == 422
    assert (
        client.get(
            "/ui/market-data/livermore/stock-detail",
            params={"stock_code": "000001.SZ", "lookback": 4},
        ).status_code
        == 422
    )
    assert (
        client.get(
            "/ui/market-data/livermore/stock-detail",
            params={"stock_code": "000001.SZ", "lookback": 251},
        ).status_code
        == 422
    )
    assert (
        client.get(
            "/ui/market-data/livermore/stock-detail",
            params={"stock_code": "000001.SZ", "as_of_date": "not-a-date"},
        ).status_code
        == 422
    )
    assert (
        client.get(
            "/ui/market-data/livermore/stock-detail",
            params={"stock_code": "bad code!"},
        ).status_code
        == 422
    )
    get_settings.cache_clear()
