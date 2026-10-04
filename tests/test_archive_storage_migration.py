"""Negative migration probes preserve immutable source identities and containment."""
from __future__ import annotations

import hashlib
import ast
import json
import os
import stat
import subprocess
import tempfile
from pathlib import Path

import pytest

from backend.app.repositories.object_store_repo import (
    ObjectStoreRepository,
    read_local_archive_bytes,
    resolve_local_archive_path,
)
from scripts.archive_storage_migration import (
    OFFLINE_RECEIPT_PURPOSE,
    SAMPLE_OWNERSHIP_MARKER,
    WRITER_EXCLUSION_FIELDS,
    apply_maintenance_archive_relocation,
    apply_sample_archive_relocation,
    plan_archive_relocation,
)
from scripts.dev_runtime_control import RuntimeControlError, enter_maintenance


@pytest.fixture
def sample():
    with tempfile.TemporaryDirectory(prefix="moss-archive-migration-sample-") as directory:
        owned = Path(directory)
        (owned / SAMPLE_OWNERSHIP_MARKER).write_text(
            '{"format_version":1,"purpose":"moss-archive-migration-sample"}', encoding="utf-8"
        )
        source = owned / "original archive"
        target = owned / "relocated archive"
        file = source / "ZQTZSHOW" / "files" / "source.xls"
        file.parent.mkdir(parents=True)
        file.write_bytes(b"immutable synthetic archive input")
        yield owned, source, target, file


def _apply(sample):
    owned, source, target, file = sample
    plan = plan_archive_relocation(source, target)
    receipt = apply_sample_archive_relocation(plan, owned)
    return target, file, receipt


def _rewrite_receipt(path: Path, transform) -> None:
    value = json.loads(path.read_bytes())
    transform(value)
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    path.write_text(json.dumps(value), encoding="utf-8")
    path.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)


def test_archive_migration_preview_does_not_create_target_or_change_source(sample):
    _owned, source, target, file = sample
    before = file.read_bytes()
    plan = plan_archive_relocation(source, target)
    assert not target.exists()
    assert file.read_bytes() == before
    assert plan["receipt"]["entries"] == [{
        "source_path": str(file),
        "target_relative_path": "ZQTZSHOW/files/source.xls",
        "sha256": hashlib.sha256(before).hexdigest(),
    }]


def test_archive_mapping_reads_verified_copy_and_keeps_source_identity(sample):
    target, original, receipt = _apply(sample)
    before = original.read_bytes()
    original.write_bytes(b"old path must not be read after migration")
    mapped = resolve_local_archive_path(original, target)
    assert mapped == target / "ZQTZSHOW" / "files" / "source.xls"
    assert read_local_archive_bytes(original, target) == before
    store = ObjectStoreRepository("unused", "unused", "unused", "unused", mode="local", local_archive_path=str(target))
    with store.open_archived_binary(str(original)) as handle:
        mapped.write_bytes(b"changed after immutable payload was captured")
        assert handle.read() == before
    assert json.loads(receipt.read_bytes())["entries"][0]["source_path"] == str(original)
    assert not receipt.stat().st_mode & stat.S_IWUSR


def test_archive_copy_preserves_source_modification_time_for_selection_and_preflight(sample):
    _owned, _source, _target, original = sample
    os.utime(original, ns=(1_500_000_000_000_000_000, 1_600_000_000_123_456_700))
    expected = original.stat().st_mtime_ns
    target, _original, _receipt = _apply(sample)
    assert resolve_local_archive_path(original, target).stat().st_mtime_ns == expected


