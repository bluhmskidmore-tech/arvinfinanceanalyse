import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT_DIR = ROOT / "docs" / "audits"
MANIFEST_PATH = AUDIT_DIR / "2026-06-10-system-audit-manifest.json"
COVERAGE_REPORT_PATH = AUDIT_DIR / "business-display-coverage-report.json"
EXPECTED_SECURITY_SCAN_ERRORS = [
    (
        "local-secret-hygiene required input artifact is missing: "
        "test_output/security-scans/osv-report.json"
    ),
    (
        "local-secret-hygiene required input artifact is missing: "
        "test_output/security-scans/gitleaks-report.json"
    ),
]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_system_audit_manifest_references_existing_artifacts_and_stays_fail_closed() -> None:
    manifest = _load_json(MANIFEST_PATH)

    assert manifest["report_kind"] == "system_wide_skills_audit_manifest"
    assert manifest["generated_at"] == "2026-08-06T22:30:00+08:00"
    assert manifest["status"] == {
        "overall": "evidence_package_ready_but_business_closure_not_achieved",
        "fail_closed": True,
        "approves_metrics": False,
        "approves_pages": False,
        "captures_business_owner_approval": False,
        "writes_governance_records": False,
        "certifies_routes": False,
    }

    required_artifacts = {
        "index",
        "executive_summary_zh",
        "owner_review_brief_zh",
        "owner_decision_capture_template_zh",
        "main_report",
        "action_register",
        "completion_checklist",
        "completion_snapshot",
        "owner_governance_follow_up_packet",
        "owner_governance_follow_up_brief_zh",
        "calculation_logic_audit",
        "calculation_owner_decision_matrix",
        "calculation_owner_decision_snapshot",
        "calculation_owner_decision_snapshot_script",
        "calculation_owner_decision_packet",
        "calculation_owner_decision_packet_script",
        "calculation_owner_decision_packet_tests",
        "calculation_owner_meeting_checklist",
        "calculation_owner_meeting_checklist_script",
        "calculation_owner_meeting_checklist_tests",
        "calculation_first_priority_readiness_packet",
        "calculation_first_priority_readiness_packet_script",
        "calculation_first_priority_readiness_packet_tests",
        "calculation_post_owner_execution_plan",
        "calculation_post_owner_execution_plan_script",
        "calculation_post_owner_execution_plan_tests",
        "owner_approval_evidence_summary",
        "owner_approval_fail_closed_snapshot",
        "direct_app_mcp_gitnexus_tool_surface_snapshot",
        "direct_app_mcp_gitnexus_tool_surface_runbook",
        "direct_app_mcp_gitnexus_tool_surface_refresh_script",
        "ledger_pnl_direct_governance_record_snapshot",
        "ledger_pnl_direct_governance_record_runbook",
        "local_secret_hygiene_snapshot",
        "local_secret_hygiene_runbook",
        "local_secret_hygiene_owner_attestation_packet",
        "local_secret_hygiene_owner_attestation_packet_script",
        "local_secret_hygiene_owner_attestation_packet_tests",
        "local_secret_hygiene_refresh_script",
        "business_display_coverage",
        "real_backend_smoke_runbook",
        "real_backend_smoke_result",
        "system_audit_pulse_snapshot",
        "system_audit_pulse_script",
        "system_audit_pulse_tests",
        "system_audit_monitoring_snapshot",
        "system_audit_monitoring_script",
        "system_audit_monitoring_tests",
        "system_audit_monitoring_verifier_script",
        "system_audit_monitoring_verifier_tests",
        "system_audit_blocker_intake_board_script",
        "system_audit_blocker_intake_board_tests",
    }
    assert required_artifacts <= set(manifest["artifacts"])

    missing = [
        rel_path
        for rel_path in manifest["artifacts"].values()
        if not (ROOT / rel_path).exists()
    ]
    assert missing == []


