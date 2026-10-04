import hashlib
import io
import json
import os
import re
import socket
import stat
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PureWindowsPath
from uuid import uuid4

ARCHIVE_RELOCATION_RECEIPT = ".moss-archive-relocations.json"


def _require_host_archive_path(value: str | Path) -> None:
    text = os.fspath(value)
    windows = PureWindowsPath(text)
    if (os.name == "nt" and bool(windows.root) != bool(windows.drive)) or (
        os.name != "nt" and (windows.drive or text.startswith("\\"))
    ):
        raise ValueError("archive path uses a foreign or ambiguous host root")


def _archive_path_key(value: str | Path) -> str:
    _require_host_archive_path(value)
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("archive relocation source must be an absolute path without traversal")
    return os.path.normcase(os.path.abspath(path))


def _require_no_archive_links(path: Path) -> None:
    for component in (path, *path.parents):
        try:
            metadata = component.lstat()
        except FileNotFoundError:
            continue
        if (
            stat.S_ISLNK(metadata.st_mode)
            or getattr(metadata, "st_file_attributes", 0) & 0x400
            or (stat.S_ISREG(metadata.st_mode) and metadata.st_nlink > 1)
        ):
            raise ValueError("archive relocation paths must not traverse links or junctions")


def _unique_archive_receipt_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate field in archive relocation receipt")
        result[key] = value
    return result


def _archive_relocation(path: Path, archive_root: Path) -> tuple[Path, str]:
    receipt_path = archive_root / ARCHIVE_RELOCATION_RECEIPT
    _require_no_archive_links(receipt_path)
    try:
        receipt = json.loads(receipt_path.read_bytes(), object_pairs_hook=_unique_archive_receipt_object)
    except FileNotFoundError as exc:
        raise ValueError(f"archived_path is outside local archive root: {path}") from exc
    if not isinstance(receipt, dict) or set(receipt) != {"format_version", "source_archive_root", "entries"}:
        raise ValueError("invalid archive relocation receipt")
    if type(receipt["format_version"]) is not int or receipt["format_version"] != 1 or not isinstance(receipt["entries"], list):
        raise ValueError("unsupported archive relocation receipt")
    source_root = Path(str(receipt["source_archive_root"]))
    _archive_path_key(source_root)
    requested = _archive_path_key(path)
    seen = set()
    matched = None
    for entry in receipt["entries"]:
        if not isinstance(entry, dict) or set(entry) != {"source_path", "target_relative_path", "sha256"}:
            raise ValueError("invalid archive relocation entry")
        if not all(isinstance(entry[key], str) for key in entry):
            raise ValueError("archive relocation entry fields must be strings")
        source = Path(entry["source_path"])
        source_key = _archive_path_key(source)
        if source_key in seen or not source.is_relative_to(source_root):
            raise ValueError("duplicate or out-of-root archive relocation source")
        seen.add(source_key)
        relative_text = str(entry["target_relative_path"])
        relative = Path(relative_text)
        if (
            not relative_text or relative.is_absolute() or relative.drive
            or "\\" in relative_text or ":" in relative_text
            or any(part in {"", ".", ".."} for part in relative_text.split("/"))
            or not re.fullmatch(r"[0-9a-f]{64}", str(entry["sha256"]))
        ):
            raise ValueError("invalid archive relocation target or content hash")
        target = archive_root / relative
        _require_no_archive_links(target)
        if not target.resolve().is_relative_to(archive_root):
            raise ValueError("archive relocation target escapes local archive root")
        if source_key == requested:
            matched = (target, str(entry["sha256"]))
    if matched is None:
        raise ValueError("historical archived_path has no exact relocation entry")
    return matched


def resolve_local_archive_path(archived_path: str | Path, archive_root: str | Path) -> Path:
    """Resolve a historical identity only inside the current trusted local archive."""
    _require_host_archive_path(archived_path)
    _require_host_archive_path(archive_root)
    if ".." in Path(archived_path).parts:
        raise ValueError("archived_path must not contain traversal")
    root = Path(os.path.abspath(archive_root))
    path = Path(os.path.abspath(archived_path))
    if path.is_relative_to(root):
        resolved = path.resolve()
        if not resolved.is_relative_to(root.resolve()):
            raise ValueError("archived_path is outside local archive root")
        return resolved
    target = _archive_relocation(path, root)[0]
    read_local_archive_bytes(path, root)
    return target


def read_local_archive_bytes(archived_path: str | Path, archive_root: str | Path) -> bytes:
    _require_host_archive_path(archived_path)
    _require_host_archive_path(archive_root)
    if ".." in Path(archived_path).parts:
        raise ValueError("archived_path must not contain traversal")
    root = Path(os.path.abspath(archive_root))
    historical = Path(os.path.abspath(archived_path))
    if historical.is_relative_to(root):
        path = historical.resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError("archived_path is outside local archive root")
        return path.read_bytes()
    path, expected_sha256 = _archive_relocation(historical, root)
    try:
        with path.open("rb") as handle:
            before = os.fstat(handle.fileno())
            payload = handle.read()
            after = os.fstat(handle.fileno())
    except FileNotFoundError as exc:
        raise ValueError("relocated archive target is missing") from exc
    _require_no_archive_links(path)
    current = path.stat()
    def identity(item):
        return item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns
    if not stat.S_ISREG(before.st_mode) or identity(before) != identity(after) or identity(after) != identity(current):
        raise ValueError("relocated archive changed during content verification")
    if hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise ValueError("relocated archive content hash does not match migration receipt")
    return payload


