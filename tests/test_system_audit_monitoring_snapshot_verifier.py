from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.verify_system_audit_monitoring_snapshot import verify_monitoring_snapshot


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_system_audit_monitoring_snapshot.py"
MANIFEST = ROOT / "docs" / "audits" / "2026-06-10-system-audit-manifest.json"
ARTIFACT_KEYS = [
    "system_audit_monitoring_snapshot",
    "completion_snapshot",
    "system_audit_pulse_snapshot",
    "calculation_owner_decision_snapshot",
    "direct_app_mcp_gitnexus_tool_surface_snapshot",
    "local_secret_hygiene_snapshot",
    "ledger_pnl_direct_governance_record_snapshot",
    "owner_governance_follow_up_packet",
    "owner_governance_follow_up_brief_zh",
    "calculation_owner_decision_matrix",
]


def _copy_monitoring_package(tmp_path: Path) -> Path:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    audit_dir = tmp_path / "docs" / "audits"
    audit_dir.mkdir(parents=True)
    original_follow_up_packet = manifest["artifacts"]["owner_governance_follow_up_packet"]
    for key in ARTIFACT_KEYS:
        source = ROOT / manifest["artifacts"][key]
        target = audit_dir / source.name
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        manifest["artifacts"][key] = f"docs/audits/{source.name}"

    completion_path = tmp_path / manifest["artifacts"]["completion_snapshot"]
    completion = json.loads(completion_path.read_text(encoding="utf-8"))
    for source_key in [
        "owner_governance_follow_up_packet",
        "owner_governance_follow_up_brief_zh",
    ]:
        completion["source_artifacts"][source_key] = manifest["artifacts"][source_key]
    completion_path.write_text(
        json.dumps(completion, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    brief_path = tmp_path / manifest["artifacts"]["owner_governance_follow_up_brief_zh"]
    brief = brief_path.read_text(encoding="utf-8").replace(
        original_follow_up_packet,
        manifest["artifacts"]["owner_governance_follow_up_packet"],
    )
    brief = brief.replace(
        "`2026-06-10-owner-governance-follow-up-packet.json`",
        f"`{manifest['artifacts']['owner_governance_follow_up_packet']}`",
    )
    brief_path.write_text(brief, encoding="utf-8")

    manifest_path = audit_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest_path


def _load_package_json(manifest_path: Path, key: str) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return json.loads((manifest_path.parents[2] / manifest["artifacts"][key]).read_text(encoding="utf-8"))


def _write_package_json(manifest_path: Path, key: str, payload: dict) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    path = manifest_path.parents[2] / manifest["artifacts"][key]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_verify_monitoring_snapshot_passes_for_checked_in_audit_package() -> None:
    result = verify_monitoring_snapshot(manifest_path=MANIFEST)

    assert result["status"] == "pass"
    assert result["generated_at"] == "2026-06-10T21:25:00+08:00"
    assert result["open_blocker_count"] == 5
    assert result["completion_status"] == "pass"
    assert result["pulse_status"] == "pass"
    assert result["pulse_completion_state"] == "not_complete"
    assert result["errors"] == []


def test_verify_monitoring_snapshot_fails_when_monitoring_write_flag_drifts(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_monitoring_package(tmp_path)
    monitoring = _load_package_json(manifest_path, "system_audit_monitoring_snapshot")
    monitoring["write_outputs"] = False
    _write_package_json(manifest_path, "system_audit_monitoring_snapshot", monitoring)

    result = verify_monitoring_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert "monitoring write_outputs expected True, got False" in result["errors"]


def test_verify_monitoring_snapshot_fails_when_ledger_formal_use_is_promoted(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_monitoring_package(tmp_path)
    monitoring = _load_package_json(manifest_path, "system_audit_monitoring_snapshot")
    monitoring["refresh_results"]["ledger_pnl_direct_governance_record"][
        "formal_use_allowed"
    ] = True
    _write_package_json(manifest_path, "system_audit_monitoring_snapshot", monitoring)

    result = verify_monitoring_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert "Ledger PnL formal_use_allowed must be false" in result["errors"]


def test_verify_monitoring_snapshot_fails_when_direct_app_evidence_is_claimed(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_monitoring_package(tmp_path)
    monitoring = _load_package_json(manifest_path, "system_audit_monitoring_snapshot")
    monitoring["refresh_results"]["direct_app_mcp_gitnexus_tool_surface"][
        "direct_app_mcp_evidence_captured"
    ] = True
    _write_package_json(manifest_path, "system_audit_monitoring_snapshot", monitoring)

    result = verify_monitoring_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert "direct App MCP evidence captured must be false" in result["errors"]


def test_verify_monitoring_snapshot_fails_when_secret_hygiene_is_cleared(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_monitoring_package(tmp_path)
    monitoring = _load_package_json(manifest_path, "system_audit_monitoring_snapshot")
    monitoring["refresh_results"]["local_secret_hygiene"]["clears_secret_scan"] = True
    _write_package_json(manifest_path, "system_audit_monitoring_snapshot", monitoring)

    result = verify_monitoring_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert "local secret refresh clears_secret_scan must be false" in result["errors"]


def test_verify_monitoring_snapshot_fails_when_pulse_completion_state_drifts(
    tmp_path: Path,
) -> None:
    manifest_path = _copy_monitoring_package(tmp_path)
    monitoring = _load_package_json(manifest_path, "system_audit_monitoring_snapshot")
    monitoring["pulse"]["completion_state"] = "complete"
    _write_package_json(manifest_path, "system_audit_monitoring_snapshot", monitoring)

    result = verify_monitoring_snapshot(manifest_path=manifest_path, repo_root=tmp_path)

    assert result["status"] == "fail"
    assert "monitoring pulse completion_state expected 'not_complete', got 'complete'" in result[
        "errors"
    ]


def test_verify_monitoring_snapshot_cli_outputs_json() -> None:
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
    assert payload["report_kind"] == "system_audit_monitoring_snapshot_verification"
    assert payload["status"] == "pass"
    assert payload["open_blocker_count"] == 5
    assert payload["pulse_completion_state"] == "not_complete"
    assert payload["errors"] == []
