from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

# isort: split
from backend.app.schemas.release_approval import (
    ApprovalGateReceipt,
    AuthorityApprovalReceipt,
    ManifestApprovalRequirement,
)

ReleaseState = Literal[
    "draft",
    "candidate",
    "validated",
    "approved",
    "current",
    "deprecated",
    "rejected",
    "rolled_back",
]
ReleaseScopeKind = Literal["logical_lane", "physical_bundle"]
PublicReleaseAction = Literal[
    "prepare",
    "validate",
    "approve-record",
    "promote",
    "rollback",
]
ReleaseAction = PublicReleaseAction
ReleaseEventAction = Literal[
    "prepare",
    "validate",
    "approve-record",
    "promote",
    "rollback",
    "supersede",
    "reactivate",
]
ReceiptOutcome = Literal[
    "applied",
    "replayed",
    "blocked",
    "conflict",
    "invalid",
    "error",
]

_HEX_40 = re.compile(r"^[0-9a-fA-F]{40}$")
_HEX_64 = re.compile(r"^[0-9a-fA-F]{64}$")
_SENSITIVE_KEYS = {
    "password",
    "secret",
    "api_key",
    "access_token",
    "authorization",
    "dsn",
    "connection_string",
    "credential",
    "credentials",
}
_PHYSICAL_PATH_KEYS = {"duckdb_path", "database_path", "physical_path"}


def _normalized_hex(value: Any, *, length: int, field_name: str) -> str:
    normalized = str(value or "").strip()
    pattern = _HEX_40 if length == 40 else _HEX_64
    if pattern.fullmatch(normalized) is None:
        raise ValueError(f"{field_name} must be {length} hexadecimal characters")
    return normalized.lower() if length == 40 else normalized.upper()


