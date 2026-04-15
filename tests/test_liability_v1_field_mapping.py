from __future__ import annotations

from tests.liability_v1_harness import (
    INTERFACE_SPECS,
    SampleCase,
    authority_field_paths,
    compatibility_diffs,
    load_authority_matrix_text,
    load_template_manifest,
    monthly_basis_gate,
    sample_cases_from_manifest,
    semantic_gate_findings,
)


def test_template_manifest_covers_all_liability_compatibility_interfaces() -> None:
    manifest = load_template_manifest()
    cases = sample_cases_from_manifest(manifest)

    assert {case.interface for case in cases} == set(INTERFACE_SPECS)
    for case in cases:
        assert case.compatibility_oracle == case.spec.compatibility_oracle
        assert case.semantic_oracle == case.spec.semantic_oracle
        assert case.source["binding_level"] == "compatibility_only"


def test_template_manifest_authority_fields_exist_in_matrix() -> None:
    manifest = load_template_manifest()
    cases = sample_cases_from_manifest(manifest)
    matrix_text = load_authority_matrix_text()

    for case in cases:
        assert case.spec.path in matrix_text
        assert authority_field_paths(case)
        assert not semantic_gate_findings(case)


def test_template_manifest_marks_monthly_basis_gate_as_observed() -> None:
    manifest = load_template_manifest()
    cases = sample_cases_from_manifest(manifest)

    monthly_case = next(case for case in cases if case.interface == "liabilities_monthly")
    gate = monthly_basis_gate(monthly_case)

    assert monthly_case.spec.monthly_basis_gate_required is True
    assert gate["status"] == "approved"
    assert gate["basis"] == "observed"
    assert gate["reason"]


def test_compatibility_diff_helper_does_not_hide_shape_drift() -> None:
    expected_payload = {
        "report_date": "2026-01-31",
        "top_10": [{"name": "Bank A", "value": 100.0}],
    }
    actual_payload = {
        "report_date": "2026-01-31",
        "top_10": [{"name": "Bank A", "value": 100.0, "weighted_cost": 0.025}],
        "by_type": [],
    }

    diffs = compatibility_diffs(actual_payload, expected_payload)

    assert diffs == [
        "$.by_type: unexpected field in actual payload",
        "$.top_10[0].weighted_cost: unexpected field in actual payload",
    ]


def test_sample_case_exposes_separate_compatibility_and_semantic_views() -> None:
    case = SampleCase(
        sample_id="liabilities-monthly-template",
        interface="liabilities_monthly",
        request={"year": 2026},
        expected={
            "compatibility": {"oracle": "v1_payload", "payload": {"year": 2026, "months": []}},
            "semantic": {
                "oracle": "authority_matrix",
                "status": "pending",
                "basis_gate": {"status": "approved", "basis": "observed", "reason": "Observed basis approved."},
            },
        },
        source={"binding_level": "compatibility_only"},
        raw={},
    )

    assert case.compatibility_payload == {"year": 2026, "months": []}
    assert case.semantic_contract["status"] == "pending"
    assert monthly_basis_gate(case)["status"] == "approved"
    assert monthly_basis_gate(case)["basis"] == "observed"
