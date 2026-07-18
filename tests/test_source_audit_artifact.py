from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import zipfile
from pathlib import Path

import pytest

from tests.helpers import load_module


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def _committed_source_repo(tmp_path: Path) -> tuple[Path, str, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "audit@example.invalid")
    _git(repo, "config", "user.name", "Audit Test")

    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("COMMITTED = True\n", encoding="utf-8")
    (repo / ".env").write_text("SECRET=must-not-export\n", encoding="utf-8")
    (repo / ".env.example").write_text("SECRET=\n", encoding="utf-8")
    (repo / "data").mkdir()
    (repo / "data" / "runtime.json").write_text("{}\n", encoding="utf-8")
    stale = repo / "audit_pack" / "source_snapshot"
    stale.mkdir(parents=True)
    (stale / "old.py").write_text("STALE = True\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "fixture")
    source_commit = _git(repo, "rev-parse", "HEAD")

    (repo / "generator-marker.txt").write_text(
        "generator revision\n",
        encoding="utf-8",
    )
    _git(repo, "add", "generator-marker.txt")
    _git(repo, "commit", "-m", "generator revision")
    generator_commit = _git(repo, "rev-parse", "HEAD")

    (repo / "src" / "app.py").write_text("DIRTY = True\n", encoding="utf-8")
    (repo / "src" / "untracked.py").write_text("UNTRACKED = True\n", encoding="utf-8")
    return repo, source_commit, generator_commit


def test_source_audit_artifact_is_commit_scoped_filtered_and_verifiable(
    tmp_path: Path,
) -> None:
    module = load_module(
        "scripts.build_source_audit_artifact",
        "scripts/build_source_audit_artifact.py",
    )
    repo, commit, generator_commit = _committed_source_repo(tmp_path)

    first = module.build_source_audit_artifact(
        repo_root=repo,
        commit=commit,
        output_dir=tmp_path / "first",
    )
    second = module.build_source_audit_artifact(
        repo_root=repo,
        commit=commit,
        output_dir=tmp_path / "second",
    )

    first_archive = Path(first["archive_path"])
    second_archive = Path(second["archive_path"])
    manifest = json.loads(Path(first["manifest_path"]).read_text(encoding="utf-8"))
    exported_paths = [item["path"] for item in manifest["files"]]

    assert manifest["schema_version"] == "moss.source-audit-artifact.v1"
    assert manifest["source_commit"] == commit
    assert manifest["generator_commit"] == generator_commit
    assert manifest["generator_commit"] != manifest["source_commit"]
    assert (
        manifest["generator_script_sha256"]
        == hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
    )
    assert len(manifest["source_tree"]) == 40
    assert exported_paths == [".env.example", "src/app.py"]
    assert (
        manifest["archive"]["sha256"]
        == hashlib.sha256(first_archive.read_bytes()).hexdigest()
    )
    assert (
        hashlib.sha256(first_archive.read_bytes()).digest()
        == hashlib.sha256(second_archive.read_bytes()).digest()
    )
    assert not list(first_archive.parent.glob(".moss-source-audit-tmp-*"))
    assert not list(second_archive.parent.glob(".moss-source-audit-tmp-*"))

    with zipfile.ZipFile(first_archive) as archive:
        assert archive.namelist() == exported_paths
        for item in manifest["files"]:
            exported_bytes = archive.read(item["path"])
            assert item["size"] == len(exported_bytes)
            assert item["sha256"] == hashlib.sha256(exported_bytes).hexdigest()
        exported_app = archive.read("src/app.py")
        assert b"COMMITTED = True" in exported_app
        assert b"DIRTY = True" not in exported_app


def test_source_audit_artifact_keeps_unfiltered_tar_outside_output_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_module(
        "scripts.build_source_audit_artifact",
        "scripts/build_source_audit_artifact.py",
    )
    repo, commit, _generator_commit = _committed_source_repo(tmp_path)
    output_dir = tmp_path / "artifacts"
    real_run = module.subprocess.run
    tar_paths: list[Path] = []

    def recording_run(args: list[str], **kwargs: object) -> object:
        if args[:3] == ["git", "archive", "--format=tar"]:
            output_arg = next(arg for arg in args if arg.startswith("--output="))
            tar_paths.append(Path(output_arg.split("=", 1)[1]).resolve())
        return real_run(args, **kwargs)

    monkeypatch.setattr(module.subprocess, "run", recording_run)

    module.build_source_audit_artifact(
        repo_root=repo,
        commit=commit,
        output_dir=output_dir,
    )

    assert not tar_paths


def test_source_audit_artifact_does_not_create_unused_temp_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_module(
        "scripts.build_source_audit_artifact",
        "scripts/build_source_audit_artifact.py",
    )
    repo, commit, _generator_commit = _committed_source_repo(tmp_path)
    temp_calls: list[bool] = []

    def unexpected_mkdtemp(*_args: object, **_kwargs: object) -> str:
        temp_calls.append(True)
        raise AssertionError("source audit build created an unused temp directory")

    monkeypatch.setattr(tempfile, "mkdtemp", unexpected_mkdtemp)

    result = module.build_source_audit_artifact(
        repo_root=repo,
        commit=commit,
        output_dir=tmp_path / "out",
    )

    assert not temp_calls
    assert Path(result["archive_path"]).is_file()


def test_source_audit_artifact_requires_a_full_commit_sha(tmp_path: Path) -> None:
    module = load_module(
        "scripts.build_source_audit_artifact",
        "scripts/build_source_audit_artifact.py",
    )
    repo, _commit, _generator_commit = _committed_source_repo(tmp_path)

    with pytest.raises(ValueError, match="full 40-character commit SHA"):
        module.build_source_audit_artifact(
            repo_root=repo,
            commit="HEAD",
            output_dir=tmp_path / "out",
        )


def test_source_audit_artifact_workflow_is_manual_commit_scoped_and_uploaded() -> None:
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github" / "workflows" / "source-audit-artifact.yml").read_text(
        encoding="utf-8"
    )

    assert "workflow_dispatch:" in workflow
    assert "scripts/build_source_audit_artifact.py" in workflow
    assert "--commit" in workflow
    assert "github.sha" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert ".codex-artifacts" not in workflow
    artifact_root = "source-audit-artifacts/${{ inputs.commit || github.sha }}"
    workflow_lines = {line.strip() for line in workflow.splitlines()}
    assert (
        f"{artifact_root}/"
        "moss-v3-source-audit-${{ inputs.commit || github.sha }}.zip" in workflow_lines
    )
    assert (
        f"{artifact_root}/"
        "moss-v3-source-audit-${{ inputs.commit || github.sha }}.manifest.json"
        in workflow_lines
    )
    assert "ref:" not in workflow
    assert "pull_request:" not in workflow

    gitignore = (root / ".gitignore").read_text(encoding="utf-8")
    assert "/audit_pack/source_snapshot/" in gitignore


