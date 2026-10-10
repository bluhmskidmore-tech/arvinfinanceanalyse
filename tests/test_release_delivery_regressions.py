from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from backend.app.governance import release_approval as approval_module
from backend.app.governance.release_approval import (
    ApprovalVerificationBlocked,
    ReleaseApprovalVerifier,
)
from backend.app.schemas.release_approval import build_approval_gate_receipt
from backend.app.schemas.release_control import canonical_sha256
from tests.test_release_approval_evidence_gate import (
    _authority_receipt,
    _captured_evidence_statuses,
    _mapped_registry,
    _manifest,
)
from tests.test_release_control_repo import _candidate_to_approved, _repo
from tests.test_release_control_state_machine import (
    _authority_receipt as _service_authority_receipt,
    _complete_payload,
    _scopes,
    _service,
    _VerifiedTestApprovalVerifier,
    _validation_receipts,
)


def _release_control_error_type(service):
    return service.__class__.__init__.__globals__["ReleaseControlError"]


class _NonBooleanAttestation:
    def __init__(self, values: tuple[object, ...]) -> None:
        self.values = iter(values)
        self.calls = 0

    def verify(self, _receipt):
        self.calls += 1
        return next(self.values)


class _RejectedRecordApprovalVerifier:
    def __init__(self, receipt) -> None:
        self.receipt = receipt

    def verify_record_approval(self, **_kwargs):
        raise ApprovalVerificationBlocked(self.receipt)


class _MutatingPromotionGateVerifier(_VerifiedTestApprovalVerifier):
    def __init__(self, field: str) -> None:
        self.field = field

    def verify_promotion(self, **kwargs):
        gate = self._verify(**kwargs)
        payload = gate.model_dump(mode="json")
        payload.pop("receipt_sha256", None)
        if self.field == "authority_receipt_sha256":
            payload["authority_receipt_sha256"] = "A" * 64
        elif self.field == "subjects":
            payload["subjects"] = []
        elif self.field == "subject_approval":
            payload["subjects"][0]["approval_id"] = "wrong-approval"
        elif self.field == "subject_scope":
            payload["subjects"][0]["subject_key"] = "wrong-scope"
        elif self.field == "subject_evidence":
            payload["subjects"][0]["evidence_receipt_sha256"] = "B" * 64
        return build_approval_gate_receipt(payload)


def test_non_boolean_attestation_blocks_before_evidence_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = _mapped_registry()
    manifest = _manifest(registry=registry)
    authority_receipt = _authority_receipt(manifest, registry=registry)
    attestation = _NonBooleanAttestation(("approved",))
    evidence_calls = 0

    def evidence_must_not_run(*_args, **_kwargs):
        nonlocal evidence_calls
        evidence_calls += 1
        raise AssertionError("non-boolean trust result must block before evidence")

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
    )

    with pytest.raises(ApprovalVerificationBlocked) as exc_info:
        verifier.verify_record_approval(
            release_id=manifest.release_id,
            manifest_sha256=manifest.content_sha256,
            manifest_payload=manifest.payload,
            authority_receipt=authority_receipt,
        )

    assert "authority_attestation_not_verified" in exc_info.value.receipt.reason_codes
    assert evidence_calls == 0
    assert attestation.calls == 1


def test_non_boolean_attestation_recheck_invalidates_after_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = _mapped_registry()
    manifest = _manifest(registry=registry)
    authority_receipt = _authority_receipt(manifest, registry=registry)
    attestation = _NonBooleanAttestation((True, "approved"))
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
    )

    with pytest.raises(ApprovalVerificationBlocked) as exc_info:
        verifier.verify_promotion(
            release_id=manifest.release_id,
            manifest_sha256=manifest.content_sha256,
            manifest_payload=manifest.payload,
            authority_receipt=authority_receipt,
        )

    assert "authority_attestation_changed_during_verification" in (
        exc_info.value.receipt.reason_codes
    )
    assert evidence_calls == 1
    assert attestation.calls == 2


