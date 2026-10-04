from __future__ import annotations

import builtins
import json
import shutil
from pathlib import Path

import pytest

from backend.app.governance.release_control import (
    ReleaseControlService,
    ReleaseGateBlockedError,
)
from backend.app.governance.exact_numeric_policy import build_exact_numeric_policy
from backend.app.repositories.release_control_repo import ReleaseControlRepository
from backend.app.schemas.release_control import canonical_sha256
from tests.helpers import load_module


EXPECTED_SCOPES = {
    ("physical_bundle", "duckdb-main"),
    ("logical_lane", "bond-analytics-risk-tensor"),
    ("logical_lane", "bond-analytics-core"),
}


def _load_rehearsal_module():
    return load_module(
        "scripts.wp7_release_rehearsal",
        "scripts/wp7_release_rehearsal.py",
    )


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _aliases_by_scope(aliases: object) -> dict[tuple[str, str], dict[str, object]]:
    assert isinstance(aliases, list)
    by_scope = {
        (str(alias["scope_kind"]), str(alias["scope_key"])): alias for alias in aliases
    }
    assert set(by_scope) == EXPECTED_SCOPES
    assert len(aliases) == len(EXPECTED_SCOPES)
    return by_scope


def _assert_rejected_probe(probe: object) -> None:
    assert isinstance(probe, dict)
    assert probe["status"] == "rejected"
    assert probe["before_state_sha256"] == probe["after_state_sha256"]
    assert probe["state_unchanged"] is True


def test_rehearsal_promotes_and_rolls_back_the_complete_bundle_with_sealed_receipt(
    tmp_path: Path,
) -> None:
    rehearsal = _load_rehearsal_module()
    workspace_root = tmp_path / "wp7-rehearsal"

    receipt = rehearsal.run_rehearsal(
        workspace_root,
        run_id="contract-success",
        host_environment="test",
    )

    assert receipt["schema_version"] == "wp7-release-rehearsal/v1"
    assert receipt["status"] == "passed"
    assert receipt["rehearsal_only"] is True
    assert receipt["synthetic_evidence"] is True
    assert receipt["structure_only"] is True
    assert receipt["integrity_only"] is True
    assert receipt["authenticity_attested"] is False
    assert receipt["release_gate_eligible"] is False
    assert receipt["wp7_production_eligible"] is False
    assert receipt["production_writes"] is False

    candidate_aliases = _aliases_by_scope(receipt["candidate_promote"]["aliases"])
    candidate_release_ids = {
        alias["current_release_id"] for alias in candidate_aliases.values()
    }
    baseline_release_ids = {
        alias["previous_release_id"] for alias in candidate_aliases.values()
    }
    assert len(candidate_release_ids) == 1
    assert len(baseline_release_ids) == 1
    candidate_release_id = candidate_release_ids.pop()
    baseline_release_id = baseline_release_ids.pop()
    assert candidate_release_id
    assert baseline_release_id
    assert candidate_release_id != baseline_release_id
    assert {alias["revision"] for alias in candidate_aliases.values()} == {2}

    rollback_aliases = _aliases_by_scope(receipt["rollback"]["aliases"])
    assert {alias["current_release_id"] for alias in rollback_aliases.values()} == {
        baseline_release_id
    }
    assert {alias["previous_release_id"] for alias in rollback_aliases.values()} == {
        candidate_release_id
    }
    assert {alias["revision"] for alias in rollback_aliases.values()} == {3}

    probes = receipt["negative_probes"]
    assert isinstance(probes, dict)
    assert set(probes) == {
        "candidate_checksum_tamper",
        "incomplete_scope_plan",
    }
    _assert_rejected_probe(probes["candidate_checksum_tamper"])
    _assert_rejected_probe(probes["incomplete_scope_plan"])

    artifacts = receipt["artifacts"]
    assert isinstance(artifacts, dict)
    assert {
        "baseline_bundle",
        "candidate_bundle",
        "backup_bundle",
        "control_db",
    }.issubset(artifacts)
    for artifact in artifacts.values():
        assert isinstance(artifact, dict)
        assert Path(str(artifact["path"])).is_absolute()
        assert len(str(artifact["sha256"])) == 64

    receipt_path = Path(str(receipt["receipt_path"]))
    assert receipt_path.is_absolute()
    on_disk = _read_json(receipt_path)
    assert on_disk == receipt
    unsigned = {key: value for key, value in on_disk.items() if key != "receipt_sha256"}
    assert on_disk["receipt_sha256"] == canonical_sha256(unsigned)

    verification = rehearsal.verify_rehearsal_receipt(receipt_path)
    assert verification["status"] == "passed"
    assert verification["integrity_only"] is True
    assert verification["authenticity_attested"] is False
    assert verification["verified_receipt_sha256"] == receipt["receipt_sha256"]
    unsigned_verification = {
        key: value for key, value in verification.items() if key != "receipt_sha256"
    }
    assert verification["receipt_sha256"] == canonical_sha256(unsigned_verification)


def test_rehearsal_rejects_production_before_creating_workspace(
    tmp_path: Path,
) -> None:
    rehearsal = _load_rehearsal_module()
    workspace_root = tmp_path / "must-not-be-created"

    with pytest.raises(rehearsal.RehearsalError) as caught:
        rehearsal.run_rehearsal(
            workspace_root,
            run_id="production-rejected",
            host_environment="production",
        )

    assert caught.value.code == "production_environment_forbidden"
    assert not workspace_root.exists()