def test_system_audit_manifest_counts_match_coverage_and_fresh_verification() -> None:
    manifest = _load_json(MANIFEST_PATH)
    coverage = _load_json(COVERAGE_REPORT_PATH)
    pulse_snapshot = _load_json(ROOT / manifest["artifacts"]["system_audit_pulse_snapshot"])
    action_register = (ROOT / manifest["artifacts"]["action_register"]).read_text(
        encoding="utf-8"
    )
    decision_matrix = (
        ROOT / manifest["artifacts"]["calculation_owner_decision_matrix"]
    ).read_text(encoding="utf-8")
    decision_packet = (
        ROOT / manifest["artifacts"]["calculation_owner_decision_packet"]
    ).read_text(encoding="utf-8")
    owner_meeting_checklist = (
        ROOT / manifest["artifacts"]["calculation_owner_meeting_checklist"]
    ).read_text(encoding="utf-8")
    first_priority_packet = (
        ROOT / manifest["artifacts"]["calculation_first_priority_readiness_packet"]
    ).read_text(encoding="utf-8")
    post_owner_plan = (
        ROOT / manifest["artifacts"]["calculation_post_owner_execution_plan"]
    ).read_text(encoding="utf-8")

    counts = manifest["counts"]
    assert counts["business_display_tracked_routes"] == coverage["summary"]["tracked_route_count"]
    assert counts["business_display_route_gaps"] == coverage["summary"]["route_gap_count"]
    assert (
        counts["browser_smoke_a11y_configured_routes"]
        == coverage["summary"]["browser_smoke_a11y_configured_route_count"]
    )

    fresh_by_command = {
        item["command"]: item["summary"]
        for item in manifest["fresh_verification"]["commands"]
    }
    assert set(fresh_by_command) == {
        "python scripts\\codex_page_readiness.py --all",
        "python scripts\\codex_page_readiness.py --route-scope",
        "python scripts\\business_display_coverage_report.py",
        "python scripts\\system_audit_pulse.py",
    }
    all_pages = fresh_by_command["python scripts\\codex_page_readiness.py --all"]
    route_scope = fresh_by_command["python scripts\\codex_page_readiness.py --route-scope"]
    coverage_summary = fresh_by_command["python scripts\\business_display_coverage_report.py"]
    pulse = fresh_by_command["python scripts\\system_audit_pulse.py"]

    assert all_pages["page_count"] == counts["seeded_pages"]
    assert all_pages["static_pass_count"] == counts["static_pass_pages"]
    assert all_pages["owner_approval_pending_count"] == counts["owner_approval_pending_pages"]
    assert all_pages["owner_approval_action_item_sum"] == counts["owner_approval_action_items"]
    assert all_pages["direct_evidence_explicit_count"] == counts["seeded_pages"]
    assert all_pages["direct_evidence_null_count"] == 0
    assert all_pages["audit_review_null_count"] == 0
    assert (
        all_pages["missing_direct_records_count"]
        + all_pages["direct_records_ready_for_audit_review_count"]
        == counts["seeded_pages"]
    )
    assert route_scope["business_contract_certified_count"] == counts[
        "business_contract_certified_routes"
    ]
    assert coverage_summary["tracked_route_count"] == counts["business_display_tracked_routes"]
    assert coverage_summary["route_gap_count"] == counts["business_display_route_gaps"]
    assert pulse == {
        "status": "pass",
        "completion_state": "not_complete",
        "open_blocker_count": len(manifest["open_blockers"]),
        "route_count": 40,
        "business_contract_certified_count": counts["business_contract_certified_routes"],
        "business_display_route_gap_count": counts["business_display_route_gaps"],
        "completion_snapshot_error_count": 0,
        "readiness_source": "manifest_last_full_readiness",
    }
    assert manifest["fresh_verification"]["verified_at"] == (
        "2026-06-10T19:08:54+08:00"
    )
    assert pulse_snapshot["report_kind"] == "system_audit_pulse"
    assert pulse_snapshot["status"] == "fail"
    assert pulse_snapshot["completion_state"] == pulse["completion_state"]
    assert pulse_snapshot["full_score_ready"] is False
    assert pulse_snapshot["open_blocker_count"] == len(manifest["open_blockers"])
    assert pulse_snapshot["route_scope"]["route_count"] == 40
    assert pulse_snapshot["route_scope"]["visible_unseeded_route_count"] == 1
    assert (
        pulse_snapshot["route_scope"]["business_contract_certified_count"]
        == counts["business_contract_certified_routes"]
    )
    assert (
        pulse_snapshot["business_display"]["tracked_route_count"]
        == counts["business_display_tracked_routes"]
    )
    assert (
        pulse_snapshot["business_display"]["route_gap_count"]
        == counts["business_display_route_gaps"]
    )
    assert pulse_snapshot["completion_snapshot"]["status"] == "fail"
    assert pulse_snapshot["completion_snapshot"]["error_count"] == 2
    assert pulse_snapshot["all_page_readiness"]["source"] == "manifest_last_full_readiness"
    assert pulse_snapshot["drift_errors"][:2] == EXPECTED_SECURITY_SCAN_ERRORS
    assert pulse_snapshot["evidence_scope"] == {
        "read_only": True,
        "writes_duckdb": False,
        "writes_governance_records": False,
        "approves_metrics": False,
        "approves_pages": False,
        "captures_business_owner_approval": False,
        "certifies_routes": False,
        "clears_secret_scan": False,
        "promotes_candidate_data": False,
    }
    assert "does not approve metrics" in pulse_snapshot["claim_boundary"]
    assert "does not approve routes" in manifest["fresh_verification"]["interpretation"]

    priority_rows = [
        line
        for line in action_register.splitlines()
        if line.startswith("| P0-gate |")
        or line.startswith("| P1-")
        or line.startswith("| P2-")
    ]
    assert len(priority_rows) == counts["action_register_priority_rows"]

    open_decision_section, verified_closed_section = decision_matrix.split(
        "## Verified Closed Before Owner Review", maxsplit=1
    )
    open_decision_rows = [
        line
        for line in open_decision_section.splitlines()
        if line.startswith("| P1-")
    ]
    open_decision_ids = [line.split("|")[1].strip() for line in open_decision_rows]
    expected_open_decision_ids = [
        "P1-01",
        "P1-02",
        "P1-03",
        "P1-04",
        "P1-05",
        "P1-06",
        "P1-10",
        "P1-11",
    ]
    assert len(open_decision_rows) == counts["calculation_display_open_p1"]
    assert open_decision_ids == expected_open_decision_ids
    assert all(not line.startswith("| P1-08 |") for line in open_decision_rows)
    assert "P1-08" in verified_closed_section
    assert "original 2026-06-10 10-row baseline remains explicitly historical" in (
        decision_matrix
    )
    assert "Current rows still needing owner-decision work" in decision_matrix
    assert "P1-07" in verified_closed_section
    assert "P1-09" in verified_closed_section
    assert "passed with 2 test files and 16 tests" in decision_matrix

    prework_marker = "## Engineering Prework / Impact Slice Map"
    assert prework_marker in verified_closed_section
    prework_section = verified_closed_section.split(prework_marker, maxsplit=1)[1]
    assert "does not choose or approve any convention" in prework_section
    assert "does not change code" in prework_section
    assert "does not certify routes/pages" in prework_section
    assert "| P1-" not in prework_section
    for p1_id in expected_open_decision_ids:
        assert f"**{p1_id}" in prework_section

    assert "Calculation P1 Owner Decision Packet" in decision_packet
    assert "`decision_item_count=8`" in decision_packet
    assert "`pending_decision_count=8`" in decision_packet
    assert "`captured_decision_count=0`" in decision_packet
    assert (
        "`post_owner_required_fields=selected_decision, owner_rationale, "
        "implementation_owner, verification_gate, status`"
    ) in decision_packet
    assert "First priority group: `P1-10, P1-11`" in decision_packet
    assert "Owner decision gate" in decision_packet
    assert "Backend DTO added or confirmed" in decision_packet
    assert "`captures_owner_decisions=false`" in decision_packet
    assert "`chooses_or_approves_conventions=false`" in decision_packet
    assert "treat proposed review defaults as approved rules" in decision_packet
    assert "does not choose or approve conventions" in decision_packet
    assert "authorizing Ledger PnL `--write`" not in decision_packet
    assert "authorize Ledger PnL `--write`" in decision_packet
    for p1_id in expected_open_decision_ids:
        assert f"`{p1_id}`" in decision_packet

    assert "Calculation P1 Owner Meeting Checklist" in owner_meeting_checklist
    assert "Owner meeting material ready: `true`" in owner_meeting_checklist
    assert "Implementation ready: `false`" in owner_meeting_checklist
    assert "`decision_item_count=8`" in owner_meeting_checklist
    assert "`total_missing_capture_field_count=40`" in owner_meeting_checklist
    assert "`meeting_missing_field_count=8`" in owner_meeting_checklist
    assert "`captures_owner_decisions=false`" in owner_meeting_checklist
    assert "`chooses_or_approves_conventions=false`" in owner_meeting_checklist
    assert "Owner decision gate" in owner_meeting_checklist
    assert "`docs/calc_rules.md` unit rule" in owner_meeting_checklist
    assert "Every row must have `selected_decision`" in owner_meeting_checklist
    assert "treat this checklist as owner approval" in owner_meeting_checklist
    assert "does not choose or approve calculation conventions" in owner_meeting_checklist
    for p1_id in expected_open_decision_ids:
        assert f"`{p1_id}`" in owner_meeting_checklist

    assert "Calculation P1 First Priority Readiness Packet" in first_priority_packet
    assert "source_snapshot_status=owner_decision_required" in first_priority_packet
    assert "`first_priority_ids=P1-10, P1-11`" in first_priority_packet
    assert (
        "`post_owner_required_fields=selected_decision, owner_rationale, "
        "implementation_owner, verification_gate, status`"
    ) in first_priority_packet
    assert "`owner_intake_ready=true`" in first_priority_packet
    assert "`implementation_ready=false`" in first_priority_packet
    assert "Owner Decision Gate" in first_priority_packet
    assert "backend DTO / frontend removal tests" in first_priority_packet
    assert "API contract plus frontend test" in first_priority_packet
    assert "`captures_owner_decisions=false`" in first_priority_packet
    assert "`chooses_or_approves_conventions=false`" in first_priority_packet
    assert "yieldAnalysisAggregates.ts" in first_priority_packet
    assert "zqtzAdbAvgRollup.ts" in first_priority_packet
    assert "CreditSpreadView.tsx" in first_priority_packet
    assert "rating/tenor bucket-boundary regression remains pending" in (
        first_priority_packet
    )
    assert "count this readiness packet as owner decision capture" in (
        first_priority_packet
    )
    assert "does not choose or approve any calculation convention" in (
        first_priority_packet
    )

    assert "Calculation P1 Post-Owner Execution Plan" in post_owner_plan
    assert "`ready_for_implementation_count=0`" in post_owner_plan
    assert "`incomplete_count=8`" in post_owner_plan
    assert "`global_owner_decision_gate_ready=false`" in post_owner_plan
    assert "`implementation_ready=false`" in post_owner_plan
    assert "`captures_owner_decisions=false`" in post_owner_plan
    assert "`chooses_or_approves_conventions=false`" in post_owner_plan
    assert "execute implementation when the meeting record is incomplete" in (
        post_owner_plan
    )
    assert "does not choose or approve conventions" in post_owner_plan
    for p1_id in expected_open_decision_ids:
        assert f"`{p1_id}`" in post_owner_plan

    calculation_blocker = next(
        item
        for item in manifest["open_blockers"]
        if item["id"] == "calculation-display-p1-decisions"
    )
    assert calculation_blocker["decision_rows"] == len(open_decision_rows)

    p108_evidence = next(
        item
        for item in manifest["verification_evidence"]
        if item["scope"] == "bond_dashboard_null_handling_formatter_and_page_slice"
    )
    assert calculation_blocker["last_checked_at"] in p108_evidence["result"]
    assert calculation_blocker["last_checked_at"] in decision_matrix

    pulse_evidence = next(
        item
        for item in manifest["verification_evidence"]
        if item["scope"] == "system_audit_pulse_read_only_guard"
    )
    assert "pytest tests/test_system_audit_pulse.py -q" in pulse_evidence["command"]
    assert "python scripts\\system_audit_pulse.py" in pulse_evidence["command"]
    assert "--format markdown" in pulse_evidence["command"]
    assert "9 passed" in pulse_evidence["result"]
    assert "completion_state=not_complete" in pulse_evidence["result"]
    assert f"open_blocker_count={len(manifest['open_blockers'])}" in pulse_evidence[
        "result"
    ]
    assert "business_contract_certified_count=0" in pulse_evidence["result"]
    assert "route_gap_count=0" in pulse_evidence["result"]
    assert "markdown watch board renders" in pulse_evidence["result"]
    assert "pulse status fail" in pulse_evidence["result"]
    assert "drift_error_count=5" in pulse_evidence["result"]
    assert "no approval/write/secret-clear/certification flags" in pulse_evidence[
        "result"
    ]

    monitoring_snapshot = _load_json(
        ROOT / manifest["artifacts"]["system_audit_monitoring_snapshot"]
    )
    assert monitoring_snapshot["report_kind"] == "system_audit_monitoring_snapshot"
    assert monitoring_snapshot["generated_at"] == "2026-08-06T22:30:00+08:00"
    assert monitoring_snapshot["evidence_scope"] == {
        "read_only": True,
        "writes_duckdb": False,
        "writes_governance_records": False,
        "writes_or_rotates_secrets": False,
        "reads_secret_values": False,
        "approves_metrics": False,
        "approves_pages": False,
        "captures_business_owner_approval": False,
        "certifies_routes": False,
        "clears_secret_scan": False,
        "promotes_candidate_data": False,
    }
    assert monitoring_snapshot["completion_verification"]["status"] == "fail"
    assert monitoring_snapshot["completion_verification"]["open_blocker_count"] == len(
        manifest["open_blockers"]
    )
    assert (
        monitoring_snapshot["completion_verification"][
            "follow_up_completion_order_status"
        ]
        == "pass"
    )
    assert (
        monitoring_snapshot["completion_verification"][
            "follow_up_completion_order_error_count"
        ]
        == 0
    )
    assert monitoring_snapshot["completion_verification"]["error_count"] == 2
    assert (
        monitoring_snapshot["completion_verification"]["errors"]
        == EXPECTED_SECURITY_SCAN_ERRORS
    )
    assert (
        monitoring_snapshot["completion_verification"][
            "calculation_post_owner_ready_for_implementation_count"
        ]
        == 0
    )
    assert (
        monitoring_snapshot["completion_verification"][
            "calculation_post_owner_incomplete_count"
        ]
        == 8
    )
    assert (
        monitoring_snapshot["completion_verification"][
            "calculation_post_owner_global_gate_ready"
        ]
        is False
    )
    assert (
        monitoring_snapshot["completion_verification"][
            "calculation_post_owner_implementation_ready"
        ]
        is False
    )
    assert monitoring_snapshot["pulse"]["status"] == "fail"
    assert monitoring_snapshot["pulse"]["completion_state"] == "not_complete"
    assert monitoring_snapshot["pulse"]["open_blocker_count"] == len(
        manifest["open_blockers"]
    )
    assert monitoring_snapshot["pulse"]["drift_error_count"] == 5
    assert monitoring_snapshot["pulse"]["drift_errors"][:2] == (
        EXPECTED_SECURITY_SCAN_ERRORS
    )
    assert monitoring_snapshot["blocker_intake_board"]["status"] == (
        "open_external_input_required"
    )
    assert monitoring_snapshot["blocker_intake_board"]["blocker_count"] == len(
        manifest["open_blockers"]
    )
    assert monitoring_snapshot["blocker_intake_board"]["completion_order"] == [
        "calculation-display-p1-decisions",
        "ledger-pnl-direct-governance-record",
        "owner-approval-7-pages",
        "direct-app-mcp-gitnexus-evidence",
        "local-secret-hygiene",
    ]
    assert monitoring_snapshot["blocker_intake_board"]["next_blocker_id"] == (
        "calculation-display-p1-decisions"
    )
    assert monitoring_snapshot["blocker_intake_board"]["next_blocker_detail"] == (
        monitoring_snapshot["pulse"]["next_blocker_detail"]
    )
    assert monitoring_snapshot["blocker_intake_board"]["next_blocker_detail"][
        "responsible_owner_type"
    ] == "business_owner_and_metric_governance"
    assert monitoring_snapshot["blocker_intake_board"]["next_blocker_detail"][
        "strict_gate_command"
    ] == (
        "python scripts\\refresh_calculation_p1_owner_decision_snapshot.py "
        "--require-owner-decisions-captured"
    )
    assert monitoring_snapshot["blocker_intake_board"]["evidence_scope"] == {
        "read_only": True,
        "approves_metrics": False,
        "approves_pages": False,
        "captures_business_owner_approval": False,
        "writes_governance_records": False,
        "authorizes_ledger_pnl_governance_write": False,
        "captures_direct_app_mcp_gitnexus_evidence": False,
        "requests_or_captures_secret_values": False,
        "clears_secret_scan": False,
        "certifies_routes": False,
    }
    assert "does not approve metrics" in monitoring_snapshot["blocker_intake_board"][
        "boundary"
    ]
    latest_recheck = monitoring_snapshot["latest_session_recheck"]
    assert latest_recheck["checked_at"]
    assert latest_recheck["closure_effect"] == "none"
    assert latest_recheck["open_blocker_count"] == len(manifest["open_blockers"])
    assert latest_recheck["next_blocker"] == monitoring_snapshot["pulse"][
        "next_blocker_detail"
    ]
    blocker_times = {
        blocker["id"]: blocker["last_checked_at"]
        for blocker in manifest["open_blockers"]
    }
    assert latest_recheck["direct_app_mcp_gitnexus_tool_surface"][
        "checked_at"
    ] == blocker_times["direct-app-mcp-gitnexus-evidence"]
    assert latest_recheck["local_secret_hygiene"]["checked_at"] == blocker_times[
        "local-secret-hygiene"
    ]
    assert latest_recheck["ledger_pnl_direct_governance_record"][
        "checked_at"
    ] == blocker_times["ledger-pnl-direct-governance-record"]
    assert latest_recheck["calculation_owner_decision"]["checked_at"] == blocker_times[
        "calculation-display-p1-decisions"
    ]
    assert latest_recheck["direct_app_mcp_gitnexus_tool_surface"][
        "returned_primary_tool_count"
    ] == 0
    assert latest_recheck["direct_app_mcp_gitnexus_tool_surface"][
        "returned_gitnexus_tool_count"
    ] == 3
    assert latest_recheck["direct_app_mcp_gitnexus_tool_surface"][
        "returned_moss_general_tool_count"
    ] == 0
    assert latest_recheck["direct_app_mcp_gitnexus_tool_surface"][
        "returned_moss_named_tool_count"
    ] == 0
    assert latest_recheck["direct_app_mcp_gitnexus_tool_surface"][
        "direct_app_mcp_evidence_captured"
    ] is False
    assert latest_recheck["direct_app_mcp_gitnexus_tool_surface"][
        "direct_gitnexus_evidence_captured"
    ] is False
    assert latest_recheck["direct_app_mcp_gitnexus_tool_surface"][
        "relevant_direct_tool_count"
    ] == 0
    assert latest_recheck["local_secret_hygiene"]["values_read"] is False
    assert latest_recheck["local_secret_hygiene"]["secret_values_captured"] is False
    assert latest_recheck["ledger_pnl_direct_governance_record"][
        "record_write_status"
    ] == "not_requested"
    assert latest_recheck["ledger_pnl_direct_governance_record"][
        "writes_governance_records"
    ] is False
    assert latest_recheck["calculation_owner_decision"][
        "captured_decision_count"
    ] == 0
    assert latest_recheck["calculation_owner_decision"][
        "incomplete_decision_count"
    ] == counts["calculation_display_open_p1"]
    assert latest_recheck["calculation_owner_decision"][
        "chooses_or_approves_conventions"
    ] is False
    assert monitoring_snapshot["refresh_results"]["calculation_owner_decision"][
        "open_decision_count"
    ] == counts["calculation_display_open_p1"]
    assert monitoring_snapshot["refresh_results"]["calculation_owner_decision"][
        "captured_decision_count"
    ] == 0
    assert monitoring_snapshot["refresh_results"]["calculation_owner_decision"][
        "incomplete_decision_count"
    ] == counts["calculation_display_open_p1"]
    assert monitoring_snapshot["refresh_results"]["ledger_pnl_direct_governance_record"][
        "record_write_status"
    ] == "not_requested"
    assert monitoring_snapshot["refresh_results"]["ledger_pnl_direct_governance_record"][
        "formal_use_allowed"
    ] is False
    assert monitoring_snapshot["refresh_results"]["direct_app_mcp_gitnexus_tool_surface"][
        "direct_app_mcp_evidence_captured"
    ] is False
    assert monitoring_snapshot["refresh_results"]["direct_app_mcp_gitnexus_tool_surface"][
        "direct_gitnexus_evidence_captured"
    ] is False
    assert monitoring_snapshot["refresh_results"]["local_secret_hygiene"][
        "secret_values_captured"
    ] is False
    assert monitoring_snapshot["refresh_results"]["local_secret_hygiene"][
        "clears_secret_scan"
    ] is False
    assert "does not write DuckDB or governance records" in monitoring_snapshot[
        "boundary"
    ]
    monitoring_evidence = next(
        item
        for item in manifest["verification_evidence"]
        if item["scope"] == "system_audit_monitoring_refresh"
    )
    assert "python scripts\\refresh_system_audit_monitoring.py" in monitoring_evidence[
        "command"
    ]
    assert "tests/test_system_audit_monitoring_refresh.py" in monitoring_evidence[
        "command"
    ]
    assert monitoring_snapshot["generated_at"] in monitoring_evidence["result"]
    assert "drift_error_count=5" in monitoring_evidence["result"]
    assert "blocker intake board next=calculation-display-p1-decisions" in (
        monitoring_evidence["result"]
    )
    assert "monitoring refresh/intake tests 11 passed" in monitoring_evidence["result"]

    monitoring_verifier_evidence = next(
        item
        for item in manifest["verification_evidence"]
        if item["scope"] == "system_audit_monitoring_snapshot_verifier"
    )
    assert "tests/test_system_audit_monitoring_snapshot_verifier.py" in (
        monitoring_verifier_evidence["command"]
    )
    assert "python scripts\\verify_system_audit_monitoring_snapshot.py" in (
        monitoring_verifier_evidence["command"]
    )
    assert "26 passed" in monitoring_verifier_evidence["result"]
    assert "pulse_completion_state=not_complete" in monitoring_verifier_evidence[
        "result"
    ]
    assert "errors=[]" in monitoring_verifier_evidence["result"]
    assert "direct App evidence" in monitoring_verifier_evidence["result"]