def _commit_index_symlink(repo: Path, link_path: str, target: str) -> str:
    blob_source = repo / "symlink-target.txt"
    blob_source.write_text(target, encoding="utf-8")
    blob = _git(repo, "hash-object", "-w", blob_source.name)
    blob_source.unlink()
    _git(
        repo,
        "update-index",
        "--add",
        "--cacheinfo",
        f"120000,{blob},{link_path}",
    )
    _git(repo, "commit", "-m", f"add symlink {link_path}")
    return _git(repo, "rev-parse", "HEAD")


def test_source_audit_scan_tree_uses_historical_exported_bytes(
    tmp_path: Path,
) -> None:
    module = load_module(
        "scripts.build_source_audit_artifact",
        "scripts/build_source_audit_artifact.py",
    )
    repo, _source_commit, _generator_commit = _committed_source_repo(tmp_path)
    _git(repo, "restore", "src/app.py")
    (repo / "src" / "untracked.py").unlink()

    synthetic_token = "ghp_" + ("A" * 36)
    secret_path = repo / "src" / "runtime_config.py"
    secret_path.write_text(f"TOKEN = '{synthetic_token}'\n", encoding="utf-8")
    _git(repo, "add", "src/runtime_config.py")
    _git(repo, "commit", "-m", "historical secret fixture")
    historical_commit = _git(repo, "rev-parse", "HEAD")

    secret_path.write_text("TOKEN = 'rotated'\n", encoding="utf-8")
    _git(repo, "add", "src/runtime_config.py")
    _git(repo, "commit", "-m", "rotate fixture secret")
    assert _git(repo, "rev-parse", "HEAD") != historical_commit

    scan_dir = tmp_path / "scan-tree"
    result = module.build_source_audit_artifact(
        repo_root=repo,
        commit=historical_commit,
        output_dir=tmp_path / "artifact",
        scan_dir=scan_dir,
    )

    scanned_bytes = (scan_dir / "src" / "runtime_config.py").read_bytes()
    assert synthetic_token.encode("utf-8") in scanned_bytes
    assert b"rotated" not in scanned_bytes
    with zipfile.ZipFile(result["archive_path"]) as archive:
        assert archive.read("src/runtime_config.py") == scanned_bytes


