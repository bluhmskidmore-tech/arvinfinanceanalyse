import pytest

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_agent_eval,
]

from scripts.agent_eval.reward import evaluate_result
from scripts.agent_eval.spec import validate_result_spec


def test_evaluate_result_passes_when_required_moss_gates_are_satisfied():
    task = {
        "id": "ledger_pnl_unit_mismatch_001",
        "required_evidence": ["moss-metric-contracts", "moss-lineage-evidence"],
        "checks": ["npm run test -- LedgerPnlPage"],
        "business_gates": ["unit_consistency", "date_semantics"],
        "page_gates": ["no_console_errors"],
        "allowed_scope": ["frontend/src/features/ledger-pnl/", "frontend/src/test/"],
        "forbidden": ["backend/app/schema_registry/", "frontend/src/api/client.ts"],
    }
    result = {
        "evidence": ["moss-metric-contracts", "moss-lineage-evidence"],
        "checks": {"npm run test -- LedgerPnlPage": "passed"},
        "business_gates": {"unit_consistency": True, "date_semantics": True},
        "page_gates": {"no_console_errors": True},
        "changed_files": [
            "frontend/src/features/ledger-pnl/pages/LedgerPnlPage.tsx",
            "frontend/src/test/LedgerPnlPage.test.tsx",
        ],
    }

    scorecard = evaluate_result(task, result)

    assert scorecard["status"] == "pass"
    assert scorecard["score"] == 100
    assert scorecard["hard_failures"] == []


def test_evaluate_result_blocks_missing_contract_evidence_and_forbidden_changes():
    task = {
        "id": "ledger_pnl_unit_mismatch_001",
        "required_evidence": ["moss-metric-contracts", "moss-lineage-evidence"],
        "checks": ["npm run test -- LedgerPnlPage"],
        "business_gates": ["unit_consistency"],
        "page_gates": ["no_console_errors"],
        "allowed_scope": ["frontend/src/features/ledger-pnl/"],
        "forbidden": ["backend/app/schema_registry/", "frontend/src/api/client.ts"],
    }
    result = {
        "evidence": ["moss-lineage-evidence"],
        "checks": {"npm run test -- LedgerPnlPage": "failed"},
        "business_gates": {"unit_consistency": True},
        "page_gates": {"no_console_errors": True},
        "changed_files": [
            "frontend/src/features/ledger-pnl/pages/LedgerPnlPage.tsx",
            "frontend/src/api/client.ts",
        ],
    }

    scorecard = evaluate_result(task, result)

    assert scorecard["status"] == "fail"
    assert scorecard["score"] < 70
    assert "Missing required evidence: moss-metric-contracts" in scorecard["hard_failures"]
    assert "Required check failed: npm run test -- LedgerPnlPage" in scorecard["hard_failures"]
    assert "Forbidden path changed: frontend/src/api/client.ts" in scorecard["hard_failures"]


def test_evaluate_result_penalizes_out_of_scope_diff_without_hard_failure():
    task = {
        "id": "ledger_pnl_unit_mismatch_001",
        "required_evidence": [],
        "checks": [],
        "business_gates": ["unit_consistency"],
        "page_gates": [],
        "allowed_scope": ["frontend/src/features/ledger-pnl/"],
        "forbidden": ["backend/app/schema_registry/"],
    }
    result = {
        "business_gates": {"unit_consistency": True},
        "changed_files": [
            "frontend/src/features/ledger-pnl/pages/LedgerPnlPage.tsx",
            "frontend/src/features/risk-overview/pages/RiskOverviewPage.tsx",
        ],
    }

    scorecard = evaluate_result(task, result)

    assert scorecard["status"] == "fail"
    assert scorecard["hard_failures"] == []
    assert "Out-of-scope path changed: frontend/src/features/risk-overview/pages/RiskOverviewPage.tsx" in scorecard["warnings"]


def test_validate_result_spec_rejects_malformed_status_maps():
    with pytest.raises(ValueError, match="business_gates"):
        validate_result_spec(
            {
                "evidence": [],
                "checks": {},
                "business_gates": [],
                "page_gates": {},
                "changed_files": [],
            },
        )
