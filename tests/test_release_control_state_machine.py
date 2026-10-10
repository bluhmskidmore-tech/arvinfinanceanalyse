from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

import pytest

from backend.app.schemas.release_approval import (
    ApprovalGateSubjectStatus,
    build_approval_gate_receipt,
    build_authority_approval_receipt,
)
from backend.app.schemas.release_control import canonical_sha256
from tests.helpers import load_module


def _load_release_control_service():
    return load_module(
        "backend.app.governance.release_control",
        "backend/app/governance/release_control.py",
    )


def _load_release_control_repo():
    return load_module(
        "backend.app.repositories.release_control_repo",
        "backend/app/repositories/release_control_repo.py",
    )


class _VerifiedTestApprovalVerifier:
    """Test-only authority adapter; production uses the fail-closed verifier."""

    @staticmethod
    def _verify(*, release_id, manifest_sha256, manifest_payload, authority_receipt):
        assert authority_receipt.release_id == release_id
        assert authority_receipt.manifest_sha256 == manifest_sha256
        assert (
            authority_receipt.registry_sha256
            == manifest_payload.approval_registry_sha256
        )
        subjects = tuple(
            ApprovalGateSubjectStatus(
                approval_id=subject.approval_id,
                subject_kind=subject.subject_kind,
                subject_key=subject.subject_key,
                states=subject.states,
                evidence_receipt_sha256=subject.evidence_receipt_sha256,
            )
            for subject in authority_receipt.subjects
        )
        return build_approval_gate_receipt(
            {
                "status": "passed",
                "reason_codes": (),
                "release_id": release_id,
                "manifest_sha256": manifest_sha256,
                "registry_sha256": authority_receipt.registry_sha256,
                "authority_receipt_sha256": authority_receipt.receipt_sha256,
                "checked_at": datetime.now(UTC),
                "subjects": subjects,
            }
        )

    def verify_record_approval(self, **kwargs):
        return self._verify(**kwargs)

    def verify_promotion(self, **kwargs):
        return self._verify(**kwargs)


class _BlockedPromotionApprovalVerifier(_VerifiedTestApprovalVerifier):
    def verify_promotion(self, **kwargs):
        authority_receipt = kwargs["authority_receipt"]
        return build_approval_gate_receipt(
            {
                "status": "blocked",
                "reason_codes": ("authority_receipt_expired",),
                "release_id": kwargs["release_id"],
                "manifest_sha256": kwargs["manifest_sha256"],
                "registry_sha256": authority_receipt.registry_sha256,
                "authority_receipt_sha256": authority_receipt.receipt_sha256,
                "checked_at": datetime.now(UTC),
                "subjects": (),
            }
        )


