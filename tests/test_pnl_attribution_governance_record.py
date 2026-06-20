from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.mcp.moss_project_mcp import (
    page_governance_record_validation,
    product_page_trace_bundles,
)

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "emit_pnl_attribution_governance_record.py"
STATIC_AUDIT_PACKET = ROOT / "docs" / "pnl" / "pnl-attribution-governance-audit-packet.md"


def _run_generator(*args: str) -> dict[str, object]:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )
    return json.loads(completed.stdout)


def _markdown_section(text: str, heading: str) -> str:
    start = text.index(heading)
    following_heading = text.find("\n## ", start + len(heading))
    if following_heading == -1:
        return text[start:].strip()
    return text[start:following_heading].strip()


def test_pnl_attribution_governance_record_dry_run_preflights_without_writing(
    tmp_path: Path,
) -> None:
    governance_dir = tmp_path / "governance"

    payload = _run_generator(
        "--governance-dir",
        str(governance_dir),
        "--created-at",
        "2026-06-05T00:00:00Z",
    )

    assert payload["scope"] == "pnl-attribution-governance-record-generation"
    assert payload["mode"] == "dry-run"
    assert payload["target_stream"] == "cache_manifest"
    assert payload["target_path"] == str(governance_dir / "cache_manifest.jsonl")
    assert payload["evidence_scope"]["writes_governance_records"] is False
    assert not governance_dir.exists()

    record = payload["record"]
    assert record == {
        "page_id": "PAGE-PNL-ATTR-WB-001",
        "page_slug": "pnl-attribution",
        "frontend_route": "/pnl-attribution",
        "primary_api": "/api/pnl-attribution/volume-rate",
        "report_date": "2026-04-30",
        "basis": "formal",
        "source_surface": "formal_attribution",
        "tables_used": [
            "fact_formal_pnl_fi",
            "fact_nonstd_pnl_bridge",
            "fact_formal_zqtz_balance_daily",
        ],
        "source_version": "sv_pnl_by_business_gs_attr_wb",
        "rule_version": "rv_pnl_attribution_workbench_v1",
        "cache_version": "cv_pnl_attribution_workbench_v1",
        "cache_key": "pnl-attribution:volume-rate:2026-04-30:mom",
        "result_kind": "pnl_attribution.volume_rate",
        "golden_sample_id": "GS-PNL-ATTR-WB-A",
        "created_at": "2026-06-05T00:00:00Z",
        "formal_use_allowed": False,
    }

    preflight = payload["preflight"]
    assert preflight["page_id"] == "PAGE-PNL-ATTR-WB-001"
    assert preflight["approval_status"] == "candidate_or_pending"
    assert preflight["record_formal_use_policy"] == "must_be_false_until_candidate_closure"
    assert preflight["validation"]["validation_status"] == "ready_for_audit_review"
    assert preflight["validation"]["missing_required_fields"] == []
    assert preflight["validation"]["failed_required_field_groups"] == []
    assert preflight["evidence_scope"]["writes_governance_records"] is False
    assert preflight["evidence_scope"]["approves_metric_or_page"] is False