def test_completion_checklist_maps_open_blockers_without_approval() -> None:
    manifest = _load_json(MANIFEST_PATH)
    checklist = (ROOT / manifest["artifacts"]["completion_checklist"]).read_text(
        encoding="utf-8"
    )

    assert "This checklist is the completion audit" in checklist
    assert "It does not approve metrics" in checklist
    assert "does not close any blocker" in checklist

    for blocker in manifest["open_blockers"]:
        assert f"`{blocker['id']}`" in checklist
        assert blocker["last_checked_at"] in checklist

    assert "`owner-approval-7-pages`" in checklist
    assert "7 pending, 0 captured, 0 closure-approved" in checklist
    assert "`ledger-pnl-direct-governance-record`" in checklist
    assert "record_write_status=not_requested" in checklist
    assert "`calculation-display-p1-decisions`" in checklist
    assert "8 rows remain open" in checklist
    assert "`direct-app-mcp-gitnexus-evidence`" in checklist
    assert "`tool_search` returned 0 relevant direct MOSS/GitNexus tools" in checklist
    assert "focused MOSS and GitNexus keyword rechecks returned 0 tools" in checklist
    assert "`local-secret-hygiene`" in checklist
    assert "redacted gitleaks 2 ignored/untracked" in checklist
    assert "do not run `python scripts\\emit_ledger_pnl_governance_record.py --write`" in checklist
    assert "do not copy credential values" in checklist


