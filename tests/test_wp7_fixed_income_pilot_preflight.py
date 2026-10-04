from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from tests.helpers import load_module


def _load_module():
    return load_module(
        "scripts.wp7_fixed_income_pilot_preflight",
        "scripts/wp7_fixed_income_pilot_preflight.py",
    )


def _sha(seed: str) -> str:
    import hashlib

    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def _ready_packet(module) -> dict[str, object]:
    packet = copy.deepcopy(module.default_handoff_packet())
    packet["release_id"] = "rel-fi-20260831"
    packet["target_environment"] = "prod-shanghai-a"
    packet["physical_bundle_scope"] = "duckdb-main"
    packet["owners"] = {
        role: {"name": role, "reference": f"TICKET-{role}"}
        for role in module.REQUIRED_OWNER_ROLES
    }
    packet["topology"] = {
        "topology_kind": "single_instance_whole_bundle_window",
        "whole_bundle_window": True,
        "reference": "OPS-TOPO-1",
    }
    packet["windows"] = {
        "maintenance": {
            "start": "2026-09-01T20:00:00+08:00",
            "end": "2026-09-01T22:00:00+08:00",
            "timezone": "Asia/Shanghai",
            "reference": "OPS-WINDOW-1",
        },
        "observation": {
            "duration_minutes": "45",
            "success_criteria": "api smoke stable and aliases consistent",
            "reference": "OPS-OBS-1",
        },
    }
    packet["recovery_objectives"] = {
        "rto": "30 minutes",
        "rpo": "0 minutes",
        "reference": "OPS-RTO-RPO-1",
    }
    packet["paths"] = {
        "target_environment_root": r"F:\ops\moss-prod",
        "current_bundle": r"F:\ops\moss-prod\data\duckdb-main-current.duckdb",
        "previous_bundle": r"F:\ops\moss-prod\data\duckdb-main-previous.duckdb",
        "candidate_bundle": r"F:\ops\moss-prod\release\candidate\duckdb-main-candidate.duckdb",
        "rollback_bundle_dir": r"F:\ops\moss-prod\release\rollback",
        "governance_ledger_dir": r"F:\ops\moss-prod\governance",
        "backup_dir": r"F:\ops\moss-prod\backup",
        "receipt_dir": r"F:\ops\moss-prod\receipts",
        "log_dir": r"F:\ops\moss-prod\logs",
        "backend_build_artifact": r"F:\ops\moss-prod\artifacts\backend.zip",
        "frontend_build_artifact": r"F:\ops\moss-prod\artifacts\frontend.zip",
    }
    packet["writer_stop_proofs"] = {
        "keepalive": {
            "status": "paused",
            "summary": "paused",
            "reference": "OPS-STOP-1",
        },
        "scheduler": {
            "status": "disabled",
            "summary": "disabled",
            "reference": "OPS-STOP-2",
        },
        "supervisor": {
            "status": "stopped",
            "summary": "stopped",
            "reference": "OPS-STOP-3",
        },
        "queue": {"status": "drained", "summary": "empty", "reference": "OPS-STOP-4"},
        "worker": {
            "status": "stopped",
            "summary": "no worker",
            "reference": "OPS-STOP-5",
        },
        "api": {
            "status": "quiesced",
            "summary": "read only",
            "reference": "OPS-STOP-6",
        },
        "connections": {
            "status": "no_active_writers",
            "summary": "0 writer sessions",
            "reference": "OPS-STOP-7",
        },
        "wal": {"status": "stopped", "summary": "no growth", "reference": "OPS-STOP-8"},
    }
    packet["backups"] = {
        key: {"sha256": _sha(chr(97 + index)), "reference": f"OPS-BACKUP-{index + 1}"}
        for index, key in enumerate(module.REQUIRED_BACKUP_FIELDS)
    }
    packet["approvals"] = {
        "required_states": list(module.REQUIRED_APPROVAL_STATES),
        "authority": {"reference": "OPS-AUTH-1", "digest": _sha("f")},
        "states": {
            key: {
                "status": True,
                "reference": f"OPS-APPROVAL-{index + 1}",
                "digest": _sha(chr(103 + index)),
                "summary": f"{key} complete",
            }
            for index, key in enumerate(module.REQUIRED_APPROVAL_STATES)
        },
    }
    packet["build_receipts"] = {
        key: {"reference": f"OPS-BUILD-{index + 1}", "digest": _sha(chr(108 + index))}
        for index, key in enumerate(module.REQUIRED_BUILD_FIELDS)
    }
    packet["platform_evidence"] = {
        "github": {"reference": "OPS-GH-1", "digest": _sha("o")},
        "formal_authority": {"reference": "OPS-AUTH-2", "digest": _sha("p")},
    }
    packet["rollback_plan"] = {
        "rollback_mode": module.SEALED_BUNDLE_REACTIVATE,
        "reason_reference": "OPS-ROLLBACK-1",
        module.SEALED_BUNDLE_REACTIVATE: {
            "same_maintenance_window": True,
            "writer_still_stopped": True,
            "other_domain_writes_present": False,
            "previous_bundle_reference": "OPS-PREVIOUS-1",
            "previous_bundle_sha256": _sha("q"),
        },
        module.FORWARD_REBUILD: {
            "latest_base_bundle_reference": "OPS-BASE-1",
            "latest_base_bundle_sha256": _sha("r"),
            "rollback_candidate_reference": "OPS-ROLLBACK-CANDIDATE-1",
            "rollback_candidate_sha256": _sha("s"),
            "revalidation_reference": "OPS-REVALIDATE-1",
            "reapproval_reference": "OPS-REAPPROVE-1",
        },
    }
    return packet


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def test_default_pending_template_is_fail_closed() -> None:
    module = _load_module()

    report = module.build_fixed_income_pilot_preflight_report()

    assert report["status"] == "blocked"
    assert report["go_no_go"] == "no_go"
    assert report["release_eligible"] is False
    assert report["authorizes_pilot"] is False
    assert report["production_writes"] is False
    assert "pilot_identity_pending" in report["blocker_reason_codes"]
    assert "owner_roster_pending" in report["blocker_reason_codes"]
    assert report["packet_observation"]["packet_source"] == "default_pending_template"
    serialized = json.dumps(report, ensure_ascii=False)
    assert r"F:\ops" not in serialized


