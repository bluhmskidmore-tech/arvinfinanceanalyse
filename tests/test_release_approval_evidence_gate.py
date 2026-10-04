from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from backend.app.governance import release_approval as approval_module
from backend.app.governance.release_approval import (
    ApprovalVerificationBlocked,
    ReleaseApprovalVerifier,
    execute_registry_evidence,
    load_release_approval_registry,
)
from backend.app.governance.release_control import (
    ReleaseControlService,
    ReleaseGateBlockedError,
)
from backend.app.schemas.release_approval import (
    ApprovalGateSubjectStatus,
    ApprovalStateVector,
    AuthorityApprovalReceipt,
    ReleaseApprovalRegistry,
    ReleaseApprovalRegistryEntry,
    build_authority_approval_receipt,
)
from backend.app.schemas.release_control import ReleaseManifest


def _manifest_payload(
    registry: ReleaseApprovalRegistry | None = None,
    *,
    requirement_entries: Sequence[ReleaseApprovalRegistryEntry] | None = None,
    lane_keys: Sequence[str] = ("approval-test-lane",),
) -> dict[str, object]:
    registry = registry or load_release_approval_registry()
    entries = tuple(
        registry.entries if requirement_entries is None else requirement_entries
    )
    requirements = [
        {
            "approval_id": entry.approval_id,
            "subject_kind": entry.subject_kind,
            "subject_key": entry.subject_key,
            "required_states": list(entry.required_states),
        }
        for entry in entries
    ]
    logical_scopes = [
        {
            "scope_kind": "logical_lane",
            "scope_key": lane_key,
            "artifact_kind": "approval-test-candidate",
            "artifact_version": f"{lane_key}-v1",
            "artifact_sha256": "F" * 64,
            "evidence_sha256": "1" * 64,
        }
        for lane_key in lane_keys
    ]
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
        "approval_registry_sha256": registry.registry_sha256,
        "approval_requirements": requirements,
        "scopes": [
            *logical_scopes,
            {
                "scope_kind": "physical_bundle",
                "scope_key": "duckdb-main",
                "artifact_kind": "duckdb-main",
                "artifact_version": "approval-test-duckdb-v1",
                "artifact_sha256": "2" * 64,
                "evidence_sha256": "3" * 64,
                "contained_lane_versions": {
                    lane_key: f"{lane_key}-v1" for lane_key in lane_keys
                },
            },
        ],
    }


def _manifest(
    *,
    extension: str | None = None,
    registry: ReleaseApprovalRegistry | None = None,
    requirement_entries: Sequence[ReleaseApprovalRegistryEntry] | None = None,
    lane_keys: Sequence[str] = ("approval-test-lane",),
) -> ReleaseManifest:
    payload = _manifest_payload(
        registry,
        requirement_entries=requirement_entries,
        lane_keys=lane_keys,
    )
    if extension is not None:
        payload["extension_marker"] = extension
    return ReleaseManifest(release_id="release-approval-test", payload=payload)


def _authority_receipt(
    manifest: ReleaseManifest,
    *,
    registry: ReleaseApprovalRegistry | None = None,
    entries: Sequence[ReleaseApprovalRegistryEntry] | None = None,
    states: Mapping[str, bool] | None = None,
    expires_at: str | None = "2099-01-01T00:00:00Z",
    revoked_at: str | None = None,
    revocation_reference: str | None = None,
) -> AuthorityApprovalReceipt:
    registry = registry or load_release_approval_registry()
    selected_entries = tuple(registry.entries if entries is None else entries)
    subject_states = {
        "evidence_captured": True,
        "machine_validated": True,
        "business_approved": True,
        "formal_use_allowed": True,
        "closure_approved": True,
    }
    if states is not None:
        subject_states.update(states)
    return build_authority_approval_receipt(
        {
            "release_id": manifest.release_id,
            "manifest_sha256": manifest.content_sha256,
            "registry_sha256": registry.registry_sha256,
            "authority_reference": "opaque-test-attestation",
            "authority_verifier_receipt_sha256": "4" * 64,
            "decision": "approved",
            "decided_at": "2026-08-01T00:00:00Z",
            "expires_at": expires_at,
            "revoked_at": revoked_at,
            "revocation_reference": revocation_reference,
            "subjects": [
                {
                    "approval_id": entry.approval_id,
                    "subject_kind": entry.subject_kind,
                    "subject_key": entry.subject_key,
                    "authority_policy_id": entry.authority_policy_id,
                    "scope_kind": entry.scope_mapping.scope_kind or "logical_lane",
                    "scope_key": entry.scope_mapping.scope_key or "approval-test-lane",
                    "decision": "approved",
                    "states": subject_states,
                    "evidence_receipt_sha256": "5" * 64,
                }
                for entry in selected_entries
            ],
        }
    )


