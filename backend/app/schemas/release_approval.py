from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ApprovalSubjectKind = Literal["page", "calculation_p1"]
ApprovalStateName = Literal[
    "evidence_captured",
    "machine_validated",
    "business_approved",
    "formal_use_allowed",
    "closure_approved",
]
ApprovalDecision = Literal["approved", "rejected"]
ReleaseApprovalScopeKind = Literal["logical_lane", "physical_bundle"]

APPROVAL_STATE_NAMES: tuple[ApprovalStateName, ...] = (
    "evidence_captured",
    "machine_validated",
    "business_approved",
    "formal_use_allowed",
    "closure_approved",
)
_HEX_64 = re.compile(r"^[0-9a-fA-F]{64}$")
_OPAQUE_REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@-]{0,255}$")
_WINDOWS_ABSOLUTE_PATH = re.compile(r"^[A-Za-z]:[/\\]")


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest().upper()


def _normalized_sha256(value: Any, *, field_name: str) -> str:
    normalized = str(value or "").strip()
    if _HEX_64.fullmatch(normalized) is None:
        raise ValueError(f"{field_name} must be 64 hexadecimal characters")
    return normalized.upper()


def _require_timezone(value: datetime, *, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


def _normalized_reference(value: Any, *, field_name: str) -> str:
    normalized = str(value or "").strip()
    if _OPAQUE_REFERENCE.fullmatch(normalized) is None:
        raise ValueError(f"{field_name} must be an opaque reference token")
    if normalized.startswith(("/", "\\")) or _WINDOWS_ABSOLUTE_PATH.match(normalized):
        raise ValueError(f"{field_name} must not be an absolute path")
    return normalized


class _ApprovalModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )


class ApprovalStateVector(_ApprovalModel):
    """Five independent release-approval facts; no field implies another."""

    evidence_captured: bool
    machine_validated: bool
    business_approved: bool
    formal_use_allowed: bool
    closure_approved: bool

    @property
    def all_satisfied(self) -> bool:
        return all(getattr(self, state) for state in APPROVAL_STATE_NAMES)


class ReleaseApprovalCommand(_ApprovalModel):
    """Repository-relative, fixed argv declared by the registry."""

    argv: tuple[str, ...] = Field(min_length=2)


class ReleaseApprovalScopeMapping(_ApprovalModel):
    status: Literal["PENDING", "mapped"]
    scope_kind: ReleaseApprovalScopeKind | None
    scope_key: str | None

    @model_validator(mode="after")
    def _validate_mapping(self) -> ReleaseApprovalScopeMapping:
        if self.status == "PENDING":
            if self.scope_kind is not None or self.scope_key is not None:
                raise ValueError("PENDING scope mapping must not claim a scope")
            return self
        if self.scope_kind is None or not str(self.scope_key or "").strip():
            raise ValueError("mapped scope requires scope_kind and scope_key")
        return self


class ReleaseApprovalRegistryEntry(_ApprovalModel):
    approval_id: str = Field(min_length=1)
    subject_kind: ApprovalSubjectKind
    subject_key: str = Field(min_length=1)
    authority_policy_id: str = Field(min_length=1, max_length=256)
    scope_mapping: ReleaseApprovalScopeMapping
    command: ReleaseApprovalCommand
    required_states: tuple[ApprovalStateName, ...] = Field(
        min_length=1,
        max_length=len(APPROVAL_STATE_NAMES),
    )

    @field_validator("required_states", mode="after")
    @classmethod
    def _require_unique_independent_states(
        cls,
        value: tuple[ApprovalStateName, ...],
    ) -> tuple[ApprovalStateName, ...]:
        if len(set(value)) != len(value):
            raise ValueError("required_states must not contain duplicates")
        return value