def test_complete_structure_still_does_not_authorize_release_or_production() -> None:
    module = _load_module()
    packet = _ready_packet(module)

    report = module.build_fixed_income_pilot_preflight_report(
        packet=packet, packet_source="unit_test"
    )

    assert report["status"] == "awaiting_owner_execution"
    assert report["go_no_go"] == "pending_owner_execution"
    assert report["release_eligible"] is False
    assert report["authorizes_pilot"] is False
    assert report["production_writes"] is False
    assert report["packet_observation"]["all_gates_passed"] is True
    assert report["blocker_reason_codes"] == []
    assert report["packet_observation"]["packet_source"] == "unit_test"
    assert all(gate["outcome"] == "pass" for gate in report["gates"])
    serialized = json.dumps(report, ensure_ascii=False)
    assert r"F:\ops\moss-prod" not in serialized


def test_forward_rebuild_requires_its_branch_specific_fields() -> None:
    module = _load_module()
    packet = _ready_packet(module)
    packet["rollback_plan"]["rollback_mode"] = module.FORWARD_REBUILD
    packet["rollback_plan"][module.FORWARD_REBUILD]["reapproval_reference"] = "PENDING"

    report = module.build_fixed_income_pilot_preflight_report(packet=packet)

    assert report["status"] == "blocked"
    rollback_gate = next(
        g for g in report["gates"] if g["name"] == "rollback_branch_complete"
    )
    assert rollback_gate["reason_code"] == "rollback_branch_pending"
    assert (
        "rollback_plan.forward_rebuild.reapproval_reference" in rollback_gate["fields"]
    )