def _mapped_registry(
    *, registry_id: str = "test-mapped-registry"
) -> ReleaseApprovalRegistry:
    payload = load_release_approval_registry().model_dump(mode="json")
    payload["registry_id"] = registry_id
    for entry in payload["entries"]:
        entry["authority_policy_id"] = f"test-policy:{entry['approval_id']}"
        entry["scope_mapping"] = {
            "status": "mapped",
            "scope_kind": "logical_lane",
            "scope_key": "approval-test-lane",
        }
    return ReleaseApprovalRegistry.model_validate(payload)


def _two_lane_registry(
    *,
    require_closure: bool = True,
) -> tuple[ReleaseApprovalRegistry, tuple[ReleaseApprovalRegistryEntry, ...]]:
    payload = load_release_approval_registry().model_dump(mode="json")
    payload["registry_id"] = "test-two-lane-registry"
    split = len(payload["entries"]) // 2
    for index, entry in enumerate(payload["entries"]):
        entry["authority_policy_id"] = f"test-policy:{entry['approval_id']}"
        entry["scope_mapping"] = {
            "status": "mapped",
            "scope_kind": "logical_lane",
            "scope_key": "lane-a" if index < split else "lane-b",
        }
        if index < split and not require_closure:
            entry["required_states"] = [
                state
                for state in entry["required_states"]
                if state != "closure_approved"
            ]
    registry = ReleaseApprovalRegistry.model_validate(payload)
    applicable = tuple(
        entry for entry in registry.entries if entry.scope_mapping.scope_key == "lane-a"
    )
    return registry, applicable


def _captured_evidence_statuses(
    receipt: AuthorityApprovalReceipt,
    *,
    closure_approved: bool = True,
) -> tuple[ApprovalGateSubjectStatus, ...]:
    return tuple(
        ApprovalGateSubjectStatus(
            approval_id=subject.approval_id,
            subject_kind=subject.subject_kind,
            subject_key=subject.subject_key,
            states=ApprovalStateVector(
                evidence_captured=True,
                machine_validated=True,
                business_approved=False,
                formal_use_allowed=True,
                closure_approved=closure_approved,
            ),
            evidence_receipt_sha256=subject.evidence_receipt_sha256,
        )
        for subject in receipt.subjects
    )


class _TrustedAuthorityAttestation:
    def verify(self, _receipt: AuthorityApprovalReceipt) -> bool:
        return True


class _RejectedAuthorityAttestation:
    def verify(self, _receipt: AuthorityApprovalReceipt) -> bool:
        return False


class _FailingAuthorityAttestation:
    def verify(self, _receipt: AuthorityApprovalReceipt) -> bool:
        raise RuntimeError("external verifier detail must remain private")


class _ChangingAuthorityAttestation:
    def __init__(self) -> None:
        self.calls = 0

    def verify(self, _receipt: AuthorityApprovalReceipt) -> bool:
        self.calls += 1
        return self.calls == 1


class _NoWriteRepo:
    def __init__(self, manifest: ReleaseManifest, *, authority_receipt=None) -> None:
        self.manifest = manifest
        self.authority_receipt = authority_receipt
        self.append_count = 0
        self.activate_count = 0

    def get_manifest(self, release_id: str):
        assert release_id == self.manifest.release_id
        return {
            "release_id": self.manifest.release_id,
            "state": "candidate",
            "target_environment": self.manifest.target_environment,
            "manifest_kind": "release_bundle",
            "content_sha256": self.manifest.content_sha256,
            "payload": self.manifest.payload.canonical_payload(),
        }

    def list_events(self, **kwargs):
        if (
            kwargs.get("action") == "approve-record"
            and self.authority_receipt is not None
        ):
            return [
                {
                    "release_id": self.manifest.release_id,
                    "action": "approve-record",
                    "from_state": "validated",
                    "to_state": "approved",
                    "event_payload": {
                        "authority_receipt": self.authority_receipt.model_dump(
                            mode="json"
                        )
                    },
                }
            ]
        return []

    def append_event(self, **_kwargs):
        self.append_count += 1
        raise AssertionError("approval gate must run before append_event")

    def activate_release(self, **_kwargs):
        self.activate_count += 1
        raise AssertionError("approval gate must run before alias activation")


