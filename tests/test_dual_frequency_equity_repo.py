from __future__ import annotations

from pathlib import Path

import duckdb

from backend.app.repositories.dual_frequency_equity_repo import (
    load_dual_frequency_equity_history,
)


def _seed_full_history(path: Path) -> None:
    conn = duckdb.connect(str(path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_choice_macro_daily (
              series_id varchar,
              trade_date varchar,
              value_numeric double,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              quality_flag varchar,
              run_id varchar
            )
            """
        )
        conn.executemany(
            """
            insert into fact_choice_macro_daily values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "CA.CSI300",
                    "2026-01-02",
                    100.0,
                    "index-source-v1",
                    "index-vendor-v1",
                    "index-rule-v1",
                    "ok",
                    "index:20260102T010000Z",
                ),
                (
                    "CA.CSI300",
                    "2026-01-05",
                    999.0,
                    "index-source-old",
                    "index-vendor-old",
                    "index-rule-old",
                    "ok",
                    "index:20260105T000000Z",
                ),
                (
                    "CA.CSI300",
                    "2026-01-05",
                    102.0,
                    "index-source-v2",
                    "index-vendor-v2",
                    "index-rule-v2",
                    "ok",
                    "index:20260105T010000Z",
                ),
                (
                    "CA.CSI300",
                    "2026-01-06",
                    104.0,
                    "index-source-v2",
                    "index-vendor-v2",
                    "index-rule-v2",
                    "ok",
                    "index:20260106T010000Z",
                ),
                (
                    "CA.CSI300",
                    "2026-01-07",
                    106.0,
                    "index-source-v2",
                    "index-vendor-v2",
                    "index-rule-v2",
                    "ok",
                    "index:20260107T010000Z",
                ),
                (
                    "OTHER",
                    "2026-01-07",
                    1.0,
                    "other-source",
                    "other-vendor",
                    "other-rule",
                    "ok",
                    "other:20260107T010000Z",
                ),
            ],
        )
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar,
              stock_code varchar,
              amount double,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              run_id varchar
            )
            """
        )
        stock_rows: list[tuple[object, ...]] = []
        for trade_date, first_amount, second_amount in [
            ("2026-01-02", 10.0, 20.0),
            ("2026-01-05", 100.0, 200.0),
            ("2026-01-06", 300.0, 400.0),
            ("2026-01-07", 500.0, 600.0),
        ]:
            stock_rows.extend(
                [
                    (
                        trade_date,
                        "000001.SZ",
                        first_amount,
                        "stock-source-v2",
                        "stock-vendor-v2",
                        "stock-rule-v2",
                        f"stock:{trade_date.replace('-', '')}T010000Z",
                    ),
                    (
                        trade_date,
                        "000002.SZ",
                        second_amount,
                        "stock-source-v2",
                        "stock-vendor-v2",
                        "stock-rule-v2",
                        f"stock:{trade_date.replace('-', '')}T010000Z",
                    ),
                ]
            )
        stock_rows.append(
            (
                "2026-01-05",
                "000001.SZ",
                9_999.0,
                "stock-source-old",
                "stock-vendor-old",
                "stock-rule-old",
                "stock:20260105T000000Z",
            )
        )
        conn.executemany(
            """
            insert into choice_stock_daily_observation values (?, ?, ?, ?, ?, ?, ?)
            """,
            stock_rows,
        )
    finally:
        conn.close()


def _seed_index_only(path: Path) -> None:
    conn = duckdb.connect(str(path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_choice_macro_daily (
              series_id varchar,
              trade_date varchar,
              value_numeric double,
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
            insert into fact_choice_macro_daily values
              ('CA.CSI300', '2026-01-02', 100.0, 'sv', 'vv', 'rv', 'ok', 'run-1'),
              ('CA.CSI300', '2026-01-05', 101.0, 'sv', 'vv', 'rv', 'ok', 'run-2')
            """
        )
    finally:
        conn.close()


