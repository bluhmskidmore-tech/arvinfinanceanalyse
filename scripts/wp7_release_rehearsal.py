from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.governance.release_control import (  # noqa: E402
    ReleaseControlError,
    ReleaseControlService,
)
from backend.app.repositories.release_control_repo import (  # noqa: E402
    ReleaseControlRepository,
)
from backend.app.governance.exact_numeric_policy import (  # noqa: E402
    build_exact_numeric_policy,
)
from backend.app.schemas.release_approval import (  # noqa: E402
    ApprovalGateSubjectStatus,
    AuthorityApprovalReceipt,
    build_approval_gate_receipt,
    build_authority_approval_receipt,
)
from backend.app.schemas.release_control import canonical_sha256  # noqa: E402

TARGET_ENVIRONMENT = "wp7-rehearsal"
RECEIPT_SCHEMA = "wp7-release-rehearsal/v1"
VERIFICATION_SCHEMA = "wp7-release-rehearsal-verification/v1"
_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_SHA256_RE = re.compile(r"^[0-9A-F]{64}$")
_MAX_RECEIPT_BYTES = 4 * 1024 * 1024
_APPROVAL_ID = "wp7-rehearsal:whole-bundle"
_SUBJECT_KEY = "wp7-rehearsal-bundle"
_SCOPE_IDENTITIES = (
    ("physical_bundle", "duckdb-main"),
    ("logical_lane", "bond-analytics-core"),
    ("logical_lane", "bond-analytics-risk-tensor"),
)
_ARTIFACT_RELATIVE_PATHS = {
    "baseline_bundle": Path("bundles") / "baseline.duckdb",
    "candidate_bundle": Path("bundles") / "candidate.duckdb",
    "backup_bundle": Path("backups") / "baseline.duckdb",
    "control_db": Path("release-control.sqlite3"),
}


class RehearsalError(RuntimeError):
    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        self.detail = detail or code
        super().__init__(self.detail)