def test_five_approval_states_are_independent() -> None:
    states = ApprovalStateVector(
        evidence_captured=True,
        machine_validated=False,
        business_approved=False,
        formal_use_allowed=True,
        closure_approved=False,
    )

    assert states.evidence_captured is True
    assert states.machine_validated is False
    assert states.business_approved is False
    assert states.formal_use_allowed is True
    assert states.closure_approved is False
    assert states.all_satisfied is False


def test_page_checker_capture_sets_only_evidence_state_and_redacts_raw_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = ReleaseApprovalRegistry.model_validate(
        {
            "schema_version": "release-approval-registry/v1",
            "registry_id": "test",
            "entries": [
                {
                    "approval_id": "page:average-balance",
                    "subject_kind": "page",
                    "subject_key": "average-balance",
                    "authority_policy_id": "test-policy",
                    "scope_mapping": {
                        "status": "mapped",
                        "scope_kind": "logical_lane",
                        "scope_key": "approval-test-lane",
                    },
                    "command": {
                        "argv": [
                            "scripts/check_average_balance_business_owner_approval.py",
                            "--require-captured",
                        ]
                    },
                    "required_states": [
                        "evidence_captured",
                        "machine_validated",
                        "business_approved",
                        "formal_use_allowed",
                        "closure_approved",
                    ],
                }
            ],
        }
    )
    calls: list[dict[str, object]] = []

    def fake_run(argv, **kwargs):
        calls.append({"argv": argv, **kwargs})
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {
                    "approval_status": "captured",
                    "business_owner_approval_captured": True,
                    "formal_use_allowed": True,
                    "closure_approved": False,
                    "template_path": "F:/secret/internal-approval.md",
                    "approval_body": "confidential approval prose",
                }
            ),
            stderr="raw secret stderr",
        )

    monkeypatch.setattr(
        approval_module, "validate_registry_structure", lambda *_args, **_kwargs: ()
    )
    monkeypatch.setattr(approval_module.subprocess, "run", fake_run)

    statuses = execute_registry_evidence(registry)

    assert calls[0]["shell"] is False
    assert calls[0]["argv"][1] == "-I"
    assert calls[0]["argv"][2:] == list(registry.entries[0].command.argv)
    assert set(calls[0]["env"]) <= {"SYSTEMROOT", "WINDIR", "TEMP", "TMP"}
    assert "PYTHONPATH" not in calls[0]["env"]
    assert "PYTHONHOME" not in calls[0]["env"]
    assert statuses[0].states.model_dump() == {
        "evidence_captured": True,
        "machine_validated": True,
        "business_approved": False,
        "formal_use_allowed": True,
        "closure_approved": False,
    }
    serialized = statuses[0].model_dump_json()
    assert "secret" not in serialized
    assert "approval prose" not in serialized
    assert "F:/" not in serialized


def test_page_checker_does_not_treat_false_string_as_captured() -> None:
    registry = load_release_approval_registry()
    page_entry = next(
        entry for entry in registry.entries if entry.subject_kind == "page"
    )

    status = approval_module._typed_checker_status(
        page_entry,
        payload={
            "approval_status": "captured",
            "business_owner_approval_captured": "false",
            "formal_use_allowed": False,
            "closure_approved": False,
        },
        returncode=0,
    )

    assert status.states.evidence_captured is False


def test_authority_receipt_digest_detects_tampering_and_rejects_raw_body() -> None:
    manifest = _manifest()
    receipt = _authority_receipt(manifest)
    tampered = receipt.model_dump(mode="json")
    tampered["subjects"][0]["subject_key"] = "tampered"

    with pytest.raises(ValidationError, match="receipt_sha256"):
        AuthorityApprovalReceipt.model_validate(tampered)

    with_body = receipt.model_dump(mode="json")
    with_body["approval_body"] = "raw approval text must not be copied"
    with pytest.raises(ValidationError):
        AuthorityApprovalReceipt.model_validate(with_body)