def test_identity_and_window_fields_must_match_allowed_pilot_shape() -> None:
    module = _load_module()
    packet = _ready_packet(module)
    packet["target_environment"] = "prod-b"
    packet["physical_bundle_scope"] = "duckdb-secondary"
    packet["runbook_reference"] = "docs/runbooks/other.md"
    packet["topology"]["whole_bundle_window"] = False
    packet["windows"]["maintenance"]["end"] = "2026-09-01T19:00:00+08:00"
    packet["windows"]["observation"]["duration_minutes"] = "0"

    report = module.build_fixed_income_pilot_preflight_report(packet=packet)

    identity_gate = next(
        g for g in report["gates"] if g["name"] == "pilot_identity_complete"
    )
    assert identity_gate["outcome"] == "blocked"
    assert "physical_bundle_scope" in identity_gate["fields"]
    assert "runbook_reference" in identity_gate["fields"]
    topology_gate = next(g for g in report["gates"] if g["name"] == "topology_complete")
    assert "topology.whole_bundle_window" in topology_gate["fields"]
    maintenance_gate = next(
        g for g in report["gates"] if g["name"] == "maintenance_window_complete"
    )
    assert "windows.maintenance.order" in maintenance_gate["fields"]
    observation_gate = next(
        g for g in report["gates"] if g["name"] == "observation_window_complete"
    )
    assert "windows.observation.duration_minutes" in observation_gate["fields"]


def test_maintenance_window_requires_aware_iso_and_timezone_match() -> None:
    module = _load_module()
    packet = _ready_packet(module)
    packet["windows"]["maintenance"]["start"] = "2026-09-01T20:00:00"
    packet["windows"]["maintenance"]["end"] = "2026-09-01T22:00:00+00:00"

    report = module.build_fixed_income_pilot_preflight_report(packet=packet)

    maintenance_gate = next(
        g for g in report["gates"] if g["name"] == "maintenance_window_complete"
    )
    assert "windows.maintenance.start:timezone_required" in maintenance_gate["fields"]
    assert "windows.maintenance.end:timezone_mismatch" in maintenance_gate["fields"]


def test_paths_must_be_absolute_and_normalized() -> None:
    module = _load_module()
    packet = _ready_packet(module)
    packet["paths"]["candidate_bundle"] = r"candidate\bundle.duckdb"
    packet["paths"]["current_bundle"] = r"F:\ops\moss-prod\data\..\current.duckdb"

    report = module.build_fixed_income_pilot_preflight_report(packet=packet)

    paths_gate = next(
        g for g in report["gates"] if g["name"] == "governed_paths_complete"
    )
    assert paths_gate["outcome"] == "blocked"
    assert "paths.candidate_bundle:not_absolute" in paths_gate["fields"]
    assert "paths.current_bundle:not_normalized" in paths_gate["fields"]


def test_current_previous_and_candidate_paths_must_be_distinct() -> None:
    module = _load_module()
    packet = _ready_packet(module)
    packet["paths"]["candidate_bundle"] = packet["paths"]["current_bundle"].lower()

    report = module.build_fixed_income_pilot_preflight_report(packet=packet)

    paths_gate = next(
        g for g in report["gates"] if g["name"] == "governed_paths_complete"
    )
    assert "paths.bundle_identity:not_distinct" in paths_gate["fields"]


