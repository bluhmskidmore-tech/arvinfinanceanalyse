"""Read only committed backend source for first-baseline CI comparisons."""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterator

COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_WINDOWS_DEVICE_RE = re.compile(r"^(con|prn|aux|nul|com[0-9]|lpt[0-9])(?:\.|$)", re.I)


class BaseSourceError(RuntimeError):
    """The exact base source could not be established safely."""


def _git(repo: Path, arguments: list[str], *, input_bytes: bytes | None = None) -> bytes:
    try:
        result = subprocess.run(
            ["git", *arguments], cwd=repo, input=input_bytes,
            capture_output=True, check=False,
        )
    except OSError as error:
        raise BaseSourceError("trusted base git command could not be executed") from error
    if result.returncode != 0:
        raise BaseSourceError("trusted base git evidence could not be read")
    return result.stdout


def resolve_commit(repo: Path, ref: str) -> str:
    resolved = _git(repo, ["rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}"])
    commit = resolved.decode("ascii").strip().lower()
    if COMMIT_RE.fullmatch(commit) is None:
        raise BaseSourceError("trusted base ref did not resolve to a commit")
    return commit


def _tree_entries(repo: Path, commit: str, paths: list[str]) -> list[tuple[str, str, str]]:
    if COMMIT_RE.fullmatch(commit) is None:
        raise BaseSourceError("trusted base requires an exact commit SHA")
    raw = _git(repo, ["ls-tree", "-rz", "--full-tree", commit, "--", *paths])
    entries = []
    try:
        for entry in raw.split(b"\0"):
            if entry:
                metadata, path = entry.split(b"\t", 1)
                mode, kind, object_id = metadata.decode("ascii").split()
                if kind != "blob" or mode not in {"100644", "100755"}:
                    raise BaseSourceError("trusted base contains a symlink, submodule, or unsupported object")
                entries.append((mode, object_id, path.decode("utf-8")))
    except (UnicodeError, ValueError) as error:
        raise BaseSourceError("trusted base tree metadata is invalid") from error
    return entries


def read_committed_blob(repo: Path, commit: str, path: str) -> bytes | None:
    entries = _tree_entries(repo, commit, [path])
    if not entries:
        return None
    if len(entries) != 1 or entries[0][2] != path:
        raise BaseSourceError("trusted baseline is not a regular file")
    return _git(repo, ["cat-file", "blob", entries[0][1]])


def _safe_path(root: Path, relative: str) -> Path:
    path = PurePosixPath(relative)
    if (
        path.is_absolute() or path.as_posix() != relative
        or any(part in {".", ".."} or ":" in part or "\\" in part
               or part.rstrip(" .") != part or _WINDOWS_DEVICE_RE.match(part)
               for part in path.parts)
        or not relative.startswith("backend/")
    ):
        raise BaseSourceError("trusted base source path is unsafe")
    target = root.joinpath(*path.parts)
    if not target.resolve().is_relative_to(root.resolve()):
        raise BaseSourceError("trusted base source path escapes the isolated directory")
    return target


@dataclass(frozen=True)
class BaseSource:
    root: Path
    commit: str
    inputs_sha256: str
    pyproject_sha256: str
    lock_sha256: str

    def provenance(self) -> dict[str, str]:
        return {
            "method": "exact_git_base_backend_source",
            "commit": self.commit,
            "inputs_sha256": self.inputs_sha256,
            "pyproject_sha256": self.pyproject_sha256,
            "lock_sha256": self.lock_sha256,
        }


