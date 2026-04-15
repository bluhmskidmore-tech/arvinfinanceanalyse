from __future__ import annotations

from tests.liability_v1_disposition import (
    DISPOSITION_CATEGORIES,
    classify_diff,
    generate_semantic_disposition_report,
    monthly_tie_order_residual_paths,
)
from tests.liability_v1_harness import SampleCase


def test_classify_diff_marks_missing_pct_as_transitional_seam() -> None:
    diff = "$.top_10[0].pct: missing in actual payload"
    assert classify_diff("liabilities_counterparty", diff) == "transitional-seam"


def test_classify_diff_marks_yield_metric_values_as_pending_confirmation() -> None:
    diff = "$.kpi.asset_yield: expected 0.02, got 1.84"
    assert classify_diff("yield_metrics", diff) == "pending-confirmation"


def test_classify_diff_marks_counterparty_by_type_taxonomy_as_historical_compatibility() -> None:
    diff = "$.by_type[1].name: expected 'Non-Bank FI', got 'NonBank'"
    assert classify_diff("liabilities_counterparty", diff) == "historical-compatibility"


def test_disposition_categories_allow_only_known_buckets() -> None:
    assert DISPOSITION_CATEGORIES == {
        "implementation-defect",
        "data-issue",
        "historical-compatibility",
        "pending-confirmation",
        "architecture-invalid",
        "transitional-seam",
    }


def test_monthly_tie_order_residual_paths_detects_equal_value_counterparty_swap() -> None:
    expected_payload = {
        "months": [
            {
                "counterparty_details": [
                    {"name": "A BANK", "avg_value": 10.0, "weighted_cost": 0.0125, "type": "Bank"},
                    {"name": "B BANK", "avg_value": 10.0, "weighted_cost": 0.0138, "type": "Bank"},
                ],
                "counterparty_top10": [],
            }
        ]
    }
    actual_payload = {
        "months": [
            {
                "counterparty_details": [
                    {"name": "B BANK", "avg_value": 10.0, "weighted_cost": 0.0138, "type": "Bank"},
                    {"name": "A BANK", "avg_value": 10.0, "weighted_cost": 0.0125, "type": "Bank"},
                ],
                "counterparty_top10": [],
            }
        ]
    }

    residuals = monthly_tie_order_residual_paths(actual_payload, expected_payload)

    assert residuals == {
        "$.months[0].counterparty_details[0].name": "equal-value-tie-order",
        "$.months[0].counterparty_details[0].type": "equal-value-tie-order",
        "$.months[0].counterparty_details[0].weighted_cost": "equal-value-tie-order",
        "$.months[0].counterparty_details[1].name": "equal-value-tie-order",
        "$.months[0].counterparty_details[1].type": "equal-value-tie-order",
        "$.months[0].counterparty_details[1].weighted_cost": "equal-value-tie-order",
    }


def test_monthly_tie_order_residual_paths_does_not_mark_non_tie_value_drift() -> None:
    expected_payload = {
        "months": [
            {
                "counterparty_details": [
                    {"name": "A BANK", "avg_value": 10.0, "weighted_cost": 0.0125, "type": "Bank"},
                    {"name": "B BANK", "avg_value": 9.0, "weighted_cost": 0.0138, "type": "Bank"},
                ],
                "counterparty_top10": [],
            }
        ]
    }
    actual_payload = {
        "months": [
            {
                "counterparty_details": [
                    {"name": "B BANK", "avg_value": 9.0, "weighted_cost": 0.0138, "type": "Bank"},
                    {"name": "A BANK", "avg_value": 10.0, "weighted_cost": 0.0125, "type": "Bank"},
                ],
                "counterparty_top10": [],
            }
        ]
    }

    assert monthly_tie_order_residual_paths(actual_payload, expected_payload) == {}


def test_generate_semantic_disposition_report_marks_monthly_tie_order_as_transitional(monkeypatch) -> None:
    expected_payload = {
        "year": 2026,
        "months": [
            {
                "counterparty_details": [
                    {"name": "A BANK", "avg_value": 10.0, "weighted_cost": 0.0125, "type": "Bank"},
                    {"name": "B BANK", "avg_value": 10.0, "weighted_cost": 0.0138, "type": "Bank"},
                ],
                "counterparty_top10": [
                    {"name": "A BANK", "avg_value": 10.0, "weighted_cost": 0.0125, "type": "Bank"},
                    {"name": "B BANK", "avg_value": 10.0, "weighted_cost": 0.0138, "type": "Bank"},
                ],
            }
        ],
    }
    actual_payload = {
        "year": 2026,
        "months": [
            {
                "counterparty_details": [
                    {"name": "B BANK", "avg_value": 10.0, "weighted_cost": 0.0138, "type": "Bank"},
                    {"name": "A BANK", "avg_value": 10.0, "weighted_cost": 0.0125, "type": "Bank"},
                ],
                "counterparty_top10": [
                    {"name": "B BANK", "avg_value": 10.0, "weighted_cost": 0.0138, "type": "Bank"},
                    {"name": "A BANK", "avg_value": 10.0, "weighted_cost": 0.0125, "type": "Bank"},
                ],
            }
        ],
    }

    case = SampleCase(
        sample_id="monthly-tie-order",
        interface="liabilities_monthly",
        request={"year": 2026},
        expected={"compatibility": {"payload": expected_payload}},
        source={},
        raw={},
    )

    class _StubResponse:
        status_code = 200

        def json(self):
            return actual_payload

    class _StubClient:
        def get(self, path, params):
            return _StubResponse()

    monkeypatch.setattr("tests.liability_v1_disposition.load_json_file", lambda _path: {"status": "stub"})
    monkeypatch.setattr("tests.liability_v1_disposition.sample_cases_from_manifest", lambda _manifest: [case])
    monkeypatch.setattr("tests.liability_v1_disposition._build_client", lambda: _StubClient())

    report = generate_semantic_disposition_report()
    iface = report["interfaces"][0]
    findings = iface["representative_findings"]
    tie_findings = [item for item in findings if item.get("residual_kind") == "equal-value-tie-order"]

    assert iface["residual_kind_counts"] == {"equal-value-tie-order": 8}
    assert tie_findings
    assert all(item["category"] == "transitional-seam" for item in tie_findings)