def canonical_json(value: Any) -> str:
    """Return the sole JSON representation used for release request digests."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest().upper()


def _normalized_key(value: Any) -> str:
    camel_split = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(value).strip())
    return re.sub(r"[^0-9a-z]+", "_", camel_split.casefold()).strip("_")


def _key_matches_forbidden(value: Any, forbidden_keys: set[str]) -> bool:
    normalized = _normalized_key(value)
    normalized_forbidden = {_normalized_key(key) for key in forbidden_keys}
    if normalized in normalized_forbidden:
        return True
    if normalized.replace("_", "") in {key.replace("_", "") for key in normalized_forbidden}:
        return True
    return any(
        normalized.startswith(f"{key}_") or normalized.endswith(f"_{key}") or f"_{key}_" in normalized
        for key in normalized_forbidden
    )


def _contains_forbidden_key(value: Any, forbidden_keys: set[str]) -> bool:
    if isinstance(value, Mapping):
        return any(
            _key_matches_forbidden(key, forbidden_keys) or _contains_forbidden_key(item, forbidden_keys)
            for key, item in value.items()
        )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return any(_contains_forbidden_key(item, forbidden_keys) for item in value)
    return False


class _ReleaseModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        populate_by_name=True,
    )


class ReleaseScope(_ReleaseModel):
    """One immutable scope binding in the whole-bundle promotion plan."""

    model_config = ConfigDict(
        extra="allow",
        frozen=True,
        str_strip_whitespace=True,
        populate_by_name=True,
    )

    scope_kind: ReleaseScopeKind
    scope_key: str = Field(min_length=1)
    artifact_kind: str = Field(min_length=1)
    artifact_version: str = Field(min_length=1)
    artifact_sha256: str = Field(min_length=64, max_length=64)
    evidence_sha256: str = Field(min_length=64, max_length=64)
    contained_lane_versions: dict[str, str] = Field(default_factory=dict)
    alias_payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("artifact_sha256", "evidence_sha256", mode="after")
    @classmethod
    def _normalize_scope_digests(cls, value: str) -> str:
        return _normalized_hex(value, length=64, field_name="scope digest")

    @model_validator(mode="before")
    @classmethod
    def _reject_physical_path_on_logical_lane(cls, data: Any) -> Any:
        if not isinstance(data, Mapping):
            return data
        if _contains_forbidden_key(data.get("alias_payload", {}), _SENSITIVE_KEYS):
            raise ValueError("alias_payload must not contain credential keys")
        if data.get("scope_kind") == "logical_lane" and _contains_forbidden_key(
            data,
            _PHYSICAL_PATH_KEYS,
        ):
            raise ValueError("logical_lane scope must not contain physical path keys")
        return data

    @model_validator(mode="after")
    def _validate_scope_boundary(self) -> ReleaseScope:
        if self.scope_kind == "physical_bundle":
            if self.scope_key != "duckdb-main":
                raise ValueError("v1 physical_bundle scope_key must be duckdb-main")
            if not self.contained_lane_versions:
                raise ValueError("physical_bundle:duckdb-main must declare contained_lane_versions")
        elif self.contained_lane_versions:
            raise ValueError("logical_lane must not declare contained_lane_versions")
        return self


class ReleaseManifestPayload(_ReleaseModel):
    """Frozen, self-contained whole-bundle plan accepted by ``prepare``."""

    model_config = ConfigDict(
        extra="allow",
        frozen=True,
        str_strip_whitespace=True,
        populate_by_name=True,
    )

    target_environment: str = Field(min_length=1)
    git_sha: str = Field(min_length=1)
    schema_heads: dict[str, Any] = Field(min_length=1)
    contracts: dict[str, Any] = Field(min_length=1)
    builds: dict[str, Any] = Field(min_length=1)
    numeric_policy: dict[str, Any] = Field(min_length=1)
    required_validation_gates: list[str] = Field(min_length=1)
    approval_registry_sha256: str = Field(min_length=64, max_length=64)
    approval_requirements: list[ManifestApprovalRequirement] = Field(min_length=1)
    scopes: list[ReleaseScope] = Field(min_length=2)

    @model_validator(mode="before")
    @classmethod
    def _reject_credentials(cls, data: Any) -> Any:
        if _contains_forbidden_key(data, _SENSITIVE_KEYS):
            raise ValueError("manifest payload must not contain credential keys")
        return data

    @field_validator("git_sha", mode="after")
    @classmethod
    def _normalize_git_sha(cls, value: str) -> str:
        return _normalized_hex(value, length=40, field_name="git_sha")

    @field_validator("approval_registry_sha256", mode="after")
    @classmethod
    def _normalize_approval_registry_digest(cls, value: str) -> str:
        return _normalized_hex(
            value,
            length=64,
            field_name="approval_registry_sha256",
        )

    @field_validator("required_validation_gates", mode="before")
    @classmethod
    def _normalize_required_validation_gates(cls, value: Any) -> list[str]:
        if not isinstance(value, list):
            raise ValueError("required_validation_gates must be a list")
        normalized = [str(gate or "").strip() for gate in value]
        if not normalized or any(not gate for gate in normalized):
            raise ValueError("required_validation_gates must contain non-empty names")
        if len(normalized) != len(set(normalized)):
            raise ValueError("required_validation_gates must be unique")
        return normalized

    @field_validator(
        "schema_heads",
        "contracts",
        "builds",
        "numeric_policy",
        mode="after",
    )
    @classmethod
    def _require_non_empty_bindings(cls, value: dict[str, Any]) -> dict[str, Any]:
        if any(key == "" for key in value):
            raise ValueError("manifest binding keys must be non-empty")
        return value

    @model_validator(mode="after")
    def _validate_whole_bundle_plan(self) -> ReleaseManifestPayload:
        for storage in ("postgres", "duckdb"):
            heads = self.schema_heads.get(storage)
            if not isinstance(heads, list) or not heads or any(not str(head or "").strip() for head in heads):
                raise ValueError(f"schema_heads.{storage} must be a non-empty list")

        for build_name in ("backend", "frontend"):
            build = self.builds.get(build_name)
            if not isinstance(build, Mapping):
                raise ValueError(f"builds.{build_name} must be an object")
            _normalized_hex(
                build.get("git_sha"),
                length=40,
                field_name=f"builds.{build_name}.git_sha",
            )
            _normalized_hex(
                build.get("build_sha256"),
                length=64,
                field_name=f"builds.{build_name}.build_sha256",
            )

        for contract_key in (
            "openapi_sha256",
            "dto_sha256",
            "receipt_sha256",
        ):
            _normalized_hex(
                self.contracts.get(contract_key),
                length=64,
                field_name=f"contracts.{contract_key}",
            )

        if not str(self.numeric_policy.get("policy_version") or "").strip():
            raise ValueError("numeric_policy.policy_version is required")
        _normalized_hex(
            self.numeric_policy.get("policy_sha256"),
            length=64,
            field_name="numeric_policy.policy_sha256",
        )

        scope_keys = [scope.scope_key for scope in self.scopes]
        if len(scope_keys) != len(set(scope_keys)):
            raise ValueError("scope_key must be unique across the promotion plan")

        approval_ids = [requirement.approval_id for requirement in self.approval_requirements]
        approval_subjects = [
            (requirement.subject_kind, requirement.subject_key)
            for requirement in self.approval_requirements
        ]
        if len(approval_ids) != len(set(approval_ids)):
            raise ValueError("approval_requirements approval_id values must be unique")
        if len(approval_subjects) != len(set(approval_subjects)):
            raise ValueError("approval_requirements subjects must be unique")

        physical = [scope for scope in self.scopes if scope.scope_kind == "physical_bundle"]
        logical = [scope for scope in self.scopes if scope.scope_kind == "logical_lane"]
        if len(physical) != 1 or physical[0].scope_key != "duckdb-main":
            raise ValueError("promotion plan must contain exactly physical_bundle:duckdb-main")
        if not logical:
            raise ValueError("promotion plan must contain at least one logical_lane")

        logical_versions = {scope.scope_key: scope.artifact_version for scope in logical}
        if physical[0].contained_lane_versions != logical_versions:
            raise ValueError("duckdb-main contained_lane_versions must exactly match all logical lanes")
        return self

    def canonical_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)


class ReleaseManifest(_ReleaseModel):
    release_id: str = Field(min_length=1)
    state: Literal["candidate"] = "candidate"
    payload: ReleaseManifestPayload
    content_sha256: str | None = Field(default=None, min_length=64, max_length=64)

    @model_validator(mode="after")
    def _derive_content_digest(self) -> ReleaseManifest:
        digest = canonical_sha256(self.payload.canonical_payload())
        if self.content_sha256 is not None and self.content_sha256.upper() != digest:
            raise ValueError("content_sha256 does not match canonical manifest payload")
        object.__setattr__(self, "content_sha256", digest)
        return self

    @property
    def target_environment(self) -> str:
        return self.payload.target_environment


class ReleaseEvent(_ReleaseModel):
    release_id: str = Field(min_length=1)
    action: ReleaseEventAction
    from_state: ReleaseState | None = None
    to_state: ReleaseState
    manifest_digest: str | None = Field(
        default=None,
        validation_alias=AliasChoices("manifest_digest", "manifest_sha256"),
        min_length=64,
        max_length=64,
    )
    event_payload: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None

    @model_validator(mode="after")
    def _validate_transition_and_approval_binding(self) -> ReleaseEvent:
        expected_transitions: dict[
            str,
            set[tuple[ReleaseState | None, ReleaseState]],
        ] = {
            "prepare": {("draft", "candidate")},
            "validate": {("candidate", "validated")},
            "approve-record": {("validated", "approved")},
            "promote": {("approved", "current")},
            "rollback": {
                ("current", "rolled_back"),
            },
            "supersede": {("current", "deprecated")},
            "reactivate": {
                ("approved", "current"),
                ("deprecated", "current"),
                ("rolled_back", "current"),
            },
        }
        expected = expected_transitions[self.action]
        if (self.from_state, self.to_state) not in expected:
            raise ValueError(f"invalid {self.action} transition: {self.from_state!r} -> {self.to_state!r}")
        if self.action == "approve-record":
            if self.manifest_digest is None:
                raise ValueError("approval must bind manifest_digest")
            try:
                authority = AuthorityApprovalReceipt.model_validate(
                    self.event_payload.get("authority_receipt")
                )
                gate = ApprovalGateReceipt.model_validate(
                    self.event_payload.get("approval_gate_receipt")
                )
            except (TypeError, ValueError):
                raise ValueError(
                    "approval must bind canonical authority and passed gate receipts"
                ) from None
            if gate.status != "passed":
                raise ValueError("approval gate receipt must be passed")
            if authority.decision != "approved" or any(
                subject.decision != "approved" for subject in authority.subjects
            ):
                raise ValueError("authority receipt must record approved decisions")
            if authority.release_id != self.release_id or gate.release_id != self.release_id:
                raise ValueError("approval receipts must bind event release_id")
            if (
                authority.manifest_sha256 != self.manifest_digest
                or gate.manifest_sha256 != self.manifest_digest
            ):
                raise ValueError("approval receipts must bind event manifest_digest")
            if authority.registry_sha256 != gate.registry_sha256:
                raise ValueError("approval receipts must bind the same registry digest")
            if gate.authority_receipt_sha256 != authority.receipt_sha256:
                raise ValueError("approval gate must bind authority receipt digest")
            authority_subjects = {
                subject.approval_id: subject for subject in authority.subjects
            }
            gate_subjects = {subject.approval_id: subject for subject in gate.subjects}
            if set(authority_subjects) != set(gate_subjects):
                raise ValueError("approval gate subjects must match authority receipt")
            for approval_id, subject in authority_subjects.items():
                gate_subject = gate_subjects[approval_id]
                if (
                    gate_subject.subject_kind != subject.subject_kind
                    or gate_subject.subject_key != subject.subject_key
                    or gate_subject.states != subject.states
                    or gate_subject.evidence_receipt_sha256
                    != subject.evidence_receipt_sha256
                ):
                    raise ValueError(
                        "approval gate subject evidence must match authority receipt"
                    )
            if self.event_payload.get("authority_reference") != authority.authority_reference:
                raise ValueError("approval event authority reference must match receipt")
            payload_manifest_digest = str(
                self.event_payload.get("manifest_digest") or ""
            ).upper()
            if payload_manifest_digest != self.manifest_digest:
                raise ValueError("approval event payload must bind manifest_digest")
            expected_payload_keys = {
                "authority_reference",
                "manifest_digest",
                "authority_receipt",
                "approval_gate_receipt",
            }
            if set(self.event_payload) != expected_payload_keys:
                raise ValueError("approval event payload contains unsupported fields")
        return self


class ReleaseAlias(_ReleaseModel):
    target_environment: str = Field(min_length=1)
    scope_kind: ReleaseScopeKind
    scope_key: str = Field(min_length=1)
    current_release_id: str = Field(min_length=1)
    previous_release_id: str | None = None
    revision: int = Field(ge=0)
    alias_payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_alias_boundary(self) -> ReleaseAlias:
        if _contains_forbidden_key(self.alias_payload, _SENSITIVE_KEYS):
            raise ValueError("alias_payload must not contain credential keys")
        if self.scope_kind == "physical_bundle":
            if self.scope_key != "duckdb-main":
                raise ValueError("v1 physical_bundle alias must be duckdb-main")
        elif _contains_forbidden_key(self.alias_payload, _PHYSICAL_PATH_KEYS):
            raise ValueError("logical_lane alias must not contain physical path keys")
        return self


class ScopeExpectation(_ReleaseModel):
    scope_kind: ReleaseScopeKind
    scope_key: str = Field(min_length=1)
    expected_revision: int = Field(ge=0)
    alias_payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_expectation_boundary(self) -> ScopeExpectation:
        if _contains_forbidden_key(self.alias_payload, _SENSITIVE_KEYS):
            raise ValueError("alias_payload must not contain credential keys")
        if self.scope_kind == "physical_bundle":
            if self.scope_key != "duckdb-main":
                raise ValueError("v1 physical_bundle expectation must be duckdb-main")
        elif _contains_forbidden_key(self.alias_payload, _PHYSICAL_PATH_KEYS):
            raise ValueError("logical_lane alias must not contain physical path keys")
        return self


class WholeBundleActivationRequest(_ReleaseModel):
    release_id: str = Field(min_length=1)
    target_environment: str = Field(min_length=1)
    manifest_digest: str = Field(min_length=64, max_length=64)
    scopes: list[ScopeExpectation] = Field(min_length=2)
    idempotency_key: str = Field(min_length=1)

    @model_validator(mode="after")
    def _require_complete_unique_plan(self) -> WholeBundleActivationRequest:
        identities = [(scope.scope_kind, scope.scope_key) for scope in self.scopes]
        if len(identities) != len(set(identities)):
            raise ValueError("activation scope expectations must be unique")
        physical = [identity for identity in identities if identity[0] == "physical_bundle"]
        logical = [identity for identity in identities if identity[0] == "logical_lane"]
        if physical != [("physical_bundle", "duckdb-main")]:
            raise ValueError("activation must include exactly physical_bundle:duckdb-main")
        if not logical:
            raise ValueError("activation must include at least one logical_lane")
        return self


class ActionReceipt(_ReleaseModel):
    action: ReleaseAction
    outcome: ReceiptOutcome
    release_id: str | None = None
    release_state: ReleaseState | None = None
    manifest_digest: str | None = None
    target_environment: str | None = None
    idempotency_key: str | None = None
    replayed: bool = False
    scopes: list[dict[str, Any]] = Field(default_factory=list)
    aliases: dict[str, ReleaseAlias] = Field(default_factory=dict)
    blockers: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)

    @property
    def release_id_or_empty(self) -> str:
        return self.release_id or ""

    @property
    def content_sha256(self) -> str | None:
        return self.manifest_digest


class ReleaseView(_ReleaseModel):
    release_id: str
    state: ReleaseState
    manifest: dict[str, Any]
    events: list[dict[str, Any]]
    aliases: list[dict[str, Any]]

    @property
    def audit_chain(self) -> list[dict[str, Any]]:
        return self.events

    @property
    def content_sha256(self) -> str | None:
        value = self.manifest.get("content_sha256")
        return str(value) if value is not None else None