@pytest.mark.parametrize(
    "authority_reference",
    ["raw approval prose with spaces", "F:/secret/internal-approval.md"],
)
def test_authority_receipt_reference_cannot_embed_body_or_absolute_path(
    authority_reference: str,
) -> None:
    receipt = _authority_receipt(_manifest())
    body = receipt.model_dump(mode="json", exclude={"receipt_sha256"})
    body["authority_reference"] = authority_reference

    with pytest.raises(ValidationError, match="opaque reference|absolute path"):
        build_authority_approval_receipt(body)


def test_free_text_identity_and_reference_cannot_append_approval_event() -> None:
    manifest = _manifest()
    repo = _NoWriteRepo(manifest)
    service = ReleaseControlService(repo=repo)

    with pytest.raises(ReleaseGateBlockedError, match="structured authority receipt"):
        service.record_approval(
            release_id=manifest.release_id,
            manifest_digest=manifest.content_sha256,
            approved_by="application-user-id",
            authority_reference="non-empty-free-text",
        )

    assert repo.append_count == 0


def test_pending_scope_mapping_blocks_before_approval_event_append() -> None:
    manifest = _manifest()
    receipt = _authority_receipt(manifest)
    repo = _NoWriteRepo(manifest)
    service = ReleaseControlService(repo=repo)

    with pytest.raises(ReleaseGateBlockedError) as exc_info:
        service.record_approval(
            release_id=manifest.release_id,
            manifest_digest=manifest.content_sha256,
            authority_receipt=receipt,
            approved_by="application-user-id",
            authority_reference="looks-signed-but-is-not-authority",
        )

    assert "scope_mapping_pending" in str(exc_info.value)
    assert repo.append_count == 0


def test_manifest_digest_change_invalidates_previous_authority_receipt() -> None:
    original = _manifest()
    changed = _manifest(extension="post-approval-change")
    receipt = _authority_receipt(original)
    verifier = ReleaseApprovalVerifier(clock=lambda: datetime(2026, 8, 31, tzinfo=UTC))

    with pytest.raises(ApprovalVerificationBlocked) as exc_info:
        verifier.verify_record_approval(
            release_id=changed.release_id,
            manifest_sha256=changed.content_sha256,
            manifest_payload=changed.payload,
            authority_receipt=receipt,
        )

    assert "authority_receipt_manifest_mismatch" in exc_info.value.receipt.reason_codes


@pytest.mark.parametrize(
    ("attestation_verifier", "expected_reason"),
    [
        (None, "authority_attestation_verifier_not_configured"),
        (_RejectedAuthorityAttestation(), "authority_attestation_not_verified"),
        (_FailingAuthorityAttestation(), "authority_attestation_not_verified"),
    ],
)
def test_authority_attestation_missing_rejected_or_error_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    attestation_verifier,
    expected_reason: str,
) -> None:
    registry = _mapped_registry()
    manifest = _manifest(registry=registry)
    receipt = _authority_receipt(manifest, registry=registry)
    monkeypatch.setattr(
        approval_module,
        "load_release_approval_registry",
        lambda _path=None: registry,
    )
    evidence_executed = False

    def fail_if_executed(*_args, **_kwargs):
        nonlocal evidence_executed
        evidence_executed = True
        raise AssertionError("untrusted authority must block before evidence execution")

    monkeypatch.setattr(
        approval_module,
        "execute_registry_evidence",
        fail_if_executed,
    )
    verifier = ReleaseApprovalVerifier(
        authority_attestation_verifier=attestation_verifier,
        clock=lambda: datetime(2026, 8, 31, tzinfo=UTC),
    )

    with pytest.raises(ApprovalVerificationBlocked) as exc_info:
        verifier.verify_record_approval(
            release_id=manifest.release_id,
            manifest_sha256=manifest.content_sha256,
            manifest_payload=manifest.payload,
            authority_receipt=receipt,
        )

    assert expected_reason in exc_info.value.receipt.reason_codes
    assert evidence_executed is False


