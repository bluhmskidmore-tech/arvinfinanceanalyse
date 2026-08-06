from __future__ import annotations

from scripts.run_fable_extension_study import _render_extension_readme


def test_readme_surfaces_decision_relevant_quality_and_stability_findings() -> None:
    summary = {
        "status": "research_only_data_quality_blocked",
        "promotion_verdict": "insufficient_evidence",
        "promotion_blockers": ["primary_adjusted_coverage_below_gate"],
        "sample_accountability": {
            "primary_universe_row_count": 771,
            "primary_adjusted_coverage": 0.708171,
        },
        "continuous_effect": {
            "20d_adjusted_primary": {
                "slope_per_10pp_extension": -0.005963,
                "bootstrap_ci_95": [-0.016938, 0.00586],
            }
        },
        "chronological_holdout": {
            "20d_adjusted_primary": {"direction_consistent": False}
        },
        "state_lineage": {"conflict_count": 377, "conflict_rate": 0.488975},
    }
    manifest = {
        "study_version": "rv_fable_extension_study_v1",
        "result_sha256": "abc",
    }

    readme = _render_extension_readme(summary=summary, manifest=manifest)

    assert "primary_adjusted_coverage: 0.708171" in readme
    assert "slope_per_10pp_extension: -0.005963" in readme
    assert "bootstrap_ci_95: [-0.016938, 0.00586]" in readme
    assert "holdout_direction_consistent: false" in readme
    assert "state_lineage_conflict_rate: 0.488975" in readme
    assert "promotion_blockers: primary_adjusted_coverage_below_gate" in readme