def test_system_audit_blocker_intake_board_is_indexed_and_non_approving() -> None:
    manifest = _load_json(MANIFEST_PATH)
    index = (ROOT / manifest["artifacts"]["index"]).read_text(encoding="utf-8")

    assert manifest["artifacts"]["system_audit_blocker_intake_board_script"] == (
        "scripts/system_audit_blocker_intake_board.py"
    )
    assert manifest["artifacts"]["system_audit_blocker_intake_board_tests"] == (
        "tests/test_system_audit_blocker_intake_board.py"
    )
    assert "Blocker intake board" in index
    assert "2026-06-10-calculation-p1-owner-decision-packet.md" in index
    assert "2026-06-10-calculation-p1-owner-meeting-checklist.md" in index
    assert "2026-06-10-calculation-p1-first-priority-readiness-packet.md" in index
    assert "python scripts\\calculation_p1_owner_decision_packet.py" in index
    assert "python scripts\\calculation_p1_owner_meeting_checklist.py" in index
    assert "python scripts\\calculation_p1_first_priority_readiness_packet.py" in index
    assert "python scripts\\system_audit_blocker_intake_board.py --format markdown" in index
    assert "calculation-display-p1-decisions" in index
    assert "authorizing Ledger PnL `--write`" in index


def test_completion_snapshot_matches_open_blockers_and_stays_non_approving() -> None:
    manifest = _load_json(MANIFEST_PATH)
    snapshot = _load_json(ROOT / manifest["artifacts"]["completion_snapshot"])

    assert snapshot["report_kind"] == "system_audit_completion_snapshot"
    assert snapshot["generated_at"] == "2026-08-06T22:30:00+08:00"
    assert snapshot["source_artifacts"]["system_audit_monitoring_snapshot"] == manifest[
        "artifacts"
    ]["system_audit_monitoring_snapshot"]
    assert snapshot["status"] == {
        "overall": "not_complete",
        "fail_closed": True,
        "approves_metrics": False,
        "approves_pages": False,
        "captures_business_owner_approval": False,
        "writes_governance_records": False,
        "certifies_routes": False,
        "clears_secret_scan": False,
        "captures_direct_app_mcp_gitnexus_evidence": False,
    }
    assert snapshot["summary"]["open_blocker_count"] == len(manifest["open_blockers"])
    assert snapshot["summary"]["completed_blocker_count"] == 0
    assert snapshot["summary"]["required_completion_gate_count"] == len(
        snapshot["completion_gates"]
    )
    assert snapshot["summary"]["business_contract_certified_routes"] == manifest[
        "counts"
    ]["business_contract_certified_routes"]
    assert snapshot["summary"]["owner_approval_pending_pages"] == manifest["counts"][
        "owner_approval_pending_pages"
    ]
    assert snapshot["summary"]["calculation_display_open_p1"] == manifest["counts"][
        "calculation_display_open_p1"
    ]

    gates_by_id = {gate["blocker_id"]: gate for gate in snapshot["completion_gates"]}
    assert set(gates_by_id) == {blocker["id"] for blocker in manifest["open_blockers"]}
    for blocker in manifest["open_blockers"]:
        gate = gates_by_id[blocker["id"]]
        assert gate["status"] == "not_complete"
        assert gate["last_checked_at"] == blocker["last_checked_at"]
        assert gate["required_evidence"]
        assert gate["current_contradicting_evidence"]
        assert gate["fail_closed_until"]

    assert snapshot["summary"]["direct_app_tool_discovery_count"] == 0
    assert snapshot["summary"]["readiness_direct_evidence_null_count"] == 0
    assert snapshot["summary"]["readiness_audit_review_null_count"] == 0
    assert (
        snapshot["summary"]["readiness_missing_direct_records_count"]
        + snapshot["summary"]["readiness_direct_records_ready_for_audit_review_count"]
        == manifest["counts"]["seeded_pages"]
    )
    assert snapshot["summary"]["local_secret_gitleaks_finding_count"] == 2
    assert "does not approve metrics" in snapshot["boundary"]
    assert "does not approve" in snapshot["boundary"]
    assert "local secrets" in snapshot["boundary"]