@pytest.mark.parametrize("stage", ["preview", "target_verify"])
def test_archive_directory_read_error_is_never_treated_as_empty(sample, monkeypatch, stage):
    import scripts.archive_storage_migration as migration

    owned, source, target, _file = sample
    plan = plan_archive_relocation(source, target)
    original_walk = migration.os.walk
    def unreadable_walk(root, *, followlinks=False, onerror=None):
        if stage == "preview" or Path(root) == target:
            if onerror is not None:
                onerror(PermissionError("synthetic unreadable archive directory"))
            return iter(())
        return original_walk(root, followlinks=followlinks, onerror=onerror)
    monkeypatch.setattr(migration.os, "walk", unreadable_walk)
    with pytest.raises(PermissionError, match="unreadable"):
        if stage == "preview":
            plan_archive_relocation(source, target)
        else:
            apply_sample_archive_relocation(plan, owned)
    assert not (target / ".moss-archive-relocations.json").exists()


def test_archive_mapping_does_not_fall_back_to_existing_old_file_when_receipt_is_missing(sample):
    target, original, receipt = _apply(sample)
    receipt.chmod(stat.S_IRUSR | stat.S_IWUSR)
    receipt.unlink()
    assert original.exists()
    with pytest.raises(ValueError, match="outside local archive root"):
        read_local_archive_bytes(original, target)


def test_archive_mapping_requires_full_exact_identity_not_basename(sample):
    target, original, _receipt = _apply(sample)
    unmatched = original.parent.parent / original.name
    unmatched.write_bytes(original.read_bytes())
    with pytest.raises(ValueError, match="no exact relocation"):
        read_local_archive_bytes(unmatched, target)


def test_archive_mapping_rejects_missing_or_modified_copy_even_when_original_exists(sample):
    target, original, _receipt = _apply(sample)
    mapped = target / "ZQTZSHOW" / "files" / "source.xls"
    mapped.write_bytes(b"corrupt copy")
    with pytest.raises(ValueError, match="content hash"):
        read_local_archive_bytes(original, target)
    mapped.unlink()
    with pytest.raises(ValueError, match="target is missing"):
        resolve_local_archive_path(original, target)


@pytest.mark.parametrize("relative", ["../escape.xls", "nested/../escape.xls", "/absolute.xls", "C:drive.xls", "//server/share.xls", "nested\\source.xls"])
def test_archive_mapping_rejects_receipt_traversal_or_absolute_targets(sample, relative):
    target, original, receipt = _apply(sample)
    _rewrite_receipt(receipt, lambda value: value["entries"][0].update(target_relative_path=relative))
    with pytest.raises(ValueError, match="invalid archive relocation target"):
        read_local_archive_bytes(original, target)


def test_archive_mapping_rejects_duplicate_canonical_source_keys(sample):
    target, original, receipt = _apply(sample)
    def duplicate(value):
        second = dict(value["entries"][0])
        if os.name == "nt":
            second["source_path"] = second["source_path"].upper().replace("\\", "/")
        value["entries"].append(second)
    _rewrite_receipt(receipt, duplicate)
    with pytest.raises(ValueError, match="duplicate or out-of-root"):
        read_local_archive_bytes(original, target)


def test_archive_mapping_rejects_boolean_format_version_and_requested_traversal(sample):
    target, original, receipt = _apply(sample)
    _rewrite_receipt(receipt, lambda value: value.update(format_version=True))
    with pytest.raises(ValueError, match="unsupported archive relocation"):
        read_local_archive_bytes(original, target)
    with pytest.raises(ValueError, match="traversal"):
        read_local_archive_bytes(original.parent / ".." / "files" / original.name, target)


def test_archive_mapping_rejects_foreign_host_source_identity_without_old_read(sample):
    target, original, receipt = _apply(sample)
    foreign = "/var/moss/archive" if os.name == "nt" else "C:/MOSS/archive"
    _rewrite_receipt(receipt, lambda value: value.update(source_archive_root=foreign))
    assert original.exists()
    with pytest.raises(ValueError, match="foreign or ambiguous"):
        read_local_archive_bytes(original, target)


