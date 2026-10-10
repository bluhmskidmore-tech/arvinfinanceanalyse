from __future__ import annotations

from scripts.run_fable_extension_study import (
    build_candidate_panel,
    summarize_extension_study,
)

TRADING_DATES = [f"2026-06-{day:02d}" for day in range(2, 22)]


def _row(
    stock_code: str,
    *,
    data_status: str,
    adjusted_20d: float | None,
    raw_20d: float | None,
) -> dict[str, object]:
    return {
        "signal_date": "2026-06-01",
        "stock_code": stock_code,
        "market_state": "HOT",
        "entry_executable": True,
        "signal_close_value": 108.0,
        "signal_sma20_value": 100.0,
        "signal_feature_status": "ready",
        "return_5d_net_adj": 0.01,
        "return_5d_net": 0.01,
        "return_10d_net_adj": 0.02,
        "return_10d_net": 0.02,
        "return_20d_net_adj": adjusted_20d,
        "return_20d_net": raw_20d,
        "data_status": data_status,
    }


def test_summary_separates_adjustment_gap_from_stale_materialization() -> None:
    panel = build_candidate_panel(
        [
            _row(
                "000001.SZ",
                data_status="complete",
                adjusted_20d=None,
                raw_20d=0.03,
            ),
            _row(
                "000002.SZ",
                data_status="pending",
                adjusted_20d=None,
                raw_20d=None,
            ),
            _row(
                "000003.SZ",
                data_status="complete",
                adjusted_20d=0.04,
                raw_20d=0.03,
            ),
        ],
        trading_dates=TRADING_DATES,
        macro_points={"2026-06-01": {"state": "HOT", "source": "replayed"}},
    )

    summary = summarize_extension_study(
        panel,
        study_version="rv_fable_extension_study_v1",
        minimum_primary_coverage=0.95,
        minimum_overall_rows=200,
        minimum_overall_dates=40,
        minimum_bin_rows=30,
        minimum_bin_dates=10,
        minimum_cell_rows=20,
        minimum_cell_dates=8,
        bootstrap_iterations=100,
        bootstrap_seed=7,
    )

    assert summary["sample_accountability"]["materialization_20d"] == {
        "adjusted_outcome_ready": 1,
        "stored_complete_adjustment_missing": 1,
        "stored_pending_after_market_maturity": 1,
        "other_matured_incomplete": 0,
    }
