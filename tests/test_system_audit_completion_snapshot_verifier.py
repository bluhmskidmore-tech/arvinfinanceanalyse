from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.verify_system_audit_completion_snapshot import verify_completion_snapshot


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_system_audit_completion_snapshot.py"
MANIFEST = ROOT / "docs" / "audits" / "2026-06-10-system-audit-manifest.json"


def _copy_audit_files(tmp_path: Path) -> Path:
    audit_dir = tmp_path / "docs" / "audits"
    audit_dir.mkdir(parents=True)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    snapshot = json.loads(
        (ROOT / manifest["artifacts"]["completion_snapshot"]).read_text(encoding="utf-8")
    )
    follow_up_packet = json.loads(
        (ROOT / manifest["artifacts"]["owner_governance_follow_up_packet"]).read_text(
            encoding="utf-8"
        )
    )
    follow_up_brief = (
        ROOT / manifest["artifacts"]["owner_governance_follow_up_brief_zh"]
    ).read_text(encoding="utf-8")
    calculation_matrix = (
        ROOT / manifest["artifacts"]["calculation_owner_decision_matrix"]
    ).read_text(encoding="utf-8")
    calculation_snapshot = json.loads(
        (ROOT / manifest["artifacts"]["calculation_owner_decision_snapshot"]).read_text(
            encoding="utf-8"
        )
    )
    monitoring_snapshot = json.loads(
        (ROOT / manifest["artifacts"]["system_audit_monitoring_snapshot"]).read_text(
            encoding="utf-8"
        )
    )
    manifest_path = audit_dir / "manifest.json"
    snapshot_path = audit_dir / "completion-snapshot.json"
    follow_up_packet_path = audit_dir / "owner-governance-follow-up-packet.json"
    follow_up_brief_path = audit_dir / "owner-governance-follow-up-brief.zh.md"
    calculation_matrix_path = audit_dir / "calculation-p1-owner-decision-matrix.md"
    calculation_snapshot_path = audit_dir / "calculation-p1-owner-decision-snapshot.json"
    monitoring_snapshot_path = audit_dir / "system-audit-monitoring-snapshot.json"
    original_follow_up_packet_path = manifest["artifacts"][
        "owner_governance_follow_up_packet"
    ]
    manifest["artifacts"]["completion_snapshot"] = "docs/audits/completion-snapshot.json"
    manifest["artifacts"][
        "owner_governance_follow_up_packet"
    ] = "docs/audits/owner-governance-follow-up-packet.json"
    manifest["artifacts"][
        "owner_governance_follow_up_brief_zh"
    ] = "docs/audits/owner-governance-follow-up-brief.zh.md"
    manifest["artifacts"][
        "calculation_owner_decision_matrix"
    ] = "docs/audits/calculation-p1-owner-decision-matrix.md"
    manifest["artifacts"][
        "calculation_owner_decision_snapshot"
    ] = "docs/audits/calculation-p1-owner-decision-snapshot.json"
    manifest["artifacts"][
        "system_audit_monitoring_snapshot"
    ] = "docs/audits/system-audit-monitoring-snapshot.json"
    follow_up_brief = follow_up_brief.replace(
        original_follow_up_packet_path,
        manifest["artifacts"]["owner_governance_follow_up_packet"],
    )
    follow_up_brief = follow_up_brief.replace(
        "`2026-06-10-owner-governance-follow-up-packet.json`",
        f"`{manifest['artifacts']['owner_governance_follow_up_packet']}`",
    )
    snapshot["source_artifacts"][
        "owner_governance_follow_up_packet"
    ] = "docs/audits/owner-governance-follow-up-packet.json"
    snapshot["source_artifacts"][
        "owner_governance_follow_up_brief_zh"
    ] = "docs/audits/owner-governance-follow-up-brief.zh.md"
    snapshot["source_artifacts"][
        "system_audit_monitoring_snapshot"
    ] = "docs/audits/system-audit-monitoring-snapshot.json"
    follow_up_packet["source_artifacts"][
        "system_audit_monitoring_snapshot"
    ] = "docs/audits/system-audit-monitoring-snapshot.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    follow_up_packet_path.write_text(
        json.dumps(follow_up_packet, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    follow_up_brief_path.write_text(follow_up_brief, encoding="utf-8")
    calculation_matrix_path.write_text(calculation_matrix, encoding="utf-8")
    calculation_snapshot_path.write_text(
        json.dumps(calculation_snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    monitoring_snapshot_path.write_text(
        json.dumps(monitoring_snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest_path


def test_verify_completion_snapshot_passes_for_checked_in_audit_package() -> None:
    result = verify_completion_snapshot(manifest_path=MANIFEST)

    assert result["status"] == "pass"
    assert result["open_blocker_count"] == 5
    assert result["completion_gate_count"] == 5
    assert result["follow_up_packet_count"] == 5
    assert result["follow_up_brief_blocker_count"] == 5
    assert result["calculation_prework_p1_count"] == 10
    assert result["calculation_snapshot_status"] == "owner_decision_required"
    assert result["errors"] == []


def test_verify_completion_snapshot_fails_when_gate_timestamp_drifts(tmp_path: Path) -> None:
    manifest_path = _copy_audit_files(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    snapshot_path = tmp_path / manifest["artifacts"]["completion_snapshot"]
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    snapshot["completion_gates"][0]["last_checked_at"] = "2099-01-01T00:00:00+00:00"
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    result = verify_completion_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert any("last_checked_at does not match manifest" in item for item in result["errors"])


def test_verify_completion_snapshot_fails_when_monitoring_timestamp_drifts(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_audit_files(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    monitoring_path = tmp_path / manifest["artifacts"]["system_audit_monitoring_snapshot"]
    monitoring = json.loads(monitoring_path.read_text(encoding="utf-8"))
    monitoring["generated_at"] = "2099-01-01T00:00:00+00:00"
    monitoring_path.write_text(
        json.dumps(monitoring, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    result = verify_completion_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert "manifest generated_at does not match system audit monitoring snapshot" in result[
        "errors"
    ]


def test_verify_completion_snapshot_fails_when_monitoring_writes_governance(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_audit_files(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    monitoring_path = tmp_path / manifest["artifacts"]["system_audit_monitoring_snapshot"]
    monitoring = json.loads(monitoring_path.read_text(encoding="utf-8"))
    monitoring["evidence_scope"]["writes_governance_records"] = True
    monitoring["refresh_results"]["ledger_pnl_direct_governance_record"][
        "record_write_status"
    ] = "written"
    monitoring_path.write_text(
        json.dumps(monitoring, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    result = verify_completion_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert "system audit monitoring snapshot evidence_scope is not fail-closed" in result[
        "errors"
    ]
    assert "system audit monitoring must not write Ledger PnL governance records" in result[
        "errors"
    ]


def test_verify_completion_snapshot_fails_when_follow_up_packet_approves_metrics(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_audit_files(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    packet_path = tmp_path / manifest["artifacts"]["owner_governance_follow_up_packet"]
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    packet["status"]["approves_metrics"] = True
    packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")

    result = verify_completion_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert any(
        "owner/governance follow-up packet status approves_metrics must be False" in item
        for item in result["errors"]
    )


def test_verify_completion_snapshot_fails_when_calculation_snapshot_approves_convention(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_audit_files(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    snapshot_path = tmp_path / manifest["artifacts"]["calculation_owner_decision_snapshot"]
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    snapshot["status"]["chooses_or_approves_conventions"] = True
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    result = verify_completion_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert any(
        "calculation owner decision snapshot status chooses_or_approves_conventions must be False"
        in item
        for item in result["errors"]
    )


def test_verify_completion_snapshot_fails_when_calculation_snapshot_drift_is_present(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_audit_files(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    snapshot_path = tmp_path / manifest["artifacts"]["calculation_owner_decision_snapshot"]
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    snapshot["drift_errors"] = ["P1-08 appears in open owner-decision rows"]
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    result = verify_completion_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert "calculation owner decision snapshot has drift_errors" in result["errors"]


def test_verify_completion_snapshot_fails_when_ledger_write_guard_is_removed(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_audit_files(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    packet_path = tmp_path / manifest["artifacts"]["owner_governance_follow_up_packet"]
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    ledger_packet = next(
        item
        for item in packet["blocker_packets"]
        if item["blocker_id"] == "ledger-pnl-direct-governance-record"
    )
    ledger_packet["authorization_required_commands_not_preapproved"] = []
    ledger_packet["prohibited_actions"] = []
    packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")

    result = verify_completion_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert "Ledger PnL --write command must remain authorization-required" in result["errors"]
    assert "Ledger PnL follow-up must prohibit unauthorized --write execution" in result[
        "errors"
    ]


def test_verify_completion_snapshot_fails_when_secret_boundary_is_removed(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_audit_files(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    packet_path = tmp_path / manifest["artifacts"]["owner_governance_follow_up_packet"]
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    secret_packet = next(
        item
        for item in packet["blocker_packets"]
        if item["blocker_id"] == "local-secret-hygiene"
    )
    secret_packet["prohibited_actions"] = []
    secret_packet["explicit_non_approval_boundary"] = "Secret values may be handled later."
    secret_packet["engineering_prework_available_now"] = []
    secret_packet["closure_evidence_after_external_input"] = []
    packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")

    result = verify_completion_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert "local secret follow-up must prohibit reading or pasting values" in result["errors"]
    assert "local secret follow-up must prohibit committing credential values" in result[
        "errors"
    ]
    assert "local secret follow-up must preserve explicit no-secret-values boundary" in result[
        "errors"
    ]
    assert "local-secret-hygiene missing engineering_prework_available_now" in result[
        "errors"
    ]
    assert "local-secret-hygiene missing closure_evidence_after_external_input" in result[
        "errors"
    ]
    assert "local secret follow-up must keep engineering prework value-free" in result[
        "errors"
    ]
    assert "local secret follow-up must require no-value closure evidence" in result[
        "errors"
    ]


def test_verify_completion_snapshot_fails_when_follow_up_brief_drops_blocker(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_audit_files(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    brief_path = tmp_path / manifest["artifacts"]["owner_governance_follow_up_brief_zh"]
    brief = brief_path.read_text(encoding="utf-8").replace(
        "calculation-display-p1-decisions",
        "calc-display-p1-decisions-removed",
    )
    brief_path.write_text(brief, encoding="utf-8")

    result = verify_completion_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert (
        "owner/governance follow-up brief missing blocker calculation-display-p1-decisions"
        in result["errors"]
    )


def test_verify_completion_snapshot_fails_when_follow_up_brief_boundary_is_removed(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_audit_files(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    brief_path = tmp_path / manifest["artifacts"]["owner_governance_follow_up_brief_zh"]
    brief = brief_path.read_text(encoding="utf-8").replace(
        "不授权 Ledger PnL `--write`",
        "Ledger PnL write may be handled later",
    )
    brief_path.write_text(brief, encoding="utf-8")

    result = verify_completion_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert (
        "owner/governance follow-up brief missing required phrase: 不授权 Ledger PnL `--write`"
        in result["errors"]
    )


def test_verify_completion_snapshot_fails_when_calculation_prework_map_drops_item(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_audit_files(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    matrix_path = tmp_path / manifest["artifacts"]["calculation_owner_decision_matrix"]
    matrix = matrix_path.read_text(encoding="utf-8").replace(
        "- **P1-10 Frontend formal aggregation**:",
        "- **P1-10-removed Frontend formal aggregation**:",
    )
    matrix_path.write_text(matrix, encoding="utf-8")

    result = verify_completion_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert "calculation prework map missing P1-10" in result["errors"]


def test_verify_completion_snapshot_fails_when_calculation_prework_boundary_is_removed(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_audit_files(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    matrix_path = tmp_path / manifest["artifacts"]["calculation_owner_decision_matrix"]
    matrix = matrix_path.read_text(encoding="utf-8").replace(
        "It does not choose or approve any convention; it does not change code; it does not certify routes/pages.",
        "It prepares implementation work.",
    )
    matrix_path.write_text(matrix, encoding="utf-8")

    result = verify_completion_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert (
        "calculation prework map missing boundary: does not choose or approve any convention"
        in result["errors"]
    )
    assert (
        "calculation prework map missing boundary: does not change code"
        in result["errors"]
    )
    assert (
        "calculation prework map missing boundary: does not certify routes/pages"
        in result["errors"]
    )


def test_verify_completion_snapshot_cli_outputs_json() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--manifest", str(MANIFEST)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["report_kind"] == "system_audit_completion_snapshot_verification"
    assert payload["status"] == "pass"
    assert payload["follow_up_packet_count"] == 5
    assert payload["follow_up_brief_blocker_count"] == 5
    assert payload["calculation_prework_p1_count"] == 10
    assert payload["errors"] == []
