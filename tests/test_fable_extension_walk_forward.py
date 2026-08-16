from __future__ import annotations

from scripts.run_fable_extension_study import (
    assess_bin_monotonicity,
    chronological_holdout_effect,
)


def test_chronological_holdout_keeps_dates_disjoint_and_fixed() -> None:
    rows = [
        {
            "signal_date": f"2026-{month:02d}-01",
            "extension": month / 100.0,
            "outcome": 0.20 - month / 50.0,
        }
        for month in range(1, 11)
    ]

    result = chronological_holdout_effect(
        rows,
        outcome_field="outcome",
        train_fraction=0.70,
        bootstrap_iterations=100,
        bootstrap_seed=23,
    )

    assert result["discovery"]["date_count"] == 7
    assert result["holdout"]["date_count"] == 3
    assert result["discovery"]["end_date"] < result["holdout"]["start_date"]
    assert result["discovery"]["effect"]["direction"] == "negative"
    assert result["holdout"]["effect"]["direction"] == "negative"
    assert result["direction_consistent"] is True


def test_monotonicity_uses_only_interpretation_eligible_bins() -> None:
    bins = {
        "lt_0": {
            "interpretation_eligible": False,
            "20d_adjusted": {"mean_return": 0.50},
        },
        "0_5": {
            "interpretation_eligible": True,
            "20d_adjusted": {"mean_return": 0.10},
        },
        "5_10": {
            "interpretation_eligible": True,
            "20d_adjusted": {"mean_return": 0.05},
        },
        "10_15": {
            "interpretation_eligible": True,
            "20d_adjusted": {"mean_return": 0.00},
        },
        "15_plus": {
            "interpretation_eligible": True,
            "20d_adjusted": {"mean_return": -0.05},
        },
    }

    assert assess_bin_monotonicity(bins) == {
        "assessment": "deteriorating",
        "eligible_bin_count": 4,
        "eligible_bins": ["0_5", "5_10", "10_15", "15_plus"],
    }
