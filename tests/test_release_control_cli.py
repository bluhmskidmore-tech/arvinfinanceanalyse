from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.schemas.release_approval import (
    build_approval_gate_receipt,
    build_authority_approval_receipt,
)
from tests.helpers import load_module


def _load_release_control_cli():
    return load_module(
        "scripts.release_control",
        "scripts/release_control.py",
    )


def _plan_payload() -> dict[str, object]:
    return {
        "scopes": [
            {
                "scope_kind": "physical_bundle",
                "scope_key": "duckdb-main",
                "expected_revision": 1,
            },
            {
                "scope_kind": "logical_lane",
                "scope_key": "bond-analytics-risk-tensor",
                "expected_revision": 1,
            },
            {
                "scope_kind": "logical_lane",
                "scope_key": "bond-analytics-core",
                "expected_revision": 1,
            },
        ],
    }


def _manifest_payload() -> dict[str, object]:
    return {
        "target_environment": "test",
        "git_sha": "0123456789abcdef0123456789abcdef01234567",
        "schema_heads": {"postgres": ["7d1a2c3e4f50"], "duckdb": ["v45"]},
        "builds": {
            "backend": {
                "git_sha": "0123456789abcdef0123456789abcdef01234567",
                "build_sha256": "D" * 64,
            },
            "frontend": {
                "git_sha": "89abcdef0123456789abcdef0123456789abcdef",
                "build_sha256": "E" * 64,
            },
        },
        "contracts": {
            "openapi_sha256": "A" * 64,
            "dto_sha256": "B" * 64,
            "receipt_sha256": "C" * 64,
        },
        "numeric_policy": {
            "policy_version": "exact-numeric-v1",
            "policy_sha256": "6" * 64,
        },
        "required_validation_gates": ["schema", "contracts", "governance"],
        "approval_registry_sha256": "7" * 64,
        "approval_requirements": [
            {
                "approval_id": "test:release-bundle",
                "subject_kind": "page",
                "subject_key": "release-bundle",
                "required_states": [
                    "evidence_captured",
                    "machine_validated",
                    "business_approved",
                    "formal_use_allowed",
                    "closure_approved",
                ],
            }
        ],
        "scopes": [
            {
                "scope_kind": "logical_lane",
                "scope_key": "bond-analytics-risk-tensor",
                "artifact_kind": "bond-risk-tensor-candidate",
                "artifact_version": "risk-v6",
                "artifact_sha256": "F" * 64,
                "evidence_sha256": "1" * 64,
            },
            {
                "scope_kind": "logical_lane",
                "scope_key": "bond-analytics-core",
                "artifact_kind": "bond-analytics-candidate",
                "artifact_version": "bond-v6",
                "artifact_sha256": "2" * 64,
                "evidence_sha256": "3" * 64,
            },
            {
                "scope_kind": "physical_bundle",
                "scope_key": "duckdb-main",
                "artifact_kind": "duckdb-main",
                "artifact_version": "duckdb-main-2026-08-31T120000Z",
                "artifact_sha256": "4" * 64,
                "evidence_sha256": "5" * 64,
                "contained_lane_versions": {
                    "bond-analytics-risk-tensor": "risk-v6",
                    "bond-analytics-core": "bond-v6",
                },
            },
        ],
    }


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _approval_receipt_payload() -> dict[str, object]:
    receipt = build_authority_approval_receipt(
        {
            "release_id": "release-2026-08-31-bond-risk-v1",
            "manifest_sha256": "A" * 64,
            "registry_sha256": "7" * 64,
            "authority_reference": "test-authority-receipt",
            "authority_verifier_receipt_sha256": "8" * 64,
            "decision": "approved",
            "decided_at": "2026-08-30T00:00:00Z",
            "expires_at": "2099-01-01T00:00:00Z",
            "revoked_at": None,
            "revocation_reference": None,
            "subjects": [
                {
                    "approval_id": "test:release-bundle",
                    "subject_kind": "page",
                    "subject_key": "release-bundle",
                    "authority_policy_id": "test-policy",
                    "scope_kind": "logical_lane",
                    "scope_key": "bond-analytics-risk-tensor",
                    "decision": "approved",
                    "states": {
                        "evidence_captured": True,
                        "machine_validated": True,
                        "business_approved": True,
                        "formal_use_allowed": True,
                        "closure_approved": True,
                    },
                    "evidence_receipt_sha256": "9" * 64,
                }
            ],
        }
    )
    return receipt.model_dump(mode="json")