def test_owner_governance_follow_up_packet_routes_all_open_blockers_fail_closed() -> None:
    manifest = _load_json(MANIFEST_PATH)
    packet = _load_json(ROOT / manifest["artifacts"]["owner_governance_follow_up_packet"])
    index = (ROOT / manifest["artifacts"]["index"]).read_text(encoding="utf-8")
    executive_summary_zh = (
        ROOT / manifest["artifacts"]["executive_summary_zh"]
    ).read_text(encoding="utf-8")
    follow_up_brief_zh = (
        ROOT / manifest["artifacts"]["owner_governance_follow_up_brief_zh"]
    ).read_text(encoding="utf-8")
    main_report = (ROOT / manifest["artifacts"]["main_report"]).read_text(encoding="utf-8")
    action_register = (ROOT / manifest["artifacts"]["action_register"]).read_text(
        encoding="utf-8"
    )

    assert packet["report_kind"] == "owner_governance_follow_up_packet"
    assert packet["generated_at"] == "2026-08-06T22:30:00+08:00"
    assert packet["source_artifacts"]["system_audit_monitoring_snapshot"] == manifest[
        "artifacts"
    ]["system_audit_monitoring_snapshot"]
    assert packet["status"] == {
        "overall": "follow_up_required",
        "fail_closed": True,
        "approves_metrics": False,
        "approves_pages": False,
        "captures_business_owner_approval": False,
        "writes_governance_records": False,
        "certifies_routes": False,
        "clears_secret_scan": False,
        "captures_direct_app_mcp_gitnexus_evidence": False,
        "requests_or_captures_secret_values": False,
        "authorizes_ledger_pnl_governance_write": False,
    }

    manifest_blockers = {item["id"]: item for item in manifest["open_blockers"]}
    packet_blockers = {
        item["blocker_id"]: item for item in packet["blocker_packets"]
    }
    assert set(packet_blockers) == set(manifest_blockers)
    assert packet["blocker_packet_count"] == len(manifest_blockers)
    assert len(packet["completion_order"]) == len(manifest_blockers)
    assert set(packet["completion_order"]) == set(manifest_blockers)
    assert packet["completion_order"][0] == "calculation-display-p1-decisions"
    assert packet["completion_order"].index("calculation-display-p1-decisions") < packet[
        "completion_order"
    ].index("owner-approval-7-pages")
    assert packet["completion_order"].index("ledger-pnl-direct-governance-record") < packet[
        "completion_order"
    ].index("owner-approval-7-pages")

    for blocker_id, blocker in manifest_blockers.items():
        follow_up = packet_blockers[blocker_id]
        assert follow_up["current_status"] == "not_complete"
        assert follow_up["last_checked_at"] == blocker["last_checked_at"]
        assert follow_up["responsible_owner_type"]
        assert follow_up["required_input_artifacts"]
        assert follow_up["required_meeting_or_governance_output"]
        assert follow_up["required_verification_commands"]
        assert follow_up["engineering_prework_available_now"]
        assert follow_up["external_input_required_for_closure"]
        assert follow_up["closure_evidence_after_external_input"]
        assert "does not" in follow_up["explicit_non_approval_boundary"]
        assert follow_up["prohibited_actions"]
        assert follow_up["fail_closed_until"]
        missing_inputs = [
            path
            for path in follow_up["required_input_artifacts"]
            if not path.startswith("<")
            and not (ROOT / path).exists()
        ]
        if blocker_id == "local-secret-hygiene":
            assert missing_inputs == [
                "test_output/security-scans/osv-report.json",
                "test_output/security-scans/gitleaks-report.json",
            ]
        else:
            assert missing_inputs == []

    ledger_packet = packet_blockers["ledger-pnl-direct-governance-record"]
    assert ledger_packet["authorization_required_commands_not_preapproved"] == [
        "python scripts\\emit_ledger_pnl_governance_record.py --write"
    ]
    assert "--write without explicit governance-owner/user authorization" in " ".join(
        ledger_packet["prohibited_actions"]
    )
    assert "does not authorize --write execution" in ledger_packet[
        "explicit_non_approval_boundary"
    ]
    assert "authorization" in " ".join(
        ledger_packet["external_input_required_for_closure"]
    )

    secret_packet = packet_blockers["local-secret-hygiene"]
    assert "read or paste config/.env values" in secret_packet["prohibited_actions"]
    assert "commit config/.env or any credential value" in secret_packet[
        "prohibited_actions"
    ]
    assert "does not read, request, capture, rotate, clear, or approve any secret value" in (
        secret_packet["explicit_non_approval_boundary"]
    )
    assert "without reading config/.env values" in " ".join(
        secret_packet["engineering_prework_available_now"]
    )
    assert "no secret values appear" in " ".join(
        secret_packet["closure_evidence_after_external_input"]
    )

    direct_app_packet = packet_blockers["direct-app-mcp-gitnexus-evidence"]
    assert "treat local stdio MCP success as direct App-surface closure" in (
        direct_app_packet["prohibited_actions"]
    )
    assert "fallback-only" in " ".join(
        direct_app_packet["engineering_prework_available_now"]
    )

    assert "does not approve metrics" in packet["global_non_approval_boundary"]
    assert "local secret hygiene" in packet["global_non_approval_boundary"]
    assert "Owner/governance follow-up packet" in index
    assert "2026-06-10-owner-governance-follow-up-packet.json" in index
    assert "2026-06-10-owner-governance-follow-up-brief.zh.md" in index
    assert "| P1-00A | Use the owner/governance follow-up packet" in action_register
    assert "2026-06-10-owner-governance-follow-up-brief.zh.md" in action_register
    assert "follow_up_packet_count=5" in action_register
    assert "calculation_prework_p1_count=8" in action_register
    assert "unauthorized Ledger PnL `--write`" in action_register
    assert "2026-06-10-owner-governance-follow-up-packet.json" in main_report
    assert "2026-06-10-owner-governance-follow-up-brief.zh.md" in main_report
    assert "follow_up_packet_count=5" in main_report
    assert "follow_up_brief_blocker_count=5" in main_report
    assert "calculation_prework_p1_count=8" in main_report
    assert "verify_system_audit_monitoring_snapshot.py" in main_report
    assert "pulse_completion_state=not_complete" in main_report
    assert "21 passed" in main_report
    assert "7 passed" in main_report
    assert "does not authorize Ledger PnL `--write`" in main_report
    assert "2026-06-10-owner-governance-follow-up-packet.json" in executive_summary_zh
    assert "2026-06-10-owner-governance-follow-up-brief.zh.md" in executive_summary_zh
    assert "follow_up_packet_count=5" in executive_summary_zh
    assert "follow_up_brief_blocker_count=5" in executive_summary_zh
    assert "calculation_prework_p1_count=8" in executive_summary_zh
    assert "verify_system_audit_monitoring_snapshot.py" in executive_summary_zh
    assert "pulse_completion_state=not_complete" in executive_summary_zh
    assert "21 passed" in executive_summary_zh
    assert "7 passed" in executive_summary_zh
    assert "12 条优先级行动" in executive_summary_zh
    assert "不授权 Ledger PnL `--write`" in executive_summary_zh

    assert "2026-06-10-owner-governance-follow-up-packet.json" in follow_up_brief_zh
    assert "follow_up_packet_count=5" in follow_up_brief_zh
    assert "open_blocker_count=5" in follow_up_brief_zh
    assert "不批准指标、页面、治理记录或 route certification" in follow_up_brief_zh
    assert "不授权 Ledger PnL `--write`" in follow_up_brief_zh
    assert "不读取、不请求、不捕获 secret 值" in follow_up_brief_zh
    for blocker_id, follow_up in packet_blockers.items():
        assert blocker_id in follow_up_brief_zh
        for path in follow_up["required_input_artifacts"]:
            assert path in follow_up_brief_zh