@dataclass
class ObjectStoreRepository:
    endpoint: str
    access_key: str
    secret_key: str
    bucket: str
    mode: str = "minio"
    local_archive_path: str = "data/archive"

    @staticmethod
    def _safe_component(value: str) -> str:
        sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
        return sanitized or "artifact"

    def _build_archived_filename(
        self,
        source_path: Path,
        source_key: str | None = None,
        ingest_batch_id: str | None = None,
    ) -> str:
        suffix = source_path.suffix
        safe_name = self._safe_component(source_path.name)
        safe_stem = safe_name[: -len(suffix)] if suffix and safe_name.endswith(suffix) else safe_name
        archive_key = source_key or source_path.as_posix()
        digest = hashlib.sha256(archive_key.encode("utf-8")).hexdigest()[:12]
        batch_component = ""
        if ingest_batch_id:
            batch_component = f"__{self._safe_component(ingest_batch_id)}"
        return f"{safe_stem}__{digest}{batch_component}{suffix}"

    @staticmethod
    def _new_archive_batch_id() -> str:
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        return f"archive-{timestamp}-{uuid4().hex[:8]}"

    def healthcheck(self) -> dict[str, object]:
        if self.mode == "local":
            archive_path = Path(self.local_archive_path)
            try:
                archive_path.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                return {
                    "ok": False,
                    "mode": "local",
                    "path": str(archive_path),
                    "bucket": self.bucket,
                    "error": str(exc),
                }
            return {
                "ok": archive_path.exists() and archive_path.is_dir(),
                "mode": "local",
                "path": str(archive_path),
                "bucket": self.bucket,
            }

        host, _, port_str = self.endpoint.partition(":")
        port = int(port_str) if port_str else 9000
        try:
            with socket.create_connection((host, port), timeout=0.2):
                tcp_reachable = True
        except OSError:
            tcp_reachable = False
        return {
            "ok": False,
            "mode": "minio",
            "endpoint": self.endpoint,
            "bucket": self.bucket,
            "tcp_reachable": tcp_reachable,
            "read_write_supported": False,
            "error": "MinIO object-store read/write operations are not implemented.",
        }

    def archive_file(
        self,
        source_path: Path,
        source_name: str,
        source_key: str | None = None,
        ingest_batch_id: str | None = None,
    ) -> dict[str, object]:
        if self.mode != "local":
            raise NotImplementedError("Phase 1 only implements local archive mode.")

        effective_ingest_batch_id = ingest_batch_id or self._new_archive_batch_id()
        archive_root = Path(self.local_archive_path).resolve()
        target_dir = archive_root / self._safe_component(source_name)
        files_dir = target_dir / "files"
        files_dir.mkdir(parents=True, exist_ok=True)
        target_path = files_dir / self._build_archived_filename(
            source_path,
            source_key=source_key,
            ingest_batch_id=effective_ingest_batch_id,
        )
        target_path.write_bytes(source_path.read_bytes())
        return {
            "mode": "local",
            "source_name": source_name,
            "source_path": str(source_path),
            "ingest_batch_id": effective_ingest_batch_id,
            "archived_path": str(target_path),
            "archived_at": datetime.now(UTC).isoformat(),
        }

    def archive_bytes(
        self,
        payload: bytes,
        source_name: str,
        source_key: str,
        ingest_batch_id: str | None = None,
        suffix: str = ".json",
    ) -> dict[str, object]:
        if self.mode != "local":
            raise NotImplementedError("Phase 1/2 thin slice only implements local archive mode.")

        effective_ingest_batch_id = ingest_batch_id or self._new_archive_batch_id()
        archive_root = Path(self.local_archive_path).resolve()
        target_dir = archive_root / self._safe_component(source_name)
        files_dir = target_dir / "files"
        files_dir.mkdir(parents=True, exist_ok=True)
        pseudo_source = Path(f"{self._safe_component(source_name)}{suffix}")
        target_path = files_dir / self._build_archived_filename(
            pseudo_source,
            source_key=source_key,
            ingest_batch_id=effective_ingest_batch_id,
        )
        target_path.write_bytes(payload)
        return {
            "mode": "local",
            "source_name": source_name,
            "source_path": source_key,
            "ingest_batch_id": effective_ingest_batch_id,
            "archived_path": str(target_path),
            "archived_at": datetime.now(UTC).isoformat(),
        }

    def build_vendor_snapshot_manifest(
        self,
        vendor_name: str,
        vendor_version: str,
        archived_path: str,
        snapshot_kind: str = "macro",
        capture_mode: str = "skeleton",
    ) -> dict[str, object]:
        return {
            "vendor_name": vendor_name,
            "vendor_version": vendor_version,
            "snapshot_kind": snapshot_kind,
            "archive_mode": self.mode,
            "archived_path": archived_path,
            "capture_mode": capture_mode,
            "read_target": "duckdb",
        }

    def read_archived_bytes(self, archived_path: str) -> bytes:
        if self.mode != "local":
            raise NotImplementedError("read_archived_bytes is only implemented for local archive mode.")
        return read_local_archive_bytes(archived_path, self.local_archive_path)

    @contextmanager
    def open_archived_binary(self, archived_path: str):
        """Yield a readable binary stream for an archived object (local mode). Caller must not use the handle outside the with-block."""
        if self.mode != "local":
            raise NotImplementedError("open_archived_binary is only implemented for local archive mode.")
        archive_root = Path(self.local_archive_path).resolve()
        path = Path(os.path.abspath(archived_path))
        if path.is_relative_to(archive_root):
            with self._resolve_archived_path(archived_path).open("rb") as handle:
                yield handle
        else:
            with io.BytesIO(self.read_archived_bytes(archived_path)) as handle:
                yield handle

    def _resolve_archived_path(self, archived_path: str) -> Path:
        return resolve_local_archive_path(archived_path, self.local_archive_path)
