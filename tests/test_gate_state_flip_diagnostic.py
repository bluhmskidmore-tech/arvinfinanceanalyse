from __future__ import annotations

import duckdb
import pytest

from scripts.diagnose_gate_state_flips import (
    analyze_gate_state_flips,
    build_gate_state_flip_comparison,
    run_gate_state_flip_diagnostic,
    simulate_delayed_downgrade,
)


def test_gate_state_flip_stats_count_whipsaw_and_dwell() -> None:
    points = [
        {"date": "2026-01-01", "state": "OFF", "exposure": 0.0},
        {"date": "2026-01-02", "state": "WARM", "exposure": 0.5},
        {"date": "2026-01-03", "state": "OFF", "exposure": 0.0},
        {"date": "2026-01-04", "state": "OFF", "exposure": 0.0},
    ]

    payload = analyze_gate_state_flips(points)

    assert payload["status"] == "ready"
    assert payload["transition_count"] == 2
    assert payload["whipsaw_count"] == 1
    assert payload["whipsaw_ratio"] == pytest.approx(0.5)
    assert payload["avg_dwell_days_by_state"]["OFF"] == pytest.approx(1.5)
    assert payload["avg_dwell_days_by_state"]["WARM"] == pytest.approx(1.0)


def test_delayed_downgrade_requires_two_days_but_upgrade_is_immediate() -> None:
    points = [
        {"date": "2026-01-01", "state": "HOT", "exposure": 1.0},
        {"date": "2026-01-02", "state": "WARM", "exposure": 0.5},
        {"date": "2026-01-03", "state": "WARM", "exposure": 0.5},
        {"date": "2026-01-04", "state": "HOT", "exposure": 1.0},
    ]

    delayed = simulate_delayed_downgrade(points, confirm_days=2)

    assert [row["delayed_exposure"] for row in delayed] == [1.0, 1.0, 0.5, 1.0]
    assert [row["delayed_state"] for row in delayed] == ["HOT", "HOT", "WARM", "HOT"]


def test_gate_state_flip_comparison_reports_delayed_line_metrics() -> None:
    points = [
        {"date": "2026-01-01", "state": "HOT", "exposure": 1.0},
        {"date": "2026-01-02", "state": "WARM", "exposure": 0.5},
        {"date": "2026-01-03", "state": "WARM", "exposure": 0.5},
        {"date": "2026-01-04", "state": "HOT", "exposure": 1.0},
    ]
    benchmark_rows = [
        {"date": row["date"], "daily_return": 0.10}
        for row in points
    ]

    payload = build_gate_state_flip_comparison(points, benchmark_rows, initial_capital=100.0)

    assert payload["status"] == "ready"
    metrics = payload["metrics"]
    assert metrics["immediate_index"]["terminal_value"] == pytest.approx(133.4025)
    assert metrics["delayed_downgrade_index"]["terminal_value"] == pytest.approx(139.755)
    assert metrics["cumulative_return_delta"] == pytest.approx(0.063525)
    assert metrics["conclusion"] == "delayed_downgrade_added_value"


def test_gate_state_flip_diagnostic_blocks_without_benchmark_rows(tmp_path) -> None:
    db_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute("create table unrelated_table (id integer)")
    finally:
        conn.close()

    report_path = tmp_path / "gate-flips.md"
    payload = run_gate_state_flip_diagnostic(db_path=str(db_path), report_path=report_path)

    assert payload["status"] == "blocked"
    assert "CA.CSI300" in payload["reason"]
    assert "- status: blocked" in report_path.read_text(encoding="utf-8")
