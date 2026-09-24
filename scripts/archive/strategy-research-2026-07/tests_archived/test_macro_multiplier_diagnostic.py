# ARCHIVED 2026-08-12（C5 脚本盘点批次 1 归档）：随 ../diagnose_macro_multiplier.py 一并移出 tests/。
# pytest 不再收集（pytest.ini testpaths 仅 tests/、backend/tests/）；归档件冻结、不保证可运行，仅作追溯。
from __future__ import annotations

import duckdb
import pytest

from scripts.diagnose_macro_multiplier import (
    build_macro_multiplier_comparison,
    macro_status_from_score,
    run_macro_multiplier_diagnostic,
)


def test_macro_status_from_score_thresholds() -> None:
    assert macro_status_from_score(-0.31) == "supportive"
    assert macro_status_from_score(-0.30) == "supportive"
    assert macro_status_from_score(-0.29) == "neutral"
    assert macro_status_from_score(0.29) == "neutral"
    assert macro_status_from_score(0.30) == "restrictive"
    assert macro_status_from_score(None) == "unknown"


def test_macro_multiplier_comparison_applies_multipliers_and_counts_switches() -> None:
    benchmark_rows = [
        {"date": "2026-01-01", "daily_return": 0.10},
        {"date": "2026-01-02", "daily_return": 0.10},
        {"date": "2026-01-03", "daily_return": 0.10},
        {"date": "2026-01-04", "daily_return": 0.10},
    ]
    exposure_rows = [
        {"date": row["date"], "exposure": 1.0}
        for row in benchmark_rows
    ]
    macro_rows = [
        {"date": "2026-01-01", "macro_status": "supportive"},
        {"date": "2026-01-02", "macro_status": "neutral"},
        {"date": "2026-01-03", "macro_status": "restrictive"},
        {"date": "2026-01-04", "macro_status": "unknown"},
    ]

    payload = build_macro_multiplier_comparison(
        benchmark_rows,
        exposure_rows,
        macro_rows,
        macro_multipliers={"supportive": 1.0, "neutral": 0.5, "restrictive": 0.0, "unknown": 0.0},
        initial_capital=100.0,
    )

    assert payload["status"] == "ready"
    metrics = payload["metrics"]
    assert metrics["gate_index"]["terminal_value"] == pytest.approx(146.41)
    assert metrics["gate_macro_index"]["terminal_value"] == pytest.approx(115.5)
    assert metrics["cumulative_return_delta"] == pytest.approx(-0.3091)
    assert metrics["conclusion"] == "macro_multiplier_dragged"
    assert payload["macro_status"]["switch_count"] == 3
    assert payload["macro_status"]["day_counts"] == {
        "supportive": 1,
        "neutral": 1,
        "restrictive": 1,
        "unknown": 1,
    }
    assert payload["macro_status"]["day_ratios"]["neutral"] == pytest.approx(0.25)


def test_macro_multiplier_diagnostic_writes_blocked_report_when_macro_history_missing(tmp_path) -> None:
    db_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_choice_macro_daily (
              series_id varchar,
              trade_date varchar,
              value_numeric double
            )
            """
        )
        conn.execute(
            """
            insert into fact_choice_macro_daily values
            ('CA.CSI300', '2026-01-01', 100.0),
            ('CA.CSI300', '2026-01-02', 101.0)
            """
        )
    finally:
        conn.close()

    report_path = tmp_path / "macro-report.md"
    payload = run_macro_multiplier_diagnostic(db_path=str(db_path), report_path=report_path)

    assert payload["status"] == "blocked"
    assert "Missing macro composite history source" in payload["reason"]
    report_text = report_path.read_text(encoding="utf-8")
    assert "- status: blocked" in report_text
    assert "macro_composite_history" in report_text