@pytest.mark.parametrize(
    ("link_path", "target"),
    [
        ("absolute-link", "/etc/passwd"),
        ("escape-link", "../outside-repository"),
        ("src/windows-link", "C:\\Windows\\system.ini"),
        ("src/control-link", "app.py\nsecond-path"),
        ("src/ads-link", "app.py:stream"),
        ("src/device-link", "NUL"),
    ],
)
def test_source_audit_artifact_rejects_unsafe_symlink_targets(
    tmp_path: Path,
    link_path: str,
    target: str,
) -> None:
    module = load_module(
        "scripts.build_source_audit_artifact",
        "scripts/build_source_audit_artifact.py",
    )
    repo, _source_commit, _generator_commit = _committed_source_repo(tmp_path)
    commit = _commit_index_symlink(repo, link_path, target)

    with pytest.raises(ValueError, match="Unsafe symlink target"):
        module.build_source_audit_artifact(
            repo_root=repo,
            commit=commit,
            output_dir=tmp_path / "artifact",
        )


def test_source_audit_artifact_allows_internal_relative_symlink(
    tmp_path: Path,
) -> None:
    module = load_module(
        "scripts.build_source_audit_artifact",
        "scripts/build_source_audit_artifact.py",
    )
    repo, _source_commit, _generator_commit = _committed_source_repo(tmp_path)
    commit = _commit_index_symlink(repo, "src/nested/app-link.py", "../app.py")
    scan_dir = tmp_path / "scan-tree"

    result = module.build_source_audit_artifact(
        repo_root=repo,
        commit=commit,
        output_dir=tmp_path / "artifact",
        scan_dir=scan_dir,
    )
    manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))
    link_entry = next(
        item for item in manifest["files"] if item["path"] == "src/nested/app-link.py"
    )

    assert link_entry["kind"] == "symlink"
    scanned_link = scan_dir / "src" / "nested" / "app-link.py"
    assert scanned_link.is_file()
    assert not scanned_link.is_symlink()
    assert scanned_link.read_bytes() == b"../app.py"
    with zipfile.ZipFile(result["archive_path"]) as archive:
        assert archive.read("src/nested/app-link.py") == b"../app.py"


def test_source_audit_workflow_scans_target_export_before_upload() -> None:
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github" / "workflows" / "source-audit-artifact.yml").read_text(
        encoding="utf-8"
    )

    assert "- name: Install Gitleaks" in workflow
    assert "gitleaks/releases/download/v8.30.1/" in workflow
    assert (
        "551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb" in workflow
    )
    assert (
        "SCAN_DIR: ${{ runner.temp }}/moss-source-audit-scan/"
        "${{ inputs.commit || github.sha }}"
    ) in workflow
    assert '--scan-dir "$SCAN_DIR"' in workflow
    assert "- name: Scan exported target commit" in workflow

    install_index = workflow.index("- name: Install Gitleaks")
    build_index = workflow.index("- name: Build deterministic source artifact")
    scan_index = workflow.index("- name: Scan exported target commit")
    upload_index = workflow.index("- name: Upload source archive and manifest")
    assert install_index < build_index < scan_index < upload_index

    scan_block = workflow[scan_index:upload_index]
    assert 'gitleaks dir "$SCAN_DIR"' in scan_block
    assert '--config ".gitleaks.toml"' in scan_block
    assert '--gitleaks-ignore-path "$EMPTY_GITLEAKS_IGNORE"' in scan_block
    assert "--ignore-gitleaks-allow" in scan_block
    assert "--exit-code 1" in scan_block
    assert "--max-archive-depth 2" in scan_block
    assert "--max-decode-depth 2" in scan_block
    assert "--redact" in scan_block
    assert "--no-banner" in scan_block
    assert workflow.count("set -euo pipefail") >= 2
    assert "continue-on-error" not in workflow
    assert "|| true" not in workflow

    upload_block = workflow[upload_index:]
    assert "source-audit-scan" not in upload_block
    assert "if: always()" not in upload_block
    assert "source-audit-artifacts/${{ inputs.commit || github.sha }}" in upload_block


