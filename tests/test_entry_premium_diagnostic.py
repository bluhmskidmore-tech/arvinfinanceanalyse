from __future__ import annotations

import duckdb
import pytest

from scripts.diagnose_entry_premium import (
    _load_execution_rows,
    analyze_entry_premium,
    build_entry_premium_summary,
    entry_premium_bucket,
    run_entry_premium_diagnostic,
)


def test_entry_premium_bucket_boundaries() -> None:
    assert entry_premium_bucket(-0.0001) == "<0"
    assert entry_premium_bucket(0.0) == "[0,1%)"
    assert entry_premium_bucket(0.009999) == "[0,1%)"
    assert entry_premium_bucket(0.01) == "[1%,2%)"
    assert entry_premium_bucket(0.02) == "[2%,3%)"
    assert entry_premium_bucket(0.03) == "[3%,5%)"
    assert entry_premium_bucket(0.05) == ">=5%"


def test_entry_premium_summary_uses_net_adjusted_return_columns() -> None:
    rows = [
        {
            "signal_kind": "stock_candidate",
            "market_state": "HOT",
            "signal_close": 100.0,
            "entry_price": 103.0,
            "return_5d_gross_adj": 0.20,
            "return_5d_net_adj": -0.10,
        }
    ]

    summary = build_entry_premium_summary(rows)
    signal_rows = [
        row
        for row in summary
        if row["group_type"] == "signal_kind"
        and row["horizon"] == "5d"
        and row["entry_premium_bucket"] == "[3%,5%)"
    ]

    assert signal_rows[0]["sample_count"] == 1
    assert signal_rows[0]["avg_net_return"] == pytest.approx(-0.10)
    assert signal_rows[0]["win_rate"] == pytest.approx(0.0)


def test_entry_premium_recommends_threshold_when_high_premium_expectation_is_negative() -> None:
    payload = analyze_entry_premium(
        [
            {
                "signal_kind": "stock_candidate",
                "market_state": "HOT",
                "signal_close": 100.0,
                "entry_price": 106.0,
                "return_1d_net_adj": -0.01,
                "return_5d_net_adj": -0.03,
                "return_20d_net_adj": -0.08,
            },
            {
                "signal_kind": "stock_candidate",
                "market_state": "HOT",
                "signal_close": 100.0,
                "entry_price": 101.0,
                "return_1d_net_adj": 0.01,
                "return_5d_net_adj": 0.03,
                "return_20d_net_adj": 0.08,
            },
        ]
    )

    conclusion = payload["conclusion"]
    assert conclusion["recommendation"] == "max_entry_premium=0.03"
    assert conclusion["recommended_threshold"] == pytest.approx(0.03)
    assert conclusion["estimated_abandon_ratio"] == pytest.approx(0.5)


def test_entry_premium_loader_coalesces_null_adjusted_returns(tmp_path) -> None:
    db_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table livermore_candidate_execution_history (
              signal_date varchar,
              stock_code varchar,
              signal_kind varchar,
              market_state varchar,
              signal_close double,
              entry_price double,
              return_1d_net_adj double,
              return_1d_net double,
              return_5d_net_adj double,
              return_5d_net double,
              return_20d_net_adj double,
              return_20d_net double
            )
            """
        )
        conn.execute(
            """
            insert into livermore_candidate_execution_history values
            ('2026-06-01', '000001.SZ', 'stock_candidate', 'HOT', 10.0, 10.4,
             null, -0.01, null, -0.02, null, -0.03)
            """
        )
        rows, issues = _load_execution_rows(conn, signal_kind="stock_candidate")
    finally:
        conn.close()

    assert issues == []
    assert rows[0]["return_1d_net_adj"] == pytest.approx(-0.01)
    assert rows[0]["return_5d_net_adj"] == pytest.approx(-0.02)
    assert rows[0]["return_20d_net_adj"] == pytest.approx(-0.03)


def test_entry_premium_diagnostic_writes_blocked_report_when_execution_table_missing(tmp_path) -> None:
    db_path = tmp_path / "moss.duckdb"
    report_path = tmp_path / "entry-premium.md"
    conn = duckdb.connect(str(db_path), read_only=False)
    conn.close()

    payload = run_entry_premium_diagnostic(
        db_path=str(db_path),
        report_path=report_path,
    )

    assert payload["status"] == "blocked"
    assert "livermore_candidate_execution_history" in payload["reason"]
    report_text = report_path.read_text(encoding="utf-8")
    assert "- status: blocked" in report_text
    assert "livermore_candidate_execution_history" in report_text
