"""Local raw zone: immutable vendor payloads under ``data/raw/{vendor}/{batch}/{filename}``."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class RawZoneRepository:
    """Append-only raw files; no overwrite when existing content differs."""

    local_raw_path: str = "data/raw"

    @staticmethod
    def _safe_component(value: str) -> str:
        sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
        return sanitized or "artifact"

    def _target_path(self, vendor_name: str, ingest_batch_id: str, filename: str) -> Path:
        root = Path(self.local_raw_path)
        return (
            root
            / self._safe_component(vendor_name)
            / self._safe_component(ingest_batch_id)
            / self._safe_component(filename)
        )

    def archive_bytes(
        self,
        vendor_name: str,
        ingest_batch_id: str,
        filename: str,
        payload: bytes,
    ) -> dict[str, object]:
        target = self._target_path(vendor_name, ingest_batch_id, filename)
        digest = hashlib.sha256(payload).hexdigest()
        if target.exists():
            existing = target.read_bytes()
            if existing == payload:
                archived_at = datetime.fromtimestamp(target.stat().st_mtime, tz=UTC).isoformat()
                return {
                    "raw_zone_path": str(target),
                    "archived_at": archived_at,
                    "sha256": digest,
                }
            raise FileExistsError(
                f"raw zone path exists with different content: {target}",
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        archived_at = datetime.now(UTC).isoformat()
        return {
            "raw_zone_path": str(target),
            "archived_at": archived_at,
            "sha256": digest,
        }

    def archive_file(
        self,
        vendor_name: str,
        ingest_batch_id: str,
        source_path: Path,
    ) -> dict[str, object]:
        payload = source_path.read_bytes()
        return self.archive_bytes(vendor_name, ingest_batch_id, source_path.name, payload)

    def read_bytes(self, raw_zone_path: str) -> bytes:
        path = Path(raw_zone_path)
        if not path.is_file():
            raise FileNotFoundError(str(path))
        return path.read_bytes()

    def healthcheck(self) -> dict[str, object]:
        raw_path = Path(self.local_raw_path)
        try:
            raw_path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return {
                "ok": False,
                "mode": "local_raw",
                "path": str(raw_path),
                "error": str(exc),
            }
        return {
            "ok": raw_path.exists() and raw_path.is_dir(),
            "mode": "local_raw",
            "path": str(raw_path),
        }
