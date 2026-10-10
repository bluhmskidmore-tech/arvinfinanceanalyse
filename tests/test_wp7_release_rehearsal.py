from __future__ import annotations

import builtins
import json
import os
import shutil
from contextlib import contextmanager
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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MOSS_ENVIRONMENT", "test")
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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MOSS_ENVIRONMENT", "production")
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
    monkeypatch.setenv("MOSS_ENVIRONMENT", "test")
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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MOSS_ENVIRONMENT", "test")
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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MOSS_ENVIRONMENT", "test")
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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MOSS_ENVIRONMENT", "test")
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
    monkeypatch.setenv("MOSS_ENVIRONMENT", "test")
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


@pytest.mark.parametrize(
    ("observed", "requested"),
    [("development", "test"), ("production", "test"), ("test", "production")],
)
def test_rehearsal_rejects_mismatched_host_environment_before_creating_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, observed: str, requested: str,
) -> None:
    monkeypatch.setenv("MOSS_ENVIRONMENT", observed)
    rehearsal = _load_rehearsal_module()
    workspace = tmp_path / "must-not-be-created"
    with pytest.raises(rehearsal.RehearsalError) as caught:
        rehearsal.run_rehearsal(workspace, run_id="environment-mismatch", host_environment=requested)
    assert caught.value.code == "host_environment_mismatch"
    assert not workspace.exists()


def _new_synthetic_target(tmp_path: Path) -> tuple[Path, Path]:
    workspace = tmp_path / "synthetic-workspace"
    (workspace / "bundles").mkdir(parents=True)
    return workspace, workspace / "bundles" / "candidate.duckdb"


