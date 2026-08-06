from __future__ import annotations

import pytest

from scripts.run_fable_extension_study import (
    build_candidate_panel,
    date_block_bootstrap_effect,
    summarize_extension_study,
)

TRADING_DATES = [
    "2026-06-02",
    "2026-06-03",
    "2026-06-04",
    "2026-06-05",
    "2026-06-08",
    "2026-06-09",
    "2026-06-10",
    "2026-06-11",
    "2026-06-12",
    "2026-06-15",
    "2026-06-16",
    "2026-06-17",
    "2026-06-18",
    "2026-06-19",
    "2026-06-22",
    "2026-06-23",
    "2026-06-24",
    "2026-06-25",
    "2026-06-26",
    "2026-06-29",
]


def _row(
    stock_code: str,
    *,
    extension: float,
    entry_executable: bool = True,
    adjusted_20d: float | None = 0.10,
    raw_20d: float | None = 0.09,
) -> dict[str, object]:
    return {
        "signal_date": "2026-06-01",
        "entry_date": "2026-06-02",
        "stock_code": stock_code,
        "candidate_rank": 1,
        "market_state": "WARM",
        "entry_executable": entry_executable,
        "signal_close_value": 100.0 * (1.0 + extension),
        "signal_sma20_value": 100.0,
        "signal_feature_status": "ready",
        "return_5d_net_adj": 0.02,
        "return_5d_net": 0.019,
        "return_10d_net_adj": 0.04,
        "return_10d_net": 0.039,
        "return_20d_net_adj": adjusted_20d,
        "return_20d_net": raw_20d,
    }


def test_panel_uses_signal_close_macro_state_and_keeps_source_blocked_rows() -> None:
    rows = [
        _row("000001.SZ", extension=0.04),
        _row("000002.SZ", extension=0.08, adjusted_20d=None, raw_20d=-0.05),
        _row("000003.SZ", extension=0.12, entry_executable=False),
    ]
    macro_points = {
        "2026-06-01": {"state": "HOT", "source": "replayed"},
        "2026-06-02": {"state": "WARM", "source": "replayed"},
    }

    panel = build_candidate_panel(
        rows,
        trading_dates=TRADING_DATES,
        macro_points=macro_points,
    )

    assert len(panel) == 3
    assert {row["stored_signal_state"] for row in panel} == {"WARM"}
    assert {row["replayed_signal_state"] for row in panel} == {"HOT"}
    assert all(row["state_lineage_conflict"] is True for row in panel)
    assert panel[0]["gate_state_as_of_date"] == "2026-06-01"
    assert panel[0]["extension_bin"] == "0_5"
    assert panel[1]["extension_bin"] == "5_10"
    assert panel[1]["maturity_20d"] == "matured_adjustment_missing"
    assert panel[2]["primary_eligible"] is False


def test_panel_rejects_conflicting_logical_candidate_keys() -> None:
    rows = [
        _row("000001.SZ", extension=0.04),
        {**_row("000001.SZ", extension=0.08), "candidate_rank": 2},
    ]

    with pytest.raises(ValueError, match="conflicting logical candidate duplicates"):
        build_candidate_panel(
            rows,
            trading_dates=TRADING_DATES,
            macro_points={"2026-06-01": {"state": "HOT", "source": "replayed"}},
        )


def test_summary_reconciles_primary_and_sensitivity_samples() -> None:
    panel = build_candidate_panel(
        [
            _row("000001.SZ", extension=0.04),
            _row("000002.SZ", extension=0.08, adjusted_20d=None, raw_20d=-0.05),
            _row("000003.SZ", extension=0.12, entry_executable=False),
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

    accountability = summary["sample_accountability"]
    assert accountability["source_row_count"] == 3
    assert accountability["primary_universe_row_count"] == 2
    assert accountability["source_blocked_row_count"] == 1
    assert accountability["horizons"]["20d"] == {
        "complete_adjusted": 1,
        "matured_adjustment_missing": 1,
        "matured_missing_bar": 0,
        "natural_pending": 0,
    }
    assert accountability["primary_adjusted_coverage"] == pytest.approx(0.5)
    assert accountability["raw_sensitivity_coverage"] == pytest.approx(1.0)
    assert summary["extension_bins"]["0_5"]["20d_adjusted"]["mean_return"] == 0.10
    assert summary["extension_bins"]["5_10"]["20d_adjusted"]["sample_count"] == 0
    assert (
        summary["extension_bins"]["5_10"]["20d_raw_sensitivity"]["mean_return"] == -0.05
    )
    assert summary["status"] == "research_only_data_quality_blocked"
    assert summary["promotion_verdict"] == "insufficient_evidence"
    assert summary["state_lineage"]["conflict_count"] == 2
    assert set(summary["gate_state_extension_cells"]) == {
        "stored_signal_state",
        "replayed_signal_state",
    }


def test_sample_adequacy_counts_only_feature_and_adjusted_outcome_ready_rows() -> None:
    missing_feature = {
        **_row("000002.SZ", extension=0.08),
        "signal_sma20_value": None,
        "signal_feature_status": "missing_history",
    }
    panel = build_candidate_panel(
        [_row("000001.SZ", extension=0.04), missing_feature],
        trading_dates=TRADING_DATES,
        macro_points={"2026-06-01": {"state": "WARM", "source": "replayed"}},
    )

    summary = summarize_extension_study(
        panel,
        study_version="rv_fable_extension_study_v1",
        minimum_primary_coverage=0.95,
        minimum_overall_rows=2,
        minimum_overall_dates=1,
        minimum_bin_rows=1,
        minimum_bin_dates=1,
        minimum_cell_rows=1,
        minimum_cell_dates=1,
        bootstrap_iterations=10,
        bootstrap_seed=7,
    )

    assert summary["sample_adequacy"]["primary_adjusted_row_count"] == 2
    assert summary["sample_adequacy"]["primary_analysis_ready_row_count"] == 1
    assert summary["sample_adequacy"]["adequate"] is False


def test_date_block_bootstrap_effect_is_deterministic_and_negative() -> None:
    rows = [
        {"signal_date": "2026-01-01", "extension": 0.01, "outcome": 0.20},
        {"signal_date": "2026-02-01", "extension": 0.05, "outcome": 0.10},
        {"signal_date": "2026-03-01", "extension": 0.10, "outcome": 0.00},
        {"signal_date": "2026-04-01", "extension": 0.20, "outcome": -0.10},
    ]

    first = date_block_bootstrap_effect(
        rows,
        outcome_field="outcome",
        iterations=200,
        seed=17,
    )
    second = date_block_bootstrap_effect(
        rows,
        outcome_field="outcome",
        iterations=200,
        seed=17,
    )

    assert first == second
    assert first["slope_per_10pp_extension"] < 0
    assert first["sample_count"] == 4
    assert first["distinct_date_count"] == 4
