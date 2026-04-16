import json

from tests.helpers import load_module


def test_vendor_snapshot_manifest_skeleton_can_be_written_to_governance(tmp_path):
    schema_module = load_module("backend.app.schemas.vendor", "backend/app/schemas/vendor.py")
    repo_module = load_module(
        "backend.app.repositories.object_store_repo",
        "backend/app/repositories/object_store_repo.py",
    )
    governance_module = load_module(
        "backend.app.repositories.governance_repo",
        "backend/app/repositories/governance_repo.py",
    )

    manifest_model = getattr(schema_module, "VendorSnapshotManifest", None)
    if manifest_model is None:
        raise AssertionError("backend.app.schemas.vendor must define VendorSnapshotManifest")

    object_store_repo = repo_module.ObjectStoreRepository(
        endpoint="127.0.0.1:1",
        access_key="minioadmin",
        secret_key="minioadmin",
        bucket="moss-artifacts",
        mode="local",
        local_archive_path=str(tmp_path / "archive"),
    )
    manifest = object_store_repo.build_vendor_snapshot_manifest(
        vendor_name="choice",
        vendor_version="vv_choice_skeleton",
        archived_path=str(tmp_path / "archive" / "choice" / "raw" / "snapshot.json"),
        snapshot_kind="macro",
    )

    typed_manifest = manifest_model(**manifest)
    governance_repo = governance_module.GovernanceRepository(base_dir=tmp_path / "governance")
    governance_repo.append(governance_module.VENDOR_SNAPSHOT_MANIFEST_STREAM, typed_manifest.model_dump(mode="json"))

    rows = governance_repo.read_all(governance_module.VENDOR_SNAPSHOT_MANIFEST_STREAM)
    assert rows == [typed_manifest.model_dump(mode="json")]
    assert rows[0]["capture_mode"] == "skeleton"


def test_vendor_snapshot_manifest_can_report_live_capture_mode(tmp_path):
    schema_module = load_module("backend.app.schemas.vendor", "backend/app/schemas/vendor.py")
    repo_module = load_module(
        "backend.app.repositories.object_store_repo",
        "backend/app/repositories/object_store_repo.py",
    )

    object_store_repo = repo_module.ObjectStoreRepository(
        endpoint="127.0.0.1:1",
        access_key="minioadmin",
        secret_key="minioadmin",
        bucket="moss-artifacts",
        mode="local",
        local_archive_path=str(tmp_path / "archive"),
    )
    manifest = object_store_repo.build_vendor_snapshot_manifest(
        vendor_name="choice",
        vendor_version="vv_choice_live",
        archived_path=str(tmp_path / "archive" / "choice" / "raw" / "snapshot.json"),
        snapshot_kind="macro",
        capture_mode="live",
    )

    typed_manifest = schema_module.VendorSnapshotManifest(**manifest)

    assert typed_manifest.capture_mode == "live"
    assert typed_manifest.archive_mode == "local"


def test_materialize_metadata_keeps_vendor_version_separate_from_source_version():
    schema_module = load_module(
        "backend.app.schemas.materialize",
        "backend/app/schemas/materialize.py",
    )

    build_run = schema_module.CacheBuildRunRecord(
        run_id="materialize:test-run",
        job_name="materialize",
        status="completed",
        cache_key="phase1.native.cache",
        lock="lock:duckdb:materialize",
        source_version="sv_preview_empty",
        vendor_version="vv_none",
    )
    manifest = schema_module.CacheManifestRecord(
        cache_key="phase1.native.cache",
        source_version="sv_preview_empty",
        vendor_version="vv_none",
        rule_version="rv_phase1_source_preview_v1",
    )

    assert build_run.source_version == "sv_preview_empty"
    assert build_run.vendor_version == "vv_none"
    assert manifest.source_version == "sv_preview_empty"
    assert manifest.vendor_version == "vv_none"

    dumped = json.loads(manifest.model_dump_json())
    assert dumped["source_version"] == "sv_preview_empty"
    assert dumped["vendor_version"] == "vv_none"
