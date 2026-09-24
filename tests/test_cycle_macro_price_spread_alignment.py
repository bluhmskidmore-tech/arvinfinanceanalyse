from __future__ import annotations

from datetime import date

import duckdb

from backend.app.services.market_data_livermore_service import (
    _load_cycle_input_evidence,
)


def _create_macro_daily_table(conn: duckdb.DuckDBPyConnection) -> None:
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


def test_price_spread_is_missing_when_pe_and_cn10y_have_no_shared_trade_date(tmp_path) -> None:
    """PE landed on a different trading day than CN10Y must not be blended into one spread."""
    db_path = tmp_path / "macro.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        _create_macro_daily_table(conn)
        conn.executemany(
            "insert into fact_choice_macro_daily values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "CA.CSI300_PE",
                    "CSI300 PE",
                    "2026-05-08",
                    14.0,
                    "daily",
                    "x",
                    "sv_pe",
                    "vv_pe",
                    "rv_pe",
                    "ok",
                    "run-pe",
                ),
                (
                    "EMM00166466",
                    "China 10Y yield",
                    "2026-05-07",
                    2.1,
                    "daily",
                    "%",
                    "sv_y",
                    "vv_y",
                    "rv_y",
                    "ok",
                    "run-y",
                ),
            ],
        )
    finally:
        conn.close()

    evidence = _load_cycle_input_evidence(duckdb_path=str(db_path), as_of_date=date(2026, 5, 8))

    assert evidence.price_spread_ready is False
    assert evidence.macro_snapshot is not None
    assert evidence.macro_snapshot.price_spread_ready is False
    assert "price_spread" in evidence.macro_snapshot.missing_inputs


def test_price_spread_falls_back_to_latest_shared_trade_date(tmp_path) -> None:
    """When the very latest points differ, reuse the latest date landed in both series instead of dropping it."""
    db_path = tmp_path / "macro.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        _create_macro_daily_table(conn)
        conn.executemany(
            "insert into fact_choice_macro_daily values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "CA.CSI300_PE",
                    "CSI300 PE",
                    "2026-05-07",
                    14.2,
                    "daily",
                    "x",
                    "sv_pe",
                    "vv_pe",
                    "rv_pe",
                    "ok",
                    "run-pe-1",
                ),
                (
                    "CA.CSI300_PE",
                    "CSI300 PE",
                    "2026-05-08",
                    14.0,
                    "daily",
                    "x",
                    "sv_pe",
                    "vv_pe",
                    "rv_pe",
                    "ok",
                    "run-pe-2",
                ),
                (
                    "EMM00166466",
                    "China 10Y yield",
                    "2026-05-07",
                    2.05,
                    "daily",
                    "%",
                    "sv_y",
                    "vv_y",
                    "rv_y",
                    "ok",
                    "run-y",
                ),
            ],
        )
    finally:
        conn.close()

    evidence = _load_cycle_input_evidence(duckdb_path=str(db_path), as_of_date=date(2026, 5, 8))

    assert evidence.price_spread_ready is True
    assert evidence.macro_snapshot is not None
    lineage = evidence.macro_snapshot.lineage["price_spread"]
    assert lineage["pe"] == 14.2
    assert lineage["cn10y"] == 2.05
    assert "2026-05-07" in evidence.price_spread_evidence