def _promote_success_receipt() -> dict[str, object]:
    return {
        "action": "promote",
        "outcome": "applied",
        "status": "current",
        "release_id": "release-2026-08-31-bond-risk-v1",
        "manifest_digest": "A" * 64,
        "target_environment": "test",
    }


def _rollback_success_receipt() -> dict[str, object]:
    return {
        "action": "rollback",
        "outcome": "applied",
        "status": "current",
        "release_id": "release-a",
        "manifest_digest": "B" * 64,
        "target_environment": "test",
    }


def test_prepare_command_prints_structured_receipt_and_returns_zero(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    cli = _load_release_control_cli()
    manifest_file = tmp_path / "manifest.json"
    _write_json(manifest_file, _manifest_payload())
    monkeypatch.setattr(
        cli,
        "run_prepare",
        lambda **_kwargs: {
            "status": "candidate",
            "release_id": "release-2026-08-31-bond-risk-v1",
            "content_sha256": "A" * 64,
            "exit_code": 0,
        },
    )

    exit_code = cli.main(
        [
            "prepare",
            "--release-id",
            "release-2026-08-31-bond-risk-v1",
            "--manifest-file",
            str(manifest_file),
            "--freeze",
        ]
    )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["status"] == "candidate"


def test_approve_command_accepts_only_structured_authority_receipt_file(
    tmp_path: Path,
) -> None:
    cli = _load_release_control_cli()
    approval_file = tmp_path / "approval.json"
    authority_receipt = _approval_receipt_payload()
    _write_json(approval_file, {"authority_receipt": authority_receipt})
    calls: list[dict[str, object]] = []

    class FakeService:
        def record_approval(self, **kwargs):
            calls.append(kwargs)
            return {
                "action": "approve-record",
                "outcome": "applied",
                "release_id": kwargs["release_id"],
            }

    result = cli.run_approve_record(
        release_id="release-2026-08-31-bond-risk-v1",
        approval_file=approval_file,
        service=FakeService(),
    )

    assert result["exit_code"] == 0
    assert calls == [
        {
            "release_id": "release-2026-08-31-bond-risk-v1",
            "manifest_digest": "A" * 64,
            "authority_receipt": authority_receipt,
            "idempotency_key": None,
        }
    ]


def test_approve_cli_does_not_expose_approved_by_or_free_text_authority_flags(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cli = _load_release_control_cli()

    exit_code = cli.main(
        [
            "approve-record",
            "--release-id",
            "release-2026-08-31-bond-risk-v1",
            "--approved-by",
            "application-user-id",
            "--authority-reference",
            "non-empty-free-text",
        ]
    )

    assert exit_code == cli.EXIT_INVALID
    assert json.loads(capsys.readouterr().out)["error_code"] == "invalid_input"


def test_promote_command_passes_whole_bundle_plan_and_expected_revisions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cli = _load_release_control_cli()
    plan_file = tmp_path / "plan.json"
    payload = _plan_payload()
    _write_json(plan_file, payload)
    calls: list[dict[str, object]] = []

    def fake_run_promote(**kwargs):
        calls.append(kwargs)
        return {"status": "current", "exit_code": 0}

    monkeypatch.setattr(cli, "run_promote", fake_run_promote)

    assert (
        cli.main(
            [
                "promote",
                "--release-id",
                "release-2026-08-31-bond-risk-v1",
                "--plan-file",
                str(plan_file),
                "--idempotency-key",
                "promote-2026-08-31-01",
            ]
        )
        == 0
    )
    assert calls == [
        {
            "release_id": "release-2026-08-31-bond-risk-v1",
            "scopes": payload["scopes"],
            "idempotency_key": "promote-2026-08-31-01",
            "receipt_file": None,
        }
    ]


def test_promote_retry_with_same_idempotency_key_returns_same_receipt(
    tmp_path: Path,
) -> None:
    cli = _load_release_control_cli()
    plan_file = tmp_path / "plan.json"
    _write_json(plan_file, _plan_payload())

    class FakeService:
        def __init__(self) -> None:
            self.receipt = {
                "status": "current",
                "release_id": "release-2026-08-31-bond-risk-v1",
                "idempotency_key": "promote-2026-08-31-01",
            }

        def promote_release_bundle(self, **_kwargs):
            return dict(self.receipt)

    service = FakeService()

    first = cli.run_promote(
        release_id="release-2026-08-31-bond-risk-v1",
        plan_file=plan_file,
        idempotency_key="promote-2026-08-31-01",
        service=service,
    )
    second = cli.run_promote(
        release_id="release-2026-08-31-bond-risk-v1",
        plan_file=plan_file,
        idempotency_key="promote-2026-08-31-01",
        service=service,
    )

    assert second == first


def test_blocked_promote_returns_nonzero_exit_code(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    cli = _load_release_control_cli()
    plan_file = tmp_path / "plan.json"
    payload = _plan_payload()
    _write_json(plan_file, payload)
    monkeypatch.setattr(
        cli,
        "run_promote",
        lambda **_kwargs: {
            "status": "blocked",
            "release_id": "release-2026-08-31-bond-risk-v1",
            "outcome": "revision_conflict",
            "blockers": ["stale_revision:logical_lane:bond-analytics-risk-tensor"],
            "exit_code": 1,
        },
    )

    exit_code = cli.main(
        [
            "promote",
            "--release-id",
            "release-2026-08-31-bond-risk-v1",
            "--plan-file",
            str(plan_file),
            "--idempotency-key",
            "promote-2026-08-31-02",
        ]
    )

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "blocked"
    assert payload["outcome"] == "revision_conflict"


def test_blocked_promote_emits_reason_codes_without_exception_text(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    cli = _load_release_control_cli()
    plan_file = tmp_path / "plan.json"
    _write_json(plan_file, _plan_payload())
    gate = build_approval_gate_receipt(
        {
            "status": "blocked",
            "reason_codes": (
                "authority_receipt_expired",
                "authority_receipt_revoked",
            ),
            "release_id": "release-2026-08-31-bond-risk-v1",
            "manifest_sha256": "A" * 64,
            "registry_sha256": "7" * 64,
            "authority_receipt_sha256": "8" * 64,
            "checked_at": "2026-08-31T00:00:00Z",
            "subjects": (),
        }
    )

    def blocked_promote(**_kwargs):
        raise cli.ReleaseGateBlockedError(
            "sensitive external verifier exception text",
            reason_codes=gate.reason_codes,
            approval_gate_receipt=gate,
        )

    monkeypatch.setattr(cli, "run_promote", blocked_promote)

    exit_code = cli.main(
        [
            "promote",
            "--release-id",
            "release-2026-08-31-bond-risk-v1",
            "--plan-file",
            str(plan_file),
            "--idempotency-key",
            "promote-2026-08-31-structured-block",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == cli.EXIT_BLOCKED
    assert payload["error_code"] == "release_gate_blocked"
    assert payload["reason_codes"] == [
        "authority_receipt_expired",
        "authority_receipt_revoked",
    ]
    assert payload["approval_gate_receipt"] == gate.model_dump(mode="json")
    assert "sensitive external verifier exception text" not in captured.out
    assert "sensitive external verifier exception text" not in captured.err


def test_rollback_command_requires_explicit_target_reason_mode_and_plan(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cli = _load_release_control_cli()
    plan_file = tmp_path / "plan.json"
    payload = _plan_payload()
    _write_json(plan_file, payload)
    calls: list[dict[str, object]] = []

    def fake_run_rollback(**kwargs):
        calls.append(kwargs)
        return {"status": "rolled_back", "exit_code": 0}

    monkeypatch.setattr(cli, "run_rollback", fake_run_rollback)

    assert (
        cli.main(
            [
                "rollback",
                "--to-release-id",
                "release-a",
                "--reason",
                "post-promote smoke failed",
                "--mode",
                "sealed_bundle_reactivate",
                "--plan-file",
                str(plan_file),
                "--idempotency-key",
                "rollback-2026-08-31-01",
            ]
        )
        == 0
    )
    assert calls == [
        {
            "to_release_id": "release-a",
            "reason": "post-promote smoke failed",
            "mode": "sealed_bundle_reactivate",
            "scopes": payload["scopes"],
            "idempotency_key": "rollback-2026-08-31-01",
            "receipt_file": None,
        }
    ]


def test_run_promote_keeps_applied_receipt_when_receipt_file_write_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cli = _load_release_control_cli()
    plan_file = tmp_path / "plan.json"
    receipt_file = tmp_path / "promote-receipt.json"
    _write_json(plan_file, _plan_payload())

    class FakeService:
        def promote_release_bundle(self, **_kwargs):
            return dict(_promote_success_receipt())

    original_write_text = Path.write_text

    def fail_only_receipt_file(
        self: Path, data: str, encoding: str | None = None, **kwargs
    ):
        if self == receipt_file:
            raise OSError("disk full")
        return original_write_text(self, data, encoding=encoding, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_only_receipt_file)

    receipt = cli.run_promote(
        release_id="release-2026-08-31-bond-risk-v1",
        plan_file=plan_file,
        idempotency_key="promote-2026-08-31-receipt-file-failure",
        receipt_file=receipt_file,
        service=FakeService(),
    )

    assert receipt == {
        "action": "promote",
        "outcome": "applied",
        "status": "current",
        "release_id": "release-2026-08-31-bond-risk-v1",
        "manifest_digest": "A" * 64,
        "target_environment": "test",
        "action_applied": True,
        "error_code": "receipt_file_write_failed",
        "details": {"receipt_file_status": "write_failed"},
        "exit_code": 3,
    }


def test_run_rollback_keeps_applied_receipt_when_receipt_file_write_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cli = _load_release_control_cli()
    plan_file = tmp_path / "plan.json"
    receipt_file = tmp_path / "rollback-receipt.json"
    _write_json(plan_file, _plan_payload())

    class FakeService:
        def rollback_release_bundle(self, **_kwargs):
            return dict(_rollback_success_receipt())

    original_write_text = Path.write_text

    def fail_only_receipt_file(
        self: Path, data: str, encoding: str | None = None, **kwargs
    ):
        if self == receipt_file:
            raise OSError("disk full")
        return original_write_text(self, data, encoding=encoding, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_only_receipt_file)

    receipt = cli.run_rollback(
        to_release_id="release-a",
        plan_file=plan_file,
        idempotency_key="rollback-2026-08-31-receipt-file-failure",
        receipt_file=receipt_file,
        reason="post-promote smoke failed",
        mode="sealed_bundle_reactivate",
        service=FakeService(),
    )

    assert receipt == {
        "action": "rollback",
        "outcome": "applied",
        "status": "current",
        "release_id": "release-a",
        "manifest_digest": "B" * 64,
        "target_environment": "test",
        "action_applied": True,
        "error_code": "receipt_file_write_failed",
        "details": {"receipt_file_status": "write_failed"},
        "exit_code": 3,
    }


def test_main_promote_receipt_file_write_failure_keeps_applied_output(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    cli = _load_release_control_cli()
    plan_file = tmp_path / "plan.json"
    receipt_file = tmp_path / "promote-receipt.json"
    _write_json(plan_file, _plan_payload())

    class FakeService:
        def promote_release_bundle(self, **_kwargs):
            return dict(_promote_success_receipt())

    monkeypatch.setattr(cli, "_build_service", lambda: FakeService())
    original_write_text = Path.write_text

    def fail_only_receipt_file(
        self: Path, data: str, encoding: str | None = None, **kwargs
    ):
        if self == receipt_file:
            raise OSError("disk full")
        return original_write_text(self, data, encoding=encoding, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_only_receipt_file)

    exit_code = cli.main(
        [
            "promote",
            "--release-id",
            "release-2026-08-31-bond-risk-v1",
            "--plan-file",
            str(plan_file),
            "--idempotency-key",
            "promote-2026-08-31-receipt-file-failure",
            "--receipt-file",
            str(receipt_file),
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 3
    assert payload == {
        "action": "promote",
        "outcome": "applied",
        "status": "current",
        "release_id": "release-2026-08-31-bond-risk-v1",
        "manifest_digest": "A" * 64,
        "target_environment": "test",
        "action_applied": True,
        "error_code": "receipt_file_write_failed",
        "details": {"receipt_file_status": "write_failed"},
        "exit_code": 3,
    }