class _RehearsalReleaseControlService(ReleaseControlService):
    """Permit synthetic gates only for the workspace-bound SQLite authority."""

    def __init__(
        self,
        *,
        repo: ReleaseControlRepository,
        workspace: Path,
    ) -> None:
        expected_database = (
            workspace / _ARTIFACT_RELATIVE_PATHS["control_db"]
        ).resolve(strict=False)
        configured_database = Path(str(repo.engine.url.database or "")).resolve(
            strict=False
        )
        if (
            repo.engine.dialect.name != "sqlite"
            or configured_database != expected_database
        ):
            raise RehearsalError("rehearsal_control_authority_not_isolated")
        _assert_no_symlink_or_junction(expected_database, field_name="control_db")
        _assert_regular_artifact(expected_database)
        super().__init__(
            repo=repo,
            approval_verifier=_RehearsalOnlyApprovalVerifier(),
        )

    def record_validation(
        self,
        release_id: str,
        validation_receipts: Mapping[str, Any] | None = None,
        *,
        receipt: Mapping[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> Any:
        receipts = validation_receipts if validation_receipts is not None else receipt
        manifest, _stored = self._require_manifest(release_id)
        if not isinstance(receipts, Mapping):
            raise RehearsalError("rehearsal_validation_receipts_invalid")
        for value in receipts.values():
            if (
                not isinstance(value, Mapping)
                or value.get("release_id") != release_id
                or value.get("manifest_sha256") != manifest.content_sha256
                or value.get("target_environment") != TARGET_ENVIRONMENT
            ):
                raise RehearsalError("rehearsal_validation_binding_mismatch")
        return super().record_validation(
            release_id,
            validation_receipts=receipts,
            idempotency_key=idempotency_key,
        )

    @staticmethod
    def _failed_validation_gates(
        receipts: Mapping[str, Any],
        *,
        required_gates: Sequence[str],
    ) -> list[str]:
        required = set(required_gates)
        if set(receipts) != required:
            return ["rehearsal_gate_set_mismatch"]
        failed: list[str] = []
        for gate in required_gates:
            value = receipts.get(gate)
            if not isinstance(value, Mapping):
                failed.append(gate)
                continue
            body = {key: item for key, item in value.items() if key != "receipt_sha256"}
            if (
                value.get("schema_version") != "wp7-rehearsal-synthetic-validation/v1"
                or value.get("gate") != gate
                or value.get("status") != "passed"
                or value.get("rehearsal_only") is not True
                or value.get("synthetic_evidence") is not True
                or value.get("structure_only") is not True
                or value.get("release_gate_eligible") is not False
                or value.get("gate_scope") != "rehearsal_only"
                or str(value.get("receipt_sha256") or "").upper()
                != canonical_sha256(body)
            ):
                failed.append(gate)
        return failed


class _RehearsalOnlyApprovalVerifier:
    """Synthetic authority adapter restricted to the isolated rehearsal target."""

    @staticmethod
    def _verify(
        *,
        release_id: str,
        manifest_sha256: str,
        manifest_payload: Mapping[str, Any] | Any,
        authority_receipt: AuthorityApprovalReceipt,
    ) -> Any:
        manifest = (
            manifest_payload.model_dump(mode="json")
            if hasattr(manifest_payload, "model_dump")
            else dict(manifest_payload)
        )
        if (
            manifest.get("target_environment") != TARGET_ENVIRONMENT
            or manifest.get("rehearsal_only") is not True
            or manifest.get("synthetic_evidence") is not True
        ):
            raise RehearsalError("rehearsal_approval_target_mismatch")
        if not authority_receipt.authority_reference.startswith("wp7-rehearsal:"):
            raise RehearsalError("rehearsal_authority_reference_mismatch")
        if (
            authority_receipt.release_id != release_id
            or authority_receipt.manifest_sha256 != manifest_sha256
            or authority_receipt.registry_sha256
            != manifest.get("approval_registry_sha256")
        ):
            raise RehearsalError("rehearsal_authority_binding_mismatch")

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

    def verify_record_approval(self, **kwargs: Any) -> Any:
        return self._verify(**kwargs)

    def verify_promotion(self, **kwargs: Any) -> Any:
        return self._verify(**kwargs)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _assert_no_symlink_or_junction(path: Path, *, field_name: str) -> None:
    current = Path(path.anchor) if path.is_absolute() else Path(".")
    parts = path.parts[1:] if path.is_absolute() else path.parts
    reparse_mask = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    for part in parts:
        current /= part
        if not os.path.lexists(current):
            continue
        try:
            metadata = current.stat(follow_symlinks=False)
        except OSError as exc:
            raise RehearsalError(f"{field_name}_identity_unavailable") from exc
        is_junction = getattr(current, "is_junction", lambda: False)
        file_attributes = int(getattr(metadata, "st_file_attributes", 0))
        if (
            current.is_symlink()
            or is_junction()
            or bool(file_attributes & reparse_mask)
        ):
            raise RehearsalError(f"{field_name}_contains_symlink_or_junction")


def _path_identity(path: Path, *, field_name: str) -> tuple[int, int]:
    try:
        metadata = path.stat(follow_symlinks=False)
    except OSError as exc:
        raise RehearsalError(f"{field_name}_identity_unavailable") from exc
    return int(metadata.st_dev), int(metadata.st_ino)


def _assert_workspace_layout(workspace: Path) -> None:
    for field_name, path in (
        ("workspace_root", workspace),
        ("workspace_bundles", workspace / "bundles"),
        ("workspace_backups", workspace / "backups"),
    ):
        _assert_no_symlink_or_junction(path, field_name=field_name)
        if not path.is_dir():
            raise RehearsalError(f"{field_name}_identity_invalid")


def _hashed_receipt(body: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(body)
    payload.pop("receipt_sha256", None)
    return {**payload, "receipt_sha256": canonical_sha256(payload)}


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(
            dict(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _model_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        dumped = value.model_dump(mode="json", exclude_none=True)
    elif isinstance(value, Mapping):
        dumped = dict(value)
    else:
        raise RehearsalError("unsupported_release_control_receipt")
    if not isinstance(dumped, dict):
        raise RehearsalError("unsupported_release_control_receipt")
    return dumped


def _resolve_host_environment(host_environment: str | None) -> str:
    observed = str(os.environ.get("MOSS_ENVIRONMENT", "") or "").strip().lower()
    requested = str(host_environment or "").strip().lower()
    if observed and requested and observed != requested:
        raise RehearsalError("host_environment_mismatch")
    resolved = requested or observed or "development"
    if resolved == "production":
        raise RehearsalError("production_environment_forbidden")
    if resolved not in {"development", "test", "staging"}:
        raise RehearsalError("host_environment_invalid")
    return resolved


def _resolve_run_id(run_id: str | None) -> str:
    resolved = str(run_id or "").strip()
    if not resolved:
        resolved = datetime.now(UTC).strftime("wp7-%Y%m%dT%H%M%S%fZ")
    if not _RUN_ID_RE.fullmatch(resolved):
        raise RehearsalError("run_id_invalid")
    return resolved


def _normalize_new_workspace(workspace_root: str | Path) -> Path:
    raw = os.fspath(workspace_root)
    if not raw or raw.startswith("~") or "$" in raw or re.search(r"%[^%]+%", raw):
        raise RehearsalError("workspace_root_must_be_absolute")
    requested = Path(raw)
    if not requested.is_absolute():
        raise RehearsalError("workspace_root_must_be_absolute")
    if requested.exists() or os.path.lexists(requested):
        raise RehearsalError("workspace_root_must_not_exist")
    if requested.name in {"", ".", ".."}:
        raise RehearsalError("workspace_root_invalid")

    parent = requested.parent
    _assert_no_symlink_or_junction(parent, field_name="workspace_parent")
    if not parent.is_dir():
        raise RehearsalError("workspace_parent_invalid")
    resolved_parent = parent.resolve(strict=True)
    normalized = resolved_parent / requested.name
    if os.path.normcase(str(requested)) != os.path.normcase(str(normalized)):
        raise RehearsalError("workspace_root_must_be_normalized")
    protected = {
        ROOT.resolve(),
        Path.home().resolve(),
        Path(requested.anchor).resolve(),
    }
    if normalized in protected or resolved_parent == Path(requested.anchor).resolve():
        raise RehearsalError("workspace_root_protected")
    return normalized


def _create_workspace(path: Path) -> None:
    _assert_no_symlink_or_junction(path.parent, field_name="workspace_parent")
    parent_before = _path_identity(path.parent, field_name="workspace_parent")
    try:
        path.mkdir()
    except FileExistsError as exc:
        raise RehearsalError("workspace_root_must_not_exist") from exc
    parent_after = _path_identity(path.parent, field_name="workspace_parent")
    if parent_before != parent_after:
        raise RehearsalError("workspace_parent_identity_changed")
    _assert_no_symlink_or_junction(path, field_name="workspace_root")
    if not path.is_dir():
        raise RehearsalError("workspace_root_identity_invalid")
    root_identity = _path_identity(path, field_name="workspace_root")
    (path / "bundles").mkdir()
    (path / "backups").mkdir()
    _assert_workspace_layout(path)
    if _path_identity(path, field_name="workspace_root") != root_identity:
        raise RehearsalError("workspace_root_identity_changed")


def _git_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    value = result.stdout.strip().lower()
    if result.returncode != 0 or re.fullmatch(r"[0-9a-f]{40}", value) is None:
        raise RehearsalError("git_sha_unavailable")
    return value


def _create_synthetic_bundle(path: Path, *, release_id: str, ordinal: int) -> None:
    _assert_no_symlink_or_junction(path, field_name="synthetic_bundle_path")
    if os.path.lexists(path):
        raise RehearsalError("synthetic_bundle_path_must_be_new")
    # Lazy import keeps receipt verification independent of DuckDB.
    from backend.app.tasks.wp7_rehearsal_bundle import (
        SyntheticBundleError,
        create_synthetic_bundle,
    )

    try:
        create_synthetic_bundle(
            path=path,
            workspace=path.parent.parent,
            release_id=release_id,
            ordinal=ordinal,
        )
    except SyntheticBundleError as exc:
        raise RehearsalError(exc.code) from exc


def _assert_sha256(path: Path, expected_sha256: str, *, code: str) -> None:
    if _sha256_file(path) != expected_sha256:
        raise RehearsalError(code)


def _manifest_payload(
    *,
    release_id: str,
    bundle_sha256: str,
    git_sha: str,
) -> dict[str, Any]:
    lane_versions = {
        "bond-analytics-core": f"{release_id}-bond-v6",
        "bond-analytics-risk-tensor": f"{release_id}-risk-v6",
    }
    evidence_sha256 = canonical_sha256(
        {
            "schema_version": RECEIPT_SCHEMA,
            "release_id": release_id,
            "bundle_sha256": bundle_sha256,
            "synthetic_evidence": True,
        }
    )
    registry_sha256 = canonical_sha256(
        {
            "registry_id": "wp7-rehearsal-synthetic-only",
            "approval_id": _APPROVAL_ID,
            "target_environment": TARGET_ENVIRONMENT,
        }
    )
    numeric_policy = build_exact_numeric_policy(rehearsal_only=True)
    return {
        "target_environment": TARGET_ENVIRONMENT,
        "git_sha": git_sha,
        "schema_heads": {"postgres": ["rehearsal-only"], "duckdb": ["synthetic-v1"]},
        "builds": {
            "backend": {
                "git_sha": git_sha,
                "build_sha256": canonical_sha256(
                    {"kind": "backend", "git_sha": git_sha, "rehearsal_only": True}
                ),
            },
            "frontend": {
                "git_sha": git_sha,
                "build_sha256": canonical_sha256(
                    {"kind": "frontend", "git_sha": git_sha, "rehearsal_only": True}
                ),
            },
        },
        "scopes": [
            {
                "scope_kind": "logical_lane",
                "scope_key": "bond-analytics-core",
                "artifact_kind": "bond-analytics-candidate",
                "artifact_version": lane_versions["bond-analytics-core"],
                "artifact_sha256": bundle_sha256,
                "evidence_sha256": evidence_sha256,
                "alias_payload": {"rehearsal_only": True},
            },
            {
                "scope_kind": "logical_lane",
                "scope_key": "bond-analytics-risk-tensor",
                "artifact_kind": "bond-risk-tensor-candidate",
                "artifact_version": lane_versions["bond-analytics-risk-tensor"],
                "artifact_sha256": bundle_sha256,
                "evidence_sha256": evidence_sha256,
                "alias_payload": {"rehearsal_only": True},
            },
            {
                "scope_kind": "physical_bundle",
                "scope_key": "duckdb-main",
                "artifact_kind": "duckdb-main",
                "artifact_version": f"{release_id}-duckdb-main",
                "artifact_sha256": bundle_sha256,
                "evidence_sha256": evidence_sha256,
                "contained_lane_versions": lane_versions,
                "alias_payload": {
                    "rehearsal_only": True,
                    "bundle_sha256": bundle_sha256,
                },
            },
        ],
        "contracts": {
            "openapi_sha256": canonical_sha256(
                {"contract": "openapi", "git_sha": git_sha, "rehearsal_only": True}
            ),
            "dto_sha256": canonical_sha256(
                {"contract": "dto", "git_sha": git_sha, "rehearsal_only": True}
            ),
            "receipt_sha256": canonical_sha256(
                {"contract": "receipt", "schema_version": RECEIPT_SCHEMA}
            ),
        },
        "numeric_policy": numeric_policy,
        "required_validation_gates": ["schema", "contracts", "governance"],
        "approval_registry_sha256": registry_sha256,
        "approval_requirements": [
            {
                "approval_id": _APPROVAL_ID,
                "subject_kind": "page",
                "subject_key": _SUBJECT_KEY,
                "required_states": [
                    "evidence_captured",
                    "machine_validated",
                    "business_approved",
                    "formal_use_allowed",
                    "closure_approved",
                ],
            }
        ],
        "rehearsal_only": True,
        "synthetic_evidence": True,
        "production_release_gate_eligible": False,
    }


def _validation_receipts(
    *,
    release_id: str,
    manifest_sha256: str,
) -> dict[str, dict[str, Any]]:
    receipts: dict[str, dict[str, Any]] = {}
    for gate in ("schema", "contracts", "governance"):
        body = {
            "schema_version": "wp7-rehearsal-synthetic-validation/v1",
            "gate": gate,
            "status": "passed",
            "release_gate_eligible": False,
            "rehearsal_only": True,
            "synthetic_evidence": True,
            "structure_only": True,
            "gate_scope": "rehearsal_only",
            "release_id": release_id,
            "manifest_sha256": manifest_sha256,
            "target_environment": TARGET_ENVIRONMENT,
        }
        receipts[gate] = {**body, "receipt_sha256": canonical_sha256(body)}
    return receipts


def _authority_receipt(
    *,
    release_id: str,
    manifest_sha256: str,
    registry_sha256: str,
) -> AuthorityApprovalReceipt:
    now = datetime.now(UTC)
    evidence_sha256 = canonical_sha256(
        {
            "release_id": release_id,
            "manifest_sha256": manifest_sha256,
            "rehearsal_only": True,
        }
    )
    return build_authority_approval_receipt(
        {
            "release_id": release_id,
            "manifest_sha256": manifest_sha256,
            "registry_sha256": registry_sha256,
            "authority_reference": f"wp7-rehearsal:{release_id}",
            "authority_verifier_receipt_sha256": canonical_sha256(
                {"authority": "synthetic-rehearsal", "release_id": release_id}
            ),
            "decision": "approved",
            "decided_at": now - timedelta(minutes=1),
            "expires_at": now + timedelta(hours=1),
            "revoked_at": None,
            "revocation_reference": None,
            "subjects": [
                {
                    "approval_id": _APPROVAL_ID,
                    "subject_kind": "page",
                    "subject_key": _SUBJECT_KEY,
                    "authority_policy_id": "wp7-rehearsal-synthetic-only",
                    "scope_kind": "physical_bundle",
                    "scope_key": "duckdb-main",
                    "decision": "approved",
                    "states": {
                        "evidence_captured": True,
                        "machine_validated": True,
                        "business_approved": True,
                        "formal_use_allowed": True,
                        "closure_approved": True,
                    },
                    "evidence_receipt_sha256": evidence_sha256,
                }
            ],
        }
    )


def _scope_expectations(expected_revision: int) -> list[dict[str, Any]]:
    return [
        {
            "scope_kind": scope_kind,
            "scope_key": scope_key,
            "expected_revision": expected_revision,
        }
        for scope_kind, scope_key in _SCOPE_IDENTITIES
    ]


def _prepare_approved(
    service: ReleaseControlService,
    *,
    release_id: str,
    payload: Mapping[str, Any],
) -> tuple[str, dict[str, Any]]:
    prepared = service.prepare_release(
        release_id=release_id,
        payload=payload,
        freeze=True,
        idempotency_key=f"{release_id}:prepare",
    )
    digest = str(prepared.manifest_digest)
    validated = service.record_validation(
        release_id,
        validation_receipts=_validation_receipts(
            release_id=release_id,
            manifest_sha256=digest,
        ),
        idempotency_key=f"{release_id}:validate",
    )
    authority = _authority_receipt(
        release_id=release_id,
        manifest_sha256=digest,
        registry_sha256=str(payload["approval_registry_sha256"]),
    )
    approved = service.record_approval(
        release_id=release_id,
        manifest_digest=digest,
        authority_receipt=authority,
        idempotency_key=f"{release_id}:approve",
    )
    return digest, {
        "prepare": _model_dict(prepared),
        "validate": _model_dict(validated),
        "approve": _model_dict(approved),
        "authority_receipt_sha256": authority.receipt_sha256,
    }


def _state_snapshot(
    service: ReleaseControlService,
    release_ids: Sequence[str],
) -> dict[str, Any]:
    return {
        release_id: _model_dict(service.show_release(release_id))
        for release_id in release_ids
    }


def _state_sha256(
    service: ReleaseControlService,
    release_ids: Sequence[str],
) -> str:
    return canonical_sha256(_state_snapshot(service, release_ids))


def _aliases_by_identity(
    aliases: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    return {
        f"{alias['scope_kind']}:{alias['scope_key']}": dict(alias) for alias in aliases
    }


def _assert_alias_snapshot(
    aliases: Sequence[Mapping[str, Any]],
    *,
    current_release_id: str,
    previous_release_id: str,
    revision: int,
) -> None:
    indexed = _aliases_by_identity(aliases)
    expected = {f"{kind}:{key}" for kind, key in _SCOPE_IDENTITIES}
    if set(indexed) != expected:
        raise RehearsalError("alias_scope_set_mismatch")
    if any(
        alias.get("current_release_id") != current_release_id
        or alias.get("previous_release_id") != previous_release_id
        or alias.get("revision") != revision
        for alias in indexed.values()
    ):
        raise RehearsalError("alias_restore_invariant_failed")


def _event_prefix_preserved(
    before: Mapping[str, Any], after: Mapping[str, Any]
) -> bool:
    for release_id, before_view in before.items():
        after_view = after.get(release_id)
        if not isinstance(after_view, Mapping):
            return False
        before_events = before_view.get("events")
        after_events = after_view.get("events")
        if not isinstance(before_events, list) or not isinstance(after_events, list):
            return False
        if after_events[: len(before_events)] != before_events:
            return False
    return True


def _tamper_probe(
    service: ReleaseControlService,
    *,
    release_ids: Sequence[str],
    candidate_path: Path,
    expected_sha256: str,
) -> dict[str, Any]:
    before_sha256 = _state_sha256(service, release_ids)
    original = candidate_path.read_bytes()
    tampered = bytearray(original)
    tampered[0] ^= 0x01
    candidate_path.write_bytes(tampered)
    try:
        try:
            _assert_sha256(
                candidate_path,
                expected_sha256,
                code="candidate_bundle_sha256_mismatch",
            )
        except RehearsalError as exc:
            if exc.code != "candidate_bundle_sha256_mismatch":
                raise
            status = "rejected"
        else:
            raise RehearsalError("candidate_tamper_probe_not_rejected")
    finally:
        candidate_path.write_bytes(original)
    _assert_sha256(
        candidate_path,
        expected_sha256,
        code="candidate_bundle_restore_failed",
    )
    after_sha256 = _state_sha256(service, release_ids)
    if after_sha256 != before_sha256:
        raise RehearsalError("candidate_tamper_probe_changed_release_state")
    return {
        "status": status,
        "error_code": "candidate_bundle_sha256_mismatch",
        "before_state_sha256": before_sha256,
        "after_state_sha256": after_sha256,
        "state_unchanged": True,
    }


def _incomplete_scope_probe(
    service: ReleaseControlService,
    *,
    release_ids: Sequence[str],
    release_id: str,
    manifest_digest: str,
) -> dict[str, Any]:
    before_sha256 = _state_sha256(service, release_ids)
    try:
        service.promote_release_bundle(
            release_id=release_id,
            manifest_digest=manifest_digest,
            scopes=_scope_expectations(1)[:-1],
            idempotency_key=f"{release_id}:incomplete-scope-probe",
        )
    except ReleaseControlError:
        status = "rejected"
    else:
        raise RehearsalError("incomplete_scope_probe_not_rejected")
    after_sha256 = _state_sha256(service, release_ids)
    if after_sha256 != before_sha256:
        raise RehearsalError("incomplete_scope_probe_changed_release_state")
    return {
        "status": status,
        "error_code": "incomplete_scope_plan_rejected",
        "before_state_sha256": before_sha256,
        "after_state_sha256": after_sha256,
        "state_unchanged": True,
    }


def _run_state_machine(
    *,
    workspace: Path,
    run_id: str,
    candidate_path: Path,
    baseline_sha256: str,
    candidate_sha256: str,
) -> dict[str, Any]:
    control_db = workspace / _ARTIFACT_RELATIVE_PATHS["control_db"]
    _assert_workspace_layout(workspace)
    _assert_no_symlink_or_junction(control_db, field_name="control_db")
    if os.path.lexists(control_db):
        raise RehearsalError("control_db_must_be_new")
    repo = ReleaseControlRepository(sql_dsn=f"sqlite:///{control_db.as_posix()}")
    service = _RehearsalReleaseControlService(
        repo=repo,
        workspace=workspace,
    )
    release_a = f"{run_id}-baseline-a"
    release_b = f"{run_id}-candidate-b"
    release_ids = (release_a, release_b)
    git_sha = _git_sha()
    try:
        digest_a, setup_a = _prepare_approved(
            service,
            release_id=release_a,
            payload=_manifest_payload(
                release_id=release_a,
                bundle_sha256=baseline_sha256,
                git_sha=git_sha,
            ),
        )
        baseline_promote_receipt = service.promote_release_bundle(
            release_id=release_a,
            manifest_digest=digest_a,
            scopes=_scope_expectations(0),
            idempotency_key=f"{run_id}:promote-baseline",
        )
        baseline_snapshot = _state_snapshot(service, (release_a,))

        digest_b, setup_b = _prepare_approved(
            service,
            release_id=release_b,
            payload=_manifest_payload(
                release_id=release_b,
                bundle_sha256=candidate_sha256,
                git_sha=git_sha,
            ),
        )
        negative_probes = {
            "candidate_checksum_tamper": _tamper_probe(
                service,
                release_ids=release_ids,
                candidate_path=candidate_path,
                expected_sha256=candidate_sha256,
            ),
            "incomplete_scope_plan": _incomplete_scope_probe(
                service,
                release_ids=release_ids,
                release_id=release_b,
                manifest_digest=digest_b,
            ),
        }

        _assert_sha256(
            candidate_path,
            candidate_sha256,
            code="candidate_bundle_sha256_mismatch",
        )
        candidate_promote_receipt = service.promote_release_bundle(
            release_id=release_b,
            manifest_digest=digest_b,
            scopes=_scope_expectations(1),
            idempotency_key=f"{run_id}:promote-candidate",
        )
        candidate_snapshot = _state_snapshot(service, release_ids)
        candidate_aliases = candidate_snapshot[release_b]["aliases"]
        _assert_alias_snapshot(
            candidate_aliases,
            current_release_id=release_b,
            previous_release_id=release_a,
            revision=2,
        )

        rollback_receipt = service.rollback_release_bundle(
            to_release_id=release_a,
            manifest_digest=digest_a,
            scopes=_scope_expectations(2),
            reason="wp7 isolated rehearsal restore invariant",
            mode="sealed_bundle_reactivate",
            idempotency_key=f"{run_id}:rollback-baseline",
        )
        rollback_replay = service.rollback_release_bundle(
            to_release_id=release_a,
            manifest_digest=digest_a,
            scopes=_scope_expectations(2),
            reason="wp7 isolated rehearsal restore invariant",
            mode="sealed_bundle_reactivate",
            idempotency_key=f"{run_id}:rollback-baseline",
        )
        if rollback_replay != rollback_receipt:
            raise RehearsalError("rollback_idempotency_replay_mismatch")

        rollback_snapshot = _state_snapshot(service, release_ids)
        rollback_aliases = rollback_snapshot[release_a]["aliases"]
        _assert_alias_snapshot(
            rollback_aliases,
            current_release_id=release_a,
            previous_release_id=release_b,
            revision=3,
        )
        if rollback_snapshot[release_b]["state"] != "rolled_back":
            raise RehearsalError("removed_candidate_not_rolled_back")
        if not _event_prefix_preserved(candidate_snapshot, rollback_snapshot):
            raise RehearsalError("event_append_only_invariant_failed")

        return {
            "git_sha": git_sha,
            "release_ids": {"baseline": release_a, "candidate": release_b},
            "manifest_digests": {"baseline": digest_a, "candidate": digest_b},
            "baseline_setup": setup_a,
            "candidate_setup": setup_b,
            "baseline_promote": {
                "receipt": _model_dict(baseline_promote_receipt),
                "aliases": baseline_snapshot[release_a]["aliases"],
                "state_sha256": canonical_sha256(baseline_snapshot),
            },
            "candidate_promote": {
                "receipt": _model_dict(candidate_promote_receipt),
                "aliases": candidate_aliases,
                "state_sha256": canonical_sha256(candidate_snapshot),
            },
            "rollback": {
                "receipt": _model_dict(rollback_receipt),
                "aliases": rollback_aliases,
                "state_sha256": canonical_sha256(rollback_snapshot),
                "idempotency_replay_equal": True,
            },
            "negative_probes": negative_probes,
            "event_append_only": True,
            "final_states": {
                release_id: view["state"]
                for release_id, view in rollback_snapshot.items()
            },
        }
    finally:
        repo.close()


def _quarantine_receipt(
    *,
    workspace: Path,
    run_id: str,
    host_environment: str,
    error: Exception,
) -> None:
    code = (
        error.code if isinstance(error, RehearsalError) else "rehearsal_runtime_error"
    )
    body = {
        "schema_version": RECEIPT_SCHEMA,
        "action": "wp7-release-rehearsal",
        "mode": "isolated-synthetic-whole-bundle",
        "run_id": run_id,
        "status": "blocked",
        "rehearsal_status": "quarantined",
        "reason_codes": [code],
        "host_environment": host_environment,
        "target_environment": TARGET_ENVIRONMENT,
        "workspace_root": str(workspace),
        "rehearsal_only": True,
        "synthetic_evidence": True,
        "structure_only": True,
        "integrity_only": True,
        "authenticity_attested": False,
        "release_gate_eligible": False,
        "wp7_production_eligible": False,
        "production_writes": False,
    }
    _write_json(workspace / "rehearsal-quarantine.json", _hashed_receipt(body))


def run_rehearsal(
    workspace_root: str | Path,
    run_id: str | None = None,
    host_environment: str | None = None,
) -> dict[str, Any]:
    """Run whole-bundle mechanics only inside a new, isolated local workspace."""

    resolved_environment = _resolve_host_environment(host_environment)
    resolved_run_id = _resolve_run_id(run_id)
    workspace = _normalize_new_workspace(workspace_root)
    _create_workspace(workspace)
    started_at = datetime.now(UTC)

    baseline_path = workspace / _ARTIFACT_RELATIVE_PATHS["baseline_bundle"]
    candidate_path = workspace / _ARTIFACT_RELATIVE_PATHS["candidate_bundle"]
    backup_path = workspace / _ARTIFACT_RELATIVE_PATHS["backup_bundle"]
    receipt_path = workspace / "rehearsal-receipt.json"
    try:
        release_a = f"{resolved_run_id}-baseline-a"
        release_b = f"{resolved_run_id}-candidate-b"
        _create_synthetic_bundle(baseline_path, release_id=release_a, ordinal=1)
        _assert_workspace_layout(workspace)
        _create_synthetic_bundle(candidate_path, release_id=release_b, ordinal=2)
        _assert_workspace_layout(workspace)
        baseline_sha256 = _sha256_file(baseline_path)
        candidate_sha256 = _sha256_file(candidate_path)
        _assert_no_symlink_or_junction(backup_path, field_name="backup_bundle")
        if os.path.lexists(backup_path):
            raise RehearsalError("backup_bundle_must_be_new")
        backup_path.write_bytes(baseline_path.read_bytes())
        _assert_workspace_layout(workspace)
        backup_sha256 = _sha256_file(backup_path)
        if backup_sha256 != baseline_sha256:
            raise RehearsalError("baseline_backup_sha256_mismatch")

        mechanics = _run_state_machine(
            workspace=workspace,
            run_id=resolved_run_id,
            candidate_path=candidate_path,
            baseline_sha256=baseline_sha256,
            candidate_sha256=candidate_sha256,
        )
        _assert_sha256(
            baseline_path,
            baseline_sha256,
            code="baseline_bundle_changed_during_rehearsal",
        )
        _assert_sha256(
            candidate_path,
            candidate_sha256,
            code="candidate_bundle_changed_during_rehearsal",
        )
        control_db = workspace / _ARTIFACT_RELATIVE_PATHS["control_db"]
        artifacts = {
            "baseline_bundle": {
                "path": str(baseline_path),
                "sha256": baseline_sha256,
                "synthetic": True,
            },
            "candidate_bundle": {
                "path": str(candidate_path),
                "sha256": candidate_sha256,
                "synthetic": True,
            },
            "backup_bundle": {
                "path": str(backup_path),
                "sha256": backup_sha256,
                "synthetic": True,
            },
            "control_db": {
                "path": str(control_db),
                "sha256": _sha256_file(control_db),
                "synthetic": True,
            },
        }
        body = {
            "schema_version": RECEIPT_SCHEMA,
            "action": "wp7-release-rehearsal",
            "mode": "isolated-synthetic-whole-bundle",
            "run_id": resolved_run_id,
            "status": "passed",
            "rehearsal_status": "rehearsal_completed",
            "reason_codes": [],
            "started_at": started_at.isoformat(),
            "finished_at": datetime.now(UTC).isoformat(),
            "host_environment": resolved_environment,
            "target_environment": TARGET_ENVIRONMENT,
            "workspace_root": str(workspace),
            "receipt_path": str(receipt_path),
            "rehearsal_only": True,
            "synthetic_evidence": True,
            "structure_only": True,
            "integrity_only": True,
            "authenticity_attested": False,
            "release_gate_eligible": False,
            "wp7_production_eligible": False,
            "production_writes": False,
            "sandbox_event_alias_writes": True,
            "artifacts": artifacts,
            **mechanics,
            "restore_invariants": {
                "candidate_promoted_as_complete_scope_set": True,
                "baseline_restored_as_complete_scope_set": True,
                "alias_revision_after_rollback": 3,
                "event_history_append_only": mechanics["event_append_only"],
                "bundle_files_unchanged": True,
                "real_release_state_unchanged": True,
            },
            "unexercised_production_controls": [
                "owner_and_authority_assignments",
                "real_writer_quiescence",
                "real_backup_and_restore",
                "production_approval_attestation",
                "external_receipt_attestation",
                "isolated_api_readiness_against_real_candidate",
                "production_observation_window",
                "approved_rto_rpo",
            ],
        }
        receipt = _hashed_receipt(body)
        _write_json(receipt_path, receipt)
        return receipt
    except Exception as exc:
        _quarantine_receipt(
            workspace=workspace,
            run_id=resolved_run_id,
            host_environment=resolved_environment,
            error=exc,
        )
        raise


def _read_receipt(path: Path) -> dict[str, Any]:
    if not path.is_absolute():
        raise RehearsalError("receipt_path_must_be_absolute")
    _assert_no_symlink_or_junction(path, field_name="receipt_path")
    try:
        metadata = path.stat(follow_symlinks=False)
        if not stat.S_ISREG(metadata.st_mode):
            raise RehearsalError("receipt_file_invalid")
        if metadata.st_size > _MAX_RECEIPT_BYTES:
            raise RehearsalError("receipt_file_too_large")
        value = json.loads(path.read_text(encoding="utf-8"))
    except RehearsalError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RehearsalError("receipt_file_invalid") from exc
    if not isinstance(value, dict):
        raise RehearsalError("receipt_file_invalid")
    return value


def _assert_regular_artifact(path: Path) -> None:
    _assert_no_symlink_or_junction(path, field_name="artifact_path")
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise RehearsalError("artifact_missing") from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise RehearsalError("artifact_identity_invalid")


def verify_rehearsal_receipt(receipt_path: str | Path) -> dict[str, Any]:
    """Verify the self-hash, fixed paths, and artifact hashes of a rehearsal receipt."""

    path = Path(receipt_path)
    receipt = _read_receipt(path)
    declared_sha256 = str(receipt.get("receipt_sha256") or "").upper()
    body = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    if not _SHA256_RE.fullmatch(declared_sha256) or declared_sha256 != canonical_sha256(
        body
    ):
        raise RehearsalError("receipt_sha256_mismatch")
    if (
        receipt.get("schema_version") != RECEIPT_SCHEMA
        or receipt.get("status") != "passed"
        or receipt.get("rehearsal_only") is not True
        or receipt.get("synthetic_evidence") is not True
        or receipt.get("structure_only") is not True
        or receipt.get("integrity_only") is not True
        or receipt.get("authenticity_attested") is not False
        or receipt.get("release_gate_eligible") is not False
        or receipt.get("wp7_production_eligible") is not False
        or receipt.get("production_writes") is not False
        or receipt.get("target_environment") != TARGET_ENVIRONMENT
    ):
        raise RehearsalError("receipt_disclosure_invariant_failed")

    workspace_raw = str(receipt.get("workspace_root") or "")
    workspace_declared = Path(workspace_raw)
    if not workspace_declared.is_absolute():
        raise RehearsalError("workspace_identity_invalid")
    _assert_no_symlink_or_junction(
        workspace_declared,
        field_name="workspace_root",
    )
    if not workspace_declared.is_dir():
        raise RehearsalError("workspace_identity_invalid")
    workspace = workspace_declared.resolve(strict=True)
    expected_receipt_path = workspace / "rehearsal-receipt.json"
    if not path.is_absolute() or path != expected_receipt_path:
        raise RehearsalError("artifact_path_mismatch")
    _assert_regular_artifact(path)
    if str(receipt.get("receipt_path") or "") != str(expected_receipt_path):
        raise RehearsalError("artifact_path_mismatch")

    artifacts = receipt.get("artifacts")
    if not isinstance(artifacts, Mapping):
        raise RehearsalError("artifact_set_invalid")
    for name, relative_path in _ARTIFACT_RELATIVE_PATHS.items():
        artifact = artifacts.get(name)
        if not isinstance(artifact, Mapping):
            raise RehearsalError("artifact_set_invalid")
        expected_path = workspace / relative_path
        declared_path = Path(str(artifact.get("path") or ""))
        if not declared_path.is_absolute() or declared_path != expected_path:
            raise RehearsalError("artifact_path_mismatch")
        _assert_regular_artifact(declared_path)
        declared_artifact_sha256 = str(artifact.get("sha256") or "").upper()
        if (
            not _SHA256_RE.fullmatch(declared_artifact_sha256)
            or _sha256_file(declared_path) != declared_artifact_sha256
        ):
            raise RehearsalError("artifact_sha256_mismatch")

    verification_body = {
        "schema_version": VERIFICATION_SCHEMA,
        "action": "verify-wp7-release-rehearsal",
        "status": "passed",
        "verified_receipt_sha256": declared_sha256,
        "run_id": receipt.get("run_id"),
        "workspace_root": str(workspace),
        "rehearsal_only": True,
        "structure_only": True,
        "integrity_only": True,
        "authenticity_attested": False,
        "release_gate_eligible": False,
        "wp7_production_eligible": False,
        "production_writes": False,
    }
    return _hashed_receipt(verification_body)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run or verify an isolated, non-production WP7 whole-bundle rehearsal.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--workspace-root", required=True)
    run.add_argument("--run-id")
    run.add_argument("--host-environment")
    verify = commands.add_parser("verify")
    verify.add_argument("--receipt-file", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    try:
        if args.command == "run":
            result = run_rehearsal(
                args.workspace_root,
                run_id=args.run_id,
                host_environment=args.host_environment,
            )
        else:
            result = verify_rehearsal_receipt(args.receipt_file)
        exit_code = 0
    except RehearsalError as exc:
        result = {
            "schema_version": RECEIPT_SCHEMA,
            "status": "blocked",
            "reason_codes": [exc.code],
            "rehearsal_only": True,
            "structure_only": True,
            "integrity_only": True,
            "authenticity_attested": False,
            "release_gate_eligible": False,
            "wp7_production_eligible": False,
            "production_writes": False,
        }
        exit_code = 1
    except Exception:
        result = {
            "schema_version": RECEIPT_SCHEMA,
            "status": "error",
            "reason_codes": ["rehearsal_runtime_error"],
            "rehearsal_only": True,
            "structure_only": True,
            "integrity_only": True,
            "authenticity_attested": False,
            "release_gate_eligible": False,
            "wp7_production_eligible": False,
            "production_writes": False,
        }
        exit_code = 2
    print(
        json.dumps(
            result,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
