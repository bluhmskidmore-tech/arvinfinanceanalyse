from __future__ import annotations

from datetime import date, timedelta

from scripts.run_fable_extension_study import (
    build_candidate_panel,
    summarize_extension_study,
)


def test_state_interaction_reports_coverage_effect_and_holdout_by_lineage() -> None:
    signal_dates = [f"2026-01-{day:02d}" for day in range(1, 7)]
    trading_dates = [
        (date(2026, 1, 2) + timedelta(days=offset)).isoformat() for offset in range(40)
    ]
    rows = []
    macro_points = {}
    for index, signal_date in enumerate(signal_dates):
        extension = 0.05 + index * 0.02
        state = "HOT" if index < 3 else "OVERHEAT"
        rows.append(
            {
                "signal_date": signal_date,
                "stock_code": f"00000{index + 1}.SZ",
                "market_state": state,
                "entry_executable": True,
                "signal_close_value": 100.0 * (1.0 + extension),
                "signal_sma20_value": 100.0,
                "signal_feature_status": "ready",
                "return_5d_net_adj": 0.01,
                "return_5d_net": 0.01,
                "return_10d_net_adj": 0.01,
                "return_10d_net": 0.01,
                "return_20d_net_adj": 0.20 - extension,
                "return_20d_net": 0.19 - extension,
                "data_status": "complete",
            }
        )
        macro_points[signal_date] = {"state": state, "source": "replayed"}

    panel = build_candidate_panel(
        rows,
        trading_dates=trading_dates,
        macro_points=macro_points,
    )
    summary = summarize_extension_study(
        panel,
        study_version="rv_fable_extension_study_v1",
        minimum_primary_coverage=0.95,
        minimum_overall_rows=1,
        minimum_overall_dates=1,
        minimum_bin_rows=1,
        minimum_bin_dates=1,
        minimum_cell_rows=1,
        minimum_cell_dates=1,
        bootstrap_iterations=100,
        bootstrap_seed=17,
    )

    effects = summary["gate_state_effects"]
    assert set(effects) == {"stored_signal_state", "replayed_signal_state"}
    hot = effects["replayed_signal_state"]["HOT"]
    assert hot["candidate_count"] == 3
    assert hot["adjusted_outcome_coverage"] == 1.0
    assert hot["20d_adjusted_primary"]["slope_per_10pp_extension"] < 0
    assert hot["chronological_holdout"]["status"] == "ready"

    hot_bin = summary["gate_state_extension_cells"]["replayed_signal_state"]["HOT"][
        "5_10"
    ]
    assert hot_bin["adjusted_outcome_coverage"] == 1.0
