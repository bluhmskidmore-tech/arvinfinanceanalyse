from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ValidationError

# isort: split
from backend.app.schemas.release_approval import (
    ApprovalGateReceipt,
    ApprovalGateSubjectStatus,
    ApprovalStateVector,
    AuthorityApprovalReceipt,
    ManifestApprovalRequirement,
    ReleaseApprovalRegistry,
    ReleaseApprovalRegistryEntry,
    build_approval_gate_receipt,
    canonical_sha256,
)

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REGISTRY_PATH = ROOT / "config" / "release_approval_registry.v1.json"

PAGE_CHECKER_BY_SUBJECT = {
    "average-balance": "scripts/check_average_balance_business_owner_approval.py",
    "balance-analysis": "scripts/check_balance_analysis_business_owner_approval.py",
    "bond-analysis": "scripts/check_bond_analysis_business_owner_approval.py",
    "ledger-pnl": "scripts/check_ledger_pnl_business_owner_approval.py",
    "pnl-attribution": "scripts/check_pnl_attribution_business_owner_approval.py",
    "portfolio-home": "scripts/check_portfolio_home_business_owner_approval.py",
    "product-category-pnl": "scripts/check_product_category_pnl_business_owner_approval.py",
    "stock-analysis": "scripts/check_stock_analysis_business_owner_approval.py",
}
OPEN_CALCULATION_P1_IDS = (
    "P1-01",
    "P1-02",
    "P1-03",
    "P1-04",
    "P1-05",
    "P1-06",
    "P1-10",
    "P1-11",
)
CALCULATION_CHECKER = "scripts/check_calculation_p1_owner_decisions.py"
_SHELL_META = re.compile(r"[;&|><`$()\r\n]")


class ReleaseApprovalError(RuntimeError):
    pass


class ApprovalRegistryError(ReleaseApprovalError):
    pass


class ApprovalVerificationBlocked(ReleaseApprovalError):
    def __init__(self, receipt: ApprovalGateReceipt) -> None:
        self.receipt = receipt
        super().__init__(
            "release approval evidence gate blocked: " + ",".join(receipt.reason_codes)
        )


@runtime_checkable
class AuthorityAttestationVerifierProtocol(Protocol):
    def verify(self, receipt: AuthorityApprovalReceipt) -> bool: ...


@runtime_checkable
class ReleaseApprovalVerifierProtocol(Protocol):
    def verify_record_approval(
        self,
        *,
        release_id: str,
        manifest_sha256: str,
        manifest_payload: Mapping[str, Any] | BaseModel,
        authority_receipt: AuthorityApprovalReceipt,
    ) -> ApprovalGateReceipt: ...

    def verify_promotion(
        self,
        *,
        release_id: str,
        manifest_sha256: str,
        manifest_payload: Mapping[str, Any] | BaseModel,
        authority_receipt: AuthorityApprovalReceipt,
    ) -> ApprovalGateReceipt: ...


def _plain_mapping(value: Mapping[str, Any] | BaseModel) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        dumped = value.model_dump(mode="json")
        return {str(key): item for key, item in dumped.items()}
    return {str(key): item for key, item in value.items()}


def _isolated_checker_environment() -> dict[str, str]:
    allowed = ("SYSTEMROOT", "WINDIR", "TEMP", "TMP")
    return {key: os.environ[key] for key in allowed if key in os.environ}


def load_release_approval_registry(
    path: str | Path = DEFAULT_REGISTRY_PATH,
) -> ReleaseApprovalRegistry:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return ReleaseApprovalRegistry.model_validate(payload)
    except (OSError, UnicodeError, json.JSONDecodeError, ValidationError):
        raise ApprovalRegistryError("release approval registry is missing or invalid") from None


