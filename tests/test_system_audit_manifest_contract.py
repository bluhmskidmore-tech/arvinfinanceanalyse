import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT_DIR = ROOT / "docs" / "audits"
MANIFEST_PATH = AUDIT_DIR / "2026-06-10-system-audit-manifest.json"
COVERAGE_REPORT_PATH = AUDIT_DIR / "business-display-coverage-report.json"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_system_audit_manifest_references_existing_artifacts_and_stays_fail_closed() -> None:
    manifest = _load_json(MANIFEST_PATH)

    assert manifest["report_kind"] == "system_wide_skills_audit_manifest"
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
        "calculation_logic_audit",
        "calculation_owner_decision_matrix",
        "owner_approval_evidence_summary",
        "owner_approval_fail_closed_snapshot",
        "direct_app_mcp_gitnexus_tool_surface_snapshot",
        "direct_app_mcp_gitnexus_tool_surface_runbook",
        "ledger_pnl_direct_governance_record_snapshot",
        "ledger_pnl_direct_governance_record_runbook",
        "local_secret_hygiene_snapshot",
        "local_secret_hygiene_runbook",
        "business_display_coverage",
        "real_backend_smoke_runbook",
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
    action_register = (ROOT / manifest["artifacts"]["action_register"]).read_text(
        encoding="utf-8"
    )
    decision_matrix = (
        ROOT / manifest["artifacts"]["calculation_owner_decision_matrix"]
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
    }
    all_pages = fresh_by_command["python scripts\\codex_page_readiness.py --all"]
    route_scope = fresh_by_command["python scripts\\codex_page_readiness.py --route-scope"]
    coverage_summary = fresh_by_command["python scripts\\business_display_coverage_report.py"]

    assert all_pages["page_count"] == counts["seeded_pages"]
    assert all_pages["static_pass_count"] == counts["static_pass_pages"]
    assert all_pages["owner_approval_pending_count"] == counts["owner_approval_pending_pages"]
    assert all_pages["owner_approval_action_item_sum"] == counts["owner_approval_action_items"]
    assert route_scope["business_contract_certified_count"] == counts[
        "business_contract_certified_routes"
    ]
    assert coverage_summary["tracked_route_count"] == counts["business_display_tracked_routes"]
    assert coverage_summary["route_gap_count"] == counts["business_display_route_gaps"]
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
    assert len(open_decision_rows) == counts["calculation_display_open_p1"]
    assert all(not line.startswith("| P1-08 |") for line in open_decision_rows)
    assert "P1-08" in verified_closed_section


def test_real_backend_smoke_runbook_preserves_non_closure_boundary() -> None:
    manifest = _load_json(MANIFEST_PATH)
    runbook = (ROOT / manifest["artifacts"]["real_backend_smoke_runbook"]).read_text(
        encoding="utf-8"
    )

    assert "VITE_DATA_SOURCE=real" in runbook
    assert "tests/playwright/a11y-visual-smoke.spec.mjs --workers=1" in runbook
    assert "Full mock smoke, even when all routes pass." in runbook
    assert "Route-mocked real-client smoke." in runbook
    assert "does not grant owner approval" in runbook
    assert "business-contract certification" in runbook


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
    assert snapshot["test_result"]["result"] == "90 passed"

    open_owner_blocker = next(
        item for item in manifest["open_blockers"] if item["id"] == "owner-approval-7-pages"
    )
    assert [page["page_slug"] for page in snapshot["pages"]] == open_owner_blocker["pages"]
    assert all(page["approval_status"] == "pending" for page in snapshot["pages"])
    assert all(
        page["business_owner_approval_captured"] is False for page in snapshot["pages"]
    )
    assert all(page["closure_approved"] is False for page in snapshot["pages"])
    assert all(page["strict_require_captured_exit_code"] != 0 for page in snapshot["pages"])
    assert "does not approve, sign, certify" in snapshot["boundary"]


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
    }

    dry_run = snapshot["dry_run_result"]
    assert dry_run["record_write_status"] == "not_requested"
    assert dry_run["existing_record_line"] is None
    assert dry_run["validation_status"] == "ready_for_audit_review"
    assert dry_run["missing_required_fields"] == []
    assert dry_run["failed_required_field_groups"] == []
    assert dry_run["formal_use_allowed"] is False

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

    assert "python scripts\\emit_ledger_pnl_governance_record.py --write" in runbook
    assert "Confirm governance-owner authorization" in runbook
    assert "Dry-run output without `--write`" in runbook
    assert "does not write governance records" in snapshot["boundary"]


def test_direct_app_mcp_gitnexus_snapshot_preserves_tool_surface_gap() -> None:
    manifest = _load_json(MANIFEST_PATH)
    snapshot = _load_json(
        ROOT / manifest["artifacts"]["direct_app_mcp_gitnexus_tool_surface_snapshot"]
    )
    runbook = (
        ROOT / manifest["artifacts"]["direct_app_mcp_gitnexus_tool_surface_runbook"]
    ).read_text(encoding="utf-8")

    assert snapshot["report_kind"] == "direct_app_mcp_gitnexus_tool_surface_snapshot"
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
    assert discovery["discovered_tool_count"] == 0
    assert discovery["discovered_tools"] == []

    expected_servers = {
        "gitnexus",
        "moss-metric-contracts",
        "moss-lineage-evidence",
        "moss-data-catalog",
        "moss-data-quality",
    }
    assert set(snapshot["expected_direct_servers"]) == expected_servers
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
    assert "pytest tests/test_system_audit_manifest_contract.py -q" in runbook


def test_local_secret_hygiene_snapshot_never_captures_values() -> None:
    manifest = _load_json(MANIFEST_PATH)
    snapshot = _load_json(ROOT / manifest["artifacts"]["local_secret_hygiene_snapshot"])
    runbook = (ROOT / manifest["artifacts"]["local_secret_hygiene_runbook"]).read_text(
        encoding="utf-8"
    )

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
    assert boundary["config_env_exists"] is True
    assert boundary["git_check_ignore"]["exit_code"] == 0
    assert boundary["git_check_ignore"]["matched_rule"] == ".gitignore:4:config/.env"
    assert boundary["git_ls_files"]["tracked_path_count"] == 0
    assert boundary["git_status_ignored"]["result"] == "!! config/.env"
    assert snapshot["scan_plan"]["gitleaks_redaction_enabled"] is True

    assert "Do not paste credential values" in runbook
    assert "Do not add `config/.env` to Git." in runbook
    assert "does not read, expose, rotate, clear, or approve any secret value" in snapshot[
        "boundary"
    ]


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

    assert "填写本模板不等于完成页面审批、治理记录写入" in capture_template
    assert "本模板不替代单页 owner approval template" in capture_template
    assert "本模板不替代测试输出或 strict checker" in capture_template