def test_authority_attestation_change_during_verification_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = _mapped_registry()
    manifest = _manifest(registry=registry)
    receipt = _authority_receipt(manifest, registry=registry)
    attestation = _ChangingAuthorityAttestation()
    monkeypatch.setattr(
        approval_module,
        "load_release_approval_registry",
        lambda _path=None: registry,
    )
    monkeypatch.setattr(
        approval_module,
        "execute_registry_evidence",
        lambda *_args, **_kwargs: _captured_evidence_statuses(receipt),
    )
    verifier = ReleaseApprovalVerifier(
        authority_attestation_verifier=attestation,
        clock=lambda: datetime(2026, 8, 31, tzinfo=UTC),
    )

    with pytest.raises(ApprovalVerificationBlocked) as exc_info:
        verifier.verify_record_approval(
            release_id=manifest.release_id,
            manifest_sha256=manifest.content_sha256,
            manifest_payload=manifest.payload,
            authority_receipt=receipt,
        )

    assert "authority_attestation_changed_during_verification" in (
        exc_info.value.receipt.reason_codes
    )
    assert attestation.calls == 2


def test_verifier_rechecks_expiry_after_evidence_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = _mapped_registry()
    manifest = _manifest(registry=registry)
    receipt = _authority_receipt(
        manifest,
        registry=registry,
        expires_at="2026-08-31T01:00:00Z",
    )
    times = iter(
        [
            datetime(2026, 8, 31, 0, 0, tzinfo=UTC),
            datetime(2026, 8, 31, 2, 0, tzinfo=UTC),
        ]
    )
    monkeypatch.setattr(
        approval_module,
        "load_release_approval_registry",
        lambda _path=None: registry,
    )
    monkeypatch.setattr(
        approval_module,
        "execute_registry_evidence",
        lambda *_args, **_kwargs: _captured_evidence_statuses(receipt),
    )
    verifier = ReleaseApprovalVerifier(
        authority_attestation_verifier=_TrustedAuthorityAttestation(),
        clock=lambda: next(times),
    )

    with pytest.raises(ApprovalVerificationBlocked) as exc_info:
        verifier.verify_record_approval(
            release_id=manifest.release_id,
            manifest_sha256=manifest.content_sha256,
            manifest_payload=manifest.payload,
            authority_receipt=receipt,
        )

    assert "authority_receipt_expired" in exc_info.value.receipt.reason_codes
    assert exc_info.value.receipt.checked_at == datetime(
        2026,
        8,
        31,
        2,
        0,
        tzinfo=UTC,
    )


def test_verifier_reloads_registry_after_evidence_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initial_registry = _mapped_registry(registry_id="initial-registry")
    changed_registry = _mapped_registry(registry_id="changed-registry")
    manifest = _manifest(registry=initial_registry)
    receipt = _authority_receipt(manifest, registry=initial_registry)
    registries = iter([initial_registry, changed_registry])
    monkeypatch.setattr(
        approval_module,
        "load_release_approval_registry",
        lambda _path=None: next(registries),
    )
    monkeypatch.setattr(
        approval_module,
        "execute_registry_evidence",
        lambda *_args, **_kwargs: _captured_evidence_statuses(receipt),
    )
    verifier = ReleaseApprovalVerifier(
        authority_attestation_verifier=_TrustedAuthorityAttestation(),
        clock=lambda: datetime(2026, 8, 31, tzinfo=UTC),
    )

    with pytest.raises(ApprovalVerificationBlocked) as exc_info:
        verifier.verify_record_approval(
            release_id=manifest.release_id,
            manifest_sha256=manifest.content_sha256,
            manifest_payload=manifest.payload,
            authority_receipt=receipt,
        )

    assert "approval_registry_changed_during_verification" in (
        exc_info.value.receipt.reason_codes
    )
    assert exc_info.value.receipt.registry_sha256 == changed_registry.registry_sha256


