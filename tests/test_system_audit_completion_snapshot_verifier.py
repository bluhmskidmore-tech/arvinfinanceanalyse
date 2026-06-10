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
    manifest_path = audit_dir / "manifest.json"
    snapshot_path = audit_dir / "completion-snapshot.json"
    follow_up_packet_path = audit_dir / "owner-governance-follow-up-packet.json"
    follow_up_brief_path = audit_dir / "owner-governance-follow-up-brief.zh.md"
    manifest["artifacts"]["completion_snapshot"] = "docs/audits/completion-snapshot.json"
    manifest["artifacts"][
        "owner_governance_follow_up_packet"
    ] = "docs/audits/owner-governance-follow-up-packet.json"
    manifest["artifacts"][
        "owner_governance_follow_up_brief_zh"
    ] = "docs/audits/owner-governance-follow-up-brief.zh.md"
    snapshot["source_artifacts"][
        "owner_governance_follow_up_packet"
    ] = "docs/audits/owner-governance-follow-up-packet.json"
    snapshot["source_artifacts"][
        "owner_governance_follow_up_brief_zh"
    ] = "docs/audits/owner-governance-follow-up-brief.zh.md"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    follow_up_packet_path.write_text(
        json.dumps(follow_up_packet, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    follow_up_brief_path.write_text(follow_up_brief, encoding="utf-8")
    return manifest_path


def test_verify_completion_snapshot_passes_for_checked_in_audit_package() -> None:
    result = verify_completion_snapshot(manifest_path=MANIFEST)

    assert result["status"] == "pass"
    assert result["open_blocker_count"] == 5
    assert result["completion_gate_count"] == 5
    assert result["follow_up_packet_count"] == 5
    assert result["follow_up_brief_blocker_count"] == 5
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
    assert payload["errors"] == []
