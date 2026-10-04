from __future__ import annotations

import hashlib
import json
from typing import Any

import pytest

from tests.helpers import load_module


def _load_release_control_schema():
    return load_module(
        "backend.app.schemas.release_control",
        "backend/app/schemas/release_control.py",
    )


def _canonical_sha256(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest().upper()


def _manifest_payload() -> dict[str, Any]:
    return {
        "target_environment": "test",
        "git_sha": "0123456789abcdef0123456789abcdef01234567",
        "schema_heads": {
            "postgres": ["7d1a2c3e4f50"],
            "duckdb": ["v45"],
        },
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
                "scope_kind": "physical_bundle",
                "scope_key": "duckdb-main",
                "artifact_kind": "duckdb-main",
                "artifact_version": "duckdb-main-2026-08-31T120000Z",
                "artifact_sha256": "2" * 64,
                "evidence_sha256": "3" * 64,
                "contained_lane_versions": {
                    "bond-analytics-risk-tensor": "risk-v6",
                },
            },
        ],
    }


def _incomplete_manifest_payload() -> dict[str, Any]:
    return {
        "target_environment": "test",
        "git_sha": "0123456789abcdef0123456789abcdef01234567",
        "schema_heads": {"postgres": ["7d1a2c3e4f50"]},
    }


def test_candidate_manifest_rejects_incomplete_whole_bundle_payload() -> None:
    module = _load_release_control_schema()

    with pytest.raises(Exception):
        module.ReleaseManifest(
            release_id="release-2026-08-31-bond-risk-v1",
            state="candidate",
            payload=_incomplete_manifest_payload(),
        )


def test_release_manifest_derives_digest_from_canonical_payload() -> None:
    module = _load_release_control_schema()
    payload = _manifest_payload()

    manifest = module.ReleaseManifest(
        release_id="release-2026-08-31-bond-risk-v1",
        state="candidate",
        payload=payload,
    )

    assert manifest.content_sha256 == _canonical_sha256(manifest.payload.canonical_payload())


def test_manifest_approval_contract_keeps_unrelated_extension_fields() -> None:
    module = _load_release_control_schema()
    payload = _manifest_payload()
    payload["future_release_extension"] = {"version": "v2"}

    manifest = module.ReleaseManifest(
        release_id="release-2026-08-31-bond-risk-v1",
        state="candidate",
        payload=payload,
    )

    canonical = manifest.payload.canonical_payload()
    assert canonical["approval_registry_sha256"] == "7" * 64
    assert canonical["approval_requirements"][0]["approval_id"] == "test:release-bundle"
    assert canonical["future_release_extension"] == {"version": "v2"}


def test_approval_event_requires_manifest_digest_binding() -> None:
    module = _load_release_control_schema()

    with pytest.raises(Exception):
        module.ReleaseEvent(
            release_id="release-2026-08-31-bond-risk-v1",
            action="approve-record",
            from_state="validated",
            to_state="approved",
            event_payload={
                "approved_by": "finance-owner",
                "authority_reference": "github:env:formal-release",
            },
        )


def test_release_manifest_does_not_accept_blocked_as_a_persisted_state() -> None:
    module = _load_release_control_schema()

    with pytest.raises(Exception):
        module.ReleaseManifest(
            release_id="release-2026-08-31-bond-risk-v1",
            state="blocked",
            payload=_manifest_payload(),
        )


def test_logical_lane_alias_does_not_accept_physical_duckdb_path() -> None:
    module = _load_release_control_schema()

    with pytest.raises(Exception):
        module.ReleaseAlias(
            target_environment="test",
            scope_kind="logical_lane",
            scope_key="bond-analytics-risk-tensor",
            current_release_id="release-2026-08-31-bond-risk-v1",
            previous_release_id=None,
            revision=3,
            alias_payload={
                "duckdb_path": "F:/MOSS-V3/data/moss.duckdb",
            },
        )


def test_manifest_payload_rejects_nested_sensitive_keys() -> None:
    module = _load_release_control_schema()
    payload = _manifest_payload()
    payload["builds"]["backend"]["credential"] = {"Api_Key": "super-secret"}

    with pytest.raises(Exception):
        module.ReleaseManifest(
            release_id="release-2026-08-31-bond-risk-v1",
            state="candidate",
            payload=payload,
        )


def test_logical_lane_alias_rejects_nested_physical_paths() -> None:
    module = _load_release_control_schema()

    with pytest.raises(Exception):
        module.ReleaseAlias(
            target_environment="test",
            scope_kind="logical_lane",
            scope_key="bond-analytics-risk-tensor",
            current_release_id="release-2026-08-31-bond-risk-v1",
            previous_release_id=None,
            revision=3,
            alias_payload={
                "meta": {"database_path": "F:/MOSS-V3/data/moss.duckdb"},
            },
        )