def test_false_or_pending_approval_state_blocks() -> None:
    module = _load_module()
    packet = _ready_packet(module)
    packet["approvals"]["states"]["formal_use_allowed"]["status"] = False
    packet["approvals"]["states"]["closure_approved"]["summary"] = "PENDING"

    report = module.build_fixed_income_pilot_preflight_report(packet=packet)

    approvals_gate = next(
        g for g in report["gates"] if g["name"] == "five_state_approvals_complete"
    )
    assert approvals_gate["outcome"] == "blocked"
    assert "approvals.states.formal_use_allowed.status" in approvals_gate["fields"]
    assert "approvals.states.closure_approved.summary" in approvals_gate["fields"]


def test_writer_stop_status_mapping_is_exact() -> None:
    module = _load_module()
    packet = _ready_packet(module)
    packet["writer_stop_proofs"]["keepalive"]["status"] = "disabled"

    report = module.build_fixed_income_pilot_preflight_report(packet=packet)

    writer_gate = next(
        g for g in report["gates"] if g["name"] == "writer_stop_proofs_complete"
    )
    assert "keepalive:disabled" in writer_gate["fields"]


def test_safe_output_path_is_exclusive_and_confined(tmp_path: Path) -> None:
    module = _load_module()
    repo = tmp_path / "repo"
    (repo / "output").mkdir(parents=True)
    (repo / ".tmp").mkdir()
    report = {"status": "blocked"}
    output = repo / "output" / "pilot-preflight.json"

    assert (
        module.write_report_exclusive(output=output, report=report, repo_root=repo)
        == output.resolve()
    )
    assert json.loads(output.read_text(encoding="utf-8")) == report
    with pytest.raises(FileExistsError):
        module.write_report_exclusive(output=output, report=report, repo_root=repo)
    (repo / "docs").mkdir()
    with pytest.raises(ValueError, match="output/ or .tmp"):
        module.write_report_exclusive(
            output=repo / "docs" / "pilot.json", report=report, repo_root=repo
        )