def test_verifier_blocks_when_current_evidence_state_disagrees_with_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = _mapped_registry()
    manifest = _manifest(registry=registry)
    receipt = _authority_receipt(manifest, registry=registry)
    statuses = list(_captured_evidence_statuses(receipt))
    mismatched = statuses[0]
    statuses[0] = mismatched.model_copy(
        update={
            "states": mismatched.states.model_copy(update={"formal_use_allowed": False})
        }
    )
    monkeypatch.setattr(
        approval_module,
        "load_release_approval_registry",
        lambda _path=None: registry,
    )
    monkeypatch.setattr(
        approval_module,
        "execute_registry_evidence",
        lambda *_args, **_kwargs: tuple(statuses),
    )
    verifier = ReleaseApprovalVerifier(
        authority_attestation_verifier=_TrustedAuthorityAttestation(),
        clock=lambda: datetime(2026, 8, 31, tzinfo=UTC),
    )

    with pytest.raises(ApprovalVerificationBlocked) as exc_info:
        verifier.verify_record_approval(
            release_id=manifest.release_id,
            manifest_sha256=manifest.content_sha256,
            manifest_payload=manifest.payload,
            authority_receipt=receipt,
        )

    expected = f"evidence_state_mismatch:formal_use_allowed:{mismatched.approval_id}"
    assert expected in exc_info.value.receipt.reason_codes
    assert not any(
        reason.startswith("evidence_state_mismatch:business_approved:")
        for reason in exc_info.value.receipt.reason_codes
    )


