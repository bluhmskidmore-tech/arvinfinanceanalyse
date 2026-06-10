from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import scripts.system_audit_pulse as pulse_module
from scripts.system_audit_pulse import build_pulse, format_markdown_pulse


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "system_audit_pulse.py"
MANIFEST = ROOT / "docs" / "audits" / "2026-06-10-system-audit-manifest.json"


def test_system_audit_pulse_aggregates_live_monitors_without_approval() -> None:
    report = build_pulse(generated_at="2026-06-10T19:45:00+08:00")

    assert report["report_kind"] == "system_audit_pulse"
    assert report["generated_at"] == "2026-06-10T19:45:00+08:00"
    assert report["status"] == "pass"
    assert report["full_score_ready"] is False
    assert report["completion_state"] == "not_complete"
    assert report["open_blocker_count"] == 5
    assert report["evidence_scope"] == {
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
    assert report["route_scope"]["route_count"] == 39
    assert report["route_scope"]["business_contract_certified_count"] == 0
    assert report["route_scope"]["visible_unseeded_route_count"] == 0
    assert report["route_scope"]["unclassified_count"] == 0
    assert report["business_display"]["tracked_route_count"] == 26
    assert report["business_display"]["route_gap_count"] == 0
    assert report["completion_snapshot"]["status"] == "pass"
    assert report["completion_snapshot"]["open_blocker_count"] == 5
    assert report["all_page_readiness"]["source"] == "manifest_last_full_readiness"
    assert report["all_page_readiness"]["direct_evidence_null_count"] == 0
    assert report["all_page_readiness"]["audit_review_null_count"] == 0
    assert report["drift_errors"] == []
    assert "does not approve metrics" in report["claim_boundary"]


def test_system_audit_pulse_default_does_not_run_full_readiness(monkeypatch) -> None:
    def fail_full_readiness():
        raise AssertionError("default pulse should use the manifest's last full readiness scan")

    monkeypatch.setattr(
        pulse_module,
        "build_all_page_readiness_report",
        fail_full_readiness,
    )

    report = build_pulse(generated_at="2026-06-10T19:45:00+08:00")

    assert report["status"] == "pass"
    assert report["all_page_readiness"]["source"] == "manifest_last_full_readiness"


def test_system_audit_pulse_detects_route_scope_drift(monkeypatch) -> None:
    original = pulse_module.build_route_scope_classification_report

    def drifted_route_scope():
        payload = original()
        payload["summary"] = dict(payload["summary"])
        payload["summary"]["visible_unseeded_route_count"] = 1
        return payload

    monkeypatch.setattr(
        pulse_module,
        "build_route_scope_classification_report",
        drifted_route_scope,
    )

    report = build_pulse(generated_at="2026-06-10T19:45:00+08:00")

    assert report["status"] == "fail"
    assert (
        "route_scope.visible_unseeded_route_count expected 0, got 1"
        in report["drift_errors"]
    )


def test_system_audit_pulse_detects_business_display_drift(monkeypatch) -> None:
    original = pulse_module.build_business_display_coverage_report

    def drifted_coverage(*args, **kwargs):
        payload = original(*args, **kwargs)
        payload["summary"] = dict(payload["summary"])
        payload["summary"]["route_gap_count"] = 1
        return payload

    monkeypatch.setattr(
        pulse_module,
        "build_business_display_coverage_report",
        drifted_coverage,
    )

    report = build_pulse(generated_at="2026-06-10T19:45:00+08:00")

    assert report["status"] == "fail"
    assert "business_display.route_gap_count expected 0, got 1" in report["drift_errors"]


def test_system_audit_pulse_cli_outputs_json() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--generated-at",
            "2026-06-10T19:45:00+08:00",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["report_kind"] == "system_audit_pulse"
    assert payload["status"] == "pass"
    assert payload["full_score_ready"] is False
    assert payload["open_blocker_count"] == 5
    assert payload["all_page_readiness"]["source"] == "manifest_last_full_readiness"


def test_system_audit_pulse_formats_markdown_without_approval() -> None:
    report = build_pulse(generated_at="2026-06-10T19:45:00+08:00")

    markdown = format_markdown_pulse(report)

    assert markdown.startswith("# System Audit Pulse")
    assert "- Completion state: `not_complete`" in markdown
    assert "- Open blockers: `5`" in markdown
    assert "`business_contract_certified=0`" in markdown
    assert "`route_gaps=0`" in markdown
    assert "`direct_evidence_null=0`" in markdown
    assert "`audit_review_null=0`" in markdown
    assert "- `none`" in markdown
    assert "does not approve metrics" in markdown
    assert "governance records" in markdown


def test_system_audit_pulse_cli_outputs_markdown() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--generated-at",
            "2026-06-10T19:45:00+08:00",
            "--format",
            "markdown",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    assert completed.returncode == 0
    assert "# System Audit Pulse" in completed.stdout
    assert "- Completion state: `not_complete`" in completed.stdout
    assert "`business_contract_certified=0`" in completed.stdout
    assert "does not approve metrics" in completed.stdout


def test_system_audit_pulse_cli_strict_full_score_gate_rejects_current_blockers() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--generated-at",
            "2026-06-10T19:45:00+08:00",
            "--require-full-score-ready",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    assert completed.returncode == 1
    payload = json.loads(completed.stdout)
    assert payload["status"] == "pass"
    assert payload["full_score_ready"] is False
    assert payload["completion_state"] == "not_complete"
    assert payload["open_blocker_count"] == 5
    assert "System audit is not full-score ready" in completed.stderr
    assert "open_blocker_count=5" in completed.stderr