@contextmanager
def isolated_backend_source(repo: Path, commit: str, parent: Path) -> Iterator[BaseSource]:
    """Extract regular code blobs only; never use a worktree, .env, or business data."""
    allowed_root = (repo / ".codex-tmp").resolve()
    if ((repo / ".codex-tmp").is_symlink() or not allowed_root.is_relative_to(repo.resolve())
            or parent.is_symlink() or not parent.resolve().is_relative_to(allowed_root)):
        raise BaseSourceError("trusted source directory must be inside this repository's .codex-tmp")
    parent = parent.resolve()
    parent.mkdir(parents=True, exist_ok=True)
    entries = [
        entry for entry in _tree_entries(repo, commit, ["backend"])
        if entry[2].endswith((".py", ".pyi", ".ipynb"))
        or entry[2] in {"backend/pyproject.toml", "backend/uv.lock"}
    ]
    names = {entry[2] for entry in entries}
    if len({name.casefold() for name in names}) != len(entries):
        raise BaseSourceError("trusted base source contains duplicate or case-colliding paths")
    if not {"backend/app/main.py", "backend/pyproject.toml", "backend/uv.lock"} <= names:
        raise BaseSourceError("trusted base is missing backend source or dependency evidence")
    manifest = "".join(f"{mode} {object_id} {path}\n" for mode, object_id, path in entries)
    # cat-file's length-delimited batch protocol avoids archive links and path extraction.
    raw = _git(repo, ["cat-file", "--batch"], input_bytes="".join(
        f"{object_id}\n" for _, object_id, _ in entries
    ).encode("ascii"))
    with tempfile.TemporaryDirectory(prefix="source-", dir=parent) as temporary:
        root = Path(temporary)
        digests: dict[str, str] = {}
        cursor = 0
        for _, object_id, relative in entries:
            header_end = raw.find(b"\n", cursor)
            try:
                observed, kind, size_text = raw[cursor:header_end].decode("ascii").split()
                size = int(size_text)
            except (UnicodeError, ValueError) as error:
                raise BaseSourceError("trusted base blob metadata is invalid") from error
            begin, end = header_end + 1, header_end + 1 + size
            if header_end < cursor or observed != object_id or kind != "blob" or size < 0 or raw[end:end+1] != b"\n":
                raise BaseSourceError("trusted base blob content is incomplete")
            content = raw[begin:end]
            if hashlib.sha1(f"blob {size}\0".encode("ascii") + content).hexdigest() != object_id:
                raise BaseSourceError("trusted base blob content does not match its git identity")
            target = _safe_path(root, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            digests[relative] = hashlib.sha256(content).hexdigest()
            cursor = end + 1
        if cursor != len(raw):
            raise BaseSourceError("trusted base blob stream has unexpected content")
        yield BaseSource(root, commit, hashlib.sha256(manifest.encode("utf-8")).hexdigest(),
                         digests["backend/pyproject.toml"], digests["backend/uv.lock"])


def source_environment(source_root: Path) -> dict[str, str]:
    """Retain OS process requirements, without local MOSS settings or Python paths."""
    keep = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "LANG", "LC_ALL"}
    environment = {key: value for key, value in os.environ.items() if key.upper() in keep}
    environment["PYTHONUTF8"] = "1"
    environment["MOSS_DATA_INPUT_ROOT"] = str(source_root / "data_input")
    return environment


def run_source_python(source: BaseSource, code: str, arguments: list[str], *, environment: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    # Editable installs can expose the PR checkout even with Python's -I flag.
    # Keep only the interpreter's libraries and ordinary import finders; callers
    # explicitly add the isolated source paths when importing the base app.
    setup = (
        "import sys;from pathlib import Path;"
        "runtime_roots=[Path(sys.prefix).resolve(),Path(sys.base_prefix).resolve()];"
        "sys.path=[p for p in sys.path if any(Path(p).resolve().is_relative_to(r) for r in runtime_roots)];"
        "sys.meta_path=[f for f in sys.meta_path if getattr(f,'__module__',type(f).__module__) "
        "in {'_frozen_importlib','_frozen_importlib_external'}];"
    )
    try:
        return subprocess.run(
            [sys.executable, "-I", "-c", setup + code, str(source.root), *arguments],
            cwd=source.root, env=environment or source_environment(source.root),
            capture_output=True, text=True, encoding="utf-8", check=False, timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise BaseSourceError("trusted base source export could not complete") from error