def test_safe_output_path_rejects_symlink_parent_deterministically(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    repo = tmp_path / "repo"
    linked_output = repo / "output"
    (repo / ".tmp").mkdir(parents=True)
    linked_output.mkdir()
    original_is_symlink = Path.is_symlink

    def _is_symlink(path: Path) -> bool:
        return path == linked_output or original_is_symlink(path)

    monkeypatch.setattr(Path, "is_symlink", _is_symlink)

    with pytest.raises(ValueError, match="symlink_junction_or_reparse"):
        module._safe_output_path(linked_output / "pilot.json", repo_root=repo)


def test_cli_prints_report_and_returns_nonzero_when_blocked(tmp_path: Path) -> None:
    module = _load_module()
    script = module.ROOT / "scripts" / "wp7_fixed_income_pilot_preflight.py"

    completed = subprocess.run(
        [sys.executable, str(script), "--generated-at", "2026-08-31T12:00:00+08:00"],
        cwd=module.ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    assert completed.returncode == 2
    payload = json.loads(completed.stdout)
    assert payload["status"] == "blocked"
    assert payload["packet_observation"]["packet_source"] == "default_pending_template"


def test_cli_can_read_packet_and_write_safe_output(tmp_path: Path) -> None:
    module = _load_module()
    repo = module.ROOT
    packet_path = tmp_path / "packet.json"
    output_path = repo / ".tmp" / f"wp7-preflight-{tmp_path.name}.json"
    _write_json(packet_path, _ready_packet(module))
    script = module.ROOT / "scripts" / "wp7_fixed_income_pilot_preflight.py"
    if output_path.exists():
        output_path.unlink()

    try:
        completed = subprocess.run(
            [
                sys.executable,
                str(script),
                "--packet",
                str(packet_path),
                "--output",
                str(output_path),
                "--generated-at",
                "2026-08-31T12:00:00+08:00",
            ],
            cwd=tmp_path,
            check=False,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            text=True,
        )

        assert completed.returncode == 3, completed.stderr
        report = json.loads(completed.stdout)
        assert report["status"] == "awaiting_owner_execution"
        assert report["release_eligible"] is False
        assert output_path.exists()
        persisted = json.loads(output_path.read_text(encoding="utf-8"))
        assert (
            persisted["packet_observation"]["packet_sha256"]
            == report["packet_observation"]["packet_sha256"]
        )
    finally:
        output_path.unlink(missing_ok=True)


def test_cli_missing_packet_is_sanitized_invalid(tmp_path: Path) -> None:
    module = _load_module()
    script = module.ROOT / "scripts" / "wp7_fixed_income_pilot_preflight.py"

    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--packet",
            str(tmp_path / "missing.json"),
        ],
        cwd=module.ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    assert completed.returncode == 1
    assert "Traceback" not in completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["status"] == "invalid"
    assert payload["blocker_reason_codes"] == ["packet_unavailable"]
    assert str(tmp_path) not in completed.stdout


def test_cli_rejects_duplicate_json_keys_without_echoing_path(tmp_path: Path) -> None:
    module = _load_module()
    packet_path = tmp_path / "duplicate.json"
    packet_path.write_text('{"release_id":"a","release_id":"b"}', encoding="utf-8")
    script = module.ROOT / "scripts" / "wp7_fixed_income_pilot_preflight.py"

    completed = subprocess.run(
        [sys.executable, str(script), "--packet", str(packet_path)],
        cwd=module.ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    payload = json.loads(completed.stdout)
    assert completed.returncode == 1
    assert payload["blocker_reason_codes"] == ["packet_duplicate_keys"]
    assert str(packet_path) not in completed.stdout


def test_cli_rejects_non_utf8_and_oversized_packets(tmp_path: Path) -> None:
    module = _load_module()
    script = module.ROOT / "scripts" / "wp7_fixed_income_pilot_preflight.py"
    bad_utf8 = tmp_path / "bad-utf8.json"
    bad_utf8.write_bytes(b"\xff\xfe\xfd")
    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b"{" + (b"a" * (1024 * 1024 + 1)) + b"}")

    utf8_run = subprocess.run(
        [sys.executable, str(script), "--packet", str(bad_utf8)],
        cwd=module.ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )
    oversize_run = subprocess.run(
        [sys.executable, str(script), "--packet", str(oversized)],
        cwd=module.ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    assert json.loads(utf8_run.stdout)["blocker_reason_codes"] == ["packet_not_utf8"]
    assert json.loads(oversize_run.stdout)["blocker_reason_codes"] == [
        "packet_too_large"
    ]


def test_cli_rejects_invalid_generated_at_without_traceback(tmp_path: Path) -> None:
    module = _load_module()
    script = module.ROOT / "scripts" / "wp7_fixed_income_pilot_preflight.py"

    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--generated-at",
            "2026-08-31T12:00:00",
        ],
        cwd=module.ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    payload = json.loads(completed.stdout)
    assert completed.returncode == 1
    assert payload["status"] == "invalid"
    assert payload["blocker_reason_codes"] == ["generated_at_invalid"]
    assert "Traceback" not in completed.stderr


def test_cli_print_template_outputs_default_packet_and_nonzero() -> None:
    module = _load_module()
    script = module.ROOT / "scripts" / "wp7_fixed_income_pilot_preflight.py"

    completed = subprocess.run(
        [sys.executable, str(script), "--print-template"],
        cwd=module.ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    assert completed.returncode == 4
    payload = json.loads(completed.stdout)
    assert payload == module.default_handoff_packet()


def test_runbook_contract_keeps_blocked_and_non_authoritative_boundary() -> None:
    module = _load_module()
    runbook = (module.ROOT / module.RUNBOOK_PATH).read_text(encoding="utf-8")

    assert "执行状态：**BLOCKED" in runbook
    assert "scripts/wp7_fixed_income_pilot_preflight.py" in runbook
    assert "authorizes_pilot=false" in runbook
    assert "production_writes=false" in runbook
    assert "sealed_bundle_reactivate" in runbook
    assert "forward_rebuild" in runbook
