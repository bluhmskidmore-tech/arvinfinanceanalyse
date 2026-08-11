from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import duckdb
import pytest

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
              tradestatus varchar,
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
                    "Trading",
                    "sv_choice_stock_daily_test",
                    "vv_choice_stock_daily_test",
                )
            )
        conn.executemany(
            """
            insert into choice_stock_daily_observation
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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


def test_stock_kline_analysis_uses_trading_rows_for_window_metrics(tmp_path) -> None:
    module = load_module(
        "backend.app.services.stock_kline_analysis_service",
        "backend/app/services/stock_kline_analysis_service.py",
    )
    db_path = tmp_path / "stock-kline-placeholders.duckdb"
    _create_daily_observation_db(str(db_path))
    conn = duckdb.connect(str(db_path))
    try:
        conn.executemany(
            """
            insert into choice_stock_daily_observation
            values (?, '000001.SZ', null, null, null, null, null, null, null, null, null, null, 'sv_placeholder', 'vv_placeholder')
            """,
            [((date(2026, 3, 7) + timedelta(days=i)).isoformat(),) for i in range(10)],
        )
    finally:
        conn.close()

    envelope = module.stock_kline_analysis_envelope(
        duckdb_path=str(db_path),
        stock_code="000001.SZ",
        as_of_date=date(2026, 3, 16),
        lookback=60,
    )

    result = envelope["result"]
    closes = [10.0 + i * 0.05 + 0.03 for i in range(65)]
    closes[-2] = 10.0 + 63 * 0.05 - 0.08
    closes[-1] = 10.0 + 64 * 0.05 + 0.42

    assert envelope["result_meta"]["evidence_rows"] == 60
    assert result["as_of_date"] == "2026-03-06"
    assert result["latest_candle"]["trade_date"] == "2026-03-06"
    assert result["indicators"]["ma20"] == pytest.approx(sum(closes[-20:]) / 20)
    assert result["indicators"]["return_20d"] == pytest.approx(closes[-1] / closes[-21] - 1)
    assert "invalid_ohlc_rows" not in result["validity"]["warnings"]


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


def test_stock_kline_analysis_ignores_null_close_rows_in_tail_metrics(tmp_path) -> None:
    module = load_module(
        "backend.app.services.stock_kline_analysis_service",
        "backend/app/services/stock_kline_analysis_service.py",
    )
    db_path = tmp_path / "stock-kline-null-tail.duckdb"
    _create_daily_observation_db(str(db_path), rows=30)
    conn = duckdb.connect(str(db_path))
    try:
        conn.executemany(
            """
            insert into choice_stock_daily_observation
            values (?, '000001.SZ', null, null, null, null, null, null, null, null, null, 'Trading', 'sv_placeholder', 'vv_placeholder')
            """,
            [((date(2026, 1, 31) + timedelta(days=i)).isoformat(),) for i in range(10)],
        )
        valid_tail_rows: list[tuple[Any, ...]] = []
        for i in range(30, 40):
            trade_date = (date(2026, 2, 10) + timedelta(days=i - 30)).isoformat()
            base = 10.0 + i * 0.05
            open_value = base
            close_value = base + 0.03
            high_value = close_value + 0.08
            low_value = open_value - 0.08
            valid_tail_rows.append(
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
                    "Trading",
                    "sv_choice_stock_daily_test",
                    "vv_choice_stock_daily_test",
                )
            )
        conn.executemany(
            """
            insert into choice_stock_daily_observation
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            valid_tail_rows,
        )
    finally:
        conn.close()

    envelope = module.stock_kline_analysis_envelope(
        duckdb_path=str(db_path),
        stock_code="000001.SZ",
        as_of_date=date(2026, 2, 19),
        lookback=60,
    )

    result = envelope["result"]
    closes = [10.0 + i * 0.05 + 0.03 for i in range(40)]
    closes[28] = 10.0 + 28 * 0.05 - 0.08
    closes[29] = 10.0 + 29 * 0.05 + 0.42

    assert envelope["result_meta"]["evidence_rows"] == 50
    assert result["as_of_date"] == "2026-02-19"
    assert result["latest_candle"]["trade_date"] == "2026-02-19"
    assert result["indicators"]["ma20"] == pytest.approx(sum(closes[-20:]) / 20)
    assert result["indicators"]["return_20d"] == pytest.approx(closes[-1] / closes[-21] - 1)
    assert "invalid_ohlc_rows" in result["validity"]["warnings"]


