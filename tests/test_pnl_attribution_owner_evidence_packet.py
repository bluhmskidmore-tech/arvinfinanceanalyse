from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.pnl_attribution_owner_evidence_packet import build_packet, render_markdown
from tests.governance_evidence_inputs import governance_evidence_inputs


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pnl_attribution_owner_evidence_packet.py"
OWNER_EVIDENCE_PACKET = ROOT / "docs" / "pnl" / "pnl-attribution-owner-evidence-packet.md"
ARCHIVED_BOUNDARY = (
    ROOT / "docs" / "audits" / "2026-06-05-pnl-attribution-gate-i-certification-boundary.json"
)
SIGNOFF_PACKET = ROOT / "docs" / "pnl" / "pnl-attribution-sign-off-packet.md"


def _run_packet(*args: str) -> tuple[int, dict[str, object]]:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )
    return completed.returncode, json.loads(completed.stdout)


def test_pnl_attribution_owner_evidence_packet_preserves_candidate_boundary(
    tmp_path: Path,
    governance_evidence_inputs,
) -> None:
    governance_dir = tmp_path / "governance"

    packet = build_packet(
        governance_dir=governance_dir,
        duckdb_path=Path(governance_evidence_inputs["MOSS_DUCKDB_PATH"]),
        created_at="2026-06-05T00:00:00Z",
    )

    assert packet["packet_kind"] == "pnl_attribution_owner_evidence_packet"
    assert packet["page_slug"] == "pnl-attribution"
    assert packet["route"] == "/pnl-attribution"
    assert packet["primary_api"] == "/api/pnl-attribution/volume-rate"
    assert packet["business_contract_status"] == "evidence-pending"
    assert packet["business_contract_certified"] is False
    assert packet["handoff_status"] == "owner_actions_required"
    assert packet["approval_status"] == "pending"
    assert packet["formal_use_allowed"] is False
    assert packet["closure_approved"] is False
    assert packet["business_owner_approval_captured"] is False
    assert packet["approval_action_item_count"] == 11
    assert packet["golden_sample_approval_artifact_status"] == "captured-awaiting-approval"
    assert packet["golden_sample_approval_artifact_mismatch"] is False
    assert packet["golden_sample_boundary"] == "primary_workbench_dto_only"
    assert (
        packet["primary_api_result_meta_scope"]
        == "primary_api_dto_formal_result_meta_only"
    )
    assert packet["primary_api_result_meta_formal_use_allowed"] is True
    assert packet["page_formal_use_allowed"] is False
    assert packet["page_owner_approval_required"] is True
    assert packet["governance_record_write_status"] == "not_requested"
    assert packet["governance_validation_status"] == "ready_for_audit_review"
    assert packet["governance_existing_record_line"] is None
    assert packet["catalog_date_sampled_table_count"] == 5
    assert packet["catalog_date_table_names"] == [
        "fact_formal_pnl_fi",
        "fact_nonstd_pnl_bridge",
        "fact_formal_zqtz_balance_daily",
        "fact_formal_bond_analytics_daily",
        "yield_curve_daily",
    ]
    assert packet["evidence_scope"] == {
        "approves_metric_or_page": False,
        "writes_governance_records": False,
        "proves_page_execution": False,
        "captures_business_owner_approval": False,
        "certification_effect": "none",
        "validates_required_fields": True,
    }
    assert packet["latest_verification_evidence"] == {
        "static_readiness": "static-pass",
        "page_smoke": "passed",
        "backend_workbench_numeric_campisi_tests": "94 passed",
        "frontend_page_tests": "27 passed",
        "browser_a11y_smoke": "1 passed",
        "frontend_typecheck": "passed",
        "frontend_debt_audit": "passed",
        "frontend_production_build": "passed",
        "full_readiness_run": "passed",
        "boundary": (
            "Full page readiness passed on 2026-06-06: static readiness, page smoke, "
            "MCP contract tests, backend tests, frontend tests, browser a11y smoke, "
            "typecheck, debt audit, and production build all completed. This is "
            "technical evidence only; owner approval remains pending."
        ),
    }
    assert packet["out_of_scope_surfaces"] == [
        "full page closure",
        "advanced attribution surfaces",
        "Campisi surfaces",
        "/api/pnl/overview formal PnL truth",
        "executive analytical overlay /ui/pnl/attribution",
        "business-owner approval",
    ]
    assert packet["owner_action_items"][0] == {
        "blocker": "business_owner_name",
        "template_field": "Business owner name",
        "required_value": "Business owner legal or operating name",
        "current_status": "missing",
    }
    assert "candidate_boundary_acceptance" in packet["remaining_blockers"]
    assert "formal_use_promotion_boundary" not in packet["remaining_blockers"]
    assert "closure_promotion_boundary" not in packet["remaining_blockers"]