@pytest.mark.parametrize("foreign", ["/old/file", "\\old\\file", "C:old/file"] if os.name == "nt" else ["C:/old/file", "C:\\old\\file", "//server/share/file", "\\\\server\\share\\file"])
def test_archive_foreign_identity_is_rejected_before_cwd_relative_resolution(sample, monkeypatch, foreign):
    _owned, _source, target, _original = sample
    target.mkdir()
    monkeypatch.chdir(target)
    if os.name != "nt" and foreign.startswith("C:/"):
        alias = target / foreign
        alias.parent.mkdir(parents=True)
        alias.write_bytes(b"not a historical archive")
    for reader in (read_local_archive_bytes, resolve_local_archive_path):
        with pytest.raises(ValueError, match="foreign or ambiguous"):
            reader(foreign, target)
        with pytest.raises(ValueError, match="foreign or ambiguous"):
            reader("relative file", foreign)


def test_archive_native_relative_path_contract_remains_within_current_root(sample, monkeypatch):
    _owned, source, _target, original = sample
    monkeypatch.chdir(source)
    relative = original.relative_to(source)
    assert read_local_archive_bytes(relative, source) == original.read_bytes()


@pytest.mark.parametrize("linked_file", ["receipt", "target"])
def test_archive_mapping_rejects_hard_linked_target_and_receipt(sample, linked_file):
    target, original, receipt = _apply(sample)
    mapped = target / "ZQTZSHOW" / "files" / "source.xls"
    os.link(receipt if linked_file == "receipt" else mapped, target.parent / "linked alias")
    with pytest.raises(ValueError, match="links or junctions"):
        read_local_archive_bytes(original, target)


def test_archive_migration_refuses_receipt_overwrite_and_conflicting_target(sample):
    owned, source, target, original = sample
    mapped = target / "ZQTZSHOW" / "files" / "source.xls"
    mapped.parent.mkdir(parents=True)
    mapped.write_bytes(b"unique existing target")
    with pytest.raises(ValueError, match="conflicting file"):
        plan_archive_relocation(source, target)
    mapped.unlink()
    receipt = apply_sample_archive_relocation(plan_archive_relocation(source, target), owned)
    before = receipt.read_bytes()
    with pytest.raises(ValueError, match="already has"):
        plan_archive_relocation(source, target)
    assert receipt.read_bytes() == before
    assert original.read_bytes() == b"immutable synthetic archive input"


def test_archive_migration_rejects_forged_plan_and_unowned_destination(sample):
    owned, source, target, _original = sample
    plan = plan_archive_relocation(source, target)
    plan["receipt"]["entries"][0]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="plan changed"):
        apply_sample_archive_relocation(plan, owned)
    assert not target.exists()
    outside = owned.parent / f"unowned-{owned.name}"
    plan = plan_archive_relocation(source, outside)
    with pytest.raises(ValueError, match="escapes the owned"):
        apply_sample_archive_relocation(plan, owned)
    assert not outside.exists()


def _directory_link(path: Path, target: Path) -> None:
    if os.name == "nt":
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "New-Item -ItemType Junction -Path $env:MOSS_TEST_LINK -Target $env:MOSS_TEST_TARGET | Out-Null"],
            env={**os.environ, "MOSS_TEST_LINK": str(path), "MOSS_TEST_TARGET": str(target)},
            capture_output=True,
            check=False,
        )
        if result.returncode:
            pytest.skip("directory junction creation is unavailable")
    else:
        path.symlink_to(target, target_is_directory=True)


def test_archive_mapping_rejects_actual_linked_target_parent(sample):
    target, original, receipt = _apply(sample)
    outside = target.parent / "outside archive"
    outside.mkdir()
    (outside / "source.xls").write_bytes(original.read_bytes())
    _directory_link(target / "linked parent", outside)
    _rewrite_receipt(receipt, lambda value: value["entries"][0].update(target_relative_path="linked parent/source.xls"))
    with pytest.raises(ValueError, match="links or junctions"):
        read_local_archive_bytes(original, target)


