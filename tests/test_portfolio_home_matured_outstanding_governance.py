from __future__ import annotations

from scripts.portfolio_home_owner_action_packet import _blocker_closure_matrix
from scripts.portfolio_home_blocker_closure_matrix_check import matrix_completeness_report


REPORT_DATE = "2026-05-31"


def test_matured_outstanding_blocker_has_data_owner_closure_evidence() -> None:
    matrix = _blocker_closure_matrix(
        score_blockers=["bond_matured_outstanding_reconciliation_required"],
        scorecard_actions=[
            {
                "blocker": "bond_matured_outstanding_reconciliation_required",
                "owner": "data_owner",
                "next_action": "Reconcile matured outstanding positions.",
                "exit_criteria": "Queue exits 0 after source reconciliation.",
            }
        ],
        report_date=REPORT_DATE,
    )

    row = matrix[0]
    assert row["owner"] == "data_owner"
    assert row["decision_artifacts"] == []
    assert row["required_fields"] == []
    assert row["recheck_commands"] == [
        (
            "python scripts/portfolio_home_matured_outstanding_queue.py "
            f"--report-date {REPORT_DATE} --require-empty"
        ),
        (
            "python scripts/portfolio_home_full_closure_evidence.py "
            f"--report-date {REPORT_DATE} --require-clean"
        ),
    ]
    assert row["evidence_sources"][0]["name"] == "matured_outstanding_queue"
    assert row["evidence_sources"][0]["fields"] == ["summary", "rows"]
    assert "exception" not in row["removes_blocker_when"].lower()
    assert "strict queue exits 0" in row["removes_blocker_when"]


def test_closure_matrix_allowlist_accepts_report_date_qualification() -> None:
    command = "python scripts/portfolio_home_matured_outstanding_queue.py --require-empty"
    qualified = (
        "python scripts/portfolio_home_matured_outstanding_queue.py "
        f"--report-date {REPORT_DATE} --require-empty"
    )
    report = matrix_completeness_report(
        score_blockers=["bond_matured_outstanding_reconciliation_required"],
        matrix=[
            {
                "blocker": "bond_matured_outstanding_reconciliation_required",
                "owner": "data_owner",
                "next_action": "Reconcile positions.",
                "decision_artifacts": [],
                "required_fields": [],
                "recheck_commands": [qualified],
                "evidence_sources": [{"command": qualified}],
                "exit_criteria": "Queue exits 0.",
                "removes_blocker_when": "Queue is empty.",
            }
        ],
        verification_commands=[command],
    )

    assert report["status"] == "clean"
    assert report["blockers"] == []