def test_load_history_returns_bounded_ascending_rows_and_canonical_evidence(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "history.duckdb"
    _seed_full_history(duckdb_path)

    result = load_dual_frequency_equity_history(
        duckdb_path=duckdb_path,
        lookback_rows=3,
    )

    assert result["status"] == "ready"
    assert result["quality"] == "ok"
    assert result["warnings"] == []
    assert result["earliest_trade_date"] == "2026-01-05"
    assert result["latest_trade_date"] == "2026-01-07"
    assert result["effective_as_of_date"] == "2026-01-07"
    assert result["row_count"] == 3
    assert result["rows"] == [
        {"trade_date": "2026-01-05", "close": 102.0, "amount": 300.0},
        {"trade_date": "2026-01-06", "close": 104.0, "amount": 700.0},
        {"trade_date": "2026-01-07", "close": 106.0, "amount": 1_100.0},
    ]
    assert result["tables_used"] == [
        "fact_choice_macro_daily",
        "choice_stock_daily_observation",
    ]
    assert result["sources"]["index"]["source_versions"] == [
        "index-source-v2"
    ]
    amount_source = result["sources"]["market_amount"]
    assert amount_source["status"] == "ready"
    assert amount_source["quality"] == "ok"
    assert amount_source["valid_amount_observation_count"] == 6
    assert amount_source["null_amount_observation_count"] == 0
    assert amount_source["source_versions"] == ["stock-source-v2"]


def test_load_history_honors_as_of_date_before_applying_lookback(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "history.duckdb"
    _seed_full_history(duckdb_path)

    result = load_dual_frequency_equity_history(
        duckdb_path=duckdb_path,
        as_of_date="2026-01-05",
        lookback_rows=20,
    )

    assert result["status"] == "ready"
    assert result["requested_as_of_date"] == "2026-01-05"
    assert [row["trade_date"] for row in result["rows"]] == [
        "2026-01-02",
        "2026-01-05",
    ]
    assert result["latest_trade_date"] == "2026-01-05"


def test_load_history_missing_database_is_unavailable_without_creating_file(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "missing.duckdb"

    result = load_dual_frequency_equity_history(duckdb_path=duckdb_path)

    assert result["status"] == "unavailable"
    assert result["quality"] == "unavailable"
    assert result["rows"] == []
    assert result["tables_used"] == []
    assert result["warnings"] == ["missing_database"]
    assert not duckdb_path.exists()


def test_load_history_missing_index_table_is_unavailable(tmp_path: Path) -> None:
    duckdb_path = tmp_path / "empty.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    conn.execute("create table unrelated_table (value integer)")
    conn.close()

    result = load_dual_frequency_equity_history(duckdb_path=duckdb_path)

    assert result["status"] == "unavailable"
    assert result["rows"] == []
    assert result["warnings"] == ["missing_table:fact_choice_macro_daily"]


def test_load_history_missing_market_amount_table_keeps_index_rows_partial(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "index-only.duckdb"
    _seed_index_only(duckdb_path)

    result = load_dual_frequency_equity_history(duckdb_path=duckdb_path)

    assert result["status"] == "partial"
    assert result["quality"] == "degraded"
    assert result["rows"] == [
        {"trade_date": "2026-01-02", "close": 100.0, "amount": None},
        {"trade_date": "2026-01-05", "close": 101.0, "amount": None},
    ]
    assert result["tables_used"] == ["fact_choice_macro_daily"]
    assert "missing_table:choice_stock_daily_observation" in result["warnings"]
    assert "market_amount_missing_dates" in result["warnings"]
    assert result["sources"]["market_amount"]["missing_trade_date_count"] == 2


def test_load_history_missing_amount_column_keeps_index_rows_partial(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "missing-amount.duckdb"
    _seed_index_only(duckdb_path)
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    conn.execute(
        """
        create table choice_stock_daily_observation (
          trade_date varchar,
          stock_code varchar
        )
        """
    )
    conn.execute(
        "insert into choice_stock_daily_observation values ('2026-01-02', '000001.SZ')"
    )
    conn.close()

    result = load_dual_frequency_equity_history(duckdb_path=duckdb_path)

    assert result["status"] == "partial"
    assert all(row["amount"] is None for row in result["rows"])
    assert (
        "missing_columns:choice_stock_daily_observation:amount"
        in result["warnings"]
    )
    assert "choice_stock_daily_observation" not in result["tables_used"]


def test_load_history_missing_stock_code_fails_closed_without_aggregating_amount(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "missing-stock-code.duckdb"
    _seed_index_only(duckdb_path)
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    conn.execute(
        """
        create table choice_stock_daily_observation (
          trade_date varchar,
          amount double,
          source_version varchar,
          vendor_version varchar,
          rule_version varchar,
          run_id varchar
        )
        """
    )
    conn.executemany(
        """
        insert into choice_stock_daily_observation values (?, ?, ?, ?, ?, ?)
        """,
        [
            ("2026-01-02", 10.0, "sv-old", "vv-old", "rv", "run-1"),
            ("2026-01-02", 999.0, "sv-new", "vv-new", "rv", "run-2"),
        ],
    )
    conn.close()

    result = load_dual_frequency_equity_history(duckdb_path=duckdb_path)

    assert result["status"] == "partial"
    assert result["quality"] == "degraded"
    assert result["rows"] == [
        {"trade_date": "2026-01-02", "close": 100.0, "amount": None},
        {"trade_date": "2026-01-05", "close": 101.0, "amount": None},
    ]
    assert (
        "missing_columns:choice_stock_daily_observation:stock_code"
        in result["warnings"]
    )
    assert "market_amount_missing_dates" in result["warnings"]
    assert "choice_stock_daily_observation" not in result["tables_used"]
    amount_source = result["sources"]["market_amount"]
    assert amount_source["status"] == "unavailable"
    assert amount_source["quality"] == "unavailable"
    assert amount_source["date_count"] == 0
    assert amount_source["valid_amount_observation_count"] == 0
    assert amount_source["missing_trade_date_count"] == 2


def test_load_history_exposes_null_amount_coverage_without_zero_fallback(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "null-amount.duckdb"
    _seed_index_only(duckdb_path)
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    conn.execute(
        """
        create table choice_stock_daily_observation (
          trade_date varchar,
          stock_code varchar,
          amount double,
          source_version varchar,
          vendor_version varchar,
          rule_version varchar,
          run_id varchar
        )
        """
    )
    conn.executemany(
        """
        insert into choice_stock_daily_observation values (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            ("2026-01-02", "000001.SZ", 10.0, "sv", "vv", "rv", "run-1"),
            ("2026-01-02", "000002.SZ", None, "sv", "vv", "rv", "run-1"),
        ],
    )
    conn.close()

    result = load_dual_frequency_equity_history(duckdb_path=duckdb_path)

    assert result["status"] == "partial"
    assert result["rows"] == [
        {"trade_date": "2026-01-02", "close": 100.0, "amount": 10.0},
        {"trade_date": "2026-01-05", "close": 101.0, "amount": None},
    ]
    amount_source = result["sources"]["market_amount"]
    assert amount_source["status"] == "ready"
    assert amount_source["quality"] == "degraded"
    assert amount_source["valid_amount_observation_count"] == 1
    assert amount_source["null_amount_observation_count"] == 1
    assert "market_amount_null_values_ignored" in result["warnings"]
    assert "market_amount_missing_dates" in result["warnings"]
    assert amount_source["missing_trade_date_count"] == 1