def test_real_backend_smoke_runbook_preserves_non_closure_boundary() -> None:
    manifest = _load_json(MANIFEST_PATH)
    runbook = (ROOT / manifest["artifacts"]["real_backend_smoke_runbook"]).read_text(
        encoding="utf-8"
    )
    result = (ROOT / manifest["artifacts"]["real_backend_smoke_result"]).read_text(
        encoding="utf-8"
    )

    assert "VITE_DATA_SOURCE=real" in runbook
    assert "tests/playwright/a11y-visual-smoke.spec.mjs --workers=1" in runbook
    assert "Full mock smoke, even when all routes pass." in runbook
    assert "Route-mocked real-client smoke." in runbook
    assert "does not grant owner approval" in runbook
    assert "business-contract certification" in runbook

    assert "47 passed" in result
    assert 'VITE_DATA_SOURCE: "real"' in result
    assert "does not grant business-owner approval" in result
    assert "does not write or approve governance records" in result
    assert "does not approve metrics" in result
    assert "does not certify routes" in result
    assert "does not replace direct Codex App MCP/GitNexus evidence" in result


def test_owner_approval_snapshot_matches_manifest_and_stays_fail_closed() -> None:
    manifest = _load_json(MANIFEST_PATH)
    snapshot = _load_json(
        ROOT / manifest["artifacts"]["owner_approval_fail_closed_snapshot"]
    )

    assert snapshot["report_kind"] == "owner_approval_fail_closed_snapshot"
    assert snapshot["status"] == {
        "fail_closed": True,
        "approves_metrics": False,
        "approves_pages": False,
        "captures_business_owner_approval": False,
        "certifies_routes": False,
    }

    summary = snapshot["summary"]
    assert summary["page_count"] == manifest["counts"]["owner_approval_pending_pages"]
    assert summary["pending_count"] == manifest["counts"]["owner_approval_pending_pages"]
    assert summary["captured_count"] == 0
    assert summary["closure_approved_count"] == 0
    assert summary["approval_action_item_sum"] == manifest["counts"][
        "owner_approval_action_items"
    ]
    assert summary["strict_require_captured_rejected_count"] == summary["page_count"]
    assert snapshot["test_result"]["result"] == "93 passed"

    open_owner_blocker = next(
        item for item in manifest["open_blockers"] if item["id"] == "owner-approval-7-pages"
    )
    assert open_owner_blocker["last_checked_at"] == snapshot["generated_at"]
    assert [page["page_slug"] for page in snapshot["pages"]] == open_owner_blocker["pages"]
    assert all(page["approval_status"] == "pending" for page in snapshot["pages"])
    assert all(
        page["business_owner_approval_captured"] is False for page in snapshot["pages"]
    )
    assert all(page["closure_approved"] is False for page in snapshot["pages"])
    assert all(page["strict_require_captured_exit_code"] != 0 for page in snapshot["pages"])
    assert "does not approve, sign, certify" in snapshot["boundary"]

    owner_evidence = next(
        item
        for item in manifest["verification_evidence"]
        if item["scope"] == "owner_approval_fail_closed_snapshot"
    )
    assert snapshot["generated_at"] in owner_evidence["result"]
    assert snapshot["test_result"]["result"] in owner_evidence["result"]


def test_ledger_pnl_direct_governance_snapshot_stays_non_writing() -> None:
    manifest = _load_json(MANIFEST_PATH)
    snapshot = _load_json(
        ROOT / manifest["artifacts"]["ledger_pnl_direct_governance_record_snapshot"]
    )
    runbook = (
        ROOT / manifest["artifacts"]["ledger_pnl_direct_governance_record_runbook"]
    ).read_text(encoding="utf-8")

    assert snapshot["report_kind"] == "ledger_pnl_direct_governance_record_snapshot"
    assert snapshot["page"] == {
        "page_slug": "ledger-pnl",
        "page_id": "PAGE-LEDGER-PNL-001",
        "frontend_route": "/ledger-pnl",
        "primary_api": "/api/ledger-pnl/summary",
    }
    assert snapshot["status"] == {
        "overall": "dry_run_candidate_only",
        "fail_closed": True,
        "writes_governance_records": False,
        "approves_metrics": False,
        "approves_pages": False,
        "captures_business_owner_approval": False,
        "certifies_routes": False,
        "closure_blocked_by_missing_written_record": True,
    }

    dry_run = snapshot["dry_run_result"]
    assert dry_run["record_write_status"] == "not_requested"
    assert dry_run["existing_record_line"] is None
    assert dry_run["validation_status"] == "ready_for_audit_review"
    assert dry_run["missing_required_fields"] == []
    assert dry_run["failed_required_field_groups"] == []
    assert dry_run["formal_use_allowed"] is False
    assert snapshot["closure_blocked_by_missing_written_record"] is True
    assert snapshot["post_write_validation"]["ready"] is False
    assert snapshot["post_write_validation"]["blocking_reasons"] == [
        "written_record_located",
        "governance_direct_records_ready",
        "audit_review_not_blocked_by_record_gaps",
    ]

    assert snapshot["record_key"] == {
        "page_id": "PAGE-LEDGER-PNL-001",
        "primary_api": "/api/ledger-pnl/summary",
        "report_date": "2026-05-31",
        "cache_key": "ledger_pnl.summary:2026-05-31:ALL",
    }
    assert snapshot["written_record_search"]["matches"] == {
        "PAGE-LEDGER-PNL-001": 0,
        "/api/ledger-pnl/summary": 0,
        "ledger_pnl.summary:2026-05-31:ALL": 0,
    }

    readiness = snapshot["page_readiness_result"]
    assert readiness["overall_status"] == "static-pass"
    assert readiness["formal_use_allowed"] is False
    assert readiness["closure_approved"] is False
    assert readiness["business_owner_approval_captured"] is False
    assert readiness["approval_status"] == "pending"
    assert readiness["catalog_date_evidence"] == {
        "status": "incomplete",
        "table_count": 3,
        "present_table_count": 2,
        "date_sampled_table_count": 1,
        "sampled_table_names": [
            "qdb_general_ledger_workbook",
            "ledger_import_batch",
            "ledger_raw_row",
        ],
        "blocking_detail": (
            "qdb_general_ledger_workbook is not present in the current catalog sample; "
            "ledger_raw_row has no date column."
        ),
    }
    assert readiness["governance_record_validation"] == {
        "status": "missing_direct_records",
        "ready_record_count": 0,
        "incomplete_record_count": 0,
        "direct_record_count": 0,
        "expanded_anchor_record_count": 0,
    }
    assert readiness["audit_review"] == {
        "status": "blocked_by_record_gaps",
        "closure_approved": False,
        "direct_page_api_record_fields": "blocked",
    }

    assert "python scripts\\emit_ledger_pnl_governance_record.py --write" in runbook
    assert "Confirm governance-owner authorization" in runbook
    assert "Dry-run output without `--write`" in runbook
    assert "post_write_validation.ready must be true" in snapshot["closure_gate"]
    assert snapshot["generated_at"] in runbook
    assert "does not write governance records" in snapshot["boundary"]

    ledger_blocker = next(
        item
        for item in manifest["open_blockers"]
        if item["id"] == "ledger-pnl-direct-governance-record"
    )
    assert ledger_blocker["last_checked_at"] == snapshot["generated_at"]

    ledger_evidence = next(
        item
        for item in manifest["verification_evidence"]
        if item["scope"] == "ledger_pnl_direct_governance_record_snapshot"
    )
    assert snapshot["generated_at"] in ledger_evidence["result"]