def test_archive_mapping_rejects_actual_receipt_symlink(sample):
    target, original, receipt = _apply(sample)
    actual = target.parent / "actual receipt.json"
    receipt.chmod(stat.S_IRUSR | stat.S_IWUSR)
    receipt.rename(actual)
    try:
        receipt.symlink_to(actual)
    except OSError:
        pytest.skip("file symlink creation requires privileges unavailable on this host")
    with pytest.raises(ValueError, match="links or junctions"):
        read_local_archive_bytes(original, target)


def test_sample_write_rejects_repository_temp_and_boolean_ownership(sample):
    owned, source, target, _file = sample
    marker = owned / SAMPLE_OWNERSHIP_MARKER
    marker.write_text('{"format_version":true,"purpose":"moss-archive-migration-sample"}', encoding="utf-8")
    with pytest.raises(ValueError, match="marker is invalid"):
        apply_sample_archive_relocation(plan_archive_relocation(source, target), owned)
    repo_temp = Path(__file__).resolve().parents[1] / ".codex-tmp" / "repository-maintenance-20261004" / "data"
    with pytest.raises(ValueError, match="specific task temporary"):
        apply_sample_archive_relocation(plan_archive_relocation(source, target), repo_temp)
    assert not target.exists()


@pytest.fixture
def maintenance_sample(tmp_path):
    repo = tmp_path / "repository"
    controller = repo / "scripts" / "dev_runtime_control.py"
    controller.parent.mkdir(parents=True)
    controller.write_text("# synthetic controller ownership boundary\n", encoding="utf-8")
    source = repo / "data" / "archive"
    source.mkdir(parents=True)
    original = source / "source.xls"
    original.write_bytes(b"offline synthetic business archive")
    target = tmp_path / "external storage" / "archive"
    maintenance = enter_maintenance(repo, "synthetic archive migration")
    evidence_dir = repo / ".codex-tmp" / "migration"
    evidence_dir.mkdir(parents=True)
    evidence = evidence_dir / "writer-exclusion.json"
    evidence.write_bytes(b'{"synthetic":true,"writers":0}')
    receipt_path = evidence_dir / "offline-receipt.json"
    receipt = {
        "format_version": 1, "purpose": OFFLINE_RECEIPT_PURPOSE, "repo_root": str(repo),
        "source_root": str(source), "target_root": str(target),
        "maintenance_entered_at": maintenance["entered_at"],
        "writer_exclusion": {name: True for name in WRITER_EXCLUSION_FIELDS},
        "evidence_files": [{"path": str(evidence), "sha256": hashlib.sha256(evidence.read_bytes()).hexdigest()}],
    }
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    return repo, source, target, original, maintenance, evidence, receipt_path


def _apply_maintenance(sample, *, token=None):
    repo, source, target, _original, maintenance, _evidence, receipt = sample
    return apply_maintenance_archive_relocation(
        plan_archive_relocation(source, target), repo_root=repo,
        owner_token=maintenance["owner_token"] if token is None else token, offline_receipt=receipt,
    )


def test_maintenance_archive_copy_preserves_source_and_exact_historical_identity(maintenance_sample):
    _repo, _source, target, original, _maintenance, _evidence, _offline = maintenance_sample
    before = original.read_bytes()
    receipt = _apply_maintenance(maintenance_sample)
    assert original.read_bytes() == before
    assert read_local_archive_bytes(original, target) == before
    assert json.loads(receipt.read_bytes())["entries"][0]["source_path"] == str(original)
    assert not receipt.stat().st_mode & stat.S_IWUSR


def test_maintenance_archive_copy_requires_current_owner_and_active_maintenance(maintenance_sample):
    repo, _source, target, _original, _maintenance, _evidence, _offline = maintenance_sample
    with pytest.raises(RuntimeControlError, match="owner token"):
        _apply_maintenance(maintenance_sample, token="wrong-owner")
    (repo / "tmp-governance" / "runtime-clean" / "control" / "maintenance.json").unlink()
    with pytest.raises(FileNotFoundError):
        _apply_maintenance(maintenance_sample)
    assert not target.exists()


