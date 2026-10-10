"""Create only new synthetic WP7 bundles inside the rehearsal workspace."""

from __future__ import annotations

import os
import shutil
import stat
import tempfile
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import BinaryIO

import duckdb
from backend.app.governance.locks import acquire_lock, resolve_duckdb_writer_lock
from backend.app.repositories.task_write_guard import (
    repository_task_write_scope,
    require_repository_task_write_scope,
)


class SyntheticBundleError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _assert_no_links(path: Path) -> None:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        if not os.path.lexists(current):
            continue
        metadata = current.stat(follow_symlinks=False)
        is_junction = getattr(current, "is_junction", lambda: False)
        if (
            current.is_symlink()
            or is_junction()
            or int(getattr(metadata, "st_file_attributes", 0))
            & int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
        ):
            raise SyntheticBundleError("synthetic_bundle_path_contains_symlink_or_junction")


def _parent_identity(path: Path, workspace: Path) -> tuple[tuple[int, int], ...]:
    if (
        not path.is_absolute()
        or not workspace.is_absolute()
        or path.parent != workspace / "bundles"
        or path.name not in {"baseline.duckdb", "candidate.duckdb"}
        or os.path.normcase(str(workspace)) != os.path.normcase(str(workspace.resolve()))
    ):
        raise SyntheticBundleError("synthetic_bundle_path_outside_workspace")
    _assert_no_links(path.parent)
    identities = []
    for directory in (workspace, path.parent):
        metadata = directory.stat(follow_symlinks=False)
        if not stat.S_ISDIR(metadata.st_mode):
            raise SyntheticBundleError("synthetic_bundle_parent_identity_invalid")
        identities.append((int(metadata.st_dev), int(metadata.st_ino)))
    return tuple(identities)


def _target_identity(path: Path, workspace: Path) -> tuple[tuple[int, int], ...]:
    identities = _parent_identity(path, workspace)
    _assert_no_links(path)
    if os.path.lexists(path):
        raise SyntheticBundleError("synthetic_bundle_path_must_be_new")
    return identities


@contextmanager
def _bound_directories(
    path: Path,
    workspace: Path,
    expected_identity: tuple[tuple[int, int], ...],
) -> Iterator[tuple[Path, Path, int | None]]:
    """Bind the authorized directories before creating any lock, staging file or target."""
    with ExitStack() as stack:
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.CreateFileW.argtypes = [
                wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
            ]
            kernel32.CreateFileW.restype = wintypes.HANDLE
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel32.CloseHandle.restype = wintypes.BOOL
            current = Path(path.anchor)
            directories = [current]
            for part in path.parent.parts[1:]:
                current /= part
                directories.append(current)
            for directory in directories:
                handle = kernel32.CreateFileW(
                    str(directory), 0x80000000, 0x00000003, None, 3,
                    0x02000000 | 0x00200000, None,
                )
                # GENERIC_READ, SHARE_READ | SHARE_WRITE (never SHARE_DELETE),
                # OPEN_EXISTING, BACKUP_SEMANTICS | OPEN_REPARSE_POINT.
                if handle == ctypes.c_void_p(-1).value:
                    raise SyntheticBundleError("synthetic_bundle_directory_binding_unavailable") from ctypes.WinError()
                stack.callback(kernel32.CloseHandle, handle)
                _assert_no_links(directory)
            if _parent_identity(path, workspace) != expected_identity:
                raise SyntheticBundleError("synthetic_bundle_parent_identity_changed")
            yield workspace, path.parent, None
            return

        if not hasattr(os, "O_DIRECTORY") or not hasattr(os, "O_NOFOLLOW"):
            raise SyntheticBundleError("synthetic_bundle_directory_binding_unavailable")
        flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW")
        workspace_fd = os.open(workspace, flags)
        stack.callback(os.close, workspace_fd)
        bundles_fd = os.open("bundles", flags, dir_fd=workspace_fd)
        stack.callback(os.close, bundles_fd)
        observed = tuple(
            (int(os.fstat(descriptor).st_dev), int(os.fstat(descriptor).st_ino))
            for descriptor in (workspace_fd, bundles_fd)
        )
        if observed != expected_identity:
            raise SyntheticBundleError("synthetic_bundle_parent_identity_changed")
        # DuckDB takes a filename. The OS descriptor namespace keeps staging
        # bound to the same directory even if its ordinary pathname is renamed.
        descriptor_root = Path("/proc/self/fd")
        if not descriptor_root.is_dir():
            descriptor_root = Path("/dev/fd")
        bound_workspace = descriptor_root / str(workspace_fd)
        bound_bundles = descriptor_root / str(bundles_fd)
        try:
            descriptor_identity = tuple(
                (int(directory.stat().st_dev), int(directory.stat().st_ino))
                for directory in (bound_workspace, bound_bundles)
            )
        except OSError as exc:
            raise SyntheticBundleError("synthetic_bundle_directory_binding_unavailable") from exc
        if descriptor_identity != expected_identity:
            raise SyntheticBundleError("synthetic_bundle_directory_binding_unavailable")
        yield bound_workspace, bound_bundles, bundles_fd