def test_stock_kline_analysis_normalizes_cross_generation_volume_before_ratio(tmp_path) -> None:
    module = load_module(
        "backend.app.services.stock_kline_analysis_service",
        "backend/app/services/stock_kline_analysis_service.py",
    )
    db_path = tmp_path / "stock-kline-mixed-units.duckdb"
    _create_daily_observation_db(str(db_path), rows=30)
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            update choice_stock_daily_observation
            set volume = volume / 100.0,
                amount = amount / 1000.0,
                vendor_version = 'vv_choice_tushare_stock_20251231'
            where trade_date < (select max(trade_date) from choice_stock_daily_observation)
            """
        )
    finally:
        conn.close()

    envelope = module.stock_kline_analysis_envelope(
        duckdb_path=str(db_path),
        stock_code="000001.SZ",
        as_of_date=date(2026, 1, 30),
        lookback=30,
    )

    expected_average = sum(1_000_000 + i * 1_000 for i in range(9, 29)) / 20
    expected_ratio = (1_000_000 + 29 * 1_000) / expected_average
    result = envelope["result"]
    assert result["state"] == "ok"
    assert result["indicators"]["volume_ratio_20d"] == pytest.approx(expected_ratio)
    assert result["validity"]["liquidity"]["average_volume_20d"] == pytest.approx(
        sum(1_000_000 + i * 1_000 for i in range(10, 30)) / 20
    )


def test_stock_kline_analysis_fails_closed_to_null_when_vendor_column_missing(
    tmp_path,
) -> None:
    module = load_module(
        "backend.app.services.stock_kline_analysis_service",
        "backend/app/services/stock_kline_analysis_service.py",
    )
    db_path = tmp_path / "stock-kline-legacy-schema.duckdb"
    _create_daily_observation_db(str(db_path), rows=30)
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute("alter table choice_stock_daily_observation drop column vendor_version")
    finally:
        conn.close()

    envelope = module.stock_kline_analysis_envelope(
        duckdb_path=str(db_path),
        stock_code="000001.SZ",
        as_of_date=date(2026, 1, 30),
        lookback=30,
    )

    result = envelope["result"]
    assert result["state"] == "ok"
    assert result["latest_candle"]["volume"] is None
    assert result["latest_candle"]["amount"] is None
    assert result["indicators"]["volume_ratio_20d"] is None
    assert "vendor_version_column_missing_null_units" in result["validity"]["warnings"]
    assert envelope["result_meta"]["quality_flag"] == "warning"


def test_stock_kline_analysis_null_vendor_row_propagates_none_with_warning(tmp_path) -> None:
    module = load_module(
        "backend.app.services.stock_kline_analysis_service",
        "backend/app/services/stock_kline_analysis_service.py",
    )
    db_path = tmp_path / "stock-kline-null-vendor-row.duckdb"
    _create_daily_observation_db(str(db_path), rows=30)
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            "update choice_stock_daily_observation set vendor_version = NULL "
            "where trade_date = '2026-01-30'"
        )
    finally:
        conn.close()

    envelope = module.stock_kline_analysis_envelope(
        duckdb_path=str(db_path),
        stock_code="000001.SZ",
        as_of_date=date(2026, 1, 30),
        lookback=30,
    )

    result = envelope["result"]
    assert result["latest_candle"]["volume"] is None
    assert result["latest_candle"]["amount"] is None
    assert "volume_unit_scale_unknown" in result["validity"]["warnings"]
    assert "amount_unit_scale_unknown" in result["validity"]["warnings"]
    assert envelope["result_meta"]["quality_flag"] == "warning"
