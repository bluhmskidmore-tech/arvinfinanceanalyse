from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import duckdb

from tests.helpers import load_module


def _create_daily_observation_db(path: str, *, rows: int = 65) -> None:
    conn = duckdb.connect(path)
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
              pctchange double,
              turn double,
              amplitude double,
              source_version varchar,
              vendor_version varchar
            )
            """
        )
        start = date(2026, 1, 1)
        payload: list[tuple[Any, ...]] = []
        for i in range(rows):
            trade_date = (start + timedelta(days=i)).isoformat()
            base = 10.0 + i * 0.05
            open_value = base
            close_value = base + 0.03
            high_value = close_value + 0.08
            low_value = open_value - 0.08
            if i == rows - 2:
                open_value = base + 0.25
                close_value = base - 0.08
                high_value = open_value + 0.05
                low_value = close_value - 0.05
            if i == rows - 1:
                open_value = base - 0.16
                close_value = base + 0.42
                high_value = close_value + 0.05
                low_value = open_value - 0.05
            payload.append(
                (
                    trade_date,
                    "000001.SZ",
                    open_value,
                    high_value,
                    low_value,
                    close_value,
                    1_000_000 + i * 1_000,
                    (1_000_000 + i * 1_000) * close_value,
                    0.5,
                    1.2,
                    2.0,
                    "sv_choice_stock_daily_test",
                    "vv_choice_stock_daily_test",
                )
            )
        conn.executemany(
            """
            insert into choice_stock_daily_observation
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            payload,
        )
    finally:
        conn.close()


def test_stock_kline_analysis_envelope_scores_ohlcv_observation(tmp_path) -> None:
    module = load_module(
        "backend.app.services.stock_kline_analysis_service",
        "backend/app/services/stock_kline_analysis_service.py",
    )
    db_path = tmp_path / "stock-kline.duckdb"
    _create_daily_observation_db(str(db_path))

    envelope = module.stock_kline_analysis_envelope(
        duckdb_path=str(db_path),
        stock_code="000001.SZ",
        as_of_date=date(2026, 3, 10),
        lookback=65,
    )

    meta = envelope["result_meta"]
    result = envelope["result"]

    assert meta["result_kind"] == "market_data.stock_analysis.kline"
    assert meta["basis"] == "analytical"
    assert meta["formal_use_allowed"] is False
    assert meta["source_version"] == "sv_choice_stock_daily_test"
    assert meta["vendor_version"] == "vv_choice_stock_daily_test"
    assert meta["tables_used"] == ["choice_stock_daily_observation"]
    assert meta["evidence_rows"] == 65

    assert result["state"] == "ok"
    assert result["contract_status"] == "observational_only"
    assert result["formal_use_allowed"] is False
    assert result["trading_instruction_allowed"] is False
    assert result["stock_code"] == "000001.SZ"
    assert result["validity"]["usable"] is True
    assert result["observation_signal"]["level"] == "constructive_watch"
    assert result["observation_signal"]["score"] >= 70
    assert {item["key"] for item in result["patterns"]} >= {"bullish_engulfing", "wide_body"}


def test_stock_kline_analysis_missing_db_keeps_observational_boundary(tmp_path) -> None:
    module = load_module(
        "backend.app.services.stock_kline_analysis_service",
        "backend/app/services/stock_kline_analysis_service.py",
    )

    envelope = module.stock_kline_analysis_envelope(
        duckdb_path=str(tmp_path / "missing.duckdb"),
        stock_code="000001.SZ",
        as_of_date=None,
        lookback=60,
    )

    meta = envelope["result_meta"]
    result = envelope["result"]

    assert meta["quality_flag"] == "warning"
    assert meta["evidence_rows"] == 0
    assert result["state"] == "missing"
    assert result["validity"]["usable"] is False
    assert result["observation_signal"]["level"] == "not_applicable"
    assert result["observation_signal"]["risks"] == ["duckdb_missing"]
