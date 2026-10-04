from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from backend.app.schemas.release_approval import (
    build_approval_gate_receipt,
    build_authority_approval_receipt,
)
from tests.helpers import load_module


def _load_release_control_repo():
    return load_module(
        "backend.app.repositories.release_control_repo",
        "backend/app/repositories/release_control_repo.py",
    )


def _manifest_payload(
    release_id: str,
    *,
    target_environment: str = "test",
    include_core_lane: bool = True,
    scope_alias_payloads: dict[tuple[str, str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    alias_payloads = scope_alias_payloads or {}
    scopes: list[dict[str, Any]] = [
        {
            "scope_kind": "logical_lane",
            "scope_key": "bond-analytics-risk-tensor",
            "artifact_kind": "bond-risk-tensor-candidate",
            "artifact_version": f"{release_id}-risk-v6",
            "artifact_sha256": "F" * 64,
            "evidence_sha256": "1" * 64,
            "alias_payload": alias_payloads.get(
                ("logical_lane", "bond-analytics-risk-tensor"), {}
            ),
        }
    ]
    contained_lane_versions = {
        "bond-analytics-risk-tensor": f"{release_id}-risk-v6",
    }
    if include_core_lane:
        scopes.append(
            {
                "scope_kind": "logical_lane",
                "scope_key": "bond-analytics-core",
                "artifact_kind": "bond-analytics-candidate",
                "artifact_version": f"{release_id}-bond-v6",
                "artifact_sha256": "2" * 64,
                "evidence_sha256": "3" * 64,
                "alias_payload": alias_payloads.get(
                    ("logical_lane", "bond-analytics-core"), {}
                ),
            }
        )
        contained_lane_versions["bond-analytics-core"] = f"{release_id}-bond-v6"
    scopes.append(
        {
            "scope_kind": "physical_bundle",
            "scope_key": "duckdb-main",
            "artifact_kind": "duckdb-main",
            "artifact_version": f"{release_id}-duckdb-main",
            "artifact_sha256": "4" * 64,
            "evidence_sha256": "5" * 64,
            "contained_lane_versions": contained_lane_versions,
            "alias_payload": alias_payloads.get(("physical_bundle", "duckdb-main"), {}),
        }
    )
    return {
        "target_environment": target_environment,
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
        "scopes": scopes,
    }


def _repo(tmp_path: Path):
    module = _load_release_control_repo()
    return module.ReleaseControlRepository(
        sql_dsn=f"sqlite:///{(tmp_path / 'release-control.db').as_posix()}",
    )


def _approval_event_payload(
    *,
    release_id: str,
    manifest_digest: str,
    registry_sha256: str,
    decision: str = "approved",
    checked_at: str = "2026-08-31T00:00:00Z",
) -> dict[str, Any]:
    states = {
        "evidence_captured": True,
        "machine_validated": True,
        "business_approved": True,
        "formal_use_allowed": True,
        "closure_approved": True,
    }
    authority = build_authority_approval_receipt(
        {
            "release_id": release_id,
            "manifest_sha256": manifest_digest,
            "registry_sha256": registry_sha256,
            "authority_reference": "test-authority-attestation",
            "authority_verifier_receipt_sha256": "8" * 64,
            "decision": decision,
            "decided_at": "2026-08-01T00:00:00Z",
            "expires_at": "2099-01-01T00:00:00Z",
            "revoked_at": None,
            "revocation_reference": None,
            "subjects": [
                {
                    "approval_id": "test:release-bundle",
                    "subject_kind": "page",
                    "subject_key": "release-bundle",
                    "authority_policy_id": "test-authority-policy",
                    "scope_kind": "logical_lane",
                    "scope_key": "bond-analytics-risk-tensor",
                    "decision": decision,
                    "states": states,
                    "evidence_receipt_sha256": "9" * 64,
                }
            ],
        }
    )
    gate = build_approval_gate_receipt(
        {
            "status": "passed",
            "reason_codes": [],
            "release_id": release_id,
            "manifest_sha256": manifest_digest,
            "registry_sha256": registry_sha256,
            "authority_receipt_sha256": authority.receipt_sha256,
            "checked_at": checked_at,
            "subjects": [
                {
                    "approval_id": "test:release-bundle",
                    "subject_kind": "page",
                    "subject_key": "release-bundle",
                    "states": states,
                    "evidence_receipt_sha256": "9" * 64,
                }
            ],
        }
    )
    return {
        "authority_reference": authority.authority_reference,
        "manifest_digest": manifest_digest,
        "authority_receipt": authority.model_dump(mode="json"),
        "approval_gate_receipt": gate.model_dump(mode="json"),
    }


def _candidate_to_approved(
    repo,
    release_id: str,
    *,
    target_environment: str = "test",
    include_core_lane: bool = True,
    scope_alias_payloads: dict[tuple[str, str], dict[str, Any]] | None = None,
) -> object:
    manifest = repo.create_manifest(
        release_id=release_id,
        state="candidate",
        payload=_manifest_payload(
            release_id,
            target_environment=target_environment,
            include_core_lane=include_core_lane,
            scope_alias_payloads=scope_alias_payloads,
        ),
    )
    repo.append_event(
        release_id=release_id,
        action="validate",
        from_state="candidate",
        to_state="validated",
        manifest_digest=manifest.manifest_digest,
        target_environment=target_environment,
        event_payload={
            "validation_receipts": {
                "schema": {"status": "passed", "receipt_sha256": "D" * 64},
                "contracts": {"status": "passed", "receipt_sha256": "E" * 64},
                "governance": {"status": "passed", "receipt_sha256": "F" * 64},
            }
        },
    )
    repo.append_event(
        release_id=release_id,
        action="approve-record",
        from_state="validated",
        to_state="approved",
        manifest_digest=manifest.manifest_digest,
        target_environment=target_environment,
        event_payload=_approval_event_payload(
            release_id=release_id,
            manifest_digest=manifest.manifest_digest,
            registry_sha256=manifest.payload["approval_registry_sha256"],
        ),
    )
    return manifest


def test_create_manifest_keeps_frozen_digest_when_caller_mutates_input_payload(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    payload = _manifest_payload("release-2026-08-31-bond-risk-v1")

    stored = repo.create_manifest(
        release_id="release-2026-08-31-bond-risk-v1",
        state="candidate",
        payload=payload,
    )
    payload["git_sha"] = "tampered-after-write"

    reloaded = repo.get_manifest(stored.release_id)

    assert reloaded.payload["git_sha"] == "0123456789abcdef0123456789abcdef01234567"
    assert reloaded.content_sha256 == stored.content_sha256


def test_create_manifest_rejects_incomplete_payload_without_persisting_row(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)

    with pytest.raises(Exception):
        repo.create_manifest(
            release_id="release-incomplete",
            state="candidate",
            payload={
                "target_environment": "test",
                "git_sha": "0123456789abcdef0123456789abcdef01234567",
            },
        )

    assert repo.get_manifest("release-incomplete") is None


def test_promote_bundle_rejects_stale_scope_revision_without_partial_alias_updates(
    tmp_path: Path,
) -> None:
    # SQLite here only proves local transaction rollback semantics. The real
    # compare-and-swap concurrency race still needs PostgreSQL coverage.
    repo = _repo(tmp_path)
    release_a = _candidate_to_approved(repo, "release-a")
    release_b = _candidate_to_approved(repo, "release-b")
    repo.activate_release(
        action="promote",
        target_environment="test",
        release_id="release-a",
        manifest_digest=release_a.manifest_digest,
        scope_expectations=[
            {
                "scope_kind": "physical_bundle",
                "scope_key": "duckdb-main",
                "expected_revision": 0,
            },
            {
                "scope_kind": "logical_lane",
                "scope_key": "bond-analytics-risk-tensor",
                "expected_revision": 0,
            },
            {
                "scope_kind": "logical_lane",
                "scope_key": "bond-analytics-core",
                "expected_revision": 0,
            },
        ],
        idempotency_key="promote-2026-08-31-bootstrap",
    )

    with pytest.raises(Exception):
        repo.activate_release(
            action="promote",
            target_environment="test",
            release_id="release-b",
            manifest_digest=release_b.manifest_digest,
            scope_expectations=[
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
            idempotency_key="promote-2026-08-31-01",
        )

    aliases = repo.list_aliases(target_environment="test")
    assert {
        (alias.scope_kind, alias.scope_key, alias.current_release_id, alias.revision)
        for alias in aliases
    } == {
        ("physical_bundle", "duckdb-main", "release-a", 1),
        ("logical_lane", "bond-analytics-risk-tensor", "release-a", 1),
        ("logical_lane", "bond-analytics-core", "release-a", 1),
    }


def test_promote_bundle_replay_keeps_revision_and_event_count_stable(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    release_a = _candidate_to_approved(repo, "release-a")
    release_b = _candidate_to_approved(repo, "release-b")
    repo.activate_release(
        action="promote",
        target_environment="test",
        release_id="release-a",
        manifest_digest=release_a.manifest_digest,
        scope_expectations=[
            {
                "scope_kind": "physical_bundle",
                "scope_key": "duckdb-main",
                "expected_revision": 0,
            },
            {
                "scope_kind": "logical_lane",
                "scope_key": "bond-analytics-risk-tensor",
                "expected_revision": 0,
            },
            {
                "scope_kind": "logical_lane",
                "scope_key": "bond-analytics-core",
                "expected_revision": 0,
            },
        ],
        idempotency_key="promote-2026-08-31-bootstrap",
    )

    first = repo.activate_release(
        action="promote",
        target_environment="test",
        release_id="release-b",
        manifest_digest=release_b.manifest_digest,
        scope_expectations=[
            {
                "scope_kind": "physical_bundle",
                "scope_key": "duckdb-main",
                "expected_revision": 1,
            },
            {
                "scope_kind": "logical_lane",
                "scope_key": "bond-analytics-risk-tensor",
                "expected_revision": 1,
            },
            {
                "scope_kind": "logical_lane",
                "scope_key": "bond-analytics-core",
                "expected_revision": 1,
            },
        ],
        idempotency_key="promote-2026-08-31-02",
    )
    second = repo.activate_release(
        action="promote",
        target_environment="test",
        release_id="release-b",
        manifest_digest=release_b.manifest_digest,
        scope_expectations=[
            {
                "scope_kind": "physical_bundle",
                "scope_key": "duckdb-main",
                "expected_revision": 1,
            },
            {
                "scope_kind": "logical_lane",
                "scope_key": "bond-analytics-risk-tensor",
                "expected_revision": 1,
            },
            {
                "scope_kind": "logical_lane",
                "scope_key": "bond-analytics-core",
                "expected_revision": 1,
            },
        ],
        idempotency_key="promote-2026-08-31-02",
    )

    assert second == first
    assert (
        repo.get_alias(
            target_environment="test",
            scope_kind="physical_bundle",
            scope_key="duckdb-main",
        ).revision
        == 2
    )
    assert (
        len(
            repo.list_events(
                release_id="release-b", action="promote", target_environment="test"
            )
        )
        == 1
    )


def test_activation_atomically_persists_first_passed_gate_receipt_across_replay(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    release = _candidate_to_approved(repo, "release-a")
    first_gate = _approval_event_payload(
        release_id="release-a",
        manifest_digest=release.manifest_digest,
        registry_sha256=release.payload["approval_registry_sha256"],
        checked_at="2026-08-31T00:00:00Z",
    )["approval_gate_receipt"]
    later_gate = _approval_event_payload(
        release_id="release-a",
        manifest_digest=release.manifest_digest,
        registry_sha256=release.payload["approval_registry_sha256"],
        checked_at="2026-08-31T00:00:01Z",
    )["approval_gate_receipt"]
    activation = {
        "action": "promote",
        "target_environment": "test",
        "release_id": "release-a",
        "manifest_digest": release.manifest_digest,
        "scope_expectations": [
            {
                "scope_kind": "physical_bundle",
                "scope_key": "duckdb-main",
                "expected_revision": 0,
            },
            {
                "scope_kind": "logical_lane",
                "scope_key": "bond-analytics-risk-tensor",
                "expected_revision": 0,
            },
            {
                "scope_kind": "logical_lane",
                "scope_key": "bond-analytics-core",
                "expected_revision": 0,
            },
        ],
        "idempotency_key": "promote-gate-receipt-replay",
    }

    first = repo.activate_release(
        **activation,
        approval_gate_receipt=first_gate,
    )
    replay = repo.activate_release(
        **activation,
        approval_gate_receipt=later_gate,
    )

    assert replay == first
    assert first.approval_gate_receipt == first_gate
    events = repo.list_events(
        release_id="release-a",
        action="promote",
        target_environment="test",
    )
    assert len(events) == 1
    assert events[0].event_payload["approval_gate_receipt"] == first_gate
    assert events[0].receipt["approval_gate_receipt"] == first_gate
    assert events[0].event_payload["approval_gate_receipt"] != later_gate


def test_idempotency_key_conflict_rejects_different_bundle_request(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    release_a = _candidate_to_approved(repo, "release-a")
    release_b = _candidate_to_approved(repo, "release-b")
    repo.activate_release(
        action="promote",
        target_environment="test",
        release_id="release-a",
        manifest_digest=release_a.manifest_digest,
        scope_expectations=[
            {
                "scope_kind": "physical_bundle",
                "scope_key": "duckdb-main",
                "expected_revision": 0,
            },
            {
                "scope_kind": "logical_lane",
                "scope_key": "bond-analytics-risk-tensor",
                "expected_revision": 0,
            },
            {
                "scope_kind": "logical_lane",
                "scope_key": "bond-analytics-core",
                "expected_revision": 0,
            },
        ],
        idempotency_key="promote-2026-08-31-bootstrap",
    )
    repo.activate_release(
        action="promote",
        target_environment="test",
        release_id="release-b",
        manifest_digest=release_b.manifest_digest,
        scope_expectations=[
            {
                "scope_kind": "physical_bundle",
                "scope_key": "duckdb-main",
                "expected_revision": 1,
            },
            {
                "scope_kind": "logical_lane",
                "scope_key": "bond-analytics-risk-tensor",
                "expected_revision": 1,
            },
            {
                "scope_kind": "logical_lane",
                "scope_key": "bond-analytics-core",
                "expected_revision": 1,
            },
        ],
        idempotency_key="promote-2026-08-31-03",
    )

    with pytest.raises(Exception):
        repo.activate_release(
            action="promote",
            target_environment="test",
            release_id="release-b",
            manifest_digest=release_b.manifest_digest,
            scope_expectations=[
                {
                    "scope_kind": "physical_bundle",
                    "scope_key": "duckdb-main",
                    "expected_revision": 1,
                    "alias_payload": {"channel": "rollback"},
                },
                {
                    "scope_kind": "logical_lane",
                    "scope_key": "bond-analytics-risk-tensor",
                    "expected_revision": 1,
                },
                {
                    "scope_kind": "logical_lane",
                    "scope_key": "bond-analytics-core",
                    "expected_revision": 1,
                },
            ],
            idempotency_key="promote-2026-08-31-03",
        )


def test_promote_bundle_rejects_manifest_that_omits_existing_controlled_aliases(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    release_a = _candidate_to_approved(repo, "release-a")
    repo.activate_release(
        action="promote",
        target_environment="test",
        release_id="release-a",
        manifest_digest=release_a.manifest_digest,
        scope_expectations=[
            {
                "scope_kind": "physical_bundle",
                "scope_key": "duckdb-main",
                "expected_revision": 0,
            },
            {
                "scope_kind": "logical_lane",
                "scope_key": "bond-analytics-risk-tensor",
                "expected_revision": 0,
            },
            {
                "scope_kind": "logical_lane",
                "scope_key": "bond-analytics-core",
                "expected_revision": 0,
            },
        ],
        idempotency_key="promote-2026-08-31-existing-alias-bootstrap",
    )
    before = {
        (alias.scope_kind, alias.scope_key): (alias.current_release_id, alias.revision)
        for alias in repo.list_aliases(target_environment="test")
    }
    release_b = _candidate_to_approved(repo, "release-b", include_core_lane=False)

    with pytest.raises(Exception):
        repo.activate_release(
            action="promote",
            target_environment="test",
            release_id="release-b",
            manifest_digest=release_b.manifest_digest,
            scope_expectations=[
                {
                    "scope_kind": "physical_bundle",
                    "scope_key": "duckdb-main",
                    "expected_revision": 1,
                },
                {
                    "scope_kind": "logical_lane",
                    "scope_key": "bond-analytics-risk-tensor",
                    "expected_revision": 1,
                },
            ],
            idempotency_key="promote-2026-08-31-existing-alias-shrink",
        )

    after = {
        (alias.scope_kind, alias.scope_key): (alias.current_release_id, alias.revision)
        for alias in repo.list_aliases(target_environment="test")
    }
    assert after == before


def test_activate_release_rejects_nested_physical_path_inside_logical_alias_payload(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    release = _candidate_to_approved(repo, "release-nested-path")

    with pytest.raises(Exception):
        repo.activate_release(
            action="promote",
            target_environment="test",
            release_id="release-nested-path",
            manifest_digest=release.manifest_digest,
            scope_expectations=[
                {
                    "scope_kind": "physical_bundle",
                    "scope_key": "duckdb-main",
                    "expected_revision": 0,
                },
                {
                    "scope_kind": "logical_lane",
                    "scope_key": "bond-analytics-risk-tensor",
                    "expected_revision": 0,
                    "alias_payload": {
                        "meta": {
                            "duckdb_path": "/srv/releases/release-nested-path.duckdb"
                        }
                    },
                },
                {
                    "scope_kind": "logical_lane",
                    "scope_key": "bond-analytics-core",
                    "expected_revision": 0,
                },
            ],
            idempotency_key="promote-2026-08-31-nested-path",
        )


def test_idempotency_key_can_be_reused_for_different_releases(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    release_a = _candidate_to_approved(repo, "release-a")
    release_b = _candidate_to_approved(repo, "release-b")
    repo.activate_release(
        action="promote",
        target_environment="test",
        release_id="release-a",
        manifest_digest=release_a.manifest_digest,
        scope_expectations=[
            {
                "scope_kind": "physical_bundle",
                "scope_key": "duckdb-main",
                "expected_revision": 0,
            },
            {
                "scope_kind": "logical_lane",
                "scope_key": "bond-analytics-risk-tensor",
                "expected_revision": 0,
            },
            {
                "scope_kind": "logical_lane",
                "scope_key": "bond-analytics-core",
                "expected_revision": 0,
            },
        ],
        idempotency_key="shared-manual-key",
    )

    second = repo.activate_release(
        action="promote",
        target_environment="test",
        release_id="release-b",
        manifest_digest=release_b.manifest_digest,
        scope_expectations=[
            {
                "scope_kind": "physical_bundle",
                "scope_key": "duckdb-main",
                "expected_revision": 1,
            },
            {
                "scope_kind": "logical_lane",
                "scope_key": "bond-analytics-risk-tensor",
                "expected_revision": 1,
            },
            {
                "scope_kind": "logical_lane",
                "scope_key": "bond-analytics-core",
                "expected_revision": 1,
            },
        ],
        idempotency_key="shared-manual-key",
    )

    assert second.release_id == "release-b"


def test_idempotency_key_can_be_reused_across_target_environments(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    release_test = _candidate_to_approved(
        repo, "release-test", target_environment="test"
    )
    release_staging = _candidate_to_approved(
        repo, "release-staging", target_environment="staging"
    )
    repo.activate_release(
        action="promote",
        target_environment="test",
        release_id="release-test",
        manifest_digest=release_test.manifest_digest,
        scope_expectations=[
            {
                "scope_kind": "physical_bundle",
                "scope_key": "duckdb-main",
                "expected_revision": 0,
            },
            {
                "scope_kind": "logical_lane",
                "scope_key": "bond-analytics-risk-tensor",
                "expected_revision": 0,
            },
            {
                "scope_kind": "logical_lane",
                "scope_key": "bond-analytics-core",
                "expected_revision": 0,
            },
        ],
        idempotency_key="shared-manual-key",
    )

    second = repo.activate_release(
        action="promote",
        target_environment="staging",
        release_id="release-staging",
        manifest_digest=release_staging.manifest_digest,
        scope_expectations=[
            {
                "scope_kind": "physical_bundle",
                "scope_key": "duckdb-main",
                "expected_revision": 0,
            },
            {
                "scope_kind": "logical_lane",
                "scope_key": "bond-analytics-risk-tensor",
                "expected_revision": 0,
            },
            {
                "scope_kind": "logical_lane",
                "scope_key": "bond-analytics-core",
                "expected_revision": 0,
            },
        ],
        idempotency_key="shared-manual-key",
    )

    assert second.target_environment == "staging"


def test_append_event_rejects_unknown_action_and_keeps_release_state(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    manifest = repo.create_manifest(
        release_id="release-a",
        state="candidate",
        payload=_manifest_payload("release-a"),
    )

    with pytest.raises(Exception):
        repo.append_event(
            release_id="release-a",
            action="nonsense",
            from_state="candidate",
            to_state="candidate",
            manifest_digest=manifest.manifest_digest,
            target_environment="test",
            event_payload={},
        )

    assert repo.get_manifest("release-a").state == "candidate"


def test_append_event_rejects_stale_from_state_and_keeps_release_state(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    manifest = repo.create_manifest(
        release_id="release-a",
        state="candidate",
        payload=_manifest_payload("release-a"),
    )

    with pytest.raises(Exception):
        repo.append_event(
            release_id="release-a",
            action="validate",
            from_state="draft",
            to_state="validated",
            manifest_digest=manifest.manifest_digest,
            target_environment="test",
            event_payload={
                "validation_receipts": {
                    "schema": {"status": "passed", "receipt_sha256": "D" * 64},
                    "contracts": {"status": "passed", "receipt_sha256": "E" * 64},
                    "governance": {"status": "passed", "receipt_sha256": "F" * 64},
                }
            },
        )

    assert repo.get_manifest("release-a").state == "candidate"


def test_append_approval_rejects_legacy_free_text_without_structured_receipts(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    manifest = repo.create_manifest(
        release_id="release-a",
        state="candidate",
        payload=_manifest_payload("release-a"),
    )
    repo.append_event(
        release_id="release-a",
        action="validate",
        from_state="candidate",
        to_state="validated",
        manifest_digest=manifest.manifest_digest,
        event_payload={
            "validation_receipts": {
                "schema": {"status": "passed", "receipt_sha256": "D" * 64},
                "contracts": {"status": "passed", "receipt_sha256": "E" * 64},
                "governance": {"status": "passed", "receipt_sha256": "F" * 64},
            }
        },
    )

    with pytest.raises(Exception, match="canonical authority and passed gate receipts"):
        repo.append_event(
            release_id="release-a",
            action="approve-record",
            from_state="validated",
            to_state="approved",
            manifest_digest=manifest.manifest_digest,
            event_payload={
                "authority_reference": "looks-approved",
                "manifest_digest": manifest.manifest_digest,
            },
        )

    assert repo.get_manifest("release-a").state == "validated"


def test_append_approval_rejects_canonical_receipts_with_registry_mismatch(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    manifest = repo.create_manifest(
        release_id="release-a",
        state="candidate",
        payload=_manifest_payload("release-a"),
    )
    repo.append_event(
        release_id="release-a",
        action="validate",
        from_state="candidate",
        to_state="validated",
        manifest_digest=manifest.manifest_digest,
        event_payload={
            "validation_receipts": {
                "schema": {"status": "passed", "receipt_sha256": "D" * 64},
                "contracts": {"status": "passed", "receipt_sha256": "E" * 64},
                "governance": {"status": "passed", "receipt_sha256": "F" * 64},
            }
        },
    )
    event_payload = _approval_event_payload(
        release_id="release-a",
        manifest_digest=manifest.manifest_digest,
        registry_sha256=manifest.payload["approval_registry_sha256"],
    )
    gate_body = dict(event_payload["approval_gate_receipt"])
    gate_body.pop("receipt_sha256")
    gate_body["registry_sha256"] = "A" * 64
    mismatched_gate = build_approval_gate_receipt(gate_body)
    event_payload["approval_gate_receipt"] = mismatched_gate.model_dump(mode="json")

    with pytest.raises(Exception, match="same registry digest"):
        repo.append_event(
            release_id="release-a",
            action="approve-record",
            from_state="validated",
            to_state="approved",
            manifest_digest=manifest.manifest_digest,
            event_payload=event_payload,
        )

    assert repo.get_manifest("release-a").state == "validated"

    event_payload = _approval_event_payload(
        release_id="release-a",
        manifest_digest=manifest.manifest_digest,
        registry_sha256="A" * 64,
    )
    with pytest.raises(Exception, match="frozen manifest registry"):
        repo.append_event(
            release_id="release-a",
            action="approve-record",
            from_state="validated",
            to_state="approved",
            manifest_digest=manifest.manifest_digest,
            event_payload=event_payload,
        )

    assert repo.get_manifest("release-a").state == "validated"

    event_payload = _approval_event_payload(
        release_id="release-a",
        manifest_digest=manifest.manifest_digest,
        registry_sha256=manifest.payload["approval_registry_sha256"],
        decision="rejected",
    )
    with pytest.raises(Exception, match="approved decisions"):
        repo.append_event(
            release_id="release-a",
            action="approve-record",
            from_state="validated",
            to_state="approved",
            manifest_digest=manifest.manifest_digest,
            event_payload=event_payload,
        )

    assert repo.get_manifest("release-a").state == "validated"

    event_payload = _approval_event_payload(
        release_id="release-a",
        manifest_digest=manifest.manifest_digest,
        registry_sha256=manifest.payload["approval_registry_sha256"],
    )
    event_payload["approved_by"] = "application-user-is-not-authority"
    with pytest.raises(Exception, match="unsupported fields"):
        repo.append_event(
            release_id="release-a",
            action="approve-record",
            from_state="validated",
            to_state="approved",
            manifest_digest=manifest.manifest_digest,
            event_payload=event_payload,
        )

    assert repo.get_manifest("release-a").state == "validated"


def test_append_event_rejects_invalid_state_transition_and_keeps_release_state(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    manifest = repo.create_manifest(
        release_id="release-a",
        state="candidate",
        payload=_manifest_payload("release-a"),
    )

    with pytest.raises(Exception):
        repo.append_event(
            release_id="release-a",
            action="approve-record",
            from_state="candidate",
            to_state="approved",
            manifest_digest=manifest.manifest_digest,
            target_environment="test",
            event_payload={
                "authority_reference": "github:env:formal-release",
                "approved_by": "finance-owner",
                "manifest_digest": manifest.manifest_digest,
            },
        )

    assert repo.get_manifest("release-a").state == "candidate"
