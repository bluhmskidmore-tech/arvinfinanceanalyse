from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts import trusted_base_source as source_module

COMMIT = "a" * 40


def _fake_git(monkeypatch: pytest.MonkeyPatch, additions: dict[str, bytes] | None = None, *, mode: str = "100644"):
    files = {
        "backend/app/main.py": b"value = 'trusted-base'\n",
        "backend/pyproject.toml": b"[project]\nname = 'fixture'\n",
        "backend/uv.lock": b"version = 1\n",
        "backend/.env": b"MOSS_USER_ROLE=admin\n",
        "backend/private.json": b'{"business": "must not extract"}\n',
    } | (additions or {})
    blobs = {path: hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest()
             for path, content in files.items()}
    requests = []

    def git(repo, arguments, *, input_bytes=None):
        requests.append((arguments, input_bytes))
        if arguments[0] == "ls-tree":
            assert COMMIT in arguments
            return b"".join(f"{mode} blob {blobs[path]}\t{path}\0".encode() for path in sorted(files))
        assert arguments == ["cat-file", "--batch"]
        objects = {blobs[path]: content for path, content in files.items()}
        return b"".join(object_id + f" blob {len(objects[object_id.decode()])}\n".encode()
                        + objects[object_id.decode()] + b"\n" for object_id in input_bytes.splitlines())

    monkeypatch.setattr(source_module, "_git", git)
    return requests


def test_source_extraction_uses_exact_blobs_and_excludes_env_and_data(tmp_path, monkeypatch):
    requests = _fake_git(monkeypatch)
    parent = tmp_path / ".codex-tmp" / "bootstrap"
    with source_module.isolated_backend_source(tmp_path, COMMIT, parent) as source:
        assert (source.root / "backend/app/main.py").read_bytes() == b"value = 'trusted-base'\n"
        assert not (source.root / "backend/.env").exists()
        assert not (source.root / "backend/private.json").exists()
        assert source.provenance()["commit"] == COMMIT
        assert len(source.inputs_sha256) == 64
        assert source.lock_sha256 == hashlib.sha256(b"version = 1\n").hexdigest()
        isolated = source.root
    assert not isolated.exists()
    assert len(requests[1][1].splitlines()) == 3


def test_relative_source_parent_still_yields_an_absolute_import_root(tmp_path, monkeypatch):
    _fake_git(monkeypatch)
    monkeypatch.chdir(tmp_path)
    with source_module.isolated_backend_source(tmp_path, COMMIT, Path(".codex-tmp/bootstrap")) as source:
        assert source.root.is_absolute()
        result = source_module.run_source_python(source, "print(Path(sys.argv[1]).is_dir())", [])
        assert result.returncode == 0
        assert result.stdout.strip() == "True"


@pytest.mark.parametrize("mode", ["120000", "160000", "040000"])
def test_symlinks_submodules_and_non_regular_objects_are_rejected(tmp_path, monkeypatch, mode):
    _fake_git(monkeypatch, mode=mode)
    with pytest.raises(source_module.BaseSourceError, match="symlink, submodule"):
        with source_module.isolated_backend_source(tmp_path, COMMIT, tmp_path / ".codex-tmp/bootstrap"):
            pytest.fail("unsafe object was extracted")


@pytest.mark.parametrize("relative", ["backend/../escape.py", "backend/C:escape.py", "backend/con.py", "backend/name. /a.py"])
def test_source_paths_cannot_escape_or_alias_windows_paths(tmp_path, monkeypatch, relative):
    _fake_git(monkeypatch, {relative: b"pass\n"})
    with pytest.raises(source_module.BaseSourceError, match="path is unsafe"):
        with source_module.isolated_backend_source(tmp_path, COMMIT, tmp_path / ".codex-tmp/bootstrap"):
            pytest.fail("unsafe path was extracted")
    assert not (tmp_path / "escape.py").exists()


def test_case_colliding_source_paths_fail_closed(tmp_path, monkeypatch):
    _fake_git(monkeypatch, {"backend/app/MAIN.py": b"different = True\n"})
    with pytest.raises(source_module.BaseSourceError, match="case-colliding"):
        with source_module.isolated_backend_source(tmp_path, COMMIT, tmp_path / ".codex-tmp/bootstrap"):
            pytest.fail("case collision was extracted")


def test_source_parent_must_stay_in_repository_temporary_directory(tmp_path, monkeypatch):
    _fake_git(monkeypatch)
    with pytest.raises(source_module.BaseSourceError, match="inside this repository"):
        with source_module.isolated_backend_source(tmp_path, COMMIT, tmp_path / "outside"):
            pytest.fail("outside source parent was accepted")


def test_blob_content_must_match_git_object_identity(tmp_path, monkeypatch):
    _fake_git(monkeypatch)
    real_fake = source_module._git

    def tampered(repo, arguments, **kwargs):
        raw = real_fake(repo, arguments, **kwargs)
        return raw.replace(b"trusted-base", b"spoofed-base") if arguments[0] == "cat-file" else raw

    monkeypatch.setattr(source_module, "_git", tampered)
    with pytest.raises(source_module.BaseSourceError, match="git identity"):
        with source_module.isolated_backend_source(tmp_path, COMMIT, tmp_path / ".codex-tmp/bootstrap"):
            pytest.fail("tampered source was accepted")


def test_source_process_cannot_inherit_local_settings_or_editable_app(tmp_path, monkeypatch):
    _fake_git(monkeypatch)
    monkeypatch.setenv("MOSS_USER_ROLE", "admin")
    monkeypatch.setenv("MOSS_DUCKDB_PATH", "D:/private/moss.duckdb")
    monkeypatch.setenv("RAW_FILES_DIR", "D:/private/raw")
    monkeypatch.setenv("PYTHONPATH", str(Path.cwd() / "backend"))
    with source_module.isolated_backend_source(tmp_path, COMMIT, tmp_path / ".codex-tmp/bootstrap") as source:
        completed = source_module.run_source_python(source, """
import os,json
root=Path(sys.argv[1])
sys.path[:0]=[str(root),str(root/'backend')]
import backend.app.main as main
try:
    import app.core_finance
    escaped=True
except ModuleNotFoundError:
    escaped=False
print(json.dumps({'value':main.value,'escaped':escaped,'env':{
    key:os.getenv(key) for key in ['MOSS_USER_ROLE','MOSS_DUCKDB_PATH','RAW_FILES_DIR','PYTHONPATH']
}}))
""", [])
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["value"] == "trusted-base"
    assert payload["escaped"] is False
    assert all(value is None for value in payload["env"].values())