def test_pnl_attribution_governance_record_explicit_write_is_mcp_validated(
    tmp_path: Path,
) -> None:
    governance_dir = tmp_path / "governance"

    payload = _run_generator(
        "--governance-dir",
        str(governance_dir),
        "--created-at",
        "2026-06-05T00:00:00Z",
        "--write",
    )

    stream_path = governance_dir / "cache_manifest.jsonl"
    assert payload["mode"] == "write"
    assert payload["target_path"] == str(stream_path)
    assert payload["evidence_scope"]["writes_governance_records"] is True
    assert stream_path.is_file()

    written_records = [
        json.loads(line)
        for line in stream_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert written_records == [payload["record"]]

    validation_payload = page_governance_record_validation(
        product_page_trace_bundles(),
        {"cache_manifest": stream_path},
        ["pnl-attribution"],
        ["cache_manifest"],
        max_results=10,
    )
    page = validation_payload["pages"][0]
    assert page["page_id"] == "PAGE-PNL-ATTR-WB-001"
    assert page["validation_status"] == "direct_records_ready_for_audit_review"
    assert page["direct_record_validations"][0]["validation_status"] == "ready_for_audit_review"
    assert page["direct_record_validations"][0]["record_formal_use_allowed"] is False
    assert page["evidence_scope"]["approves_metric_or_page"] is False
    assert page["evidence_scope"]["proves_page_execution"] is False


def test_pnl_attribution_governance_record_write_is_idempotent(
    tmp_path: Path,
) -> None:
    governance_dir = tmp_path / "governance"
    governance_dir.mkdir()
    (governance_dir / "cache_manifest.jsonl").write_text(
        json.dumps({"table_name": "fact_formal_pnl_fi"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    args = (
        "--governance-dir",
        str(governance_dir),
        "--created-at",
        "2026-06-05T00:00:00Z",
        "--write",
    )

    first_payload = _run_generator(*args)
    second_payload = _run_generator(*args)

    assert first_payload["record_write_status"] == "appended"
    assert second_payload["record_write_status"] == "already_exists"
    assert second_payload["existing_record_line"] == 2
    assert second_payload["record_key"] == {
        "page_id": "PAGE-PNL-ATTR-WB-001",
        "primary_api": "/api/pnl-attribution/volume-rate",
        "report_date": "2026-04-30",
        "cache_key": "pnl-attribution:volume-rate:2026-04-30:mom",
    }

    stream_path = governance_dir / "cache_manifest.jsonl"
    written_records = [
        json.loads(line)
        for line in stream_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert written_records == [{"table_name": "fact_formal_pnl_fi"}, first_payload["record"]]


def test_pnl_attribution_governance_record_updates_existing_evidence_fields(
    tmp_path: Path,
) -> None:
    governance_dir = tmp_path / "governance"
    first_payload = _run_generator(
        "--governance-dir",
        str(governance_dir),
        "--created-at",
        "2026-06-05T00:00:00Z",
        "--write",
    )

    second_payload = _run_generator(
        "--governance-dir",
        str(governance_dir),
        "--created-at",
        "2026-06-05T00:00:00Z",
        "--write",
        "--ui-api-payload-evidence",
        "codex-page-readiness:pnl-attribution:ui-api-payload",
        "--live-smoke-evidence",
        "codex-page-readiness:pnl-attribution:live-smoke",
    )

    assert first_payload["record_write_status"] == "appended"
    assert second_payload["record_write_status"] == "updated_existing"
    assert second_payload["existing_record_line"] == 1

    stream_path = governance_dir / "cache_manifest.jsonl"
    written_records = [
        json.loads(line)
        for line in stream_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(written_records) == 1
    assert written_records[0]["ui_api_payload_evidence"] == "codex-page-readiness:pnl-attribution:ui-api-payload"
    assert written_records[0]["live_smoke_evidence"] == "codex-page-readiness:pnl-attribution:live-smoke"


def test_pnl_attribution_governance_record_can_write_audit_packet(
    tmp_path: Path,
) -> None:
    governance_dir = tmp_path / "governance"
    packet_path = tmp_path / "pnl-attribution-governance-audit-packet.md"
    missing_duckdb = tmp_path / "missing.duckdb"

    payload = _run_generator(
        "--governance-dir",
        str(governance_dir),
        "--duckdb-path",
        str(missing_duckdb),
        "--created-at",
        "2026-06-05T00:00:00Z",
        "--write",
        "--ui-api-payload-evidence",
        "codex-page-readiness:pnl-attribution:ui-api-payload",
        "--live-smoke-evidence",
        "codex-page-readiness:pnl-attribution:live-smoke",
        "--audit-packet-path",
        str(packet_path),
    )

    assert payload["record_write_status"] == "appended"
    assert payload["audit_packet_path"] == str(packet_path)
    assert payload["audit_packet"]["page_id"] == "PAGE-PNL-ATTR-WB-001"
    assert payload["audit_packet"]["audit_review_status"] == "ready_for_audit_review"
    assert payload["audit_packet"]["closure_approved"] is False
    assert payload["audit_packet"]["summary"]["closure_approved"] is False
    assert payload["audit_packet"]["manual_review_blockers"] == ["business_owner_approval"]
    assert payload["audit_packet"]["summary"]["manual_review_blocker_count"] == 1
    assert payload["audit_packet"]["summary"]["manual_review_evidence_present_count"] == 2
    assert payload["audit_packet"]["evidence_scope"]["approves_metric_or_page"] is False

    packet = packet_path.read_text(encoding="utf-8")
    assert "# PnL Attribution Governance Audit Packet" in packet
    assert "PAGE-PNL-ATTR-WB-001" in packet
    assert "Audit review status: `ready_for_audit_review`" in packet
    assert "Approval status: `candidate_or_pending`" in packet
    assert "Formal use allowed: `false`" in packet
    assert "Closure approved: `false`" in packet
    assert "Manual blocker count: `1`" in packet
    assert "Manual blockers: `business_owner_approval`" in packet
    assert (
        "Evidence references attached for reviewer confirmation: "
        "`ui_api_payload_review, live_smoke_evidence_review`"
    ) in packet
    assert "Evidence present:" not in packet
    assert "Sign-off packet: `docs/pnl/pnl-attribution-sign-off-packet.md`" in packet
    assert "Owner evidence packet: `docs/pnl/pnl-attribution-owner-evidence-packet.md`" in packet
    assert "Approval status command: `python scripts/check_pnl_attribution_business_owner_approval.py`" in packet
    assert "Strict approval gate command: `python scripts/check_pnl_attribution_business_owner_approval.py --require-captured`" in packet
    assert (
        "PowerShell readiness strict approval gate command: "
        "`scripts\\codex-page-readiness.ps1 -PageSlug pnl-attribution -RequireApprovalCaptured`"
    ) in packet
    assert (
        "PowerShell all-page readiness strict approval gate command: "
        "`scripts\\codex-page-readiness.ps1 -All -RequireApprovalCaptured`"
    ) in packet
    assert "Business owner approval captured: `false`" in packet
    assert "Business owner approval status: `pending`" in packet
    assert "Business owner approval blockers: `business_owner_approval, business_owner_name, business_owner_role, approval_decision, approval_date, business_owner_signature, governance_record_review, golden_sample_review, ui_api_payload_review, live_smoke_evidence_review, verification_commands_rerun, candidate_boundary_acceptance`" in packet
    assert "- Verification commands rerun before approval: `yes` (`pending`)" in packet
    assert "## Evidence Scope" in packet
    assert "- `approves_metric_or_page=false`" in packet
    assert "- `writes_governance_records=false`" in packet
    assert "- `proves_page_execution=false`" in packet
    assert "- `captures_business_owner_approval=false`" in packet
    assert "Does not approve page closure or metric formal use." in packet
    assert "Does not cover advanced/Campisi full-surface closure." in packet
    assert "Confirm live smoke/browser evidence before signing." in packet
    assert (
        "Page smoke rerun: `scripts\\codex-page-smoke.ps1 -PageSlug pnl-attribution` (`passed`)"
        in packet
    )
    assert (
        "Page verification rerun: `scripts\\codex-verify-page.ps1 -PageSlug pnl-attribution -Run` (`passed`)"
        in packet
    )
    assert (
        "Page readiness rerun: `scripts\\codex-page-readiness.ps1 -PageSlug pnl-attribution -Run` (`passed`)"
        in packet
    )
    assert (
        "Page closure command status: `verification rerun complete; "
        "business-owner review and signature still pending`"
    ) in packet
    assert "Run page smoke: `scripts\\codex-page-smoke.ps1 -PageSlug pnl-attribution`" not in packet
    assert "Run page verification: `scripts\\codex-verify-page.ps1 -PageSlug pnl-attribution -Run`" not in packet
    assert "listed for follow-up; not executed by this packet" not in packet


def test_pnl_attribution_generated_audit_packet_follow_up_matches_static_packet(
    tmp_path: Path,
) -> None:
    governance_dir = tmp_path / "governance"
    packet_path = tmp_path / "pnl-attribution-governance-audit-packet.md"
    missing_duckdb = tmp_path / "missing.duckdb"

    _run_generator(
        "--governance-dir",
        str(governance_dir),
        "--duckdb-path",
        str(missing_duckdb),
        "--created-at",
        "2026-06-05T00:00:00Z",
        "--write",
        "--ui-api-payload-evidence",
        "codex-page-readiness:pnl-attribution:ui-api-payload",
        "--live-smoke-evidence",
        "codex-page-readiness:pnl-attribution:live-smoke",
        "--audit-packet-path",
        str(packet_path),
    )

    generated = packet_path.read_text(encoding="utf-8")
    static = STATIC_AUDIT_PACKET.read_text(encoding="utf-8")

    assert _markdown_section(generated, "## Required Follow-up") == _markdown_section(
        static,
        "## Required Follow-up",
    )
