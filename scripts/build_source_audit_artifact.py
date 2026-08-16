from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "moss.source-audit-artifact.v1"
GENERATOR_VERSION = "1"
FULL_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
EXCLUDED_PREFIXES = (
    ".codex-artifacts/",
    ".codex-tmp/",
    "audit_pack/source_snapshot/",
    "backend/data/",
    "data/",
    "data_input/",
    "dist/",
    "frontend/dist/",
    "frontend/node_modules/",
    "node_modules/",
)
WINDOWS_RESERVED_NAMES = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{number}" for number in range(1, 10)),
    *(f"lpt{number}" for number in range(1, 10)),
}


def _run_git(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def _is_exportable(path: str) -> bool:
    normalized = str(PurePosixPath(path))
    if any(
        normalized == prefix.rstrip("/") or normalized.startswith(prefix)
        for prefix in EXCLUDED_PREFIXES
    ):
        return False
    filename = PurePosixPath(normalized).name
    if filename == ".env":
        return False
    if filename.startswith(".env.") and filename != ".env.example":
        return False
    return True


def _validate_symlink_target(path: str, target: str) -> None:
    target_path = PurePosixPath(target)
    target_parts = target.split("/")
    if (
        not target
        or target_path.is_absolute()
        or bool(PureWindowsPath(target).drive)
        or "\\" in target
        or any(ord(character) < 32 or ord(character) == 127 for character in target)
        or any(
            part == ""
            or (
                part not in {".", ".."}
                and (
                    ":" in part
                    or part.rstrip(" .") != part
                    or part.split(".", 1)[0].casefold() in WINDOWS_RESERVED_NAMES
                )
            )
            for part in target_parts
        )
    ):
        raise ValueError(f"Unsafe symlink target for {path}: {target!r}")

    resolved_parts = list(PurePosixPath(path).parent.parts)
    for part in target_path.parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if not resolved_parts:
                raise ValueError(f"Unsafe symlink target for {path}: {target!r}")
            resolved_parts.pop()
        else:
            resolved_parts.append(part)


def _validate_export_path(path: str) -> PurePosixPath:
    parts = path.split("/")
    if (
        not path
        or PurePosixPath(path).is_absolute()
        or bool(PureWindowsPath(path).drive)
        or "\\" in path
        or ":" in path
        or any(ord(character) < 32 or ord(character) == 127 for character in path)
        or any(part in {"", ".", ".."} for part in parts)
        or any(part.rstrip(" .") != part for part in parts)
        or any(
            part.split(".", 1)[0].casefold() in WINDOWS_RESERVED_NAMES for part in parts
        )
    ):
        raise ValueError(f"Unsafe export path: {path!r}")
    return PurePosixPath(*parts)


def _read_git_blobs(repo: Path, object_ids: list[str]) -> list[bytes]:
    if not object_ids:
        return []
    request = b"".join(object_id.encode("ascii") + b"\n" for object_id in object_ids)
    completed = subprocess.run(
        ["git", "cat-file", "--batch"],
        cwd=repo,
        input=request,
        capture_output=True,
        check=True,
    )
    output = completed.stdout
    cursor = 0
    blobs: list[bytes] = []
    for expected_object_id in object_ids:
        header_end = output.find(b"\n", cursor)
        if header_end < 0:
            raise RuntimeError("Malformed git cat-file response: missing header")
        header_parts = output[cursor:header_end].split()
        if len(header_parts) != 3:
            raise RuntimeError("Malformed git cat-file response header")
        actual_object_id, object_type, size_text = header_parts
        if (
            actual_object_id != expected_object_id.encode("ascii")
            or object_type != b"blob"
        ):
            raise RuntimeError("Unexpected git cat-file object response")
        try:
            size = int(size_text)
        except ValueError as error:
            raise RuntimeError("Malformed git cat-file object size") from error
        payload_start = header_end + 1
        payload_end = payload_start + size
        if payload_end >= len(output) or output[payload_end : payload_end + 1] != b"\n":
            raise RuntimeError("Malformed git cat-file response payload")
        blobs.append(output[payload_start:payload_end])
        cursor = payload_end + 1
    if cursor != len(output):
        raise RuntimeError("Unexpected trailing git cat-file output")
    return blobs


def _load_export_entries(
    repo: Path,
    commit: str,
) -> list[tuple[str, bytes, bool]]:
    completed = subprocess.run(
        ["git", "ls-tree", "-r", "-z", "--full-tree", commit],
        cwd=repo,
        capture_output=True,
        check=True,
    )
    casefold_paths: dict[str, str] = {}
    tree_entries: list[tuple[str, str, bool]] = []
    casefold_directories: dict[str, str] = {}
    for record in completed.stdout.split(b"\0"):
        if not record:
            continue
        metadata_bytes, separator, path_bytes = record.partition(b"\t")
        if not separator:
            raise RuntimeError("Malformed git ls-tree entry")
        try:
            metadata = metadata_bytes.decode("ascii")
            path = path_bytes.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError("Unsafe export path: non-UTF-8 Git entry") from error
        metadata_parts = metadata.split()
        if len(metadata_parts) != 3:
            raise RuntimeError("Malformed git ls-tree metadata")
        mode, object_type, object_id = metadata_parts
        normalized_path = _validate_export_path(path).as_posix()
        if not _is_exportable(normalized_path):
            continue

        path_parts = normalized_path.split("/")
        directory_paths = [
            "/".join(path_parts[:index]) for index in range(1, len(path_parts))
        ]
        for directory_path in directory_paths:
            directory_key = directory_path.casefold()
            previous_file = casefold_paths.get(directory_key)
            if previous_file is not None:
                raise ValueError(
                    "Unsafe case-insensitive export path collision: "
                    f"{previous_file!r} and {directory_path!r}"
                )
            previous_directory = casefold_directories.get(directory_key)
            if previous_directory is not None and previous_directory != directory_path:
                raise ValueError(
                    "Unsafe case-insensitive export path collision: "
                    f"{previous_directory!r} and {directory_path!r}"
                )
            casefold_directories[directory_key] = directory_path

        collision_key = normalized_path.casefold()
        previous_path = casefold_paths.get(collision_key)
        if previous_path is not None and previous_path != normalized_path:
            raise ValueError(
                "Unsafe case-insensitive export path collision: "
                f"{previous_path!r} and {normalized_path!r}"
            )
        previous_directory = casefold_directories.get(collision_key)
        if previous_directory is not None:
            raise ValueError(
                "Unsafe case-insensitive export path collision: "
                f"{previous_directory!r} and {normalized_path!r}"
            )
        casefold_paths[collision_key] = normalized_path
        if object_type != "blob" or mode not in {"100644", "100755", "120000"}:
            raise ValueError(
                f"Unsupported Git tree entry for source audit: {normalized_path}"
            )
        tree_entries.append((normalized_path, object_id, mode == "120000"))

    blobs = _read_git_blobs(repo, [object_id for _, object_id, _ in tree_entries])
    export_entries: list[tuple[str, bytes, bool]] = []
    for (path, _object_id, is_symlink), data in zip(
        tree_entries,
        blobs,
        strict=True,
    ):
        if is_symlink:
            try:
                target = data.decode("utf-8")
            except UnicodeDecodeError as error:
                raise ValueError(f"Unsafe symlink target for {path}") from error
            _validate_symlink_target(path, target)
        export_entries.append((path, data, is_symlink))
    export_entries.sort(key=lambda item: item[0])
    return export_entries


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _zip_info(path: str, *, symlink: bool) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
    info.create_system = 3
    info.compress_type = zipfile.ZIP_DEFLATED
    mode = 0o120777 if symlink else 0o100644
    info.external_attr = mode << 16
    return info


def build_source_audit_artifact(
    *,
    repo_root: str | Path,
    commit: str,
    output_dir: str | Path,
    scan_dir: str | Path | None = None,
) -> dict[str, object]:
    repo = Path(repo_root).resolve()
    if FULL_SHA_RE.fullmatch(commit) is None:
        raise ValueError("commit must be a full 40-character commit SHA")
    resolved_commit = _run_git(repo, "rev-parse", "--verify", f"{commit}^{{commit}}")
    if resolved_commit.lower() != commit.lower():
        raise ValueError(
            "commit must resolve to the exact full 40-character commit SHA"
        )
    source_tree = _run_git(repo, "rev-parse", f"{resolved_commit}^{{tree}}")
    generator_commit = _run_git(repo, "rev-parse", "HEAD")
    generator_script_sha256 = _sha256(Path(__file__).read_bytes())

    output = Path(output_dir).resolve()
    scan_root = Path(scan_dir).resolve() if scan_dir is not None else None
    if scan_root is not None and (
        scan_root == output
        or scan_root in output.parents
        or output in scan_root.parents
        or scan_root == repo
        or scan_root in repo.parents
        or repo in scan_root.parents
    ):
        raise ValueError(
            "scan_dir must be outside repo_root and output_dir without overlap"
        )
    output.mkdir(parents=True, exist_ok=True)
    archive_name = f"moss-v3-source-audit-{resolved_commit}.zip"
    manifest_name = f"moss-v3-source-audit-{resolved_commit}.manifest.json"
    archive_path = output / archive_name
    manifest_path = output / manifest_name

    file_entries: list[dict[str, object]] = []
    export_entries = _load_export_entries(repo, resolved_commit)

    if scan_root is not None:
        scan_root.mkdir(parents=True, exist_ok=False)
        for path, data, _is_symlink in export_entries:
            destination = scan_root.joinpath(*PurePosixPath(path).parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
    with zipfile.ZipFile(
        archive_path,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
        strict_timestamps=False,
    ) as archive:
        for path, data, is_symlink in export_entries:
            archive.writestr(
                _zip_info(path, symlink=is_symlink),
                data,
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            )
            file_entries.append(
                {
                    "path": path,
                    "kind": "symlink" if is_symlink else "file",
                    "size": len(data),
                    "sha256": _sha256(data),
                }
            )

    archive_bytes = archive_path.read_bytes()
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generator_version": GENERATOR_VERSION,
        "generator_commit": generator_commit,
        "generator_script_sha256": generator_script_sha256,
        "source_commit": resolved_commit,
        "source_tree": source_tree,
        "scope": "tracked files from the named commit only; dirty and untracked files excluded",
        "excluded_prefixes": list(EXCLUDED_PREFIXES),
        "files": file_entries,
        "archive": {
            "filename": archive_name,
            "size": len(archive_bytes),
            "sha256": _sha256(archive_bytes),
        },
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "archive_path": str(archive_path),
        "manifest_path": str(manifest_path),
        "source_commit": resolved_commit,
        "source_tree": source_tree,
        "file_count": len(file_entries),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a deterministic, commit-scoped source audit artifact.",
    )
    parser.add_argument("--commit", required=True, help="Full 40-character commit SHA.")
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--output-dir")
    parser.add_argument("--scan-dir")
    args = parser.parse_args(argv)

    output_dir = args.output_dir or str(
        Path(args.repo_root) / ".codex-artifacts" / "source-audit" / args.commit
    )
    result = build_source_audit_artifact(
        repo_root=args.repo_root,
        commit=args.commit,
        output_dir=output_dir,
        scan_dir=args.scan_dir,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
