from __future__ import annotations

import inspect
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any, Protocol, cast, runtime_checkable

from pydantic import BaseModel, ValidationError

# isort: split
from backend.app.governance.release_approval import (
    ApprovalVerificationBlocked,
    ReleaseApprovalVerifier,
    ReleaseApprovalVerifierProtocol,
)
from backend.app.repositories.release_control_repo import (
    ReleaseControlError as RepositoryReleaseControlError,
)
from backend.app.schemas.release_approval import (
    ApprovalGateReceipt,
    AuthorityApprovalReceipt,
)
from backend.app.schemas.release_control import (
    ActionReceipt,
    ReleaseAlias,
    ReleaseManifest,
    ReleaseManifestPayload,
    ReleaseScope,
    ReleaseState,
    ReleaseView,
    ScopeExpectation,
    WholeBundleActivationRequest,
    canonical_sha256,
)


class ReleaseControlError(RuntimeError):
    """Base error whose message is safe for internal callers, not CLI output."""


class ReleaseInputError(ReleaseControlError):
    """The command payload is malformed or violates a bundle invariant."""


class ReleaseGateBlockedError(ReleaseControlError):
    """The requested transition is not allowed by the current release state."""

    def __init__(
        self,
        message: str,
        *,
        reason_codes: Sequence[str] = (),
        approval_gate_receipt: ApprovalGateReceipt | None = None,
    ) -> None:
        self.reason_codes = tuple(dict.fromkeys(str(code) for code in reason_codes if code))
        safe_message = message
        if self.reason_codes:
            safe_message = f"{message}: {', '.join(self.reason_codes)}"
        super().__init__(safe_message)
        self.approval_gate_receipt = approval_gate_receipt


class ReleaseConflictError(ReleaseControlError):
    """A digest, idempotency, or alias revision compare-and-swap conflicted."""


class ReleaseNotFoundError(ReleaseGateBlockedError):
    pass


@runtime_checkable
class ReleaseControlRepositoryProtocol(Protocol):
    def create_manifest(self, **kwargs: Any) -> Any: ...

    def get_manifest(self, release_id: str) -> Any | None: ...

    def append_event(self, **kwargs: Any) -> Any: ...

    def list_events(self, **kwargs: Any) -> Sequence[Any]: ...

    def get_alias(self, **kwargs: Any) -> Any | None: ...

    def activate_release(self, **kwargs: Any) -> Any: ...


_REPOSITORY_CONFLICT_NAMES = {
    "AliasRevisionConflictError",
    "AliasTargetConflictError",
    "IdempotencyConflictError",
    "ManifestConflictError",
    "ManifestDigestMismatchError",
}
_REPOSITORY_NOT_FOUND_NAMES = {"ManifestNotFoundError"}
_REPOSITORY_INPUT_NAMES = {"WholeBundleScopeError"}
_REPOSITORY_GATE_NAMES = {"ReleaseStateConflictError"}
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def _value(record: Any, name: str, default: Any = None) -> Any:
    if record is None:
        return default
    if isinstance(record, Mapping):
        return record.get(name, default)
    return getattr(record, name, default)


