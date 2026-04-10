import socket
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
from uuid import uuid4


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
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
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
                ok = True
        except OSError:
            ok = False
        return {"ok": ok, "mode": "minio", "endpoint": self.endpoint, "bucket": self.bucket}

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
        archive_root = Path(self.local_archive_path)
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
            "archived_at": datetime.now(timezone.utc).isoformat(),
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
        archive_root = Path(self.local_archive_path)
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
            "archived_at": datetime.now(timezone.utc).isoformat(),
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
        path = Path(archived_path)
        if not path.is_file():
            raise FileNotFoundError(str(path))
        return path.read_bytes()

    @contextmanager
    def open_archived_binary(self, archived_path: str):
        """Yield a readable binary stream for an archived object (local mode). Caller must not use the handle outside the with-block."""
        if self.mode != "local":
            raise NotImplementedError("open_archived_binary is only implemented for local archive mode.")
        path = Path(archived_path)
        if not path.is_file():
            raise FileNotFoundError(str(path))
        with path.open("rb") as handle:
            yield handle