def test_rejected_record_approval_does_not_append_an_approval_event(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    release_id = "release-rejected-approval"
    prepare = service.prepare_release(
        release_id=release_id,
        payload=_complete_payload(release_id),
        freeze=True,
    )
    service.record_validation(release_id, validation_receipts=_validation_receipts())
    before = service.show_release(release_id)
    blocked_receipt = build_approval_gate_receipt(
        {
            "status": "blocked",
            "reason_codes": ("authority_attestation_not_verified",),
            "release_id": release_id,
            "manifest_sha256": prepare.manifest_digest,
            "registry_sha256": "7" * 64,
            "authority_receipt_sha256": "8" * 64,
            "checked_at": "2026-08-31T00:00:00Z",
            "subjects": (),
        }
    )
    service.approval_verifier = _RejectedRecordApprovalVerifier(blocked_receipt)

    with pytest.raises(_release_control_error_type(service)) as exc_info:
        service.record_approval(
            release_id=release_id,
            manifest_digest=prepare.manifest_digest,
            authority_receipt=_service_authority_receipt(
                release_id,
                prepare.manifest_digest,
            ),
        )

    assert "authority_attestation_not_verified" in str(exc_info.value)
    after = service.show_release(release_id)
    assert after.state == "validated"
    assert after.events == before.events
    assert after.aliases == before.aliases


def test_approval_replay_returns_the_original_receipt_once(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    release_id = "release-approval-replay"
    prepare = service.prepare_release(
        release_id=release_id,
        payload=_complete_payload(release_id),
        freeze=True,
    )
    service.record_validation(release_id, validation_receipts=_validation_receipts())
    authority_receipt = _service_authority_receipt(release_id, prepare.manifest_digest)
    first = service.record_approval(
        release_id=release_id,
        manifest_digest=prepare.manifest_digest,
        authority_receipt=authority_receipt,
        idempotency_key="approval-replay",
    )
    second = service.record_approval(
        release_id=release_id,
        manifest_digest=prepare.manifest_digest,
        authority_receipt=authority_receipt,
        idempotency_key="approval-replay",
    )

    assert second == first
    approval_events = [
        event
        for event in service.show_release(release_id).events
        if event["action"] == "approve-record"
    ]
    assert len(approval_events) == 1
    assert approval_events[0]["receipt"] == first.model_dump(
        mode="json",
        exclude_none=True,
    )


def test_approval_replay_rechecks_current_authority_before_replaying(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    release_id = "release-approval-revoked-replay"
    prepare = service.prepare_release(
        release_id=release_id,
        payload=_complete_payload(release_id),
        freeze=True,
    )
    service.record_validation(release_id, validation_receipts=_validation_receipts())
    authority_receipt = _service_authority_receipt(release_id, prepare.manifest_digest)
    first = service.record_approval(
        release_id=release_id,
        manifest_digest=prepare.manifest_digest,
        authority_receipt=authority_receipt,
        idempotency_key="approval-revoked-replay",
    )
    blocked_receipt = build_approval_gate_receipt(
        {
            "status": "blocked",
            "reason_codes": ("authority_receipt_revoked",),
            "release_id": release_id,
            "manifest_sha256": prepare.manifest_digest,
            "registry_sha256": "7" * 64,
            "authority_receipt_sha256": "8" * 64,
            "checked_at": "2026-08-31T00:00:00Z",
            "subjects": (),
        }
    )
    service.approval_verifier = _RejectedRecordApprovalVerifier(blocked_receipt)

    with pytest.raises(_release_control_error_type(service)):
        service.record_approval(
            release_id=release_id,
            manifest_digest=prepare.manifest_digest,
            authority_receipt=authority_receipt,
            idempotency_key="approval-revoked-replay",
        )

    approval_events = [
        event
        for event in service.show_release(release_id).events
        if event["action"] == "approve-record"
    ]
    assert first.outcome == "applied"
    assert len(approval_events) == 1


@pytest.mark.parametrize(
    "field",
    [
        "missing_authority_receipt",
        "missing_approval_gate_receipt",
        "stored_authority_wrong_release",
        "stored_gate_wrong_manifest",
    ],
)
def test_approval_replay_rejects_event_payload_binding_tampering(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    field: str,
) -> None:
    service = _service(tmp_path)
    release_id = "release-approval-event-payload-binding"
    prepare = service.prepare_release(
        release_id=release_id,
        payload=_complete_payload(release_id),
        freeze=True,
    )
    service.record_validation(release_id, validation_receipts=_validation_receipts())
    authority_receipt = _service_authority_receipt(release_id, prepare.manifest_digest)
    idempotency_key = f"approval-event-payload-{field}"
    service.record_approval(
        release_id=release_id,
        manifest_digest=prepare.manifest_digest,
        authority_receipt=authority_receipt,
        idempotency_key=idempotency_key,
    )

    repository = service.repo
    original_list_events = repository.list_events
    stored_event = next(
        event
        for event in original_list_events(release_id=release_id, action="approve-record")
        if event["idempotency_key"] == idempotency_key
    )
    event_payload = deepcopy(stored_event["event_payload"])
    if field == "missing_authority_receipt":
        event_payload.pop("authority_receipt")
    elif field == "missing_approval_gate_receipt":
        event_payload.pop("approval_gate_receipt")
    elif field == "stored_authority_wrong_release":
        event_payload["authority_receipt"] = _service_authority_receipt(
            "other-release",
            prepare.manifest_digest,
        ).model_dump(mode="json")
    elif field == "stored_gate_wrong_manifest":
        gate_payload = deepcopy(event_payload["approval_gate_receipt"])
        gate_payload.pop("receipt_sha256", None)
        gate_payload["manifest_sha256"] = "B" * 64
        event_payload["approval_gate_receipt"] = build_approval_gate_receipt(
            gate_payload
        ).model_dump(mode="json")

    def list_events(**kwargs):
        if kwargs.get("action") == "approve-record":
            malformed_event = dict(stored_event)
            malformed_event["event_payload"] = event_payload
            return [malformed_event]
        return original_list_events(**kwargs)

    monkeypatch.setattr(repository, "list_events", list_events)

    with pytest.raises(_release_control_error_type(service)):
        service.record_approval(
            release_id=release_id,
            manifest_digest=prepare.manifest_digest,
            authority_receipt=authority_receipt,
            idempotency_key=idempotency_key,
        )

    approval_events = [
        event
        for event in service.show_release(release_id).events
        if event["action"] == "approve-record"
    ]
    assert len(approval_events) == 1


@pytest.mark.parametrize("field", ["release_id_numeric", "idempotency_key_numeric"])
def test_activation_replay_rejects_non_string_event_envelope_fields(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    field: str,
) -> None:
    service = _service(tmp_path)
    release_id = "release-activation-envelope-type-binding"
    prepare = service.prepare_release(
        release_id=release_id,
        payload=_complete_payload(release_id),
        freeze=True,
    )
    service.record_validation(release_id, validation_receipts=_validation_receipts())
    service.record_approval(
        release_id=release_id,
        manifest_digest=prepare.manifest_digest,
        authority_receipt=_service_authority_receipt(release_id, prepare.manifest_digest),
    )
    idempotency_key = "123" if field == "idempotency_key_numeric" else "activation-envelope-type"
    first = service.promote_release_bundle(
        release_id=release_id,
        scopes=_scopes(0),
        idempotency_key=idempotency_key,
    )
    repository = service.repo
    original_list_events = repository.list_events
    target_event = next(
        event
        for event in original_list_events(release_id=release_id, action="promote")
        if event["idempotency_key"] == idempotency_key
    )
    malformed_event = dict(target_event)
    if field == "release_id_numeric":
        malformed_event["release_id"] = 123
    elif field == "idempotency_key_numeric":
        malformed_event["idempotency_key"] = 123

    def list_events(**kwargs):
        if kwargs.get("action") == "promote":
            return [malformed_event]
        return original_list_events(**kwargs)

    monkeypatch.setattr(repository, "list_events", list_events)

    with pytest.raises(_release_control_error_type(service)):
        service.promote_release_bundle(
            release_id=release_id,
            scopes=_scopes(0),
            idempotency_key=idempotency_key,
        )

    assert len(
        [
            event
            for event in service.show_release(release_id).events
            if event["action"] == "promote"
        ]
    ) == 1
    assert first.outcome == "applied"


@pytest.mark.parametrize(
    "field",
    ["release_id", "to_state", "event_id_numeric", "idempotency_key_numeric"],
)
def test_approval_replay_rejects_non_matching_event_envelope(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    field: str,
) -> None:
    service = _service(tmp_path)
    release_id = "release-approval-envelope-binding"
    prepare = service.prepare_release(
        release_id=release_id,
        payload=_complete_payload(release_id),
        freeze=True,
    )
    service.record_validation(release_id, validation_receipts=_validation_receipts())
    authority_receipt = _service_authority_receipt(release_id, prepare.manifest_digest)
    idempotency_key = "123" if field == "idempotency_key_numeric" else f"approval-envelope-{field}"
    service.record_approval(
        release_id=release_id,
        manifest_digest=prepare.manifest_digest,
        authority_receipt=authority_receipt,
        idempotency_key=idempotency_key,
    )
    repository = service.repo
    original_list_events = repository.list_events
    stored_event = next(
        event
        for event in original_list_events(release_id=release_id, action="approve-record")
        if event["idempotency_key"] == idempotency_key
    )
    malformed_event = dict(stored_event)
    if field == "release_id":
        malformed_event["release_id"] = "other-release"
    elif field == "to_state":
        malformed_event["to_state"] = "validated"
    elif field == "event_id_numeric":
        malformed_event["event_id"] = 123
    elif field == "idempotency_key_numeric":
        malformed_event["idempotency_key"] = 123

    def list_events(**kwargs):
        if kwargs.get("action") == "approve-record":
            return [malformed_event]
        return original_list_events(**kwargs)

    monkeypatch.setattr(repository, "list_events", list_events)

    with pytest.raises(_release_control_error_type(service)):
        service.record_approval(
            release_id=release_id,
            manifest_digest=prepare.manifest_digest,
            authority_receipt=authority_receipt,
            idempotency_key=idempotency_key,
        )

    assert len(
        [
            event
            for event in service.show_release(release_id).events
            if event["action"] == "approve-record"
        ]
    ) == 1


@pytest.mark.parametrize(
    "field",
    [
        "authority_receipt_sha256",
        "subjects",
        "subject_approval",
        "subject_scope",
        "subject_evidence",
    ],
)
def test_promotion_rejects_passed_gate_that_does_not_bind_authority(
    tmp_path: Path,
    field: str,
) -> None:
    service = _service(tmp_path)
    release_id = "release-promotion-gate-binding"
    prepare = service.prepare_release(
        release_id=release_id,
        payload=_complete_payload(release_id),
        freeze=True,
    )
    service.record_validation(release_id, validation_receipts=_validation_receipts())
    service.record_approval(
        release_id=release_id,
        manifest_digest=prepare.manifest_digest,
        authority_receipt=_service_authority_receipt(release_id, prepare.manifest_digest),
    )
    service.approval_verifier = _MutatingPromotionGateVerifier(field)
    activation_calls = 0

    def fail_if_activated(**_kwargs):
        nonlocal activation_calls
        activation_calls += 1
        raise AssertionError("approval gate must reject before alias activation")

    service.repo.activate_release = fail_if_activated

    with pytest.raises(_release_control_error_type(service)):
        service.promote_release_bundle(
            release_id=release_id,
            scopes=_scopes(0),
            idempotency_key=f"gate-binding-{field}",
        )

    assert activation_calls == 0


def _malformed_replay_event(
    *, idempotency_key: str, receipt: object, request_sha256: str | None
) -> dict[str, object]:
    return {
        "event_id": "malformed-replay-event",
        "action": "validate",
        "idempotency_key": idempotency_key,
        "request_sha256": request_sha256,
        "receipt": receipt,
    }


@pytest.mark.parametrize(
    ("receipt", "missing_request"),
    [
        (None, False),
        ({"action": "invalid-action"}, False),
        (None, True),
    ],
    ids=["missing-receipt", "invalid-receipt", "missing-request-digest"],
)
def test_malformed_matching_validation_replay_cannot_become_applied(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    receipt: object,
    missing_request: bool,
) -> None:
    service = _service(tmp_path)
    release_id = "release-malformed-validation-replay"
    service.prepare_release(
        release_id=release_id,
        payload=_complete_payload(release_id),
        freeze=True,
    )
    repository = service.repo
    original_list_events = repository.list_events
    validation_receipts = _validation_receipts()
    request_sha256 = canonical_sha256(
        {
            "action": "validate",
            "release_id": release_id,
            "manifest_digest": service.repo.get_manifest(release_id).content_sha256,
            "validation_receipts": validation_receipts,
        }
    )

    def list_events(**kwargs):
        if kwargs.get("action") == "validate":
            return [
                _malformed_replay_event(
                    idempotency_key="malformed-validation-replay",
                    receipt=receipt,
                    request_sha256=None if missing_request else request_sha256,
                )
            ]
        return original_list_events(**kwargs)

    monkeypatch.setattr(repository, "list_events", list_events)

    with pytest.raises(_release_control_error_type(service)):
        service.record_validation(
            release_id,
            validation_receipts=validation_receipts,
            idempotency_key="malformed-validation-replay",
        )


class _MalformedActivationRepository:
    def __init__(
        self,
        manifest: Any,
        receipt: dict[str, Any],
        *,
        wrong_request_sha256: str | None = None,
        preserve_fields: set[str] | None = None,
        mutate_receipt: Any = None,
    ) -> None:
        self.manifest = manifest
        self.receipt = receipt
        self.wrong_request_sha256 = wrong_request_sha256
        self.preserve_fields = preserve_fields or set()
        self.mutate_receipt = mutate_receipt

    def get_manifest(self, _release_id: str):
        return self.manifest

    def list_events(self, **kwargs):
        if kwargs.get("action") == "approve-record":
            return [{"to_state": "approved"}]
        return []

    def activate_release(self, **_kwargs):
        kwargs = _kwargs
        result = deepcopy(self.receipt)
        result["request_sha256"] = self.wrong_request_sha256 or kwargs["request_sha256"]
        if "operation_payload" not in self.preserve_fields:
            result["operation_payload"] = deepcopy(kwargs["operation_payload"])
        if "approval_gate_receipt" not in self.preserve_fields:
            result["approval_gate_receipt"] = deepcopy(kwargs["approval_gate_receipt"])
        if "events" not in self.preserve_fields:
            result["events"] = [
                {
                    "event_id": "synthetic-activation-event",
                    "release_id": kwargs["release_id"],
                    "action": kwargs["action"],
                    "from_state": "approved",
                    "to_state": "current",
                }
            ]
        if callable(self.mutate_receipt):
            self.mutate_receipt(result)
        return result


def _activation_receipt_base(
    *,
    release_id: str,
    manifest_digest: str,
    idempotency_key: str,
) -> dict[str, Any]:
    return {
        "action": "promote",
        "release_id": release_id,
        "manifest_digest": manifest_digest,
        "target_environment": "test",
        "idempotency_key": idempotency_key,
        "status": "current",
        "scopes": [
            {
                "target_environment": "test",
                "scope_kind": "physical_bundle",
                "scope_key": "duckdb-main",
                "previous_release_id": None,
                "current_release_id": release_id,
                "previous_revision": 0,
                "revision": 1,
                "alias_payload": {},
            },
            {
                "target_environment": "test",
                "scope_kind": "logical_lane",
                "scope_key": "bond-analytics-risk-tensor",
                "previous_release_id": None,
                "current_release_id": release_id,
                "previous_revision": 0,
                "revision": 1,
                "alias_payload": {},
            },
            {
                "target_environment": "test",
                "scope_kind": "logical_lane",
                "scope_key": "bond-analytics-core",
                "previous_release_id": None,
                "current_release_id": release_id,
                "previous_revision": 0,
                "revision": 1,
                "alias_payload": {},
            },
        ],
    }


@pytest.mark.parametrize(
    "field",
    [
        "action",
        "release_id",
        "manifest_digest",
        "target_environment",
        "idempotency_key",
        "request_sha256",
        "status",
        "scope_target_environment",
        "scope_current_release_id",
        "scope_revision",
        "scope_alias_payload",
        "scope_key",
        "missing_scope",
        "duplicate_scope",
        "operation_payload",
        "approval_gate_receipt",
        "approval_gate_checked_at",
        "events",
        "scope_previous_revision",
    ],
)
def test_live_activation_receipt_must_bind_request_and_scope_plan(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    field: str,
) -> None:
    service = _service(tmp_path)
    release_id = "release-live-receipt-binding"
    digest = service.prepare_release(
        release_id=release_id,
        payload=_complete_payload(release_id),
        freeze=True,
    ).manifest_digest
    service.record_validation(release_id, validation_receipts=_validation_receipts())
    service.record_approval(
        release_id=release_id,
        manifest_digest=digest,
        authority_receipt=_service_authority_receipt(release_id, digest),
    )
    idempotency_key = f"promote-{field}"
    receipt = _activation_receipt_base(
        release_id=release_id,
        manifest_digest=digest,
        idempotency_key=idempotency_key,
    )
    if field == "action":
        receipt["action"] = "rollback"
    elif field == "release_id":
        receipt["release_id"] = "other-release"
    elif field == "manifest_digest":
        receipt["manifest_digest"] = "A" * 64
    elif field == "target_environment":
        receipt["target_environment"] = "staging"
    elif field == "idempotency_key":
        receipt["idempotency_key"] = "other-key"
    elif field == "request_sha256":
        receipt["request_sha256"] = "B" * 64
    elif field == "status":
        receipt["status"] = "approved"
    elif field == "scope_target_environment":
        receipt["scopes"][0]["target_environment"] = "staging"
    elif field == "scope_current_release_id":
        receipt["scopes"][0]["current_release_id"] = "other-release"
    elif field == "scope_revision":
        receipt["scopes"][0]["revision"] = 2
    elif field == "scope_alias_payload":
        receipt["scopes"][0]["alias_payload"] = {"channel": "wrong"}
    elif field == "scope_key":
        receipt["scopes"][0]["scope_key"] = "unexpected-scope"
    elif field == "missing_scope":
        receipt["scopes"].pop()
    elif field == "duplicate_scope":
        receipt["scopes"].append(deepcopy(receipt["scopes"][0]))
    elif field == "operation_payload":
        receipt["operation_payload"] = {"reason": "tampered"}
    elif field == "approval_gate_receipt":
        receipt["approval_gate_receipt"] = {"status": "blocked"}
    elif field == "events":
        receipt["events"] = []
    elif field == "scope_previous_revision":
        receipt["scopes"][0]["previous_revision"] = 1

    def mutate_receipt(result: dict[str, Any]) -> None:
        if field != "approval_gate_checked_at":
            return
        gate_payload = deepcopy(result["approval_gate_receipt"])
        gate_payload.pop("receipt_sha256", None)
        gate_payload["checked_at"] = "2026-09-05T00:00:00Z"
        result["approval_gate_receipt"] = build_approval_gate_receipt(gate_payload).model_dump(
            mode="json"
        )

    monkeypatch.setattr(
        service.repo,
        "activate_release",
        _MalformedActivationRepository(
            service.repo.get_manifest(release_id),
            receipt,
            wrong_request_sha256=("B" * 64 if field == "request_sha256" else None),
            preserve_fields=({field} if field != "approval_gate_checked_at" else set()),
            mutate_receipt=mutate_receipt,
        ).activate_release,
    )

    with pytest.raises(_release_control_error_type(service)):
        service.promote_release_bundle(
            release_id=release_id,
            scopes=_scopes(0),
            idempotency_key=idempotency_key,
        )


def test_replayed_activation_receipt_must_bind_request_and_scope_plan(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    release_id = "release-replayed-receipt-binding"
    digest = service.prepare_release(
        release_id=release_id,
        payload=_complete_payload(release_id),
        freeze=True,
    ).manifest_digest
    service.record_validation(release_id, validation_receipts=_validation_receipts())
    service.record_approval(
        release_id=release_id,
        manifest_digest=digest,
        authority_receipt=_service_authority_receipt(release_id, digest),
    )
    idempotency_key = "replayed-receipt-binding"
    receipt = _activation_receipt_base(
        release_id=release_id,
        manifest_digest=digest,
        idempotency_key=idempotency_key,
    )
    receipt["status"] = "approved"
    normalized_scopes = [
        {
            "scope_kind": "physical_bundle",
            "scope_key": "duckdb-main",
            "expected_revision": 0,
            "alias_payload": {},
        },
        {
            "scope_kind": "logical_lane",
            "scope_key": "bond-analytics-core",
            "expected_revision": 0,
            "alias_payload": {},
        },
        {
            "scope_kind": "logical_lane",
            "scope_key": "bond-analytics-risk-tensor",
            "expected_revision": 0,
            "alias_payload": {},
        },
    ]
    request_sha256 = canonical_sha256(
        {
            "action": "promote",
            "target_environment": "test",
            "release_id": release_id,
            "manifest_digest": digest,
            "target_transition": "current",
            "replacement_transition": "deprecated",
            "operation_payload": {},
            "scope_expectations": normalized_scopes,
        }
    )
    receipt["request_sha256"] = request_sha256
    repository = service.repo
    original_list_events = repository.list_events

    def list_events(**kwargs):
        if kwargs.get("action") == "promote":
            return [
                {
                    "event_id": "replayed-activation",
                    "idempotency_key": idempotency_key,
                    "request_sha256": request_sha256,
                    "receipt": receipt,
                }
            ]
        return original_list_events(**kwargs)

    monkeypatch.setattr(repository, "list_events", list_events)

    with pytest.raises(_release_control_error_type(service)):
        service.promote_release_bundle(
            release_id=release_id,
            scopes=_scopes(0),
            idempotency_key=idempotency_key,
        )


@pytest.mark.parametrize(
    "field",
    [
        "operation_payload",
        "approval_gate_receipt",
        "approval_gate_checked_at",
        "events",
        "scope_previous_revision",
        "event_payload_request_release_id",
        "scope_alias_payload_none",
        "scope_alias_payload_list",
    ],
)
def test_replayed_activation_receipt_rejects_unbound_operational_fields(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    field: str,
) -> None:
    service = _service(tmp_path)
    release_id = "release-replayed-operational-binding"
    prepare = service.prepare_release(
        release_id=release_id,
        payload=_complete_payload(release_id),
        freeze=True,
    )
    service.record_validation(release_id, validation_receipts=_validation_receipts())
    service.record_approval(
        release_id=release_id,
        manifest_digest=prepare.manifest_digest,
        authority_receipt=_service_authority_receipt(release_id, prepare.manifest_digest),
    )
    idempotency_key = f"replayed-operational-{field}"
    first = service.promote_release_bundle(
        release_id=release_id,
        scopes=_scopes(0),
        idempotency_key=idempotency_key,
    )
    malformed_receipt = deepcopy(first.details["repository_receipt"])
    original_promote_event = next(
        event
        for event in service.repo.list_events(release_id=release_id, action="promote")
        if event["idempotency_key"] == idempotency_key
    )
    event_payload = deepcopy(original_promote_event["event_payload"])
    if field == "operation_payload":
        malformed_receipt["operation_payload"] = {"reason": "tampered"}
    elif field == "approval_gate_receipt":
        malformed_receipt["approval_gate_receipt"]["manifest_sha256"] = "B" * 64
    elif field == "approval_gate_checked_at":
        gate_payload = deepcopy(malformed_receipt["approval_gate_receipt"])
        gate_payload.pop("receipt_sha256", None)
        gate_payload["checked_at"] = "2026-09-05T00:00:00Z"
        malformed_receipt["approval_gate_receipt"] = build_approval_gate_receipt(
            gate_payload
        ).model_dump(mode="json")
    elif field == "events":
        malformed_receipt["events"] = [{"action": "unexpected"}]
    elif field == "scope_previous_revision":
        malformed_receipt["scopes"][0]["previous_revision"] = 1
    elif field == "event_payload_request_release_id":
        event_payload["request"]["release_id"] = "other-release"
    elif field == "scope_alias_payload_none":
        malformed_receipt["scopes"][0]["alias_payload"] = None
    elif field == "scope_alias_payload_list":
        malformed_receipt["scopes"][0]["alias_payload"] = []

    repository = service.repo
    original_list_events = repository.list_events

    def list_events(**kwargs):
        if kwargs.get("action") == "promote":
            return [
                {
                    "event_id": "replayed-operational-event",
                    "idempotency_key": idempotency_key,
                    "request_sha256": first.details["repository_receipt"]["request_sha256"],
                    "receipt": malformed_receipt,
                    "event_payload": event_payload,
                }
            ]
        return original_list_events(**kwargs)

    monkeypatch.setattr(repository, "list_events", list_events)

    with pytest.raises(_release_control_error_type(service)):
        service.promote_release_bundle(
            release_id=release_id,
            scopes=_scopes(0),
            idempotency_key=idempotency_key,
        )


def test_replayed_activation_receipt_rejects_fake_previous_release_with_supersede_event(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    release_id = "release-replayed-previous-release-binding"
    prepare = service.prepare_release(
        release_id=release_id,
        payload=_complete_payload(release_id),
        freeze=True,
    )
    service.record_validation(release_id, validation_receipts=_validation_receipts())
    service.record_approval(
        release_id=release_id,
        manifest_digest=prepare.manifest_digest,
        authority_receipt=_service_authority_receipt(release_id, prepare.manifest_digest),
    )
    idempotency_key = "replayed-previous-release-binding"
    first = service.promote_release_bundle(
        release_id=release_id,
        scopes=_scopes(0),
        idempotency_key=idempotency_key,
    )
    malformed_receipt = deepcopy(first.details["repository_receipt"])
    malformed_receipt["scopes"][0]["previous_release_id"] = "ghost-release"
    malformed_receipt["events"].append(
        {
            "event_id": "ghost-supersede-event",
            "release_id": "ghost-release",
            "action": "supersede",
            "from_state": "current",
            "to_state": "deprecated",
        }
    )
    repository = service.repo
    original_list_events = repository.list_events
    target_event = next(
        event
        for event in original_list_events(release_id=release_id, action="promote")
        if event["idempotency_key"] == idempotency_key
    )

    def list_events(**kwargs):
        if kwargs.get("action") == "promote":
            replay_event = dict(target_event)
            replay_event["receipt"] = malformed_receipt
            return [replay_event]
        return original_list_events(**kwargs)

    monkeypatch.setattr(repository, "list_events", list_events)

    with pytest.raises(_release_control_error_type(service)):
        service.promote_release_bundle(
            release_id=release_id,
            scopes=_scopes(0),
            idempotency_key=idempotency_key,
        )


def test_historical_activation_replay_survives_alias_replacement(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    manifests: dict[str, str] = {}
    for release_id in ("release-historical-replay-a", "release-historical-replay-b"):
        prepare = service.prepare_release(
            release_id=release_id,
            payload=_complete_payload(release_id),
            freeze=True,
        )
        manifests[release_id] = prepare.manifest_digest
        service.record_validation(release_id, validation_receipts=_validation_receipts())
        service.record_approval(
            release_id=release_id,
            manifest_digest=prepare.manifest_digest,
            authority_receipt=_service_authority_receipt(release_id, prepare.manifest_digest),
        )

    idempotency_key = "historical-replay-after-replacement"
    first = service.promote_release_bundle(
        release_id="release-historical-replay-a",
        manifest_digest=manifests["release-historical-replay-a"],
        scopes=_scopes(0),
        idempotency_key=idempotency_key,
    )
    service.promote_release_bundle(
        release_id="release-historical-replay-b",
        manifest_digest=manifests["release-historical-replay-b"],
        scopes=_scopes(1),
        idempotency_key="historical-replacement",
    )

    replay = service.promote_release_bundle(
        release_id="release-historical-replay-a",
        manifest_digest=manifests["release-historical-replay-a"],
        scopes=_scopes(0),
        idempotency_key=idempotency_key,
    )

    assert replay == first
    assert service.show_release("release-historical-replay-a").state == "deprecated"
    assert service.show_release("release-historical-replay-b").state == "current"


def test_replayed_activation_receipt_rejects_missing_previous_release_after_replacement(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    for release_id in ("release-replayed-previous-a", "release-replayed-previous-b"):
        prepare = service.prepare_release(
            release_id=release_id,
            payload=_complete_payload(release_id),
            freeze=True,
        )
        service.record_validation(release_id, validation_receipts=_validation_receipts())
        service.record_approval(
            release_id=release_id,
            manifest_digest=prepare.manifest_digest,
            authority_receipt=_service_authority_receipt(release_id, prepare.manifest_digest),
        )
    service.promote_release_bundle(
        release_id="release-replayed-previous-a",
        scopes=_scopes(0),
        idempotency_key="replayed-previous-bootstrap",
    )
    idempotency_key = "replayed-previous-missing"
    first = service.promote_release_bundle(
        release_id="release-replayed-previous-b",
        scopes=_scopes(1),
        idempotency_key=idempotency_key,
    )
    malformed_receipt = deepcopy(first.details["repository_receipt"])
    for scope in malformed_receipt["scopes"]:
        scope["previous_release_id"] = None
    repository = service.repo
    original_list_events = repository.list_events
    target_event = next(
        event
        for event in original_list_events(
            release_id="release-replayed-previous-b",
            action="promote",
        )
        if event["idempotency_key"] == idempotency_key
    )

    def list_events(**kwargs):
        if kwargs.get("action") == "promote":
            replay_event = dict(target_event)
            replay_event["receipt"] = malformed_receipt
            return [replay_event]
        return original_list_events(**kwargs)

    monkeypatch.setattr(repository, "list_events", list_events)

    with pytest.raises(_release_control_error_type(service)):
        service.promote_release_bundle(
            release_id="release-replayed-previous-b",
            scopes=_scopes(1),
            idempotency_key=idempotency_key,
        )


@pytest.mark.parametrize(
    "field",
    [
        "outcome",
        "replayed",
        "outcome_replayed_pair",
        "scopes",
        "aliases",
        "blockers",
        "details",
    ],
)
def test_replayed_action_receipt_rejects_mutated_optional_fields(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    field: str,
) -> None:
    service = _service(tmp_path)
    release_id = "release-replayed-action-binding"
    service.prepare_release(
        release_id=release_id,
        payload=_complete_payload(release_id),
        freeze=True,
    )
    validation_receipts = _validation_receipts()
    first = service.record_validation(
        release_id,
        validation_receipts=validation_receipts,
        idempotency_key="validation-optional-fields",
    )
    malformed_receipt = first.model_dump(mode="json")
    if field == "outcome":
        malformed_receipt["outcome"] = "replayed"
    elif field == "replayed":
        malformed_receipt["replayed"] = True
    elif field == "outcome_replayed_pair":
        malformed_receipt["outcome"] = "replayed"
        malformed_receipt["replayed"] = True
    elif field == "scopes":
        malformed_receipt["scopes"] = [{"tampered": True}]
    elif field == "aliases":
        malformed_receipt["aliases"] = {"tampered": {}}
    elif field == "blockers":
        malformed_receipt["blockers"] = ["tampered"]
    elif field == "details":
        malformed_receipt["details"] = {"tampered": True}
    repository = service.repo
    original_list_events = repository.list_events
    request_sha256 = canonical_sha256(
        {
            "action": "validate",
            "release_id": release_id,
            "manifest_digest": first.manifest_digest,
            "validation_receipts": validation_receipts,
        }
    )

    def list_events(**kwargs):
        if kwargs.get("action") == "validate":
            return [
                {
                    "event_id": "replayed-action-event",
                    "idempotency_key": "validation-optional-fields",
                    "request_sha256": request_sha256,
                    "receipt": malformed_receipt,
                }
            ]
        return original_list_events(**kwargs)

    monkeypatch.setattr(repository, "list_events", list_events)

    with pytest.raises(_release_control_error_type(service)):
        service.record_validation(
            release_id,
            validation_receipts=validation_receipts,
            idempotency_key="validation-optional-fields",
        )


@pytest.mark.parametrize("field", ["blockers", "details"])
def test_lifecycle_append_rejects_stored_receipt_optional_field_mutation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    field: str,
) -> None:
    service = _service(tmp_path)
    release_id = "release-lifecycle-receipt-binding"
    service.prepare_release(
        release_id=release_id,
        payload=_complete_payload(release_id),
        freeze=True,
    )
    validation_receipts = _validation_receipts()
    repository = service.repo

    def append_event(**kwargs):
        stored_receipt = deepcopy(kwargs["receipt"])
        stored_receipt[field] = ["tampered"] if field == "blockers" else {"tampered": True}
        return {"receipt": stored_receipt, "replayed": False}

    monkeypatch.setattr(repository, "append_event", append_event)

    with pytest.raises(_release_control_error_type(service)):
        service.record_validation(
            release_id,
            validation_receipts=validation_receipts,
            idempotency_key=f"lifecycle-{field}",
        )


def test_activation_write_failure_rolls_back_aliases_events_and_states(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    release_a = _candidate_to_approved(repo, "release-write-failure-a")
    release_b = _candidate_to_approved(repo, "release-write-failure-b")
    scopes = _scopes(0)
    repo.activate_release(
        action="promote",
        target_environment="test",
        release_id=release_a.release_id,
        manifest_digest=release_a.manifest_digest,
        scope_expectations=scopes,
        idempotency_key="write-failure-bootstrap",
    )
    aliases_before = repo.list_aliases(target_environment="test")
    events_before = {
        release_id: repo.list_events(release_id=release_id)
        for release_id in (release_a.release_id, release_b.release_id)
    }

    def fail_after_partial_writes(stage: str, _context: dict[str, Any]) -> None:
        if stage == "before_receipt_event":
            raise OSError("simulated receipt persistence failure")

    with pytest.raises(OSError, match="simulated receipt persistence failure"):
        repo.activate_release(
            action="promote",
            target_environment="test",
            release_id=release_b.release_id,
            manifest_digest=release_b.manifest_digest,
            scope_expectations=_scopes(1),
            idempotency_key="write-failure-promote",
            fault_injector=fail_after_partial_writes,
        )

    assert repo.list_aliases(target_environment="test") == aliases_before
    assert {
        release_id: repo.list_events(release_id=release_id)
        for release_id in (release_a.release_id, release_b.release_id)
    } == events_before
    assert repo.get_manifest(release_a.release_id).state == "current"
    assert repo.get_manifest(release_b.release_id).state == "approved"

    receipt = repo.activate_release(
        action="promote",
        target_environment="test",
        release_id=release_b.release_id,
        manifest_digest=release_b.manifest_digest,
        scope_expectations=_scopes(1),
        idempotency_key="write-failure-promote",
    )
    assert receipt.status == "current"