def _safe_command_reason(
    entry: ReleaseApprovalRegistryEntry,
    *,
    repo_root: Path,
) -> str | None:
    argv = entry.command.argv
    if any(not token or "\x00" in token or _SHELL_META.search(token) for token in argv):
        return "registry_command_contains_shell_syntax"

    script = argv[0]
    script_path = PurePosixPath(script)
    if Path(script).is_absolute() or script_path.is_absolute() or ".." in script_path.parts:
        return "registry_command_path_not_repository_relative"
    if "\\" in script:
        return "registry_command_path_not_normalized"

    resolved = (repo_root / Path(*script_path.parts)).resolve()
    try:
        resolved.relative_to(repo_root.resolve())
    except ValueError:
        return "registry_command_path_escapes_repository"
    if not resolved.is_file():
        return "registry_command_script_missing"

    if entry.subject_kind == "page":
        expected_script = PAGE_CHECKER_BY_SUBJECT.get(entry.subject_key)
        if expected_script is None or tuple(argv) != (expected_script, "--require-captured"):
            return "registry_page_command_not_allowlisted"
        return None

    expected = (
        CALCULATION_CHECKER,
        "--decision-id",
        entry.subject_key,
        "--require-captured",
    )
    if entry.subject_key not in OPEN_CALCULATION_P1_IDS or tuple(argv) != expected:
        return "registry_calculation_command_not_allowlisted"
    return None


