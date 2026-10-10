from __future__ import annotations

from datetime import UTC, datetime

import pytest

from backend.app.governance import release_approval as approval_module
from backend.app.governance.release_approval import (
    ApprovalVerificationBlocked,
    ReleaseApprovalVerifier,
)
from backend.app.governance.release_control import (
    ReleaseConflictError,
    ReleaseControlService,
    ReleaseGateBlockedError,
)
from backend.app.repositories.release_control_repo import (
    IdempotencyConflictError,
    ManifestConflictError,
    ReleaseStateConflictError,
)
from backend.app.schemas.release_approval import build_approval_gate_receipt
from backend.app.schemas.release_control import ActionReceipt, ReleaseManifest
from tests.test_release_approval_evidence_gate import (
    _authority_receipt,
    _captured_evidence_statuses,
    _manifest,
    _mapped_registry,
)
from tests.test_release_control_state_machine import _complete_payload, _scopes


class _AlwaysFailingAttestation:
    def __init__(self) -> None:
        self.calls = 0

    def verify(self, _receipt) -> bool:
        self.calls += 1
        raise LookupError("untrusted attestation adapter detail")


class _FailingAttestationRecheck:
    def __init__(self) -> None:
        self.calls = 0

    def verify(self, _receipt) -> bool:
        self.calls += 1
        if self.calls == 1:
            return True
        raise LookupError("changed attestation adapter detail")


def test_non_runtime_attestation_error_fails_closed_before_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = _mapped_registry()
    manifest = _manifest(registry=registry)
    authority_receipt = _authority_receipt(manifest, registry=registry)
    attestation = _AlwaysFailingAttestation()
    evidence_calls = 0

    def evidence_must_not_run(*_args, **_kwargs):
        nonlocal evidence_calls
        evidence_calls += 1
        raise AssertionError("untrusted authority must block before evidence execution")

    monkeypatch.setattr(
        approval_module,
        "load_release_approval_registry",
        lambda _path=None: registry,
    )
    monkeypatch.setattr(
        approval_module,
        "execute_registry_evidence",
        evidence_must_not_run,
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
            authority_receipt=authority_receipt,
        )

    assert exc_info.value.receipt.status == "blocked"
    assert "authority_attestation_not_verified" in exc_info.value.receipt.reason_codes
    assert "untrusted attestation adapter detail" not in str(exc_info.value)
    assert attestation.calls == 1
    assert evidence_calls == 0


def test_non_runtime_attestation_recheck_error_invalidates_approval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = _mapped_registry()
    manifest = _manifest(registry=registry)
    authority_receipt = _authority_receipt(manifest, registry=registry)
    attestation = _FailingAttestationRecheck()
    evidence_calls = 0

    def captured_evidence(*_args, **_kwargs):
        nonlocal evidence_calls
        evidence_calls += 1
        return _captured_evidence_statuses(authority_receipt)

    monkeypatch.setattr(
        approval_module,
        "load_release_approval_registry",
        lambda _path=None: registry,
    )
    monkeypatch.setattr(
        approval_module,
        "execute_registry_evidence",
        captured_evidence,
    )
    verifier = ReleaseApprovalVerifier(
        authority_attestation_verifier=attestation,
        clock=lambda: datetime(2026, 8, 31, tzinfo=UTC),
    )

    with pytest.raises(ApprovalVerificationBlocked) as exc_info:
        verifier.verify_promotion(
            release_id=manifest.release_id,
            manifest_sha256=manifest.content_sha256,
            manifest_payload=manifest.payload,
            authority_receipt=authority_receipt,
        )

    assert exc_info.value.receipt.status == "blocked"
    assert "authority_attestation_changed_during_verification" in (
        exc_info.value.receipt.reason_codes
    )
    assert "changed attestation adapter detail" not in str(exc_info.value)
    assert attestation.calls == 2
    assert evidence_calls == 1


class _CreateFailureRepo:
    def __init__(self, error: Exception) -> None:
        self.error = error
        self.append_calls = 0

    def get_manifest(self, _release_id: str):
        return None

    def create_manifest(self, **_kwargs):
        raise self.error

    def append_event(self, **_kwargs):
        self.append_calls += 1
        raise AssertionError("a failed create must not append a lifecycle event")


@pytest.mark.parametrize("known_error", [True, False])
def test_prepare_release_maps_only_known_repository_errors(known_error: bool) -> None:
    release_id = "release-create-boundary"
    payload = _complete_payload(release_id)
    manifest = ReleaseManifest(release_id=release_id, state="candidate", payload=payload)
    error: Exception
    expected_error: type[Exception]
    if known_error:
        error = ManifestConflictError(
            release_id,
            expected_digest=manifest.content_sha256,
            actual_digest="0" * 64,
        )
        expected_error = ReleaseConflictError
    else:
        error = LookupError("unexpected create failure")
        expected_error = LookupError
    repo = _CreateFailureRepo(error)
    service = ReleaseControlService(repo=repo)

    with pytest.raises(expected_error) as exc_info:
        service.prepare_release(release_id=release_id, payload=payload, freeze=True)

    if known_error:
        assert str(exc_info.value) == "repository compare-and-swap conflict"
        assert exc_info.value.__cause__ is error
    else:
        assert exc_info.value is error
    assert repo.append_calls == 0


