from __future__ import annotations

from pathlib import Path

from scripts.mcp.golden_approval import golden_sample_readiness
from scripts.mcp.moss_project_mcp import (
    page_evidence_readiness_row,
    page_trace_bundle,
    product_page_trace_bundles,
)


def test_page_evidence_readiness_separates_contract_formal_golden_and_owner_status() -> None:
    bundles = product_page_trace_bundles()

    for page_slug in ("PAGE-PNL-001", "PAGE-BRIDGE-001"):
        page = page_evidence_readiness_row(page_trace_bundle(bundles, page_slug))
        assert page["contract_status"] == "formal_or_governed"
        assert page["formal_envelope_allowed"] is True
        assert page["golden_approval_status"] == "captured-awaiting-approval"
        assert page["business_owner_closure_status"] == "direct_review_required"
        assert page["checks"]["golden_sample"]["status"] == "formal_sample"
        assert page["checks"]["golden_sample"]["approval_status"] == "captured-awaiting-approval"
        assert all(
            evidence["status"] == "captured-awaiting-approval"
            for evidence in page["checks"]["golden_sample"]["approval_evidence"]
        )

    approved = page_evidence_readiness_row(
        page_trace_bundle(bundles, "PAGE-PNL-BY-BUSINESS-001")
    )
    assert approved["golden_approval_status"] == "approved"
    assert approved["checks"]["golden_sample"]["approval_evidence"] == [
        {
            "sample_id": "GS-PNL-BUSINESS-INSIGHTS-A",
            "approval_path": "tests/golden_samples/GS-PNL-BUSINESS-INSIGHTS-A/approval.md",
            "status": "approved",
        }
    ]


def test_golden_approval_with_placeholder_signoff_fails_closed(tmp_path: Path) -> None:
    sample_dir = tmp_path / "tests" / "golden_samples" / "GS-INVALID-A"
    sample_dir.mkdir(parents=True)
    (sample_dir / "approval.md").write_text(
        "\n".join(
            (
                "# Approval",
                "",
                "- Sample ID: `GS-INVALID-A`",
                "- Status: `approved`",
                "- Owner: `TBD`",
                "- Approver: `Finance`",
                "- Approved at: `2026-07-16`",
            )
        ),
        encoding="utf-8",
    )

    readiness = golden_sample_readiness(
        {"golden_samples": ["tests/golden_samples/GS-INVALID-A"]},
        "formal_or_governed",
        repo_root=tmp_path,
        bundle_text="",
    )

    assert readiness["status"] == "formal_sample"
    assert readiness["approval_status"] == "invalid_or_missing_approval"
    assert readiness["approval_evidence"][0]["status"] == "invalid_approval_artifact"