@pytest.mark.parametrize("field", ["source_root", "target_root", "maintenance_entered_at", "format_version", "writer_exclusion", "evidence_files"])
def test_maintenance_archive_copy_rejects_stale_or_incomplete_operator_receipt(maintenance_sample, field):
    _repo, _source, target, _original, _maintenance, _evidence, offline = maintenance_sample
    receipt = json.loads(offline.read_bytes())
    receipt[field] = {
        "source_root": "wrong source", "target_root": "wrong target", "maintenance_entered_at": 0,
        "format_version": True, "writer_exclusion": {name: 1 for name in WRITER_EXCLUSION_FIELDS},
        "evidence_files": [],
    }[field]
    offline.write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(ValueError, match="offline receipt"):
        _apply_maintenance(maintenance_sample)
    assert not target.exists()


def test_maintenance_archive_copy_rejects_changed_writer_evidence(maintenance_sample):
    _repo, _source, target, _original, _maintenance, evidence, _offline = maintenance_sample
    evidence.write_bytes(b'{"synthetic":true,"writers":1}')
    with pytest.raises(ValueError, match="evidence changed"):
        _apply_maintenance(maintenance_sample)
    assert not target.exists()


def test_maintenance_archive_copy_rejects_hard_linked_operator_receipt(maintenance_sample):
    _repo, _source, target, _original, _maintenance, _evidence, offline = maintenance_sample
    os.link(offline, offline.with_name("alias.json"))
    with pytest.raises(ValueError, match="links or junctions"):
        _apply_maintenance(maintenance_sample)
    assert not target.exists()


def test_maintenance_archive_copy_rejects_nonempty_or_repository_destination(maintenance_sample):
    repo, source, target, _original, maintenance, _evidence, offline = maintenance_sample
    target.mkdir(parents=True)
    unique = target / "unique target evidence.txt"
    unique.write_bytes(b"must never be overwritten")
    with pytest.raises(ValueError, match="absent or empty"):
        _apply_maintenance(maintenance_sample)
    assert unique.read_bytes() == b"must never be overwritten"
    with pytest.raises(ValueError, match="external target"):
        apply_maintenance_archive_relocation(
            plan_archive_relocation(source, repo / "data" / "other archive"), repo_root=repo,
            owner_token=maintenance["owner_token"], offline_receipt=offline,
        )


@pytest.mark.parametrize("change", ["add_file", "change_copied_file", "remove_target", "add_target"])
def test_archive_copy_rechecks_full_source_set_before_publishing_receipt(sample, monkeypatch, change):
    import scripts.archive_storage_migration as migration

    owned, source, target, original = sample
    later = source / "ZZZ" / "later.txt"
    later.parent.mkdir()
    later.write_bytes(b"later synthetic archive")
    plan = plan_archive_relocation(source, target)
    real_sha256 = migration._file_sha256
    def change_after_early_copy(path):
        result = real_sha256(path)
        if path == target / "ZZZ" / "later.txt":
            if change == "add_file":
                (source / "added.txt").write_bytes(b"new archive source")
            elif change == "change_copied_file":
                original.write_bytes(b"changed source after its copy")
            elif change == "remove_target":
                (target / original.relative_to(source)).unlink(missing_ok=True)
            else:
                (target / "unexpected.txt").write_bytes(b"unexpected target archive")
        return result
    monkeypatch.setattr(migration, "_file_sha256", change_after_early_copy)
    with pytest.raises(ValueError, match="source set changed|conflicting file|copy file set"):
        apply_sample_archive_relocation(plan, owned)
    assert not (target / ".moss-archive-relocations.json").exists()


def test_maintenance_exclusion_is_rechecked_before_receipt_publication(maintenance_sample, monkeypatch):
    import scripts.archive_storage_migration as migration

    repo, _source, target, _original, _maintenance, _evidence, _offline = maintenance_sample
    real_sha256 = migration._file_sha256
    def remove_owner_after_copy(path):
        result = real_sha256(path)
        if path == target / "source.xls":
            (repo / "tmp-governance" / "runtime-clean" / "control" / "maintenance.json").unlink(missing_ok=True)
        return result
    monkeypatch.setattr(migration, "_file_sha256", remove_owner_after_copy)
    with pytest.raises(FileNotFoundError):
        _apply_maintenance(maintenance_sample)
    assert not (target / ".moss-archive-relocations.json").exists()