def _open_install_target(path: Path, *, directory_fd: int | None) -> BinaryIO:
    if directory_fd is None:
        # On Windows every parent remains pinned without FILE_SHARE_DELETE.
        return path.open("xb")
    descriptor = os.open(
        path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW"),
        0o600, dir_fd=directory_fd,
    )
    return os.fdopen(descriptor, "wb")


def _write_synthetic_database(path: Path, *, release_id: str, ordinal: int) -> None:
    require_repository_task_write_scope("wp7_synthetic_bundle")
    connection = duckdb.connect(str(path), read_only=False)
    try:
        connection.execute("begin transaction")
        try:
            connection.execute("CREATE SCHEMA rehearsal")
            connection.execute(
                """
                CREATE TABLE rehearsal.bundle_metadata (
                    release_id VARCHAR NOT NULL,
                    ordinal INTEGER NOT NULL,
                    rehearsal_only BOOLEAN NOT NULL
                )
                """
            )
            connection.execute(
                "INSERT INTO rehearsal.bundle_metadata VALUES (?, ?, TRUE)",
                [release_id, ordinal],
            )
            connection.execute("commit")
        except Exception:
            connection.execute("rollback")
            raise
        connection.execute("CHECKPOINT")
    finally:
        connection.close()


def create_synthetic_bundle(
    *,
    path: Path,
    workspace: Path,
    release_id: str,
    ordinal: int,
) -> None:
    """Never open an existing target database; install the synthetic bytes exclusively."""
    environment = str(os.environ.get("MOSS_ENVIRONMENT", "") or "").strip().lower()
    if environment == "production":
        raise SyntheticBundleError("production_environment_forbidden")
    if environment not in {"", "development", "test", "staging"}:
        raise SyntheticBundleError("host_environment_invalid")
    expected_identity = _target_identity(path, workspace)
    writer_lock = resolve_duckdb_writer_lock(path)
    with _bound_directories(path, workspace, expected_identity) as (bound_workspace, bound_bundles, bundles_fd):
        with acquire_lock(writer_lock, base_dir=bound_workspace):
            if _target_identity(path, workspace) != expected_identity:
                raise SyntheticBundleError("synthetic_bundle_parent_identity_changed")
            with repository_task_write_scope(__name__):
                with tempfile.TemporaryDirectory(prefix=".synthetic-bundle-", dir=bound_bundles) as temporary:
                    staged_path = Path(temporary) / "bundle.duckdb"
                    _write_synthetic_database(staged_path, release_id=release_id, ordinal=ordinal)
                    if _target_identity(path, workspace) != expected_identity:
                        raise SyntheticBundleError("synthetic_bundle_parent_identity_changed")
                    created_identity: tuple[int, int] | None = None
                    try:
                        with staged_path.open("rb") as source, _open_install_target(path, directory_fd=bundles_fd) as target:
                            metadata = os.fstat(target.fileno())
                            created_identity = (int(metadata.st_dev), int(metadata.st_ino))
                            if _parent_identity(path, workspace) != expected_identity:
                                raise SyntheticBundleError("synthetic_bundle_parent_identity_changed")
                            shutil.copyfileobj(source, target)
                    except FileExistsError as exc:
                        raise SyntheticBundleError("synthetic_bundle_path_must_be_new") from exc
                    except Exception:
                        if created_identity is not None and bundles_fd is not None:
                            metadata = os.stat(path.name, dir_fd=bundles_fd, follow_symlinks=False)
                            if (int(metadata.st_dev), int(metadata.st_ino)) == created_identity:
                                os.unlink(path.name, dir_fd=bundles_fd)
                        raise
                    _assert_no_links(path)
                    if _parent_identity(path, workspace) != expected_identity:
                        raise SyntheticBundleError("synthetic_bundle_parent_identity_changed")