class ReleaseApprovalRegistry(_ApprovalModel):
    schema_version: Literal["release-approval-registry/v1"]
    registry_id: str = Field(min_length=1)
    entries: tuple[ReleaseApprovalRegistryEntry, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _require_unique_entries(self) -> ReleaseApprovalRegistry:
        approval_ids = [entry.approval_id for entry in self.entries]
        subjects = [(entry.subject_kind, entry.subject_key) for entry in self.entries]
        if len(approval_ids) != len(set(approval_ids)):
            raise ValueError("approval_id must be unique")
        if len(subjects) != len(set(subjects)):
            raise ValueError("approval subject must be unique")
        return self

    def canonical_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    @property
    def registry_sha256(self) -> str:
        return canonical_sha256(self.canonical_payload())


class ManifestApprovalRequirement(_ApprovalModel):
    approval_id: str = Field(min_length=1)
    subject_kind: ApprovalSubjectKind
    subject_key: str = Field(min_length=1)
    required_states: tuple[ApprovalStateName, ...] = Field(
        min_length=1,
        max_length=len(APPROVAL_STATE_NAMES),
    )

    @field_validator("required_states", mode="after")
    @classmethod
    def _require_unique_states(
        cls,
        value: tuple[ApprovalStateName, ...],
    ) -> tuple[ApprovalStateName, ...]:
        if len(set(value)) != len(value):
            raise ValueError("required_states must not contain duplicates")
        return value


class AuthoritySubjectApproval(_ApprovalModel):
    approval_id: str = Field(min_length=1)
    subject_kind: ApprovalSubjectKind
    subject_key: str = Field(min_length=1)
    authority_policy_id: str = Field(min_length=1, max_length=256)
    scope_kind: ReleaseApprovalScopeKind
    scope_key: str = Field(min_length=1)
    decision: ApprovalDecision
    states: ApprovalStateVector
    evidence_receipt_sha256: str

    @field_validator("evidence_receipt_sha256", mode="after")
    @classmethod
    def _normalize_evidence_digest(cls, value: str) -> str:
        return _normalized_sha256(value, field_name="evidence_receipt_sha256")


class AuthorityApprovalReceiptBody(_ApprovalModel):
    schema_version: Literal["release-authority-approval/v1"] = "release-authority-approval/v1"
    release_id: str = Field(min_length=1)
    manifest_sha256: str
    registry_sha256: str
    authority_reference: str = Field(min_length=1, max_length=256)
    authority_verifier_receipt_sha256: str
    decision: ApprovalDecision
    decided_at: datetime
    expires_at: datetime | None
    revoked_at: datetime | None
    revocation_reference: str | None
    subjects: tuple[AuthoritySubjectApproval, ...] = Field(min_length=1)

    @field_validator(
        "manifest_sha256",
        "registry_sha256",
        "authority_verifier_receipt_sha256",
        mode="after",
    )
    @classmethod
    def _normalize_receipt_digests(cls, value: str) -> str:
        return _normalized_sha256(value, field_name="approval receipt digest")

    @field_validator("decided_at", "expires_at", "revoked_at", mode="after")
    @classmethod
    def _require_aware_datetimes(cls, value: datetime | None, info: Any) -> datetime | None:
        if value is None:
            return None
        return _require_timezone(value, field_name=info.field_name)

    @field_validator("authority_reference", "revocation_reference", mode="after")
    @classmethod
    def _require_opaque_references(cls, value: str | None, info: Any) -> str | None:
        if value is None:
            return None
        return _normalized_reference(value, field_name=info.field_name)

    @model_validator(mode="after")
    def _validate_receipt_window(self) -> AuthorityApprovalReceiptBody:
        if self.expires_at is not None and self.expires_at <= self.decided_at:
            raise ValueError("expires_at must be after decided_at")
        if self.revoked_at is None and self.revocation_reference is not None:
            raise ValueError("revocation_reference requires revoked_at")
        if self.revoked_at is not None and not str(self.revocation_reference or "").strip():
            raise ValueError("revoked_at requires revocation_reference")
        approval_ids = [subject.approval_id for subject in self.subjects]
        if len(approval_ids) != len(set(approval_ids)):
            raise ValueError("authority receipt subjects must have unique approval_id values")
        return self


class AuthorityApprovalReceipt(AuthorityApprovalReceiptBody):
    receipt_sha256: str

    @field_validator("receipt_sha256", mode="after")
    @classmethod
    def _normalize_receipt_sha256(cls, value: str) -> str:
        return _normalized_sha256(value, field_name="receipt_sha256")

    @model_validator(mode="after")
    def _verify_canonical_digest(self) -> AuthorityApprovalReceipt:
        payload = self.model_dump(mode="json", exclude={"receipt_sha256"})
        if self.receipt_sha256 != canonical_sha256(payload):
            raise ValueError("receipt_sha256 does not match canonical approval receipt")
        return self


class ApprovalGateSubjectStatus(_ApprovalModel):
    approval_id: str = Field(min_length=1)
    subject_kind: ApprovalSubjectKind
    subject_key: str = Field(min_length=1)
    states: ApprovalStateVector
    evidence_receipt_sha256: str | None

    @field_validator("evidence_receipt_sha256", mode="after")
    @classmethod
    def _normalize_optional_digest(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalized_sha256(value, field_name="evidence_receipt_sha256")


class ApprovalGateReceiptBody(_ApprovalModel):
    schema_version: Literal["release-approval-gate/v1"] = "release-approval-gate/v1"
    status: Literal["passed", "blocked"]
    reason_codes: tuple[str, ...]
    release_id: str = Field(min_length=1)
    manifest_sha256: str
    registry_sha256: str
    authority_receipt_sha256: str | None
    checked_at: datetime
    subjects: tuple[ApprovalGateSubjectStatus, ...]

    @field_validator("manifest_sha256", "registry_sha256", mode="after")
    @classmethod
    def _normalize_gate_digests(cls, value: str) -> str:
        return _normalized_sha256(value, field_name="approval gate digest")

    @field_validator("authority_receipt_sha256", mode="after")
    @classmethod
    def _normalize_authority_digest(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalized_sha256(value, field_name="authority_receipt_sha256")

    @field_validator("checked_at", mode="after")
    @classmethod
    def _require_checked_at_timezone(cls, value: datetime) -> datetime:
        return _require_timezone(value, field_name="checked_at")

    @model_validator(mode="after")
    def _validate_status_reasons(self) -> ApprovalGateReceiptBody:
        if len(self.reason_codes) != len(set(self.reason_codes)):
            raise ValueError("reason_codes must be unique")
        if self.status == "passed" and self.reason_codes:
            raise ValueError("passed approval gate must not contain reason codes")
        if self.status == "blocked" and not self.reason_codes:
            raise ValueError("blocked approval gate requires reason codes")
        return self


class ApprovalGateReceipt(ApprovalGateReceiptBody):
    receipt_sha256: str

    @field_validator("receipt_sha256", mode="after")
    @classmethod
    def _normalize_gate_receipt_sha256(cls, value: str) -> str:
        return _normalized_sha256(value, field_name="receipt_sha256")

    @model_validator(mode="after")
    def _verify_gate_digest(self) -> ApprovalGateReceipt:
        payload = self.model_dump(mode="json", exclude={"receipt_sha256"})
        if self.receipt_sha256 != canonical_sha256(payload):
            raise ValueError("receipt_sha256 does not match canonical approval gate receipt")
        return self


def build_authority_approval_receipt(
    payload: Mapping[str, Any] | AuthorityApprovalReceiptBody,
) -> AuthorityApprovalReceipt:
    body = (
        payload
        if isinstance(payload, AuthorityApprovalReceiptBody)
        else AuthorityApprovalReceiptBody.model_validate(payload)
    )
    serialized = body.model_dump(mode="json", exclude={"receipt_sha256"})
    return AuthorityApprovalReceipt.model_validate(
        {**serialized, "receipt_sha256": canonical_sha256(serialized)}
    )


def build_approval_gate_receipt(
    payload: Mapping[str, Any] | ApprovalGateReceiptBody,
) -> ApprovalGateReceipt:
    body = (
        payload
        if isinstance(payload, ApprovalGateReceiptBody)
        else ApprovalGateReceiptBody.model_validate(payload)
    )
    serialized = body.model_dump(mode="json", exclude={"receipt_sha256"})
    return ApprovalGateReceipt.model_validate(
        {**serialized, "receipt_sha256": canonical_sha256(serialized)}
    )