@pytest.mark.parametrize("family", ["zqtz", "tyw", "pnl_csv", "pnl_xls", "pnl_516"])
def test_preview_parser_uses_captured_bytes_even_when_historical_file_is_destroyed(tmp_path, family):
    from backend.app.core_finance.source_preview_parsers import parse_source_file
    from tests.test_pnl_source_fi_row_mapping import FI_HEADERS, _write_fi_xls
    from tests.test_pnl_source_preview_flow import _write_nonstd_preview_workbook
    from tests.test_snapshot_materialize_flow import _write_synthetic_snapshot_inputs

    if family in {"zqtz", "tyw"}:
        _write_synthetic_snapshot_inputs(tmp_path, "2025-12-31")
        path = tmp_path / ("ZQTZSHOW-20251231.xls" if family == "zqtz" else "TYWLSHOW-20251231.xls")
    elif family == "pnl_516":
        path = tmp_path / "\u975e\u6807516-20260101-0228.xlsx"
        _write_nonstd_preview_workbook(path)
    elif family == "pnl_xls":
        path = tmp_path / "FI\u635f\u76ca202512.xls"
        _write_fi_xls(path, FI_HEADERS, [["B1", "name", "book", "center", "type", "bond", "USD", 1.25, -12.5, None]])
    else:
        path = tmp_path / "FI\u635f\u76ca202512.csv"
        path.write_bytes(('\ufeff\u503a\u5238\u4ee3\u7801,\u503a\u5238\u540d\u79f0,\u6295\u8d44\u7c7b\u578b,\u6210\u672c\u4e2d\u5fc3\r\nB1,"embedded\r\nname",bond,center\r\n').encode("utf-8"))
    before = parse_source_file(path, "historical_batch", "historical_source_version")
    payload = path.read_bytes()
    path.write_bytes(b"historical path is unavailable as valid parser input")
    assert parse_source_file(path, "historical_batch", "historical_source_version", file_bytes=payload) == before
    assert before[2]