def test_verifier_executes_and_requires_only_entries_for_manifest_lane(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, applicable = _two_lane_registry(require_closure=False)
    manifest = _manifest(
        registry=registry,
        requirement_entries=applicable,
        lane_keys=("lane-a",),
    )
    receipt = _authority_receipt(
        manifest,
        registry=registry,
        entries=applicable,
        states={"closure_approved": False},
    )
    executed: list[tuple[str, ...]] = []

    def fake_execute(_registry, *, entries, **_kwargs):
        executed.append(tuple(entry.approval_id for entry in entries))
        return _captured_evidence_statuses(receipt, closure_approved=False)

    monkeypatch.setattr(
        approval_module,
        "load_release_approval_registry",
        lambda _path=None: registry,
    )
    monkeypatch.setattr(approval_module, "execute_registry_evidence", fake_execute)
    verifier = ReleaseApprovalVerifier(
        authority_attestation_verifier=_TrustedAuthorityAttestation(),
        clock=lambda: datetime(2026, 8, 31, tzinfo=UTC),
    )

    gate = verifier.verify_record_approval(
        release_id=manifest.release_id,
        manifest_sha256=manifest.content_sha256,
        manifest_payload=manifest.payload,
        authority_receipt=receipt,
    )

    applicable_ids = tuple(entry.approval_id for entry in applicable)
    lane_b_ids = {
        entry.approval_id
        for entry in registry.entries
        if entry.scope_mapping.scope_key == "lane-b"
    }
    assert gate.status == "passed"
    assert executed == [applicable_ids]
    assert {subject.approval_id for subject in gate.subjects} == set(applicable_ids)
    assert not ({subject.approval_id for subject in gate.subjects} & lane_b_ids)


def test_verifier_rejects_extra_authority_subject_from_other_lane(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, applicable = _two_lane_registry()
    manifest = _manifest(
        registry=registry,
        requirement_entries=applicable,
        lane_keys=("lane-a",),
    )
    receipt = _authority_receipt(manifest, registry=registry, entries=registry.entries)
    executed = False

    def fail_if_executed(*_args, **_kwargs):
        nonlocal executed
        executed = True
        raise AssertionError("non-applicable checker must not execute")

    monkeypatch.setattr(
        approval_module,
        "load_release_approval_registry",
        lambda _path=None: registry,
    )
    monkeypatch.setattr(approval_module, "execute_registry_evidence", fail_if_executed)
    verifier = ReleaseApprovalVerifier(
        authority_attestation_verifier=_TrustedAuthorityAttestation(),
        clock=lambda: datetime(2026, 8, 31, tzinfo=UTC),
    )

    with pytest.raises(ApprovalVerificationBlocked) as exc_info:
        verifier.verify_record_approval(
            release_id=manifest.release_id,
            manifest_sha256=manifest.content_sha256,
            manifest_payload=manifest.payload,
            authority_receipt=receipt,
        )

    assert "authority_receipt_subject_set_mismatch" in (
        exc_info.value.receipt.reason_codes
    )
    assert executed is False


def test_verifier_blocks_missing_required_closure_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, applicable = _two_lane_registry(require_closure=True)
    manifest = _manifest(
        registry=registry,
        requirement_entries=applicable,
        lane_keys=("lane-a",),
    )
    receipt = _authority_receipt(
        manifest,
        registry=registry,
        entries=applicable,
        states={"closure_approved": False},
    )
    monkeypatch.setattr(
        approval_module,
        "load_release_approval_registry",
        lambda _path=None: registry,
    )
    verifier = ReleaseApprovalVerifier(
        authority_attestation_verifier=_TrustedAuthorityAttestation(),
        clock=lambda: datetime(2026, 8, 31, tzinfo=UTC),
    )

    with pytest.raises(ApprovalVerificationBlocked) as exc_info:
        verifier.verify_record_approval(
            release_id=manifest.release_id,
            manifest_sha256=manifest.content_sha256,
            manifest_payload=manifest.payload,
            authority_receipt=receipt,
        )

    assert any(
        reason.startswith("approval_required_state_missing:closure_approved:")
        for reason in exc_info.value.receipt.reason_codes
    )


def test_verifier_rejects_manifest_requirement_from_other_lane(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, applicable = _two_lane_registry()
    manifest = _manifest(
        registry=registry,
        requirement_entries=registry.entries,
        lane_keys=("lane-a",),
    )
    receipt = _authority_receipt(manifest, registry=registry, entries=applicable)
    monkeypatch.setattr(
        approval_module,
        "load_release_approval_registry",
        lambda _path=None: registry,
    )
    verifier = ReleaseApprovalVerifier(
        authority_attestation_verifier=_TrustedAuthorityAttestation(),
        clock=lambda: datetime(2026, 8, 31, tzinfo=UTC),
    )

    with pytest.raises(ApprovalVerificationBlocked) as exc_info:
        verifier.verify_record_approval(
            release_id=manifest.release_id,
            manifest_sha256=manifest.content_sha256,
            manifest_payload=manifest.payload,
            authority_receipt=receipt,
        )

    assert "manifest_approval_requirements_mismatch" in (
        exc_info.value.receipt.reason_codes
    )


def test_verifier_blocks_when_manifest_has_no_applicable_registry_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, _applicable = _two_lane_registry()
    manifest = _manifest(registry=registry, lane_keys=("lane-c",))
    receipt = _authority_receipt(manifest, registry=registry)
    monkeypatch.setattr(
        approval_module,
        "load_release_approval_registry",
        lambda _path=None: registry,
    )
    verifier = ReleaseApprovalVerifier(
        authority_attestation_verifier=_TrustedAuthorityAttestation(),
        clock=lambda: datetime(2026, 8, 31, tzinfo=UTC),
    )

    with pytest.raises(ApprovalVerificationBlocked) as exc_info:
        verifier.verify_record_approval(
            release_id=manifest.release_id,
            manifest_sha256=manifest.content_sha256,
            manifest_payload=manifest.payload,
            authority_receipt=receipt,
        )

    assert "no_applicable_approval_requirements" in (
        exc_info.value.receipt.reason_codes
    )


def test_expired_and_revoked_approval_blocks_promotion_before_alias_or_event_write() -> (
    None
):
    manifest = _manifest()
    receipt = _authority_receipt(
        manifest,
        expires_at="2026-08-15T00:00:00Z",
        revoked_at="2026-08-20T00:00:00Z",
        revocation_reference="revocation-test-receipt",
    )
    repo = _NoWriteRepo(manifest, authority_receipt=receipt)
    verifier = ReleaseApprovalVerifier(clock=lambda: datetime(2026, 8, 31, tzinfo=UTC))
    service = ReleaseControlService(repo=repo, approval_verifier=verifier)

    with pytest.raises(ReleaseGateBlockedError) as exc_info:
        service.promote_release(
            release_id=manifest.release_id,
            manifest_digest=manifest.content_sha256,
            target_environment="test",
            scope_expectations=[
                {
                    "scope_kind": "physical_bundle",
                    "scope_key": "duckdb-main",
                    "expected_revision": 0,
                },
                {
                    "scope_kind": "logical_lane",
                    "scope_key": "approval-test-lane",
                    "expected_revision": 0,
                },
            ],
            idempotency_key="promote-expired-revoked",
        )

    assert "authority_receipt_expired" in str(exc_info.value)
    assert "authority_receipt_revoked" in str(exc_info.value)
    assert repo.append_count == 0
    assert repo.activate_count == 0