def test_pnl_attribution_owner_evidence_packet_cli_writes_markdown(
    tmp_path: Path,
    governance_evidence_inputs,
) -> None:
    output_path = tmp_path / "packet.md"
    governance_dir = tmp_path / "governance"

    returncode, payload = _run_packet(
        "--output",
        str(output_path),
        "--governance-dir",
        str(governance_dir),
        "--created-at",
        "2026-06-05T00:00:00Z",
    )

    assert returncode == 0
    assert payload["packet_path"] == str(output_path)
    assert payload["handoff_status"] == "owner_actions_required"
    assert payload["business_contract_certified"] is False
    assert payload["approval_action_item_count"] == 11
    assert payload["governance_record_write_status"] == "not_requested"
    assert payload["evidence_scope"]["writes_governance_records"] is False
    assert payload["evidence_scope"]["certification_effect"] == "none"

    text = output_path.read_text(encoding="utf-8")
    assert "# PnL Attribution Owner Evidence Packet" in text
    assert "Business contract status: `evidence-pending`" in text
    assert "Formal use allowed: `formal_use_allowed=false`" in text
    assert "Closure approved: `closure_approved=false`" in text
    assert "Golden sample boundary: `primary_workbench_dto_only`" in text
    assert "Primary API DTO result_meta may be formal/formal_use_allowed=true." in text
    assert (
        "This does not approve PAGE-PNL-ATTR-WB-001 page closure, owner approval, "
        "or full-page formal use."
    ) in text
    assert "Primary API result_meta scope: `primary_api_dto_formal_result_meta_only`" in text
    assert "Page formal use allowed: `false`" in text
    assert "Page owner approval required: `true`" in text
    assert "Governance record write status: `not_requested`" in text
    assert "Governance validation status: `ready_for_audit_review`" in text
    assert "Latest Verification Evidence" in text
    assert "Backend workbench/numeric/Campisi tests: `94 passed`" in text
    assert "Frontend page tests: `27 passed`" in text
    assert "Browser a11y smoke: `1 passed`" in text
    assert "Full readiness run: `passed`" in text
    assert "technical evidence only; owner approval remains pending" in text
    assert "This packet does not approve page closure" in text
    assert "- `certification_effect=none`" in text
    assert "Advanced attribution surfaces" in text
    assert "Campisi surfaces" in text
    assert "Business Owner Approval Action Items" in text
    assert "Candidate-only boundary accepted: `yes` (`pending`)" in text
    assert "- - Candidate-only boundary accepted" not in text


def test_pnl_attribution_owner_evidence_packet_matches_generator_output(
    governance_evidence_inputs,
) -> None:
    packet = build_packet(
        governance_dir=Path(governance_evidence_inputs["MOSS_GOVERNANCE_PATH"]),
        duckdb_path=Path(governance_evidence_inputs["MOSS_DUCKDB_PATH"]),
    )
    # The synthetic stream has no record with the generator's fixed historical
    # key. Its current lookup must not inherit the archived private-stream line.
    assert packet["governance_existing_record_line"] is None
    archived = json.loads(ARCHIVED_BOUNDARY.read_text(encoding="utf-8"))
    governance = archived["governance_record_evidence"]
    assert packet["governance_record_key"] == governance["record_key"]
    assert packet["governance_record_write_status"] == governance["record_write_status"]
    assert packet["governance_validation_status"] == governance["validation_status"]
    assert governance["mode"] == "dry-run"
    assert governance["evidence_scope"]["writes_governance_records"] is False
    archived_line = governance["existing_record_line"]
    assert isinstance(archived_line, int) and archived_line > 0
    signoff = SIGNOFF_PACKET.read_text(encoding="utf-8")
    assert f"Governance record: `{governance['target_path']}:{archived_line}`" in signoff
    # Render the archived locator as archived metadata, while all other packet
    # fields still come from the real generator and current contract inputs.
    packet["governance_existing_record_line"] = archived_line
    expected = render_markdown(packet)
    actual = OWNER_EVIDENCE_PACKET.read_text(encoding="utf-8")

    assert actual == expected


def test_pnl_attribution_owner_evidence_packet_locates_current_synthetic_record(
    tmp_path: Path,
    governance_evidence_inputs,
) -> None:
    manifest = Path(governance_evidence_inputs["MOSS_GOVERNANCE_PATH"]) / "cache_manifest.jsonl"
    unrelated = next(
        record
        for line in manifest.read_text(encoding="utf-8").splitlines()
        if (record := json.loads(line))["page_slug"] == "pnl-attribution"
    )
    matching = dict(unrelated)
    matching.update({
        "report_date": "2026-04-30",
        "cache_key": "pnl-attribution:volume-rate:2026-04-30:mom",
    })
    governance_dir = tmp_path / "synthetic-key-governance"
    governance_dir.mkdir()
    current_manifest = governance_dir / "cache_manifest.jsonl"
    current_manifest.write_text(json.dumps(unrelated) + "\n", encoding="utf-8")
    missing = build_packet(
        governance_dir=governance_dir,
        duckdb_path=Path(governance_evidence_inputs["MOSS_DUCKDB_PATH"]),
    )
    assert missing["governance_existing_record_line"] is None
    with current_manifest.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(matching) + "\n")
    before_dry_run = current_manifest.read_bytes()

    packet = build_packet(
        governance_dir=governance_dir,
        duckdb_path=Path(governance_evidence_inputs["MOSS_DUCKDB_PATH"]),
    )

    assert packet["governance_existing_record_line"] == 2
    assert packet["governance_record_key"] == {
        "page_id": "PAGE-PNL-ATTR-WB-001",
        "primary_api": "/api/pnl-attribution/volume-rate",
        "report_date": "2026-04-30",
        "cache_key": "pnl-attribution:volume-rate:2026-04-30:mom",
    }
    assert matching["source_surface"] == "synthetic_readiness_fixture"
    assert matching["basis"] == "analytical"
    assert packet["governance_record_write_status"] == "not_requested"
    assert packet["formal_use_allowed"] is False
    assert packet["closure_approved"] is False
    assert packet["business_owner_approval_captured"] is False
    assert "Existing record line: `2`" in render_markdown(packet)
    assert current_manifest.read_bytes() == before_dry_run