def test_pnl_migration_preserves_full_rows_identity_and_fails_closed_before_direct_fallback(sample):
    from backend.app.repositories.governance_repo import SOURCE_MANIFEST_STREAM, GovernanceRepository
    from backend.app.services.pnl_source_service import list_pnl_refresh_report_dates, load_latest_pnl_refresh_input
    from backend.app.services.pnl_v1_cache_support import _pnl_v1_data_manifest_archived_paths_fingerprint
    from tests.test_pnl_source_fi_row_mapping import FI_HEADERS, _write_fi_xls

    owned, source, _target, original = sample
    _write_fi_xls(original, FI_HEADERS, [["B1", "name", "book", "center", "type", "bond", "USD", 1.25, -12.5, None]])
    governance = owned / "governance"
    repo = GovernanceRepository(governance)
    repo.append(SOURCE_MANIFEST_STREAM, {
        "source_family": "pnl", "report_date": "2025-12-31", "source_file": "FI\u635f\u76ca202512.xls",
        "source_version": "sv_historical", "ingest_batch_id": "ib_historical", "created_at": "2026-01-01T00:00:00Z",
        "status": "completed", "archived_path": str(original),
    })
    manifest = governance / "source_manifest.jsonl"
    historical_bytes = manifest.read_bytes()
    data_root = owned / "inputs"
    data_root.mkdir()
    kwargs = {"governance_dir": governance, "data_root": data_root, "report_date": "2025-12-31"}
    before = load_latest_pnl_refresh_input(**kwargs, archive_root=source)
    # The physical root may be named processed; eligibility still follows the
    # original historical identity rather than the new directory name.
    target = owned / "processed"
    receipt = apply_sample_archive_relocation(plan_archive_relocation(source, target), owned)
    original.write_bytes(b"old location cannot supply valid FI bytes")
    after = load_latest_pnl_refresh_input(**kwargs, archive_root=target)
    assert after == before
    assert after.fi_rows[0]["source_version"] == "sv_historical"
    assert list_pnl_refresh_report_dates(governance_dir=governance, data_root=data_root, archive_root=target) == ["2025-12-31"]
    assert len(_pnl_v1_data_manifest_archived_paths_fingerprint(str(governance), target)) == 1
    assert manifest.read_bytes() == historical_bytes
    mapped = target / "ZQTZSHOW" / "files" / "source.xls"
    mapped_stat = mapped.stat()
    expected_hash = hashlib.sha256(mapped.read_bytes()).hexdigest()
    _rewrite_receipt(receipt, lambda value: value["entries"][0].update(sha256="0" * 64))
    current_stat = mapped.stat()
    assert (current_stat.st_size, current_stat.st_mtime_ns, current_stat.st_ino) == (
        mapped_stat.st_size, mapped_stat.st_mtime_ns, mapped_stat.st_ino,
    )
    with pytest.raises(ValueError, match="content hash"):
        _pnl_v1_data_manifest_archived_paths_fingerprint(str(governance), target)
    with pytest.raises(ValueError, match="content hash"):
        load_latest_pnl_refresh_input(**kwargs, archive_root=target)
    _rewrite_receipt(receipt, lambda value: value["entries"][0].update(sha256=expected_hash))
    direct = data_root / "FI\u635f\u76ca202512.xls"
    _write_fi_xls(direct, FI_HEADERS, [["OTHER", "fallback", "book", "center", "type", "bond", "USD", 999, 999, 999]])
    receipt.chmod(stat.S_IRUSR | stat.S_IWUSR)
    receipt.unlink()
    with pytest.raises(ValueError, match="outside local archive root"):
        load_latest_pnl_refresh_input(**kwargs, archive_root=target)
    with pytest.raises(ValueError, match="outside local archive root"):
        _pnl_v1_data_manifest_archived_paths_fingerprint(str(governance), target)


def test_excluded_processed_history_never_resolves_archive_receipt(tmp_path, monkeypatch):
    from backend.app.repositories.governance_repo import SOURCE_MANIFEST_STREAM, GovernanceRepository
    from backend.app.services import pnl_source_service, pnl_v1_cache_support

    governance = tmp_path / "governance"
    GovernanceRepository(governance).append(SOURCE_MANIFEST_STREAM, {
        "source_family": "pnl", "status": "completed", "archived_path": str(tmp_path / "old" / "processed" / "FI.xls"),
    })
    def unexpected(*args, **kwargs):
        pytest.fail("excluded historical processed path must not resolve a relocation receipt")
    monkeypatch.setattr(pnl_source_service, "resolve_local_archive_path", unexpected)
    monkeypatch.setattr(pnl_v1_cache_support, "resolve_local_archive_path", unexpected)
    assert pnl_source_service._manifest_candidates(governance, archive_root=tmp_path / "current") == []
    assert pnl_v1_cache_support._pnl_v1_data_manifest_archived_paths_fingerprint(str(governance), tmp_path / "current") == ()