def test_direct_app_mcp_gitnexus_snapshot_preserves_tool_surface_gap() -> None:
    manifest = _load_json(MANIFEST_PATH)
    snapshot = _load_json(
        ROOT / manifest["artifacts"]["direct_app_mcp_gitnexus_tool_surface_snapshot"]
    )
    runbook = (
        ROOT / manifest["artifacts"]["direct_app_mcp_gitnexus_tool_surface_runbook"]
    ).read_text(encoding="utf-8")

    assert snapshot["report_kind"] == "direct_app_mcp_gitnexus_tool_surface_snapshot"
    assert snapshot["refresh_command"] == (
        "python scripts\\refresh_direct_app_mcp_gitnexus_tool_surface_snapshot.py"
    )
    assert snapshot["observation_source"] == "caller_supplied_tool_search_results"
    assert snapshot["status"] == {
        "overall": "tool_surface_unavailable_in_current_codex_app_session",
        "fail_closed": True,
        "direct_app_mcp_evidence_captured": False,
        "direct_gitnexus_evidence_captured": False,
        "approves_metrics": False,
        "approves_pages": False,
        "captures_business_owner_approval": False,
        "writes_governance_records": False,
        "certifies_routes": False,
    }

    discovery = snapshot["tool_discovery"]
    assert discovery["tool"] == "tool_search"
    assert (
        discovery["query"]
        == "moss metric contracts lineage evidence data catalog gitnexus MCP tools"
    )
    assert snapshot["generated_at"] == discovery["checked_at"]
    assert discovery["discovered_tool_count"] == 0
    assert discovery["discovered_tools"] == []
    assert discovery["relevant_direct_tool_count"] == 0
    focused_rechecks = {
        item["query"]: item for item in snapshot["focused_rechecks"]
    }
    assert set(focused_rechecks) == {
        "gitnexus MCP impact call path symbol repository evidence",
        "moss metric contracts lineage evidence data catalog MCP tools",
        "moss-data-catalog moss-lineage-evidence moss-metric-contracts",
    }
    gitnexus_recheck = focused_rechecks[
        "gitnexus MCP impact call path symbol repository evidence"
    ]
    assert gitnexus_recheck["returned_tool_count"] == 0
    assert gitnexus_recheck["returned_tools"] == []
    assert gitnexus_recheck["relevant_direct_tool_count"] == 0
    assert "no direct MOSS MCP evidence tools exposed" in gitnexus_recheck[
        "interpretation"
    ]
    assert all(
        item["returned_tool_count"] == 0
        for query, item in focused_rechecks.items()
        if query != "gitnexus MCP impact call path symbol repository evidence"
    )
    assert all(
        item["relevant_direct_tool_count"] == 0
        for item in focused_rechecks.values()
    )

    expected_servers = {
        "gitnexus",
        "moss-metric-contracts",
        "moss-lineage-evidence",
        "moss-data-catalog",
        "moss-data-quality",
    }
    assert set(snapshot["expected_direct_servers"]) == expected_servers
    assert snapshot["detected_direct_servers"] == []
    assert set(snapshot["missing_direct_servers"]) == expected_servers
    sources_by_path = {
        source["path"]: source for source in snapshot["local_registration_sources"]
    }
    assert set(sources_by_path) == {
        ".codex/config.toml",
        ".mcp.json",
        "docs/MCP_RUNBOOK.md",
    }
    assert set(sources_by_path[".codex/config.toml"]["declared_servers"]) == expected_servers
    assert set(sources_by_path[".mcp.json"]["declared_servers"]) == expected_servers
    assert sources_by_path[".codex/config.toml"]["declares_expected_servers"] is True
    assert sources_by_path[".mcp.json"]["declares_expected_servers"] is True
    assert sources_by_path["docs/MCP_RUNBOOK.md"]["documents_fresh_session_retry"] is True

    assert snapshot["interpretation"] == {
        "repo_configuration_status": "expected_servers_declared_locally",
        "current_app_tool_surface_status": "direct_moss_and_gitnexus_tools_not_exposed",
        "local_stdio_evidence_status": "fallback_only_not_direct_app_surface_evidence",
        "closure_effect": "none",
    }
    assert all(
        value == "not_callable_as_direct_codex_app_tool_in_this_session"
        for value in snapshot["direct_evidence_gap"].values()
    )
    assert "start a fresh Codex App session" in snapshot["closure_gate"][0]
    assert "does not approve metrics" in snapshot["boundary"]
    assert "does not approve pages" in snapshot["boundary"]
    assert "does not write governance records" in snapshot["boundary"]

    assert "Start a fresh Codex App session" in runbook
    assert "Do not treat any of the following as direct App-surface closure" in runbook
    assert "Local stdio MCP handshake success." in runbook
    assert "focused recheck results" in runbook
    assert "pytest tests/test_system_audit_manifest_contract.py -q" in runbook
    assert discovery["checked_at"] in runbook

    direct_app_blocker = next(
        item
        for item in manifest["open_blockers"]
        if item["id"] == "direct-app-mcp-gitnexus-evidence"
    )
    assert direct_app_blocker["last_checked_at"] == discovery["checked_at"]

    direct_app_evidence = next(
        item
        for item in manifest["verification_evidence"]
        if item["scope"] == "direct_app_mcp_gitnexus_tool_discovery"
    )
    assert discovery["checked_at"] in direct_app_evidence["result"]