class _ActivationFailureRepo:
    def __init__(self, manifest: ReleaseManifest, error: Exception) -> None:
        self.error = error
        self.activate_kwargs: dict[str, object] | None = None
        self.stored = {
            "release_id": manifest.release_id,
            "content_sha256": manifest.content_sha256,
            "payload": manifest.payload.model_dump(mode="json"),
        }

    def get_manifest(self, _release_id: str):
        return self.stored

    def list_events(self, **_kwargs):
        return [{"to_state": "approved"}]

    def activate_release(self, **kwargs):
        self.activate_kwargs = kwargs
        raise self.error


def _passed_gate(manifest: ReleaseManifest):
    return build_approval_gate_receipt(
        {
            "status": "passed",
            "reason_codes": (),
            "release_id": manifest.release_id,
            "manifest_sha256": manifest.content_sha256,
            "registry_sha256": manifest.payload.approval_registry_sha256,
            "authority_receipt_sha256": "8" * 64,
            "checked_at": datetime(2026, 8, 31, tzinfo=UTC),
            "subjects": (),
        }
    )


def _activation_service(
    monkeypatch: pytest.MonkeyPatch,
    *,
    error: Exception,
) -> tuple[ReleaseControlService, _ActivationFailureRepo, ReleaseManifest]:
    release_id = "release-activation-boundary"
    manifest = ReleaseManifest(
        release_id=release_id,
        state="candidate",
        payload=_complete_payload(release_id),
    )
    repo = _ActivationFailureRepo(manifest, error)
    service = ReleaseControlService(repo=repo)
    monkeypatch.setattr(
        service,
        "_verify_promotion_approval",
        lambda *, manifest: _passed_gate(manifest),
    )
    monkeypatch.setattr(service, "_find_event_replay", lambda **_kwargs: None)
    return service, repo, manifest


def test_rollback_repository_error_is_disclosed_without_success_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = ReleaseStateConflictError(
        "release-activation-boundary",
        action="rollback",
        actual_state="approved",
    )
    service, repo, manifest = _activation_service(monkeypatch, error=error)

    with pytest.raises(ReleaseGateBlockedError) as exc_info:
        service.rollback_release_bundle(
            to_release_id=manifest.release_id,
            scopes=_scopes(0),
            reason="post-promote validation failed",
            mode="forward_rebuild",
            idempotency_key="rollback-boundary",
        )

    assert str(exc_info.value) == "repository rejected the release state transition"
    assert exc_info.value.__cause__ is error
    assert repo.activate_kwargs is not None
    assert repo.activate_kwargs["action"] == "rollback"
    assert repo.activate_kwargs["operation_payload"] == {
        "reason": "post-promote validation failed",
        "mode": "forward_rebuild",
    }


def test_promote_unknown_repository_error_is_raised_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = LookupError("unexpected promote failure")
    service, repo, manifest = _activation_service(monkeypatch, error=error)

    with pytest.raises(LookupError) as exc_info:
        service.promote_release_bundle(
            release_id=manifest.release_id,
            scopes=_scopes(0),
            idempotency_key="promote-boundary",
        )

    assert exc_info.value is error
    assert repo.activate_kwargs is not None
    assert repo.activate_kwargs["action"] == "promote"
    assert repo.activate_kwargs["operation_payload"] == {}


class _AppendFailureRepo:
    def __init__(self, error: Exception) -> None:
        self.error = error
        self.append_calls = 0

    def append_event(self, **_kwargs):
        self.append_calls += 1
        raise self.error


@pytest.mark.parametrize("known_error", [True, False])
def test_lifecycle_append_maps_only_known_repository_errors(known_error: bool) -> None:
    release_id = "release-event-boundary"
    error: Exception
    expected_error: type[Exception]
    if known_error:
        error = IdempotencyConflictError(
            "prepare",
            "prepare-boundary",
            target_environment="test",
            release_id=release_id,
        )
        expected_error = ReleaseConflictError
    else:
        error = LookupError("unexpected append failure")
        expected_error = LookupError
    repo = _AppendFailureRepo(error)
    service = ReleaseControlService(repo=repo)
    receipt = ActionReceipt(
        action="prepare",
        outcome="applied",
        release_id=release_id,
        release_state="candidate",
        manifest_digest="A" * 64,
        target_environment="test",
        idempotency_key="prepare-boundary",
    )

    with pytest.raises(expected_error) as exc_info:
        service._append_lifecycle_event(
            receipt=receipt,
            from_state="draft",
            to_state="candidate",
            request_sha256="B" * 64,
            event_payload={"manifest_kind": "release_bundle"},
        )

    if known_error:
        assert str(exc_info.value) == "repository compare-and-swap conflict"
        assert exc_info.value.__cause__ is error
    else:
        assert exc_info.value is error
    assert repo.append_calls == 1
