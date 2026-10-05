from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.app.governance.release_approval import (
    DEFAULT_REGISTRY_PATH,
    load_release_approval_registry,
    validate_registry_structure,
)
from backend.app.schemas.release_approval import ReleaseApprovalRegistry, canonical_sha256
from tests.helpers import load_module

ROOT = Path(__file__).resolve().parents[1]


def _registry_payload() -> dict[str, object]:
    return json.loads(DEFAULT_REGISTRY_PATH.read_text(encoding="utf-8"))


def test_registry_tracks_exactly_live_eight_page_checkers_and_eight_open_p1_ids() -> None:
    registry = load_release_approval_registry()
    live_page_scripts = sorted(
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "scripts").glob("check_*_business_owner_approval.py")
    )
    completion = load_module(
        "scripts.verify_system_audit_completion_snapshot",
        "scripts/verify_system_audit_completion_snapshot.py",
    )

    assert len(registry.entries) == 16
    assert sorted(
        entry.command.argv[0]
        for entry in registry.entries
        if entry.subject_kind == "page"
    ) == live_page_scripts
    assert [
        entry.subject_key
        for entry in registry.entries
        if entry.subject_kind == "calculation_p1"
    ] == completion.EXPECTED_OPEN_CALCULATION_P1_IDS
    assert all(entry.authority_policy_id == "PENDING" for entry in registry.entries)
    assert all(entry.scope_mapping.status == "PENDING" for entry in registry.entries)


def test_structure_gate_passes_while_operational_authority_remains_pending() -> None:
    checker = load_module(
        "scripts.check_release_approval_registry",
        "scripts/check_release_approval_registry.py",
    )

    report = checker.build_report()

    assert report["status"] == "structure_passed"
    assert report["entry_count"] == 16
    assert report["pending_authority_policy_count"] == 16
    assert report["pending_scope_mapping_count"] == 16
    assert report["gate_scope"] == "structure_only"
    assert report["approval_decision"] == "not_evaluated"
    assert report["fail_closed_for_release_approval"] is True
    assert report["release_gate_eligible"] is False
    assert report["operational_approval_ready"] is False
    digest_payload = {key: value for key, value in report.items() if key != "receipt_sha256"}
    assert report["receipt_sha256"] == canonical_sha256(digest_payload)


@pytest.mark.parametrize(
    ("argv", "reason_prefix"),
    [
        (
            [(ROOT.parent / "outside" / "check.py").as_posix(), "--require-captured"],
            "registry_command_path_not_repository_relative",
        ),
        (
            ["scripts/../outside.py", "--require-captured"],
            "registry_command_path_not_repository_relative",
        ),
        (
            ["scripts/check_average_balance_business_owner_approval.py;whoami", "--require-captured"],
            "registry_command_contains_shell_syntax",
        ),
        (
            [
                "scripts/check_average_balance_business_owner_approval.py",
                "--require-captured",
                "--output",
                "receipt.json",
            ],
            "registry_page_command_not_allowlisted",
        ),
    ],
)
def test_registry_rejects_non_allowlisted_paths_shell_syntax_and_arguments(
    argv: list[str],
    reason_prefix: str,
) -> None:
    payload = deepcopy(_registry_payload())
    payload["entries"][0]["command"]["argv"] = argv
    registry = ReleaseApprovalRegistry.model_validate(payload)

    reasons = validate_registry_structure(registry, repo_root=ROOT)

    assert any(reason.startswith(reason_prefix) for reason in reasons)


def test_registry_schema_rejects_environment_injection() -> None:
    payload = deepcopy(_registry_payload())
    payload["entries"][0]["command"]["env"] = {"PYTHONPATH": "outside"}

    with pytest.raises(ValidationError):
        ReleaseApprovalRegistry.model_validate(payload)


def test_calculation_adapter_calls_read_only_builder_not_refresh_main(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = load_module(
        "scripts.check_calculation_p1_owner_decisions",
        "scripts/check_calculation_p1_owner_decisions.py",
    )
    calls: list[str] = []

    def fake_build_snapshot():
        calls.append("build_snapshot")
        return {
            "drift_errors": [],
            "capture_template": {"captured_decision_ids": ["P1-01"]},
            "meeting_record": {"is_complete": True},
        }

    monkeypatch.setattr(adapter, "build_snapshot", fake_build_snapshot)

    status = adapter.build_status("P1-01")

    assert calls == ["build_snapshot"]
    assert status["read_only"] is True
    assert status["states"] == {
        "evidence_captured": True,
        "machine_validated": True,
        "business_approved": False,
        "formal_use_allowed": False,
        "closure_approved": False,
    }