def test_rehearsal_rejects_relative_workspace_before_creating_it(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    rehearsal = _load_rehearsal_module()
    monkeypatch.chdir(tmp_path)
    workspace_root = Path("relative-wp7-rehearsal")

    with pytest.raises(rehearsal.RehearsalError) as caught:
        rehearsal.run_rehearsal(
            workspace_root,
            run_id="relative-path-rejected",
            host_environment="test",
        )

    assert caught.value.code == "workspace_root_must_be_absolute"
    assert not workspace_root.exists()


def test_rehearsal_rejects_an_existing_workspace(
    tmp_path: Path,
) -> None:
    rehearsal = _load_rehearsal_module()
    workspace_root = tmp_path / "already-exists"
    workspace_root.mkdir()

    with pytest.raises(rehearsal.RehearsalError) as caught:
        rehearsal.run_rehearsal(
            workspace_root,
            run_id="existing-path-rejected",
            host_environment="test",
        )

    assert caught.value.code == "workspace_root_must_not_exist"
    assert list(workspace_root.iterdir()) == []


def test_receipt_verification_rejects_relocated_artifact_even_after_rehash(
    tmp_path: Path,
) -> None:
    rehearsal = _load_rehearsal_module()
    receipt = rehearsal.run_rehearsal(
        tmp_path / "wp7-rehearsal",
        run_id="path-tamper",
        host_environment="test",
    )
    receipt_path = Path(str(receipt["receipt_path"]))
    tampered = _read_json(receipt_path)
    candidate = tampered["artifacts"]["candidate_bundle"]
    original_path = Path(str(candidate["path"]))
    relocated_path = tmp_path / "relocated-candidate.duckdb"
    shutil.copyfile(original_path, relocated_path)
    candidate["path"] = str(relocated_path.resolve())
    unsigned = {
        key: value for key, value in tampered.items() if key != "receipt_sha256"
    }
    tampered["receipt_sha256"] = canonical_sha256(unsigned)
    receipt_path.write_text(
        json.dumps(tampered, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(rehearsal.RehearsalError) as caught:
        rehearsal.verify_rehearsal_receipt(receipt_path)

    assert caught.value.code == "artifact_path_mismatch"


def test_synthetic_rehearsal_gate_receipts_fail_closed_in_standard_service(
    tmp_path: Path,
) -> None:
    rehearsal = _load_rehearsal_module()
    repo = ReleaseControlRepository(
        sql_dsn=f"sqlite:///{(tmp_path / 'standard-service.sqlite3').as_posix()}",
    )
    service = ReleaseControlService(repo=repo)
    try:
        release_id = "rehearsal-receipt-must-not-pass-standard-gate"
        prepared = service.prepare_release(
            release_id=release_id,
            payload=rehearsal._manifest_payload(
                release_id=release_id,
                bundle_sha256="A" * 64,
                git_sha="0" * 40,
            ),
            freeze=True,
        )

        with pytest.raises(
            ReleaseGateBlockedError, match="validation gates did not pass"
        ):
            service.record_validation(
                release_id,
                validation_receipts=rehearsal._validation_receipts(
                    release_id=release_id,
                    manifest_sha256=prepared.manifest_digest,
                ),
            )

        assert service.show_release(release_id).state == "candidate"
    finally:
        repo.close()


def test_manifest_payload_binds_exact_numeric_policy_registry_digest() -> None:
    rehearsal = _load_rehearsal_module()

    payload = rehearsal._manifest_payload(
        release_id="manifest-policy-binding",
        bundle_sha256="A" * 64,
        git_sha="0" * 40,
    )

    assert payload["numeric_policy"] == build_exact_numeric_policy(rehearsal_only=True)


def test_receipt_verification_rejects_external_symlink_alias_after_rehash(
    tmp_path: Path,
) -> None:
    rehearsal = _load_rehearsal_module()
    receipt = rehearsal.run_rehearsal(
        tmp_path / "wp7-rehearsal",
        run_id="symlink-path-tamper",
        host_environment="test",
    )
    receipt_path = Path(str(receipt["receipt_path"]))
    tampered = _read_json(receipt_path)
    candidate = tampered["artifacts"]["candidate_bundle"]
    original_path = Path(str(candidate["path"]))
    alias_path = tmp_path / "candidate-alias.duckdb"
    try:
        alias_path.symlink_to(original_path)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")
    candidate["path"] = str(alias_path.absolute())
    unsigned = {
        key: value for key, value in tampered.items() if key != "receipt_sha256"
    }
    tampered["receipt_sha256"] = canonical_sha256(unsigned)
    receipt_path.write_text(
        json.dumps(tampered, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(rehearsal.RehearsalError) as caught:
        rehearsal.verify_rehearsal_receipt(receipt_path)

    assert caught.value.code == "artifact_path_mismatch"


def test_verify_path_does_not_import_duckdb(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    rehearsal = _load_rehearsal_module()
    receipt = rehearsal.run_rehearsal(
        tmp_path / "wp7-rehearsal",
        run_id="verify-without-duckdb-import",
        host_environment="test",
    )
    original_import = builtins.__import__

    def reject_duckdb_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "duckdb":
            raise AssertionError("verify must not import duckdb")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", reject_duckdb_import)
    verify_only = load_module(
        "scripts.wp7_release_rehearsal_verify_only",
        "scripts/wp7_release_rehearsal.py",
    )

    assert (
        verify_only.verify_rehearsal_receipt(receipt["receipt_path"])["status"]
        == "passed"
    )
