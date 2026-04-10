from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from tests.helpers import ROOT, load_module


def test_ingest_service_scans_data_input_and_returns_manifest_rows():
    module = load_module("backend.app.services.ingest_service", "backend/app/services/ingest_service.py")
    ingest_service = getattr(module, "IngestService", None)
    if ingest_service is None:
        pytest.fail("backend.app.services.ingest_service must define IngestService")

    service = ingest_service(data_root=ROOT / "data_input")
    rows = service.scan()
    assert rows, "Expected scan() to discover at least one source file under data_input"
    first = rows[0]
    assert {"source_name", "file_name", "file_path", "file_size"} <= set(first)


def test_ingest_service_archives_files_in_local_mode_and_records_archive_metadata(tmp_path):
    ingest_module = load_module("backend.app.services.ingest_service", "backend/app/services/ingest_service.py")
    manifest_module = load_module(
        "backend.app.repositories.source_manifest_repo",
        "backend/app/repositories/source_manifest_repo.py",
    )
    object_store_module = load_module(
        "backend.app.repositories.object_store_repo",
        "backend/app/repositories/object_store_repo.py",
    )

    service = ingest_module.IngestService(
        data_root=ROOT / "data_input",
        manifest_repo=manifest_module.SourceManifestRepository(),
        object_store_repo=object_store_module.ObjectStoreRepository(
            endpoint="127.0.0.1:1",
            access_key="minioadmin",
            secret_key="minioadmin",
            bucket="moss-artifacts",
            mode="local",
            local_archive_path=str(tmp_path / "archive"),
        ),
    )

    rows = service.scan_and_archive()
    assert rows, "Expected scan_and_archive() to discover and archive source files"
    first = rows[0]
    assert first["archive_mode"] == "local"
    assert first["archived_path"]
    assert Path(first["archived_path"]).exists()
    assert service.manifest_repo.rows


def test_ingest_service_archives_duplicate_basenames_without_overwriting(tmp_path):
    ingest_module = load_module("backend.app.services.ingest_service", "backend/app/services/ingest_service.py")
    manifest_module = load_module(
        "backend.app.repositories.source_manifest_repo",
        "backend/app/repositories/source_manifest_repo.py",
    )
    object_store_module = load_module(
        "backend.app.repositories.object_store_repo",
        "backend/app/repositories/object_store_repo.py",
    )

    data_root = tmp_path / "data_input"
    first_source = data_root / "desk-a" / "demo-positions.csv"
    second_source = data_root / "desk-b" / "demo-positions.csv"
    first_source.parent.mkdir(parents=True, exist_ok=True)
    second_source.parent.mkdir(parents=True, exist_ok=True)
    first_source.write_text("desk-a", encoding="utf-8")
    second_source.write_text("desk-b", encoding="utf-8")

    archive_root = tmp_path / "archive"
    service = ingest_module.IngestService(
        data_root=data_root,
        manifest_repo=manifest_module.SourceManifestRepository(),
        object_store_repo=object_store_module.ObjectStoreRepository(
            endpoint="127.0.0.1:1",
            access_key="minioadmin",
            secret_key="minioadmin",
            bucket="moss-artifacts",
            mode="local",
            local_archive_path=str(archive_root),
        ),
    )

    rows = service.scan_and_archive()
    archived_paths = [Path(row["archived_path"]) for row in rows]

    assert len(rows) == 2
    assert len(set(archived_paths)) == 2
    assert len(list((archive_root / "demo" / "files").iterdir())) == len(rows)
    assert sorted(path.read_text(encoding="utf-8") for path in archived_paths) == ["desk-a", "desk-b"]


def test_ingest_service_keeps_repeat_archives_immutable_across_runs(tmp_path):
    ingest_module = load_module("backend.app.services.ingest_service", "backend/app/services/ingest_service.py")
    manifest_module = load_module(
        "backend.app.repositories.source_manifest_repo",
        "backend/app/repositories/source_manifest_repo.py",
    )
    object_store_module = load_module(
        "backend.app.repositories.object_store_repo",
        "backend/app/repositories/object_store_repo.py",
    )

    data_root = tmp_path / "data_input"
    source_file = data_root / "desk-a" / "demo-positions.csv"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text("first-run", encoding="utf-8")

    archive_root = tmp_path / "archive"
    service = ingest_module.IngestService(
        data_root=data_root,
        manifest_repo=manifest_module.SourceManifestRepository(),
        object_store_repo=object_store_module.ObjectStoreRepository(
            endpoint="127.0.0.1:1",
            access_key="minioadmin",
            secret_key="minioadmin",
            bucket="moss-artifacts",
            mode="local",
            local_archive_path=str(archive_root),
        ),
    )

    first_rows = service.scan_and_archive()
    first_archived_path = Path(first_rows[0]["archived_path"])
    first_batch_id = first_rows[0]["ingest_batch_id"]

    source_file.write_text("second-run", encoding="utf-8")

    second_rows = service.scan_and_archive()
    second_archived_path = Path(second_rows[0]["archived_path"])
    second_batch_id = second_rows[0]["ingest_batch_id"]

    assert first_batch_id != second_batch_id
    assert first_archived_path != second_archived_path
    assert first_archived_path.exists()
    assert second_archived_path.exists()
    assert first_archived_path.read_text(encoding="utf-8") == "first-run"
    assert second_archived_path.read_text(encoding="utf-8") == "second-run"


def test_ingest_task_returns_manifest_summary(monkeypatch, tmp_path):
    ingest_task_module = sys.modules.get("backend.app.tasks.ingest")
    if ingest_task_module is None:
        ingest_task_module = load_module("backend.app.tasks.ingest", "backend/app/tasks/ingest.py")
    monkeypatch.setenv("MOSS_DATA_INPUT_ROOT", str(ROOT / "data_input"))
    monkeypatch.setattr(
        ingest_task_module,
        "get_settings",
        lambda: SimpleNamespace(
            minio_endpoint="127.0.0.1:1",
            minio_access_key="minioadmin",
            minio_secret_key="minioadmin",
            minio_bucket="moss-artifacts",
            object_store_mode="local",
            local_archive_path=tmp_path / "archive",
        ),
    )
    payload = ingest_task_module.ingest_demo_manifest.fn()
    assert payload["status"] == "completed"
    assert payload["row_count"] > 0
    assert "archive_mode" in payload


def test_ingest_task_resolves_data_root_from_runtime_environment(monkeypatch, tmp_path):
    ingest_task_module = sys.modules.get("backend.app.tasks.ingest")
    if ingest_task_module is None:
        ingest_task_module = load_module("backend.app.tasks.ingest", "backend/app/tasks/ingest.py")
    runtime_root = tmp_path / "runtime-data-input"
    captured: dict[str, object] = {}

    class FakeSummary:
        def model_dump(self, mode: str = "json") -> dict[str, object]:
            return {"status": "completed", "row_count": 0, "archive_mode": "local", "manifest_rows": []}

    class FakeIngestService:
        def __init__(self, data_root, manifest_repo, object_store_repo):
            captured["data_root"] = data_root
            captured["manifest_repo"] = manifest_repo
            captured["object_store_repo"] = object_store_repo

        def run(self):
            return FakeSummary()

    monkeypatch.setenv("MOSS_DATA_INPUT_ROOT", str(runtime_root))
    monkeypatch.setattr(ingest_task_module, "IngestService", FakeIngestService)

    payload = ingest_task_module.ingest_demo_manifest.fn()

    assert payload["status"] == "completed"
    assert captured["data_root"] == runtime_root
