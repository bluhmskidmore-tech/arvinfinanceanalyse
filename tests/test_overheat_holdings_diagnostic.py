from __future__ import annotations

import json
from datetime import date, timedelta

import duckdb
import pytest

from scripts.diagnose_overheat_holdings import (
    analyze_overheat_holding_samples,
    run_overheat_holdings_diagnostic,
)


def test_overheat_holding_summary_counts_current_exit_blindspot() -> None:
    payload = analyze_overheat_holding_samples(
        [
            {
                "market_state": "OVERHEAT",
                "stock_code": "000001.SZ",
                "return_10d_net": -0.12,
                "return_20d_net": -0.18,
                "max_drawdown_10d": 0.11,
                "max_drawdown_20d": 0.15,
                "risk_exit_evaluable": True,
                "risk_exit_triggered": False,
            },
            {
                "market_state": "OVERHEAT",
                "stock_code": "000002.SZ",
                "return_10d_net": 0.03,
                "return_20d_net": 0.04,
                "max_drawdown_10d": 0.02,
                "max_drawdown_20d": 0.03,
                "risk_exit_evaluable": True,
                "risk_exit_triggered": False,
            },
            {
                "market_state": "HOT",
                "stock_code": "000003.SZ",
                "return_10d_net": 0.02,
                "return_20d_net": 0.05,
                "max_drawdown_10d": 0.01,
                "max_drawdown_20d": 0.02,
                "risk_exit_evaluable": True,
                "risk_exit_triggered": False,
            },
        ]
    )

    assert payload["status"] == "ready"
    assert payload["overheat_blindspot"]["blindspot_count"] == 1
    assert payload["overheat_blindspot"]["blindspot_ratio"] == pytest.approx(0.5)
    assert payload["state_summary"]["OVERHEAT"]["returns"]["20d"]["avg_net_return"] == pytest.approx(-0.07)
    assert payload["conclusion"] == "overheat_holding_blindspot_needs_rule_research"


def test_overheat_holdings_diagnostic_blocks_when_position_table_missing(tmp_path) -> None:
    db_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar,
              stock_code varchar,
              close_value double,
              volume double
            )
            """
        )
    finally:
        conn.close()

    report_path = tmp_path / "overheat.md"
    payload = run_overheat_holdings_diagnostic(db_path=str(db_path), report_path=report_path)

    assert payload["status"] == "blocked"
    assert "livermore_position_snapshot" in payload["reason"]
    assert "- status: blocked" in report_path.read_text(encoding="utf-8")


def test_overheat_holdings_diagnostic_builds_ready_report_from_snapshot_and_prices(tmp_path) -> None:
    db_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    as_of = date(2026, 1, 25)
    try:
        conn.execute(
            """
            create table livermore_position_snapshot (
              as_of_date varchar,
              stock_code varchar,
              stock_name varchar,
              entry_cost double,
              bars_since_entry integer,
              entry_date varchar,
              position_quantity double,
              position_status varchar
            )
            """
        )
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar,
              stock_code varchar,
              close_value double,
              volume double
            )
            """
        )
        conn.execute(
            """
            create table livermore_candidate_history (
              snapshot_as_of_date varchar,
              signal_evidence_json varchar
            )
            """
        )
        conn.execute(
            """
            insert into livermore_position_snapshot values
            (?, '000001.SZ', 'Alpha', 100.0, 24, null, 1.0, 'ACTIVE')
            """,
            [as_of.isoformat()],
        )
        rows = []
        for index in range(50):
            trade_date = date(2026, 1, 1) + timedelta(days=index)
            close = 100.0 if trade_date <= as_of else max(88.0, 100.0 - (trade_date - as_of).days * 1.2)
            rows.append((trade_date.isoformat(), "000001.SZ", close, 1_000_000.0))
        conn.executemany("insert into choice_stock_daily_observation values (?, ?, ?, ?)", rows)
        conn.execute(
            "insert into livermore_candidate_history values (?, ?)",
            [
                as_of.isoformat(),
                json.dumps({"market_gate": {"state": "OVERHEAT", "exposure": 1.0}}),
            ],
        )
    finally:
        conn.close()

    report_path = tmp_path / "overheat.md"
    payload = run_overheat_holdings_diagnostic(db_path=str(db_path), report_path=report_path)

    assert payload["status"] == "ready"
    assert payload["sample_count"] == 1
    assert payload["state_summary"]["OVERHEAT"]["sample_count"] == 1
    assert payload["overheat_blindspot"]["blindspot_count"] == 1
    assert payload["overheat_blindspot"]["blindspot_ratio"] == pytest.approx(1.0)
    assert "OVERHEAT" in report_path.read_text(encoding="utf-8")
