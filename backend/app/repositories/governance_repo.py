from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass
from pathlib import Path

from backend.app.governance.locks import LockDefinition, acquire_lock


CACHE_BUILD_RUN_STREAM = "cache_build_run"
CACHE_MANIFEST_STREAM = "cache_manifest"
SOURCE_MANIFEST_STREAM = "source_manifest"
SNAPSHOT_BUILD_RUN_STREAM = "snapshot_build_run"
SNAPSHOT_MANIFEST_STREAM = "snapshot_manifest"
VENDOR_SNAPSHOT_MANIFEST_STREAM = "vendor_snapshot_manifest"
VENDOR_VERSION_REGISTRY_STREAM = "vendor_version_registry"


@dataclass
class GovernanceRepository:
    base_dir: Path | str = Path("data/governance")

    def __post_init__(self) -> None:
        self.base_dir = Path(self.base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def append(self, stream: str, payload: dict[str, object]) -> Path:
        with acquire_lock(self._batch_lock(), base_dir=self.base_dir):
            return self._append_unlocked(stream, payload)

    def _append_unlocked(self, stream: str, payload: dict[str, object]) -> Path:
        target = self.base_dir / f"{stream}.jsonl"
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return target

    def append_many_atomic(self, entries: list[tuple[str, dict[str, object]]]) -> list[Path]:
        with acquire_lock(self._batch_lock(), base_dir=self.base_dir):
            original_sizes: dict[Path, int] = {}
            written_paths: list[Path] = []
            try:
                for stream, payload in entries:
                    target = self.base_dir / f"{stream}.jsonl"
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if target not in original_sizes:
                        original_sizes[target] = target.stat().st_size if target.exists() else 0
                    written_paths.append(self._append_unlocked(stream, payload))
                return written_paths
            except Exception:
                for target, size in original_sizes.items():
                    if not target.exists():
                        continue
                    with target.open("r+b") as handle:
                        handle.truncate(size)
                    if size == 0:
                        target.unlink(missing_ok=True)
                raise

    def read_all(self, stream: str) -> list[dict[str, object]]:
        with acquire_lock(self._batch_lock(), base_dir=self.base_dir):
            target = self.base_dir / f"{stream}.jsonl"
            if not target.exists():
                return []
            return [
                json.loads(line)
                for line in target.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

    def _batch_lock(self) -> LockDefinition:
        digest = hashlib.sha256(str(self.base_dir).encode("utf-8")).hexdigest()[:8]
        return LockDefinition(
            key=f"lock:governance:jsonl:{digest}",
            ttl_seconds=30,
        )