def validate_registry_structure(
    registry: ReleaseApprovalRegistry,
    *,
    repo_root: str | Path = ROOT,
    expected_page_scripts: Sequence[str] | None = None,
    expected_calculation_ids: Sequence[str] | None = None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    root = Path(repo_root).resolve()
    page_scripts = tuple(
        sorted(
            expected_page_scripts
            if expected_page_scripts is not None
            else PAGE_CHECKER_BY_SUBJECT.values()
        )
    )
    calculation_ids = tuple(
        expected_calculation_ids
        if expected_calculation_ids is not None
        else OPEN_CALCULATION_P1_IDS
    )
    registered_page_scripts = tuple(
        sorted(entry.command.argv[0] for entry in registry.entries if entry.subject_kind == "page")
    )
    registered_calculation_ids = tuple(
        entry.subject_key for entry in registry.entries if entry.subject_kind == "calculation_p1"
    )
    if registered_page_scripts != page_scripts:
        reasons.append("registry_page_checker_set_mismatch")
    if registered_calculation_ids != calculation_ids:
        reasons.append("registry_calculation_p1_set_mismatch")
    if len(registry.entries) != len(page_scripts) + len(calculation_ids):
        reasons.append("registry_entry_count_mismatch")

    for entry in registry.entries:
        command_reason = _safe_command_reason(entry, repo_root=root)
        if command_reason is not None:
            reasons.append(f"{command_reason}:{entry.approval_id}")
    return tuple(dict.fromkeys(reasons))


def _failed_evidence_status(
    entry: ReleaseApprovalRegistryEntry,
    *,
    status: str,
) -> ApprovalGateSubjectStatus:
    states = ApprovalStateVector(
        evidence_captured=False,
        machine_validated=False,
        business_approved=False,
        formal_use_allowed=False,
        closure_approved=False,
    )
    digest = canonical_sha256(
        {
            "schema_version": "release-approval-evidence/v1",
            "approval_id": entry.approval_id,
            "subject_kind": entry.subject_kind,
            "subject_key": entry.subject_key,
            "status": status,
            "states": states.model_dump(mode="json"),
        }
    )
    return ApprovalGateSubjectStatus(
        approval_id=entry.approval_id,
        subject_kind=entry.subject_kind,
        subject_key=entry.subject_key,
        states=states,
        evidence_receipt_sha256=digest,
    )


def _typed_checker_status(
    entry: ReleaseApprovalRegistryEntry,
    *,
    payload: Mapping[str, Any],
    returncode: int,
) -> ApprovalGateSubjectStatus:
    if entry.subject_kind == "page":
        captured = payload.get("business_owner_approval_captured") is True and returncode == 0
        checker_status = str(payload.get("approval_status") or "invalid").strip().casefold()
        machine_validated = returncode in {0, 1} and checker_status in {
            "approved",
            "captured",
            "pending",
        }
        formal_use_allowed = payload.get("formal_use_allowed") is True
        closure_approved = payload.get("closure_approved") is True
    else:
        raw_states = payload.get("states")
        captured = (
            isinstance(raw_states, Mapping)
            and raw_states.get("evidence_captured") is True
            and returncode == 0
        )
        checker_status = str(payload.get("status") or "invalid").strip().casefold()
        machine_validated = (
            isinstance(raw_states, Mapping)
            and raw_states.get("machine_validated") is True
        )
        formal_use_allowed = (
            isinstance(raw_states, Mapping)
            and raw_states.get("formal_use_allowed") is True
        )
        closure_approved = (
            isinstance(raw_states, Mapping)
            and raw_states.get("closure_approved") is True
        )

    states = ApprovalStateVector(
        evidence_captured=captured,
        machine_validated=machine_validated,
        business_approved=False,
        formal_use_allowed=formal_use_allowed,
        closure_approved=closure_approved,
    )
    selected = {
        "schema_version": "release-approval-evidence/v1",
        "approval_id": entry.approval_id,
        "subject_kind": entry.subject_kind,
        "subject_key": entry.subject_key,
        "checker_status": checker_status,
        "states": states.model_dump(mode="json"),
    }
    return ApprovalGateSubjectStatus(
        approval_id=entry.approval_id,
        subject_kind=entry.subject_kind,
        subject_key=entry.subject_key,
        states=states,
        evidence_receipt_sha256=canonical_sha256(selected),
    )


def execute_registry_evidence(
    registry: ReleaseApprovalRegistry,
    *,
    entries: Sequence[ReleaseApprovalRegistryEntry] | None = None,
    repo_root: str | Path = ROOT,
    timeout_seconds: float = 60.0,
) -> tuple[ApprovalGateSubjectStatus, ...]:
    """Run only fixed registry commands and retain a typed, redacted projection."""

    root = Path(repo_root).resolve()
    structural_reasons = validate_registry_structure(registry, repo_root=root)
    if structural_reasons:
        raise ApprovalRegistryError("release approval registry command policy is invalid")

    selected_entries = tuple(registry.entries if entries is None else entries)
    registry_entries_by_id = {entry.approval_id: entry for entry in registry.entries}
    if len({entry.approval_id for entry in selected_entries}) != len(selected_entries) or any(
        registry_entries_by_id.get(entry.approval_id) != entry for entry in selected_entries
    ):
        raise ApprovalRegistryError("release approval evidence selection is invalid")

    statuses: list[ApprovalGateSubjectStatus] = []
    for entry in selected_entries:
        argv = [sys.executable, "-I", *entry.command.argv]
        try:
            completed = subprocess.run(
                argv,
                cwd=root,
                shell=False,
                env=_isolated_checker_environment(),
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout_seconds,
            )
        except (OSError, subprocess.SubprocessError):
            statuses.append(_failed_evidence_status(entry, status="execution_error"))
            continue
        try:
            payload = json.loads(completed.stdout)
        except (TypeError, json.JSONDecodeError):
            statuses.append(_failed_evidence_status(entry, status="invalid_output"))
            continue
        if not isinstance(payload, Mapping):
            statuses.append(_failed_evidence_status(entry, status="invalid_output"))
            continue
        statuses.append(
            _typed_checker_status(
                entry,
                payload=payload,
                returncode=completed.returncode,
            )
        )
    return tuple(statuses)


class ReleaseApprovalVerifier:
    """Fail-closed verifier for release-bound approval receipts."""

    def __init__(
        self,
        *,
        registry_path: str | Path = DEFAULT_REGISTRY_PATH,
        repo_root: str | Path = ROOT,
        authority_attestation_verifier: AuthorityAttestationVerifierProtocol | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.registry_path = Path(registry_path)
        self.repo_root = Path(repo_root).resolve()
        self.authority_attestation_verifier = authority_attestation_verifier
        self.clock = clock or (lambda: datetime.now(UTC))

    def verify_record_approval(
        self,
        *,
        release_id: str,
        manifest_sha256: str,
        manifest_payload: Mapping[str, Any] | BaseModel,
        authority_receipt: AuthorityApprovalReceipt,
    ) -> ApprovalGateReceipt:
        return self._verify(
            release_id=release_id,
            manifest_sha256=manifest_sha256,
            manifest_payload=manifest_payload,
            authority_receipt=authority_receipt,
        )

    def verify_promotion(
        self,
        *,
        release_id: str,
        manifest_sha256: str,
        manifest_payload: Mapping[str, Any] | BaseModel,
        authority_receipt: AuthorityApprovalReceipt,
    ) -> ApprovalGateReceipt:
        return self._verify(
            release_id=release_id,
            manifest_sha256=manifest_sha256,
            manifest_payload=manifest_payload,
            authority_receipt=authority_receipt,
        )

    def _verify(
        self,
        *,
        release_id: str,
        manifest_sha256: str,
        manifest_payload: Mapping[str, Any] | BaseModel,
        authority_receipt: AuthorityApprovalReceipt,
    ) -> ApprovalGateReceipt:
        registry = load_release_approval_registry(self.registry_path)
        checked_at = self.clock()
        if checked_at.tzinfo is None or checked_at.utcoffset() is None:
            raise ReleaseApprovalError("approval verifier clock must be timezone-aware")

        manifest = _plain_mapping(manifest_payload)
        manifest_registry_sha = str(manifest.get("approval_registry_sha256") or "").upper()
        reasons = list(validate_registry_structure(registry, repo_root=self.repo_root))
        if manifest_registry_sha != registry.registry_sha256:
            reasons.append("manifest_registry_digest_mismatch")

        manifest_scopes = self._manifest_scope_identities(manifest, reasons=reasons)
        pending_scope_entries = tuple(
            entry for entry in registry.entries if entry.scope_mapping.status == "PENDING"
        )
        for entry in pending_scope_entries:
            reasons.append(f"scope_mapping_pending:{entry.approval_id}")
        applicable_entries: tuple[ReleaseApprovalRegistryEntry, ...] = ()
        if not pending_scope_entries:
            applicable_entries = tuple(
                entry
                for entry in registry.entries
                if (
                    entry.scope_mapping.scope_kind,
                    entry.scope_mapping.scope_key,
                )
                in manifest_scopes
            )
            if not applicable_entries:
                reasons.append("no_applicable_approval_requirements")

        requirements = self._manifest_requirements(manifest, reasons=reasons)
        applicable_requirements = {
            (
                entry.approval_id,
                entry.subject_kind,
                entry.subject_key,
                tuple(entry.required_states),
            )
            for entry in applicable_entries
        }
        if not pending_scope_entries and requirements != applicable_requirements:
            reasons.append("manifest_approval_requirements_mismatch")

        if authority_receipt.release_id != release_id:
            reasons.append("authority_receipt_release_mismatch")
        if authority_receipt.manifest_sha256 != str(manifest_sha256).upper():
            reasons.append("authority_receipt_manifest_mismatch")
        if authority_receipt.registry_sha256 != registry.registry_sha256:
            reasons.append("authority_receipt_registry_mismatch")
        if authority_receipt.decision != "approved":
            reasons.append("authority_receipt_decision_not_approved")
        self._append_time_reasons(
            authority_receipt,
            checked_at=checked_at,
            reasons=reasons,
        )

        subjects_by_id = {subject.approval_id: subject for subject in authority_receipt.subjects}
        if not pending_scope_entries and set(subjects_by_id) != {
            entry.approval_id for entry in applicable_entries
        }:
            reasons.append("authority_receipt_subject_set_mismatch")
        for entry in applicable_entries:
            subject = subjects_by_id.get(entry.approval_id)
            if entry.authority_policy_id == "PENDING":
                reasons.append(f"authority_policy_pending:{entry.approval_id}")
            if subject is None:
                continue
            if (subject.subject_kind, subject.subject_key) != (
                entry.subject_kind,
                entry.subject_key,
            ):
                reasons.append(f"authority_subject_mismatch:{entry.approval_id}")
            if subject.authority_policy_id != entry.authority_policy_id:
                reasons.append(f"authority_policy_mismatch:{entry.approval_id}")
            if entry.scope_mapping.status == "mapped" and (
                subject.scope_kind,
                subject.scope_key,
            ) != (entry.scope_mapping.scope_kind, entry.scope_mapping.scope_key):
                reasons.append(f"authority_scope_mismatch:{entry.approval_id}")
            if subject.decision != "approved":
                reasons.append(f"authority_decision_not_approved:{entry.approval_id}")
            for state_name in entry.required_states:
                if not getattr(subject.states, state_name):
                    reasons.append(
                        f"approval_required_state_missing:{state_name}:{entry.approval_id}"
                    )

        if not reasons:
            if self.authority_attestation_verifier is None:
                reasons.append("authority_attestation_verifier_not_configured")
            else:
                try:
                    trusted = self.authority_attestation_verifier.verify(authority_receipt)
                # Verifier adapters are a trust boundary: any adapter fault denies approval.
                except Exception:  # noqa: BLE001
                    trusted = False
                if trusted is not True:
                    reasons.append("authority_attestation_not_verified")

        evidence_statuses: tuple[ApprovalGateSubjectStatus, ...] = ()
        if not reasons:
            evidence_statuses = execute_registry_evidence(
                registry,
                entries=applicable_entries,
                repo_root=self.repo_root,
            )
            evidence_by_id = {status.approval_id: status for status in evidence_statuses}
            for entry in applicable_entries:
                subject = subjects_by_id[entry.approval_id]
                evidence = evidence_by_id[entry.approval_id]
                for state_name in (
                    "evidence_captured",
                    "machine_validated",
                    "formal_use_allowed",
                    "closure_approved",
                ):
                    if getattr(subject.states, state_name) != getattr(
                        evidence.states,
                        state_name,
                    ):
                        reasons.append(
                            f"evidence_state_mismatch:{state_name}:{entry.approval_id}"
                        )
                if subject.evidence_receipt_sha256 != evidence.evidence_receipt_sha256:
                    reasons.append(f"evidence_receipt_mismatch:{entry.approval_id}")

        final_registry = load_release_approval_registry(self.registry_path)
        final_checked_at = self.clock()
        if final_checked_at.tzinfo is None or final_checked_at.utcoffset() is None:
            raise ReleaseApprovalError("approval verifier clock must be timezone-aware")
        reasons.extend(validate_registry_structure(final_registry, repo_root=self.repo_root))
        if final_registry.registry_sha256 != registry.registry_sha256:
            reasons.append("approval_registry_changed_during_verification")
        if manifest_registry_sha != final_registry.registry_sha256:
            reasons.append("manifest_registry_digest_mismatch")
        if authority_receipt.registry_sha256 != final_registry.registry_sha256:
            reasons.append("authority_receipt_registry_mismatch")
        self._append_time_reasons(
            authority_receipt,
            checked_at=final_checked_at,
            reasons=reasons,
        )
        if not reasons and self.authority_attestation_verifier is not None:
            try:
                finally_trusted = self.authority_attestation_verifier.verify(
                    authority_receipt
                )
            # Recheck faults must invalidate trust after evidence execution as well.
            except Exception:  # noqa: BLE001
                finally_trusted = False
            if finally_trusted is not True:
                reasons.append("authority_attestation_changed_during_verification")
        registry = final_registry
        checked_at = final_checked_at

        gate_subjects = tuple(
            ApprovalGateSubjectStatus(
                approval_id=subject.approval_id,
                subject_kind=subject.subject_kind,
                subject_key=subject.subject_key,
                states=subject.states,
                evidence_receipt_sha256=subject.evidence_receipt_sha256,
            )
            for subject in authority_receipt.subjects
        )
        gate = build_approval_gate_receipt(
            {
                "status": "blocked" if reasons else "passed",
                "reason_codes": tuple(dict.fromkeys(reasons)),
                "release_id": release_id,
                "manifest_sha256": str(manifest_sha256).upper(),
                "registry_sha256": registry.registry_sha256,
                "authority_receipt_sha256": authority_receipt.receipt_sha256,
                "checked_at": checked_at,
                "subjects": gate_subjects,
            }
        )
        if reasons:
            raise ApprovalVerificationBlocked(gate)
        return gate

    @staticmethod
    def _append_time_reasons(
        authority_receipt: AuthorityApprovalReceipt,
        *,
        checked_at: datetime,
        reasons: list[str],
    ) -> None:
        if authority_receipt.decided_at > checked_at:
            reasons.append("authority_receipt_not_yet_effective")
        if (
            authority_receipt.expires_at is not None
            and checked_at >= authority_receipt.expires_at
        ):
            reasons.append("authority_receipt_expired")
        if authority_receipt.revoked_at is not None:
            reasons.append("authority_receipt_revoked")

    @staticmethod
    def _manifest_scope_identities(
        manifest: Mapping[str, Any],
        *,
        reasons: list[str],
    ) -> set[tuple[str, str]]:
        raw_scopes = manifest.get("scopes")
        if not isinstance(raw_scopes, Sequence) or isinstance(
            raw_scopes,
            (str, bytes, bytearray),
        ):
            reasons.append("manifest_scopes_invalid")
            return set()
        identities: list[tuple[str, str]] = []
        for raw in raw_scopes:
            if not isinstance(raw, Mapping):
                reasons.append("manifest_scopes_invalid")
                continue
            scope_kind = str(raw.get("scope_kind") or "").strip()
            scope_key = str(raw.get("scope_key") or "").strip()
            if scope_kind not in {"logical_lane", "physical_bundle"} or not scope_key:
                reasons.append("manifest_scopes_invalid")
                continue
            identities.append((scope_kind, scope_key))
        if len(identities) != len(set(identities)):
            reasons.append("manifest_scopes_invalid")
        return set(identities)

    @staticmethod
    def _manifest_requirements(
        manifest: Mapping[str, Any],
        *,
        reasons: list[str],
    ) -> set[tuple[str, str, str, tuple[str, ...]]]:
        raw_requirements = manifest.get("approval_requirements")
        if not isinstance(raw_requirements, Sequence) or isinstance(
            raw_requirements,
            (str, bytes, bytearray),
        ):
            reasons.append("manifest_approval_requirements_invalid")
            return set()
        requirements: set[tuple[str, str, str, tuple[str, ...]]] = set()
        approval_ids: list[str] = []
        subjects: list[tuple[str, str]] = []
        for raw in raw_requirements:
            try:
                requirement = ManifestApprovalRequirement.model_validate(raw)
            except ValidationError:
                reasons.append("manifest_approval_requirements_invalid")
                continue
            approval_ids.append(requirement.approval_id)
            subjects.append((requirement.subject_kind, requirement.subject_key))
            requirements.add(
                (
                    requirement.approval_id,
                    requirement.subject_kind,
                    requirement.subject_key,
                    tuple(requirement.required_states),
                )
            )
        if len(approval_ids) != len(set(approval_ids)) or len(subjects) != len(
            set(subjects)
        ):
            reasons.append("manifest_approval_requirements_invalid")
        return requirements
