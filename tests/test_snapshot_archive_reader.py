"""Archive read helper must return bytes without requiring callers to open Path."""

from __future__ import annotations

from pathlib import Path

from backend.app.repositories.object_store_repo import ObjectStoreRepository


def test_read_archived_bytes_local_mode_returns_file_payload(tmp_path):
    archive_root = tmp_path / "archive"
    store = ObjectStoreRepository(
        endpoint="localhost:9000",
        access_key="x",
        secret_key="x",
        bucket="b",
        mode="local",
        local_archive_path=str(archive_root),
    )
    payload = b"hello-snapshot-archive"
    info = store.archive_bytes(
        payload,
        source_name="zqtz",
        source_key="unit-test-key",
        ingest_batch_id="batch-a",
        suffix=".xls",
    )
    archived_path = str(info["archived_path"])
    assert Path(archived_path).is_file()
    assert store.read_archived_bytes(archived_path) == payload


def test_open_archived_binary_yields_readable_stream_matching_bytes(tmp_path):
    archive_root = tmp_path / "archive"
    store = ObjectStoreRepository(
        endpoint="localhost:9000",
        access_key="x",
        secret_key="x",
        bucket="b",
        mode="local",
        local_archive_path=str(archive_root),
    )
    payload = b"stream-read-check"
    info = store.archive_bytes(
        payload,
        source_name="tyw",
        source_key="key-b",
        ingest_batch_id="batch-b",
        suffix=".xls",
    )
    archived_path = str(info["archived_path"])
    with store.open_archived_binary(archived_path) as handle:
        assert handle.read() == payload
    assert store.read_archived_bytes(archived_path) == payload


def test_read_archived_bytes_rejects_non_local_mode():
    store = ObjectStoreRepository(
        endpoint="localhost:9000",
        access_key="x",
        secret_key="x",
        bucket="b",
        mode="minio",
        local_archive_path="data/archive",
    )
    try:
        store.read_archived_bytes("s3://any")
    except NotImplementedError as exc:
        assert "local" in str(exc).lower()
    else:
        raise AssertionError("expected NotImplementedError")
