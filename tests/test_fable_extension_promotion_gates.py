from __future__ import annotations

import pytest

from scripts.run_fable_extension_study import evaluate_promotion_gates


COST_BASIS_METADATA = {
    "primary_formula_versions": ["fv_test"],
    "primary_entry_price_kinds": ["next_open"],
    "primary_price_adjustment_modes": ["adj_factor_ratio"],
    "primary_buy_cost_bps_values": [8.0],
    "primary_sell_cost_bps_values": [13.0],
    "primary_slippage_bps_values": [10.0],
    "primary_cost_basis_missing_counts": {
        "formula_version": 0,
        "entry_price_kind": 0,
        "price_adjustment_mode": 0,
        "buy_cost_bps": 0,
        "sell_cost_bps": 0,
        "slippage_bps": 0,
    },
}


def test_promotion_evaluation_enforces_stability_lineage_cost_and_retention() -> None:
    summary = {
        "promotion_blockers": ["primary_adjusted_coverage_below_gate"],
        "sample_accountability": {"primary_adjusted_coverage": 0.70},
        "sample_adequacy": {"adequate": True},
        "continuous_effect": {
            "20d_adjusted_primary": {
                "slope_per_10pp_extension": -0.01,
                "bootstrap_ci_95": [-0.03, 0.01],
            }
        },
        "chronological_holdout": {
            "20d_adjusted_primary": {
                "direction_consistent": False,
                "discovery": {"effect": {"direction": "negative"}},
                "holdout": {"effect": {"direction": "positive"}},
            }
        },
        "monotonicity": {"assessment": "non_monotonic"},
        "state_lineage": {"conflict_count": 4},
    }
    panel = [
        {
            "primary_eligible": True,
            "extension_bin": "15_plus" if index < 7 else "10_15",
            "stored_signal_state": "OVERHEAT",
            "replayed_signal_state": "OVERHEAT",
        }
        for index in range(10)
    ]
    contract = {
        "formal_use_allowed": False,
        "primary_endpoint": {
            "field": "return_20d_net_adj",
            "basis": "net_next_open_adjusted",
        },
        "sample_gates": {"minimum_primary_coverage": 0.95},
        "promotion": {
            "hard_rule_allowed": False,
            "candidate_retention_floor": 0.60,
            "required_evidence": [
                "primary_adjusted_coverage_gate_passes",
                "overall_sample_gate_passes",
                "chronological_holdout_direction_is_consistent",
                "bin_relation_is_not_inconclusive",
                "cost_basis_remains_comparable",
                "candidate_retention_floor_passes",
            ],
        },
    }

    evaluated = evaluate_promotion_gates(
        summary,
        panel=panel,
        contract=contract,
        source_metadata=COST_BASIS_METADATA,
    )

    blockers = set(evaluated["promotion_blockers"])
    assert "primary_extension_effect_ci_not_strictly_negative" in blockers
    assert "chronological_holdout_not_negative_consistent" in blockers
    assert "extension_bins_not_monotonic_deteriorating" in blockers
    assert "gate_state_lineage_conflict" in blockers
    assert "fixed_15_plus_retention_below_floor" in blockers
    assert "contract_hard_rule_promotion_prohibited" in blockers
    assert (
        evaluated["promotion_gate_evaluation"]["cost_basis_comparable"]["passed"]
        is True
    )
    lens = evaluated["retention_lenses"]["fixed_extension_bin_exclusions"]["15_plus"]
    assert lens["retained_candidate_share"] == 0.3
    assert lens["retention_floor_passed"] is False
    assert evaluated["promotion_verdict"] == "insufficient_evidence"
    required = evaluated["contract_required_evidence"]
    assert required["chronological_holdout_direction_is_consistent"] == {
        "runtime_gate": "chronological_holdout_direction_consistency",
        "passed": False,
    }
    assert required["bin_relation_is_not_inconclusive"] == {
        "runtime_gate": "extension_bin_relation_not_inconclusive",
        "passed": True,
    }


def test_cost_basis_gate_fails_closed_when_execution_basis_is_incomplete() -> None:
    summary = {
        "promotion_blockers": [],
        "sample_accountability": {"primary_adjusted_coverage": 1.0},
        "sample_adequacy": {"adequate": True},
        "continuous_effect": {},
        "chronological_holdout": {},
        "monotonicity": {},
        "state_lineage": {},
    }
    contract = {
        "primary_endpoint": {
            "field": "return_20d_net_adj",
            "basis": "net_next_open_adjusted",
        },
        "sample_gates": {"minimum_primary_coverage": 0.95},
        "promotion": {
            "hard_rule_allowed": False,
            "candidate_retention_floor": 0.60,
            "required_evidence": ["cost_basis_remains_comparable"],
        },
    }

    evaluated = evaluate_promotion_gates(
        summary,
        panel=[],
        contract=contract,
        source_metadata={"formula_versions": ["fv_test"]},
    )

    gate = evaluated["promotion_gate_evaluation"]["cost_basis_comparable"]
    assert gate["passed"] is False
    assert "cost_basis_comparability_not_verified" in evaluated["promotion_blockers"]


@pytest.mark.parametrize(
    "price_adjustment_mode",
    ["raw", "unadjusted", "mystery_mode"],
)
def test_cost_basis_gate_fails_closed_for_incompatible_adjustment_mode(
    price_adjustment_mode: str,
) -> None:
    summary = {
        "promotion_blockers": [],
        "sample_accountability": {"primary_adjusted_coverage": 1.0},
        "sample_adequacy": {"adequate": True},
        "continuous_effect": {},
        "chronological_holdout": {},
        "monotonicity": {},
        "state_lineage": {},
    }
    contract = {
        "primary_endpoint": {
            "field": "return_20d_net_adj",
            "basis": "net_next_open_adjusted",
        },
        "sample_gates": {"minimum_primary_coverage": 0.95},
        "promotion": {
            "hard_rule_allowed": False,
            "candidate_retention_floor": 0.60,
            "required_evidence": ["cost_basis_remains_comparable"],
        },
    }
    source_metadata = {
        **COST_BASIS_METADATA,
        "primary_price_adjustment_modes": [price_adjustment_mode],
    }

    evaluated = evaluate_promotion_gates(
        summary,
        panel=[],
        contract=contract,
        source_metadata=source_metadata,
    )

    gate = evaluated["promotion_gate_evaluation"]["cost_basis_comparable"]
    assert gate["passed"] is False
    assert gate["price_adjustment_mode_compatible"] is False
    assert "cost_basis_comparability_not_verified" in evaluated["promotion_blockers"]