def test_nonstd_covered_range_carries_verified_archive_root_and_original_identity(sample):
    from openpyxl import Workbook

    from backend.app.repositories.governance_repo import SOURCE_MANIFEST_STREAM, GovernanceRepository
    from backend.app.services.pnl_source_service import load_latest_pnl_refresh_input

    owned, source, target, original = sample
    historical = original.with_name("\u975e\u6807514-20260101-0630(1).xlsx")
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["\u8d26\u52a1\u65e5\u671f", "\u4f1a\u8ba1\u4e8b\u4ef6", "\u6210\u672c\u4e2d\u5fc3", "\u6295\u8d44\u7ec4\u5408", "\u8d44\u4ea7\u4ee3\u7801", "\u501f\u8d37\u6807\u8bc6", "\u79d1\u76ee\u53f7", "\u91d1\u989d"])
    sheet.append(["2026-05-31", "interest", "5010", "FIOA", "JM1", "\u8d37", "51401000004", "106.25"])
    sheet.append(["2026-06-30", "interest", "5010", "FIOA", "JM1", "\u8d37", "51401000004", "212"])
    workbook.save(historical)
    workbook.close()
    original.unlink()
    governance = owned / "governance"
    GovernanceRepository(governance).append(SOURCE_MANIFEST_STREAM, {
        "source_family": "pnl_514", "report_date": "2026-06-30", "source_file": historical.name,
        "source_version": "sv_range_historical", "ingest_batch_id": "ib_range_historical", "created_at": "2026-07-01T00:00:00Z",
        "status": "completed", "archived_path": str(historical),
    })
    kwargs = {"governance_dir": governance, "data_root": owned / "missing input", "report_date": "2026-05-31"}
    before = load_latest_pnl_refresh_input(**kwargs, archive_root=source)
    apply_sample_archive_relocation(plan_archive_relocation(source, target), owned)
    historical.write_bytes(b"invalid old workbook must never be reopened")
    after = load_latest_pnl_refresh_input(**kwargs, archive_root=target)
    assert after == before
    assert len(after.nonstd_rows_by_type["514"]) == 1
    assert after.nonstd_rows_by_type["514"][0]["source_version"] == "sv_range_historical"


def test_data_update_preflight_uses_verified_current_archive_and_rejects_bad_receipt(sample, monkeypatch):
    from types import SimpleNamespace

    from backend.app.repositories.governance_repo import SOURCE_MANIFEST_STREAM, GovernanceRepository
    from backend.app.services import data_update_service

    owned, source, target, original = sample
    governance = owned / "governance"
    GovernanceRepository(governance).append(SOURCE_MANIFEST_STREAM, {
        "source_family": "zqtz", "status": "completed", "archived_path": str(original),
        "report_date": "2025-12-31", "ingest_batch_id": "historical", "source_version": "sv_historical",
    })
    receipt = apply_sample_archive_relocation(plan_archive_relocation(source, target), owned)
    current = target / "ZQTZSHOW" / "files" / "source.xls"
    monkeypatch.setattr(data_update_service.time, "time", lambda: current.stat().st_mtime + 61)
    settings = SimpleNamespace(data_input_root=owned / "missing inputs", governance_path=governance, local_archive_path=target)
    preflight = data_update_service.input_preflight(settings, "2025-12-31", "balance_daily")
    assert next(row for row in preflight["checks"] if row["key"] == "zqtz")["status"] == "ready"
    _rewrite_receipt(receipt, lambda value: value["entries"][0].update(sha256="0" * 64))
    assert original.exists()
    with pytest.raises(ValueError, match="content hash"):
        data_update_service.input_preflight(settings, "2025-12-31", "balance_daily")


def test_production_pnl_archive_consumers_always_pass_configured_root():
    root = Path(__file__).resolve().parents[1]
    expected_calls = {
        "backend/app/services/pnl_service.py": 5,
        "backend/app/tasks/data_update_center.py": 1,
        "backend/scripts/bootstrap_data_pipeline.py": 1,
        "scripts/run_materialize_pipeline_sync.py": 1,
        "scripts/run_global_data_refresh.py": 1,
    }
    names = {"load_latest_pnl_refresh_input", "list_pnl_refresh_report_dates", "_pnl_v1_data_cache_key"}
    for relative, expected in expected_calls.items():
        tree = ast.parse((root / relative).read_text(encoding="utf-8"))
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in names]
        assert len(calls) == expected, relative
        for call in calls:
            argument = next((item.value for item in call.keywords if item.arg == "archive_root"), None)
            assert argument is not None, f"{relative}:{call.lineno}"
            assert isinstance(argument, ast.Attribute) and argument.attr == "local_archive_path", relative