def test_synthetic_writer_refuses_sql_outside_task_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from backend.app.tasks import wp7_rehearsal_bundle as writer

    def reject_connect(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("unguarded synthetic writer must not connect")

    monkeypatch.setattr(writer.duckdb, "connect", reject_connect)
    target = tmp_path / "must-not-exist.duckdb"
    with pytest.raises(PermissionError, match="repository task write scope"):
        writer._write_synthetic_database(target, release_id="synthetic", ordinal=1)
    assert not target.exists()


def test_synthetic_task_rejects_production_before_connecting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from backend.app.tasks import wp7_rehearsal_bundle as writer

    workspace, target = _new_synthetic_target(tmp_path)
    monkeypatch.setenv("MOSS_ENVIRONMENT", "production")

    def reject_connect(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("production rehearsal must not connect")

    monkeypatch.setattr(writer.duckdb, "connect", reject_connect)
    with pytest.raises(writer.SyntheticBundleError, match="production_environment_forbidden"):
        writer.create_synthetic_bundle(path=target, workspace=workspace, release_id="synthetic", ordinal=1)
    assert not target.exists()


def test_synthetic_writer_uses_a_new_task_owned_database_and_restores_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from backend.app.repositories.task_write_guard import require_repository_task_write_scope
    from backend.app.tasks import wp7_rehearsal_bundle as writer

    workspace, target = _new_synthetic_target(tmp_path)
    original_connect = writer.duckdb.connect
    opens: list[str] = []

    def connect(database: str, *, read_only: bool):
        require_repository_task_write_scope("synthetic-test")
        assert read_only is False
        staging = Path(database)
        assert staging.parent.parent.resolve() == target.parent.resolve()
        assert staging.parent.name.startswith(".synthetic-bundle-")
        assert not staging.exists()
        opens.append(database)
        return original_connect(database, read_only=read_only)

    monkeypatch.setattr(writer.duckdb, "connect", connect)
    writer.create_synthetic_bundle(path=target, workspace=workspace, release_id="synthetic", ordinal=2)
    assert len(opens) == 1
    assert not Path(opens[0]).parent.exists()
    with original_connect(str(target), read_only=True) as conn:
        assert conn.execute("select * from rehearsal.bundle_metadata").fetchall() == [("synthetic", 2, True)]
    with pytest.raises(PermissionError):
        require_repository_task_write_scope("scope-must-be-restored")


@pytest.mark.parametrize("invalid_target", ["existing", "outside_workspace"])
def test_synthetic_writer_rejects_existing_or_unbound_targets_before_connecting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, invalid_target: str,
) -> None:
    from backend.app.tasks import wp7_rehearsal_bundle as writer

    workspace, target = _new_synthetic_target(tmp_path)
    if invalid_target == "existing":
        target.write_bytes(b"existing-content")
        expected = "synthetic_bundle_path_must_be_new"
    else:
        target = tmp_path / "candidate.duckdb"
        expected = "synthetic_bundle_path_outside_workspace"

    def reject_connect(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("invalid target must not connect")

    monkeypatch.setattr(writer.duckdb, "connect", reject_connect)
    with pytest.raises(writer.SyntheticBundleError, match=expected):
        writer.create_synthetic_bundle(path=target, workspace=workspace, release_id="synthetic", ordinal=1)
    if invalid_target == "existing":
        assert target.read_bytes() == b"existing-content"
    else:
        assert not target.exists()


def test_synthetic_writer_rechecks_target_after_acquiring_the_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.tasks import wp7_rehearsal_bundle as writer

    workspace, target = _new_synthetic_target(tmp_path)

    @contextmanager
    def lock(_definition: object, *, base_dir: Path):
        assert base_dir.resolve() == workspace.resolve()
        target.write_bytes(b"race-winner")
        yield

    def reject_connect(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("replaced target must not connect")

    monkeypatch.setattr(writer, "acquire_lock", lock)
    monkeypatch.setattr(writer.duckdb, "connect", reject_connect)
    with pytest.raises(writer.SyntheticBundleError, match="synthetic_bundle_path_must_be_new"):
        writer.create_synthetic_bundle(path=target, workspace=workspace, release_id="synthetic", ordinal=1)
    assert target.read_bytes() == b"race-winner"


def test_synthetic_writer_never_overwrites_a_target_created_at_installation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.tasks import wp7_rehearsal_bundle as writer

    workspace, target = _new_synthetic_target(tmp_path)
    original_open = Path.open
    inserted = False

    def insert_race_winner() -> None:
        nonlocal inserted
        if not inserted:
            inserted = True
            with original_open(target, "wb") as race_winner:
                race_winner.write(b"race-winner")

    def open_path(path: Path, mode: str = "r", *args: object, **kwargs: object):
        if path == target and mode == "xb":
            insert_race_winner()
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", open_path)
    original_install = getattr(writer, "_open_install_target", None)
    if original_install is not None:
        def open_install(path: Path, *, directory_fd: int | None):
            insert_race_winner()
            return original_install(path, directory_fd=directory_fd)

        monkeypatch.setattr(writer, "_open_install_target", open_install)
    with pytest.raises(writer.SyntheticBundleError, match="synthetic_bundle_path_must_be_new"):
        writer.create_synthetic_bundle(path=target, workspace=workspace, release_id="synthetic", ordinal=1)
    assert target.read_bytes() == b"race-winner"


def test_synthetic_writer_never_writes_through_a_replaced_parent_at_installation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.tasks import wp7_rehearsal_bundle as writer

    workspace, target = _new_synthetic_target(tmp_path)
    displaced = workspace / "displaced-bundles"
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "sentinel").write_bytes(b"outside-unchanged")
    before_outside = {path.name: path.read_bytes() for path in outside.iterdir()}
    original_open = Path.open
    attempted = False
    rename_denied = False

    def replace_parent() -> None:
        nonlocal attempted, rename_denied
        if attempted:
            return
        attempted = True
        try:
            target.parent.rename(displaced)
        except PermissionError:
            rename_denied = True
            return
        target.parent.symlink_to(outside, target_is_directory=True)

    def open_path(path: Path, mode: str = "r", *args: object, **kwargs: object):
        if path == target and mode == "xb":
            replace_parent()
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", open_path)
    original_install = getattr(writer, "_open_install_target", None)
    if original_install is not None:
        def open_install(path: Path, *, directory_fd: int | None):
            replace_parent()
            return original_install(path, directory_fd=directory_fd)

        monkeypatch.setattr(writer, "_open_install_target", open_install)
    rejected = False
    try:
        writer.create_synthetic_bundle(path=target, workspace=workspace, release_id="synthetic", ordinal=1)
    except writer.SyntheticBundleError:
        rejected = True
    assert attempted, "the test must reach the installation race"
    assert {path.name: path.read_bytes() for path in outside.iterdir()} == before_outside
    assert not (outside / "candidate.duckdb").exists()
    if os.name == "nt":
        assert rename_denied, "directory handles must prevent the Windows parent replacement"
        assert target.is_file()
        assert not rejected
    else:
        assert not rename_denied
        assert rejected
        assert not (displaced / "candidate.duckdb").exists()
        assert not list(displaced.glob(".synthetic-bundle-*"))


@pytest.mark.windows_native
def test_windows_synthetic_writer_prevents_parent_replacement_without_external_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    if os.name != "nt":
        pytest.skip("Windows directory sharing contract")
    test_synthetic_writer_never_writes_through_a_replaced_parent_at_installation(tmp_path, monkeypatch)


def test_synthetic_writer_rejects_reparse_parents_before_connecting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    from backend.app.tasks import wp7_rehearsal_bundle as writer

    workspace, target = _new_synthetic_target(tmp_path)
    original_stat = Path.stat

    def path_stat(path: Path, *args: object, **kwargs: object):
        metadata = original_stat(path, *args, **kwargs)
        if path == target.parent and kwargs.get("follow_symlinks") is False:
            return SimpleNamespace(
                st_file_attributes=0x400, st_mode=metadata.st_mode,
                st_dev=metadata.st_dev, st_ino=metadata.st_ino,
            )
        return metadata

    def reject_connect(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("reparse parent must not connect")

    monkeypatch.setattr(Path, "stat", path_stat)
    monkeypatch.setattr(writer.duckdb, "connect", reject_connect)
    with pytest.raises(writer.SyntheticBundleError, match="contains_symlink_or_junction"):
        writer.create_synthetic_bundle(path=target, workspace=workspace, release_id="synthetic", ordinal=1)
    assert not target.exists()