def _authority_receipt(release_id: str, manifest_sha256: str):
    return build_authority_approval_receipt(
        {
            "release_id": release_id,
            "manifest_sha256": manifest_sha256,
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


def _service(tmp_path: Path):
    repo_module = _load_release_control_repo()
    service_module = _load_release_control_service()
    repo = repo_module.ReleaseControlRepository(
        sql_dsn=f"sqlite:///{(tmp_path / 'release-control.db').as_posix()}",
    )
    return service_module.ReleaseControlService(
        repo=repo,
        approval_verifier=_VerifiedTestApprovalVerifier(),
    )


def _complete_payload(
    release_id: str = "release-2026-08-31-bond-risk-v1",
) -> dict[str, object]:
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
        "scopes": [
            {
                "scope_kind": "logical_lane",
                "scope_key": "bond-analytics-risk-tensor",
                "artifact_kind": "bond-risk-tensor-candidate",
                "artifact_version": f"{release_id}-risk-v6",
                "artifact_sha256": "F" * 64,
                "evidence_sha256": "1" * 64,
            },
            {
                "scope_kind": "logical_lane",
                "scope_key": "bond-analytics-core",
                "artifact_kind": "bond-analytics-candidate",
                "artifact_version": f"{release_id}-bond-v6",
                "artifact_sha256": "2" * 64,
                "evidence_sha256": "3" * 64,
            },
            {
                "scope_kind": "physical_bundle",
                "scope_key": "duckdb-main",
                "artifact_kind": "duckdb-main",
                "artifact_version": f"{release_id}-duckdb-main",
                "artifact_sha256": "4" * 64,
                "evidence_sha256": "5" * 64,
                "contained_lane_versions": {
                    "bond-analytics-risk-tensor": f"{release_id}-risk-v6",
                    "bond-analytics-core": f"{release_id}-bond-v6",
                },
            },
        ],
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
    }


def _scopes(expected_revision: int) -> list[dict[str, object]]:
    return [
        {
            "scope_kind": "physical_bundle",
            "scope_key": "duckdb-main",
            "expected_revision": expected_revision,
        },
        {
            "scope_kind": "logical_lane",
            "scope_key": "bond-analytics-risk-tensor",
            "expected_revision": expected_revision,
        },
        {
            "scope_kind": "logical_lane",
            "scope_key": "bond-analytics-core",
            "expected_revision": expected_revision,
        },
    ]


def _self_hashed_validation_receipt(
    body: dict[str, object],
) -> dict[str, object]:
    return {**body, "receipt_sha256": canonical_sha256(body)}


def _validation_receipts() -> dict[str, dict[str, object]]:
    receipts: dict[str, dict[str, object]] = {}
    for gate in ("schema", "contracts", "governance"):
        body: dict[str, object] = {
            "schema_version": "test-release-validation-gate/v1",
            "gate": gate,
            "status": "passed",
            "release_gate_eligible": True,
        }
        receipts[gate] = _self_hashed_validation_receipt(body)
    return receipts


def _prepare_approved(service, release_id: str) -> str:
    receipt = service.prepare_release(
        release_id=release_id,
        payload=_complete_payload(release_id),
        freeze=True,
    )
    service.record_validation(
        release_id,
        validation_receipts=_validation_receipts(),
    )
    service.record_approval(
        release_id=release_id,
        manifest_digest=receipt.manifest_digest,
        authority_receipt=_authority_receipt(release_id, receipt.manifest_digest),
    )
    return receipt.manifest_digest


def test_prepare_release_rejects_freeze_when_payload_is_incomplete(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)

    with pytest.raises(Exception):
        service.prepare_release(
            release_id="release-2026-08-31-bond-risk-v1",
            payload={"git_sha": "0123456789abcdef0123456789abcdef01234567"},
            freeze=True,
        )


def test_record_approval_requires_exact_manifest_digest_and_authority_reference(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    receipt = service.prepare_release(
        release_id="release-2026-08-31-bond-risk-v1",
        payload=_complete_payload(),
        freeze=True,
    )
    service.record_validation(
        "release-2026-08-31-bond-risk-v1",
        validation_receipts=_validation_receipts(),
    )

    with pytest.raises(Exception):
        service.record_approval(
            release_id="release-2026-08-31-bond-risk-v1",
            manifest_digest=receipt.manifest_digest[:-1] + "0",
            authority_receipt=_authority_receipt(
                receipt.release_id, receipt.manifest_digest
            ),
        )


def test_record_validation_blocks_empty_required_gate_receipts_and_keeps_candidate_state(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    service.prepare_release(
        release_id="release-2026-08-31-bond-risk-v1",
        payload=_complete_payload(),
        freeze=True,
    )

    with pytest.raises(Exception):
        service.record_validation(
            "release-2026-08-31-bond-risk-v1",
            validation_receipts={},
        )

    assert service.show_release("release-2026-08-31-bond-risk-v1").state == "candidate"


def test_record_validation_blocks_missing_required_gate_digest_and_keeps_candidate_state(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    service.prepare_release(
        release_id="release-2026-08-31-bond-risk-v1",
        payload=_complete_payload(),
        freeze=True,
    )

    with pytest.raises(Exception):
        service.record_validation(
            "release-2026-08-31-bond-risk-v1",
            validation_receipts={
                "schema": {"status": "passed", "receipt_sha256": "D" * 64},
                "contracts": {"status": "passed"},
                "governance": {"status": "passed", "receipt_sha256": "F" * 64},
            },
        )

    assert service.show_release("release-2026-08-31-bond-risk-v1").state == "candidate"


def test_record_validation_accepts_exact_eligible_self_hashed_receipts(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    service.prepare_release(
        release_id="release-validation-receipts",
        payload=_complete_payload("release-validation-receipts"),
        freeze=True,
    )

    receipt = service.record_validation(
        "release-validation-receipts",
        validation_receipts=_validation_receipts(),
    )

    assert receipt.release_state == "validated"
    assert service.show_release("release-validation-receipts").state == "validated"


@pytest.mark.parametrize(
    "invalid_kind",
    (
        "openapi_diagnostic",
        "approval_registry_structure",
        "forged_hash",
        "extra_gate",
    ),
)
def test_record_validation_rejects_non_release_or_noncanonical_receipts_without_writes(
    tmp_path: Path,
    invalid_kind: str,
) -> None:
    service = _service(tmp_path)
    release_id = f"release-invalid-{invalid_kind}"
    service.prepare_release(
        release_id=release_id,
        payload=_complete_payload(release_id),
        freeze=True,
    )
    receipts = _validation_receipts()
    if invalid_kind == "openapi_diagnostic":
        receipts["contracts"] = _self_hashed_validation_receipt(
            {
                "schema_version": "api-contract-check/v1",
                "status": "diagnostic",
                "diagnostic": True,
                "release_gate_eligible": False,
            }
        )
    elif invalid_kind == "approval_registry_structure":
        receipts["governance"] = _self_hashed_validation_receipt(
            {
                "schema_version": "release-approval-registry-check/v1",
                "status": "structure_passed",
                "structure_only": True,
                "approval_decision": "not_evaluated",
                "release_gate_eligible": False,
            }
        )
    elif invalid_kind == "forged_hash":
        receipts["schema"]["gate"] = "tampered-after-hash"
    else:
        receipts["approval"] = _self_hashed_validation_receipt(
            {
                "schema_version": "test-release-validation-gate/v1",
                "gate": "approval",
                "status": "passed",
                "release_gate_eligible": True,
            }
        )
    before = service.show_release(release_id)

    with pytest.raises(Exception, match="validation gates did not pass"):
        service.record_validation(release_id, validation_receipts=receipts)

    after = service.show_release(release_id)
    assert after.state == "candidate"
    assert after.events == before.events
    assert after.aliases == before.aliases


def test_promote_bundle_requires_complete_scope_plan(tmp_path: Path) -> None:
    service = _service(tmp_path)
    receipt = service.prepare_release(
        release_id="release-2026-08-31-bond-risk-v1",
        payload=_complete_payload(),
        freeze=True,
    )
    service.record_validation(
        receipt.release_id,
        validation_receipts=_validation_receipts(),
    )
    service.record_approval(
        release_id=receipt.release_id,
        manifest_digest=receipt.manifest_digest,
        authority_receipt=_authority_receipt(
            receipt.release_id, receipt.manifest_digest
        ),
    )

    with pytest.raises(Exception):
        service.promote_release_bundle(
            release_id=receipt.release_id,
            manifest_digest=receipt.manifest_digest,
            scopes=_scopes(0)[:-1],
            idempotency_key="promote-2026-08-31-01",
        )


def test_promote_bundle_stale_revision_keeps_aliases_and_events_unchanged(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    manifests: dict[str, str] = {}
    for release_id in ("release-a", "release-b"):
        receipt = service.prepare_release(
            release_id=release_id,
            payload=_complete_payload(release_id),
            freeze=True,
        )
        manifests[release_id] = receipt.manifest_digest
        service.record_validation(
            release_id,
            validation_receipts=_validation_receipts(),
        )
        service.record_approval(
            release_id=release_id,
            manifest_digest=receipt.manifest_digest,
            authority_receipt=_authority_receipt(release_id, receipt.manifest_digest),
        )
    service.promote_release_bundle(
        release_id="release-a",
        manifest_digest=manifests["release-a"],
        scopes=_scopes(0),
        idempotency_key="promote-2026-08-31-02",
    )
    before = service.show_release("release-a")

    with pytest.raises(Exception):
        service.promote_release_bundle(
            release_id="release-b",
            manifest_digest=manifests["release-b"],
            scopes=[
                {
                    "scope_kind": "physical_bundle",
                    "scope_key": "duckdb-main",
                    "expected_revision": 1,
                },
                {
                    "scope_kind": "logical_lane",
                    "scope_key": "bond-analytics-risk-tensor",
                    "expected_revision": 0,
                },
                {
                    "scope_kind": "logical_lane",
                    "scope_key": "bond-analytics-core",
                    "expected_revision": 1,
                },
            ],
            idempotency_key="promote-2026-08-31-03",
        )

    after = service.show_release("release-a")
    assert after.state == before.state
    assert after.events == before.events


def test_promote_bundle_replay_deprecates_old_release_once_and_preserves_revisions(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    manifests: dict[str, str] = {}
    for release_id in ("release-a", "release-b"):
        receipt = service.prepare_release(
            release_id=release_id,
            payload=_complete_payload(release_id),
            freeze=True,
        )
        manifests[release_id] = receipt.manifest_digest
        service.record_validation(
            release_id,
            validation_receipts=_validation_receipts(),
        )
        service.record_approval(
            release_id=release_id,
            manifest_digest=receipt.manifest_digest,
            authority_receipt=_authority_receipt(release_id, receipt.manifest_digest),
        )
    service.promote_release_bundle(
        release_id="release-a",
        manifest_digest=manifests["release-a"],
        scopes=_scopes(0),
        idempotency_key="promote-2026-08-31-04",
    )

    first = service.promote_release_bundle(
        release_id="release-b",
        manifest_digest=manifests["release-b"],
        scopes=deepcopy(_scopes(1)),
        idempotency_key="promote-2026-08-31-05",
    )
    second = service.promote_release_bundle(
        release_id="release-b",
        manifest_digest=manifests["release-b"],
        scopes=deepcopy(_scopes(1)),
        idempotency_key="promote-2026-08-31-05",
    )

    assert second == first
    approval_gate = first.details["approval_gate_receipt"]
    assert approval_gate["status"] == "passed"
    assert first.details["repository_receipt"]["approval_gate_receipt"] == approval_gate
    promote_event = next(
        event
        for event in service.show_release("release-b").events
        if event["action"] == "promote"
    )
    assert promote_event["event_payload"]["approval_gate_receipt"] == approval_gate
    assert service.show_release("release-a").state == "deprecated"
    assert service.show_release("release-b").state == "current"


def test_promote_bundle_blocks_new_idempotency_key_once_release_is_already_current(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    manifests: dict[str, str] = {}
    for release_id in ("release-a", "release-b"):
        receipt = service.prepare_release(
            release_id=release_id,
            payload=_complete_payload(release_id),
            freeze=True,
        )
        manifests[release_id] = receipt.manifest_digest
        service.record_validation(
            release_id, validation_receipts=_validation_receipts()
        )
        service.record_approval(
            release_id=release_id,
            manifest_digest=receipt.manifest_digest,
            authority_receipt=_authority_receipt(release_id, receipt.manifest_digest),
        )
    service.promote_release_bundle(
        release_id="release-a",
        manifest_digest=manifests["release-a"],
        scopes=_scopes(0),
        idempotency_key="promote-2026-08-31-06a",
    )
    service.promote_release_bundle(
        release_id="release-b",
        manifest_digest=manifests["release-b"],
        scopes=deepcopy(_scopes(1)),
        idempotency_key="promote-2026-08-31-06b",
    )
    before = service.show_release("release-b")

    with pytest.raises(Exception):
        service.promote_release_bundle(
            release_id="release-b",
            manifest_digest=manifests["release-b"],
            scopes=deepcopy(_scopes(2)),
            idempotency_key="promote-2026-08-31-06c",
        )

    after = service.show_release("release-b")
    assert after.events == before.events
    assert [alias["revision"] for alias in after.aliases] == [
        alias["revision"] for alias in before.aliases
    ]


def test_rollback_bundle_restores_whole_plan_and_marks_removed_release_rolled_back(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    manifests: dict[str, str] = {}
    for release_id in ("release-a", "release-b"):
        receipt = service.prepare_release(
            release_id=release_id,
            payload=_complete_payload(release_id),
            freeze=True,
        )
        manifests[release_id] = receipt.manifest_digest
        service.record_validation(
            release_id,
            validation_receipts=_validation_receipts(),
        )
        service.record_approval(
            release_id=release_id,
            manifest_digest=receipt.manifest_digest,
            authority_receipt=_authority_receipt(release_id, receipt.manifest_digest),
        )
    service.promote_release_bundle(
        release_id="release-a",
        manifest_digest=manifests["release-a"],
        scopes=_scopes(0),
        idempotency_key="promote-2026-08-31-06",
    )
    service.promote_release_bundle(
        release_id="release-b",
        manifest_digest=manifests["release-b"],
        scopes=_scopes(1),
        idempotency_key="promote-2026-08-31-07",
    )
    release_a_events_before = service.show_release("release-a").events
    release_b_events_before = service.show_release("release-b").events

    receipt = service.rollback_release_bundle(
        to_release_id="release-a",
        manifest_digest=manifests["release-a"],
        scopes=_scopes(2),
        reason="post-promote smoke failed",
        mode="sealed_bundle_reactivate",
        idempotency_key="rollback-2026-08-31-01",
    )

    expected_aliases = {
        ("physical_bundle", "duckdb-main"): ("release-a", "release-b", 3),
        ("logical_lane", "bond-analytics-risk-tensor"): ("release-a", "release-b", 3),
        ("logical_lane", "bond-analytics-core"): ("release-a", "release-b", 3),
    }
    receipt_aliases = {
        (scope["scope_kind"], scope["scope_key"]): (
            scope["current_release_id"],
            scope["previous_release_id"],
            scope["revision"],
        )
        for scope in receipt.scopes
    }
    assert receipt_aliases == expected_aliases

    release_a_after = service.show_release("release-a")
    release_b_after = service.show_release("release-b")
    visible_aliases = {
        (alias["scope_kind"], alias["scope_key"]): (
            alias["current_release_id"],
            alias["previous_release_id"],
            alias["revision"],
        )
        for alias in release_a_after.aliases
    }
    assert visible_aliases == expected_aliases
    assert release_a_after.state == "current"
    assert release_b_after.state == "rolled_back"
    assert len(release_a_after.events) == len(release_a_events_before) + 1
    assert len(release_b_after.events) == len(release_b_events_before) + 1
    assert sum(event["action"] == "reactivate" for event in release_a_after.events) == 1
    assert sum(event["action"] == "rollback" for event in release_b_after.events) == 1
    approval_gate = receipt.details["approval_gate_receipt"]
    assert approval_gate["status"] == "passed"
    assert (
        receipt.details["repository_receipt"]["approval_gate_receipt"] == approval_gate
    )
    reactivate_event = next(
        event for event in release_a_after.events if event["action"] == "reactivate"
    )
    assert reactivate_event["event_payload"]["approval_gate_receipt"] == approval_gate

    replay = service.rollback_release_bundle(
        to_release_id="release-a",
        manifest_digest=manifests["release-a"],
        scopes=deepcopy(_scopes(2)),
        reason="post-promote smoke failed",
        mode="sealed_bundle_reactivate",
        idempotency_key="rollback-2026-08-31-01",
    )

    release_a_replayed = service.show_release("release-a")
    release_b_replayed = service.show_release("release-b")
    assert replay.scopes == receipt.scopes
    assert replay.details["approval_gate_receipt"] == approval_gate
    assert release_a_replayed.events == release_a_after.events
    assert release_b_replayed.events == release_b_after.events
    assert release_a_replayed.aliases == release_a_after.aliases
    assert release_b_replayed.aliases == release_b_after.aliases


def test_rollback_modes_reject_wrong_target_state_without_writes(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    release_a_digest = _prepare_approved(service, "release-a")
    approved_before = service.show_release("release-a")

    with pytest.raises(Exception, match="previously current"):
        service.rollback_release_bundle(
            to_release_id="release-a",
            manifest_digest=release_a_digest,
            scopes=_scopes(0),
            reason="test sealed state contract",
            mode="sealed_bundle_reactivate",
            idempotency_key="rollback-invalid-sealed-state",
        )

    approved_after = service.show_release("release-a")
    assert approved_after.events == approved_before.events
    assert approved_after.aliases == approved_before.aliases

    service.promote_release_bundle(
        release_id="release-a",
        manifest_digest=release_a_digest,
        scopes=_scopes(0),
        idempotency_key="promote-release-a-for-state-contract",
    )
    release_b_digest = _prepare_approved(service, "release-b")
    service.promote_release_bundle(
        release_id="release-b",
        manifest_digest=release_b_digest,
        scopes=_scopes(1),
        idempotency_key="promote-release-b-for-state-contract",
    )
    deprecated_before = service.show_release("release-a")

    with pytest.raises(Exception, match="requires an approved target"):
        service.rollback_release_bundle(
            to_release_id="release-a",
            manifest_digest=release_a_digest,
            scopes=_scopes(2),
            reason="test forward rebuild state contract",
            mode="forward_rebuild",
            idempotency_key="rollback-invalid-forward-state",
        )

    deprecated_after = service.show_release("release-a")
    assert deprecated_after.events == deprecated_before.events
    assert deprecated_after.aliases == deprecated_before.aliases


def test_forward_rebuild_rechecks_persisted_approval_before_writes(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    manifest_digest = _prepare_approved(service, "release-a")
    before = service.show_release("release-a")
    service.approval_verifier = _BlockedPromotionApprovalVerifier()

    with pytest.raises(Exception, match="did not pass"):
        service.rollback_release_bundle(
            to_release_id="release-a",
            manifest_digest=manifest_digest,
            scopes=_scopes(0),
            reason="expired approval must not authorize forward rebuild",
            mode="forward_rebuild",
            idempotency_key="rollback-forward-expired-approval",
        )

    after = service.show_release("release-a")
    assert after.events == before.events
    assert after.aliases == before.aliases


def test_sealed_reactivation_rechecks_persisted_approval_before_writes(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    release_a_digest = _prepare_approved(service, "release-a")
    service.promote_release_bundle(
        release_id="release-a",
        manifest_digest=release_a_digest,
        scopes=_scopes(0),
        idempotency_key="promote-release-a-for-expiry-check",
    )
    release_b_digest = _prepare_approved(service, "release-b")
    service.promote_release_bundle(
        release_id="release-b",
        manifest_digest=release_b_digest,
        scopes=_scopes(1),
        idempotency_key="promote-release-b-for-expiry-check",
    )
    before = service.show_release("release-a")
    service.approval_verifier = _BlockedPromotionApprovalVerifier()

    with pytest.raises(Exception, match="did not pass"):
        service.rollback_release_bundle(
            to_release_id="release-a",
            manifest_digest=release_a_digest,
            scopes=_scopes(2),
            reason="expired approval must not authorize sealed reactivation",
            mode="sealed_bundle_reactivate",
            idempotency_key="rollback-sealed-expired-approval",
        )

    after = service.show_release("release-a")
    assert after.events == before.events
    assert after.aliases == before.aliases