def _json_mapping(value: Any, *, field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ReleaseControlError(f"repository returned malformed {field_name}") from exc
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", exclude_none=True)
    if not isinstance(value, Mapping):
        raise ReleaseControlError(f"repository returned non-object {field_name}")
    return {str(key): item for key, item in value.items()}


def _plain(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", exclude_none=True)
    if is_dataclass(value):
        if isinstance(value, type):
            raise TypeError("asdict() should be called on dataclass instances")
        return _plain(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_plain(item) for item in value]
    if hasattr(value, "__table__"):
        return {column.name: _plain(getattr(value, column.name)) for column in value.__table__.columns}
    if hasattr(value, "__dict__"):
        return {str(key): _plain(item) for key, item in vars(value).items() if not str(key).startswith("_")}
    return value


def _call_with_supported_kwargs(method: Any, **kwargs: Any) -> Any:
    """Bridge the service to repository DTOs without coupling to ORM types."""

    signature = inspect.signature(method)
    if any(parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in signature.parameters.values()):
        return method(**kwargs)
    supported = {key: value for key, value in kwargs.items() if key in signature.parameters}
    return method(**supported)


class ReleaseControlService:
    """Internal whole-bundle release state machine.

    Candidate content is immutable. Lifecycle state is projected from the
    append-only event stream, while ``current`` is additionally projected from
    all Manifest scopes being active in their environment-scoped aliases.
    """

    def __init__(
        self,
        *,
        repo: ReleaseControlRepositoryProtocol,
        approval_verifier: ReleaseApprovalVerifierProtocol | None = None,
    ) -> None:
        self.repo = repo
        self.approval_verifier = approval_verifier or ReleaseApprovalVerifier()

    def prepare_release(
        self,
        *,
        release_id: str,
        payload: Mapping[str, Any] | ReleaseManifestPayload,
        freeze: bool = False,
        idempotency_key: str | None = None,
    ) -> ActionReceipt:
        if freeze is not True:
            raise ReleaseInputError("prepare only persists an explicitly frozen candidate; pass freeze=True")
        try:
            manifest = ReleaseManifest.model_validate({
                "release_id": release_id,
                "state": "candidate",
                "payload": payload,
            })
        except ValidationError as exc:
            raise ReleaseInputError("manifest is incomplete or internally inconsistent") from exc

        normalized_payload = manifest.payload.canonical_payload()
        digest = str(manifest.content_sha256)
        request_sha256 = canonical_sha256(
            {
                "action": "prepare",
                "release_id": release_id,
                "payload": normalized_payload,
            }
        )
        resolved_key = idempotency_key or f"prepare:{release_id}:{request_sha256}"

        existing = self.repo.get_manifest(release_id)
        replayed_manifest = existing is not None
        if existing is not None:
            existing_digest = str(_value(existing, "content_sha256") or "").upper()
            if existing_digest != digest:
                raise ReleaseConflictError("release_id already exists with a different manifest digest")
            prepare_events = _call_with_supported_kwargs(
                self.repo.list_events,
                release_id=release_id,
                action="prepare",
            )
            if prepare_events:
                prepare_event = prepare_events[0]
                stored_idempotency_key = _value(prepare_event, "idempotency_key")
                if not isinstance(stored_idempotency_key, str) or not stored_idempotency_key:
                    raise ReleaseControlError("repository prepare event envelope is invalid")
                self._require_replay_event_envelope(
                    prepare_event,
                    release_id=release_id,
                    action="prepare",
                    from_states={"draft"},
                    to_state="candidate",
                    manifest=manifest,
                    idempotency_key=stored_idempotency_key,
                    request_sha256=request_sha256,
                    context="prepare",
                )
                if _json_mapping(
                    _value(prepare_event, "event_payload"),
                    field_name="prepare event payload",
                ) != {"manifest_kind": "release_bundle"}:
                    raise ReleaseControlError("repository prepare event payload is invalid")
                return self._validated_action_receipt(
                    _value(prepare_event, "receipt"),
                    action="prepare",
                    release_id=release_id,
                    release_state="candidate",
                    manifest_digest=digest,
                    target_environment=manifest.target_environment,
                    idempotency_key=stored_idempotency_key,
                    context="prepare event",
                )
        else:
            try:
                existing = _call_with_supported_kwargs(
                    self.repo.create_manifest,
                    release_id=release_id,
                    state="candidate",
                    payload=normalized_payload,
                    target_environment=manifest.target_environment,
                    manifest_kind="release_bundle",
                )
            except RepositoryReleaseControlError as exc:
                self._raise_repository_error(exc)

        receipt = ActionReceipt(
            action="prepare",
            outcome="replayed" if replayed_manifest else "applied",
            release_id=release_id,
            release_state="candidate",
            manifest_digest=digest,
            target_environment=manifest.target_environment,
            idempotency_key=resolved_key,
            replayed=replayed_manifest,
        )
        return self._append_lifecycle_event(
            receipt=receipt,
            from_state="draft",
            to_state="candidate",
            request_sha256=request_sha256,
            event_payload={"manifest_kind": "release_bundle"},
        )

    def record_validation(
        self,
        release_id: str,
        validation_receipts: Mapping[str, Any] | None = None,
        *,
        receipt: Mapping[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> ActionReceipt:
        if validation_receipts is not None and receipt is not None:
            raise ReleaseInputError("pass either validation_receipts or receipt, not both")
        manifest, stored = self._require_manifest(release_id)
        receipts = dict(validation_receipts or receipt or {})
        request_sha256 = canonical_sha256(
            {
                "action": "validate",
                "release_id": release_id,
                "manifest_digest": manifest.content_sha256,
                "validation_receipts": receipts,
            }
        )
        resolved_key = idempotency_key or f"validate:{release_id}:{request_sha256}"
        validation_event_payload = {
            "validation_receipts": receipts,
            "failed_gates": [],
        }
        replay = self._find_event_replay(
            release_id=release_id,
            action="validate",
            idempotency_key=resolved_key,
            request_sha256=request_sha256,
            fallback_state="validated",
            manifest=manifest,
            expected_event_payload=validation_event_payload,
        )
        if replay is not None:
            return replay

        state = self._project_state(stored)
        if state != "candidate":
            raise ReleaseGateBlockedError(f"validate requires candidate state; current state is {state}")
        failed_gates = self._failed_validation_gates(
            receipts,
            required_gates=manifest.payload.required_validation_gates,
        )
        if failed_gates:
            raise ReleaseGateBlockedError("one or more validation gates did not pass")

        action_receipt = ActionReceipt(
            action="validate",
            outcome="applied",
            release_id=release_id,
            release_state="validated",
            manifest_digest=manifest.content_sha256,
            target_environment=manifest.target_environment,
            idempotency_key=resolved_key,
        )
        return self._append_lifecycle_event(
            receipt=action_receipt,
            from_state="candidate",
            to_state="validated",
            request_sha256=request_sha256,
            event_payload=validation_event_payload,
        )

    def validate_release(
        self,
        release_id: str,
        validation_receipts: Mapping[str, Any] | None = None,
        *,
        receipt: Mapping[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> ActionReceipt:
        return self.record_validation(
            release_id,
            validation_receipts,
            receipt=receipt,
            idempotency_key=idempotency_key,
        )

    def record_approval(
        self,
        *,
        release_id: str,
        manifest_digest: str,
        authority_receipt: Mapping[str, Any] | AuthorityApprovalReceipt | None = None,
        authority_reference: str | None = None,
        approved_by: str | None = None,
        approval_payload: Mapping[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> ActionReceipt:
        manifest, stored = self._require_manifest(release_id)
        normalized_digest = str(manifest_digest or "").strip().upper()
        if normalized_digest != manifest.content_sha256:
            raise ReleaseConflictError("approval digest does not match frozen manifest")

        raw_authority_receipt = authority_receipt
        if raw_authority_receipt is None and isinstance(approval_payload, Mapping):
            candidate = approval_payload.get("authority_receipt")
            if isinstance(candidate, (Mapping, AuthorityApprovalReceipt)):
                raw_authority_receipt = candidate
        parsed_authority_receipt = self._parse_authority_receipt(raw_authority_receipt)
        approval_gate = self._verify_record_approval(
            manifest=manifest,
            authority_receipt=parsed_authority_receipt,
        )
        event_payload = {
            "authority_reference": parsed_authority_receipt.authority_reference,
            "manifest_digest": normalized_digest,
            "authority_receipt": parsed_authority_receipt.model_dump(mode="json"),
            "approval_gate_receipt": approval_gate.model_dump(mode="json"),
        }
        request_sha256 = canonical_sha256(
            {
                "action": "approve-record",
                "release_id": release_id,
                "manifest_digest": normalized_digest,
                "authority_receipt_sha256": parsed_authority_receipt.receipt_sha256,
            }
        )
        resolved_key = idempotency_key or f"approve-record:{release_id}:{request_sha256}"
        replay = self._find_event_replay(
            release_id=release_id,
            action="approve-record",
            idempotency_key=resolved_key,
            request_sha256=request_sha256,
            fallback_state="approved",
            manifest=manifest,
            expected_event_payload=event_payload,
            authority_receipt=parsed_authority_receipt,
            expected_approval_gate=approval_gate,
        )
        if replay is not None:
            return replay

        state = self._project_state(stored)
        if state != "validated":
            raise ReleaseGateBlockedError(f"approval requires validated state; current state is {state}")
        receipt = ActionReceipt(
            action="approve-record",
            outcome="applied",
            release_id=release_id,
            release_state="approved",
            manifest_digest=manifest.content_sha256,
            target_environment=manifest.target_environment,
            idempotency_key=resolved_key,
        )
        return self._append_lifecycle_event(
            receipt=receipt,
            from_state="validated",
            to_state="approved",
            request_sha256=request_sha256,
            event_payload=event_payload,
        )

    def approve_release(self, **kwargs: Any) -> ActionReceipt:
        return self.record_approval(**kwargs)

    def promote_release(
        self,
        *,
        release_id: str,
        scope_expectations: Sequence[Mapping[str, Any] | ScopeExpectation],
        idempotency_key: str,
        target_environment: str | None = None,
        manifest_digest: str | None = None,
    ) -> ActionReceipt:
        return self._activate_whole_bundle(
            action="promote",
            release_id=release_id,
            scope_expectations=scope_expectations,
            idempotency_key=idempotency_key,
            target_environment=target_environment,
            manifest_digest=manifest_digest,
        )

    def promote_release_bundle(
        self,
        *,
        release_id: str,
        scopes: Sequence[Mapping[str, Any] | ScopeExpectation],
        idempotency_key: str,
        target_environment: str | None = None,
        manifest_digest: str | None = None,
    ) -> ActionReceipt:
        return self.promote_release(
            release_id=release_id,
            scope_expectations=scopes,
            idempotency_key=idempotency_key,
            target_environment=target_environment,
            manifest_digest=manifest_digest,
        )

    def rollback_release(
        self,
        *,
        release_id: str,
        scope_expectations: Sequence[Mapping[str, Any] | ScopeExpectation],
        idempotency_key: str,
        target_environment: str | None = None,
        manifest_digest: str | None = None,
        reason: str | None = None,
        mode: str | None = None,
    ) -> ActionReceipt:
        if not str(reason or "").strip():
            raise ReleaseInputError("rollback reason is required")
        if mode not in {"sealed_bundle_reactivate", "forward_rebuild"}:
            raise ReleaseInputError("rollback mode must be sealed_bundle_reactivate or forward_rebuild")
        return self._activate_whole_bundle(
            action="rollback",
            release_id=release_id,
            scope_expectations=scope_expectations,
            idempotency_key=idempotency_key,
            target_environment=target_environment,
            manifest_digest=manifest_digest,
            reason=str(reason).strip(),
            mode=mode,
        )

    def rollback_release_bundle(
        self,
        *,
        to_release_id: str,
        scopes: Sequence[Mapping[str, Any] | ScopeExpectation],
        reason: str,
        mode: str,
        idempotency_key: str,
        target_environment: str | None = None,
        manifest_digest: str | None = None,
    ) -> ActionReceipt:
        return self.rollback_release(
            release_id=to_release_id,
            scope_expectations=scopes,
            idempotency_key=idempotency_key,
            target_environment=target_environment,
            manifest_digest=manifest_digest,
            reason=reason,
            mode=mode,
        )

    def show_release(self, release_id: str) -> ReleaseView:
        manifest, stored = self._require_manifest(release_id)
        raw_events = list(
            _call_with_supported_kwargs(
                self.repo.list_events,
                release_id=release_id,
            )
        )
        aliases: list[dict[str, Any]] = []
        for scope in self._ordered_manifest_scopes(manifest.payload.scopes):
            alias = _call_with_supported_kwargs(
                self.repo.get_alias,
                target_environment=manifest.target_environment,
                scope_kind=scope.scope_kind,
                scope_key=scope.scope_key,
            )
            if alias is None:
                aliases.append(
                    {
                        "target_environment": manifest.target_environment,
                        "scope_kind": scope.scope_kind,
                        "scope_key": scope.scope_key,
                        "current_release_id": None,
                        "previous_release_id": None,
                        "revision": 0,
                        "alias_payload": {},
                    }
                )
            else:
                aliases.append(self._alias_view(alias, scope=scope))

        state = self._project_state(stored, events=raw_events, aliases=aliases)
        manifest_view = {
            "release_id": manifest.release_id,
            "state": "candidate",
            "target_environment": manifest.target_environment,
            "manifest_kind": str(_value(stored, "manifest_kind", "release_bundle")),
            "content_sha256": manifest.content_sha256,
            "payload": manifest.payload.canonical_payload(),
            "created_at": _plain(_value(stored, "created_at")),
        }
        return ReleaseView(
            release_id=release_id,
            state=state,
            manifest=manifest_view,
            events=[self._event_view(event) for event in raw_events],
            aliases=aliases,
        )

    def _activate_whole_bundle(
        self,
        *,
        action: str,
        release_id: str,
        scope_expectations: Sequence[Mapping[str, Any] | ScopeExpectation],
        idempotency_key: str,
        target_environment: str | None,
        manifest_digest: str | None,
        reason: str | None = None,
        mode: str | None = None,
    ) -> ActionReceipt:
        manifest, stored = self._require_manifest(release_id)
        resolved_environment = str(target_environment or manifest.target_environment).strip()
        if resolved_environment != manifest.target_environment:
            raise ReleaseInputError("target_environment must match the frozen manifest")
        resolved_digest = str(manifest_digest or manifest.content_sha256).strip().upper()
        if resolved_digest != manifest.content_sha256:
            raise ReleaseConflictError("activation digest does not match the frozen manifest")
        if not str(idempotency_key or "").strip():
            raise ReleaseInputError("idempotency_key is required for activation")

        try:
            expectations = [
                item if isinstance(item, ScopeExpectation) else ScopeExpectation(**item) for item in scope_expectations
            ]
            request = WholeBundleActivationRequest(
                release_id=release_id,
                target_environment=resolved_environment,
                manifest_digest=resolved_digest,
                scopes=expectations,
                idempotency_key=idempotency_key,
            )
        except (TypeError, ValidationError) as exc:
            raise ReleaseInputError("activation plan is malformed") from exc

        normalized_expectations = self._bind_expectations_to_manifest(
            manifest.payload,
            request.scopes,
        )
        replacement_transition = "deprecated" if action == "promote" else "rolled_back"
        operation_payload = {"reason": reason, "mode": mode} if action == "rollback" else {}
        activation_request_payload = {
            "action": action,
            "target_environment": resolved_environment,
            "release_id": release_id,
            "manifest_digest": resolved_digest,
            "target_transition": "current",
            "replacement_transition": replacement_transition,
            "operation_payload": operation_payload,
            "scope_expectations": normalized_expectations,
        }
        request_sha256 = canonical_sha256(activation_request_payload)
        approval_gate: ApprovalGateReceipt | None = None
        if action in {"promote", "rollback"}:
            approval_gate = self._verify_promotion_approval(manifest=manifest)
            replay = self._find_event_replay(
                release_id=release_id,
                action=action,
                event_action="reactivate" if action == "rollback" else None,
                idempotency_key=idempotency_key,
                request_sha256=request_sha256,
                fallback_state="current",
                manifest=manifest,
                scopes=normalized_expectations,
                operation_payload=operation_payload,
                replacement_transition=replacement_transition,
                expected_approval_gate=approval_gate,
                activation_request_payload=activation_request_payload,
            )
            if replay is not None:
                return replay
        release_events = list(
            _call_with_supported_kwargs(
                self.repo.list_events,
                release_id=release_id,
            )
        )
        state = self._project_state(stored, events=release_events)
        if action == "promote" and state != "approved":
            raise ReleaseGateBlockedError(f"{action} is not allowed from release state {state}")
        if action == "rollback":
            if mode == "forward_rebuild" and state != "approved":
                raise ReleaseGateBlockedError("forward_rebuild rollback requires an approved target release")
            if mode == "sealed_bundle_reactivate":
                was_current = any(str(_value(event, "to_state") or "") == "current" for event in release_events)
                if state not in {"deprecated", "rolled_back"} or not was_current:
                    raise ReleaseGateBlockedError(
                        "sealed_bundle_reactivate requires a previously current deprecated or rolled_back target"
                    )
        try:
            repository_receipt = _call_with_supported_kwargs(
                self.repo.activate_release,
                action=action,
                target_environment=resolved_environment,
                release_id=release_id,
                manifest_digest=resolved_digest,
                scope_expectations=normalized_expectations,
                idempotency_key=idempotency_key,
                request_sha256=request_sha256,
                target_transition="current",
                replacement_transition=replacement_transition,
                operation_payload=operation_payload,
                approval_gate_receipt=(approval_gate.model_dump(mode="json") if approval_gate is not None else None),
            )
        except RepositoryReleaseControlError as exc:
            self._raise_repository_error(exc)

        return self._activation_action_receipt(
            repository_receipt,
            action=action,
            release_id=release_id,
            manifest_digest=resolved_digest,
            target_environment=resolved_environment,
            idempotency_key=idempotency_key,
            request_sha256=request_sha256,
            scopes=normalized_expectations,
            operation_payload=operation_payload,
            replacement_transition=replacement_transition,
            approval_registry_sha256=manifest.payload.approval_registry_sha256,
            committed_approval_gate=approval_gate,
            current_approval_gate=approval_gate,
            activation_request_payload=activation_request_payload,
            committed_target_event_id=None,
        )

    @staticmethod
    def _parse_authority_receipt(
        value: Mapping[str, Any] | AuthorityApprovalReceipt | None,
    ) -> AuthorityApprovalReceipt:
        if value is None:
            raise ReleaseGateBlockedError(
                "approval requires a structured authority receipt; identity and free-text references are not authority"
            )
        try:
            return AuthorityApprovalReceipt.model_validate(value)
        except ValidationError:
            raise ReleaseGateBlockedError("authority approval receipt is invalid") from None

    def _verify_record_approval(
        self,
        *,
        manifest: ReleaseManifest,
        authority_receipt: AuthorityApprovalReceipt,
    ) -> ApprovalGateReceipt:
        try:
            gate = self.approval_verifier.verify_record_approval(
                release_id=manifest.release_id,
                manifest_sha256=str(manifest.content_sha256),
                manifest_payload=manifest.payload,
                authority_receipt=authority_receipt,
            )
        except ApprovalVerificationBlocked as exc:
            raise ReleaseGateBlockedError(
                "release approval evidence gate blocked",
                reason_codes=exc.receipt.reason_codes,
                approval_gate_receipt=exc.receipt,
            ) from exc
        return self._require_passed_approval_gate(
            gate,
            manifest=manifest,
            authority_receipt=authority_receipt,
        )

    def _verify_promotion_approval(
        self,
        *,
        manifest: ReleaseManifest,
    ) -> ApprovalGateReceipt:
        approval_events = list(
            _call_with_supported_kwargs(
                self.repo.list_events,
                release_id=manifest.release_id,
                action="approve-record",
            )
        )
        if not approval_events:
            raise ReleaseGateBlockedError("promotion requires a persisted approval receipt")
        event_payload = _value(approval_events[-1], "event_payload")
        if event_payload is None:
            event_payload = _value(approval_events[-1], "payload")
        payload = _json_mapping(event_payload, field_name="approval event payload")
        raw_authority_receipt = payload.get("authority_receipt")
        parsed_authority_receipt = self._parse_authority_receipt(
            raw_authority_receipt if isinstance(raw_authority_receipt, Mapping) else None
        )
        try:
            gate = self.approval_verifier.verify_promotion(
                release_id=manifest.release_id,
                manifest_sha256=str(manifest.content_sha256),
                manifest_payload=manifest.payload,
                authority_receipt=parsed_authority_receipt,
            )
        except ApprovalVerificationBlocked as exc:
            raise ReleaseGateBlockedError(
                "release approval evidence gate blocked",
                reason_codes=exc.receipt.reason_codes,
                approval_gate_receipt=exc.receipt,
            ) from exc
        return self._require_passed_approval_gate(
            gate,
            manifest=manifest,
            authority_receipt=parsed_authority_receipt,
        )

    @staticmethod
    def _require_passed_approval_gate(
        value: Mapping[str, Any] | ApprovalGateReceipt,
        *,
        manifest: ReleaseManifest,
        authority_receipt: AuthorityApprovalReceipt,
    ) -> ApprovalGateReceipt:
        try:
            gate = ApprovalGateReceipt.model_validate(value)
        except ValidationError:
            raise ReleaseGateBlockedError("approval verifier returned an invalid gate receipt") from None
        if gate.status != "passed":
            raise ReleaseGateBlockedError(
                "approval verifier did not pass the release",
                reason_codes=gate.reason_codes,
                approval_gate_receipt=gate,
            )
        if gate.release_id != manifest.release_id or gate.manifest_sha256 != manifest.content_sha256:
            raise ReleaseGateBlockedError("approval verifier receipt does not bind the frozen manifest")
        if gate.registry_sha256 != manifest.payload.approval_registry_sha256:
            raise ReleaseGateBlockedError("approval verifier receipt does not bind the manifest registry")
        if (
            authority_receipt.release_id != manifest.release_id
            or authority_receipt.manifest_sha256 != manifest.content_sha256
            or authority_receipt.registry_sha256 != manifest.payload.approval_registry_sha256
            or authority_receipt.decision != "approved"
            or authority_receipt.revoked_at is not None
            or gate.authority_receipt_sha256 != authority_receipt.receipt_sha256
            or gate.checked_at < authority_receipt.decided_at
            or (
                authority_receipt.expires_at is not None
                and gate.checked_at >= authority_receipt.expires_at
            )
        ):
            raise ReleaseGateBlockedError("approval verifier receipt does not bind current authority")
        authority_subjects = {
            subject.approval_id: subject for subject in authority_receipt.subjects
        }
        gate_subjects = {subject.approval_id: subject for subject in gate.subjects}
        if (
            len(gate_subjects) != len(gate.subjects)
            or set(gate_subjects) != set(authority_subjects)
        ):
            raise ReleaseGateBlockedError("approval verifier receipt does not cover authority subjects")
        for approval_id, authority_subject in authority_subjects.items():
            gate_subject = gate_subjects[approval_id]
            if (
                gate_subject.subject_kind != authority_subject.subject_kind
                or gate_subject.subject_key != authority_subject.subject_key
                or gate_subject.states != authority_subject.states
                or gate_subject.evidence_receipt_sha256
                != authority_subject.evidence_receipt_sha256
            ):
                raise ReleaseGateBlockedError(
                    f"approval verifier receipt subject is not bound to authority: {approval_id}"
                )
        return gate

    def _require_manifest(self, release_id: str) -> tuple[ReleaseManifest, Any]:
        stored = self.repo.get_manifest(release_id)
        if stored is None:
            raise ReleaseNotFoundError("release manifest was not found")
        payload = _value(stored, "payload")
        if payload is None:
            payload = _value(stored, "payload_json")
        try:
            payload_mapping = _json_mapping(payload, field_name="manifest payload")
            manifest = ReleaseManifest.model_validate({
                "release_id": str(_value(stored, "release_id", release_id)),
                "state": "candidate",
                "payload": payload_mapping,
                "content_sha256": str(_value(stored, "content_sha256") or ""),
            })
        except ValidationError as exc:
            raise ReleaseControlError("stored release manifest is invalid") from exc
        return manifest, stored

    def _project_state(
        self,
        stored_manifest: Any,
        *,
        events: Sequence[Any] | None = None,
        aliases: Sequence[Mapping[str, Any]] | None = None,
    ) -> ReleaseState:
        release_id = str(_value(stored_manifest, "release_id") or "")
        raw_events = list(
            events
            if events is not None
            else _call_with_supported_kwargs(
                self.repo.list_events,
                release_id=release_id,
            )
        )
        state: ReleaseState = "candidate"
        for event in raw_events:
            to_state = str(_value(event, "to_state") or "")
            if to_state in {
                "candidate",
                "validated",
                "approved",
                "current",
                "deprecated",
                "rejected",
                "rolled_back",
            }:
                state = to_state  # type: ignore[assignment]

        if aliases and all(str(alias.get("current_release_id") or "") == release_id for alias in aliases):
            return "current"
        return state

    def _append_lifecycle_event(
        self,
        *,
        receipt: ActionReceipt,
        from_state: ReleaseState | None,
        to_state: ReleaseState,
        request_sha256: str,
        event_payload: Mapping[str, Any],
    ) -> ActionReceipt:
        try:
            stored_event = _call_with_supported_kwargs(
                self.repo.append_event,
                release_id=receipt.release_id,
                action=receipt.action,
                from_state=from_state,
                to_state=to_state,
                manifest_sha256=receipt.manifest_digest,
                target_environment=receipt.target_environment,
                scope_kind=None,
                scope_key=None,
                event_payload=dict(event_payload),
                idempotency_key=receipt.idempotency_key,
                request_sha256=request_sha256,
                receipt=receipt.model_dump(mode="json", exclude_none=True),
            )
        except RepositoryReleaseControlError as exc:
            self._raise_repository_error(exc)

        persisted_receipt = _value(stored_event, "receipt")
        stored_receipt = self._validated_action_receipt(
            persisted_receipt,
            action=receipt.action,
            release_id=receipt.release_id_or_empty,
            release_state=to_state,
            manifest_digest=receipt.manifest_digest or "",
            target_environment=receipt.target_environment or "",
            idempotency_key=receipt.idempotency_key or "",
            context="lifecycle event",
        )
        if stored_receipt != receipt:
            raise ReleaseControlError("repository lifecycle receipt differs from the committed event")
        return stored_receipt

    def _find_event_replay(
        self,
        *,
        release_id: str,
        action: str,
        event_action: str | None = None,
        idempotency_key: str,
        request_sha256: str,
        fallback_state: ReleaseState,
        manifest: ReleaseManifest,
        scopes: Sequence[Mapping[str, Any]] | None = None,
        operation_payload: Mapping[str, Any] | None = None,
        replacement_transition: str | None = None,
        expected_approval_gate: ApprovalGateReceipt | None = None,
        expected_event_payload: Mapping[str, Any] | None = None,
        authority_receipt: AuthorityApprovalReceipt | None = None,
        activation_request_payload: Mapping[str, Any] | None = None,
    ) -> ActionReceipt | None:
        events = _call_with_supported_kwargs(
            self.repo.list_events,
            release_id=release_id,
            action=event_action or action,
        )
        for event in events:
            stored_idempotency_key = _value(event, "idempotency_key")
            if stored_idempotency_key is not None and not isinstance(
                stored_idempotency_key, str
            ):
                raise ReleaseControlError("repository idempotency event envelope is invalid")
            if stored_idempotency_key != idempotency_key:
                continue
            previous_request = _value(event, "request_sha256")
            if not isinstance(previous_request, str) or not previous_request:
                raise ReleaseControlError("repository idempotency event has no request digest")
            if previous_request != request_sha256:
                raise ReleaseConflictError("idempotency_key was already used for a different request")
            persisted_receipt = _value(event, "receipt")
            if action in {"promote", "rollback"}:
                expected_event_action = event_action or action
                allowed_from_states = (
                    {"approved"}
                    if action == "promote" or (operation_payload or {}).get("mode") == "forward_rebuild"
                    else {"deprecated", "rolled_back"}
                )
                event_id = self._require_replay_event_envelope(
                    event,
                    release_id=release_id,
                    action=expected_event_action,
                    from_states=allowed_from_states,
                    to_state="current",
                    manifest=manifest,
                    idempotency_key=idempotency_key,
                    request_sha256=request_sha256,
                    context="activation",
                )
                event_payload = _json_mapping(
                    _value(event, "event_payload"),
                    field_name="activation event payload",
                )
                activation_event_fields = {
                    "request",
                    "computed_request_sha256",
                    "operation_payload",
                    "approval_gate_receipt",
                }
                if (
                    activation_request_payload is None
                    or set(event_payload) != activation_event_fields
                    or event_payload.get("request") != dict(activation_request_payload)
                    or event_payload.get("computed_request_sha256")
                    != canonical_sha256(event_payload.get("request"))
                    or event_payload.get("computed_request_sha256") != request_sha256
                    or event_payload.get("operation_payload") != dict(operation_payload or {})
                ):
                    raise ReleaseControlError("repository activation event is not bound to this request")
                return self._activation_action_receipt(
                    persisted_receipt,
                    action=action,
                    release_id=release_id,
                    manifest_digest=cast(str, manifest.content_sha256),
                    target_environment=manifest.target_environment,
                    idempotency_key=idempotency_key,
                    request_sha256=request_sha256,
                    scopes=scopes or (),
                    operation_payload=operation_payload or {},
                    replacement_transition=replacement_transition or "",
                    approval_registry_sha256=manifest.payload.approval_registry_sha256,
                    committed_approval_gate=event_payload.get("approval_gate_receipt"),
                    current_approval_gate=expected_approval_gate,
                    activation_request_payload=activation_request_payload,
                    committed_target_event_id=event_id,
                )
            lifecycle_transitions: dict[str, tuple[set[str], ReleaseState]] = {
                "prepare": ({"draft"}, "candidate"),
                "validate": ({"candidate"}, "validated"),
                "approve-record": ({"validated"}, "approved"),
            }
            transition = lifecycle_transitions.get(action)
            if transition is None:
                raise ReleaseControlError(f"unsupported lifecycle replay action: {action}")
            self._require_replay_event_envelope(
                event,
                release_id=release_id,
                action=event_action or action,
                from_states=transition[0],
                to_state=transition[1],
                manifest=manifest,
                idempotency_key=idempotency_key,
                request_sha256=request_sha256,
                context=action,
            )
            stored_event_payload = _json_mapping(
                _value(event, "event_payload"),
                field_name=f"{action} event payload",
            )
            if action == "approve-record":
                expected_fields = {
                    "authority_reference",
                    "manifest_digest",
                    "authority_receipt",
                    "approval_gate_receipt",
                }
                if (
                    set(stored_event_payload) != expected_fields
                    or authority_receipt is None
                    or expected_approval_gate is None
                ):
                    raise ReleaseControlError("repository approval event payload is incomplete")
                try:
                    stored_authority = AuthorityApprovalReceipt.model_validate(
                        stored_event_payload.get("authority_receipt")
                    )
                    stored_gate = ApprovalGateReceipt.model_validate(
                        stored_event_payload.get("approval_gate_receipt")
                    )
                except ValidationError as exc:
                    raise ReleaseControlError("repository approval event payload is invalid") from exc
                if (
                    stored_authority != authority_receipt
                    or stored_event_payload.get("authority_reference")
                    != authority_receipt.authority_reference
                    or stored_event_payload.get("manifest_digest") != manifest.content_sha256
                ):
                    raise ReleaseControlError("repository approval event is not bound to this request")
                self._require_passed_approval_gate(
                    stored_gate,
                    manifest=manifest,
                    authority_receipt=stored_authority,
                )
                if (
                    stored_gate.authority_receipt_sha256
                    != expected_approval_gate.authority_receipt_sha256
                    or stored_gate.subjects != expected_approval_gate.subjects
                ):
                    raise ReleaseControlError("repository approval event differs from current authority")
            elif expected_event_payload is None or stored_event_payload != dict(
                expected_event_payload
            ):
                raise ReleaseControlError(f"repository {action} event payload is invalid")
            return self._validated_action_receipt(
                persisted_receipt,
                action=action,
                release_id=release_id,
                release_state=fallback_state,
                manifest_digest=cast(str, manifest.content_sha256),
                target_environment=manifest.target_environment,
                idempotency_key=idempotency_key,
                context="idempotency event",
            )
        return None

    @staticmethod
    def _require_replay_event_envelope(
        event: Any,
        *,
        release_id: str,
        action: str,
        from_states: set[str],
        to_state: ReleaseState,
        manifest: ReleaseManifest,
        idempotency_key: str,
        request_sha256: str,
        context: str,
    ) -> str:
        event_id = _value(event, "event_id")
        expected_strings = {
            "release_id": release_id,
            "action": action,
            "to_state": to_state,
            "manifest_sha256": manifest.content_sha256,
            "target_environment": manifest.target_environment,
            "idempotency_key": idempotency_key,
            "request_sha256": request_sha256,
        }
        if (
            not isinstance(event_id, str)
            or not event_id
            or any(
                not isinstance(_value(event, field), str)
                or _value(event, field) != expected
                for field, expected in expected_strings.items()
            )
            or not isinstance(_value(event, "from_state"), str)
            or _value(event, "from_state") not in from_states
            or _value(event, "scope_kind") is not None
            or _value(event, "scope_key") is not None
        ):
            raise ReleaseControlError(
                f"repository {context} event envelope is not bound to this request"
            )
        return event_id

    @staticmethod
    def _validated_action_receipt(
        value: Any,
        *,
        action: str,
        release_id: str,
        release_state: ReleaseState,
        manifest_digest: str,
        target_environment: str,
        idempotency_key: str,
        context: str,
    ) -> ActionReceipt:
        try:
            receipt = ActionReceipt.model_validate(value)
        except ValidationError as exc:
            raise ReleaseControlError(f"repository returned an invalid {context} receipt") from exc
        expected = {
            "action": action,
            "release_id": release_id,
            "release_state": release_state,
            "manifest_digest": manifest_digest,
            "target_environment": target_environment,
            "idempotency_key": idempotency_key,
        }
        expected_replayed = receipt.outcome == "replayed"
        outcome_is_allowed = (
            receipt.outcome in {"applied", "replayed"}
            if action == "prepare"
            else receipt.outcome == "applied"
        )
        if (
            not outcome_is_allowed
            or receipt.replayed is not expected_replayed
            or receipt.scopes
            or receipt.aliases
            or receipt.blockers
            or receipt.details
            or any(
                getattr(receipt, field) != expected_value
                for field, expected_value in expected.items()
            )
        ):
            raise ReleaseControlError(f"repository {context} receipt is not bound to this request")
        return receipt

    def _activation_action_receipt(
        self,
        repository_receipt: Any,
        *,
        action: str,
        release_id: str,
        manifest_digest: str,
        target_environment: str,
        idempotency_key: str,
        request_sha256: str,
        scopes: Sequence[Mapping[str, Any]],
        operation_payload: Mapping[str, Any],
        replacement_transition: str,
        approval_registry_sha256: str,
        committed_approval_gate: Mapping[str, Any] | ApprovalGateReceipt | None,
        current_approval_gate: ApprovalGateReceipt | None,
        activation_request_payload: Mapping[str, Any],
        committed_target_event_id: str | None,
    ) -> ActionReceipt:
        repository_view = _plain(repository_receipt)
        if not isinstance(repository_view, Mapping):
            raise ReleaseControlError("repository returned a malformed activation receipt")
        expected_header = {
            "action": action,
            "release_id": release_id,
            "manifest_digest": manifest_digest,
            "target_environment": target_environment,
            "idempotency_key": idempotency_key,
            "request_sha256": request_sha256,
            "status": "current",
        }
        if any(
            not isinstance(repository_view.get(field), str)
            or repository_view[field] != value
            for field, value in expected_header.items()
        ):
            raise ReleaseControlError("repository activation receipt is not bound to this request")
        expected_receipt_fields = {
            "action",
            "release_id",
            "manifest_digest",
            "target_environment",
            "idempotency_key",
            "request_sha256",
            "status",
            "operation_payload",
            "approval_gate_receipt",
            "scopes",
            "events",
        }
        if set(repository_view) != expected_receipt_fields:
            raise ReleaseControlError("repository activation receipt has unexpected or missing fields")
        if repository_view.get("operation_payload") != dict(operation_payload):
            raise ReleaseControlError("repository activation receipt operation is not bound to this request")
        try:
            stored_approval_gate = ApprovalGateReceipt.model_validate(
                repository_view.get("approval_gate_receipt")
            )
            committed_gate = ApprovalGateReceipt.model_validate(committed_approval_gate)
        except ValidationError as exc:
            raise ReleaseControlError("repository activation receipt has an invalid approval gate") from exc
        if (
            stored_approval_gate.status != "passed"
            or stored_approval_gate.release_id != release_id
            or stored_approval_gate.manifest_sha256 != manifest_digest
            or stored_approval_gate.registry_sha256 != approval_registry_sha256
        ):
            raise ReleaseControlError("repository activation approval gate is not bound to this request")
        if (
            stored_approval_gate != committed_gate
            or current_approval_gate is None
            or stored_approval_gate.authority_receipt_sha256
            != current_approval_gate.authority_receipt_sha256
            or stored_approval_gate.subjects != current_approval_gate.subjects
        ):
            raise ReleaseControlError("repository activation approval gate differs from current authority")
        raw_scopes = repository_view.get("scopes")
        if not isinstance(raw_scopes, list) or not raw_scopes:
            raise ReleaseControlError("repository activation receipt has invalid scopes")
        expected_scopes = {
            (str(scope.get("scope_kind") or ""), str(scope.get("scope_key") or "")): scope
            for scope in scopes
        }
        aliases: dict[str, ReleaseAlias] = {}
        seen_scopes: set[tuple[str, str]] = set()
        previous_release_ids: set[str] = set()
        scope_timestamps: set[datetime] = set()
        scope_views: list[dict[str, Any]] = []
        for raw_scope in raw_scopes:
            if not isinstance(raw_scope, Mapping):
                raise ReleaseControlError("repository activation receipt has a non-object scope")
            scope = dict(raw_scope)
            expected_scope_fields = {
                "target_environment",
                "scope_kind",
                "scope_key",
                "previous_release_id",
                "current_release_id",
                "previous_revision",
                "revision",
                "alias_payload",
                "updated_at",
            }
            if set(scope) != expected_scope_fields:
                raise ReleaseControlError("repository activation receipt scope has unexpected or missing fields")
            if (
                any(
                    not isinstance(scope.get(field), str) or not scope[field]
                    for field in (
                        "target_environment",
                        "scope_kind",
                        "scope_key",
                        "current_release_id",
                        "updated_at",
                    )
                )
                or (
                    scope["previous_release_id"] is not None
                    and (
                        not isinstance(scope["previous_release_id"], str)
                        or not scope["previous_release_id"]
                    )
                )
                or not isinstance(scope.get("alias_payload"), Mapping)
            ):
                raise ReleaseControlError("repository activation receipt scope has invalid field types")
            scope_views.append(scope)
            scope_kind = scope["scope_kind"]
            scope_key = scope["scope_key"]
            identity = (scope_kind, scope_key)
            expected_scope = expected_scopes.get(identity)
            if expected_scope is None or identity in seen_scopes:
                raise ReleaseControlError("repository activation receipt has unexpected or duplicate scopes")
            expected_revision = int(expected_scope.get("expected_revision", -1))
            if (
                type(scope.get("previous_revision")) is not int
                or scope["previous_revision"] != expected_revision
                or type(scope.get("revision")) is not int
                or not isinstance(scope.get("updated_at"), str)
            ):
                raise ReleaseControlError("repository activation receipt scope revision is invalid")
            try:
                updated_at = datetime.fromisoformat(scope["updated_at"].replace("Z", "+00:00"))
            except ValueError as exc:
                raise ReleaseControlError("repository activation receipt scope timestamp is invalid") from exc
            if updated_at.tzinfo is None or updated_at.utcoffset() is None:
                raise ReleaseControlError("repository activation receipt scope timestamp is invalid")
            scope_timestamps.add(updated_at)
            try:
                alias = ReleaseAlias(
                    target_environment=scope["target_environment"],
                    scope_kind=scope_kind,
                    scope_key=scope_key,
                    current_release_id=scope["current_release_id"],
                    previous_release_id=scope.get("previous_release_id"),
                    revision=int(scope.get("revision", -1)),
                    alias_payload=dict(scope["alias_payload"]),
                )
            except (TypeError, ValueError, ValidationError) as exc:
                raise ReleaseControlError("repository activation receipt has an invalid scope") from exc
            if (
                alias.target_environment != target_environment
                or alias.current_release_id != release_id
                or alias.revision != expected_revision + 1
                or alias.alias_payload != dict(expected_scope.get("alias_payload") or {})
            ):
                raise ReleaseControlError("repository activation receipt scope is not bound to this request")
            if alias.previous_release_id == release_id:
                raise ReleaseControlError("repository activation receipt scope has an invalid previous release")
            if (expected_revision == 0) != (alias.previous_release_id is None):
                raise ReleaseControlError("repository activation receipt previous release is inconsistent")
            if alias.previous_release_id is not None:
                previous_release_ids.add(alias.previous_release_id)
            aliases[f"{scope_kind}:{scope_key}"] = alias
            seen_scopes.add(identity)
        if set(expected_scopes) != seen_scopes:
            raise ReleaseControlError("repository activation receipt does not cover the requested scopes")
        if len(scope_timestamps) != 1:
            raise ReleaseControlError("repository activation receipt scopes have inconsistent timestamps")
        activated_at = next(iter(scope_timestamps))
        raw_events = repository_view.get("events")
        if not isinstance(raw_events, list):
            raise ReleaseControlError("repository activation receipt has invalid events")
        event_fields = {"event_id", "release_id", "action", "from_state", "to_state"}
        event_views: list[dict[str, str]] = []
        for raw_event in raw_events:
            if not isinstance(raw_event, Mapping) or set(raw_event) != event_fields:
                raise ReleaseControlError("repository activation receipt has an invalid event")
            if any(
                not isinstance(raw_event.get(field), str) or not raw_event[field]
                for field in event_fields
            ):
                raise ReleaseControlError("repository activation receipt has an invalid event")
            event = {field: raw_event[field] for field in event_fields}
            event_views.append(event)
        if len({event["event_id"] for event in event_views}) != len(event_views):
            raise ReleaseControlError("repository activation receipt repeats an event")
        target_action = "promote" if action == "promote" else "reactivate"
        target_events = [
            event
            for event in event_views
            if event["release_id"] == release_id and event["action"] == target_action
        ]
        allowed_target_from = (
            {"approved"}
            if action == "promote" or operation_payload.get("mode") == "forward_rebuild"
            else {"deprecated", "rolled_back"}
        )
        if (
            len(target_events) != 1
            or target_events[0]["from_state"] not in allowed_target_from
            or target_events[0]["to_state"] != "current"
            or (
                committed_target_event_id is not None
                and target_events[0]["event_id"] != committed_target_event_id
            )
        ):
            raise ReleaseControlError("repository activation receipt has an invalid target event")
        replacement_action = "supersede" if action == "promote" else "rollback"
        replacement_events = [event for event in event_views if event is not target_events[0]]
        if (
            len(replacement_events) != len(previous_release_ids)
            or {event["release_id"] for event in replacement_events} != previous_release_ids
            or any(
                event["action"] != replacement_action
                or event["from_state"] != "current"
                or event["to_state"] != replacement_transition
                for event in replacement_events
            )
        ):
            raise ReleaseControlError("repository activation receipt has invalid replacement events")
        for event in event_views:
            try:
                persisted_events = _call_with_supported_kwargs(
                    self.repo.list_events,
                    release_id=event["release_id"],
                    action=event["action"],
                )
            except RepositoryReleaseControlError as exc:
                self._raise_repository_error(exc)
            matching_events = [
                stored_event
                for stored_event in persisted_events
                if _value(stored_event, "event_id") == event["event_id"]
            ]
            if len(matching_events) != 1 or any(
                not isinstance(_value(matching_events[0], field), str)
                or _value(matching_events[0], field) != event[field]
                for field in ("release_id", "action", "from_state", "to_state")
            ):
                raise ReleaseControlError("repository activation receipt differs from the stored event")
            stored_event = matching_events[0]
            is_target_event = event is target_events[0]
            expected_event_manifest = manifest_digest
            if not is_target_event:
                try:
                    replaced_manifest = self.repo.get_manifest(event["release_id"])
                except RepositoryReleaseControlError as exc:
                    self._raise_repository_error(exc)
                expected_event_manifest = _value(replaced_manifest, "content_sha256")
            if (
                not isinstance(expected_event_manifest, str)
                or not _SHA256_RE.fullmatch(expected_event_manifest)
                or not isinstance(_value(stored_event, "manifest_sha256"), str)
                or _value(stored_event, "manifest_sha256") != expected_event_manifest
                or not isinstance(_value(stored_event, "target_environment"), str)
                or _value(stored_event, "target_environment") != target_environment
                or _value(stored_event, "scope_kind") is not None
                or _value(stored_event, "scope_key") is not None
                or (
                    not isinstance(_value(stored_event, "idempotency_key"), str)
                    or _value(stored_event, "idempotency_key") != idempotency_key
                    if is_target_event
                    else _value(stored_event, "idempotency_key") is not None
                )
                or (
                    not isinstance(_value(stored_event, "request_sha256"), str)
                    or _value(stored_event, "request_sha256") != request_sha256
                    if is_target_event
                    else _value(stored_event, "request_sha256") is not None
                )
                or (
                    _plain(_value(stored_event, "receipt")) != dict(repository_view)
                    if is_target_event
                    else _value(stored_event, "receipt") is not None
                )
            ):
                raise ReleaseControlError("repository activation receipt event envelope is invalid")
            stored_occurred_at = _value(stored_event, "occurred_at")
            if isinstance(stored_occurred_at, str):
                try:
                    stored_occurred_at = datetime.fromisoformat(
                        stored_occurred_at.replace("Z", "+00:00")
                    )
                except ValueError as exc:
                    raise ReleaseControlError(
                        "repository activation event timestamp is invalid"
                    ) from exc
            if (
                isinstance(stored_occurred_at, datetime)
                and stored_occurred_at.tzinfo is None
                and str(
                    getattr(
                        getattr(getattr(self.repo, "engine", None), "dialect", None),
                        "name",
                        "",
                    )
                )
                == "sqlite"
            ):
                stored_occurred_at = stored_occurred_at.replace(
                    tzinfo=activated_at.tzinfo
                )
            if (
                not isinstance(stored_occurred_at, datetime)
                or stored_occurred_at.tzinfo is None
                or stored_occurred_at.utcoffset() is None
                or stored_occurred_at != activated_at
            ):
                raise ReleaseControlError("repository activation event timestamp is inconsistent")
            stored_event_payload = _json_mapping(
                _value(stored_event, "event_payload"),
                field_name="stored activation event payload",
            )
            if is_target_event:
                expected_target_payload = {
                    "request": dict(activation_request_payload),
                    "computed_request_sha256": request_sha256,
                    "operation_payload": dict(operation_payload),
                    "approval_gate_receipt": committed_gate.model_dump(mode="json"),
                }
                if stored_event_payload != expected_target_payload:
                    raise ReleaseControlError("repository activation target event payload is invalid")
                continue
            expected_replacement_scopes = [
                {
                    "scope_kind": scope["scope_kind"],
                    "scope_key": scope["scope_key"],
                    "revision": scope["revision"],
                }
                for scope in scope_views
                if scope["previous_release_id"] == event["release_id"]
            ]
            expected_replacement_payload = {
                "activated_release_id": release_id,
                "activation_action": action,
                "operation_payload": dict(operation_payload),
                "scopes": expected_replacement_scopes,
            }
            if stored_event_payload != expected_replacement_payload:
                raise ReleaseControlError("repository activation replacement event payload is invalid")
        details: dict[str, Any] = {"repository_receipt": dict(repository_view)}
        approval_gate_receipt = repository_view.get("approval_gate_receipt")
        if isinstance(approval_gate_receipt, Mapping):
            details["approval_gate_receipt"] = dict(approval_gate_receipt)
        return ActionReceipt(
            action=repository_view["action"],
            outcome="applied",
            release_id=repository_view["release_id"],
            release_state="current",
            manifest_digest=repository_view["manifest_digest"],
            target_environment=repository_view["target_environment"],
            idempotency_key=repository_view["idempotency_key"],
            scopes=scope_views,
            aliases=aliases,
            details=details,
        )

    def _bind_expectations_to_manifest(
        self,
        payload: ReleaseManifestPayload,
        expectations: Sequence[ScopeExpectation],
    ) -> list[dict[str, Any]]:
        expected_by_identity = {
            (expectation.scope_kind, expectation.scope_key): expectation for expectation in expectations
        }
        manifest_by_identity = {(scope.scope_kind, scope.scope_key): scope for scope in payload.scopes}
        if set(expected_by_identity) != set(manifest_by_identity):
            raise ReleaseInputError("activation expectations must cover the complete frozen scope plan")

        normalized: list[dict[str, Any]] = []
        for scope in self._ordered_manifest_scopes(payload.scopes):
            expectation = expected_by_identity[(scope.scope_kind, scope.scope_key)]
            if expectation.alias_payload and expectation.alias_payload != scope.alias_payload:
                raise ReleaseConflictError("activation alias_payload differs from the approved manifest")
            normalized.append(
                {
                    "scope_kind": scope.scope_kind,
                    "scope_key": scope.scope_key,
                    "expected_revision": expectation.expected_revision,
                    "alias_payload": dict(scope.alias_payload),
                }
            )
        return normalized

    @staticmethod
    def _ordered_manifest_scopes(
        scopes: Sequence[ReleaseScope],
    ) -> list[ReleaseScope]:
        return sorted(
            scopes,
            key=lambda scope: (
                0 if scope.scope_kind == "physical_bundle" else 1,
                scope.scope_key,
            ),
        )

    @staticmethod
    def _failed_validation_gates(
        receipts: Mapping[str, Any],
        *,
        required_gates: Sequence[str],
    ) -> list[str]:
        failed: list[str] = []
        required_gate_set = set(required_gates)
        receipt_gate_set = set(receipts)
        for gate in sorted(required_gate_set - receipt_gate_set):
            failed.append(gate)
        for gate in sorted(receipt_gate_set - required_gate_set, key=str):
            failed.append(f"unexpected:{gate}")
        for gate in required_gates:
            value = receipts.get(gate)
            if not isinstance(value, Mapping):
                failed.append(gate)
                continue
            declared_statuses = [
                str(value[key] or "").strip().casefold() for key in ("status", "outcome") if key in value
            ]
            receipt_sha256 = str(value.get("receipt_sha256") or "").strip().upper()
            body = {key: item for key, item in value.items() if key != "receipt_sha256"}
            try:
                digest_matches = receipt_sha256 == canonical_sha256(body)
            except (TypeError, ValueError):
                digest_matches = False
            non_release_receipt = (
                value.get("release_gate_eligible") is not True
                or value.get("diagnostic") is True
                or value.get("diagnostic_only") is True
                or value.get("structure_only") is True
                or str(value.get("status") or "").strip().casefold() == "diagnostic"
                or str(value.get("evaluation") or "").strip().casefold() == "not_evaluated"
                or str(value.get("approval_decision") or "").strip().casefold() == "not_evaluated"
                or str(value.get("gate_scope") or "").strip().casefold().endswith("_only")
                or str(value.get("schema_version") or "").strip() == "release-approval-registry-check/v1"
            )
            if (
                not declared_statuses
                or any(status != "passed" for status in declared_statuses)
                or _SHA256_RE.fullmatch(receipt_sha256) is None
                or not digest_matches
                or non_release_receipt
            ):
                failed.append(gate)
        return list(dict.fromkeys(failed))

    @staticmethod
    def _event_view(event: Any) -> dict[str, Any]:
        view = _plain(event)
        if isinstance(view, Mapping):
            return dict(view)
        return {"value": view}

    @staticmethod
    def _alias_view(alias: Any, *, scope: ReleaseScope) -> dict[str, Any]:
        payload = _value(alias, "alias_payload")
        if payload is None:
            payload = _value(alias, "alias_payload_json")
        return {
            "target_environment": str(_value(alias, "target_environment", "")),
            "scope_kind": str(_value(alias, "scope_kind", scope.scope_kind)),
            "scope_key": str(_value(alias, "scope_key", scope.scope_key)),
            "current_release_id": _value(alias, "current_release_id"),
            "previous_release_id": _value(alias, "previous_release_id"),
            "revision": int(_value(alias, "revision", 0)),
            "alias_payload": _json_mapping(payload, field_name="alias payload"),
        }

    @staticmethod
    def _raise_repository_error(exc: RepositoryReleaseControlError) -> None:
        name = exc.__class__.__name__
        if name in _REPOSITORY_CONFLICT_NAMES:
            raise ReleaseConflictError("repository compare-and-swap conflict") from exc
        if name in _REPOSITORY_NOT_FOUND_NAMES:
            raise ReleaseNotFoundError("release manifest was not found") from exc
        if name in _REPOSITORY_INPUT_NAMES:
            raise ReleaseInputError("repository rejected the whole-bundle plan") from exc
        if name in _REPOSITORY_GATE_NAMES:
            raise ReleaseGateBlockedError("repository rejected the release state transition") from exc
        raise exc