def test_local_secret_hygiene_snapshot_never_captures_values() -> None:
    manifest = _load_json(MANIFEST_PATH)
    snapshot = _load_json(ROOT / manifest["artifacts"]["local_secret_hygiene_snapshot"])
    runbook = (ROOT / manifest["artifacts"]["local_secret_hygiene_runbook"]).read_text(
        encoding="utf-8"
    )
    attestation_packet = (
        ROOT / manifest["artifacts"]["local_secret_hygiene_owner_attestation_packet"]
    ).read_text(encoding="utf-8")

    assert snapshot["report_kind"] == "local_secret_hygiene_snapshot"
    assert snapshot["status"] == {
        "overall": "local_ignored_untracked_findings",
        "fail_closed": True,
        "secret_values_captured": False,
        "approves_deployment": False,
        "clears_secret_scan": False,
        "writes_or_rotates_secrets": False,
    }
    assert snapshot["detected_secret_names"] == [
        "MOSS_TUSHARE_TOKEN",
        "STITCH_API_KEY",
    ]
    assert snapshot["value_handling"] == {
        "values_read": False,
        "values_written_to_artifacts": False,
        "values_logged": False,
        "names_only_recorded": True,
    }

    boundary = snapshot["fresh_boundary_checks"]
    assert snapshot["generated_at"] == boundary["checked_at"]
    assert boundary["config_env_exists"] is True
    assert boundary["git_check_ignore"]["exit_code"] == 0
    assert boundary["git_check_ignore"]["matched_rule"] == ".gitignore:4:config/.env"
    assert boundary["git_ls_files"]["tracked_path_count"] == 0
    assert boundary["git_status_ignored"]["result"] == "!! config/.env"
    assert snapshot["scan_plan"]["gitleaks_redaction_enabled"] is True
    assert snapshot["fresh_scan_results"]["checked_at"] == snapshot["generated_at"]
    assert snapshot["fresh_scan_results"]["osv"]["exit_code"] == 0
    assert snapshot["fresh_scan_results"]["osv"]["result_count"] == 0
    assert snapshot["fresh_scan_results"]["osv"]["package_finding_count"] == 0
    assert snapshot["fresh_scan_results"]["osv"]["vulnerability_count"] == 0
    assert snapshot["fresh_scan_results"]["gitleaks"]["exit_code"] == 1
    assert (
        snapshot["fresh_scan_results"]["gitleaks"]["exit_code_interpretation"]
        == "findings_present"
    )
    assert snapshot["fresh_scan_results"]["gitleaks"]["redaction_enabled"] is True
    assert snapshot["fresh_scan_results"]["gitleaks"]["finding_count"] == 2
    assert snapshot["fresh_scan_results"]["gitleaks"]["finding_rule_ids"] == [
        "generic-api-key"
    ]
    assert snapshot["fresh_scan_results"]["gitleaks"]["finding_files"] == [
        "config/.env"
    ]
    assert (
        snapshot["fresh_scan_results"]["gitleaks"]["secret_values_captured"] is False
    )
    assert snapshot["fresh_scan_results"]["gitleaks"][
        "detected_secret_names_confirmed_in_redacted_report"
    ] == [
        "MOSS_TUSHARE_TOKEN",
        "STITCH_API_KEY",
    ]
    retry = snapshot["latest_non_closing_retry"]
    assert retry["checked_at"] == "2026-06-10T17:30:56+08:00"
    assert retry["values_read_by_human"] is False
    assert retry["values_written_to_artifacts"] is False
    assert retry["dry_run_plan"]["exit_code"] == 0
    assert retry["dry_run_plan"]["gitleaks_redaction_enabled"] is True
    assert retry["boundary_checks"]["config_env_exists"] is True
    assert retry["boundary_checks"]["git_check_ignore"]["matched_rule"] == (
        ".gitignore:4:config/.env"
    )
    assert retry["boundary_checks"]["git_ls_files"]["tracked_path_count"] == 0
    assert retry["boundary_checks"]["git_status_ignored"]["result"] == "!! config/.env"
    assert retry["redacted_gitleaks_retry"]["exit_code"] == 1
    assert retry["redacted_gitleaks_retry"]["exit_code_interpretation"] == (
        "findings_present"
    )
    assert retry["redacted_gitleaks_retry"]["finding_count"] == 2
    assert retry["redacted_gitleaks_retry"]["finding_rule_ids"] == ["generic-api-key"]
    assert retry["redacted_gitleaks_retry"]["finding_files"] == ["config/.env"]
    assert retry["redacted_gitleaks_retry"]["redaction_enabled"] is True
    assert retry["redacted_gitleaks_retry"]["secret_values_captured"] is False
    assert retry["osv_retry"]["exit_code"] == 1
    assert retry["osv_retry"]["status"] == "not_refreshed_network_proxy_refused"
    assert "proxy 127.0.0.1:9 refused" in retry["osv_retry"]["result"]
    latest_boundary = snapshot["latest_boundary_only_recheck"]
    assert latest_boundary["checked_at"] == "2026-06-27T13:05:14+08:00"
    assert latest_boundary["values_read_by_human"] is False
    assert latest_boundary["values_written_to_artifacts"] is False
    assert latest_boundary["secret_values_captured"] is False
    assert latest_boundary["scan_not_rerun"] is True
    assert latest_boundary["dry_run_plan"]["gitleaks_redaction_enabled"] is True
    assert "did not replace the last full redacted scan evidence" in latest_boundary[
        "reason"
    ]
    assert latest_boundary["test_result"] == (
        "pytest tests/test_supply_chain_security_scanning.py "
        "tests/test_secret_hygiene.py -q -> 7 passed"
    )
    assert latest_boundary["boundary_checks"]["config_env_exists"] is True
    assert latest_boundary["boundary_checks"]["git_check_ignore"]["matched_rule"] == (
        ".gitignore:4:config/.env"
    )
    assert latest_boundary["boundary_checks"]["git_ls_files"]["tracked_path_count"] == 0
    assert latest_boundary["boundary_checks"]["git_status_ignored"]["result"] == (
        "!! config/.env"
    )
    assert latest_boundary["closure_effect"] == "none"

    assert "Do not paste credential values" in runbook
    assert "Do not add `config/.env` to Git." in runbook
    assert "Local Secret Hygiene Owner Attestation Packet" in attestation_packet
    assert "`MOSS_TUSHARE_TOKEN`" in attestation_packet
    assert "`STITCH_API_KEY`" in attestation_packet
    assert "`secret_value_fields_present=false`" in attestation_packet
    assert "Do not read or paste `config/.env` values." in attestation_packet
    assert "captures_secret_values=false" in attestation_packet
    assert boundary["checked_at"] in runbook
    assert retry["checked_at"] in runbook
    assert latest_boundary["checked_at"] in runbook
    assert "proxy `127.0.0.1:9` refused the connection" in runbook
    assert "does not read, expose, rotate, clear, or approve any secret value" in snapshot[
        "boundary"
    ]

    secret_blocker = next(
        item for item in manifest["open_blockers"] if item["id"] == "local-secret-hygiene"
    )
    assert secret_blocker["last_checked_at"] == latest_boundary["checked_at"]

    secret_evidence = next(
        item
        for item in manifest["verification_evidence"]
        if item["scope"] == "local_secret_hygiene_boundary"
    )
    assert boundary["checked_at"] in secret_evidence["result"]
    assert retry["checked_at"] in secret_evidence["result"]
    assert latest_boundary["checked_at"] in secret_evidence["result"]
    assert "boundary-only recheck" in secret_evidence["result"]
    assert "proxy 127.0.0.1:9 refused" in secret_evidence["result"]


def test_owner_review_artifacts_preserve_non_approval_boundaries() -> None:
    manifest = _load_json(MANIFEST_PATH)
    brief = (ROOT / manifest["artifacts"]["owner_review_brief_zh"]).read_text(
        encoding="utf-8"
    )
    capture_template = (
        ROOT / manifest["artifacts"]["owner_decision_capture_template_zh"]
    ).read_text(encoding="utf-8")

    assert "这份 brief 用于把系统审计转成业务 owner 可开会裁决的议程" in brief
    assert "它只重组已有审计证据，不批准任何指标、页面、治理记录或 owner 签核" in brief
    assert "会议只能决定治理流程下一步，不能把 dry-run 当成正式记录" in brief
    assert "full real-backend browser smoke 已有 `47 passed` 证据" in brief
    assert "本 brief 不批准任何计算口径" in brief
    assert "鐢" not in brief
    assert "鎶" not in brief

    assert "填写本模板不等于完成页面审批、治理记录写入" in capture_template
    assert "### Candidate Option Contract" in capture_template
    assert "`Option <letter> - <copied option description>`" in capture_template
    assert "Required capture format, not a recommendation" in capture_template
    assert "accepted selected_decision example" not in capture_template
    assert "允许的 Option 字母是逐行限定的" in capture_template
    assert "approved 行只写 evidence-only 文本" in capture_template
    assert "verification_gate` 必须写明" in capture_template
    assert "`Option <allowed letter> - <copied option description>`" in capture_template
    assert "`Option C - source must carry explicit unit metadata and fail if absent`" not in (
        capture_template
    )
    assert "`Option A - backend provides governed matrix`" not in capture_template
    assert "本模板不替代单页 owner approval template" in capture_template
    assert "本模板不替代测试输出或 strict checker" in capture_template
    assert (
        "full real-backend smoke `47 passed` 结果已复核，且未被当成业务审批"
        in capture_template
    )
    assert (
        "smoke 结果不批准指标、页面、治理记录、owner approval 或 direct App MCP/GitNexus closure"
        in capture_template
    )
    assert "鐢" not in capture_template
    assert "鎶" not in capture_template
