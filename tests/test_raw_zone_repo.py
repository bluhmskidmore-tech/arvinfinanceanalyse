from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from backend.app.repositories.raw_zone_repo import RawZoneRepository


def test_archive_bytes_writes_and_returns_sha256(tmp_path) -> None:
    repo = RawZoneRepository(local_raw_path=str(tmp_path / "raw"))
    payload = b'{"x": 1}'
    out = repo.archive_bytes("acme", "batch-1", "snap.json", payload)
    assert out["sha256"] == hashlib.sha256(payload).hexdigest()
    p = Path(str(out["raw_zone_path"]))
    assert p.read_bytes() == payload
    assert "archived_at" in out


def test_archive_file_matches_archive_bytes(tmp_path) -> None:
    repo = RawZoneRepository(local_raw_path=str(tmp_path / "raw"))
    src = tmp_path / "in.bin"
    src.write_bytes(b"abc")
    out = repo.archive_file("v", "b2", src)
    assert Path(str(out["raw_zone_path"])).read_bytes() == b"abc"


def test_read_bytes_roundtrip(tmp_path) -> None:
    repo = RawZoneRepository(local_raw_path=str(tmp_path / "raw"))
    out = repo.archive_bytes("v", "b", "f.txt", b"hello")
    assert repo.read_bytes(str(out["raw_zone_path"])) == b"hello"


def test_idempotent_same_payload(tmp_path) -> None:
    repo = RawZoneRepository(local_raw_path=str(tmp_path / "raw"))
    out1 = repo.archive_bytes("v", "b", "f.json", b"same")
    out2 = repo.archive_bytes("v", "b", "f.json", b"same")
    assert out1["raw_zone_path"] == out2["raw_zone_path"]
    assert out1["sha256"] == out2["sha256"]


def test_rejects_different_content_same_path(tmp_path) -> None:
    repo = RawZoneRepository(local_raw_path=str(tmp_path / "raw"))
    repo.archive_bytes("v", "b", "f.json", b"a")
    with pytest.raises(FileExistsError, match="different content"):
        repo.archive_bytes("v", "b", "f.json", b"b")


def test_healthcheck_ok(tmp_path) -> None:
    repo = RawZoneRepository(local_raw_path=str(tmp_path / "raw"))
    hc = repo.healthcheck()
    assert hc["ok"] is True
    assert hc["mode"] == "local_raw"
