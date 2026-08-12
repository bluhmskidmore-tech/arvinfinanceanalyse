# ARCHIVED 2026-08-12（C5 脚本盘点批次 1 归档）：随 ../walk_forward_threshold_scan.py 一并移出 tests/。
# pytest 不再收集（pytest.ini testpaths 仅 tests/、backend/tests/）；归档件冻结、不保证可运行，仅作追溯。
from __future__ import annotations

import duckdb

from scripts.walk_forward_threshold_scan import (
    ThresholdConfig,
    build_threshold_grid,
    load_universe_history_rows,
    run_walk_forward_from_duckdb,
    run_walk_forward_scan,
)


def _row(
    signal_date: str,
    code: str,
    *,
    close_strength: float,
    abnormal_turnover: float,
    gap_norm: float,
    return_5d_adj: float | None,
    eligible: bool = True,
    market_state: str = "HOT",
) -> dict[str, object]:
    return {
        "signal_date": signal_date,
        "stock_code": code,
        "close_strength": close_strength,
        "abnormal_turnover": abnormal_turnover,
        "gap_norm": gap_norm,
        "market_state": market_state,
        "eligible_before_truncation": eligible,
        "return_5d_adj": return_5d_adj,
    }


def _fixture_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    months = ["2026-01", "2026-02", "2026-03", "2026-04"]
    returns_by_month = {
        "2026-01": (0.10, 0.02),
        "2026-02": (0.08, -0.01),
        "2026-03": (-0.02, 0.04),
        "2026-04": (0.03, 0.01),
    }
    for month in months:
        strong_return, loose_return = returns_by_month[month]
        rows.extend(
            [
                _row(f"{month}-05", f"{month}-A", close_strength=0.97, abnormal_turnover=1.3, gap_norm=0.04, return_5d_adj=strong_return),
                _row(f"{month}-06", f"{month}-B", close_strength=0.96, abnormal_turnover=1.4, gap_norm=0.03, return_5d_adj=strong_return),
                _row(f"{month}-07", f"{month}-C", close_strength=0.86, abnormal_turnover=1.1, gap_norm=0.01, return_5d_adj=loose_return),
                _row(f"{month}-08", f"{month}-D", close_strength=0.84, abnormal_turnover=1.1, gap_norm=0.01, return_5d_adj=0.20),
                _row(f"{month}-09", f"{month}-E", close_strength=0.99, abnormal_turnover=1.3, gap_norm=0.03, return_5d_adj=None),
                _row(f"{month}-10", f"{month}-F", close_strength=0.99, abnormal_turnover=1.3, gap_norm=0.03, return_5d_adj=0.50, market_state="OVERHEAT"),
                _row(f"{month}-11", f"{month}-G", close_strength=0.99, abnormal_turnover=1.3, gap_norm=0.03, return_5d_adj=0.50, eligible=False),
            ]
        )
    return rows


def test_walk_forward_scan_splits_windows_applies_min_sample_and_compares_fixed_v7() -> None:
    grid = build_threshold_grid(
        close_strength_values=(0.85, 0.95),
        atu_min_values=(1.0, 1.2),
        atu_max_values=(2.0,),
        gap_norm_min_values=(0.0,),
    )

    result = run_walk_forward_scan(
        _fixture_rows(),
        start="2026-01",
        train_months=1,
        test_months=1,
        step_months=1,
        min_sample=2,
        grid=grid,
        fixed_config=ThresholdConfig(close_strength_min=0.95, atu_min=1.2, atu_max=2.0, gap_norm_min=0.0),
    )

    assert result["status"] == "completed"
    assert result["window_count"] == 3
    assert result["missing_return_count"] == 4
    first = result["windows"][0]
    assert first["train_start"] == "2026-01-01"
    assert first["test_start"] == "2026-02-01"
    assert first["best_config"] == {
        "close_strength_min": 0.95,
        "atu_min": 1.2,
        "atu_max": 2.0,
        "gap_norm_min": 0.0,
    }
    assert first["train"]["n"] == 2
    assert first["train"]["avg"] == 0.1
    assert first["test"]["avg"] == 0.08
    assert first["fixed_v7_test"]["n"] == 2
    assert first["fixed_v7_test"]["win"] == 1.0
    assert result["summary"]["fixed_v7_window_count"] == 3


def test_walk_forward_scan_returns_empty_when_n_constraint_cannot_be_met() -> None:
    grid = build_threshold_grid(
        close_strength_values=(0.95,),
        atu_min_values=(1.2,),
        atu_max_values=(2.0,),
        gap_norm_min_values=(0.0,),
    )

    result = run_walk_forward_scan(
        _fixture_rows(),
        start="2026-01",
        train_months=1,
        test_months=1,
        step_months=1,
        min_sample=99,
        grid=grid,
    )

    assert result["window_count"] == 3
    assert all(window["best_config"] is None for window in result["windows"])
    assert all(window["test"]["n"] == 0 for window in result["windows"])


def test_walk_forward_scan_loads_duckdb_rows_and_writes_report(tmp_path) -> None:
    db_path = tmp_path / "walk.duckdb"
    report_path = tmp_path / "walk-report.md"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table livermore_stock_candidate_universe_history (
              snapshot_as_of_date varchar,
              stock_code varchar,
              close_strength double,
              abnormal_turnover double,
              gap_norm double,
              market_state varchar,
              eligible_before_truncation boolean,
              return_5d_adj double
            )
            """
        )
        conn.executemany(
            "insert into livermore_stock_candidate_universe_history values (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    row["signal_date"],
                    row["stock_code"],
                    row["close_strength"],
                    row["abnormal_turnover"],
                    row["gap_norm"],
                    row["market_state"],
                    row["eligible_before_truncation"],
                    row["return_5d_adj"],
                )
                for row in _fixture_rows()
            ],
        )
    finally:
        conn.close()

    rows = load_universe_history_rows(db_path)
    result = run_walk_forward_from_duckdb(
        duckdb_path=db_path,
        start="2026-01",
        train_months=1,
        test_months=1,
        step_months=1,
        min_sample=2,
        report_path=report_path,
    )

    assert len(rows) == len(_fixture_rows())
    assert result["status"] == "completed"
    assert result["report_path"] == str(report_path)
    assert "Walk-Forward Threshold Report" in report_path.read_text(encoding="utf-8")
