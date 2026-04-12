"""Contract tests for backend.app.repositories.object_store_repo."""

from __future__ import annotations

import hashlib
import re
import socket
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from backend.app.repositories.object_store_repo import ObjectStoreRepository


def test_safe_component_strips_unsafe_chars_and_empty_fallback():
    repo = ObjectStoreRepository(
        endpoint="localhost:9000",
        access_key="k",
        secret_key="s",
        bucket="b",
    )
    assert repo._safe_component("ab:c d?.xls") == "ab_c_d_.xls"
    assert repo._safe_component("...") == "artifact"
    assert repo._safe_component("") == "artifact"


def test_build_archived_filename_suffix_digest_batch_and_deterministic():
    repo = ObjectStoreRepository(
        endpoint="localhost:9000",
        access_key="k",
        secret_key="s",
        bucket="b",
        mode="local",
    )
    src = Path("My File!.xls")
    key = "/data/input/a.xls"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
    name = repo._build_archived_filename(src, source_key=key, ingest_batch_id="ib-1/2")
    assert name.endswith(".xls")
    assert digest in name
    assert "__ib-1_2" in name
    again = repo._build_archived_filename(src, source_key=key, ingest_batch_id="ib-1/2")
    assert name == again


def test_new_archive_batch_id_format():
    repo = ObjectStoreRepository(
        endpoint="localhost:9000",
        access_key="k",
        secret_key="s",
        bucket="b",
    )
    batch_id = repo._new_archive_batch_id()
    assert batch_id.startswith("archive-")
    # strftime uses %H%M%S%f (12 digits: HHMMSS +6-digit microsecond) before literal Z
    assert re.match(r"^archive-\d{8}T\d{12}Z-[0-9a-f]{8}$", batch_id)


def test_healthcheck_local_creates_dir_and_reports_fields(tmp_path):
    root = tmp_path / "arch"
    repo = ObjectStoreRepository(
        endpoint="localhost:9000",
        access_key="k",
        secret_key="s",
        bucket="my-bucket",
        mode="local",
        local_archive_path=str(root),
    )
    result = repo.healthcheck()
    assert result["ok"] is True
    assert result["mode"] == "local"
    assert result["path"] == str(root)
    assert result["bucket"] == "my-bucket"
    assert root.is_dir()


def test_healthcheck_local_mkdir_oserror(monkeypatch, tmp_path):
    root = tmp_path / "arch"

    def _boom(self, *args, **kwargs):
        raise OSError("mkdir failed")

    monkeypatch.setattr(Path, "mkdir", _boom)
    repo = ObjectStoreRepository(
        endpoint="localhost:9000",
        access_key="k",
        secret_key="s",
        bucket="b",
        mode="local",
        local_archive_path=str(root),
    )
    result = repo.healthcheck()
    assert result["ok"] is False
    assert result["error"] == "mkdir failed"
    assert result["mode"] == "local"


def test_healthcheck_minio_success(monkeypatch):
    cm = MagicMock()
    cm.__enter__.return_value = None
    cm.__exit__.return_value = None
    monkeypatch.setattr(socket, "create_connection", MagicMock(return_value=cm))
    repo = ObjectStoreRepository(
        endpoint="127.0.0.1:9000",
        access_key="k",
        secret_key="s",
        bucket="buck",
        mode="minio",
    )
    out = repo.healthcheck()
    assert out == {"ok": True, "mode": "minio", "endpoint": "127.0.0.1:9000", "bucket": "buck"}
    socket.create_connection.assert_called_once_with(("127.0.0.1", 9000), timeout=0.2)


def test_healthcheck_minio_connection_error(monkeypatch):
    monkeypatch.setattr(socket, "create_connection", MagicMock(side_effect=OSError("refused")))
    repo = ObjectStoreRepository(
        endpoint="127.0.0.1:9000",
        access_key="k",
        secret_key="s",
        bucket="buck",
        mode="minio",
    )
    assert repo.healthcheck()["ok"] is False


def test_archive_file_not_implemented_for_minio(tmp_path):
    repo = ObjectStoreRepository(
        endpoint="x:9000",
        access_key="k",
        secret_key="s",
        bucket="b",
        mode="minio",
        local_archive_path=str(tmp_path),
    )
    p = tmp_path / "a.txt"
    p.write_bytes(b"hi")
    with pytest.raises(NotImplementedError, match="local archive"):
        repo.archive_file(p, "src")


def test_archive_bytes_not_implemented_for_minio(tmp_path):
    repo = ObjectStoreRepository(
        endpoint="x:9000",
        access_key="k",
        secret_key="s",
        bucket="b",
        mode="minio",
        local_archive_path=str(tmp_path),
    )
    with pytest.raises(NotImplementedError, match="local archive"):
        repo.archive_bytes(b"{}", "src", "key")


def test_read_archived_bytes_roundtrip_local(tmp_path):
    repo = ObjectStoreRepository(
        endpoint="x:9000",
        access_key="k",
        secret_key="s",
        bucket="b",
        mode="local",
        local_archive_path=str(tmp_path),
    )
    src = tmp_path / "in.bin"
    src.write_bytes(b"abc")
    info = repo.archive_file(src, "MySource", ingest_batch_id="fixed-batch")
    data = repo.read_archived_bytes(str(info["archived_path"]))
    assert data == b"abc"


def test_open_archived_binary_local(tmp_path):
    repo = ObjectStoreRepository(
        endpoint="x:9000",
        access_key="k",
        secret_key="s",
        bucket="b",
        mode="local",
        local_archive_path=str(tmp_path),
    )
    info = repo.archive_bytes(b"xyz", "S", "logical/key.json", suffix=".json")
    with repo.open_archived_binary(str(info["archived_path"])) as handle:
        assert handle.read() == b"xyz"


def test_read_and_open_not_implemented_minio(tmp_path):
    repo = ObjectStoreRepository(
        endpoint="x:9000",
        access_key="k",
        secret_key="s",
        bucket="b",
        mode="minio",
        local_archive_path=str(tmp_path),
    )
    with pytest.raises(NotImplementedError):
        repo.read_archived_bytes("/any")
    with pytest.raises(NotImplementedError):
        with repo.open_archived_binary("/any"):
            pass


def test_read_archived_bytes_missing_file(tmp_path):
    repo = ObjectStoreRepository(
        endpoint="x:9000",
        access_key="k",
        secret_key="s",
        bucket="b",
        mode="local",
        local_archive_path=str(tmp_path),
    )
    with pytest.raises(FileNotFoundError):
        repo.read_archived_bytes(str(tmp_path / "nope.bin"))


def test_build_vendor_snapshot_manifest_shape():
    repo = ObjectStoreRepository(
        endpoint="x:9000",
        access_key="k",
        secret_key="s",
        bucket="b",
        mode="local",
    )
    m = repo.build_vendor_snapshot_manifest("choice", "1.2.3", "/path/arch.json")
    assert m == {
        "vendor_name": "choice",
        "vendor_version": "1.2.3",
        "snapshot_kind": "macro",
        "archive_mode": "local",
        "archived_path": "/path/arch.json",
        "capture_mode": "skeleton",
        "read_target": "duckdb",
    }