def test_source_audit_includes_export_ignored_tracked_blob(tmp_path: Path) -> None:
    module = load_module(
        "scripts.build_source_audit_artifact",
        "scripts/build_source_audit_artifact.py",
    )
    repo, _source_commit, _generator_commit = _committed_source_repo(tmp_path)
    _git(repo, "restore", "src/app.py")
    (repo / "src" / "untracked.py").unlink()

    tracked_bytes = b"historical tracked secret bytes\n"
    (repo / "src" / "hidden.txt").write_bytes(tracked_bytes)
    (repo / ".gitattributes").write_text(
        "src/hidden.txt export-ignore\n",
        encoding="utf-8",
    )
    _git(repo, "add", ".gitattributes", "src/hidden.txt")
    _git(repo, "commit", "-m", "export-ignore fixture")
    commit = _git(repo, "rev-parse", "HEAD")

    scan_dir = tmp_path / "scan-tree"
    result = module.build_source_audit_artifact(
        repo_root=repo,
        commit=commit,
        output_dir=tmp_path / "artifact",
        scan_dir=scan_dir,
    )

    assert (scan_dir / "src" / "hidden.txt").read_bytes() == tracked_bytes
    with zipfile.ZipFile(result["archive_path"]) as archive:
        assert archive.read("src/hidden.txt") == tracked_bytes


def test_source_audit_preserves_export_subst_blob_bytes(tmp_path: Path) -> None:
    module = load_module(
        "scripts.build_source_audit_artifact",
        "scripts/build_source_audit_artifact.py",
    )
    repo, _source_commit, _generator_commit = _committed_source_repo(tmp_path)
    _git(repo, "restore", "src/app.py")
    (repo / "src" / "untracked.py").unlink()

    tracked_bytes = b"commit=$Format:%H$\n"
    (repo / "src" / "subst.txt").write_bytes(tracked_bytes)
    (repo / ".gitattributes").write_text(
        "src/subst.txt export-subst\n",
        encoding="utf-8",
    )
    _git(repo, "add", ".gitattributes", "src/subst.txt")
    _git(repo, "commit", "-m", "export-subst fixture")
    commit = _git(repo, "rev-parse", "HEAD")

    scan_dir = tmp_path / "scan-tree"
    result = module.build_source_audit_artifact(
        repo_root=repo,
        commit=commit,
        output_dir=tmp_path / "artifact",
        scan_dir=scan_dir,
    )

    assert (scan_dir / "src" / "subst.txt").read_bytes() == tracked_bytes
    with zipfile.ZipFile(result["archive_path"]) as archive:
        assert archive.read("src/subst.txt") == tracked_bytes


@pytest.mark.parametrize(
    "path",
    [
        "/absolute.txt",
        "../escape.txt",
        "src/../escape.txt",
        "src\\escape.txt",
        "C:/drive.txt",
        "src/file:stream",
        "src/control\nname.txt",
        "src/trailing. ",
        "src/NUL.txt",
    ],
)
def test_source_audit_rejects_unsafe_export_paths(path: str) -> None:
    module = load_module(
        "scripts.build_source_audit_artifact",
        "scripts/build_source_audit_artifact.py",
    )
    validator = getattr(module, "_validate_export_path", None)

    assert callable(validator)
    with pytest.raises(ValueError, match="Unsafe export path"):
        validator(path)


@pytest.mark.parametrize(
    ("first_path", "second_path"),
    [
        ("src/App.py", "src/app.py"),
        ("src/App", "src/app/config.py"),
    ],
)
def test_source_audit_rejects_case_insensitive_export_path_collisions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    first_path: str,
    second_path: str,
) -> None:
    module = load_module(
        "scripts.build_source_audit_artifact",
        "scripts/build_source_audit_artifact.py",
    )
    first_object = "a" * 40
    second_object = "b" * 40
    tree_output = (
        f"100644 blob {first_object}\t{first_path}\0"
        f"100644 blob {second_object}\t{second_path}\0"
    ).encode("utf-8")

    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **_kwargs: subprocess.CompletedProcess(
            args[0],
            0,
            stdout=tree_output,
            stderr=b"",
        ),
    )
    monkeypatch.setattr(module, "_read_git_blobs", lambda *_args: [b"one", b"two"])

    with pytest.raises(ValueError, match="case-insensitive export path collision"):
        module._load_export_entries(tmp_path, "c" * 40)


@pytest.mark.parametrize("location", ["output", "repo"])
def test_source_audit_rejects_overlapping_scan_tree(
    tmp_path: Path,
    location: str,
) -> None:
    module = load_module(
        "scripts.build_source_audit_artifact",
        "scripts/build_source_audit_artifact.py",
    )
    repo, commit, _generator_commit = _committed_source_repo(tmp_path)
    output_dir = tmp_path / "artifact"
    scan_dir = output_dir / "scan" if location == "output" else repo / "scan"

    with pytest.raises(ValueError, match="scan_dir must be outside"):
        module.build_source_audit_artifact(
            repo_root=repo,
            commit=commit,
            output_dir=output_dir,
            scan_dir=scan_dir,
        )
